"""Precise but allowlisted state projection; never arbitrary attributes."""
from datetime import datetime, timezone
import math

from homeassistant.helpers import entity_registry as er

ATTRIBUTES = frozenset({
    'friendly_name', 'unit_of_measurement', 'device_class', 'state_class',
    'current_temperature', 'temperature', 'target_temp_low', 'target_temp_high',
    'current_humidity', 'humidity', 'hvac_action', 'hvac_modes', 'preset_mode',
    'min_temp', 'max_temp', 'target_temp_step', 'brightness', 'color_mode',
    'supported_color_modes', 'color_temp_kelvin', 'min_color_temp_kelvin',
    'max_color_temp_kelvin', 'rgb_color', 'rgbw_color', 'rgbww_color', 'hs_color',
    'xy_color', 'effect', 'effect_list', 'volume_level', 'is_volume_muted',
    'media_title', 'media_artist', 'current_position', 'battery_level', 'supported_features',
})


def safe_value(value, depth=0):
    if depth > 2:
        return None
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        # Free-form media/name values are data only, capped and without URLs.
        return value[:160] if '://' not in value else '[URL omitted]'
    if isinstance(value, (list, tuple, set, frozenset)):
        return [safe_value(v, depth+1) for v in list(value)[:20]]
    return None


class Catalogue:
    def __init__(self, scope):
        self.scope = scope

    def snapshot(self, ids):
        self.scope.require_entities(ids)
        result = []
        for eid in ids:
            state = self.scope.hass.states.get(eid)
            entry = er.async_get(self.scope.hass).async_get(eid)
            result.append({'entity_id': eid, 'state': state.state if state else None,
                'available': bool(state and state.state not in ('unknown', 'unavailable')),
                'attributes': {k: safe_value(v) for k,v in state.attributes.items() if k in ATTRIBUTES} if state else {},
                'last_updated': state.last_updated.isoformat() if state else None,
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'registered': bool(entry)})
        return {'entities': result, 'timezone': self.scope.hass.config.time_zone}
