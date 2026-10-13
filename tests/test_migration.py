import json
import pytest
from ziko.migration import export_data, decode_data, restore_data
from ziko.storage import Storage
from ziko.credentials import CredentialStore
from ziko.credentials import atomic_json
from test_credentials import record


def test_encrypted_transfer_preserves_history_memory_and_scope(tmp_path):
    source=tmp_path/'source';source.mkdir()
    store=CredentialStore(source);storage=Storage(source/'chat.sqlite')
    store.replace(record())
    atomic_json(source/'imported-sessions.json',dict(fingerprints=['receipt']))
    storage.save_memory(None,'Private memory','manual')
    storage.setting('model','chosen-model')
    cid=storage.create_conversation('Private conversation')
    storage.add_message(cid,'user','PRIVATE TEXT','completed','request')
    payload=export_data(storage,source,'owner',{'a'*32},'long password 123')
    assert 'PRIVATE TEXT' not in payload and 'owner' not in payload and 'REFRESH_SECRET' not in payload
    decoded=decode_data(payload,'long password 123','owner')
    dest=tmp_path/'dest';dest.mkdir()
    restored=Storage(dest/'chat.sqlite');restored.close()
    restore_data(dest,decoded)
    result=Storage(dest/'chat.sqlite')
    assert result.messages(cid)[0]['text']=='PRIVATE TEXT'
    assert CredentialStore(dest).host_id()==store.host_id()
    assert CredentialStore(dest).load()==record()
    assert result.memories()[0]['text']=='Private memory'
    assert result.setting('model')=='chosen-model'
    assert json.loads((dest/'imported-sessions.json').read_text())==dict(fingerprints=['receipt'])
    assert json.loads((dest/'approved-devices.json').read_text())==['a'*32]
    result.close();storage.close()


def test_invalid_password_and_owner_do_not_modify_destination(tmp_path):
    store=CredentialStore(tmp_path);storage=Storage(tmp_path/'chat.sqlite')
    payload=export_data(storage,tmp_path,'owner',set(),'long password 123')
    for password,owner in [('wrong password 123','owner'),('long password 123','other')]:
        with pytest.raises(ValueError):decode_data(payload,password,owner)
    with pytest.raises(ValueError):export_data(storage,tmp_path,'owner',set(),'short')
    storage.close()
