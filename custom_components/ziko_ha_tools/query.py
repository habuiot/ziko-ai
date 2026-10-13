"""Bounded, deterministic history processing; no Home Assistant dependency."""
from datetime import datetime, timedelta, timezone
import math
from collections.abc import Mapping


def parse_time(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (int, float)) and math.isfinite(value):
        result = datetime.fromtimestamp(value, timezone.utc)
    else:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Explicit timezone offset required')
    return result.astimezone(timezone.utc)


def parse_window(start, end, now, max_days):
    now = parse_time(now)
    end = min(parse_time(end), now) if end else now
    start = parse_time(start) if start else end - timedelta(days=1)
    if start >= end or end - start > timedelta(days=max_days):
        raise ValueError(f'Time window must be positive and at most {max_days} days')
    return start, end


def _field(record, name, default=None):
    return record.get(name, default) if isinstance(record, Mapping) else getattr(record, name, default)


def normalize_state(record, attribute):
    state = _field(record, 'state')
    attrs = _field(record, 'attributes', {}) or {}
    value = attrs.get(attribute) if attribute else state
    if state in ('unknown', 'unavailable'):
        value = None
    if value is not None and not isinstance(value, bool):
        try:
            numeric = float(value)
        except (ValueError, TypeError):
            pass
        else:
            value = numeric if math.isfinite(numeric) else None
    stamp = _field(record, 'last_updated') or _field(record, 'last_changed')
    return {'value': value, 'time': parse_time(stamp).isoformat(),
            'synthetic_boundary': bool(_field(record, 'synthetic_boundary', False)),
            'unit': attrs.get('unit_of_measurement') or
                    (attrs.get('temperature_unit') if attribute in ('current_temperature', 'temperature') else None),
            'attribute': attribute}


def matches(value, predicate):
    if not predicate or value is None:
        return False
    op, expected = predicate['operator'], predicate['value']
    if op in ('eq', 'ne'):
        try:
            left, right = float(value), float(expected)
        except (ValueError, TypeError):
            equal = str(value).casefold() == str(expected).casefold()
        else:
            equal = math.isfinite(left) and math.isfinite(right) and left == right
        return equal if op == 'eq' else not equal
    try:
        left, right = float(value), float(expected)
    except (ValueError, TypeError):
        return False
    if not math.isfinite(left) or not math.isfinite(right):
        return False
    if op == 'gt':
        return left > right
    if op == 'gte':
        return left >= right
    if op == 'lt':
        return left < right
    if op == 'lte':
        return left <= right
    raise ValueError('Unsupported comparison')


def summarize_history(records, predicate, limit, window):
    start, end = window
    ordered = sorted(records, key=lambda r: parse_time(r['time']))
    boundary = [r for r in ordered if parse_time(r['time']) < start]
    within = [r for r in ordered if start <= parse_time(r['time']) <= end]
    matching = [r for r in within if matches(r['value'], predicate)]
    numeric = [float(r['value']) for r in within
               if isinstance(r['value'], (int, float)) and not isinstance(r['value'], bool)]
    return {'records': within[-limit:], 'processed_records': len(within),
            'state_at_window_start': boundary[-1] if boundary else None,
            'last_match': matching[-1] if matching else None,
            'last_observation': within[-1] if within else None,
            'unknown_records': sum(r['value'] is None for r in within),
            'minimum': min(numeric) if numeric else None,
            'maximum': max(numeric) if numeric else None,
            'presentation_truncated': len(within) > limit,
            'note': 'Last match is a recorded observation, not an interpolated crossing or interval end.'}
