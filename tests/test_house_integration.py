import json
import httpx
from starlette.testclient import TestClient
from ziko.main import create_app
from ziko.settings import Settings
from ziko.access import USER_HEADER
from ziko.chat import ChatService
from ziko.storage import Storage

async def test_chat_gets_observation_as_data_with_stale_instruction(tmp_path):
    seen=[]
    async def provider(model,messages,instructions):
        seen.append(instructions);yield {'type':'completed'}
    s=Storage(tmp_path/'db');cid=s.create_conversation()
    chat=ChatService(s,provider,house_context=lambda:{'fresh':False,'entities':[{'entity_id':'light.x','state':'on'}]})
    chat.begin(cid,'Mi a helyzet?','m');await chat.task
    assert 'light.x' in seen[0] and 'false' in seen[0]
    assert 'elavult' in seen[0]
    assert s.memories()==[]


def test_house_endpoint_is_operator_only(tmp_path):
    app=create_app(Settings(tmp_path,'owner'),httpx.AsyncClient(trust_env=False))
    with TestClient(app,client=('172.30.32.2',123)) as client:
        assert client.get('/house',headers={USER_HEADER:'owner'}).status_code==200
        assert client.get('/house',headers={USER_HEADER:'other'}).status_code==403
        result=client.get('/house',headers={USER_HEADER:'owner'}).json()
        assert result['fresh'] is False and result['mode']=='read_only'
        assert 'token' not in json.dumps(result)
