"""Password-encrypted local transfer; never upload this payload to a repository."""
import base64
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .credentials import atomic_json, validate_record
from .scope import validate_devices

MAX_SIZE=32*1024*1024
FILES=('credentials.json','host.json','imported-sessions.json')

def cipher(password,salt):
    if not isinstance(password,str) or not 12<=len(password)<=200:
        raise ValueError('A költöztetési jelszó 12–200 karakter legyen')
    return Fernet(base64.urlsafe_b64encode(Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())))

def export_data(storage,directory,owner,approved,password):
    directory=Path(directory)
    data=dict(format=1,owner=owner,approved_devices=sorted(approved),
        database=base64.b64encode(storage.db.serialize()).decode(),
        files={name:json.loads((directory/name).read_text()) for name in FILES if (directory/name).exists()})
    raw=json.dumps(data).encode()
    if len(raw)>MAX_SIZE//2:raise ValueError('Túl nagy költöztetési mentés')
    salt=os.urandom(16)
    return 'ZIKO-MOVE-1\n'+base64.b64encode(salt).decode()+'\n'+cipher(password,salt).encrypt(raw).decode()

def decode_data(payload,password,owner):
    try:
        if not isinstance(payload,str) or len(payload)>MAX_SIZE:raise ValueError()
        header,salt,encrypted=payload.split('\n',2)
        if header!='ZIKO-MOVE-1':raise ValueError()
        salt=base64.b64decode(salt,validate=True)
        if len(salt)!=16:raise ValueError()
        raw=cipher(password,salt).decrypt(encrypted.encode())
        data=json.loads(raw)
        if data.get('format')!=1 or data.get('owner')!=owner:raise ValueError()
        validate_devices(data['approved_devices'])
        files=data['files']
        if not isinstance(files,dict) or set(files)-set(FILES):raise ValueError()
        if 'credentials.json' in files:validate_record(files['credentials.json'])
        if not isinstance(files.get('host.json',{}).get('host_id'),str):raise ValueError()
        database=base64.b64decode(data['database'],validate=True)
        db=sqlite3.connect(':memory:')
        try:
            db.deserialize(database)
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError()
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'conversations','messages','memory','settings'}<=tables:raise ValueError()
            if db.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:raise ValueError()
        finally:db.close()
        data['database']=database
        return data
    except (InvalidToken,ValueError,TypeError,KeyError,AttributeError,sqlite3.Error):
        raise ValueError('Hibás költöztetési fájl, jelszó vagy HA-felhasználó') from None

def restore_data(directory,data):
    directory=Path(directory)
    # Caller closes the fresh database first. Stage all files before replacing it.
    with tempfile.TemporaryDirectory(dir=directory,prefix='.migration-') as staged:
        stage=Path(staged)
        path=stage/'chat.sqlite';path.write_bytes(data['database']);path.chmod(0o600)
        for name,value in data['files'].items():atomic_json(stage/name,value)
        atomic_json(stage/'approved-devices.json',data['approved_devices'])
        atomic_json(stage/'migration-imported.json',dict(imported=True))
        names=(*FILES,'approved-devices.json','migration-imported.json','chat.sqlite')
        previous={name:(directory/name).read_bytes() if (directory/name).exists() else None for name in names}
        changed=[]
        try:
            for name in names:
                if (stage/name).exists():
                    os.replace(stage/name,directory/name);changed.append(name)
        except OSError:
            for name in reversed(changed):
                if previous[name] is None:(directory/name).unlink(missing_ok=True)
                else:
                    path=stage/name;path.write_bytes(previous[name]);path.chmod(0o600)
                    os.replace(path,directory/name)
            raise
