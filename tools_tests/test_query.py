from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    path = ROOT / 'custom_components' / 'ziko_ha_tools' / f'{name}.py'
    assert path.exists(), f'{name} implementation is missing'
    spec = importlib.util.spec_from_file_location(f'ziko_{name}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_attribute_only_temperature_uses_updated_time():
    q = module('query')
    row = {'state': 'heat', 'last_changed': '2026-10-12T00:00:00+00:00',
           'last_updated': '2026-10-12T02:00:00+00:00',
           'attributes': {'current_temperature': 28.1, 'temperature': 19}}
    result = q.normalize_state(row, 'current_temperature')
    assert result['value'] == 28.1
    assert result['time'] == '2026-10-12T02:00:00+00:00'


def test_last_threshold_match_is_computed_before_output_trimming():
    q = module('query')
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    rows = [{'value': 28 if i in (3, 201) else 25,
             'time': (start + timedelta(minutes=i)).isoformat()} for i in range(400)]
    result = q.summarize_history(rows, {'operator': 'gt', 'value': 27}, 10,
                                 (start, start + timedelta(days=1)))
    assert result['last_match']['time'] == rows[201]['time']
    assert len(result['records']) <= 10
    assert result['processed_records'] == 400
    assert result['presentation_truncated'] is True


def test_unknown_gap_is_not_a_numeric_value():
    q = module('query')
    row = {'state': 'unavailable', 'last_updated': '2026-10-12T02:00:00+00:00'}
    assert q.normalize_state(row, None)['value'] is None


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_values_are_unknown(value):
    q = module('query')
    assert q.normalize_state({'state': value, 'last_updated': '2026-10-12T02:00:00+00:00'}, None)['value'] is None


def test_window_rejects_naive_and_oversized_queries():
    q = module('query')
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        q.parse_window('2026-10-12T00:00:00', None, now, 14)
    with pytest.raises(ValueError):
        q.parse_window('2026-09-01T00:00:00Z', None, now, 14)


def test_window_converts_budapest_and_dst_offsets_to_utc():
    q = module('query')
    start, end = q.parse_window('2026-10-25T02:30:00+02:00',
                               '2026-10-25T02:30:00+01:00',
                               datetime(2026, 10, 26, tzinfo=timezone.utc), 14)
    assert end - start == timedelta(hours=1)
    assert start.hour == 0 and end.hour == 1


def test_boundary_state_is_not_a_new_threshold_observation():
    q = module('query')
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    rows = [{'value': 28, 'time': '2026-10-11T23:00:00+00:00'}]
    result = q.summarize_history(rows, {'operator': 'gt', 'value': 27}, 200,
                                 (start, start + timedelta(days=1)))
    assert result['last_match'] is None
    assert result['state_at_window_start']['value'] == 28



def test_numeric_equality_and_climate_unit():
    q = module('query')
    assert q.matches(28.0, {'operator': 'eq', 'value': 28})
    record = {'state': 'heat', 'attributes': {'current_temperature': 28, 'temperature_unit': '°C'},
              'last_updated': '2026-10-13T12:00:00Z'}
    assert q.normalize_state(record, 'current_temperature')['unit'] == '°C'
