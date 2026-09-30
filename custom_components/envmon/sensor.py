"""Temperatura e umidade de cada sensor DHT."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EnvmonConfigEntry
from .const import DOMAIN
from .coordinator import EnvmonCoordinator


@dataclass(frozen=True, kw_only=True)
class EnvmonSensorDescription(SensorEntityDescription):
    """Campo da API que alimenta o sensor."""

    value_fn: Callable[[dict[str, Any]], float | None]


SENSORS: tuple[EnvmonSensorDescription, ...] = (
    EnvmonSensorDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda sensor: sensor.get("temperature"),
    ),
    EnvmonSensorDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda sensor: sensor.get("humidity"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvmonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Cria temperatura e umidade para cada sensor que o servidor expõe."""
    coordinator = entry.runtime_data
    async_add_entities(
        EnvmonSensor(coordinator, sensor_id, description)
        for sensor_id in coordinator.data["sensors"]
        for description in SENSORS
    )


class EnvmonSensor(CoordinatorEntity[EnvmonCoordinator], SensorEntity):
    """Uma grandeza de um sensor DHT; cada sensor é um dispositivo."""

    _attr_has_entity_name = True
    entity_description: EnvmonSensorDescription

    def __init__(
        self,
        coordinator: EnvmonCoordinator,
        sensor_id: str,
        description: EnvmonSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_id = sensor_id
        hub_id = coordinator.data["device"]["id"]
        sensor = coordinator.data["sensors"][sensor_id]
        self._attr_unique_id = f"{hub_id}_{sensor_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub_id}_{sensor_id}")},
            name=sensor["name"],
            manufacturer="Aosong",
            model=sensor["model"],
            via_device=(DOMAIN, hub_id),
        )

    @property
    def _sensor(self) -> dict[str, Any] | None:
        return self.coordinator.data["sensors"].get(self._sensor_id)

    @property
    def available(self) -> bool:
        # Valor velho (sensor falhando há vários ciclos) não é mostrado como atual.
        sensor = self._sensor
        return super().available and sensor is not None and sensor.get("status") == "ok"

    @property
    def native_value(self) -> float | None:
        sensor = self._sensor
        return self.entity_description.value_fn(sensor) if sensor else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        sensor = self._sensor
        if sensor is None:
            return None
        return {"pin": sensor.get("pin"), "last_update": sensor.get("last_update")}
