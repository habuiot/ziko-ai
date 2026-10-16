import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.ziko_ha_tools.scope import Scope


async def test_snapshot_reads_exact_light_values_without_tokens_or_urls(house):
    from custom_components.ziko_ha_tools.catalog import Catalogue
    house.reg.async_get_or_create('light','test','lamp',suggested_object_id='lamp')
    house.reg.async_update_entity('light.lamp',area_id=house.area)
    house.hass.states.async_set('light.lamp','on',{'color_mode':'color_temp','brightness':153,
        'color_temp_kelvin':3200,'supported_color_modes':['color_temp'],'access_token':'PRIVATE',
        'entity_picture':'https://private/camera?token=PRIVATE','friendly_name':'Ágy'})
    s=Scope(house.hass,{'areas':[house.area],'read_unexposed':True})
    rows=Catalogue(s).snapshot(['light.lamp'])['entities']
    assert rows[0]['attributes']['brightness']==153
    assert rows[0]['attributes']['color_temp_kelvin']==3200
    assert 'PRIVATE' not in str(rows) and 'https://' not in str(rows)
    assert rows[0]['observed_at'] and rows[0]['last_updated']


async def test_snapshot_outside_denied_and_unavailable_is_explicit(house):
    from custom_components.ziko_ha_tools.catalog import Catalogue
    s=Scope(house.hass,{'areas':[house.area],'read_unexposed':True})
    with pytest.raises(HomeAssistantError): Catalogue(s).snapshot(['sensor.outside'])
    house.hass.states.async_set('sensor.inside','unavailable')
    assert Catalogue(s).snapshot(['sensor.inside'])['entities'][0]['available'] is False
