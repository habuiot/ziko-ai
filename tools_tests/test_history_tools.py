from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from homeassistant.core import Context
from homeassistant.helpers.llm import LLMContext, ToolInput
from probatio import to_openapi
from homeassistant.helpers.llm import selector_serializer

NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)


def context(user=None):
    return LLMContext(platform='codex_assist', context=Context(user_id=user), language='hu', assistant='conversation', device_id=None)


def tool(house, name, adapter, **config):
    from custom_components.ziko_ha_tools.scope import Scope
    from custom_components.ziko_ha_tools.tools import build_tools
    s = Scope(house.hass, {'areas': [house.area], 'read_unexposed': True, **config})
    tools = build_tools(s, context('owner'), adapter=adapter)
    return next(t for t in tools if t.name == name), s


class History:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.after_read = None

    async def history(self, entity_ids, start, end):
        self.calls.append(entity_ids)
        if self.after_read:
            self.after_read()
        return {eid: self.rows for eid in entity_ids}


async def test_measured_attribute_query_finds_latest_over_27(house):
    start = NOW - timedelta(hours=4)
    rows = [{'state': 'heat', 'attributes': {'current_temperature': 28 if i == 201 else 25, 'temperature': 19},
             'last_updated': (start + timedelta(seconds=i)).isoformat()} for i in range(400)]
    t, _ = tool(house, 'ziko_ha_tools__query_history', History(rows))
    result = await t.async_call(house.hass, ToolInput('ziko_ha_tools__query_history', {
        'entity_ids': ['climate.radiator'], 'attribute': 'current_temperature',
        'start_time': start.isoformat(), 'end_time': NOW.isoformat(),
        'operator': 'gt', 'value': 27, 'limit': 10}), context())
    assert not result.error
    assert result.data['entities']['climate.radiator']['last_match']['value'] == 28
    assert result.data['entities']['climate.radiator']['last_match']['time'] == rows[201]['last_updated']


async def test_cross_house_rejected_before_database_access(house):
    adapter = History([])
    t, _ = tool(house, 'ziko_ha_tools__query_history', adapter)
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_ids': ['sensor.outside']}), context())
    assert result.error and not adapter.calls


async def test_revoked_scope_never_returns_buffered_history(house):
    adapter = History([{'state': '28', 'last_updated': NOW.isoformat()}])
    t, s = tool(house, 'ziko_ha_tools__query_history', adapter)
    adapter.after_read = lambda: setattr(s, 'active', False)
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_ids': ['sensor.inside']}), context())
    assert result.error and 'entities' not in result.data


async def test_logbook_requires_explicit_entities(house):
    t, _ = tool(house, 'ziko_ha_tools__query_logbook', History([]))
    result = await t.async_call(house.hass, ToolInput(t.name, {}), context())
    assert result.error


def test_tool_schemas_work_with_codex_probatio_conversion(house):
    from custom_components.ziko_ha_tools.scope import Scope
    from custom_components.ziko_ha_tools.tools import build_tools
    s = Scope(house.hass, {'areas': [house.area], 'read_unexposed': True})
    tools = build_tools(s, context())
    assert {t.name for t in tools} == {'ziko_ha_tools__list_sources', 'ziko_ha_tools__query_history', 'ziko_ha_tools__query_statistics', 'ziko_ha_tools__query_logbook'}
    for t in tools:
        converted = to_openapi(t.parameters, custom_serializer=selector_serializer)
        assert converted['type'] == 'object'
        assert t.integration == 'ziko_ha_tools'
        assert t.annotations.read_only and not t.annotations.destructive



async def test_high_frequency_limit_is_not_reported_as_complete(house):
    from custom_components.ziko_ha_tools.const import MAX_ROWS
    start = NOW - timedelta(days=1)
    rows = [{'state': 'heat', 'attributes': {'current_temperature': 28 if i == 0 else 25},
             'last_updated': (start + timedelta(seconds=i)).isoformat()} for i in range(MAX_ROWS + 1)]
    t, _ = tool(house, 'ziko_ha_tools__query_history', History(rows))
    result = await t.async_call(house.hass, ToolInput(t.name, {
        'entity_ids': ['climate.radiator'], 'attribute': 'current_temperature',
        'start_time': start.isoformat(), 'end_time': NOW.isoformat(),
        'operator': 'gt', 'value': 27, 'limit': 10}), context())
    assert not result.error
    assert result.data['query_truncated'] and not result.data['query_complete']
    assert result.data['entities']['climate.radiator']['processed_records'] <= MAX_ROWS
    assert result.data['entities']['climate.radiator']['last_match'] is None


async def test_statistics_scope_revocation_after_read(house):
    class Stats:
        async def statistics(self, *args):
            scope.active = False
            return {'sensor.inside': [{'max': 99, 'min': 1}]}
    t, scope = tool(house, 'ziko_ha_tools__query_statistics', Stats())
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_ids': ['sensor.inside']}), context())
    assert result.error and '99' not in str(result.data)


async def test_logbook_projects_only_requested_entities(house):
    class Events:
        async def logbook(self, *args):
            return [{'entity_id': 'sensor.inside', 'when': 10, 'state': 'on', 'context_user_id': 'private'},
                    {'entity_id': 'sensor.outside', 'when': 11, 'state': 'on', 'name': 'private outside'}]
    t, _ = tool(house, 'ziko_ha_tools__query_logbook', Events())
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_ids': ['sensor.inside']}), context())
    assert not result.error and len(result.data['events']) == 1
    assert 'private' not in str(result.data)


async def test_database_failure_is_a_safe_structured_tool_error(house):
    class Broken:
        async def history(self, *args):
            raise OSError('private connection diagnostic')
    t, _ = tool(house, 'ziko_ha_tools__query_history', Broken())
    result = await t.async_call(house.hass, ToolInput(t.name, {'entity_ids': ['sensor.inside']}), context())
    assert result.error and 'private connection diagnostic' not in str(result.data)
