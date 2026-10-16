from types import SimpleNamespace
import pytest
import probatio as p
from homeassistant.helpers import llm
from homeassistant.helpers.llm import Tool,ToolResult,ToolInput,APIInstance
from test_presets import setup


class Wiki(Tool):
    name='search_wikipedia';description='wiki';integration='voice_satellite_llm_tools'
    parameters=p.Schema({p.Required('query'):str})
    async def async_call(self,hass,tool_input,ctx):
        return {'source':'wikipedia','query':tool_input.tool_args['query'],'device':ctx.device_id,'original_name':tool_input.tool_name}


class WikiAPI(llm.API):
    async def async_get_api_instance(self,ctx):
        return APIInstance(api=self,api_prompt='Wiki prompt',llm_context=ctx,tools=[Wiki()])


async def test_selected_visual_api_is_bridged_with_original_context(house):
    from custom_components.ziko_ha_tools.bridge import prepare_bridge
    s,c,preset=await setup(house);s._config['visual_apis']=['voice_satellite_llm_tools_wikipedia']
    unregister=llm.async_register_api(house.hass,WikiAPI(hass=house.hass,id='voice_satellite_llm_tools_wikipedia',name='Wiki'))
    try:
        await prepare_bridge(s)
        assert len(s.bridge_tools)==1
        tool=s.bridge_tools[0]
        result=await tool.async_call(house.hass,ToolInput(tool.name,{'query':'Budapest'}),c)
        assert not result.error and result.data['original_name']=='search_wikipedia'
        assert tool.name.startswith('ziko_ha_tools__')
    finally:unregister()


async def test_arbitrary_api_or_assist_recursion_never_bridged(house):
    from custom_components.ziko_ha_tools.bridge import prepare_bridge
    s,c,preset=await setup(house);s._config['visual_apis']=['assist','dangerous_custom_api','voice_satellite_llm_tools_entity_card']
    await prepare_bridge(s)
    assert s.bridge_tools==[] and s.bridge_errors


async def test_bridge_unload_or_api_revocation_is_live(house):
    from custom_components.ziko_ha_tools.bridge import prepare_bridge
    s,c,preset=await setup(house);s._config['visual_apis']=['voice_satellite_llm_tools_wikipedia']
    unregister=llm.async_register_api(house.hass,WikiAPI(hass=house.hass,id='voice_satellite_llm_tools_wikipedia',name='Wiki'))
    await prepare_bridge(s);unregister()
    result=await s.bridge_tools[0].async_call(house.hass,ToolInput(s.bridge_tools[0].name,{'query':'x'}),c)
    assert result.error
    s.active=False
    result=await s.bridge_tools[0].async_call(house.hass,ToolInput(s.bridge_tools[0].name,{'query':'x'}),c)
    assert result.error
