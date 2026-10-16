"""Read-only household tools for native Home Assistant Assist APIs."""
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN
from .scope import Scope

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass, entry):
    entry.runtime_data = Scope(hass, entry)
    from .memory import Memory
    entry.runtime_data.memory = Memory(hass, entry.entry_id)
    await entry.runtime_data.memory.async_load()
    from .bridge import prepare_bridge
    await prepare_bridge(entry.runtime_data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.runtime_data
    from .automation_editor import async_setup_guarded_actions
    async_setup_guarded_actions(hass)
    entry.async_on_unload(entry.add_update_listener(_reload))
    from .operator import async_setup_panel
    await async_setup_panel(hass)
    return True


async def _reload(hass, entry):
    if getattr(entry, 'runtime_data', None):
        entry.runtime_data.active = False
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    entry.runtime_data.active = False
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if getattr(hass, 'http', None):
        from homeassistant.components import frontend
        frontend.async_remove_panel(hass, 'ziko-tools')
    return True
