"""Approved device IDs are local configuration, never public source defaults."""
import json
import os
import re
from pathlib import Path

DEFAULT_APPROVED_DEVICES = frozenset()

def validate_devices(value):
    if not isinstance(value,list) or any(not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{32}',v) for v in value):
        raise ValueError('Hibás Házikó-eszközlista')
    return frozenset(value)

def approved_devices():
    local=Path(os.environ.get('ZIKO_DATA_DIR','/data/ziko'))/'approved-devices.json'
    if local.exists():
        return validate_devices(json.loads(local.read_text()))
    raw=os.environ.get('ZIKO_APPROVED_DEVICE_IDS')
    if raw is None:return DEFAULT_APPROVED_DEVICES
    try:return validate_devices(json.loads(raw))
    except (TypeError,json.JSONDecodeError):raise ValueError('Hibás Házikó-eszközlista') from None
