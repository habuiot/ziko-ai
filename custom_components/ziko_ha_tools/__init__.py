"""Read-only household tools for native Home Assistant Assist APIs."""
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN
from .scope import Scope

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass, entry):
    entry.runtime_data = Scope(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.runtime_data
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    if getattr(entry, 'runtime_data', None):
        entry.runtime_data.active = False
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    entry.runtime_data.active = False
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
