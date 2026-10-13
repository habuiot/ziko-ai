import asyncio
import json
import pytest
from datetime import datetime, timezone
from websockets.asyncio.server import serve
from ziko.ha_observer import HouseObserver, ReadOnlyConnection


async def test_failed_query_reports_safe_stage_and_code(caplog):
    async def server(ws):
        await ws.send(json.dumps({'type':'auth_required'}))
        await ws.recv()
        await ws.send(json.dumps({'type':'auth_ok'}))
        c=json.loads(await ws.recv())
        await ws.send(json.dumps({'id':c['id'],'type':'result','success':False,
            'error':{'code':'unauthorized','message':'Bearer SECRET'}}))
        await ws.wait_closed()
    async with serve(server,'127.0.0.1',0) as service:
        o=HouseObserver('SECRET',url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',retry_seconds=.1)
        o.start()
        try:
            async with asyncio.timeout(2):
                while not o.snapshot().get('failure'):await asyncio.sleep(.01)
            assert o.snapshot()['failure']=={'stage':'subscribe_events','error':'HAQueryError','code':'unauthorized'}
            assert 'subscribe_events' in caplog.text
            assert 'SECRET' not in caplog.text+json.dumps(o.snapshot())
        finally:await o.stop()


def fixture():
    devices=[{'id':'yes','name_by_user':'Ágy LED közép','area_id':'a'}, {'id':'no','name':'Másik lakás'}]
    entities=[{'entity_id':'light.new_name','device_id':'yes','platform':'tuya'},
              {'entity_id':'light.foreign','device_id':'no','platform':'tuya'},
              {'entity_id':'sensor.disabled','device_id':'yes','platform':'tuya','disabled_by':'user'},
              {'entity_id':'light.group','platform':'group'}]
    states=[{'entity_id':e['entity_id'],'state':'off','attributes':{'friendly_name':'LED','access_token':'SECRET','entity_picture':'/api?token=SECRET','brightness':100},'last_updated':'2026-10-13T08:00:00Z'} for e in entities]
    return devices,entities,[{'area_id':'a','name':'Nagyszoba'}],states


def ready():
    o=HouseObserver('secret',approved={'yes'})
    o.replace(*fixture())
    return o


def test_allowlist_filters_foreign_disabled_and_unlinked():
    o=ready();s=o.snapshot()
    assert [e['entity_id'] for e in s['entities']]==['light.new_name']
    assert s['entities'][0]['area']=='Nagyszoba'
    assert s['device_count']==1
    assert 'SECRET' not in json.dumps(s)
    assert 'entity_picture' not in json.dumps(o.context())


def test_all_enabled_approved_entities_are_observed_with_coverage():
    o=HouseObserver('secret',approved={'yes'})
    d,e,a,s=fixture()
    for eid,platform,category in [('sensor.battery','tuya','diagnostic'),
            ('number.setting','matter','config'),('event.remote','new_integration',None),
            ('select.mode','alexa_devices',None),('button.restart','mqtt',None)]:
        e.append(dict(entity_id=eid,device_id='yes',platform=platform,entity_category=category))
        s.append(dict(entity_id=eid,state='on',attributes={}))
    e.append(dict(entity_id='sensor.no_state',device_id='yes',platform='mqtt'))
    o.replace(d,e,a,s)
    snapshot=o.snapshot()
    assert snapshot['entity_count']==7
    assert snapshot['coverage']=={'total':8,'enabled':7,'disabled':1,'with_state':6,'without_state':1}
    assert {v['entity_id'] for v in o.context()['entities']}=={v['entity_id'] for v in e if v.get('device_id')=='yes' and not v.get('disabled_by')}
    missing=next(v for v in o.context()['entities'] if v['entity_id']=='sensor.no_state')
    assert missing['state']=='unknown' and missing['has_state'] is False


def test_changed_and_removed_entities_follow_device_not_old_name():
    o=ready();o.apply_event({'entity_id':'light.new_name','new_state':{'entity_id':'light.new_name','state':'on','attributes':{},'last_updated':'2026-10-13T09:00:00Z'}})
    assert o.snapshot()['entities'][0]['state']=='on'
    assert o.snapshot()['recent'][0]['state']=='on'
    o.apply_event({'entity_id':'light.foreign','new_state':{'entity_id':'light.foreign','state':'on'}})
    assert len(o.snapshot()['recent'])==1
    d,e,a,s=fixture();e[0]['entity_id']='light.renamed';s[0]['entity_id']='light.renamed'
    o.replace(d,e,a,s)
    assert [v['entity_id'] for v in o.snapshot()['entities']]==['light.renamed']
    assert not o.snapshot()['recent']
    o.apply_event({'entity_id':'light.renamed','new_state':None})
    assert o.snapshot()['entities'][0]['has_state'] is False
    assert o.snapshot()['coverage']['without_state']==1
    o.replace(d,[],a,[])
    assert o.snapshot()['entities']==[]


def test_stale_and_context_limit_and_bounded_history():
    o=ready();assert o.snapshot()['fresh']
    o.disconnected();assert not o.context()['fresh']
    for i in range(250):o.apply_event({'entity_id':'light.new_name','new_state':{'entity_id':'light.new_name','state':str(i)}})
    assert len(o.snapshot()['recent'])==200
    assert len(json.dumps(o.context(),ensure_ascii=False))<=48000


async def test_read_only_command_gate():
    class Socket:
        async def send(self,msg):raise AssertionError('must never send')
    r=ReadOnlyConnection(Socket(),'secret')
    with pytest.raises(ValueError):await r.send('call_service',domain='lock',service='unlock')
    with pytest.raises(ValueError):await r.send('subscribe_events',event_type='*')


async def test_real_websocket_initial_events_and_sync_race():
    observed=[]; stop=asyncio.Event()
    async def server(ws):
        await ws.send(json.dumps({'type':'auth_required'}))
        auth=json.loads(await ws.recv());assert auth=={'type':'auth','access_token':'secret'}
        await ws.send(json.dumps({'type':'auth_ok'}))
        d,e,a,s=fixture()
        for _ in range(5):
            cmd=json.loads(await ws.recv());observed.append(cmd['type'])
            value={'config/device_registry/list':d,'config/entity_registry/list':e,'config/area_registry/list':a,'get_states':s,'subscribe_events':None}[cmd['type']]
            if cmd['type']=='get_states':
                await ws.send(json.dumps({'type':'event','event':{'event_type':'state_changed','data':{'entity_id':'light.new_name','new_state':{'entity_id':'light.new_name','state':'on','last_updated':'2026-10-13T09:00:00Z'}}}}))
            await ws.send(json.dumps({'id':cmd['id'],'type':'result','success':True,'result':value}))
        await stop.wait()
    async with serve(server,'127.0.0.1',0) as service:
        port=service.sockets[0].getsockname()[1]
        o=HouseObserver('secret',approved={'yes'},url=f'ws://127.0.0.1:{port}')
        o.start()
        try:
            async with asyncio.timeout(3):
                while not o.snapshot()['fresh']:await asyncio.sleep(.01)
            assert o.snapshot()['entities'][0]['state']=='on'
            assert set(observed)=={'subscribe_events','get_states','config/device_registry/list','config/entity_registry/list','config/area_registry/list'}
        finally:stop.set();await o.stop()
    assert not o.snapshot()['fresh']


async def test_auth_failure_never_exposes_token():
    async def server(ws):
        await ws.send(json.dumps({'type':'auth_required'}));await ws.recv()
        await ws.send(json.dumps({'type':'auth_invalid','message':'secret'}))
    async with serve(server,'127.0.0.1',0) as service:
        o=HouseObserver('secret',url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',retry_seconds=.01)
        o.start();await asyncio.sleep(.1);await o.stop()
        assert not o.snapshot()['fresh']
        assert 'secret' not in json.dumps(o.snapshot())

async def test_disconnect_reconnect_rebuilds_state():
    connections=0
    async def server(ws):
        nonlocal connections
        connections+=1
        await ws.send(json.dumps({'type':'auth_required'}));await ws.recv();await ws.send(json.dumps({'type':'auth_ok'}))
        d,e,a,s=fixture();s[0]['state']='on' if connections>1 else 'off'
        for _ in range(5):
            c=json.loads(await ws.recv())
            value={'config/device_registry/list':d,'config/entity_registry/list':e,'config/area_registry/list':a,'get_states':s,'subscribe_events':None}[c['type']]
            await ws.send(json.dumps({'id':c['id'],'type':'result','success':True,'result':value}))
        if connections==1:await ws.close()
        else:await ws.wait_closed()
    async with serve(server,'127.0.0.1',0) as service:
        o=HouseObserver('secret',approved={'yes'},url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',retry_seconds=.01)
        o.start()
        try:
            async with asyncio.timeout(3):
                while not (o.snapshot()['fresh'] and o.snapshot()['entities'][0]['state']=='on'):await asyncio.sleep(.01)
            assert connections>=2
        finally:await o.stop()


def test_disabled_removal_and_new_unknown_device():
    o=ready();d,e,a,s=fixture();e[0]['disabled_by']='user'
    d.append({'id':'new','name':'Új eszköz'})
    e.append({'device_id':'new','entity_id':'light.extra','platform':'tuya'})
    o.replace(d,e,a,s)
    assert not o.snapshot()['entities']
    assert not o.catalog


def test_text_states_and_attributes_cannot_forward_urls_or_credentials():
    o=ready();d,e,a,s=fixture()
    e[0]['entity_id']='sensor.safe';s[0]['entity_id']='sensor.safe'
    s[0]['state']='rtsp://user:password@camera.local/live?token=SECRET'
    s[0]['attributes']={'preset_mode':'https://example.test?token=SECRET','unit_of_measurement':'Bearer SECRET'}
    o.replace(d,e,a,s)
    data=json.dumps(o.context())
    assert 'SECRET' not in data and 'rtsp://' not in data and 'https://' not in data


def test_buffered_removal_cannot_delete_newer_snapshot():
    o=ready()
    o.apply_event({'entity_id':'light.new_name','new_state':None,
                  'old_state':{'last_updated':'2026-10-13T07:00:00Z'},
                  '_time_fired':'2026-10-13T07:01:00Z'},after_sync=True)
    assert o.snapshot()['entities'][0]['state']=='off'


def test_large_context_keeps_all_approved_entities_for_ai_selection():
    o=HouseObserver('secret',approved={'yes'})
    d,e,a,s=fixture()
    e=[{'device_id':'yes','entity_id':f'sensor.value_{i}','platform':'mqtt','name':'Hosszú nevű érzékelő '*20} for i in range(1000)]
    s=[{'entity_id':v['entity_id'],'state':str(i),'attributes':{'unit_of_measurement':'°C'}} for i,v in enumerate(e)]
    o.replace(d,e,a,s)
    context=o.context()
    assert context['omitted_entities']==0
    assert len(context['entities'])==1000


def test_declared_select_and_enum_states_are_available_to_ai():
    o=HouseObserver('secret',approved={'yes'})
    d,e,a,s=fixture()
    e=[dict(entity_id='select.power_on',device_id='yes',platform='matter'),
       dict(entity_id='sensor.mode',device_id='yes',platform='mqtt')]
    s=[dict(entity_id='select.power_on',state='restore',attributes={'options':['on','off','restore']}),
       dict(entity_id='sensor.mode',state='Deep sleep',attributes={'device_class':'enum','options':['Deep sleep','Running']})]
    o.replace(d,e,a,s)
    entities={v['entity_id']:v for v in o.context()['entities']}
    assert entities['select.power_on']['state']=='restore'
    assert entities['select.power_on']['attributes']['options']==['on','off','restore']
    assert entities['sensor.mode']['state']=='Deep sleep'


def test_declared_modes_and_event_types_are_preserved():
    o=ready()
    o.apply_event(dict(entity_id='light.new_name',new_state=dict(entity_id='light.new_name',state='on',
        attributes={'preset_mode':'Quiet night','preset_modes':['Quiet night','Normal'],
                    'event_type':'double_press','event_types':['single_press','double_press']})))
    attrs=o.context()['entities'][0]['attributes']
    assert attrs['preset_mode']=='Quiet night' and attrs['event_type']=='double_press'


def test_option_labels_cannot_forward_secrets_urls_or_free_text():
    o=HouseObserver('secret',approved={'yes'})
    d,e,a,s=fixture();e[0]['entity_id']='select.power_on';s[0]['entity_id']='select.power_on'
    for value in ['https://user:SECRET@example.test','Bearer SECRET','password=SECRET',
                  'password SECRET','API key SECRET','sk-proj-SECRET','eyJhbGciOi.SECRET.signature',
                  '\nSECRET','UNDECLARED']:
        s[0]['state']=value
        s[0]['attributes']={'options':['restore',value] if value!='UNDECLARED' else ['restore']}
        o.replace(d,e,a,s)
        data=json.dumps(o.context())
        assert 'SECRET' not in data and 'UNDECLARED' not in data
        assert o.context()['entities'][0]['state']=='[szöveges állapot kihagyva]'
    # An arbitrary sensor declaring options is not automatically treated as an enum.
    e[0]['entity_id']=s[0]['entity_id']='sensor.free_text'
    s[0]['state']='private text';s[0]['attributes']={'options':['private text']}
    o.replace(d,e,a,s)
    assert 'private text' not in json.dumps(o.context())
