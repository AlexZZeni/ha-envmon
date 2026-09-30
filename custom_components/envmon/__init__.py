"""Integração Environmental Monitoring: sensores DHT de um Raspberry Pi."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnvmonClient
from .const import DOMAIN
from .coordinator import EnvmonCoordinator

PLATFORMS = [Platform.SENSOR]

type EnvmonConfigEntry = ConfigEntry[EnvmonCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EnvmonConfigEntry) -> bool:
    """Configura um servidor e registra o Pi como dispositivo pai dos sensores."""
    client = EnvmonClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = EnvmonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    device = coordinator.data["device"]
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device["id"])},
        name=device["name"],
        manufacturer="Raspberry Pi",
        model="Environmental Monitoring",
        sw_version=device.get("version"),
        configuration_url=client.base_url,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnvmonConfigEntry) -> bool:
    """Remove um servidor."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
