"""Fluxo de configuração: host e porta do servidor no Raspberry Pi."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnvmonClient, EnvmonError
from .const import DEFAULT_PORT, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    }
)


class EnvmonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adiciona um servidor environmental-monitoring."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = EnvmonClient(
                async_get_clientsession(self.hass), user_input[CONF_HOST], user_input[CONF_PORT]
            )
            try:
                data = await client.fetch()
            except EnvmonError:
                errors["base"] = "cannot_connect"
            else:
                device = data["device"]
                await self.async_set_unique_id(device["id"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=device["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )
