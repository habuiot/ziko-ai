import json
from ziko.storage import Storage
from ziko.monitor import Monitor


def entity(eid,state,device='d',changed='1970-01-01T00:00:00Z',**attrs):
    return dict(entity_id=eid,state=state,device_id=device,name=eid,device='Device',area='Room',
                attributes=attrs,last_changed=changed,has_state=True)


def frame(*entities,fresh=True):return dict(fresh=fresh,entities=list(entities))


def test_battery_hysteresis_binary_and_voltage(tmp_path):
    s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:1000)
    low=entity('sensor.battery','19',device_class='battery',unit_of_measurement='%')
    m.evaluate(frame(low));assert len(m.snapshot(frame(low))['alerts'])==1
    low['state']='22';m.evaluate(frame(low));assert len(m.snapshot(frame(low))['alerts'])==1
    low['state']='25';m.evaluate(frame(low));assert m.snapshot(frame(low))['alerts']==[]
    voltage=entity('sensor.voltage','3.1',device_class='battery',unit_of_measurement='V')
    m.evaluate(frame(voltage));assert m.snapshot(frame(voltage))['alerts']==[]
    binary=entity('binary_sensor.battery','on',device_class='battery')
    m.evaluate(frame(binary));assert len(m.snapshot(frame(binary))['alerts'])==1
    s.close()


def test_open_unavailable_delay_stale_and_live_entity(tmp_path):
    clock=[100];s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:clock[0])
    door=entity('binary_sensor.door','on',changed='1970-01-01T00:01:40Z',device_class='door')
    dead=entity('light.dead','unavailable',device='x',changed='1970-01-01T00:01:40Z')
    m.evaluate(frame(door,dead));assert m.snapshot(frame(door,dead))['alerts']==[]
    clock[0]=701;m.evaluate(frame(door,dead,fresh=False));assert m.snapshot(frame(door,dead,fresh=False))['alerts']==[]
    m.evaluate(frame(door,dead));assert len(m.snapshot(frame(door,dead))['alerts'])==2
    # Missing/unknown state is not recovery.
    door['state']='unknown';m.evaluate(frame(door,dead));assert len(m.snapshot(frame(door,dead))['alerts'])==2
    snap=m.snapshot(frame(door,dead,fresh=False));assert not any(a['verified'] for a in snap['alerts'])
    door['state']='off';live=entity('sensor.live','12',device='x')
    m.evaluate(frame(door,dead,live));assert m.snapshot(frame(door,dead,live))['alerts']==[]
    s.close()


def test_durable_journal_ack_scope_and_retention(tmp_path):
    path=tmp_path/'db';s=Storage(path);m=Monitor(s,clock=lambda:1000)
    event=dict(entity_id='light.one',device_id='d',name='Light',device='Device',area='Room',previous='off',state='on',time='1970-01-01T00:16:40Z')
    m.enqueue(event);m.flush()
    low=entity('sensor.battery','10',device_class='battery',unit_of_measurement='%')
    m.evaluate(frame(low));key=m.snapshot(frame(low))['alerts'][0]['key'];m.acknowledge(key)
    s.close();s=Storage(path);m=Monitor(s,clock=lambda:1001)
    snap=m.snapshot(frame(low,entity('light.one','on')))
    assert snap['alerts'][0]['acknowledged'] and len(snap['events'])==1
    assert m.snapshot(frame())['alerts']==[] and m.snapshot(frame())['events']==[]
    m.evaluate(frame());assert m.snapshot(frame())['alerts']==[]
    m=Monitor(s,clock=lambda:1000+15*86400);m.flush()
    assert m.snapshot(frame(entity('light.one','on')))['events']==[]
    s.close()


def test_journal_limit_and_overflow_are_visible(tmp_path):
    s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:1000)
    e=dict(entity_id='light.one',device_id='d',name='Light',device='Device',area='Room',previous='off',state='on',time='1970-01-01T00:16:40Z')
    for i in range(1100):m.enqueue(e)
    m.flush();assert m.snapshot(frame(entity('light.one','on')))['dropped_events']==100
    for i in range(11):
        for j in range(1000):m.enqueue(e)
        m.flush()
    assert s.db.execute('SELECT count(*) FROM house_events').fetchone()[0]<=10000
    s.close()


def test_missing_timestamps_still_accumulate(tmp_path):
    clock=[1000];s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:clock[0])
    a=entity('light.a','unavailable',changed='')
    m.evaluate(frame(a));clock[0]=1601;m.evaluate(frame(a))
    assert any(x['kind']=='unavailable' for x in m.snapshot(frame(a))['alerts'])
    s.close()


def test_journal_and_findings_survive_encrypted_migration(tmp_path):
    from ziko.migration import export_data,decode_data,restore_data
    source=tmp_path/'source';source.mkdir()
    from ziko.credentials import CredentialStore
    CredentialStore(source).host_id()
    s=Storage(source/'chat.sqlite');m=Monitor(s,clock=lambda:1000)
    low=entity('sensor.battery','10',device='a'*32,device_class='battery',unit_of_measurement='%')
    m.evaluate(frame(low));m.flush();key=m.snapshot(frame(low))['alerts'][0]['key'];m.acknowledge(key)
    record=decode_data(export_data(s,source,'owner',{'a'*32},'long password 123'),'long password 123','owner')
    target=tmp_path/'target';target.mkdir();restore_data(target,record)
    restored=Storage(target/'chat.sqlite');n=Monitor(restored,clock=lambda:1001)
    assert n.snapshot(frame(low))['alerts'][0]['acknowledged']
    assert n.snapshot(frame(low))['events'][0]['kind']=='connection'
    restored.close();s.close()


def test_missing_or_unknown_state_without_attributes_preserves_finding(tmp_path):
    s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:1000)
    low=entity('sensor.battery','10',device_class='battery',unit_of_measurement='%')
    m.evaluate(frame(low));assert m.snapshot(frame(low))['alerts']
    for state,has in [('unknown',False),('unavailable',True),('unknown',True)]:
        missing=entity('sensor.battery',state);missing['has_state']=has
        m.evaluate(frame(missing));alerts=m.snapshot(frame(missing))['alerts']
        assert any(a['kind']=='battery' and not a['verified'] for a in alerts)
    s.close()


def test_unknown_gap_resets_unproven_timer_but_never_resolves_active(tmp_path):
    clock=[1000];s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:clock[0])
    door=entity('binary_sensor.door','on',changed='',device_class='door')
    m.evaluate(frame(door));clock[0]=1500;door['state']='unknown';m.evaluate(frame(door))
    clock[0]=1601;door['state']='on';m.evaluate(frame(door));assert m.snapshot(frame(door))['alerts']==[]
    clock[0]=2202;m.evaluate(frame(door));alerts=m.snapshot(frame(door))['alerts'];assert len(alerts)==1
    key=alerts[0]['key'];m.acknowledge(key)
    door['state']='unknown';m.evaluate(frame(door))
    clock[0]=2210;door['state']='on';door['last_changed']='1970-01-01T00:36:50Z';m.evaluate(frame(door))
    alerts=m.snapshot(frame(door))['alerts'];assert len(alerts)==1 and alerts[0]['acknowledged']
    door['state']='off';m.evaluate(frame(door));assert m.snapshot(frame(door))['alerts']==[]
    s.close()


def test_known_base_state_without_battery_metadata_is_not_recovery(tmp_path):
    s=Storage(tmp_path/'db');m=Monitor(s,clock=lambda:1000)
    bulb=entity('light.bulb','on',battery_level=10)
    m.evaluate(frame(bulb));bulb['attributes']={};m.evaluate(frame(bulb))
    alerts=m.snapshot(frame(bulb))['alerts'];assert len(alerts)==1 and not alerts[0]['verified']
    s.close()
