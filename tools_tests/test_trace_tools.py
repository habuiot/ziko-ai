from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from homeassistant.core import Context
from homeassistant.helpers.llm import ToolInput
from test_history_tools import tool, context


class Traces:
    def __init__(self, raw):
        self.raw = raw
        self.calls = 0
    async def trace(self, key, run_id):
        self.calls += 1
        return self.raw
    async def traces(self, key):
        self.calls += 1
        return [self.raw]


async def owner(house, monkeypatch):
    monkeypatch.setattr(house.hass.auth, 'async_get_user', AsyncMock(return_value=SimpleNamespace(is_active=True, is_admin=True)))
    house.hass.states.async_set('automation.evening', 'on', {'id': 'evening'})


async def test_read_trace_projects_only_allowed_steps(house, monkeypatch):
    await owner(house, monkeypatch)
    raw = {'run_id': 'run', 'config': {'actions': [{'target': {'entity_id': 'sensor.inside'}}]},
           'trace': {'action/0': [{'changed_variables': {'secret': 'private'}, 'result': {'result': True}}]}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True, owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert not result.error
    assert 'private' not in str(result.data)
    assert result.data['trace']['steps'][0]['result']['result'] is True


async def test_mixed_house_trace_is_denied(house, monkeypatch):
    await owner(house, monkeypatch)
    raw = {'config': {'actions': [{'target': {'entity_id': ['sensor.inside', 'sensor.outside']}}]}, 'trace': {}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True, owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert result.error


async def test_anonymous_trace_cannot_use_owner_named_in_text(house, monkeypatch):
    await owner(house, monkeypatch)
    adapter = Traces({'config': {}, 'trace': {}})
    t, _ = tool(house, 'ziko_ha_tools__read_trace', adapter, diagnostics=True, owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_id': 'automation.evening', 'run_id': 'run'}), context())
    assert result.error and adapter.calls == 0


async def test_trace_dynamic_targets_are_not_assumed_safe(house, monkeypatch):
    await owner(house, monkeypatch)
    raw = {'config': {'actions': [{'target': {'entity_id': '{{ dynamic_target }}'}}]}, 'trace': {}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True, owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert result.error


async def test_trace_without_verifiable_config_is_denied(house, monkeypatch):
    await owner(house, monkeypatch)
    raw = {'trace': {'action/0': [{'result': {'result': True}}]}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True,
                owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name,
        {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert result.error


async def test_device_target_with_external_entity_is_denied(house, monkeypatch):
    await owner(house, monkeypatch)
    device_id = house.reg.async_get('climate.radiator').device_id
    house.reg.async_update_entity('sensor.outside', device_id=device_id)
    raw = {'config': {'actions': [{'device_id': device_id}]}, 'trace': {}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True,
                owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name,
        {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert result.error


@pytest.mark.parametrize('target_key', ['label_id', 'floor_id'])
async def test_unresolved_target_forms_are_denied(house, monkeypatch, target_key):
    await owner(house, monkeypatch)
    raw = {'config': {'actions': [{'target': {target_key: 'outside_house'}}]}, 'trace': {}}
    t, _ = tool(house, 'ziko_ha_tools__read_trace', Traces(raw), diagnostics=True,
                owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name,
        {'entity_id': 'automation.evening', 'run_id': 'run'}), context('owner'))
    assert result.error


async def test_trace_list_revalidates_earlier_buffered_runs_after_final_await(house, monkeypatch):
    await owner(house, monkeypatch)
    raw = {'config': {'actions': [{'target': {'entity_id': 'sensor.inside'}}]}, 'trace': {},
           'error': 'Could not read sensor.inside'}
    class TwoTraces:
        async def traces(self, key):
            return [{'run_id': 'first'}, {'run_id': 'second'}]
        async def trace(self, key, run_id):
            if run_id == 'second':
                house.reg.async_update_entity('sensor.inside', area_id=house.outside)
                return {'config': {'actions': [{'target': {'entity_id': 'climate.radiator'}}]},
                        'trace': {}, 'run_id': run_id}
            return {**raw, 'run_id': run_id}
    t, _ = tool(house, 'ziko_ha_tools__list_traces', TwoTraces(), diagnostics=True,
                owner_user_id='owner', automations=['automation.evening'])
    result = await t.async_call(house.hass, ToolInput(t.name,
        {'entity_id': 'automation.evening'}), context('owner'))
    assert not result.error
    assert result.data['excluded_scope_unverifiable'] == 1
    assert 'sensor.inside' not in str(result.data)
