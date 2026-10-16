"""Native Assist read tools with bounded output and live authorization."""
import asyncio
from datetime import datetime, timedelta, timezone
import re
import unicodedata

import probatio as p
from sqlalchemy.exc import SQLAlchemyError
from homeassistant.helpers.llm import Tool, ToolAnnotations, ToolResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, area_registry as ar

from .adapters import HAAdapter
from .const import DOMAIN, MAX_DAYS, MAX_ENTITIES, MAX_OUTPUT, MAX_ROWS, MAX_STATS_DAYS
from .privacy import sanitize, SENSITIVE, trace_summary
from .query import normalize_state, parse_window, summarize_history

ENTITY_FIELDS = {p.Required('entity_ids'): [str], p.Optional('start_time'): str, p.Optional('end_time'): str,
                 p.Optional('limit', default=MAX_OUTPUT): p.All(p.Coerce(int), p.Range(min=1, max=MAX_OUTPUT))}


def _search(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


class ReadTool(Tool):
    integration = DOMAIN
    annotations = ToolAnnotations(read_only=True, destructive=False, idempotent=True, open_world=False)

    def __init__(self, scope, adapter):
        self.scope, self.adapter = scope, adapter

    async def async_call(self, hass, tool_input, llm_context):
        try:
            if not self.scope.active:
                raise HomeAssistantError('Ziko tools are no longer configured')
            args = self.parameters(tool_input.tool_args)
            async with asyncio.timeout(30):
                result = await self.read(args, llm_context)
            if not self.scope.active:
                raise HomeAssistantError('Ziko tool access was revoked during the query')
            return ToolResult(data=sanitize(result))
        except (HomeAssistantError, ValueError, TypeError, KeyError, TimeoutError, RuntimeError, p.Invalid) as exc:
            return ToolResult(data={'error': sanitize(str(exc)), 'source': self.name}, error=True)
        except (OSError, SQLAlchemyError):
            return ToolResult(data={'error': 'The HA data source could not be read; no result is available.',
                                    'source': self.name}, error=True)


class ListSources(ReadTool):
    name = 'ziko_ha_tools__list_sources'
    title = 'Házikó naplóforrások'
    description = 'Find allowed household entity IDs by room/name and available measurements; query this before history when the ID is unknown.'
    parameters = p.Schema({p.Optional('search', default=''): str,
                           p.Optional('limit', default=MAX_OUTPUT): p.All(p.Coerce(int), p.Range(min=1, max=MAX_OUTPUT))})

    async def read(self, args, ctx):
        results = []
        reg = er.async_get(self.scope.hass)
        ids = sorted(set(reg.entities) | set(self.scope.hass.states.async_entity_ids()))
        for eid in ids:
            if not self.scope.allows(eid):
                continue
            state = self.scope.hass.states.get(eid)
            entry = reg.async_get(eid)
            area = ar.async_get(self.scope.hass).async_get_area(self.scope.area_id(eid))
            name = (state.attributes.get('friendly_name') if state else None) or (entry.name or entry.original_name if entry else None) or eid
            area_name = area.name if area else None
            if _search(args['search']) not in _search(f'{eid} {name} {area_name or ""}'):
                continue
            attrs = state.attributes if state else {}
            results.append({'entity_id': eid, 'name': name, 'area': area_name,
                            'history': 'recorded data only; existence/retention checked when queried',
                            'state': state.state if state else None,
                            'unit': attrs.get('unit_of_measurement'),
                            'measurement_attributes': [k for k in ('current_temperature', 'temperature', 'current_humidity', 'brightness', 'current_position', 'battery_level') if k in attrs]})
        return {'entities': results[:args['limit']], 'total_matching': len(results),
                'truncated': len(results) > args['limit'], 'timezone': self.scope.hass.config.time_zone,
                'diagnostics': 'owner-authenticated access only' if self.scope.config.get('diagnostics') else 'disabled',
                'unsupported_sources': ['Supervisor logs', 'OS logs', 'app/add-on logs']}


class QueryHistory(ReadTool):
    name = 'ziko_ha_tools__query_history'
    title = 'Eszköz-előzmények keresése'
    description = ('Read recorded household states/attributes. For measured radiator temperature use attribute=current_temperature. '
                   'operator/value searches the full processed series for the last recorded match before trimming output. '
                   'Explicit ISO timestamps with timezone; default last 24h, maximum 14 days. Last match is an observation, not an exact crossing/end time.')
    parameters = p.Schema({**ENTITY_FIELDS, p.Optional('attribute'): str,
                            p.Optional('operator'): p.In(['gt', 'gte', 'lt', 'lte', 'eq', 'ne']),
                            p.Optional('value'): p.Any(str, int, float)})

    async def read(self, args, ctx):
        ids = args['entity_ids']
        self.scope.require_entities(ids)
        attribute = args.get('attribute')
        if attribute and (not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', attribute) or SENSITIVE.search(attribute)):
            raise HomeAssistantError('Invalid or sensitive attribute')
        if ('operator' in args) != ('value' in args):
            raise HomeAssistantError('operator and value must be supplied together')
        predicate = {'operator': args['operator'], 'value': args['value']} if 'operator' in args else None
        start, end = parse_window(args.get('start_time'), args.get('end_time'), datetime.now(timezone.utc), MAX_DAYS)
        collected = {eid: {} for eid in ids}
        boundaries = {}
        per_entity_limit = MAX_ROWS // len(ids)
        cursor = end
        truncated = False
        skipped = 0
        while cursor > start:
            chunk_start = max(start, cursor - timedelta(days=1))
            raw = await self.adapter.history(ids, chunk_start, cursor)
            self.scope.require_entities(ids)
            for eid in ids:
                rows = raw.get(eid, [])
                budget = per_entity_limit - len(collected[eid])
                if len(rows) > budget:
                    truncated = True
                    rows = rows[-budget:] if budget else []
                for row in rows:
                    try:
                        item = normalize_state(row, attribute)
                    except (ValueError, TypeError, OverflowError):
                        skipped += 1
                        continue
                    if item.get('synthetic_boundary'):
                        if chunk_start == start:
                            boundaries[eid] = {**item, 'time': None, 'known_at': item['time'],
                                'note': 'Retained initial value immediately before the window; measurement time is unknown.'}
                        continue
                    collected[eid][item['time']] = item
            cursor = chunk_start
            if truncated:
                break
        self.scope.require_entities(ids)
        return {'source': 'recorder_history', 'requested_start': start.isoformat(), 'requested_end': end.isoformat(),
                'searched_start': cursor.isoformat(), 'timezone': self.scope.hass.config.time_zone,
                'query_complete': not truncated and skipped == 0, 'query_truncated': truncated,
                'invalid_records': skipped, 'entities': {eid: {**summarize_history(list(rows.values()), predicate, args['limit'], (start, end)),
                                                             'state_at_window_start': boundaries.get(eid)}
                                                       for eid, rows in collected.items()},
                'coverage_note': 'Recorder retention/exclusions may leave gaps. No rows is not proof that an event never happened.'}


class QueryStatistics(ReadTool):
    name = 'ziko_ha_tools__query_statistics'
    title = 'Mérési statisztikák'
    description = 'Read stored numeric statistics for approved entity IDs. Hour/day aggregates prove a period, not an exact minute. Maximum 366 days.'
    parameters = p.Schema({**ENTITY_FIELDS, p.Optional('period', default='hour'): p.In(['5minute', 'hour', 'day', 'week', 'month'])})

    async def read(self, args, ctx):
        ids = args['entity_ids']
        self.scope.require_entities(ids)
        start, end = parse_window(args.get('start_time'), args.get('end_time'), datetime.now(timezone.utc), MAX_STATS_DAYS)
        if args['period'] == '5minute' and end - start > timedelta(days=MAX_DAYS):
            raise HomeAssistantError('5-minute statistics queries are limited to 14 days')
        raw = await self.adapter.statistics(ids, start, end, args['period'])
        self.scope.require_entities(ids)
        result = {}
        for eid in ids:
            rows = raw.get(eid, [])
            maxima = [r['max'] for r in rows if isinstance(r.get('max'), (int, float))]
            minima = [r['min'] for r in rows if isinstance(r.get('min'), (int, float))]
            result[eid] = {'records': rows[-args['limit']:], 'total_records': len(rows),
                           'maximum': max(maxima) if maxima else None, 'minimum': min(minima) if minima else None,
                           'presentation_truncated': len(rows) > args['limit'], 'has_statistics': bool(rows)}
        return {'source': 'recorder_statistics', 'period': args['period'], 'start': start.isoformat(), 'end': end.isoformat(),
                'timezone': self.scope.hass.config.time_zone, 'entities': result,
                'note': 'Aggregated bucket data is not an exact event timestamp. Missing statistics cannot be reconstructed.'}


class QueryLogbook(ReadTool):
    name = 'ziko_ha_tools__query_logbook'
    title = 'Háztartási eseménynapló'
    description = 'Read HA Activity events for explicitly selected approved household entities; maximum 14 days. Global logbook queries are prohibited.'
    parameters = p.Schema(ENTITY_FIELDS)

    async def read(self, args, ctx):
        ids = args['entity_ids']
        self.scope.require_entities(ids)
        start, end = parse_window(args.get('start_time'), args.get('end_time'), datetime.now(timezone.utc), MAX_DAYS)
        events = await self.adapter.logbook(ids, start, end)
        self.scope.require_entities(ids)
        # Related parent contexts can contain other households; never expose them.
        fields = ('when', 'entity_id', 'state', 'name', 'domain')
        events = [{k: event[k] for k in fields if k in event}
                  for event in events if event.get('entity_id') in ids]
        events.sort(key=lambda event: event.get('when', 0), reverse=True)
        return {'source': 'logbook', 'events': events[:args['limit']], 'total_matching': len(events),
                'truncated': len(events) > args['limit'], 'start': start.isoformat(), 'end': end.isoformat(),
                'note': 'Related contexts and custom free-text entries are omitted to preserve household scope.'}


class ListTraces(ReadTool):
    name = 'ziko_ha_tools__list_traces'
    title = 'Automatizálási futások'
    description = 'List retained runs of one approved automation. Authenticated owner diagnostics required; mixed/dynamic target traces excluded.'
    parameters = p.Schema({p.Required('entity_id'): str, p.Optional('limit', default=10): p.All(p.Coerce(int), p.Range(min=1, max=MAX_OUTPUT))})

    async def read(self, args, ctx):
        await self.scope.require_owner(ctx.context)
        key = self.scope.trace_key(args['entity_id'])
        rows = await self.adapter.traces(key)
        await self.scope.require_owner(ctx.context)
        self.scope.trace_key(args['entity_id'])
        rows = sorted(rows, key=lambda row: str((row.get('timestamp') or {}).get('start') or ''), reverse=True)
        buffered = []
        for row in rows[:args['limit']]:
            raw = await self.adapter.trace(key, row['run_id'])
            await self.scope.require_owner(ctx.context)
            self.scope.trace_key(args['entity_id'])
            buffered.append(raw)
        # No await between this final validation and the returned projections.
        # A later read may have revoked scope for an earlier buffered run.
        result = []
        excluded = 0
        for raw in buffered:
            try:
                self.scope.require_trace_scope(raw)
            except HomeAssistantError:
                excluded += 1
                continue
            result.append(trace_summary({k: raw[k] for k in ('run_id', 'state', 'script_execution', 'timestamp', 'last_step', 'error', 'not_triggered') if k in raw}))
        return {'entity_id': args['entity_id'], 'runs': result, 'excluded_scope_unverifiable': excluded,
                'truncated': len(rows) > args['limit'], 'note': 'Only retained runs; missing runs cannot be reconstructed.'}


class ReadTrace(ReadTool):
    name = 'ziko_ha_tools__read_trace'
    title = 'Automatizálási futásnyom'
    description = 'Read safe step results of a selected retained automation run. Owner diagnostics only. Raw variables/config and mixed/dynamic targets are never exposed.'
    parameters = p.Schema({p.Required('entity_id'): str, p.Required('run_id'): str})

    async def read(self, args, ctx):
        await self.scope.require_owner(ctx.context)
        key = self.scope.trace_key(args['entity_id'])
        raw = await self.adapter.trace(key, args['run_id'])
        await self.scope.require_owner(ctx.context)
        self.scope.trace_key(args['entity_id'])
        self.scope.require_trace_scope(raw)
        return {'entity_id': args['entity_id'], 'trace': trace_summary(raw),
                'note': 'Raw config, variables, context and unverified child traces are omitted.'}


class QueryErrors(ReadTool):
    name = 'ziko_ha_tools__query_errors'
    title = 'HA-hibák és Core napló'
    description = 'Read structured HA errors or the fixed Core logfile. Authenticated owner diagnostics only; log covers the whole HA system. No arbitrary paths or Supervisor/OS/app logs.'
    parameters = p.Schema({p.Optional('source', default='system_log'): p.In(['system_log', 'core_log']),
                           p.Optional('limit', default=50): p.All(p.Coerce(int), p.Range(min=1, max=MAX_OUTPUT))})

    async def read(self, args, ctx):
        await self.scope.require_owner(ctx.context)
        result = await self.adapter.errors(args['source'], args['limit'])
        await self.scope.require_owner(ctx.context)
        return {**result, 'scope': 'owner-only whole HA diagnostic source; credentials redacted best-effort'}


def build_tools(scope, llm_context, adapter=None):
    adapter = adapter or HAAdapter(scope.hass)
    classes = [ListSources, QueryHistory, QueryStatistics, QueryLogbook]
    if scope.config.get('diagnostics') and llm_context.context and llm_context.context.user_id == scope.config.get('owner_user_id'):
        classes += [ListTraces, ReadTrace, QueryErrors]
    from .assistant_tools import build_assistant_tools
    return [cls(scope, adapter) for cls in classes] + build_assistant_tools(scope, llm_context) + list(getattr(scope, 'bridge_tools', []))
