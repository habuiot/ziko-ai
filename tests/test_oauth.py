import base64
import hashlib
import time
from urllib.parse import urlparse,parse_qs
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from ziko.oauth import begin_login, complete_login, verify_identity, validate_import
from test_credentials import record

@pytest.fixture
def issuer():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=__import__('json').loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='key',alg='RS256',use='sig')
    def signed(nonce='nonce',**changes):
        c=dict(iss='https://auth.openai.com',sub='user',aud='oaiapp_test',iat=int(time.time()),exp=int(time.time())+600,nonce=nonce)
        c.update(changes);return jwt.encode(c,key,algorithm='RS256',headers={'kid':'key'})
    return signed,{'keys':[jwk]}

def test_state_nonce_pkce_and_exact_redirect():
    p=begin_login('host',1455);q=parse_qs(urlparse(p.url).query)
    assert q['redirect_uri']==['http://127.0.0.1:1455/auth/callback']
    assert q['code_challenge']==[base64.urlsafe_b64encode(hashlib.sha256(p.verifier.encode()).digest()).decode().rstrip('=')]
    assert p.state != p.nonce;assert 'chatgpt.tokens.use.direct' in q['scope'][0]
    assert begin_login('host',1455).state!=p.state

async def test_dynamic_client_id_is_replaced_by_issued_id(issuer):
    signed,jwks=issuer;p=begin_login('host',1455);seen=[]
    def respond(req):
        if 'jwks' in str(req.url): return httpx.Response(200,json=jwks)
        seen.append(parse_qs(req.content.decode()))
        return httpx.Response(200,json=dict(access_token='access',refresh_token='refresh',id_token=signed(p.nonce),scope='offline_access resource.invoke chatgpt.tokens.use.direct',expires_in=3600,token_type='Bearer'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
        r=await complete_login(p,dict(state=p.state,code='code',client_id='oaiapp_test'),c)
    assert r['client_id']=='oaiapp_test';assert seen[0]['client_id']==['oaiapp_test'];assert seen[0]['redirect_uri']==[p.redirect]
    with pytest.raises(ValueError): await complete_login(p,{},c)

async def test_denied_plan_scope_blocks_inference(issuer):
    signed,jwks=issuer;p=begin_login('host',1455)
    def respond(req):
        return httpx.Response(200,json=jwks if 'jwks' in str(req.url) else dict(access_token='a',refresh_token='r',id_token=signed(p.nonce),scope='openid',expires_in=3600))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
        with pytest.raises(ValueError): await complete_login(p,dict(state=p.state,code='c',client_id='oaiapp_test'),c)

async def test_jwks_signature_audience_issuer_and_expiry(issuer):
    signed,jwks=issuer
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=jwks))) as c:
        for token in [signed(aud='wrong'),signed(iss='evil'),signed(exp=1),signed('wrong'),signed()[:-4]+'xxxx']:
            with pytest.raises(ValueError): await verify_identity(c,token,'oaiapp_test','nonce')
        assert (await verify_identity(c,signed(),'oaiapp_test','nonce'))['sub']=='user'

async def test_wrong_state_and_access_denied_never_exchange():
    p=begin_login('host',1455)
    def no_network(r): pytest.fail('Unexpected network exchange')
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as c:
        with pytest.raises(ValueError): await complete_login(p,dict(state='wrong',code='c'),c)
        p=begin_login('host',1455)
        with pytest.raises(ValueError): await complete_login(p,dict(state=p.state,error='access_denied'),c)

def test_login_requires_callback_on_browser_device():
    p=begin_login('host',54321)
    assert urlparse(p.redirect).hostname=='127.0.0.1'
    with pytest.raises(ValueError): begin_login('host',0)

async def test_import_validates_signature_and_identity(issuer):
    signed,jwks=issuer
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=jwks))) as c:
        valid=dict(record(),id_token=signed())
        assert (await validate_import(valid,c))['subject']=='user'
        for bad in [dict(valid,subject='other'),dict(valid,id_token=signed(aud='other')),dict(valid,id_token=signed(iss='evil'))]:
            with pytest.raises(ValueError):await validate_import(bad,c)

async def test_returning_login_reuses_issued_client_and_rejects_changed_client():
    existing=dict(record());p=begin_login('host',1455,existing)
    q=parse_qs(urlparse(p.url).query)
    assert q['client_id']==['oaiapp_test'];assert 'agent_name_hint' not in q
    assert q['id_token_hint']==[existing['id_token']]
    def no_network(req):pytest.fail('Changed client must not be exchanged')
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as c:
        with pytest.raises(ValueError):await complete_login(p,dict(state=p.state,code='c',client_id='oaiapp_other'),c)
