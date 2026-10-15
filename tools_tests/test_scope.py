from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.helpers import entity_registry as er


def scope(house, **extra):
    from custom_components.ziko_ha_tools.scope import Scope
    return Scope(house.hass, {'areas': [house.area], 'read_unexposed': True, **extra})


def test_scoped_device_area_inheritance_and_external_house(house):
    s = scope(house)
    assert s.allows('climate.radiator')
    assert s.allows('sensor.inside')
    assert not s.allows('sensor.outside')


def test_empty_scope_does_not_allow_everything(house):
    from custom_components.ziko_ha_tools.scope import Scope
    assert not Scope(house.hass, {'read_unexposed': True}).allows('sensor.inside')


def test_exposure_filter_is_independent_of_area(house):
    s = scope(house, read_unexposed=False)
    exposed_entities.async_expose_entity(house.hass, 'conversation', 'sensor.inside', False)
    assert not s.allows('sensor.inside')
    exposed_entities.async_expose_entity(house.hass, 'conversation', 'sensor.inside', True)
    assert s.allows('sensor.inside')


def test_disabled_entries_are_excluded_even_if_explicit(house):
    s = scope(house, entities=['sensor.inside'])
    house.reg.async_update_entity('sensor.inside', disabled_by=er.RegistryEntryDisabler.USER)
    assert not s.allows('sensor.inside')


async def test_diagnostics_require_real_active_admin_owner(house, monkeypatch):
    s = scope(house, diagnostics=True, owner_user_id='owner')
    user = SimpleNamespace(id='owner', is_admin=True, is_active=True)
    monkeypatch.setattr(house.hass.auth, 'async_get_user', AsyncMock(return_value=user))
    await s.require_owner(Context(user_id='owner'))
    for context in (None, Context(), Context(user_id='someone_else')):
        with pytest.raises(HomeAssistantError):
            await s.require_owner(context)
    user.is_active = False
    with pytest.raises(HomeAssistantError):
        await s.require_owner(Context(user_id='owner'))


def test_explicit_automation_is_not_a_general_scope_bypass(house):
    s = scope(house, automations=['automation.evening'])
    house.hass.states.async_set('automation.evening', 'on', {'id': 'evening'})
    assert s.allows_automation('automation.evening')
    assert not s.allows_automation('automation.other_house')
    assert not s.allows('sensor.outside')


async def test_owner_option_revoked_during_auth_lookup(house, monkeypatch):
    from custom_components.ziko_ha_tools.scope import Scope
    config = {'areas': [house.area], 'diagnostics': True, 'owner_user_id': 'owner'}
    scope = Scope(house.hass, config)
    async def lookup(_):
        config['diagnostics'] = False
        return SimpleNamespace(is_active=True, is_admin=True)
    monkeypatch.setattr(house.hass.auth, 'async_get_user', lookup)
    with pytest.raises(HomeAssistantError):
        await scope.require_owner(Context(user_id='owner'))
