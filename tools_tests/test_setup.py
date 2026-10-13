from pathlib import Path
import importlib.util
import pytest


def test_config_flow_uses_bulk_selectors():
    path = Path(__file__).resolve().parents[1] / 'custom_components/ziko_ha_tools/config_flow.py'
    assert path.exists(), 'config flow missing'
    from custom_components.ziko_ha_tools.config_flow import settings_schema
    schema = settings_schema({})
    from probatio import to_openapi
    from homeassistant.helpers.llm import selector_serializer
    fields = to_openapi(schema, custom_serializer=selector_serializer)['properties']
    assert 'areas' in fields and 'automations' in fields


def test_plugin_manifest_declares_native_llm_dependency():
    import json
    path = Path(__file__).resolve().parents[1] / 'custom_components/ziko_ha_tools/manifest.json'
    assert path.exists(), 'manifest missing'
    manifest = json.loads(path.read_text())
    assert 'llm' in manifest['dependencies']
    assert manifest['config_flow'] is True


async def test_unrelated_llm_api_receives_no_tools(house):
    path = Path(__file__).resolve().parents[1] / 'custom_components/ziko_ha_tools/llm.py'
    assert path.exists(), 'native LLM hook missing'
    from custom_components.ziko_ha_tools.llm import async_get_tools
    from homeassistant.helpers.llm import LLMContext
    ctx = LLMContext(platform='codex_assist', context=None, language='hu', assistant='conversation', device_id=None)
    assert async_get_tools(house.hass, ctx, 'not_assist') is None


def test_tool_names_meet_native_platform_prefix_contract(house):
    from custom_components.ziko_ha_tools.scope import Scope
    from custom_components.ziko_ha_tools.tools import build_tools
    from test_history_tools import context
    s = Scope(house.hass, {'areas': [house.area], 'read_unexposed': True})
    assert all(t.name.startswith('ziko_ha_tools__') for t in build_tools(s, context()))


async def test_configured_native_platform_is_discovered_and_unload_revokes(house, tmp_path):
    from homeassistant import loader
    from homeassistant.components import llm
    from homeassistant.config_entries import ConfigEntry
    from custom_components.ziko_ha_tools import async_setup_entry, async_unload_entry
    from homeassistant.helpers.llm import ToolInput
    from test_history_tools import context
    cc = tmp_path / 'custom_components'
    cc.mkdir()
    (cc / 'ziko_ha_tools').symlink_to(Path(__file__).resolve().parents[1] / 'custom_components/ziko_ha_tools', target_is_directory=True)
    loader.async_setup(house.hass)
    entry = ConfigEntry(version=1, minor_version=1, domain='ziko_ha_tools', title='Ziko',
                        data={'areas': [house.area], 'read_unexposed': True}, options={}, source='user',
                        unique_id='ziko', discovery_keys={}, subentries_data=())
    house.hass.config_entries._entries[entry.entry_id] = entry
    assert await async_setup_entry(house.hass, entry)
    house.hass.config.components.add('ziko_ha_tools')
    assert await llm.async_setup(house.hass, {})
    result = await llm.async_get_tools(house.hass, context(), 'assist')
    tools = [t for t in result.tools if t.integration == 'ziko_ha_tools']
    assert len(tools) == 4
    old_tool = next(t for t in tools if t.name.endswith('list_sources'))
    assert await async_unload_entry(house.hass, entry)
    denied = await old_tool.async_call(house.hass, ToolInput(old_tool.name, {}), context())
    assert denied.error
    result = await llm.async_get_tools(house.hass, context(), 'assist')
    assert not any(t.integration == 'ziko_ha_tools' for t in result.tools)


async def test_flow_requires_admin_and_nonempty_bulk_scope(house):
    from custom_components.ziko_ha_tools.config_flow import ZikoToolsFlow
    flow = ZikoToolsFlow()
    flow.handler = 'ziko_ha_tools'
    flow.hass = house.hass
    flow.context = {}
    assert (await flow.async_step_user())['reason'] == 'admin_required'
    user = await house.hass.auth.async_create_user('Fixture owner')
    flow.context = {'user_id': user.id}
    assert user.is_admin
    form = await flow.async_step_user()
    assert form['type'] == 'form'
    args = {'areas': [], 'entities': [], 'automations': [], 'read_unexposed': True, 'diagnostics': False}
    assert (await flow.async_step_user(args))['errors']['base'] == 'empty_scope'
    args['areas'] = [house.area]
    result = await flow.async_step_user(args)
    assert result['type'] == 'create_entry' and result['data']['owner_user_id'] == user.id
