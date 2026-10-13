"""Live household scope checks; prompt text never grants permissions."""
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from collections.abc import Mapping
import re


class Scope:
    def __init__(self, hass, config):
        self.hass = hass
        self._config = config
        self.active = True

    @property
    def config(self):
        if hasattr(self._config, 'options'):
            return {**self._config.data, **self._config.options}
        return self._config

    def area_id(self, entity_id):
        entry = er.async_get(self.hass).async_get(entity_id)
        if not entry:
            return None
        if entry.area_id:
            return entry.area_id
        if entry.device_id:
            device = dr.async_get(self.hass).async_get(entry.device_id)
            if device:
                return dr.async_get_effective_area_id(dr.async_get(self.hass), device)
        return None

    def allows(self, entity_id):
        if not self.active or not isinstance(entity_id, str):
            return False
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry and entry.disabled_by:
            return False
        if not entry and not self.hass.states.get(entity_id):
            return False
        config = self.config
        if entity_id not in config.get('entities', []) and self.area_id(entity_id) not in config.get('areas', []):
            return False
        return bool(config.get('read_unexposed', False) or
                    exposed_entities.async_should_expose(self.hass, 'conversation', entity_id))

    def require_entities(self, entity_ids):
        if not entity_ids or len(entity_ids) > 5 or len(set(entity_ids)) != len(entity_ids):
            raise HomeAssistantError('Select between 1 and 5 distinct household entities')
        if any(not self.allows(entity_id) for entity_id in entity_ids):
            raise HomeAssistantError('One or more requested entities are outside the permitted household scope')

    def allows_automation(self, entity_id):
        if not self.active or entity_id not in self.config.get('automations', []):
            return False
        state = self.hass.states.get(entity_id)
        entry = er.async_get(self.hass).async_get(entity_id)
        return bool(state and entity_id.startswith('automation.') and not (entry and entry.disabled_by))

    async def require_owner(self, context):
        config = self.config
        owner = config.get('owner_user_id')
        if not self.active or not config.get('diagnostics') or not owner or not context or context.user_id != owner:
            raise HomeAssistantError('Diagnostic access requires the configured owner in an authenticated HA request')
        user = await self.hass.auth.async_get_user(owner)
        if (not self.active or not self.config.get('diagnostics') or
                self.config.get('owner_user_id') != owner or
                not user or not user.is_active or not user.is_admin):
            raise HomeAssistantError('Owner administrator permission is no longer valid')

    def trace_key(self, entity_id):
        if not self.allows_automation(entity_id):
            raise HomeAssistantError('Automation is not approved for trace reading')
        item_id = self.hass.states.get(entity_id).attributes.get('id')
        if not isinstance(item_id, str) or not item_id:
            raise HomeAssistantError('Automation has no retained trace identifier')
        return f'automation.{item_id}'

    def require_trace_scope(self, raw):
        """Fail closed for mixed/dynamic targets, before emitting any trace metadata."""
        if not isinstance(raw.get('config'), Mapping) or not raw['config']:
            raise HomeAssistantError('Trace configuration is missing; household scope cannot be verified')
        registry = er.async_get(self.hass)
        known_entities = set(registry.entities) | set(self.hass.states.async_entity_ids())
        def walk(value, key=''):
            if isinstance(value, Mapping):
                for child_key, child in value.items():
                    walk(child, str(child_key))
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child, key)
            elif isinstance(value, str):
                if '{{' in value or '{%' in value:
                    raise HomeAssistantError('Dynamic/template trace targets cannot be verified within household scope')
                if key in ('label_id', 'floor_id'):
                    raise HomeAssistantError('Label/floor trace targets are not supported for verified household scope')
                if key == 'entity_id':
                    if not self.allows(value):
                        raise HomeAssistantError('Trace references an entity outside household scope')
                elif key == 'area_id':
                    if value not in self.config.get('areas', []):
                        raise HomeAssistantError('Trace references an area outside household scope')
                elif key == 'device_id':
                    entities = [e for e in registry.entities.values() if e.device_id == value and not e.disabled_by]
                    if not entities or not all(self.allows(e.entity_id) for e in entities):
                        raise HomeAssistantError('Trace references a device outside household scope')
                for reference in re.findall(r'\b[a-z_][a-z0-9_]*\.[a-z0-9_]+\b', value):
                    if reference in known_entities and not self.allows(reference) and not self.allows_automation(reference):
                        raise HomeAssistantError('Trace contains a reference outside household scope')
        walk(raw.get('config') or {})
        # Only result/error fields may be shown; raw changed_variables are never emitted.
        for elements in (raw.get('trace') or {}).values():
            for item in elements:
                walk({k: item[k] for k in ('result', 'error', 'template_errors') if k in item})
