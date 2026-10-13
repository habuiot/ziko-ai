from pathlib import Path
import json
import httpx
import pytest
from ziko.main import create_app
import ziko.main as ziko_main
from ziko.settings import Settings
from test_credentials import record
import asyncio

async def request(tmp_path,path,method='GET',payload=None,operator='owner',peer='172.30.32.2',user='owner',extra=None):
    def no_network(req):
        raise AssertionError('Ez a teszt nem kér külső kapcsolatot')
    external=httpx.AsyncClient(transport=httpx.MockTransport(no_network))
    app=create_app(Settings(tmp_path,operator),external)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=(peer,123)),base_url='http://ziko') as c:
            headers={'X-Remote-User-Id':user,'X-Ziko-Request':'1'};headers.update(extra or {})
            try:return await c.request(method,path,json=payload,headers=headers)
            finally:await external.aclose()

async def test_missing_operator_only_shows_setup(tmp_path):
    assert (await request(tmp_path,'/setup',operator='')).json()['user_id']=='owner'
    assert (await request(tmp_path,'/chat','POST',{},operator='')).status_code==403
    assert (await request(tmp_path,'/connection/import','POST',{},operator='')).status_code==403

async def test_untrusted_peer_and_wrong_user_denied(tmp_path):
    assert (await request(tmp_path,'/status',peer='127.0.0.1')).status_code==403
    assert (await request(tmp_path,'/status',user='wrong')).status_code==403


async def test_migration_is_owner_only_and_refuses_existing_data(tmp_path):
    password='migration password 123'
    assert (await request(tmp_path,'/migration/export','POST',{'password':password},user='wrong')).status_code==403
    exported=await request(tmp_path,'/migration/export','POST',{'password':password})
    assert exported.status_code==200
    frozen=await request(tmp_path,'/models')
    assert frozen.status_code==423
    imported=await request(tmp_path/'new','/migration/import','POST',{'password':password,'file':exported.json()['file']})
    assert imported.status_code==200
    replay=await request(tmp_path/'new','/migration/import','POST',{'password':password,'file':exported.json()['file']})
    assert replay.status_code==400
    await request(tmp_path/'new','/conversations','POST',{'title':'Existing data'})
    again=await request(tmp_path/'new','/migration/import','POST',{'password':password,'file':exported.json()['file']})
    assert again.status_code==400
    resumed=await request(tmp_path,'/migration/cancel','POST',{})
    assert resumed.status_code==200
    assert not (tmp_path/'migration-frozen.json').exists()


async def test_chat_waiting_for_catalog_cannot_start_after_export(tmp_path,monkeypatch):
    entered=asyncio.Event();release=asyncio.Event()
    async def token(*args):return 'test-token'
    async def delayed_models(*args):
        entered.set();await release.wait();return [dict(slug='m',display_name='M')]
    monkeypatch.setattr(ziko_main,'ensure_access_token',token)
    monkeypatch.setattr(ziko_main,'list_models',delayed_models)
    external=httpx.AsyncClient(transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(AssertionError('No provider call'))))
    app=create_app(Settings(tmp_path,'owner'),external)
    async with app.router.lifespan_context(app):
        cid=app.state.storage.create_conversation();app.state.storage.setting('model','m')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('172.30.32.2',1)),base_url='http://ziko') as c:
            headers={'X-Remote-User-Id':'owner','X-Ziko-Request':'1'}
            waiting=asyncio.create_task(c.post('/chat',json={'conversation_id':cid,'text':'Hello'},headers=headers))
            await entered.wait()
            exported=await c.post('/migration/export',json={'password':'migration password 123'},headers=headers)
            assert exported.status_code==200
            release.set();response=await waiting
            assert response.status_code==400
            assert not app.state.storage.messages(cid)
    await external.aclose()

async def test_client_never_receives_credential_fields(tmp_path):
    r=await request(tmp_path,'/status');assert r.status_code==200
    assert not any(k in r.text for k in ['access_token','refresh_token','id_token','options.json'])

async def test_csrf_rejected(tmp_path):
    r=await request(tmp_path,'/conversations','POST',{},extra={'X-Ziko-Request':''})
    assert r.status_code==403

async def test_conversations_crud_through_api(tmp_path):
    r=await request(tmp_path,'/conversations','POST',{'title':'Árvíztűrő'})
    assert r.status_code==200;cid=r.json()['id']
    assert (await request(tmp_path,f'/conversations/{cid}/export')).json()['conversation']['title']=='Árvíztűrő'
    assert (await request(tmp_path,f'/conversations/{cid}','DELETE')).status_code==200
    assert (await request(tmp_path,f'/conversations/{cid}/messages')).status_code==404

def test_relative_ingress_paths():
    js=(Path(__file__).parents[1]/'ziko_ai/src/ziko/web/app.js').read_text()
    assert "fetch('/" not in js and 'fetch("/' not in js
    assert 'new URL' in js

def test_html_escaping_for_messages_and_memory():
    js=(Path(__file__).parents[1]/'ziko_ai/src/ziko/web/app.js').read_text()
    assert 'textContent' in js
    assert 'innerHTML' not in js and 'localStorage' not in js

def test_response_failed_after_delta_is_visible():
    js=(Path(__file__).parents[1]/'ziko_ai/src/ziko/web/app.js').read_text()
    assert "case 'failed'" in js and 'Válasz félbeszakadt' in js

@pytest.mark.parametrize('path,payload',[('/model',{'slug':'old'}),('/chat',{'text':'Szia'})])
async def test_account_change_rejects_pending_catalog(tmp_path,path,payload):
    entered=asyncio.Event();release=asyncio.Event()
    async def respond(req):
        if req.url.path=='/v1/models':
            entered.set();await release.wait()
            return httpx.Response(200,json={'models':[dict(slug='old',display_name='Old',visibility='list')]})
        if req.url.path=='/.well-known/openid-configuration':
            return httpx.Response(200,json={'revocation_endpoint':'https://auth.openai.com/revoke'})
        return httpx.Response(200)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        app=create_app(Settings(tmp_path,'owner'),external)
        async with app.router.lifespan_context(app):
            app.state.store.replace(record());app.state.storage.setting('model','old')
            payload=dict(payload,conversation_id=app.state.storage.create_conversation())
            headers={'X-Remote-User-Id':'owner','X-Ziko-Request':'1'}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('172.30.32.2',1)),base_url='http://ziko',headers=headers) as c:
                pending=asyncio.create_task(c.post(path,json=payload));await entered.wait()
                assert (await c.delete('/connection')).status_code==200
                release.set();result=await pending
                assert result.status_code==400
                assert app.state.storage.setting('model')==''
                assert not app.state.chat.busy

async def test_full_chat_route_closes_inner_stream_and_persists_failure(tmp_path,monkeypatch):
    closed=asyncio.Event()
    held=[]
    def source(*args):
        async def events():
            try:
                yield {'type':'delta','text':'részleges'}
                yield {'type':'failed','code':'limit','message':'Keret elfogyott'}
            finally:closed.set()
        generator=events();held.append(generator);return generator
    monkeypatch.setattr(ziko_main,'stream_reply',source)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'models':[dict(slug='m',display_name='M',visibility='list')]}))) as external:
        app=create_app(Settings(tmp_path,'owner'),external)
        async with app.router.lifespan_context(app):
            app.state.store.replace(record());app.state.storage.setting('model','m')
            cid=app.state.storage.create_conversation()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('172.30.32.2',1)),base_url='http://ziko',headers={'X-Remote-User-Id':'owner','X-Ziko-Request':'1'}) as c:
                r=await c.post('/chat',json={'conversation_id':cid,'text':'Szia'})
                assert r.status_code==200 and 'Keret elfogyott' in r.text
                assert app.state.storage.messages(cid)[-1]['status']=='failed'
                assert closed.is_set()
