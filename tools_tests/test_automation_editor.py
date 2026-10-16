from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from aiohttp import web
from homeassistant import loader
from homeassistant.components.config.automation import EditAutomationConfigView
from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import HomeAssistantError
from test_presets import setup


def spec():
    return {'name':'Esti fény','trigger':{'type':'state','entity_id':'sensor.inside','to':'on'},
            'conditions':[], 'actions':[{'type':'light_on','entity_id':'light.lamp','brightness_pct':20}]}


async def editor(house):
    from custom_components.ziko_ha_tools.automation_editor import AutomationEditor
    s,c,p=await setup(house)
    s._config['automation_drafts']=True
    loader.async_setup(house.hass)
    from homeassistant.helpers import trigger
    await trigger.async_setup(house.hass)
    app=web.Application()
    view=EditAutomationConfigView('automation','config','automations.yaml',cv.string,data_validator=async_validate_config_item)
    view.register(house.hass,app,app.router)
    house.hass.http=SimpleNamespace(app=app)
    config_file=house.hass.config.path('configuration.yaml')
    from pathlib import Path
    Path(config_file).write_text('automation: !include automations.yaml\n')
    Path(house.hass.config.path('automations.yaml')).write_text('[]\n')
    async def reload(call): pass
    house.hass.services.async_register('automation','reload',reload)
    user=await house.hass.auth.async_get_user(c.context.user_id)
    return s,c,AutomationEditor(s),user,view


async def test_structured_spec_is_validated_by_actual_ha(house):
    from custom_components.ziko_ha_tools.automation_editor import validate_spec
    s,c,e,u,v=await editor(house)
    config=validate_spec(s,spec())
    assert config['actions'][0]['action']=='light.turn_on'
    result=await async_validate_config_item(house.hass,'ziko_test',config)
    assert result is not None


async def test_templates_unknown_services_and_cross_house_are_denied(house):
    from custom_components.ziko_ha_tools.automation_editor import validate_spec
    s,c,e,u,v=await editor(house)
    for change in [lambda x:x.update({'extra':'no'}),lambda x:x['actions'][0].update({'type':'shell_command'}),
                   lambda x:x['trigger'].update({'entity_id':'sensor.outside'}),
                   lambda x:x.update({'name':'{{ states.sensor.outside }}'}),
                   lambda x:x['actions'][0].update({'entity_id':'switch.outside'})]:
        data=spec();change(data)
        with pytest.raises((HomeAssistantError,ValueError)):validate_spec(s,data)


async def test_model_only_proposes_owner_applies_with_native_backup_and_rollback(house):
    from pathlib import Path
    s,c,e,u,v=await editor(house)
    draft=await e.propose(spec(),c)
    assert draft['value']['status']=='pending'
    assert Path(house.hass.config.path('automations.yaml')).read_text()=='[]\n'
    result=await e.apply(draft['key'],u)
    assert result['status']=='applied_disabled'
    config=await v.read_config(house.hass)
    assert len(config)==1 and config[0]['initial_state'] is False
    rolled=await e.rollback(result['revision_id'],u)
    assert rolled['status']=='rolled_back' and await v.read_config(house.hass)==[]


async def test_external_change_conflict_preserves_unrelated_configuration(house):
    from homeassistant.components.config.view import _write
    s,c,e,u,v=await editor(house)
    draft=await e.propose(spec(),c)
    unrelated={'id':'external','alias':'User rule','triggers':[],'actions':[]}
    await house.hass.async_add_executor_job(_write,house.hass.config.path('automations.yaml'),[unrelated])
    result=await e.apply(draft['key'],u)
    assert result['status']=='applied_disabled'
    config=await v.read_config(house.hass)
    assert config[0]==unrelated and len(config)==2
    update=spec();update['actions'][0]['brightness_pct']=30
    managed=await e.propose(update,c,automation_id=result['automation_id'])
    changed=deepcopy(config);changed[1]['alias']='Edited in HA'
    await house.hass.async_add_executor_job(_write,house.hass.config.path('automations.yaml'),changed)
    with pytest.raises(HomeAssistantError,match='changed'):await e.apply(managed['key'],u)
    assert (await v.read_config(house.hass))[1]['alias']=='Edited in HA'


async def test_missing_standard_include_and_wrong_owner_cannot_write(house):
    from pathlib import Path
    s,c,e,u,v=await editor(house)
    draft=await e.propose(spec(),c)
    other=await house.hass.auth.async_create_user('Other')
    with pytest.raises(HomeAssistantError):await e.apply(draft['key'],other)
    Path(house.hass.config.path('configuration.yaml')).write_text('automation: []\n')
    with pytest.raises(HomeAssistantError):await e.apply(draft['key'],u)
    assert await v.read_config(house.hass)==[]


async def test_reload_failure_is_explicit_and_never_replays_write(house):
    s,c,e,u,v=await editor(house)
    async def fail(call):raise HomeAssistantError('reload failed')
    house.hass.services.async_register('automation','reload',fail)
    draft=await e.propose(spec(),c)
    result=await e.apply(draft['key'],u)
    assert result['status']=='written_reload_failed'
    again=await e.apply(draft['key'],u)
    assert again['status']==result['status'] and len(await v.read_config(house.hass))==1


async def test_paused_writes_and_scope_revocation_deny_apply(house):
    s,c,e,u,v=await editor(house);draft=await e.propose(spec(),c)
    await s.memory.async_put('settings','writes',{'paused':True})
    with pytest.raises(HomeAssistantError):await e.apply(draft['key'],u)
    assert await v.read_config(house.hass)==[]


async def test_enable_is_owner_only_and_persists_a_rollback_revision(house):
    s,c,e,u,v=await editor(house);draft=await e.propose(spec(),c)
    applied=await e.apply(draft['key'],u)
    enabled=await e.enable(applied['automation_id'],u,applied['revision_id'])
    assert enabled['status'] in ('enabled','written_not_verified')
    assert (await v.read_config(house.hass))[0]['initial_state'] is True
    result=await e.rollback(enabled['revision_id'],u)
    assert result['status']=='rolled_back' and (await v.read_config(house.hass))[0]['initial_state'] is False


async def test_failed_write_is_recoverable_without_repeating_it(house,monkeypatch):
    s,c,e,u,v=await editor(house);draft=await e.propose(spec(),c)
    async def fail(*args):raise OSError('disk full')
    monkeypatch.setattr(e.adapter,'write',fail)
    with pytest.raises(OSError):await e.apply(draft['key'],u)
    assert (await s.memory.async_get('plan',draft['key']))['value']['status']=='applying'
    assert (await e.apply(draft['key'],u))['status']=='applying'
    assert await v.read_config(house.hass)==[]


async def test_managed_actions_recheck_scope_on_every_automation_run(house):
    from custom_components.ziko_ha_tools.automation_editor import async_setup_guarded_actions
    s,c,e,u,v=await editor(house)
    house.hass.data['ziko_ha_tools']={'fixture':s}
    async_setup_guarded_actions(house.hass)
    calls=[]
    async def turn_on(call):calls.append(dict(call.data))
    house.hass.services.async_register('light','turn_on',turn_on)
    draft=await e.propose(spec(),c);applied=await e.apply(draft['key'],u)
    action=(await v.read_config(house.hass))[0]['actions'][0]
    assert action['action']=='ziko_ha_tools.guarded_action'
    await house.hass.services.async_call('ziko_ha_tools','guarded_action',action['data'],blocking=True)
    assert len(calls)==1
    s._config['areas']=[]
    with pytest.raises(HomeAssistantError):
        await house.hass.services.async_call('ziko_ha_tools','guarded_action',action['data'],blocking=True)
    assert len(calls)==1


async def test_managed_rule_cannot_rebind_to_replacement_actuator(house):
    from custom_components.ziko_ha_tools.automation_editor import async_setup_guarded_actions
    s,c,e,u,v=await editor(house);house.hass.data['ziko_ha_tools']={'fixture':s}
    async_setup_guarded_actions(house.hass)
    draft=await e.propose(spec(),c);await e.apply(draft['key'],u)
    action=(await v.read_config(house.hass))[0]['actions'][0]
    house.reg.async_remove('light.lamp');house.hass.states.async_remove('light.lamp')
    house.reg.async_get_or_create('light','test','new_lamp',suggested_object_id='lamp')
    house.reg.async_update_entity('light.lamp',area_id=house.area)
    house.hass.states.async_set('light.lamp','off')
    async def turn_on(call):pass
    house.hass.services.async_register('light','turn_on',turn_on)
    with pytest.raises(HomeAssistantError,match='identity'):
        await house.hass.services.async_call('ziko_ha_tools','guarded_action',action['data'],blocking=True)


async def test_numeric_trigger_can_use_measured_climate_attribute(house):
    from custom_components.ziko_ha_tools.automation_editor import validate_spec
    s,c,e,u,v=await editor(house)
    data=spec();data['trigger']={'type':'numeric','entity_id':'climate.radiator','attribute':'current_temperature','above':27,'for_seconds':60}
    config=validate_spec(s,data)
    assert config['triggers'][0]['attribute']=='current_temperature'
    assert await async_validate_config_item(house.hass,'ziko_test',config)


async def test_enable_is_bound_to_exact_reviewed_revision(house):
    s,c,e,u,v=await editor(house)
    a=await e.apply((await e.propose(spec(),c))['key'],u)
    change=spec();change['actions'][0]['brightness_pct']=80
    b=await e.apply((await e.propose(change,c,a['automation_id']))['key'],u)
    with pytest.raises(HomeAssistantError,match='revision'):
        await e.enable(a['automation_id'],u,a['revision_id'])
    assert (await v.read_config(house.hass))[0]['initial_state'] is False
    enabled=await e.enable(b['automation_id'],u,b['revision_id'])
    row=await s.memory.async_get('revision',enabled['revision_id'])
    assert row['value']['status']==enabled['status']
    assert row['value']['after_spec']['actions'][0]['brightness_pct']==80
    prior=await s.memory.async_get('revision',b['revision_id'])
    assert prior['value']['before_spec']['actions'][0]['brightness_pct']==20
    assert prior['value']['after_spec']['actions'][0]['brightness_pct']==80
