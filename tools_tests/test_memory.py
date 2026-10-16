from copy import deepcopy
import pytest
from homeassistant.exceptions import HomeAssistantError


async def test_real_store_survives_new_instance_and_unicode(house):
    from custom_components.ziko_ha_tools.memory import Memory
    memory = Memory(house.hass, 'fixture')
    await memory.async_load()
    saved = await memory.async_put('fact', 'esti-feny', {'text': 'Este meleg fényt szeretek.'})
    assert saved['version'] == 1
    other = Memory(house.hass, 'fixture')
    await other.async_load()
    assert (await other.async_get('fact', 'esti-feny'))['value']['text'] == 'Este meleg fényt szeretek.'
    saved['value']['text'] = 'mutated'
    assert (await other.async_get('fact', 'esti-feny'))['value']['text'] != 'mutated'


async def test_versions_delete_and_recreation_cannot_accept_stale_write(house):
    from custom_components.ziko_ha_tools.memory import Memory
    m = Memory(house.hass, 'versions'); await m.async_load()
    await m.async_put('fact', 'x', {'text': 'one'})
    with pytest.raises(HomeAssistantError, match='version'):
        await m.async_put('fact', 'x', {'text': 'two'})
    await m.async_put('fact', 'x', {'text': 'two'}, 1)
    with pytest.raises(HomeAssistantError):
        await m.async_delete('fact', 'x', 1)
    await m.async_delete('fact', 'x', 2)
    row = await m.async_put('fact', 'x', {'text': 'three'})
    assert row['version'] == 4
    with pytest.raises(HomeAssistantError):
        await m.async_put('fact', 'x', {'text': 'stale'}, 1)


async def test_failed_save_does_not_replace_current_memory(house, monkeypatch):
    from custom_components.ziko_ha_tools.memory import Memory
    m = Memory(house.hass, 'failed'); await m.async_load()
    await m.async_put('fact', 'x', {'text': 'old'})
    async def fail(*args): raise OSError('disk full')
    monkeypatch.setattr(m.store, 'async_save', fail)
    with pytest.raises(OSError): await m.async_put('fact', 'x', {'text': 'new'}, 1)
    assert (await m.async_get('fact', 'x'))['value']['text'] == 'old'


async def test_memory_limits_are_real_and_untrusted_kinds_denied(house):
    from custom_components.ziko_ha_tools.memory import Memory
    m = Memory(house.hass, 'limits'); await m.async_load()
    for kind,key,value in [('unknown','x',{}),('fact','../x',{}),('fact','x',{'text':'a'*9000}),('fact','x',{'n':float('nan')})]:
        with pytest.raises((ValueError, HomeAssistantError)):
            await m.async_put(kind,key,value)
    assert await m.async_list('fact') == []


async def test_memory_list_is_bounded_and_history_is_retained(house):
    from custom_components.ziko_ha_tools.memory import Memory
    m = Memory(house.hass, 'history'); await m.async_load()
    for i in range(8): await m.async_put('fact','lamp',{'text':str(i)},i or None)
    row = await m.async_get('fact','lamp')
    assert row['version']==8 and len(row['previous'])==5
    assert len(await m.async_list('fact', limit=1))==1


async def test_deleted_keys_reclaim_capacity_without_stale_versions(house,monkeypatch):
    import custom_components.ziko_ha_tools.memory as module
    m=module.Memory(house.hass,'reclaim');await m.async_load()
    monkeypatch.setattr(module,'MAX_RECORDS',4)
    for i in range(12):
        r=await m.async_put('fact',f'key-{i}',{'text':'x'})
        await m.async_delete('fact',r['key'],r['version'])
    assert len(m.data['versions'])<=4
    new=await m.async_put('fact','key-0',{'text':'new'})
    with pytest.raises(HomeAssistantError):await m.async_put('fact','key-0',{'text':'stale'},1)
    assert new['version']>1


async def test_archive_limits_leave_write_pause_available(house,monkeypatch):
    import custom_components.ziko_ha_tools.memory as module
    m=module.Memory(house.hass,'capacity');await m.async_load()
    monkeypatch.setattr(module,'MAX_RECORDS',4)
    for i in range(12):await m.async_put('plan',f'plan-{i}',{'status':'complete'})
    assert len(await m.async_list('plan'))<=4
    await m.async_put('settings','writes',{'paused':True})
    assert (await m.async_get('settings','writes'))['value']['paused']


async def test_search_does_not_match_hidden_previous_values(house):
    from custom_components.ziko_ha_tools.memory import Memory
    m=Memory(house.hass,'search');await m.async_load()
    r=await m.async_put('preset','normal',{'entity_id':'light.revoked_lamp'})
    await m.async_put('preset','normal',{'entity_id':'light.current_lamp'},r['version'])
    assert await m.async_list('preset',search='revoked_lamp')==[]
