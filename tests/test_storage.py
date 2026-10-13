import pytest
from ziko.storage import Storage

def test_hungarian_history_persists_after_reopen(tmp_path):
    p=tmp_path/'chat.sqlite';s=Storage(p);cid=s.create_conversation('Árvíztűrő')
    s.add_message(cid,'user','Öt lámpát kérek','completed');s.close()
    s=Storage(p);assert s.messages(cid)[0]['text']=='Öt lámpát kérek';s.close()

def test_partial_reply_not_saved_as_completed(tmp_path):
    s=Storage(tmp_path/'chat.sqlite');cid=s.create_conversation()
    s.add_message(cid,'assistant','részleges','failed');assert s.context(cid)==[]

def test_delete_and_export_are_conversation_scoped(tmp_path):
    s=Storage(tmp_path/'chat.sqlite');a=s.create_conversation();b=s.create_conversation()
    s.add_message(a,'user','első','completed');s.add_message(b,'user','második','completed')
    assert s.export(a)['messages'][0]['text']=='első';s.delete_conversation(a)
    assert s.messages(b)[0]['text']=='második'
    with pytest.raises(KeyError):s.messages(a)

def test_explicit_memory_limits_and_sources(tmp_path):
    s=Storage(tmp_path/'chat.sqlite');mid=s.save_memory(None,'Mesterem','felhasználó')
    assert s.memories()[0]['source']=='felhasználó';assert s.memories()[0]['updated_at']
    s.save_memory(mid,'András','javítás');assert len(s.memories())==1
    with pytest.raises(ValueError):s.save_memory(None,'x'*8001,'kézi')
    s.delete_memory(mid);assert s.memories()==[]

def test_context_is_bounded_and_failed_turns_excluded(tmp_path):
    s=Storage(tmp_path/'chat.sqlite');cid=s.create_conversation()
    for i in range(30):s.add_message(cid,'user','x'*1000,'completed')
    context=s.context(cid);assert len(context)<=20;assert sum(len(x['content']) for x in context)<=24000
