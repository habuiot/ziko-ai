import asyncio
import time
from urllib.parse import parse_qs
import httpx
import pytest
from ziko.credentials import CredentialStore
from ziko.oauth import ensure_access_token
from test_credentials import record

async def test_refresh_is_single_flight_and_rotates_atomically(tmp_path):
    s=CredentialStore(tmp_path);s.replace(dict(record(),expires_at=1));calls=[]
    async def respond(req):
        calls.append(parse_qs(req.content.decode()));await asyncio.sleep(.02)
        return httpx.Response(200,json=dict(access_token='new',refresh_token='rotated',expires_in=3600,token_type='Bearer'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
        assert await asyncio.gather(*[ensure_access_token(s,c) for _ in range(5)])==['new']*5
    assert len(calls)==1;assert 'scope' not in calls[0];assert s.load()['refresh_token']=='rotated'

async def test_refresh_error_preserves_record(tmp_path):
    s=CredentialStore(tmp_path);r=dict(record(),expires_at=1);s.replace(r)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(400,json={'error':'invalid_grant'}))) as c:
        with pytest.raises(ValueError,match='jelentkez'):await ensure_access_token(s,c)
    assert s.load()==r
