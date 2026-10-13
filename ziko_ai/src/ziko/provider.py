import asyncio
import json
import httpx

API='https://api.openai.com/v1'
ERRORS={'limit':'Keret elfogyott','auth':'Újra be kell jelentkezni',
        'interrupted':'Válasz félbeszakadt','network':'Az AI átmenetileg nem elérhető',
        'too_long':'A válasz elérte a helyi méretkorlátot'}

def failure(code): return dict(type='failed',code=code,message=ERRORS.get(code,ERRORS['network']))

async def list_models(http_client: httpx.AsyncClient, access_token: str) -> list[dict]:
    r=await http_client.get(API+'/models',headers={'Authorization':'Bearer '+access_token})
    if r.status_code in (401,403): raise ValueError(ERRORS['auth'])
    if r.status_code==429: raise ValueError(ERRORS['limit'])
    if r.status_code!=200: raise ValueError(ERRORS['network'])
    try:
        models=r.json()['models']
        return [dict(slug=m['slug'],display_name=m['display_name']) for m in models
                if m.get('visibility')=='list' and isinstance(m.get('slug'),str) and isinstance(m.get('display_name'),str)]
    except (ValueError,TypeError,KeyError,AttributeError): raise ValueError('Hibás modellkatalógus') from None

def event_result(event: dict):
    kind=event.get('type')
    if kind=='response.output_text.delta' and isinstance(event.get('delta'),str): return dict(type='delta',text=event['delta'])
    if kind=='response.completed':
        return dict(type='completed') if event.get('response',{}).get('status')=='completed' else failure('interrupted')
    if kind in ('response.failed','response.incomplete','error'):
        error=event.get('response',{}).get('error') or event.get('error') or {}
        code=error.get('code','') if isinstance(error,dict) else ''
        return failure('limit' if any(x in code for x in ('limit','quota','budget')) else 'interrupted')
    return None

async def stream_reply(http_client: httpx.AsyncClient, access_token: str, model: str,
                       messages: list[dict], instructions: str):
    body=dict(model=model,input=messages,instructions=instructions,store=False,stream=True)
    size=0
    try:
        async with asyncio.timeout(90):
            async with http_client.stream('POST',API+'/responses',headers={'Authorization':'Bearer '+access_token},json=body) as r:
                if r.status_code!=200:
                    yield failure('limit' if r.status_code==429 else 'auth' if r.status_code in (401,403) else 'network');return
                lines=[];event_size=0
                async for line in r.aiter_lines():
                    if line.startswith('data:'):
                        data=line[5:].lstrip(' ');event_size+=len(data)
                        if event_size>1024*1024: yield failure('interrupted');return
                        lines.append(data)
                    elif not line and lines:
                        raw='\n'.join(lines);lines=[];event_size=0
                        if raw=='[DONE]':continue
                        try: event=json.loads(raw)
                        except ValueError: yield failure('interrupted');return
                        if not isinstance(event,dict): yield failure('interrupted');return
                        result=event_result(event)
                        if result:
                            if result['type']=='delta':
                                size+=len(result['text'])
                                if size>32000: yield failure('too_long');return
                            yield result
                            if result['type'] in ('completed','failed'):return
                yield failure('interrupted')
    except (httpx.HTTPError,TimeoutError): yield failure('network')
