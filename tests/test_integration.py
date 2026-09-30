from pathlib import Path

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.envmon.const import DOMAIN

FIXTURE = (Path(__file__).parent / "fixtures" / "sensors.json").read_text()
HOST, PORT = "10.65.240.10", 5000
URL = f"http://{HOST}:{PORT}/api/v1/sensors"


async def test_config_flow(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(URL, text=FIXTURE, headers={"Content-Type": "application/json"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Raspberry Pi"
    assert result["result"].unique_id == "raspberrypi-envmon"


async def test_config_flow_cannot_connect(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(URL, status=500)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_setup(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(URL, text=FIXTURE, headers={"Content-Type": "application/json"})
    entry = MockConfigEntry(
        domain=DOMAIN, title="Raspberry Pi", unique_id="raspberrypi-envmon",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    devices = {d.name: d for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)}
    assert set(devices) == {"Raspberry Pi", "Sensor 1", "Sensor 2"}
    assert devices["Sensor 1"].via_device_id == devices["Raspberry Pi"].id
    assert devices["Sensor 1"].model == "DHT11"

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    for e in entities:
        print(e.entity_id, hass.states.get(e.entity_id).state)
    assert len(entities) == 4

    temp = hass.states.get("sensor.sensor_1_temperature")
    assert temp.state == "23.9"
    assert temp.attributes["unit_of_measurement"] == "°C"
    assert hass.states.get("sensor.sensor_1_humidity").state == "54.5"
    # Sensor 2 está "stale" na API: não mostra valor velho como atual.
    assert hass.states.get("sensor.sensor_2_temperature").state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
