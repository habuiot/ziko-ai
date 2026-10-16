"""Authenticated owner control panel over HA's existing websocket connection."""
from pathlib import Path
import json
import probatio as p
from homeassistant.components import websocket_api,frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from .const import DOMAIN
from .policy import Policy
from .privacy import sanitize

OPERATIONS=['status','export','delete','pause','apply','rollback','enable']


class Operator:
    def __init__(self,scope):self.scope=scope;self.policy=Policy(scope)
    async def dispatch(self,user,operation,args):
        await self.policy.require_operator(user)
        if not isinstance(args,dict):raise HomeAssistantError('Invalid operator arguments')
        expected={'status':set(),'export':set(),'delete':{'kind','key','version'},'pause':{'paused'},
                  'apply':{'plan_id'},'rollback':{'revision_id'},'enable':{'automation_id','revision_id'}}
        if operation not in expected or set(args)!=expected[operation]:raise HomeAssistantError('Unknown operation or arguments')
        s=self.scope
        if operation=='status':
            facts=await s.memory.async_list('fact')
            presets=await s.memory.async_list('preset')
            plans=await s.memory.async_list('plan',limit=50)
            revisions=await s.memory.async_list('revision',limit=50)
            for row in revisions:
                meta=await s.memory.async_get('settings','auto_'+row['value']['automation_id'])
                row['value']['can_enable']=bool(meta and meta['value'].get('revision_id')==row['key']
                    and row['value']['status'] in ('applied_disabled','written_reload_failed','rolled_back')
                    and not row['value']['after'].get('initial_state'))
            settings=await s.memory.async_get('settings','writes')
            areas=ar.async_get(s.hass)
            return {'version':'0.2.0','memory_enabled':s.config.get('memory_enabled',False),
                'writes_enabled':s.config.get('allow_writes',False),'voice_memory':s.config.get('voice_memory',False),
                'automation_drafts':s.config.get('automation_drafts',False),'paused':bool(settings and settings['value'].get('paused')),
                'areas':[{'id':aid,'name':area.name if (area:=areas.async_get_area(aid)) else aid} for aid in s.config.get('areas',[])],
                'entity_count':sum(s.allows(eid) for eid in s.hass.states.async_entity_ids()),
                'facts':facts,'presets':presets,'plans':plans,'revisions':revisions,
                'bridge_errors':getattr(s,'bridge_errors',[]),'visual_tools':[t.name for t in getattr(s,'bridge_tools',[])],
                'components':{domain:domain in s.hass.config.components for domain in ['codex_assist','wyoming','edge_tts','voice_satellite','music_assistant','hacs']},
                'limits':['Memory is shared household data, not a private diary.','Write pause covers Ziko additions only, not native Assist or existing HA automations.',
                          'Automation editor accepts finite structured drafts only.','Frontend/satellite/media checks are installation status, not a microphone or physical playback test.']}
        if operation=='export':return await s.memory.async_export()
        if operation=='delete':
            if args['kind'] not in ('fact','preset'):raise HomeAssistantError('Only facts/presets can be deleted here')
            await s.memory.async_delete(args['kind'],args['key'],args['version']);return {'deleted':args['key']}
        if operation=='pause':
            if type(args['paused']) is not bool:raise HomeAssistantError('Paused must be true/false')
            old=await s.memory.async_get('settings','writes')
            await s.memory.async_put('settings','writes',{'paused':args['paused']},old['version'] if old else None)
            return {'paused':args['paused']}
        from .automation_editor import AutomationEditor
        editor=AutomationEditor(s)
        for value in args.values():
            if not isinstance(value,str) or not 1<=len(value)<=96:raise HomeAssistantError('Invalid identifier')
        if operation=='apply':return await editor.apply(args['plan_id'],user)
        if operation=='rollback':return await editor.rollback(args['revision_id'],user)
        return await editor.enable(args['automation_id'],user,args['revision_id'])


@websocket_api.websocket_command({'type':'ziko_ha_tools/operator',p.Required('operation'):p.In(OPERATIONS),p.Optional('args',default={}):dict})
@websocket_api.async_response
async def websocket_command(hass,connection,msg):
    try:
        scopes=list(hass.data.get(DOMAIN,{}).values())
        if len(scopes)!=1:raise HomeAssistantError('Ziko is not configured')
        result=await Operator(scopes[0]).dispatch(connection.user,msg['operation'],msg.get('args',{}))
        await Policy(scopes[0]).require_operator(connection.user)
        connection.send_result(msg['id'],result)
    except (HomeAssistantError,ValueError,TypeError,KeyError,OSError,p.Invalid) as err:
        connection.send_error(msg['id'],'ziko_operation_failed',sanitize(str(err))[:300] if isinstance(err,HomeAssistantError) else 'Ziko operation failed. Inspect the operator state before repeating.')


async def async_setup_panel(hass):
    if not getattr(hass,'http',None):return
    flag='ziko_ha_tools_panel_registered'
    if not hass.data.get(flag):
        websocket_api.async_register_command(hass,websocket_command)
        path=Path(__file__).parent/'frontend'
        await hass.http.async_register_static_paths([StaticPathConfig('/api/ziko_ha_tools/frontend',str(path),False)])
        hass.data[flag]=True
    frontend.async_register_built_in_panel(hass,'custom','Ziko központ','mdi:robot',
        frontend_url_path='ziko-tools',require_admin=True,update=True,
        config={'_panel_custom':{'name':'ziko-operator-panel','module_url':'/api/ziko_ha_tools/frontend/ziko-panel.js?v=0.2.0',
                                'embed_iframe':False,'trust_external':False}})
