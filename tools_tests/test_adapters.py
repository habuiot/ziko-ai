from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeassistant import loader
from homeassistant.components import recorder
from custom_components.ziko_ha_tools.adapters import HAAdapter


async def recorder_barrier(instance):
    # async_block_till_done can see an empty queue while a worker is processing
    # a state event. Always enqueue the native commit barrier in tests.
    import asyncio
    from homeassistant.components.recorder.tasks import SynchronizeTask
    future = instance.hass.loop.create_future()
    instance.queue_task(SynchronizeTask(future))
    await asyncio.wait_for(future, 10)


async def test_real_recorder_sqlite_reads_attribute_changes(house, tmp_path):
    hass = house.hass
    loader.async_setup(hass)
    from homeassistant.helpers.recorder import async_initialize_recorder
    async_initialize_recorder(hass)
    config = recorder.CONFIG_SCHEMA({'recorder': {
        'db_url': f'sqlite:///{tmp_path / "history.db"}',
        'auto_purge': False, 'commit_interval': 0,
    }})
    assert await recorder.async_setup(hass, config)
    await hass.async_start()
    instance = recorder.get_instance(hass)
    await recorder_barrier(instance)
    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    hass.states.async_set('climate.radiator', 'heat', {'current_temperature': 28.2, 'temperature': 19})
    await hass.async_block_till_done()
    await recorder_barrier(instance)
    hass.states.async_set('climate.radiator', 'heat', {'current_temperature': 25.3, 'temperature': 19})
    await hass.async_block_till_done()
    await recorder_barrier(instance)
    rows = await HAAdapter(hass).history(['climate.radiator'], start, datetime.now(timezone.utc))
    values = [row['attributes']['current_temperature'] for row in rows['climate.radiator']]
    assert 28.2 in values and 25.3 in values
    assert all(row['state'] == 'heat' for row in rows['climate.radiator'])
    assert rows['climate.radiator'][-1]['last_updated'] >= rows['climate.radiator'][0]['last_updated']
    adapter = HAAdapter(hass)
    assert await adapter.statistics(['sensor.inside'], start, datetime.now(timezone.utc), 'hour') == {}
    from homeassistant.components.logbook.models import LogbookConfig
    hass.data['logbook'] = LogbookConfig({}, None, None)
    events = await adapter.logbook(['climate.radiator'], start, datetime.now(timezone.utc))
    assert isinstance(events, list)
    # A retained boundary is not a measurement at the requested start.
    hass.states.async_set('climate.radiator', 'heat', {'current_temperature': 28.4, 'temperature': 19})
    observed = hass.states.get('climate.radiator').last_updated
    await hass.async_block_till_done()
    await recorder_barrier(instance)
    boundary_start = datetime.now(timezone.utc)
    from test_history_tools import tool, context
    from homeassistant.helpers.llm import ToolInput
    t, _ = tool(house, 'ziko_ha_tools__query_history', adapter)
    result = await t.async_call(hass, ToolInput(t.name, {
        'entity_ids': ['climate.radiator'], 'attribute': 'current_temperature',
        'start_time': boundary_start.isoformat(),
        'end_time': (boundary_start + timedelta(seconds=1)).isoformat(),
        'operator': 'gt', 'value': 27}), context())
    assert not result.error
    data = result.data['entities']['climate.radiator']
    assert data['last_match'] is None, 'query boundary must not invent a measurement time'
    assert data['processed_records'] == 0
    assert data['state_at_window_start']['value'] == 28.4
    assert data['state_at_window_start']['time'] is None
    inclusive = await adapter.history(['climate.radiator'], observed, datetime.now(timezone.utc))
    assert any(row['attributes']['current_temperature'] == 28.4 and row['last_updated'] == observed
               and not row.get('synthetic_boundary') for row in inclusive['climate.radiator'])


async def test_fixed_core_log_is_bounded_and_reports_missing(house, tmp_path):
    adapter = HAAdapter(house.hass)
    from homeassistant.exceptions import HomeAssistantError
    import pytest
    with pytest.raises(HomeAssistantError):
        await adapter.errors('core_log', 2)
    path = Path(house.hass.config.path('home-assistant.log'))
    path.write_text(('discarded\n' * 40000) + 'line last-but-one\nline last\n')
    result = await adapter.errors('core_log', 2)
    assert result['lines'] == ['line last-but-one', 'line last']
    assert result['truncated'] is True


async def test_native_retained_trace_and_missing_run(house):
    from homeassistant.components.trace.models import RestoredTrace, TraceBuckets
    from homeassistant.components.trace.const import DATA_TRACE, DATA_TRACES_RESTORED
    from homeassistant.util.limited_size_dict import LimitedSizeDict
    from homeassistant.exceptions import HomeAssistantError
    import pytest
    raw = {'domain': 'automation', 'item_id': 'evening', 'run_id': 'run',
           'context': {'user_id': None, 'parent_id': None, 'id': 'test'},
           'config': {'actions': [{'target': {'entity_id': 'sensor.inside'}}]},
           'trace': {}, 'timestamp': {'start': '2026-10-13T12:00:00Z'}}
    trace = RestoredTrace({'extended_dict': raw, 'short_dict': {'run_id': 'run', 'timestamp': raw['timestamp']}})
    house.hass.config.components.add('trace')
    house.hass.data[DATA_TRACES_RESTORED] = True
    house.hass.data[DATA_TRACE] = {'automation.evening': TraceBuckets(
        runs=LimitedSizeDict({'run': trace}), not_triggered=LimitedSizeDict())}
    adapter = HAAdapter(house.hass)
    assert (await adapter.traces('automation.evening'))[0]['run_id'] == 'run'
    assert (await adapter.trace('automation.evening', 'run'))['config'] == raw['config']
    with pytest.raises(HomeAssistantError):
        await adapter.trace('automation.evening', 'not-retained')


async def test_real_structured_system_log_format(house):
    import logging, re
    from homeassistant.components.system_log import LogErrorHandler
    handler = LogErrorHandler(house.hass, 50, False, re.compile(r'/(.*)'))
    handler.emit(logging.LogRecord('test.ziko', logging.ERROR, __file__, 1, 'safe diagnostic example', (), None))
    house.hass.data['system_log'] = handler
    result = await HAAdapter(house.hass).errors('system_log', 1)
    assert result['entries'][0]['message'] == ['safe diagnostic example']
    assert result['entries'][0]['level'] == 'ERROR'
