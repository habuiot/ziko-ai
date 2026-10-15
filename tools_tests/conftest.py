import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant import auth, config_entries
from homeassistant.components.homeassistant.exposed_entities import ExposedEntities
from homeassistant.components.homeassistant.const import DATA_EXPOSED_ENTITIES
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest_asyncio.fixture
async def house(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config.time_zone = 'Europe/Budapest'
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    dr.async_setup(hass)
    await ar.async_get(hass).async_load()
    await dr.async_load(hass)
    await er.async_load(hass)
    hass.auth = await auth.auth_manager_from_config(hass, [], [])
    exposed = ExposedEntities(hass)
    await exposed.async_initialize()
    hass.data[DATA_EXPOSED_ENTITIES] = exposed
    area = ar.async_get(hass).async_create('House room')
    outside = ar.async_get(hass).async_create('Other house')
    entry = config_entries.ConfigEntry(version=1, minor_version=1, domain='test', title='Test',
        data={}, options={}, source='user', unique_id='test', discovery_keys={}, subentries_data=())
    # Register a fixture-only entry without loading a fictitious integration.
    hass.config_entries._entries[entry.entry_id] = entry
    dev = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={('test', 'radiator')})
    dr.async_get(hass).async_update_device(dev.id, area_id=area.id)
    reg = er.async_get(hass)
    climate = reg.async_get_or_create('climate', 'test', 'radiator', suggested_object_id='radiator', device_id=dev.id)
    reg.async_get_or_create('sensor', 'test', 'inside', suggested_object_id='inside')
    reg.async_get_or_create('sensor', 'test', 'outside', suggested_object_id='outside')
    reg.async_update_entity('sensor.inside', area_id=area.id)
    reg.async_update_entity('sensor.outside', area_id=outside.id)
    hass.states.async_set('climate.radiator', 'heat', {'current_temperature': 28.1, 'temperature': 19})
    hass.states.async_set('sensor.inside', '28', {'unit_of_measurement': '°C'})
    hass.states.async_set('sensor.outside', '29')
    yield SimpleNamespace(hass=hass, area=area.id, outside=outside.id, reg=reg)
    await hass.async_stop(force=True)

