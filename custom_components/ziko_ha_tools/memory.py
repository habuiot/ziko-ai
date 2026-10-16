"""Bounded, versioned household data; atomic HA-native persistence."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
import time

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

KINDS = frozenset({'fact', 'preset', 'plan', 'revision', 'operation', 'settings'})
KEY = re.compile(r'[a-z0-9][a-z0-9_-]{0,95}\Z')
MAX_RECORDS = 1000
MAX_BYTES = 2_000_000
# Separate budgets prevent a busy journal from consuming owner recovery space.
COUNTS = {'fact':100,'preset':100,'plan':100,'revision':200,'operation':256,'settings':101}
BYTES = {'fact':300_000,'preset':300_000,'plan':350_000,'revision':700_000,'operation':150_000,'settings':180_000}


def discard(data,identity):
    version=data['versions'].pop(identity,0)
    data['versions']['__floor']=max(data['versions'].get('__floor',0),version+1)
    data['records'].pop(identity,None)


def collect(data):
    now=time.time()
    for identity,row in list(data['records'].items()):
        value=row['value']
        if row['kind']=='operation' and value.get('expires_at',datetime.fromisoformat(row['updated_at']).timestamp()+600)<now:
            discard(data,identity)
    # Legacy tombstones are replaced by a monotonic generation floor.
    for identity in list(data['versions']):
        if identity!='__floor' and identity not in data['records']:discard(data,identity)


def enforce_budget(data,kind,identity):
    if identity=='settings:writes':return  # always reserve pause/recovery capacity
    count=min(COUNTS[kind],MAX_RECORDS)
    def rows():return [(k,v) for k,v in data['records'].items() if v['kind']==kind and k!='settings:writes']
    def over():return len(rows())>count or len(json.dumps(dict(rows()),ensure_ascii=False).encode())>BYTES[kind]
    # Plans removed here fail closed on apply. Keep current and uncertain revisions.
    protected={r['value'].get('revision_id') for r in data['records'].values() if r['kind']=='settings'}
    candidates=sorted(rows(),key=lambda item:item[1]['updated_at'])
    for key,row in candidates:
        if not over():break
        if key==identity:continue
        eligible=(kind=='plan' and row['value'].get('status')!='applying') or (
            kind=='revision' and row['key'] not in protected and row['value'].get('status') not in ('prepared','prepared_enable'))
        if eligible:discard(data,key)
    if over():raise HomeAssistantError('Memory category capacity reached; delete unused facts/presets, or wait for operation expiry. Export before reviewing archives.')


class Memory:
    """Never publish an in-memory change before its disk commit succeeds."""

    def __init__(self, hass, entry_id):
        self.store = Store(hass, 1, f'ziko_ha_tools.{entry_id}', private=True, atomic_writes=True)
        self.lock = asyncio.Lock()
        self.data = {'records': {}, 'versions': {}}
        self.loaded = False

    async def async_load(self):
        async with self.lock:
            data = await self.store.async_load()
            if data is not None:
                if (not isinstance(data, dict) or set(data) != {'records', 'versions'}
                        or not isinstance(data['records'], dict) or not isinstance(data['versions'], dict)):
                    raise HomeAssistantError('Unsupported Ziko storage data; restore a backup')
                self.data = data
            self.loaded = True

    def _id(self, kind, key):
        if not self.loaded:
            raise HomeAssistantError('Ziko memory is not loaded')
        if kind not in KINDS or not isinstance(key, str) or not KEY.fullmatch(key):
            raise HomeAssistantError('Invalid memory kind or key')
        return f'{kind}:{key}'

    async def async_get(self, kind, key):
        identity = self._id(kind, key)
        return deepcopy(self.data['records'].get(identity))

    async def async_list(self, kind, search='', limit=100):
        self._id(kind, 'check')
        if not isinstance(limit, int) or not 1 <= limit <= 200 or len(search) > 100:
            raise HomeAssistantError('Invalid memory search limit')
        rows = [v for v in self.data['records'].values()
                if v['kind'] == kind and search.casefold() in json.dumps(v, ensure_ascii=False).casefold()]
        return deepcopy(sorted(rows, key=lambda v: v['updated_at'], reverse=True)[:limit])

    async def async_put(self, kind, key, value, expected_version=None):
        identity = self._id(kind, key)
        if not isinstance(value, dict) or len(json.dumps(value, allow_nan=False)) > 8192:
            raise HomeAssistantError('Memory value must be a bounded JSON object')
        async with self.lock:
            old = self.data['records'].get(identity)
            if (old and expected_version != old['version']) or (not old and expected_version is not None):
                raise HomeAssistantError('Memory version conflict; read the current version first')
            candidate = deepcopy(self.data)
            collect(candidate)
            version = candidate['versions'].get(identity, candidate['versions'].get('__floor',0)) + 1
            previous = (old.get('previous', []) + [{k: old[k] for k in ('version', 'updated_at', 'value')}])[-5:] if old else []
            row = {'kind': kind, 'key': key, 'version': version,
                   'updated_at': datetime.now(timezone.utc).isoformat(), 'value': deepcopy(value), 'previous': previous}
            candidate['records'][identity] = row
            candidate['versions'][identity] = version
            enforce_budget(candidate,kind,identity)
            if identity!='settings:writes' and len(json.dumps(candidate, ensure_ascii=False, allow_nan=False).encode()) > MAX_BYTES:
                raise HomeAssistantError('Memory storage limit reached')
            await self.store.async_save(candidate)
            self.data = candidate
            return deepcopy(row)

    async def async_delete(self, kind, key, expected_version):
        identity = self._id(kind, key)
        async with self.lock:
            old = self.data['records'].get(identity)
            if not old or old['version'] != expected_version:
                raise HomeAssistantError('Memory version conflict; read the current version first')
            candidate = deepcopy(self.data)
            discard(candidate,identity)
            collect(candidate)
            await self.store.async_save(candidate)
            self.data = candidate

    async def async_export(self):
        if not self.loaded:
            raise HomeAssistantError('Ziko memory is not loaded')
        return deepcopy(self.data)
