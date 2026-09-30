"""Coordenador de atualização de um servidor environmental-monitoring."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnvmonClient, EnvmonError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EnvmonCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Guarda a última resposta, com os sensores indexados por id."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: EnvmonClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.base_url}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.fetch()
        except EnvmonError as err:
            raise UpdateFailed(f"Erro ao ler {self.client.base_url}: {err}") from err
        return {"device": data["device"], "sensors": {s["id"]: s for s in data["sensors"]}}
