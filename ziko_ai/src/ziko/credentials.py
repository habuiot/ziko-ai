"""Local storage only. Imports additionally require OAuth signature validation."""
import asyncio
import hashlib
import json
import math
import os
import tempfile
import uuid
from pathlib import Path

ISSUER = 'https://auth.openai.com'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
IS_POSIX = os.name == 'posix'

def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(suffix='.tmp', dir=path.parent)
    try:
        if IS_POSIX:os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
        if IS_POSIX:
            directory = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)

def validate_record(record: dict) -> None:
    if not isinstance(record, dict) or record.get('issuer') != ISSUER:
        raise ValueError('Hibás kapcsolati fájl')
    for field in ('subject','client_id','access_token','refresh_token','id_token'):
        if not isinstance(record.get(field),str) or not record[field] or len(record[field]) > 32000:
            raise ValueError('Hiányos kapcsolati fájl')
    if not record['client_id'].startswith('oaiapp_'):
        raise ValueError('Hibás kliensazonosító')
    scopes=record.get('scopes')
    if not isinstance(scopes,list) or not all(isinstance(s,str) for s in scopes) or not {PLAN_SCOPE,'resource.invoke','offline_access'} <= set(scopes):
        raise ValueError('A ChatGPT-plan jogosultság hiányzik')
    expiry=record.get('expires_at')
    if isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not math.isfinite(expiry) or expiry <= 0:
        raise ValueError('Hibás lejárati idő')
    if len(json.dumps(record).encode()) > 65536:
        raise ValueError('Túl nagy kapcsolati fájl')

class CredentialStore:
    def __init__(self, data_dir: Path):
        self.directory=Path(data_dir)
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=self.directory/'credentials.json'
        self.refresh_lock=asyncio.Lock()
        host_path=self.directory/'host.json'
        if not host_path.exists(): atomic_json(host_path, {'host_id':f'urn:uuid:{uuid.uuid4()}'})
        self._host_id=json.loads(host_path.read_text())['host_id']

    def host_id(self) -> str: return self._host_id

    def load(self) -> dict | None:
        if not self.path.exists(): return None
        value=json.loads(self.path.read_text(encoding='utf-8'))
        validate_record(value)
        return value

    def replace(self, record: dict) -> None:
        validate_record(record)
        atomic_json(self.path, record)

    def import_once(self,record: dict) -> None:
        validate_record(record)
        receipt_path=self.directory/'imported-sessions.json'
        receipts=json.loads(receipt_path.read_text()) if receipt_path.exists() else {'fingerprints':[]}
        fingerprint=hashlib.sha256(record['id_token'].encode()).hexdigest()
        if fingerprint in receipts['fingerprints']:
            raise ValueError('Ezt a bejelentkezést már importáltad; új kapcsolatért jelentkezz be újra')
        receipts['fingerprints'].append(fingerprint)
        # Persist the replay barrier first. A crash requires a fresh sign-in, never rollback to a spent refresh token.
        atomic_json(receipt_path,receipts)
        self.replace(record)

    def disconnect(self) -> None:
        self.path.unlink(missing_ok=True)

    def status(self) -> dict:
        r=self.load()
        if not r: return {'connected':False,'host_id':self.host_id()}
        return {'connected':True,'host_id':self.host_id(),'subject':r['subject'],
                'email':r.get('email',''),'expires_at':r['expires_at']}
