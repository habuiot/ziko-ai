"""Continuous HA observation. No service calls or model calls live here."""
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import time
import math
import re
import logging
from websockets.asyncio.client import connect
from .scope import approved_devices

LOGGER = logging.getLogger(__name__)


class HAQueryError(ValueError):
    def __init__(self, code):
        self.code = code if code in {'unauthorized', 'unknown_command', 'invalid_format', 'not_found', 'id_reuse', 'unknown_error'} else 'other'
        super().__init__('HA-lekérdezési hiba')

READ_COMMANDS = frozenset({'get_states', 'config/device_registry/list',
    'config/entity_registry/list', 'config/area_registry/list'})
ATTRIBUTES = frozenset({'unit_of_measurement', 'device_class', 'brightness',
    'color_temp_kelvin', 'temperature', 'current_temperature', 'current_humidity',
    'hvac_action', 'preset_mode', 'percentage', 'battery_level', 'target_temp_high', 'target_temp_low'})


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(value, limit=256):
    text = str(value if value is not None else '')[:limit]
    if re.search(r'(?i)([a-z][a-z0-9+.-]*://|bearer\s|(?:token|password|secret|credential|authorization)\s*[:=])', text):
        return '[védett adat kihagyva]'
    return text


def safe_state(value):
    text = bounded(value)
    known = {'on', 'off', 'unknown', 'unavailable', 'locked', 'unlocked', 'locking', 'unlocking',
        'jammed', 'open', 'closed', 'opening', 'closing', 'idle', 'streaming', 'recording',
        'disarmed', 'armed_home', 'armed_away', 'armed_night', 'armed_vacation', 'armed_custom_bypass',
        'arming', 'pending', 'triggered', 'disarming', 'heat', 'cool', 'heat_cool', 'auto',
        'dry', 'fan_only', 'heating', 'cooling', 'cleaning', 'paused', 'docked', 'standby',
        'normal', 'low', 'high', 'medium', 'charging', 'not_charging', 'full', 'empty', 'detected', 'clear',
        'playing', 'buffering', 'home', 'not_home', 'active', 'inactive', 'connected', 'disconnected'}
    if text in known:
        return text
    try:
        if math.isfinite(float(text)):
            return text
    except ValueError:
        pass
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T[0-9:.+Z-]+', text):
        return text
    return '[szöveges állapot kihagyva]'


def safe_attributes(attrs):
    result = {}
    for key, value in attrs.items():
        if key not in ATTRIBUTES:
            continue
        if isinstance(value, (int, float)) and math.isfinite(value):
            result[key] = value
        elif isinstance(value, str) and key == 'unit_of_measurement' and re.fullmatch(r'[\w°%/ .µ³²·-]{1,24}', value):
            if bounded(value) == value:
                result[key] = value
        elif isinstance(value, str) and key == 'device_class' and re.fullmatch(r'[a-z_]{1,40}', value):
            result[key] = value
        elif isinstance(value, str) and key in ('preset_mode', 'hvac_action') and value.lower() in {
            'auto', 'manual', 'none', 'sleep', 'boost', 'eco', 'comfort', 'away', 'home',
            'activity', 'normal', 'high', 'low', 'medium', 'off', 'on', 'heat', 'cool',
            'idle', 'heating', 'cooling', 'drying', 'fan'}:
            result[key] = value
    return result


class ReadOnlyConnection:
    def __init__(self, ws, token):
        self.ws = ws
        self.token = token
        self.counter = 0

    async def authenticate(self):
        async with asyncio.timeout(15):
            greeting = json.loads(await self.ws.recv())
            if greeting.get('type') != 'auth_required':
                raise ValueError('HA-hitelesítési hiba')
            await self.ws.send(json.dumps({'type': 'auth', 'access_token': self.token}))
            result = json.loads(await self.ws.recv())
            if result.get('type') != 'auth_ok':
                raise ValueError('HA-hitelesítési hiba')

    async def send(self, kind, **fields):
        if kind not in READ_COMMANDS and not (kind == 'subscribe_events' and fields == {'event_type': 'state_changed'}):
            raise ValueError('Csak olvasás engedélyezett')
        if kind in READ_COMMANDS and fields:
            raise ValueError('Nem támogatott olvasási paraméter')
        self.counter += 1
        await self.ws.send(json.dumps(dict(id=self.counter, type=kind, **fields)))
        return self.counter


class HouseObserver:
    def __init__(self, token='', *, approved=None, url='ws://supervisor/core/websocket', retry_seconds=1):
        self.token = token
        self.approved = frozenset(approved_devices() if approved is None else approved)
        self.url = url
        self.retry_seconds = retry_seconds
        self.catalog = {}
        self.coverage = dict(total=0, enabled=0, disabled=0)
        self.states = {}
        self.recent = deque(maxlen=200)
        self.connected = False
        self.synced = None
        self.sync_monotonic = 0
        self.task = None
        self.stage = 'connect'
        self.failure = None
        self.message = 'Kapcsolódásra vár' if token else 'HA-hozzáférés még nincs engedélyezve'

    def start(self):
        if self.token and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.disconnected()

    def disconnected(self):
        self.connected = False
        self.message = 'HA-kapcsolat megszakadt; az állapotok elavultak' if self.token else 'HA-hozzáférés még nincs engedélyezve'

    def replace(self, devices, entities, areas, states):
        by_device = {d['id']: d for d in devices if d.get('id') in self.approved}
        by_area = {a['area_id']: bounded(a.get('name')) for a in areas}
        catalog = {}
        total = disabled = 0
        for e in entities:
            eid = e.get('entity_id', '')
            d = by_device.get(e.get('device_id'))
            if d is None:
                continue
            total += 1
            if e.get('disabled_by'):
                disabled += 1
                continue
            catalog[eid] = dict(device_id=d['id'], device=bounded(d.get('name_by_user') or d.get('name')),
                name=bounded(e.get('name') or e.get('original_name') or eid),
                area=by_area.get(e.get('area_id') or d.get('area_id'), 'Nincs helyiség'))
        self.catalog = catalog
        self.coverage = dict(total=total, enabled=len(catalog), disabled=disabled)
        self.states = {}
        for state in states:
            self._set(state)
        self.recent = deque((r for r in self.recent if r['entity_id'] in catalog), maxlen=200)
        self.synced = now()
        self.sync_monotonic = time.monotonic()
        self.connected = True
        self.failure = None
        self.message = 'Folyamatos megfigyelés aktív'

    def _set(self, raw):
        eid = raw.get('entity_id')
        if eid not in self.catalog:
            return
        attrs = raw.get('attributes') or {}
        safe = safe_attributes(attrs)
        meta = self.catalog[eid]
        self.states[eid] = dict(meta, entity_id=eid, name=meta['name'] if meta['name'] != eid else bounded(attrs.get('friendly_name') or meta['device']),
            state=safe_state(raw.get('state', 'unknown')), attributes=safe, has_state=True,
            last_updated=bounded(raw.get('last_updated')))

    def apply_event(self, data, *, after_sync=False):
        eid = data.get('entity_id')
        if eid not in self.catalog:
            return
        raw = data.get('new_state')
        old = self.states.get(eid)
        if raw is None:
            if after_sync and old:
                fired = data.get('_time_fired')
                if not fired or not old.get('last_updated'):
                    return
                try:
                    if datetime.fromisoformat(fired.replace('Z', '+00:00')) <= datetime.fromisoformat(old['last_updated'].replace('Z', '+00:00')):
                        return
                except (ValueError, TypeError):
                    return
            self.states.pop(eid, None)
            return
        if not isinstance(raw, dict) or raw.get('entity_id') != eid:
            return
        if after_sync and old and old.get('last_updated') and raw.get('last_updated'):
            try:
                if datetime.fromisoformat(raw['last_updated'].replace('Z', '+00:00')) < datetime.fromisoformat(old['last_updated'].replace('Z', '+00:00')):
                    return
            except (ValueError, TypeError):
                return
        self._set(raw)
        new = self.states[eid]
        if old and (old['state'] != new['state'] or old['attributes'] != new['attributes']):
            self.recent.appendleft(dict(entity_id=eid, name=new['name'], device=new['device'], area=new['area'],
                previous=old['state'], state=new['state'], time=now()))

    def snapshot(self):
        fresh = self.connected and time.monotonic() - self.sync_monotonic < 90
        entities = [self.states.get(eid) or dict(meta, entity_id=eid, state='unknown',
                    attributes={}, last_updated='', has_state=False) for eid, meta in self.catalog.items()]
        return dict(fresh=fresh, connected=self.connected, message=self.message if fresh or not self.connected else 'Az állapotok elavultak',
            observed_at=now(), synchronized_at=self.synced, device_count=len({v['device_id'] for v in self.catalog.values()}),
            entity_count=len(self.catalog), entities=sorted(entities, key=lambda v: (v['area'], v['device'], v['entity_id'])),
            coverage=dict(self.coverage, with_state=len(self.states), without_state=len(self.catalog)-len(self.states)),
            recent=list(self.recent), mode='read_only', failure=self.failure)

    def context(self):
        s = self.snapshot()
        result = {k: s[k] for k in ('fresh', 'observed_at', 'synchronized_at', 'message', 'entity_count', 'coverage')}
        result['entities'] = list(s['entities'])
        result['recent'] = s['recent'][:20]
        result['omitted_entities'] = 0
        return result

    async def _result(self, connection, kind, events, **fields):
        self.stage = kind
        ident = await connection.send(kind, **fields)
        async with asyncio.timeout(15):
            while True:
                msg = json.loads(await connection.ws.recv())
                if msg.get('type') == 'event':
                    data = msg.get('event', {})
                    if data.get('event_type') == 'state_changed':
                        events.append(dict(data.get('data', {}), _time_fired=data.get('time_fired')))
                        if len(events) > 10000:
                            raise ValueError('Túl sok HA-esemény')
                elif msg.get('type') == 'result' and msg.get('id') == ident:
                    if not msg.get('success'):
                        raise HAQueryError((msg.get('error') or {}).get('code'))
                    return msg.get('result')

    async def sync_once(self, connection, events=None):
        events = [] if events is None else events
        self.connected = False
        self.message = 'Állapotok szinkronizálása'
        devices = await self._result(connection, 'config/device_registry/list', events)
        entities = await self._result(connection, 'config/entity_registry/list', events)
        areas = await self._result(connection, 'config/area_registry/list', events)
        states = await self._result(connection, 'get_states', events)
        if not all(isinstance(v, list) for v in (devices, entities, areas, states)):
            raise ValueError('Hibás HA-adat')
        self.stage = 'build_snapshot'
        self.replace(devices, entities, areas, states)
        for data in events:
            self.apply_event(data, after_sync=True)

    async def _run(self):
        delay = self.retry_seconds
        while True:
            try:
                self.stage = 'connect'
                async with connect(self.url, proxy=None, open_timeout=15, ping_interval=20, ping_timeout=20,
                                   max_size=8 * 1024 * 1024, max_queue=256) as ws:
                    connection = ReadOnlyConnection(ws, self.token)
                    self.stage = 'authenticate'
                    await connection.authenticate()
                    events = []
                    await self._result(connection, 'subscribe_events', events, event_type='state_changed')
                    await self.sync_once(connection, events)
                    delay = self.retry_seconds
                    deadline = time.monotonic() + 60
                    self.stage = 'state_events'
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            await self.sync_once(connection)
                            deadline = time.monotonic() + 60
                            self.stage = 'state_events'
                            continue
                        try:
                            raw = await asyncio.wait_for(ws.recv(), remaining)
                        except TimeoutError:
                            continue
                        msg = json.loads(raw)
                        if msg.get('type') == 'event' and msg.get('event', {}).get('event_type') == 'state_changed':
                            self.apply_event(msg['event'].get('data', {}))
            except asyncio.CancelledError:
                self.disconnected()
                raise
            except Exception as exc:
                self.disconnected()
                error = type(exc).__name__
                # Never log raw exceptions or remote error messages: they can contain credentials.
                self.failure = dict(stage=self.stage, error=error, code=exc.code if isinstance(exc, HAQueryError) else 'none')
                LOGGER.warning('HA observer failed: stage=%s error=%s code=%s', self.stage, error, self.failure['code'])
                self.message += ' · ' + self.stage + ' / ' + error + ' / ' + self.failure['code']
            await asyncio.sleep(delay)
            delay = min(30, delay * 2)
