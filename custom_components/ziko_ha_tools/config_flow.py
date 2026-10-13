"""Bulk household selection and explicit owner-bound diagnostics."""
import probatio
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN


def settings_schema(defaults):
    return probatio.Schema({
        probatio.Required('areas', default=defaults.get('areas', [])):
            selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
        probatio.Optional('entities', default=defaults.get('entities', [])):
            selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
        probatio.Optional('automations', default=defaults.get('automations', [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain='automation', multiple=True)),
        probatio.Required('read_unexposed', default=defaults.get('read_unexposed', False)): bool,
        probatio.Required('diagnostics', default=defaults.get('diagnostics', False)): bool,
    })


async def _admin(hass, context):
    user_id = context.get('user_id')
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
