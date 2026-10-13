import json
import httpx
from ziko.provider import list_models, stream_reply

async def test_catalog_preserves_visible_server_order():
    data={'models':[dict(slug='b',display_name='B',visibility='list'),dict(slug='x',display_name='X',visibility='hidden'),dict(slug='a',display_name='A',visibility='list')]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as c:
        assert [x['slug'] for x in await list_models(c,'secret')]==['b','a']

async def events(body,status=200):
    requests=[]
    def respond(req):
        requests.append(json.loads(req.content));return httpx.Response(status,text=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
        output=[x async for x in stream_reply(c,'secret','test',[{'role':'user','content':'hello'}],'magyar')]
    return output,requests

async def test_requires_store_false_and_stream_true():
    out,req=await events('data: {"type":"response.output_text.delta","delta":"Szia"}\n\ndata: {"type":"response.completed","response":{"status":"completed"}}\n\n')
    assert req[0]['store'] is False and req[0]['stream'] is True
    assert out==[dict(type='delta',text='Szia'),dict(type='completed')]

async def test_no_unsupported_request_fields():
    _,req=await events('')
    assert set(req[0])=={'model','input','instructions','store','stream'}

async def test_midstream_subscription_limit_is_failure():
    out,_=await events('data: {"type":"response.output_text.delta","delta":"rész"}\n\ndata: {"type":"response.failed","response":{"error":{"code":"usage_limit_reached"}}}\n\n')
    assert out[-1]['type']=='failed';assert out[-1]['code']=='limit'
    assert not any(x['type']=='completed' for x in out)

async def test_disconnect_without_completed_is_failure():
    out,_=await events('data: {"type":"response.output_text.delta","delta":"rész"}\n\n')
    assert out[-1]['code']=='interrupted'

async def test_no_automatic_paid_api_fallback():
    out,req=await events('{"error":"secret server diagnostic"}',429)
    assert len(req)==1;assert out==[dict(type='failed',code='limit',message='Keret elfogyott')]

async def test_multiline_sse_and_invalid_completion():
    out,_=await events('event: event\ndata: {"type":\ndata: "response.completed", "response":{"status":"incomplete"}}\n\n')
    assert out[-1]['type']=='failed'
