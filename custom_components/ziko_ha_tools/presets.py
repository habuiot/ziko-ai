"""Capture actual light settings and restore once, with explicit verification."""
from copy import deepcopy
import math
import re
import time
import uuid

from homeassistant.exceptions import HomeAssistantError
from .policy import Policy

COLOR_FIELDS = {'color_temp': 'color_temp_kelvin', 'hs': 'hs_color', 'xy': 'xy_color',
                'rgb': 'rgb_color', 'rgbw': 'rgbw_color', 'rgbww': 'rgbww_color'}


def new_request_id():
    return f'r{int(time.time())}_{uuid.uuid4().hex}'


def validate_request_id(request_id):
    match=re.fullmatch(r'r(\d{10})_[a-f0-9]{32}',request_id)
    if not match or not -5<=time.time()-int(match[1])<=300:
        raise HomeAssistantError('Restore request expired or invalid; inspect live state, then prepare a new request if the user still wants it')


def light_data(state):
    if not state or state.state != 'on':
        raise HomeAssistantError('Light must be on and available to capture its actual setting')
    attrs = state.attributes
    mode = attrs.get('color_mode')
    if mode not in (*COLOR_FIELDS, 'white', 'brightness', 'onoff'):
        raise HomeAssistantError('The light did not report a supported current color mode')
    data = {}
    if mode != 'onoff':
        brightness = attrs.get('brightness')
        if type(brightness) is not int or not 1 <= brightness <= 255:
            raise HomeAssistantError('The light did not report a valid current brightness')
        data['brightness'] = brightness
    if mode == 'white':
        data = {'white': data['brightness']}
    elif mode in COLOR_FIELDS:
        field = COLOR_FIELDS[mode]
        value = attrs.get(field)
        if mode == 'color_temp':
            if type(value) not in (int, float) or not math.isfinite(value) or not 1000 <= value <= 40000:
                raise HomeAssistantError('Current color temperature is unavailable')
        else:
            size = {'hs':2, 'xy':2, 'rgb':3, 'rgbw':4, 'rgbww':5}[mode]
            if not isinstance(value, (list, tuple)) or len(value) != size or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
                raise HomeAssistantError('Current color values are unavailable')
            value = list(value)
        data[field] = value
    return mode, data


class Presets:
    def __init__(self, scope):
        self.scope = scope
        self.policy = Policy(scope)

    async def capture(self, entity_id, name, ctx, expected_version=None):
        await self.policy.require_access(ctx)
        if not entity_id.startswith('light.'):
            raise HomeAssistantError('Only light presets are supported')
        self.scope.require_entities([entity_id])
        from homeassistant.helpers import entity_registry as er
        entry = er.async_get(self.scope.hass).async_get(entity_id)
        if not entry:
            raise HomeAssistantError('A stable light registry identity is required')
        mode, data = light_data(self.scope.hass.states.get(entity_id))
        return await self.scope.memory.async_put('preset', name, {
            'entity_id':entity_id, 'registry_id':entry.id, 'mode':mode, 'service_data':data,
            'source':'live HA light attributes; household shared'}, expected_version)

    async def restore(self, name, request_id, ctx):
        await self.policy.require_access(ctx, write=True)
        async with self.scope.operation_lock:
            await self.policy.require_access(ctx, write=True)
            validate_request_id(request_id)
            old = await self.scope.memory.async_get('operation', request_id)
            if old:
                if old['value'].get('preset') != name:
                    raise HomeAssistantError('Request ID is already bound to another operation')
                return deepcopy(old['value'])
            row = await self.scope.memory.async_get('preset',name)
            if not row:
                raise HomeAssistantError('Preset does not exist')
            value = row['value'];eid = value['entity_id']
            entry = self.policy.require_control(eid)
            if entry.id != value['registry_id']:
                raise HomeAssistantError('Light registry identity changed; capture a new preset')
            state = self.scope.hass.states.get(eid)
            if not state or state.state in ('unknown','unavailable'):
                raise HomeAssistantError('Light is unavailable')
            if value['mode'] not in state.attributes.get('supported_color_modes', []):
                raise HomeAssistantError('Light color capabilities changed; capture a new preset')
            record = {'preset':name, 'entity_id':eid, 'status':'pending', 'preset_version':row['version'], 'expires_at':int(request_id[1:11])+600}
            saved = await self.scope.memory.async_put('operation',request_id,record)
            try:
                await self.policy.require_access(ctx, write=True)
                if self.policy.require_control(eid).id != value['registry_id']:
                    raise HomeAssistantError('Light registry identity changed before restore')
                state=self.scope.hass.states.get(eid)
                if not state or state.state in ('unknown','unavailable') or value['mode'] not in state.attributes.get('supported_color_modes',[]):
                    raise HomeAssistantError('Light availability or capabilities changed before restore')
                validate_request_id(request_id)
                await self.scope.hass.services.async_call('light','turn_on',
                    {'entity_id':eid, **value['service_data']}, blocking=True, context=ctx.context)
                await self.policy.require_access(ctx, write=True)
                if self.policy.require_control(eid).id != value['registry_id']:
                    raise HomeAssistantError('Light registry identity changed during restore')
                current = self.scope.hass.states.get(eid)
                verified = bool(current and current.state == 'on' and current.attributes.get('color_mode') == value['mode'])
                for key,expected in value['service_data'].items():
                    key = 'brightness' if key == 'white' else key
                    actual = current.attributes.get(key) if current else None
                    if isinstance(expected, list):
                        verified = verified and isinstance(actual,(list,tuple)) and len(actual)==len(expected) and all(type(a) in (int,float) and math.isfinite(a) and abs(a-b)<=(0.005 if key=='xy_color' else 1 if key=='hs_color' else 2) for a,b in zip(actual,expected))
                    else:
                        verified = verified and type(actual) in (int,float) and abs(actual-expected) <= (50 if key=='color_temp_kelvin' else 2)
                record['status'] = 'verified' if verified else 'unverified'
                record['note'] = 'HA reported matching state' if verified else 'Service accepted; exact state not yet verified. Query live state before repeating.'
            except Exception:
                # No blind retry: a failed response does not prove the device did nothing.
                record['status']='uncertain'
                record['note']='The operation did not complete with a verified result; inspect current state before any retry.'
            await self.scope.memory.async_put('operation', request_id, record, saved['version'])
            return record
