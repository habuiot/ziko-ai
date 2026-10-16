"""Bulk household selection and explicit owner-bound diagnostics."""
import probatio
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.http import current_request
from homeassistant.components.http.const import KEY_HASS_USER
from .const import DOMAIN


def settings_schema(defaults):
    from .bridge import ALLOWED_APIS
    return probatio.Schema({
        probatio.Required('areas', default=defaults.get('areas', [])):
            selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
        probatio.Optional('entities', default=defaults.get('entities', [])):
            selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
        probatio.Optional('automations', default=defaults.get('automations', [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain='automation', multiple=True)),
        probatio.Required('read_unexposed', default=defaults.get('read_unexposed', False)): bool,
        probatio.Required('diagnostics', default=defaults.get('diagnostics', False)): bool,
        probatio.Required('memory_enabled', default=defaults.get('memory_enabled', False)): bool,
        probatio.Required('voice_memory', default=defaults.get('voice_memory', False)): bool,
        probatio.Required('allow_writes', default=defaults.get('allow_writes', False)): bool,
        probatio.Optional('write_entities', default=defaults.get('write_entities', [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain=['switch', 'climate', 'media_player'], multiple=True)),
        probatio.Required('automation_drafts', default=defaults.get('automation_drafts', False)): bool,
        probatio.Optional('visual_apis', default=defaults.get('visual_apis', [])):
            selector.SelectSelector(selector.SelectSelectorConfig(multiple=True,options=[{'value':k,'label':v} for k,v in ALLOWED_APIS.items()])),
    })


async def _admin(hass, context):
    # HA's native config/options frontend does not add user_id to flow
    # context. Bind to its authenticated request, never a form field.
    request = current_request.get()
    request_user = request.get(KEY_HASS_USER) if request is not None else None
    user_id = ((request_user.id if request_user is not None else None)
               if request is not None else context.get('user_id'))
    user = await hass.auth.async_get_user(user_id) if user_id else None
    return user_id if user and user.is_admin and user.is_active else None


class ZikoToolsFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        owner = await _admin(self.hass, self.context)
        if not owner:
            return self.async_abort(reason='admin_required')
        errors = {}
        if user_input is not None:
            if not user_input.get('areas') and not user_input.get('entities'):
                errors['base'] = 'empty_scope'
            else:
                return self.async_create_entry(title='Ziko HA Tools', data={**user_input, 'owner_user_id': owner})
        return self.async_show_form(step_id='user', data_schema=settings_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZikoToolsOptions()


class ZikoToolsOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        owner = await _admin(self.hass, self.context)
        if not owner:
            return self.async_abort(reason='admin_required')
        errors = {}
        if user_input is not None:
            if not user_input.get('areas') and not user_input.get('entities'):
                errors['base'] = 'empty_scope'
            else:
                return self.async_create_entry(title='', data={**user_input, 'owner_user_id': owner})
        defaults = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        return self.async_show_form(step_id='init', data_schema=settings_schema(defaults), errors=errors)
