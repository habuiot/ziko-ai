import asyncio
from contextlib import asynccontextmanager, aclosing
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import httpx
from .access import INGRESS_IP, USER_HEADER, require_operator
from .chat import ChatService
from .ha_observer import HouseObserver
from .credentials import CredentialStore, atomic_json
from .oauth import ensure_access_token, validate_import, disconnect_account
from .provider import list_models, stream_reply
from .settings import Settings
from .storage import Storage
from .migration import export_data, decode_data, restore_data, MAX_SIZE

WEB=Path(__file__).parent/'web'

async def read_json(req,limit=65536):
    if req.headers.get('content-type','').split(';')[0]!='application/json':raise ValueError('JSON-adat szükséges')
    content=bytearray()
    async for piece in req.stream():
        content.extend(piece)
        if len(content)>limit:raise ValueError('Túl nagy kérés')
    try: value=json.loads(content)
    except (ValueError,UnicodeDecodeError):raise ValueError('Hibás JSON-adat') from None
    if not isinstance(value,dict):raise ValueError('JSON-objektum szükséges')
    return value

def create_app(settings: Settings, client: httpx.AsyncClient | None = None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store=CredentialStore(settings.data_dir)
        app.state.storage=Storage(settings.data_dir/'chat.sqlite')
        app.state.http=client or httpx.AsyncClient(timeout=httpx.Timeout(30,read=90),follow_redirects=False)
        app.state.connection_busy=False
        app.state.migration_frozen=(settings.data_dir/'migration-frozen.json').exists()
        app.state.account_epoch=0
        async def provide(model,messages,instructions):
            token=await ensure_access_token(app.state.store,app.state.http)
            async with aclosing(stream_reply(app.state.http,token,model,messages,instructions)) as source:
                async for event in source:yield event
        app.state.house=HouseObserver(settings.supervisor_token)
        if settings.operator_user_id and not app.state.migration_frozen:app.state.house.start()
        app.state.chat=ChatService(app.state.storage,provide,house_context=app.state.house.context)
        try:yield
        finally:
            await app.state.house.stop()
            if app.state.chat.busy:await app.state.chat.cancel(app.state.chat.run.request_id)
            app.state.storage.close()
            if client is None:await app.state.http.aclose()

    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

    @app.middleware('http')
    async def access(request,call_next):
        peer=request.client.host if request.client else ''
        user=request.headers.get(USER_HEADER)
        try:
            if peer!=INGRESS_IP or not user:raise PermissionError()
            if settings.operator_user_id:require_operator(peer,user,settings.operator_user_id)
            elif request.url.path not in ('/','/setup','/status','/app.js','/style.css'):raise PermissionError()
            if request.method not in ('GET','HEAD'):
                if request.headers.get('X-Ziko-Request')!='1' or request.headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError()
        except PermissionError:return JSONResponse({'error':'Hozzáférés megtagadva'},status_code=403)
        if app.state.migration_frozen and (request.method not in ('GET','HEAD') or request.url.path=='/models') and request.url.path not in ('/migration/export','/migration/cancel'):
            return JSONResponse({'error':'Költöztetési mentés elkészült. Állítsd le a régi alkalmazást, vagy szakítsd meg a költöztetést.'},status_code=423)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def value_error(req,exc):return JSONResponse({'error':str(exc)},status_code=400)
    @app.exception_handler(KeyError)
    async def key_error(req,exc):return JSONResponse({'error':'A kért elem nem található'},status_code=404)
    @app.exception_handler(httpx.HTTPError)
    async def http_error(req,exc):return JSONResponse({'error':'A külső kapcsolat átmenetileg nem elérhető'},status_code=503)

    def idle(*,allow_frozen=False):
        if app.state.chat.busy or app.state.connection_busy:raise ValueError('Egy művelet már folyamatban van')
        if app.state.migration_frozen and not allow_frozen:raise ValueError('Költöztetés miatt a régi alkalmazás szünetel')

    async def catalog():
        idle()
        if app.state.connection_busy:raise ValueError('Fiókváltás folyamatban')
        epoch=app.state.account_epoch
        token=await ensure_access_token(app.state.store,app.state.http)
        result=await list_models(app.state.http,token)
        if epoch!=app.state.account_epoch or app.state.connection_busy or app.state.migration_frozen:
            raise ValueError('A fiókkapcsolat megváltozott; ismételd meg a műveletet')
        return result

    @app.get('/')
    async def index():return FileResponse(WEB/'index.html')
    @app.get('/app.js')
    async def js():return FileResponse(WEB/'app.js',media_type='application/javascript')
    @app.get('/style.css')
    async def css():return FileResponse(WEB/'style.css',media_type='text/css')

    @app.get('/setup')
    async def setup(req: Request):
        return dict(user_id=req.headers.get(USER_HEADER),operator_configured=bool(settings.operator_user_id))

    @app.get('/status')
    async def status():
        if not settings.operator_user_id:return dict(operator_configured=False,connected=False,busy=False)
        return dict(app.state.store.status(),operator_configured=True,busy=app.state.chat.busy,
                    migration_frozen=app.state.migration_frozen,selected_model=app.state.storage.setting('model'),version='0.3.0',stage='B – folyamatos megfigyelés')

    @app.get('/house')
    async def house():return app.state.house.snapshot()

    @app.post('/migration/export')
    async def migration_export(req: Request):
        data=await read_json(req,4096);idle(allow_frozen=True);app.state.connection_busy=True
        try:
            async with app.state.store.refresh_lock:
                payload=export_data(app.state.storage,settings.data_dir,settings.operator_user_id,
                                    app.state.house.approved,data.get('password'))
                atomic_json(settings.data_dir/'migration-frozen.json',dict(frozen=True))
                app.state.migration_frozen=True
                app.state.account_epoch+=1
                await app.state.house.stop()
                return dict(file=payload)
        finally:app.state.connection_busy=False

    @app.post('/migration/cancel')
    async def migration_cancel():
        idle(allow_frozen=True);(settings.data_dir/'migration-frozen.json').unlink(missing_ok=True)
        app.state.migration_frozen=False;app.state.house.start()
        return dict(ok=True)

    @app.post('/migration/import')
    async def migration_import(req: Request):
        data=await read_json(req,MAX_SIZE+4096);idle()
        conversations=app.state.storage.conversations()
        has_history=len(conversations)>1 or any(c['title']!='Új beszélgetés' or app.state.storage.messages(c['id']) for c in conversations)
        prior_usage=any((settings.data_dir/name).exists() for name in ('imported-sessions.json','migration-imported.json'))
        if prior_usage or app.state.store.load() or has_history or app.state.storage.memories():
            raise ValueError('Költöztetési fájlt csak üres új alkalmazásba lehet importálni')
        record=decode_data(data.get('file'),data.get('password'),settings.operator_user_id)
        app.state.connection_busy=True
        try:
            await app.state.house.stop()
            app.state.storage.close()
            try:restore_data(settings.data_dir,record)
            finally:
                app.state.storage=Storage(settings.data_dir/'chat.sqlite')
                app.state.chat.storage=app.state.storage
            app.state.store=CredentialStore(settings.data_dir)
            app.state.account_epoch+=1
            app.state.house=HouseObserver(settings.supervisor_token,approved=record['approved_devices'])
            app.state.chat.house_context=app.state.house.context
            app.state.house.start()
            return dict(ok=True)
        finally:app.state.connection_busy=False

    @app.post('/connection/import')
    async def import_connection(req: Request):
        record=await read_json(req);idle();app.state.connection_busy=True
        app.state.account_epoch+=1
        try:
            async with app.state.store.refresh_lock:
                validated=await validate_import(record,app.state.http)
                app.state.store.import_once(validated)
                app.state.storage.setting('model','')
            return {'ok':True}
        finally:app.state.connection_busy=False

    @app.delete('/connection')
    async def disconnect():
        idle();app.state.connection_busy=True
        app.state.account_epoch+=1
        try:
            confirmed=await disconnect_account(app.state.store,app.state.http)
            app.state.storage.setting('model','')
            return dict(ok=True,remote_revocation_confirmed=confirmed)
        finally:app.state.connection_busy=False

    @app.get('/models')
    async def models():
        if app.state.connection_busy:raise ValueError('Fiókváltás folyamatban')
        return {'models':await catalog()}

    @app.post('/model')
    async def model(req: Request):
        data=await read_json(req,4096);idle()
        if data.get('slug') not in [m['slug'] for m in await catalog()]:raise ValueError('Válassz elérhető modellt')
        idle()
        app.state.storage.setting('model',data['slug']);return {'ok':True}

    @app.get('/conversations')
    async def conversations():return {'conversations':app.state.storage.conversations()}
    @app.post('/conversations')
    async def new_conversation(req: Request):
        data=await read_json(req,4096);idle();return {'id':app.state.storage.create_conversation(data.get('title','Új beszélgetés'))}
    @app.get('/conversations/{cid}/messages')
    async def messages(cid: str):return {'messages':app.state.storage.messages(cid)}
    @app.get('/conversations/{cid}/export')
    async def export(cid: str):
        return JSONResponse(app.state.storage.export(cid),headers={'Content-Disposition':'attachment; filename="ziko-beszelgetes.json"'})
    @app.delete('/conversations/{cid}')
    async def delete(cid: str):
        idle();app.state.storage.delete_conversation(cid);return {'ok':True}

    @app.get('/memory')
    async def memory():return {'memories':app.state.storage.memories()}
    @app.post('/memory')
    async def save_memory(req: Request):
        data=await read_json(req);idle();mid=data.get('id')
        if mid is not None and not isinstance(mid,str):raise ValueError('Hibás azonosító')
        return {'id':app.state.storage.save_memory(mid,data.get('text'),data.get('source','kézzel mentett'))}
    @app.delete('/memory/{mid}')
    async def delete_memory(mid: str):
        idle();app.state.storage.delete_memory(mid);return {'ok':True}

    @app.post('/chat')
    async def chat(req: Request):
        data=await read_json(req,32768);idle()
        cid=data.get('conversation_id');text=data.get('text')
        if not isinstance(cid,str):raise ValueError('Válassz beszélgetést')
        if not isinstance(text,str) or not text.strip() or len(text)>4000:raise ValueError('Az üzenet 1–4000 karakter legyen')
        model=app.state.storage.setting('model')
        if not model:raise ValueError('Válassz modellt')
        if model not in [m['slug'] for m in await catalog()]:raise ValueError('A modell már nem elérhető; válassz másikat')
        idle()
        run=app.state.chat.begin(cid,text,model)
        async def stream():
            async for event in app.state.chat.events(run):
                yield 'data: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

    @app.post('/chat/cancel')
    async def cancel(req: Request):
        data=await read_json(req,4096)
        await app.state.chat.cancel(data.get('request_id'))
        return {'ok':True}
    return app

app=create_app(Settings.environment())
