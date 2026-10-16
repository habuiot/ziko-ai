"""Finite automation drafts; only the authenticated operator can apply them."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import uuid

import probatio as p
import yaml
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from .policy import Policy

NAME=p.All(str,p.Length(min=1,max=80))
ATTRIBUTE=p.In(['current_temperature','temperature','current_humidity','humidity','brightness','battery_level','current_position'])
SECONDS=p.All(p.Coerce(int),p.Range(min=0,max=3600))
TRIGGER=p.Schema({p.Required('type'):p.In(['state','numeric','time','sun']),p.Optional('entity_id'):str,
    p.Optional('to'):str,p.Optional('above'):p.Any(int,float),p.Optional('below'):p.Any(int,float),
    p.Optional('at'):str,p.Optional('event'):p.In(['sunrise','sunset']),p.Optional('for_seconds'):SECONDS,p.Optional('attribute'):ATTRIBUTE})
CONDITION=p.Schema({p.Required('type'):p.In(['state','numeric','sun']),p.Optional('entity_id'):str,
    p.Optional('state'):str,p.Optional('above'):p.Any(int,float),p.Optional('below'):p.Any(int,float),
    p.Optional('after'):p.In(['sunrise','sunset']),p.Optional('before'):p.In(['sunrise','sunset']),p.Optional('attribute'):ATTRIBUTE})
ACTION=p.Schema({p.Required('type'):p.In(['light_on','light_off','switch_on','switch_off','climate_temperature','media_volume','delay']),
    p.Optional('entity_id'):str,p.Optional('brightness_pct'):p.All(int,p.Range(min=1,max=100)),
    p.Optional('color_temp_kelvin'):p.All(int,p.Range(min=2000,max=6500)),
    p.Optional('temperature'):p.All(p.Any(int,float),p.Range(min=16,max=26)),
    p.Optional('volume'):p.All(p.Any(int,float),p.Range(min=0,max=0.7)),
    p.Optional('seconds'):p.All(int,p.Range(min=1,max=300))})
SPEC=p.Schema({p.Required('name'):NAME,p.Required('trigger'):TRIGGER,
               p.Optional('conditions',default=[]):p.All([CONDITION],p.Length(max=8)),
               p.Required('actions'):p.All([ACTION],p.Length(min=1,max=10))})


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def identities(scope,spec):
    from homeassistant.helpers import entity_registry as er
    result={}
    for step in [spec['trigger'],*spec.get('conditions',[]),*spec['actions']]:
        if eid:=step.get('entity_id'):
            scope.require_entities([eid])
            entry=er.async_get(scope.hass).async_get(eid)
            if not entry:raise HomeAssistantError('Automation targets require a stable registry identity')
            result[eid]=entry.id
    return result


def check_identities(scope,spec,expected):
    if identities(scope,spec)!=expected:raise HomeAssistantError('Automation entity identity changed; owner review is required')


def guarded_config(config,automation_id,action_revision):
    config=deepcopy(config)
    config['actions']=[a if 'delay' in a else {'action':'ziko_ha_tools.guarded_action',
        'data':{'automation_id':automation_id,'action_revision':action_revision,'action_index':i}}
        for i,a in enumerate(config['actions'])]
    return config


def async_setup_guarded_actions(hass):
    """Recheck current household/write policy on every scheduled action."""
    async def guarded(call):
        scopes=list(hass.data.get('ziko_ha_tools',{}).values())
        if len(scopes)!=1:raise HomeAssistantError('Ziko runtime is not available')
        scope=scopes[0];policy=Policy(scope)
        user=await hass.auth.async_get_user(scope.config.get('owner_user_id'))
        await policy.require_operator(user,write=True)
        if not scope.config.get('automation_drafts'):raise HomeAssistantError('Managed automation actions are disabled')
        meta=await scope.memory.async_get('settings','auto_'+call.data['automation_id'])
        if not meta or meta['value'].get('action_revision')!=call.data['action_revision']:
            raise HomeAssistantError('Automation action revision is no longer current')
        config=validate_spec(scope,meta['value']['spec'])
        check_identities(scope,meta['value']['spec'],meta['value'].get('identities'))
        i=call.data['action_index']
        if not 0<=i<len(config['actions']) or 'action' not in config['actions'][i]:
            raise HomeAssistantError('Invalid managed action index')
        action=config['actions'][i];domain,service=action['action'].split('.')
        await policy.require_operator(user,write=True)
        validate_spec(scope,meta['value']['spec'])
        check_identities(scope,meta['value']['spec'],meta['value'].get('identities'))
        await hass.services.async_call(domain,service,{**action['data'],'entity_id':action['target']['entity_id']},blocking=True,context=call.context)
    hass.services.async_register('ziko_ha_tools','guarded_action',guarded,schema=p.Schema({
        p.Required('automation_id'):p.All(str,p.Match(r'^ziko_[a-f0-9]{32}$')),
        p.Required('action_revision'):p.All(str,p.Match(r'^[a-f0-9]{32}$')),
        p.Required('action_index'):p.All(int,p.Range(min=0,max=9))}))


def validate_spec(scope, spec):
    try:
        spec=SPEC(spec)
        text=json.dumps(spec,allow_nan=False)
        if any(token in text for token in ('{{','{%','://','!include','!secret')):
            raise HomeAssistantError('Templates, URLs and includes are not allowed in Ziko drafts')
        def keys(value,allowed,required=()):
            if set(value)-set(allowed) or not set(required)<=set(value):
                raise HomeAssistantError('Fields do not match the selected automation step type')
        def reference(value):
            scope.require_entities([value])
            return value
        t=spec['trigger'];kind=t['type']
        if kind=='state':
            keys(t,('type','entity_id','to','for_seconds'),('entity_id','to'))
            if not 1<=len(t['to'])<=80:raise HomeAssistantError('Invalid state trigger')
            trigger={'trigger':'state','entity_id':reference(t['entity_id']),'to':t['to']}
        elif kind=='numeric':
            keys(t,('type','entity_id','above','below','for_seconds','attribute'),('entity_id',))
            if not {'above','below'}&set(t):raise HomeAssistantError('Numeric threshold required')
            trigger={'trigger':'numeric_state','entity_id':reference(t['entity_id']),**{k:t[k] for k in ('above','below','attribute') if k in t}}
        elif kind=='time':
            keys(t,('type','at'),('at',))
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?',t['at']):raise HomeAssistantError('Use a literal local HH:MM time')
            trigger={'trigger':'time','at':t['at']}
        else:
            keys(t,('type','event'),('event',));trigger={'trigger':'sun','event':t['event']}
        if t.get('for_seconds'):trigger['for']={'seconds':t['for_seconds']}
        conditions=[]
        for c in spec['conditions']:
            kind=c['type']
            if kind=='state':
                keys(c,('type','entity_id','state'),('entity_id','state'))
                conditions.append({'condition':'state','entity_id':reference(c['entity_id']),'state':c['state']})
            elif kind=='numeric':
                keys(c,('type','entity_id','above','below','attribute'),('entity_id',))
                if not {'above','below'}&set(c):raise HomeAssistantError('Numeric threshold required')
                conditions.append({'condition':'numeric_state','entity_id':reference(c['entity_id']),**{k:c[k] for k in ('above','below','attribute') if k in c}})
            else:
                keys(c,('type','after','before'))
                if not {'after','before'}&set(c):raise HomeAssistantError('Sun condition requires before/after')
                conditions.append({'condition':'sun',**{k:c[k] for k in ('after','before') if k in c}})
        actions=[]
        policy=Policy(scope)
        for a in spec['actions']:
            kind=a['type']
            if kind=='delay':
                keys(a,('type','seconds'),('seconds',));actions.append({'delay':{'seconds':a['seconds']}});continue
            policy.require_control(a.get('entity_id',''))
            domain=a['entity_id'].split('.')[0]
            required_domain={'light_on':'light','light_off':'light','switch_on':'switch','switch_off':'switch','climate_temperature':'climate','media_volume':'media_player'}[kind]
            if domain!=required_domain:raise HomeAssistantError('Action does not match entity domain')
            if kind=='light_on':
                keys(a,('type','entity_id','brightness_pct','color_temp_kelvin'))
                service='turn_on';data={k:a[k] for k in ('brightness_pct','color_temp_kelvin') if k in a}
            elif kind in ('light_off','switch_on','switch_off'):
                keys(a,('type','entity_id'));service='turn_on' if kind.endswith('_on') else 'turn_off';data={}
            elif kind=='climate_temperature':
                keys(a,('type','entity_id','temperature'),('temperature',));service='set_temperature';data={'temperature':a['temperature']}
                state=scope.hass.states.get(a['entity_id'])
                if not state or not state.attributes.get('min_temp',16)<=a['temperature']<=state.attributes.get('max_temp',26):
                    raise HomeAssistantError('Temperature exceeds current device limits')
            else:
                keys(a,('type','entity_id','volume'),('volume',));service='volume_set';data={'volume_level':a['volume']}
            actions.append({'action':f'{domain}.{service}','target':{'entity_id':a['entity_id']},'data':data})
        return {'alias':spec['name'],'description':'Managed by Ziko; approved on the owner panel.',
                'triggers':[trigger],'conditions':conditions,'actions':actions,'mode':'restart','initial_state':False}
    except p.Invalid as err:
        raise HomeAssistantError('Invalid structured automation draft') from err


class NativeAutomationAdapter:
    """Use the existing HA view's lock and atomic writer, fail closed if absent."""
    def __init__(self,hass):self.hass=hass
    def view(self):
        from homeassistant.components.config.automation import EditAutomationConfigView
        http=getattr(self.hass,'http',None)
        if http:
            for route in http.app.router.routes():
                try:view=inspect.getclosurevars(route.handler).nonlocals.get('view')
                except (TypeError,ValueError):continue
                if isinstance(view,EditAutomationConfigView) and route.method=='POST':return view
        raise HomeAssistantError('Native HA automation editor is not available; no config was written')

    async def check_include(self):
        def check():
            path=Path(self.hass.config.path('configuration.yaml'))
            root=yaml.compose(path.read_text())
            if not isinstance(root,yaml.MappingNode):return False
            matches=[value for key,value in root.value if str(key.value).startswith('automation')]
            return bool(len(matches)==1 and isinstance(matches[0],yaml.ScalarNode)
                and matches[0].tag=='!include' and matches[0].value=='automations.yaml'
                and not Path(self.hass.config.path('automations.yaml')).is_symlink())
        if not await self.hass.async_add_executor_job(check):
            raise HomeAssistantError('A single standard automation: !include automations.yaml is required; no file changed')

    async def read(self,view):
        value=await view.read_config(self.hass)
        if not isinstance(value,list) or any(not isinstance(v,dict) for v in value):
            raise HomeAssistantError('Unsupported automations.yaml structure')
        ids=[v.get('id') for v in value if 'id' in v]
        if len(ids)!=len(set(ids)):raise HomeAssistantError('Duplicate automation IDs must be resolved before editing')
        return value

    async def write(self,view,data):
        from homeassistant.components.config.view import _write
        await self.hass.async_add_executor_job(_write,self.hass.config.path(view.path),data)


class AutomationEditor:
    def __init__(self,scope):
        self.scope=scope;self.policy=Policy(scope);self.adapter=NativeAutomationAdapter(scope.hass)

    def require_drafts(self):
        if not self.scope.active or not self.scope.config.get('automation_drafts'):
            raise HomeAssistantError('Automation drafting is disabled')

    async def propose(self,spec,ctx,automation_id=None):
        self.require_drafts();await self.policy.require_access(ctx,write=True)
        config=validate_spec(self.scope,spec)
        from homeassistant.components.automation.config import async_validate_config_item
        await async_validate_config_item(self.scope.hass,'ziko_draft',config)
        aid=automation_id or f'ziko_{uuid.uuid4().hex}'
        if not re.fullmatch(r'ziko_[a-f0-9]{32}',aid):raise HomeAssistantError('Only Ziko-managed automation IDs may be edited')
        meta=await self.scope.memory.async_get('settings','auto_'+aid)
        if automation_id and not meta:raise HomeAssistantError('Automation is not managed by Ziko')
        view=self.adapter.view()
        async with view.mutation_lock:
            rows=await self.adapter.read(view)
        old=next((r for r in rows if r.get('id')==aid),None)
        if bool(meta)!=bool(old) or (meta and meta['value']['hash']!=digest(old)):
            raise HomeAssistantError('Managed automation changed outside Ziko; owner review is required')
        await self.policy.require_access(ctx,write=True);self.require_drafts();validate_spec(self.scope,spec)
        plan_id=uuid.uuid4().hex
        config=guarded_config(config,aid,plan_id)
        return await self.scope.memory.async_put('plan',plan_id,{'automation_id':aid,'spec':spec,
            'config':config,'identities':identities(self.scope,spec),'action_revision':plan_id,'expected_hash':digest(old),'status':'pending','expires_at':datetime.now(timezone.utc).timestamp()+86400})

    async def apply(self,plan_id,user):
        await self.policy.require_operator(user,write=True);self.require_drafts()
        async with self.scope.operation_lock:
            plan=await self.scope.memory.async_get('plan',plan_id)
            if not plan:raise HomeAssistantError('Draft not found')
            value=plan['value']
            if value['status']!='pending':return value.get('result',{'status':value['status'],'note':'Do not retry automatically; inspect configuration'})
            if value['expires_at']<datetime.now(timezone.utc).timestamp():raise HomeAssistantError('Draft expired; request a fresh draft')
            config=validate_spec(self.scope,value['spec'])
            check_identities(self.scope,value['spec'],value['identities'])
            config=guarded_config(config,value['automation_id'],value['action_revision'])
            await self.adapter.check_include();view=self.adapter.view();aid=value['automation_id']
            from homeassistant.components.automation.config import async_validate_config_item
            await async_validate_config_item(self.scope.hass,aid,config)
            async with view.mutation_lock:
                current=await self.adapter.read(view)
                old=next((r for r in current if r.get('id')==aid),None)
                if digest(old)!=value['expected_hash']:raise HomeAssistantError('Automation changed after this draft; create a fresh draft')
                after={'id':aid,**config}
                old_meta=await self.scope.memory.async_get('settings','auto_'+aid)
                revision_id=uuid.uuid4().hex
                revision=await self.scope.memory.async_put('revision',revision_id,{'automation_id':aid,'before':old,'before_meta':old_meta['value'] if old_meta else None,'before_spec':old_meta['value']['spec'] if old_meta else None,'after_spec':value['spec'],'after':after,'status':'prepared'})
                value['status']='applying'
                plan=await self.scope.memory.async_put('plan',plan_id,value,plan['version'])
                await self.policy.require_operator(user,write=True);self.require_drafts();validate_spec(self.scope,value['spec'])
                check_identities(self.scope,value['spec'],value['identities'])
                modified=[after if r.get('id')==aid else r for r in current]
                if old is None:modified.append(after)
                await self.adapter.write(view,modified)
                meta=await self.scope.memory.async_get('settings','auto_'+aid)
                await self.scope.memory.async_put('settings','auto_'+aid,{'hash':digest(after),'spec':value['spec'],'identities':value['identities'],'revision_id':revision_id,'action_revision':value['action_revision']},meta['version'] if meta else None)
                result={'status':'applied_disabled','automation_id':aid,'revision_id':revision_id,
                        'note':'Saved disabled; enable only after reviewing/testing on the owner panel.'}
                try:
                    await self.scope.hass.services.async_call('automation','reload',{},blocking=True,context=Context(user_id=user.id))
                except Exception:
                    result['status']='written_reload_failed';result['note']='Configuration saved; reload failed. Do not reapply; inspect HA and use rollback if needed.'
                value.update(status='complete',result=result)
                await self.scope.memory.async_put('plan',plan_id,value,plan['version'])
                await self.scope.memory.async_put('revision',revision_id,{**revision['value'],'status':result['status']},revision['version'])
                return result

    async def rollback(self,revision_id,user):
        await self.policy.require_operator(user,write=True);self.require_drafts()
        async with self.scope.operation_lock:
            row=await self.scope.memory.async_get('revision',revision_id)
            if not row:raise HomeAssistantError('Revision not found')
            revision=row['value'];aid=revision['automation_id']
            await self.adapter.check_include();view=self.adapter.view()
            async with view.mutation_lock:
                current=await self.adapter.read(view);old=next((r for r in current if r.get('id')==aid),None)
                if digest(old)!=digest(revision['after']):raise HomeAssistantError('Automation changed; refusing to overwrite it during rollback')
                await self.policy.require_operator(user,write=True);self.require_drafts()
                previous=revision['before']
                if previous:
                    validate_spec(self.scope,revision['before_meta']['spec'])
                    check_identities(self.scope,revision['before_meta']['spec'],revision['before_meta']['identities'])
                    self.scope.require_trace_scope({'config':previous})
                modified=[r for r in current if r.get('id')!=aid]
                if previous:modified.append(previous)
                await self.adapter.write(view,modified)
                meta=await self.scope.memory.async_get('settings','auto_'+aid)
                if previous:
                    await self.scope.memory.async_put('settings','auto_'+aid,{**revision['before_meta'],'hash':digest(previous)},meta['version'])
                elif meta:await self.scope.memory.async_delete('settings','auto_'+aid,meta['version'])
                status='rolled_back'
                try:await self.scope.hass.services.async_call('automation','reload',{},blocking=True,context=Context(user_id=user.id))
                except Exception:status='rollback_written_reload_failed'
                await self.scope.memory.async_put('revision',revision_id,{**revision,'status':status},row['version'])
                return {'status':status,'automation_id':aid}

    async def enable(self,automation_id,user,reviewed_revision_id):
        await self.policy.require_operator(user,write=True);self.require_drafts()
        async with self.scope.operation_lock:
            meta=await self.scope.memory.async_get('settings','auto_'+automation_id)
            if not meta:raise HomeAssistantError('Only managed automations may be enabled')
            validate_spec(self.scope,meta['value']['spec'])
            check_identities(self.scope,meta['value']['spec'],meta['value']['identities'])
            await self.adapter.check_include();view=self.adapter.view()
            async with view.mutation_lock:
                rows=await self.adapter.read(view)
                before=next((r for r in rows if r.get('id')==automation_id),None)
                if meta['value'].get('revision_id')!=reviewed_revision_id:
                    raise HomeAssistantError('Reviewed revision is no longer current; refresh and review the new specification')
                reviewed=await self.scope.memory.async_get('revision',reviewed_revision_id)
                if not reviewed or digest(reviewed['value']['after'])!=digest(before):
                    raise HomeAssistantError('Reviewed revision does not match current configuration')
                if not before or digest(before)!=meta['value']['hash']:
                    raise HomeAssistantError('Automation changed; request owner review before enabling')
                if before.get('initial_state') is True:
                    return {'status':'already_enabled_config','automation_id':automation_id}
                after={**before,'initial_state':True};revision_id=uuid.uuid4().hex
                revision=await self.scope.memory.async_put('revision',revision_id,{'automation_id':automation_id,
                    'before':before,'before_meta':meta['value'],'before_spec':meta['value']['spec'],
                    'after_spec':meta['value']['spec'],'after':after,'status':'prepared_enable'})
                await self.policy.require_operator(user,write=True);self.require_drafts();validate_spec(self.scope,meta['value']['spec'])
                check_identities(self.scope,meta['value']['spec'],meta['value']['identities'])
                await self.adapter.write(view,[after if r.get('id')==automation_id else r for r in rows])
                await self.scope.memory.async_put('settings','auto_'+automation_id,{**meta['value'],'hash':digest(after),'revision_id':revision_id},meta['version'])
                status='written_not_verified'
                try:
                    await self.scope.hass.services.async_call('automation','reload',{},blocking=True,context=Context(user_id=user.id))
                    from homeassistant.helpers import entity_registry as er
                    eid=er.async_get(self.scope.hass).async_get_entity_id('automation','automation',automation_id)
                    state=self.scope.hass.states.get(eid) if eid else None
                    if state and state.state=='on':status='enabled'
                except Exception:status='enable_written_reload_failed'
                await self.scope.memory.async_put('revision',revision_id,{**revision['value'],'status':status},revision['version'])
                return {'status':status,'automation_id':automation_id,'revision_id':revision_id}
