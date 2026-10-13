import json
from pathlib import Path
import sqlite3
import time
import uuid

def stamp(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

class Storage:
    def __init__(self,path: Path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,role TEXT NOT NULL,text TEXT NOT NULL,status TEXT NOT NULL,request_id TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory(id TEXT PRIMARY KEY,text TEXT NOT NULL,source TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        self.db.execute("UPDATE messages SET status='failed' WHERE status='pending'")
        self.db.commit();path.chmod(0o600)

    def close(self): self.db.close()

    def create_conversation(self,title='Új beszélgetés'):
        if not isinstance(title,str) or not title.strip() or len(title)>100:raise ValueError('Hibás beszélgetésnév')
        cid=str(uuid.uuid4())
        with self.db:self.db.execute('INSERT INTO conversations VALUES(?,?,?)',(cid,title,stamp()))
        return cid

    def conversations(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM conversations ORDER BY created_at DESC,rowid DESC')]

    def require_conversation(self,cid):
        if not self.db.execute('SELECT id FROM conversations WHERE id=?',(cid,)).fetchone():raise KeyError('Nincs ilyen beszélgetés')

    def messages(self,cid):
        self.require_conversation(cid)
        return [dict(r) for r in self.db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,))]

    def add_message(self,cid,role,text,status,request_id=None):
        self.require_conversation(cid)
        if role not in ('user','assistant') or status not in ('pending','completed','failed','cancelled') or not isinstance(text,str) or len(text)>32000:
            raise ValueError('Hibás üzenet')
        with self.db:
            cur=self.db.execute('INSERT INTO messages(conversation_id,role,text,status,request_id,created_at) VALUES(?,?,?,?,?,?)',(cid,role,text,status,request_id,stamp()))
        return cur.lastrowid

    def update_message(self,message_id,text,status):
        if not isinstance(text,str) or len(text)>32000 or status not in ('completed','failed','cancelled'):raise ValueError('Hibás üzenet')
        with self.db:self.db.execute('UPDATE messages SET text=?,status=? WHERE id=?',(text,status,message_id))

    def context(self,cid):
        # Failed/cancelled turns are visible in history but excluded from model input.
        rows=self.messages(cid);selected=[];size=0
        for r in reversed(rows):
            if r['status']!='completed':continue
            if len(selected)>=20 or size+len(r['text'])>24000:break
            selected.append(dict(role=r['role'],content=r['text']));size+=len(r['text'])
        return list(reversed(selected))

    def delete_conversation(self,cid):
        self.require_conversation(cid)
        with self.db:self.db.execute('DELETE FROM conversations WHERE id=?',(cid,))

    def export(self,cid):
        messages=self.messages(cid)
        return dict(conversation=dict(self.db.execute('SELECT * FROM conversations WHERE id=?',(cid,)).fetchone()),messages=messages)

    def memories(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM memory ORDER BY updated_at DESC,rowid DESC')]

    def save_memory(self,mid,text,source):
        if not isinstance(text,str) or not text.strip() or not isinstance(source,str) or not source.strip() or len(source)>200:raise ValueError('Hiányos emlék')
        if len(text)>8000:raise ValueError('Egy emlék legfeljebb 8000 karakter')
        if mid and not self.db.execute('SELECT id FROM memory WHERE id=?',(mid,)).fetchone():raise KeyError('Nincs ilyen emlék')
        total=self.db.execute('SELECT COALESCE(SUM(length(text)),0) FROM memory WHERE id != ?',(mid or '',)).fetchone()[0]
        if total+len(text)>100000:raise ValueError('A memória tárolási kerete betelt')
        mid=mid or str(uuid.uuid4())
        with self.db:self.db.execute('INSERT INTO memory VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text,source=excluded.source,updated_at=excluded.updated_at',(mid,text,source,stamp()))
        return mid

    def delete_memory(self,mid):
        with self.db:self.db.execute('DELETE FROM memory WHERE id=?',(mid,))

    def memory_context(self):
        result=[];size=0
        for m in self.memories():
            text=m['text']
            if size+len(text)>8000:continue
            result.append(text);size+=len(text)
        return result

    def setting(self,key,value=None):
        if value is not None:
            with self.db:self.db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
        row=self.db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return row[0] if row else None
