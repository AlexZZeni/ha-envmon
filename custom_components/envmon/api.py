"""Cliente da API do servidor environmental-monitoring (Raspberry Pi)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class EnvmonError(Exception):
    """Falha ao falar com o servidor."""


class EnvmonClient:
    """Acesso a um servidor por host e porta."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self.base_url = f"http://{host}:{port}"

    async def fetch(self) -> dict[str, Any]:
        """Dispositivo e última leitura de cada sensor."""
        try:
            async with self._session.get(f"{self.base_url}/api/v1/sensors", timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise EnvmonError(str(err)) from err
        if not isinstance(data, dict) or "device" not in data or "sensors" not in data:
            raise EnvmonError("Resposta inesperada do servidor")
        return data
