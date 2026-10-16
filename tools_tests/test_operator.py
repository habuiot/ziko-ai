from types import SimpleNamespace
from pathlib import Path
import pytest
from homeassistant.exceptions import HomeAssistantError
from test_automation_editor import editor,spec


async def test_owner_status_and_memory_export_have_no_credentials(house):
    from custom_components.ziko_ha_tools.operator import Operator
    s,c,e,u,v=await editor(house)
    await s.memory.async_put('fact','comfort',{'text':'meleg fény'})
    o=Operator(s)
    result=await o.dispatch(u,'status',{})
    assert result['memory_enabled'] and result['version']=='0.2.0'
    export=await o.dispatch(u,'export',{})
    assert export['records']['fact:comfort']['value']['text']=='meleg fény'
    assert 'access_token' not in str(export)


async def test_operator_rejects_other_users_and_unloaded_scope(house):
    from custom_components.ziko_ha_tools.operator import Operator
    s,c,e,u,v=await editor(house);other=await house.hass.auth.async_create_user('Other')
    o=Operator(s)
    with pytest.raises(HomeAssistantError):await o.dispatch(other,'export',{})
    s.active=False
    with pytest.raises(HomeAssistantError):await o.dispatch(u,'status',{})


async def test_panel_controls_real_pause_and_revision_actions(house):
    from custom_components.ziko_ha_tools.operator import Operator
    s,c,e,u,v=await editor(house);o=Operator(s)
    draft=await e.propose(spec(),c)
    applied=await o.dispatch(u,'apply',{'plan_id':draft['key']})
    assert applied['status']=='applied_disabled'
    paused=await o.dispatch(u,'pause',{'paused':True})
    assert paused['paused'] is True
    with pytest.raises(HomeAssistantError):await o.dispatch(u,'enable',{'automation_id':applied['automation_id'],'revision_id':applied['revision_id']})
    await o.dispatch(u,'pause',{'paused':False})
    assert (await o.dispatch(u,'rollback',{'revision_id':applied['revision_id']}))['status']=='rolled_back'


async def test_websocket_registration_uses_native_authenticated_dispatch(house):
    from custom_components.ziko_ha_tools.operator import websocket_command
    s,c,e,u,v=await editor(house)
    house.hass.data['ziko_ha_tools']={'fixture':s}
    results=[];errors=[]
    connection=SimpleNamespace(user=u,send_result=lambda *a:results.append(a),send_error=lambda *a:errors.append(a))
    await websocket_command.__wrapped__(house.hass,connection,{'id':1,'type':'ziko_ha_tools/operator','operation':'status','args':{}})
    assert results[0][0]==1 and not errors
    connection.user=await house.hass.auth.async_create_user('Other')
    await websocket_command.__wrapped__(house.hass,connection,{'id':2,'operation':'export','args':{}})
    assert errors and len(results)==1


def test_panel_has_no_raw_html_or_token_storage_and_has_all_review_actions():
    path=Path(__file__).parents[1]/'custom_components/ziko_ha_tools/frontend/ziko-panel.js'
    assert path.exists(),'operator panel missing'
    source=path.read_text()
    assert 'innerHTML' not in source and 'localStorage' not in source and 'access_token' not in source
    for label in ['callWS','apply','rollback','enable','pause','export','textContent']:
        assert label in source


def test_review_panel_displays_concrete_specs_and_sends_reviewed_revision():
    source=(Path(__file__).parents[1]/'custom_components/ziko_ha_tools/frontend/ziko-panel.js').read_text()
    assert 'plan.value.spec' in source
    assert 'before_spec' in source and 'after_spec' in source
    assert 'revision_id: revision.key' in source
    assert 'r.can_enable' in source
