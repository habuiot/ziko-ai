"""Read-only adapters pinned to Home Assistant 2026.10 API contracts."""
from homeassistant.exceptions import HomeAssistantError


class HAAdapter:
    def __init__(self, hass):
        self.hass = hass

    async def history(self, entity_ids, start, end):
        from datetime import timedelta
        from homeassistant.components.recorder import get_instance, history, util
        if not entity_ids:
            raise HomeAssistantError('Explicit entities required')
        def query():
            with util.session_scope(hass=self.hass, read_only=True) as session:
                # The native API uses strict bounds. Overlap by 1us to retain
                # real observations exactly on a daily/request boundary.
                query_start = start - timedelta(microseconds=1)
                rows = history.get_significant_states_with_session(
                    self.hass, session, query_start, end + timedelta(microseconds=1), entity_ids=entity_ids,
                    include_start_time_state=True, significant_changes_only=False,
                    minimal_response=False, no_attributes=False)
                # HA synthesizes the initial state's timestamp at query_start.
                # It proves a boundary value, never a measurement time.
                return {eid: [{'state': row.state, 'attributes': row.attributes,
                               'last_updated': row.last_updated,
                               'synthetic_boundary': row.last_updated == query_start}
                              for row in states] for eid, states in rows.items()}
        return await get_instance(self.hass).async_add_executor_job(query)

    async def statistics(self, entity_ids, start, end, period):
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period
        if not entity_ids:
            raise HomeAssistantError('Explicit entities required')
        return await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, start, end, set(entity_ids), period,
            None, {'mean', 'min', 'max', 'sum', 'change', 'state'})

    async def logbook(self, entity_ids, start, end):
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.logbook.helpers import async_determine_event_types
        from homeassistant.components.logbook.processor import EventProcessor
        if not entity_ids:
            raise HomeAssistantError('Explicit entities required')
        if 'logbook' not in self.hass.data:
            raise HomeAssistantError('HA Activity/logbook is not available')
        event_types = async_determine_event_types(self.hass, entity_ids, None)
        processor = EventProcessor(self.hass, event_types, entity_ids=entity_ids,
                                   timestamp=True, include_entity_name=True)
        return await get_instance(self.hass).async_add_executor_job(processor.get_events, start, end)

    async def traces(self, key):
        from homeassistant.components.trace.util import async_list_traces
        if 'trace' not in self.hass.config.components:
            raise HomeAssistantError('HA trace integration is unavailable')
        return await async_list_traces(self.hass, 'automation', key)

    async def trace(self, key, run_id):
        from homeassistant.components.trace.util import async_get_trace
        if 'trace' not in self.hass.config.components:
            raise HomeAssistantError('HA trace integration is unavailable')
        try:
            return await async_get_trace(self.hass, key, run_id)
        except KeyError as exc:
            raise HomeAssistantError('Requested trace is not retained or does not exist') from exc

    async def errors(self, source, limit):
        if source == 'system_log':
            handler = self.hass.data.get('system_log')
            if not handler:
                raise HomeAssistantError('Structured HA error log is unavailable')
            rows = handler.records.to_list()
            return {'source': source, 'entries': rows[:limit], 'total_retained': len(rows), 'truncated': len(rows) > limit}
        if source != 'core_log':
            raise HomeAssistantError('Unsupported diagnostic source')
        from pathlib import Path
        from .const import MAX_LOG_BYTES
        path = Path(self.hass.config.path('home-assistant.log'))
        def read_tail():
            try:
                with path.open('rb') as stream:
                    stream.seek(0, 2)
                    size = stream.tell()
                    stream.seek(max(0, size - MAX_LOG_BYTES))
                    data = stream.read(MAX_LOG_BYTES)
                lines = data.decode('utf-8', errors='replace').splitlines()
                if size > MAX_LOG_BYTES and lines:
                    lines = lines[1:]
                return {'source': source, 'lines': lines[-limit:],
                        'truncated': size > MAX_LOG_BYTES or len(lines) > limit,
                        'note': 'Fixed HA Core logfile only; Supervisor/OS/app logs are not supported.'}
            except OSError as exc:
                raise HomeAssistantError('HA Core logfile is not available in this installation') from exc
        return await self.hass.async_add_executor_job(read_tail)
