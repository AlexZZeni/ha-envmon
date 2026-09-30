import time

import pytest

from app import create_app
from sensors import FakeBackend, SensorConfig, SensorReader, parse_sensors

DEVICE = {"id": "test", "name": "Test", "version": "0"}


class FlakyBackend:
    """Falha `failures` vezes antes de ler."""

    def __init__(self, failures, value=(22.0, 50.0)):
        self.failures = failures
        self.value = value
        self.calls = 0

    def read(self, sensor):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("Checksum did not validate")
        return self.value

    def close(self):
        pass


def make_reader(backend, **kwargs):
    kwargs.setdefault("retry_delay", 0)
    return SensorReader(backend, parse_sensors("s1:D4:DHT11:Rack,s2:D25:DHT22"), **kwargs)


def test_parse_sensors():
    sensors = parse_sensors("sensor_1:d4:dht11, sensor_2:D25:DHT22:Sala")
    assert sensors == [
        SensorConfig("sensor_1", "Sensor 1", "D4", "DHT11"),
        SensorConfig("sensor_2", "Sala", "D25", "DHT22"),
    ]


@pytest.mark.parametrize("spec", ["", "s1:D4", "s1:D4:BME280", "s1:D4:DHT11,s1:D5:DHT11"])
def test_parse_sensors_invalid(spec):
    with pytest.raises(ValueError):
        parse_sensors(spec)


def test_retries_until_success():
    backend = FlakyBackend(failures=2)
    reader = make_reader(backend)
    reader.read_once("s1")
    s1 = reader.snapshot()[0]
    assert (s1["status"], s1["temperature"], s1["humidity"]) == ("ok", 22.0, 50.0)
    assert backend.calls == 3


def test_all_retries_fail_keeps_last_good_value():
    backend = FlakyBackend(failures=0)
    reader = make_reader(backend)
    reader.read_once("s1")
    backend.failures, backend.calls = 99, 0
    reader.read_once("s1")
    s1 = reader.snapshot()[0]
    assert s1["temperature"] == 22.0
    assert s1["consecutive_errors"] == 1
    assert "Checksum" in s1["last_error"]


def test_out_of_range_is_rejected():
    reader = make_reader(FlakyBackend(failures=0, value=(22.0, 250.0)))
    reader.read_once("s1")
    assert reader.snapshot()[0]["status"] == "unavailable"


def test_stale_after_no_success(monkeypatch):
    reader = make_reader(FlakyBackend(failures=0), interval=1)
    reader.read_once("s1")
    later = time.monotonic() + reader.stale_after + 1
    monkeypatch.setattr("sensors.time.monotonic", lambda: later)
    assert reader.snapshot()[0]["status"] == "stale"


def test_api():
    reader = make_reader(FakeBackend())
    reader.read_once("s1")
    client = create_app(reader, DEVICE).test_client()

    body = client.get("/api/v1/sensors").get_json()
    assert body["device"] == DEVICE
    assert [s["id"] for s in body["sensors"]] == ["s1", "s2"]
    assert body["sensors"][0]["status"] == "ok"
    assert body["sensors"][1]["status"] == "unavailable"

    assert client.get("/api/v1/sensors/s1").get_json()["name"] == "Rack"
    assert client.get("/api/v1/sensors/nope").status_code == 404
    # Thread não iniciada: health reporta erro.
    assert client.get("/health").status_code == 503
