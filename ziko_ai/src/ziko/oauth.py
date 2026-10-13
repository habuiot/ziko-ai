import base64
from dataclasses import dataclass
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode
import httpx
import jwt
from .credentials import ISSUER, PLAN_SCOPE, CredentialStore, validate_record

RESOURCE='https://api.openai.com/v1'
TOKEN_URL=ISSUER+'/api/accounts/oauth/token'
JWKS_URL=ISSUER+'/.well-known/jwks.json'
SCOPES='openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'

@dataclass
class PendingLogin:
    state: str
    nonce: str
    verifier: str
    redirect: str
    client_id: str
    host_id: str
    url: str
    created: float
    subject: str | None = None
    consumed: bool = False

def begin_login(host_id: str, port: int, existing: dict | None = None) -> PendingLogin:
    if not 1 <= port <= 65535: raise ValueError('Hibás helyi port')
    state,nonce,verifier=(secrets.token_urlsafe(32) for _ in range(3))
    redirect=f'http://127.0.0.1:{port}/auth/callback'
    client_id=existing['client_id'] if existing else 'dynamic_agent_client'
    query=dict(client_id=client_id,ext_agent_host_id=host_id,response_type='code',
               redirect_uri=redirect,scope=SCOPES,resource=RESOURCE,state=state,nonce=nonce,
               code_challenge_method='S256',code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))
    if existing:
        query['id_token_hint']=existing['id_token']
    else: query['agent_name_hint']='Ziko AI'
    return PendingLogin(state,nonce,verifier,redirect,client_id,host_id,
                        ISSUER+'/api/accounts/authorize?'+urlencode(query),time.monotonic(),
                        existing.get('subject') if existing else None)

async def verify_identity(client: httpx.AsyncClient, token: str, audience: str, nonce: str | None = None) -> dict:
    try:
        header=jwt.get_unverified_header(token)
        if header.get('alg')!='RS256' or not isinstance(header.get('kid'),str): raise ValueError()
        response=await client.get(JWKS_URL)
        response.raise_for_status()
        keys=response.json()['keys']
        matched=[k for k in keys if k.get('kid')==header['kid'] and k.get('kty')=='RSA' and k.get('use','sig')=='sig']
        if len(matched)!=1: raise ValueError()
        key=jwt.PyJWK.from_dict(matched[0]).key
        claims=jwt.decode(token,key,algorithms=['RS256'],issuer=ISSUER,audience=audience,
                          options={'require':['iss','sub','aud','iat','exp']},leeway=5)
        if not isinstance(claims['sub'],str) or not claims['sub']: raise ValueError()
        if nonce is not None and (not isinstance(claims.get('nonce'),str) or not hmac.compare_digest(claims['nonce'],nonce)): raise ValueError()
        return claims
    except (jwt.PyJWTError,ValueError,KeyError,TypeError,httpx.HTTPError) as exc:
        raise ValueError('A fiókazonosság ellenőrzése sikertelen') from None

def token_record(tokens: dict, client_id: str, claims: dict, host_id: str) -> dict:
    if tokens.get('token_type','Bearer').lower()!='bearer': raise ValueError('Hibás hitelesítési típus')
    expiry=tokens.get('expires_in')
    if isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not 0 < expiry <= 86400*30:
        raise ValueError('Hibás lejárati idő')
    scope=tokens.get('scope')
    if not isinstance(scope,str): raise ValueError('A jogosultság nem ellenőrizhető')
    r=dict(issuer=ISSUER,subject=claims['sub'],email=claims.get('email',''),client_id=client_id,
           ext_agent_host_id=host_id,access_token=tokens.get('access_token'),refresh_token=tokens.get('refresh_token'),
           id_token=tokens.get('id_token'),scopes=scope.split(),expires_at=time.time()+expiry)
    validate_record(r)
    return r

async def complete_login(pending: PendingLogin, callback: dict, client: httpx.AsyncClient) -> dict:
    if pending.consumed: raise ValueError('A belépési kísérlet már lezárult')
    pending.consumed=True
    state=callback.get('state')
    if time.monotonic()-pending.created>600 or not isinstance(state,str) or not hmac.compare_digest(state,pending.state):
        raise ValueError('Hibás vagy lejárt belépési kísérlet')
    if callback.get('error'): raise ValueError('A bejelentkezés nem lett engedélyezve')
    client_id=callback.get('client_id',pending.client_id)
    if not isinstance(client_id,str) or not client_id.startswith('oaiapp_'): raise ValueError('Hiányzik a kiadott kliensazonosító')
    if pending.client_id!='dynamic_agent_client' and client_id!=pending.client_id:
        raise ValueError('Eltérő kliensazonosító')
    code=callback.get('code')
    if not isinstance(code,str) or not code: raise ValueError('Hiányzik a bejelentkezési kód')
    response=await client.post(TOKEN_URL,data=dict(grant_type='authorization_code',client_id=client_id,code=code,
                               code_verifier=pending.verifier,redirect_uri=pending.redirect,resource=RESOURCE))
    if response.status_code!=200: raise ValueError('A bejelentkezés sikertelen; indíts új kísérletet')
    tokens=response.json()
    claims=await verify_identity(client,tokens.get('id_token',''),client_id,pending.nonce)
    if pending.subject and claims['sub']!=pending.subject: raise ValueError('Eltérő fiókazonosság')
    return token_record(tokens,client_id,claims,pending.host_id)

async def validate_import(record: dict, client: httpx.AsyncClient) -> dict:
    validate_record(record)
    claims=await verify_identity(client,record['id_token'],record['client_id'])
    if claims['sub']!=record['subject']: raise ValueError('Eltérő fiókazonosság')
    if record['expires_at']<=time.time(): raise ValueError('Lejárt kapcsolati fájl; jelentkezz be újra')
    return dict(record,email=claims.get('email',''))

async def ensure_access_token(store: CredentialStore, client: httpx.AsyncClient) -> str:
    async with store.refresh_lock:
        if (store.directory/'migration-frozen.json').exists():
            raise ValueError('Költöztetés miatt a régi alkalmazás szünetel')
        record=store.load()
        if not record: raise ValueError('Kapcsolódás szükséges')
        if record['expires_at']>time.time()+60: return record['access_token']
        response=await client.post(TOKEN_URL,data=dict(grant_type='refresh_token',client_id=record['client_id'],
                                   refresh_token=record['refresh_token'],resource=RESOURCE))
        if response.status_code in (400,401,403): raise ValueError('Újra be kell jelentkezni')
        if response.status_code!=200: raise ValueError('A kapcsolat frissítése átmenetileg sikertelen')
        tokens=response.json()
        tokens.setdefault('scope',' '.join(record['scopes']))
        tokens.setdefault('refresh_token',record['refresh_token'])
        tokens.setdefault('id_token',record['id_token'])
        claims={'sub':record['subject'],'email':record.get('email','')}
        if tokens['id_token']!=record['id_token']:
            claims=await verify_identity(client,tokens['id_token'],record['client_id'])
            if claims['sub']!=record['subject']: raise ValueError('Eltérő fiókazonosság')
        updated=token_record(tokens,record['client_id'],claims,store.host_id())
        store.replace(updated)
        return updated['access_token']

async def disconnect_account(store: CredentialStore, client: httpx.AsyncClient) -> bool:
    """Always clear local tokens; return whether remote revocation was confirmed."""
    async with store.refresh_lock:
        r=store.load()
        confirmed=not bool(r)
        if r:
            try:
                discovery=await client.get(ISSUER+'/.well-known/openid-configuration')
                discovery.raise_for_status()
                endpoint=discovery.json()['revocation_endpoint']
                from urllib.parse import urlparse
                u=urlparse(endpoint)
                if u.scheme!='https' or u.netloc!='auth.openai.com': raise ValueError()
                response=await client.post(endpoint,data=dict(token=r['refresh_token'],token_type_hint='refresh_token',client_id=r['client_id']))
                confirmed=response.status_code==200
            except (httpx.HTTPError,KeyError,ValueError): confirmed=False
        store.disconnect()
        return confirmed
