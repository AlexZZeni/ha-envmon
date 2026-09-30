"""Constantes da integração Environmental Monitoring."""

from datetime import timedelta

DOMAIN = "envmon"

DEFAULT_PORT = 5000

# O servidor lê os sensores a cada 30 s; consultar mais rápido não traz nada novo.
UPDATE_INTERVAL = timedelta(seconds=30)
