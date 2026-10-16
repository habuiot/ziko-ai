"""Authorization is derived from HA identity, never model arguments."""
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.http import current_request
from homeassistant.components.http.const import KEY_HASS_USER


class Policy:
    def __init__(self, scope):
        self.scope = scope

    async def require_access(self, ctx, write=False):
        s = self.scope
        if not s.active or not s.config.get('memory_enabled') or not getattr(s, 'memory', None):
            raise HomeAssistantError('Ziko memory is disabled or unloaded')
        owner = s.config.get('owner_user_id')
        user = await s.hass.auth.async_get_user(owner) if owner else None
        if not s.active or not user or not user.is_admin or not user.is_active:
            raise HomeAssistantError('Configured owner authorization is not valid')
        actor = ctx.context.user_id if ctx and ctx.context else None
        if actor and actor != owner:
            raise HomeAssistantError('Only the configured owner may use this household memory')
        if not actor:
            device = dr.async_get(s.hass).async_get(ctx.device_id) if ctx and ctx.device_id else None
            area = dr.async_get_effective_area_id(dr.async_get(s.hass), device) if device else None
            if not s.config.get('voice_memory') or not device or area not in s.config.get('areas', []):
                raise HomeAssistantError('Anonymous memory requires an explicitly allowed household satellite')
        if write:
            self.require_writes()
            row = await s.memory.async_get('settings', 'writes')
            if row and row['value'].get('paused'):
                raise HomeAssistantError('Ziko writes are paused')
        if not s.active or not s.config.get('memory_enabled') or s.config.get('owner_user_id') != owner:
            raise HomeAssistantError('Authorization was revoked')
        return owner

    def require_writes(self):
        if not self.scope.active or not self.scope.config.get('allow_writes'):
            raise HomeAssistantError('Ziko actuator writes are disabled')

    async def require_operator(self, user, write=False):
        """Only called by authenticated websocket; never exposed as an LLM tool."""
        s = self.scope
        current = await s.hass.auth.async_get_user(user.id) if user else None
        if (not s.active or not current or not current.is_active or not current.is_admin
                or current.id != s.config.get('owner_user_id')):
            raise HomeAssistantError('Authenticated configured owner is required')
        if write:
            self.require_writes()
            paused = await s.memory.async_get('settings', 'writes')
            if paused and paused['value'].get('paused'):
                raise HomeAssistantError('Ziko writes are paused')
        if not s.active or current.id != s.config.get('owner_user_id'):
            raise HomeAssistantError('Owner access was revoked')

    def require_control(self, entity_id):
        s = self.scope
        self.require_writes()
        if not s.allows(entity_id) or not exposed_entities.async_should_expose(s.hass, 'conversation', entity_id):
            raise HomeAssistantError('Target is not an exposed permitted household actuator')
        if not entity_id.startswith('light.') and entity_id not in s.config.get('write_entities', []):
            raise HomeAssistantError('This actuator requires an explicit write allowlist entry')
        entry = er.async_get(s.hass).async_get(entity_id)
        if not entry:
            raise HomeAssistantError('Actuator must have a stable registry identity')
        return entry
