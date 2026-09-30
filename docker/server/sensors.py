"""Leitura dos sensores DHT em segundo plano.

Uma única thread fala com o GPIO: o DHT não tolera leituras concorrentes, e
leituras sob demanda (a cada request) falham com frequência. A API só devolve
o último valor bom.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import random
import threading
import time
from typing import Any, Protocol

_LOGGER = logging.getLogger(__name__)

MODELS = ("DHT11", "DHT22")

# Leituras fora disso são ruído no barramento, não clima.
TEMPERATURE_RANGE = (-40.0, 80.0)
HUMIDITY_RANGE = (0.0, 100.0)


@dataclass(frozen=True)
class SensorConfig:
    id: str
    name: str
    pin: str
    model: str


def parse_sensors(spec: str) -> list[SensorConfig]:
    """Lê `id:pino:modelo[:nome]` separados por vírgula.

    Ex.: `sensor_1:D4:DHT11:Rack,sensor_2:D25:DHT22:Sala`
    """
    sensors: list[SensorConfig] = []
    for item in filter(None, (part.strip() for part in spec.split(","))):
        parts = item.split(":", 3)
        if len(parts) < 3:
            raise ValueError(f"Sensor inválido {item!r}: use id:pino:modelo[:nome]")
        sensor_id, pin, model = parts[0].strip(), parts[1].strip().upper(), parts[2].strip().upper()
        if model not in MODELS:
            raise ValueError(f"Modelo {model!r} não suportado em {item!r}: use {' ou '.join(MODELS)}")
        name = parts[3].strip() if len(parts) == 4 else sensor_id.replace("_", " ").title()
        sensors.append(SensorConfig(sensor_id, name, pin, model))

    ids = [s.id for s in sensors]
    if not ids:
        raise ValueError("Nenhum sensor configurado")
    if len(set(ids)) != len(ids):
        raise ValueError(f"IDs de sensor repetidos: {ids}")
    return sensors


class Backend(Protocol):
    def read(self, sensor: SensorConfig) -> tuple[float, float]: ...
    def close(self) -> None: ...


class DhtBackend:
    """Sensores DHT reais via Adafruit Blinka (libgpiod)."""

    def __init__(self) -> None:
        import adafruit_dht
        import board

        self._adafruit_dht = adafruit_dht
        self._board = board
        self._devices: dict[str, Any] = {}

    def _device(self, sensor: SensorConfig) -> Any:
        # O device fica aberto entre leituras: recriar a cada leitura é a
        # principal causa de falhas com DHT no Raspberry Pi.
        device = self._devices.get(sensor.id)
        if device is None:
            device_class = getattr(self._adafruit_dht, sensor.model)
            device = device_class(getattr(self._board, sensor.pin))
            self._devices[sensor.id] = device
        return device

    def read(self, sensor: SensorConfig) -> tuple[float, float]:
        device = self._device(sensor)
        try:
            temperature, humidity = device.temperature, device.humidity
        except RuntimeError:
            # Checksum/timeout: comum no DHT, basta tentar de novo.
            raise
        except Exception:
            # Erro de GPIO: reabre o device na próxima tentativa.
            self._reset(sensor.id)
            raise
        if temperature is None or humidity is None:
            raise RuntimeError("Leitura vazia")
        return float(temperature), float(humidity)

    def _reset(self, sensor_id: str) -> None:
        device = self._devices.pop(sensor_id, None)
        if device is not None:
            try:
                device.exit()
            except Exception:  # noqa: BLE001 - só limpeza
                pass

    def close(self) -> None:
        for sensor_id in list(self._devices):
            self._reset(sensor_id)


class FakeBackend:
    """Valores simulados, para desenvolvimento fora do Raspberry Pi."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[float, float]] = {}

    def read(self, sensor: SensorConfig) -> tuple[float, float]:
        temperature, humidity = self._values.get(sensor.id, (24.0, 55.0))
        temperature = min(max(temperature + random.uniform(-0.3, 0.3), 15.0), 35.0)
        humidity = min(max(humidity + random.uniform(-1.0, 1.0), 30.0), 80.0)
        self._values[sensor.id] = (temperature, humidity)
        return temperature, humidity

    def close(self) -> None:
        pass


@dataclass
class _State:
    config: SensorConfig
    temperature: float | None = None
    humidity: float | None = None
    last_update: datetime | None = None
    last_success: float | None = None  # time.monotonic()
    last_error: str | None = None
    consecutive_errors: int = 0


class SensorReader(threading.Thread):
    """Lê todos os sensores a cada `interval` segundos."""

    def __init__(
        self,
        backend: Backend,
        sensors: list[SensorConfig],
        interval: float = 30.0,
        retries: int = 3,
        retry_delay: float = 2.5,
    ) -> None:
        super().__init__(name="sensor-reader", daemon=True)
        self.backend = backend
        self.interval = interval
        self.retries = retries
        self.retry_delay = retry_delay
        # Sem leitura boa nesse tempo, o valor é considerado velho.
        self.stale_after = interval * 3 + retries * retry_delay
        self._states = {s.id: _State(s) for s in sensors}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            for state in self._states.values():
                self.read_once(state.config.id)
            self._stop_event.wait(self.interval)

    def stop(self) -> None:
        self._stop_event.set()

    def read_once(self, sensor_id: str) -> None:
        state = self._states[sensor_id]
        error: Exception | None = None
        for attempt in range(self.retries):
            if attempt and self._stop_event.wait(self.retry_delay):
                return
            try:
                temperature, humidity = self.backend.read(state.config)
            except Exception as err:  # noqa: BLE001 - qualquer falha vira nova tentativa
                error = err
                continue
            if not (
                TEMPERATURE_RANGE[0] <= temperature <= TEMPERATURE_RANGE[1]
                and HUMIDITY_RANGE[0] <= humidity <= HUMIDITY_RANGE[1]
            ):
                error = ValueError(f"Leitura fora da faixa: {temperature} °C, {humidity} %")
                continue
            with self._lock:
                state.temperature = round(temperature, 1)
                state.humidity = round(humidity, 1)
                state.last_update = datetime.now(UTC)
                state.last_success = time.monotonic()
                state.last_error = None
                state.consecutive_errors = 0
            return

        with self._lock:
            state.last_error = f"{type(error).__name__}: {error}"
            state.consecutive_errors += 1
        _LOGGER.warning("Falha ao ler %s (%s): %s", sensor_id, state.config.pin, state.last_error)

    def _status(self, state: _State) -> str:
        if state.last_success is None:
            return "unavailable"
        if time.monotonic() - state.last_success > self.stale_after:
            return "stale"
        return "ok"

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": s.config.id,
                    "name": s.config.name,
                    "model": s.config.model,
                    "pin": s.config.pin,
                    "status": self._status(s),
                    "temperature": s.temperature,
                    "humidity": s.humidity,
                    "last_update": s.last_update.isoformat() if s.last_update else None,
                    "last_error": s.last_error,
                    "consecutive_errors": s.consecutive_errors,
                }
                for s in self._states.values()
            ]
