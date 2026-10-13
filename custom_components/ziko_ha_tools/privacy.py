"""Selective result projection and best-effort credential redaction."""
from collections.abc import Mapping
from datetime import datetime
import math
import re

SENSITIVE = re.compile(r'password|passwd|secret|token|authorization|cookie|api.?key', re.I)
SECRETS = (
    re.compile(r'(?im)\b((?:Authorization|Proxy-Authorization|Cookie|Set-Cookie)\s*:\s*)[^\r\n]+'),
    re.compile(r'(?i)\b(Bearer\s+)[\w.\-+/=]+'),
    re.compile(r'(?i)\b((?:password|passwd|secret|access_token|refresh_token|api_key|token)["\x27]?\s*[=:]\s*)(?:"(?:\\.|[^"\\\r\n])*"|\x27(?:\\.|[^\x27\\\r\n])*\x27|[^\s,;"\x27&]+)'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b'),
    re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
    re.compile(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/:]+:[^\s/@]+@'),
)


def sanitize(value, depth=0):
    if depth > 12:
        return '[omitted: nesting limit]'
    if isinstance(value, Mapping):
        return {str(k)[:120]: '[redacted]' if SENSITIVE.search(str(k)) else sanitize(v, depth + 1)
                for k, v in list(value.items())[:250]}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, depth + 1) for v in value[:250]]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        for pattern in SECRETS:
            value = pattern.sub(lambda m: (m.group(1) if m.lastindex else '') + '[redacted]', value)
        return value[:2000]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return '[omitted: unsupported value]'


def trace_summary(raw):
    allowed = ('run_id', 'state', 'script_execution', 'timestamp', 'last_step', 'error', 'not_triggered')
    result = {k: raw[k] for k in allowed if k in raw}
    steps = []
    for path, elements in (raw.get('trace') or {}).items():
        for item in elements:
            steps.append({'path': path, **{k: item[k] for k in ('timestamp', 'error', 'result', 'template_errors') if k in item}})
    result['steps'] = steps[-200:]
    result['steps_truncated'] = len(steps) > 200
    return sanitize(result)
