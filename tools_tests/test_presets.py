import time
import uuid

_REQUESTS={}
def request(label):
    return _REQUESTS.setdefault(label, f"r{int(time.time())}_{uuid.uuid4().hex}")

from types import SimpleNamespace
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.helpers.llm import LLMContext, ToolInput
from custom_components.ziko_ha_tools.memory import Memory
from custom_components.ziko_ha_tools.scope import Scope


async def setup(house):
    from custom_components.ziko_ha_tools.presets import Presets
    owner=await house.hass.auth.async_create_user('Owner')
    house.reg.async_get_or_create('light','test','lamp',suggested_object_id='lamp')
    house.reg.async_update_entity('light.lamp',area_id=house.area)
    house.hass.states.async_set('light.lamp','on',{'color_mode':'color_temp','supported_color_modes':['color_temp'],
         'color_temp_kelvin':3200,'brightness':153,'min_color_temp_kelvin':2000,'max_color_temp_kelvin':6500})
    exposed_entities.async_expose_entity(house.hass,'conversation','light.lamp',True)
    scope=Scope(house.hass,{'areas':[house.area],'read_unexposed':True,'owner_user_id':owner.id,
        'memory_enabled':True,'allow_writes':True,'voice_memory':False})
    scope.memory=Memory(house.hass,'preset');await scope.memory.async_load()
    ctx=LLMContext(platform='codex_assist',context=Context(user_id=owner.id),language='hu',assistant='conversation',device_id=None)
    return scope,ctx,Presets(scope)


async def test_capture_and_restore_exact_white_after_store_reopen(house):
    from custom_components.ziko_ha_tools.presets import Presets
    s,c,p=await setup(house)
    row=await p.capture('light.lamp','feher',c)
    assert row['value']['service_data']=={'brightness':153,'color_temp_kelvin':3200}
    s.memory=Memory(house.hass,'preset');await s.memory.async_load();p=Presets(s)
    seen=[]
    async def turn_on(call):
        seen.append(dict(call.data))
        house.hass.states.async_set('light.lamp','on',{'color_mode':'color_temp','supported_color_modes':['color_temp'],
            'brightness':call.data['brightness'],'color_temp_kelvin':call.data['color_temp_kelvin']})
    house.hass.services.async_register('light','turn_on',turn_on)
    house.hass.states.async_set('light.lamp','off',{'supported_color_modes':['color_temp']})
    result=await p.restore('feher',request('request-one'),c)
    assert result['status']=='verified' and seen[0]['color_temp_kelvin']==3200
    again=await p.restore('feher',request('request-one'),c)
    assert again['status']=='verified' and len(seen)==1


async def test_preset_denies_missing_color_unexposed_and_pause(house):
    s,c,p=await setup(house)
    house.hass.states.async_set('light.lamp','on',{'color_mode':'color_temp','supported_color_modes':['color_temp']})
    with pytest.raises(HomeAssistantError): await p.capture('light.lamp','bad',c)
    assert await s.memory.async_get('preset','bad') is None
    house.hass.states.async_set('light.lamp','on',{'color_mode':'brightness','supported_color_modes':['brightness'],'brightness':100})
    await p.capture('light.lamp','normal',c)
    await s.memory.async_put('settings','writes',{'paused':True})
    with pytest.raises(HomeAssistantError): await p.restore('normal',request('paused-request'),c)
    await s.memory.async_put('settings','writes',{'paused':False},1)
    exposed_entities.async_expose_entity(house.hass,'conversation','light.lamp',False)
    with pytest.raises(HomeAssistantError): await p.restore('normal',request('unexposed-request'),c)


async def test_registry_replacement_never_receives_old_preset(house):
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    house.reg.async_remove('light.lamp')
    house.hass.states.async_remove('light.lamp')
    house.reg.async_get_or_create('light','test','replacement',suggested_object_id='lamp')
    house.reg.async_update_entity('light.lamp',area_id=house.area)
    with pytest.raises(HomeAssistantError,match='identity'): await p.restore('normal',request('replaced'),c)


async def test_accepted_service_without_matching_state_is_unverified(house):
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    house.hass.states.async_set('light.lamp','off',{'supported_color_modes':['color_temp']})
    async def does_not_change(call): pass
    house.hass.services.async_register('light','turn_on',does_not_change)
    result=await p.restore('normal',request('not-matched'),c)
    assert result['status']=='unverified'


async def test_service_failure_is_not_success_and_not_retried(house):
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    calls=[]
    async def fail(call): calls.append(1);raise HomeAssistantError('offline')
    house.hass.services.async_register('light','turn_on',fail)
    result=await p.restore('normal',request('failed-call'),c)
    again=await p.restore('normal',request('failed-call'),c)
    assert result['status'] in ('failed','uncertain') and again['status']==result['status'] and calls==[1]


async def test_unknown_voice_cannot_read_or_write_memory(house):
    from custom_components.ziko_ha_tools.policy import Policy
    s,c,p=await setup(house)
    anonymous=LLMContext(platform='codex_assist',context=Context(),language='hu',assistant='conversation',device_id=None)
    with pytest.raises(HomeAssistantError):await Policy(s).require_access(anonymous)
    other=await house.hass.auth.async_create_user('Other')
    c.context=Context(user_id=other.id)
    with pytest.raises(HomeAssistantError):await Policy(s).require_access(c)


async def test_assistant_tools_registered_only_after_memory_opt_in(house):
    from custom_components.ziko_ha_tools.tools import build_tools
    s,c,p=await setup(house)
    names={t.name for t in build_tools(s,c)}
    assert {'ziko_ha_tools__get_state','ziko_ha_tools__remember','ziko_ha_tools__recall','ziko_ha_tools__save_light_preset','ziko_ha_tools__restore_light_preset'}<=names
    t=next(t for t in build_tools(s,c) if t.name.endswith('__remember'))
    result=await t.async_call(house.hass,ToolInput(t.name,{'key':'comfort','text':'Este halvány fényt szeretek.'}),c)
    assert not result.error and (await s.memory.async_get('fact','comfort'))['value']['text'].startswith('Este')
    s._config['memory_enabled']=False
    denied=await t.async_call(house.hass,ToolInput(t.name,{'key':'comfort','text':'new'}),c)
    assert denied.error


async def test_all_enabled_tool_schemas_convert_for_native_codex(house):
    from custom_components.ziko_ha_tools.tools import build_tools
    from homeassistant.helpers.llm import selector_serializer
    from probatio import to_openapi
    s,c,p=await setup(house);s._config['automation_drafts']=True
    tools=build_tools(s,c)
    assert any(t.name.endswith('__propose_automation') for t in tools)
    for tool in tools:
        schema=to_openapi(tool.parameters,custom_serializer=selector_serializer)
        assert schema['type']=='object'


async def test_replacement_during_operation_commit_is_never_actuated(house, monkeypatch):
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    original=s.memory.async_put
    async def replace(kind,key,value,expected_version=None):
        row=await original(kind,key,value,expected_version)
        if kind=='operation' and value['status']=='pending':
            house.reg.async_remove('light.lamp');house.hass.states.async_remove('light.lamp')
            house.reg.async_get_or_create('light','test','replacement',suggested_object_id='lamp')
            house.reg.async_update_entity('light.lamp',area_id=house.area)
            house.hass.states.async_set('light.lamp','on',{'supported_color_modes':['color_temp']})
        return row
    monkeypatch.setattr(s.memory,'async_put',replace)
    calls=[]
    async def turn_on(call):calls.append(dict(call.data))
    house.hass.services.async_register('light','turn_on',turn_on)
    await p.restore('normal',request('race'),c)
    assert calls==[]


@pytest.mark.parametrize('actual_mode,actual_xy',[('xy',[0.7,0.2]),('hs',[0.1,0.1])])
async def test_xy_and_color_mode_mismatch_are_not_verified(house,actual_mode,actual_xy):
    s,c,p=await setup(house)
    house.hass.states.async_set('light.lamp','on',{'color_mode':'xy','supported_color_modes':['xy'],'brightness':153,'xy_color':[0.1,0.1]})
    await p.capture('light.lamp','normal',c)
    async def turn_on(call):
        house.hass.states.async_set('light.lamp','on',{'color_mode':actual_mode,'supported_color_modes':['xy','hs'],'brightness':153,'xy_color':actual_xy})
    house.hass.services.async_register('light','turn_on',turn_on)
    result=await p.restore('normal',request('xy-mismatch'),c)
    assert result['status']=='unverified'


async def test_model_memory_never_returns_prior_preset_history(house):
    from custom_components.ziko_ha_tools.assistant_tools import Recall,SavePreset
    s,c,p=await setup(house)
    old=await p.capture('light.lamp','normal',c)
    await s.memory.async_put('preset','normal',{**old['value'],'service_data':{'brightness':30,'color_temp_kelvin':3200}},old['version'])
    result=await Recall(s).run({'kind':'preset','search':'','limit':20},c)
    assert 'previous' not in result['records'][0]
    result=await SavePreset(s).run({'entity_id':'light.lamp','name':'normal','expected_version':2},c)
    assert 'previous' not in result['saved']


async def test_expired_restore_ticket_cannot_replay_after_journal_collection(house,monkeypatch):
    from custom_components.ziko_ha_tools import presets as module
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    token=module.new_request_id();calls=[]
    async def turn_on(call):calls.append(1)
    house.hass.services.async_register('light','turn_on',turn_on)
    await p.restore('normal',token,c)
    original=module.time.time()
    monkeypatch.setattr(module.time,'time',lambda:original+700)
    await s.memory.async_put('fact','cleanup',{'text':'trigger collection'})
    assert await s.memory.async_get('operation',token) is None
    with pytest.raises(HomeAssistantError,match='expired'):
        await p.restore('normal',token,c)
    assert calls==[1]


async def test_scope_revocation_during_final_auth_never_returns_preset(house,monkeypatch):
    from custom_components.ziko_ha_tools.assistant_tools import Recall
    from custom_components.ziko_ha_tools.policy import Policy
    s,c,p=await setup(house);await p.capture('light.lamp','normal',c)
    original=Policy.require_access;count=0
    async def revoke(self,ctx,write=False):
        nonlocal count
        await original(self,ctx,write)
        count+=1
        if count==2:s._config['areas']=[]
    monkeypatch.setattr(Policy,'require_access',revoke)
    t=Recall(s)
    result=await t.async_call(house.hass,ToolInput(t.name,{'kind':'preset'}),c)
    assert result.error and 'registry_id' not in str(result.data)
