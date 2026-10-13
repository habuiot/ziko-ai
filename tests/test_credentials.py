import json
import os
import pytest
from ziko.credentials import CredentialStore
import ziko.credentials as credentials

def record(**changes):
    return dict(issuer='https://auth.openai.com',subject='user',client_id='oaiapp_test',
                access_token='ACCESS_SECRET',refresh_token='REFRESH_SECRET',id_token='ID_SECRET',
                scopes=['chatgpt.tokens.use.direct','offline_access','resource.invoke'],expires_at=9999999999,**changes)

def test_atomic_write_and_owner_only_permissions(tmp_path):
    s=CredentialStore(tmp_path);s.replace(record());assert s.load()==record()
    assert os.stat(s.path).st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob('*.tmp'))

def test_import_preserves_runtime_host_id(tmp_path):
    s=CredentialStore(tmp_path);host=s.host_id();s.replace(record(ext_agent_host_id='foreign'))
    assert CredentialStore(tmp_path).host_id()==host

def test_invalid_import_preserves_existing_account(tmp_path):
    s=CredentialStore(tmp_path);s.replace(record())
    for bad in [{},dict(record(),issuer='evil'),dict(record(),client_id='dynamic_agent_client'),dict(record(),scopes=[])]:
        with pytest.raises(ValueError): s.replace(bad)
        assert s.load()==record()

def test_status_never_exposes_access_or_refresh_token(tmp_path):
    s=CredentialStore(tmp_path);s.replace(record())
    v=json.dumps(s.status());assert 'SECRET' not in v;assert 'token' not in v
    s.disconnect();assert s.load() is None

def test_import_is_one_time_and_preserves_rotated_session(tmp_path):
    s=CredentialStore(tmp_path);s.import_once(record())
    s.replace(dict(record(),refresh_token='ROTATED_SECRET'))
    s=CredentialStore(tmp_path)
    with pytest.raises(ValueError,match='importál'):s.import_once(record())
    assert s.load()['refresh_token']=='ROTATED_SECRET'
    s.disconnect()
    with pytest.raises(ValueError):s.import_once(record())

def test_non_posix_writer_avoids_unix_only_calls(tmp_path,monkeypatch):
    monkeypatch.setattr(credentials,'IS_POSIX',False)
    def forbidden(*args):raise AssertionError('Unix-only fd operation')
    monkeypatch.setattr(credentials.os,'fchmod',forbidden)
    s=CredentialStore(tmp_path);s.replace(record())
    assert s.load()==record()
