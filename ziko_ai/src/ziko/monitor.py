"""Local, read-only rules and bounded persistent observation journal."""
import asyncio
from collections import deque
from datetime import datetime
import json
import logging
import math
import time
from .ha_observer import bounded

LOGGER=logging.getLogger(__name__)
OPERATIONAL={'sensor','binary_sensor','light','switch','lock','climate','fan','cover',
             'camera','media_player','alarm_control_panel','siren','vacuum'}


def epoch(value, fallback):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:return fallback
        result=result.timestamp()
        return result if result>=0 and (fallback is None or result<=fallback) else fallback
    except (ValueError,TypeError,AttributeError):return fallback


class Monitor:
    def __init__(self,storage,*,clock=time.time):
        self.storage=storage;self.db=storage.db;self.clock=clock
        self.pending=deque(maxlen=1000);self.task=None;self.verified=set();self.error=None
        self.coverage=dict(battery=0,openings=0,availability_devices=0)
        self.last_fresh=False;self.connection_state=None;self.continuity_lost=False
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS house_events(id INTEGER PRIMARY KEY, time REAL NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS house_events_time ON house_events(time);
        CREATE TABLE IF NOT EXISTS house_alerts(key TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS house_timers(key TEXT PRIMARY KEY, since REAL NOT NULL);
        ''')
        self.dropped=int(storage.setting('journal_dropped') or 0)

    def enqueue(self,event):
        if event.get('kind')=='connection' and isinstance(event.get('connected'),bool):
            self.connection_state=event['connected']
            if not event['connected']:
                self.continuity_lost=True;self.verified.clear()
        if len(self.pending)==self.pending.maxlen:self.dropped+=1
        safe={k:bounded(event.get(k)) for k in ('entity_id','device_id','name','device','area','previous','state','time')}
        safe['kind']=event.get('kind','state_change') if event.get('kind','state_change') in ('connection','state_change') else 'state_change'
        self.pending.append(safe)

    def flush(self):
        now=self.clock()
        batch=list(self.pending)
        with self.db:
            self.db.executemany('INSERT INTO house_events(time,data) VALUES(?,?)',
                [(epoch(e['time'],now),json.dumps(e,ensure_ascii=False)) for e in batch])
            self.db.execute('DELETE FROM house_events WHERE time<?',(now-14*86400,))
            self.db.execute('DELETE FROM house_events WHERE id NOT IN (SELECT id FROM house_events ORDER BY id DESC LIMIT 10000)')
            self.db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('journal_dropped',str(self.dropped)))
        self.pending.clear()

    def _rows(self):return {r['key']:json.loads(r['data']) for r in self.db.execute('SELECT * FROM house_alerts')}

    def _duration(self,key,bad,source,now):
        if bad is None:
            self.db.execute('DELETE FROM house_timers WHERE key=?',(key,));return None
        if not bad:
            self.db.execute('DELETE FROM house_timers WHERE key=?',(key,));return False
        row=self.db.execute('SELECT since FROM house_timers WHERE key=?',(key,)).fetchone()
        parsed=epoch(source,None) if source else None
        if parsed is not None and parsed>now:parsed=None
        since=parsed if parsed is not None else (row['since'] if row else now)
        self.db.execute('INSERT INTO house_timers VALUES(?,?) ON CONFLICT(key) DO UPDATE SET since=excluded.since',(key,since))
        return True if now-since>=600 else None

    def _check(self,key,kind,e,condition,message,previous,now):
        if condition is None:return
        self.verified.add(key)
        old=previous.get(key)
        if condition:
            active=bool(old and old['active'])
            record=dict(key=key,kind=kind,device_id=e['device_id'],entity_id=e['entity_id'],
                name=e['name'],device=e['device'],area=e['area'],message=message,active=True,
                acknowledged=old.get('acknowledged',False) if active else False,
                opened_at=old['opened_at'] if active else now,resolved_at=None)
        elif old and old['active']:
            record=dict(old,active=False,resolved_at=now)
        else:return
        if record!=old:
            self.db.execute('INSERT INTO house_alerts VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',
                            (key,json.dumps(record,ensure_ascii=False)))

    def evaluate(self,snapshot):
        now=self.clock();fresh=bool(snapshot.get('fresh'));self.last_fresh=fresh;self.verified=set()
        if self.continuity_lost:
            with self.db:self.db.execute('DELETE FROM house_timers')
            self.continuity_lost=False
        if fresh!=self.connection_state:
            self.enqueue(dict(kind='connection',name='Home Assistant',previous='Kapcsolat nem igazolt' if fresh else 'Friss állapotkép',
                              state='Teljes szinkron helyreállt' if fresh else 'Kapcsolati rés; kimaradt változások nem ismertek',
                              time=datetime.fromtimestamp(now).astimezone().isoformat()))
            self.connection_state=fresh
        if not fresh:
            with self.db:self.db.execute('DELETE FROM house_timers')
            return
        entities=snapshot['entities'];previous=self._rows();seen=set();groups={}
        coverage=dict(battery=0,openings=0,availability_devices=0)
        with self.db:
            for e in entities:
                eid=e['entity_id'];domain=eid.split('.')[0];attrs=e.get('attributes',{});state=e['state']
                known=e.get('has_state',True) and state not in ('unknown','unavailable','[szöveges állapot kihagyva]')
                for kind in ('battery:','open:'):
                    if kind+eid in previous:seen.add(kind+eid)
                    if not known:self.db.execute('DELETE FROM house_timers WHERE key=?',(kind+eid,))
                battery=None
                if domain=='binary_sensor' and attrs.get('device_class')=='battery':
                    battery='binary'
                elif domain=='sensor' and attrs.get('device_class')=='battery' and attrs.get('unit_of_measurement')=='%':
                    battery='percent'
                elif isinstance(attrs.get('battery_level'),(int,float)) and not isinstance(attrs.get('battery_level'),bool):
                    battery='attribute'
                if battery:
                    key='battery:'+eid;seen.add(key);coverage['battery']+=1;condition=None;level=None
                    if known and battery=='binary' and state in ('on','off'):condition=state=='on'
                    elif known:
                        try:
                            level=float(attrs['battery_level'] if battery=='attribute' else state)
                            if math.isfinite(level) and 0<=level<=100:
                                was_low=bool(previous.get(key,{}).get('active'))
                                condition=level<25 if was_low else level<20
                        except (ValueError,TypeError,KeyError):pass
                    message='Alacsony akkumulátor' + (f': {level:g}%' if level is not None else '')
                    self._check(key,'battery',e,condition,message,previous,now)
                if domain=='binary_sensor' and attrs.get('device_class') in ('door','window','opening','garage_door'):
                    key='open:'+eid;seen.add(key);coverage['openings']+=1
                    bad=state in ('on','open') if known and state in ('on','off','open','closed') else None
                    condition=self._duration(key,bad,e.get('last_changed'),now)
                    self._check(key,'open',e,condition,'Legalább 10 perce nyitva',previous,now)
                if domain in OPERATIONAL:groups.setdefault(e['device_id'],[]).append(e)
            for device,values in groups.items():
                key='unavailable:'+device;seen.add(key);coverage['availability_devices']+=1
                live=[e for e in values if e.get('has_state',True) and e['state'] not in ('unknown','unavailable')]
                unavailable=[e for e in values if e.get('has_state',True) and e['state']=='unavailable']
                bad=False if live else (True if len(unavailable)==len(values) else None)
                timestamps=[epoch(e.get('last_changed'),None) for e in unavailable]
                source=max(timestamps) if timestamps and all(t is not None and t<=now for t in timestamps) else None
                source=datetime.fromtimestamp(source).astimezone().isoformat() if source is not None else ''
                condition=self._duration(key,bad,source,now)
                self._check(key,'unavailable',values[0],condition,'Az eszköz állapotentitásai legalább 10 perce nem elérhetők',previous,now)
            for key,old in previous.items():
                if key not in seen:
                    self._check(key,old['kind'],old,False,'Kikerült a megfigyelésből',previous,now)
            self.db.execute('DELETE FROM house_timers WHERE key NOT IN (%s)' % (','.join('?' for _ in seen) or "''"),tuple(seen))
            # Resolved records are useful briefly; active findings are never age-pruned.
            for key,a in previous.items():
                if not a['active'] and a.get('resolved_at',now)<now-14*86400:
                    self.db.execute('DELETE FROM house_alerts WHERE key=?',(key,))
        self.coverage=coverage

    def acknowledge(self,key):
        rows=self._rows();alert=rows.get(key)
        if not alert or not alert['active']:raise ValueError('A jelzés már nem aktív')
        with self.db:self.db.execute('UPDATE house_alerts SET data=? WHERE key=?',
                                    (json.dumps(dict(alert,acknowledged=True),ensure_ascii=False),key))

    def snapshot(self,house):
        ids={e['entity_id'] for e in house['entities']};devices={e['device_id'] for e in house['entities']}
        alerts=[dict(a,verified=bool(house.get('fresh') and self.error is None and a['key'] in self.verified)) for a in self._rows().values()
                if a['active'] and a['device_id'] in devices and (a['kind']=='unavailable' or a['entity_id'] in ids)]
        alerts.sort(key=lambda a:(a['acknowledged'],-a['opened_at']))
        events=[]
        for row in self.db.execute('SELECT data FROM house_events ORDER BY id DESC'):
            e=json.loads(row['data'])
            if e['kind']=='connection' or (e['entity_id'] in ids and e['device_id'] in devices):events.append(e)
            if len(events)>=100:break
        return dict(fresh=bool(house.get('fresh')) and self.error is None,alerts=alerts,events=events,
                    coverage=self.coverage,dropped_events=self.dropped,error=self.error,retention_days=14,event_limit=10000)

    def start(self,house):
        if self.task is None or self.task.done():self.task=asyncio.create_task(self._run(house))

    async def _run(self,house):
        while True:
            try:
                self.evaluate(house.snapshot());self.flush();self.error=None
            except Exception as exc:
                self.error=type(exc).__name__;LOGGER.error('Local monitor failed: %s',self.error)
            await asyncio.sleep(10)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
        self.flush()
