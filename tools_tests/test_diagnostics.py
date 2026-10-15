from types import SimpleNamespace
from unittest.mock import AsyncMock
from homeassistant.helpers.llm import ToolInput
from test_history_tools import tool, context


class Errors:
    def __init__(self):
        self.calls = 0
        self.after_read = None
    async def errors(self, source, limit):
        self.calls += 1
        if self.after_read:
            self.after_read()
        return {'entries': [{'message': 'token=secret-token'}]}


async def test_owner_error_query_masks_credential(house, monkeypatch):
    monkeypatch.setattr(house.hass.auth, 'async_get_user', AsyncMock(return_value=SimpleNamespace(is_active=True, is_admin=True)))
    t, _ = tool(house, 'ziko_ha_tools__query_errors', Errors(), diagnostics=True, owner_user_id='owner')
    result = await t.async_call(house.hass, ToolInput(t.name, {}), context('owner'))
    assert not result.error and 'secret-token' not in str(result.data)


async def test_diagnostic_permission_revoked_during_query(house, monkeypatch):
    user = SimpleNamespace(is_active=True, is_admin=True)
    monkeypatch.setattr(house.hass.auth, 'async_get_user', AsyncMock(return_value=user))
    adapter = Errors()
    adapter.after_read = lambda: setattr(user, 'is_admin', False)
    t, _ = tool(house, 'ziko_ha_tools__query_errors', adapter, diagnostics=True, owner_user_id='owner')
    result = await t.async_call(house.hass, ToolInput(t.name, {}), context('owner'))
    assert result.error and 'entries' not in result.data


async def test_no_arbitrary_file_path_or_unsupported_source(house, monkeypatch):
    monkeypatch.setattr(house.hass.auth, 'async_get_user', AsyncMock(return_value=SimpleNamespace(is_active=True, is_admin=True)))
    adapter = Errors()
    t, _ = tool(house, 'ziko_ha_tools__query_errors', adapter, diagnostics=True, owner_user_id='owner')
    result = await t.async_call(house.hass, ToolInput(t.name, {'source': '/etc/passwd'}), context('owner'))
    assert result.error and adapter.calls == 0
