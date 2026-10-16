"""Offline, integrity-checked Ziko integration install/rollback. Python 3.10+."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile

DOMAIN='ziko_ha_tools'
PREFIX='custom_components/'+DOMAIN+'/'
BACKUPS='ziko_code_backups'


def safe_tree(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink targets are not supported')
    if path.exists():
        if not path.is_dir():raise ValueError('Expected a directory')
        for child in path.rglob('*'):
            if child.is_symlink() or (not child.is_file() and not child.is_dir()):
                raise ValueError('Symlink/special file in integration or backup; no changes made')


def tree_hash(path):
    path=Path(path);safe_tree(path)
    if not path.exists():return None
    h=hashlib.sha256()
    for p in sorted(path.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):continue
        h.update(p.relative_to(path).as_posix().encode()+b'\0');h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def verify_archive(archive):
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>500 or sum(i.file_size for i in infos)>20_000_000:
            raise ValueError('Package size limit exceeded')
        names=[i.filename for i in infos]
        if len(names)!=len(set(n.casefold() for n in names)):
            raise ValueError('Duplicate archive paths')
        for info in infos:
            name=info.filename;path=PurePosixPath(name)
            mode=info.external_attr>>16
            if (path.is_absolute() or '..' in path.parts or '\\' in name or '\x00' in name
                    or str(path)!=name or info.is_dir() or stat.S_ISLNK(mode)):
                raise ValueError('Unsafe archive member')
        if 'ZIKO_PACKAGE.json' not in names:raise ValueError('Package integrity manifest missing')
        manifest=json.loads(z.read('ZIKO_PACKAGE.json'))
        records=manifest.get('files')
        if not isinstance(records,dict) or set(records)!=set(names)-{'ZIKO_PACKAGE.json'}:
            raise ValueError('Package manifest does not exactly match archive members')
        files={}
        for name,record in records.items():
            content=z.read(name)
            if len(content)!=record.get('size') or hashlib.sha256(content).hexdigest()!=record.get('sha256'):
                raise ValueError('Package checksum mismatch')
            if name.startswith(PREFIX):
                if PurePosixPath(name).suffix not in ('.py','.json','.png','.js'):
                    raise ValueError('Unsupported integration asset')
                files[name[len(PREFIX):]]=content
        if 'manifest.json' not in files or '__init__.py' not in files:
            raise ValueError('Incomplete integration package')
        integration=json.loads(files['manifest.json'])
        if integration.get('domain')!=DOMAIN or integration.get('version')!=manifest.get('version'):
            raise ValueError('Integration identity/version mismatch')
        return manifest,files


def check_config(config,allow_untested=False):
    config=Path(config).absolute()
    if not config.is_dir() or config.is_symlink():raise ValueError('Use a real HA config directory')
    if not (config/'configuration.yaml').is_file():raise ValueError('HA configuration.yaml was not found')
    version=(config/'.HA_VERSION').read_text().strip() if (config/'.HA_VERSION').is_file() else ''
    match=re.match(r'^(\d+)\.(\d+)\.(\d+)',version)
    if not match:raise ValueError('HA version is unknown; no files changed')
    ver=tuple(map(int,match.groups()))
    if ver<(2026,10,0) or (ver[:2]!=(2026,10) and not allow_untested):
        raise ValueError('This package is verified on HA 2026.10; use a compatible release')
    for p in (config/'custom_components',config/BACKUPS,config/'custom_components'/DOMAIN):safe_tree(p)
    return config,version


@contextmanager
def install_lock(config):
    path=config/'.ziko-install.lock'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        yield
    finally:path.unlink(missing_ok=True)


def write_json(path,data):
    tmp=path.with_suffix('.tmp')
    with open(tmp,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def install(archive,config,apply=False,allow_untested=False):
    manifest,files=verify_archive(archive)
    config,ha_version=check_config(config,allow_untested)
    target=config/'custom_components'/DOMAIN
    if not apply:return {'status':'ready','version':manifest['version'],'ha_version':ha_version,'files':len(files),'note':'Read-only check; no installed files changed'}
    with install_lock(config):
        target.parent.mkdir(exist_ok=True)
        backup_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:10]
        backup=config/BACKUPS/backup_id;backup.mkdir(parents=True,mode=0o700)
        stage=Path(tempfile.mkdtemp(prefix='.ziko-stage-',dir=config))
        try:
            source=stage/DOMAIN;source.mkdir()
            for name,content in files.items():
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            record={'backup_id':backup_id,'version':manifest['version'],'before_digest':tree_hash(target),
                    'installed_digest':tree_hash(source),'had_previous':target.exists(),'rolled_back':False}
            write_json(backup/'backup.json',record)
            if target.exists():os.replace(target,backup/'previous')
            try:os.replace(source,target)
            except BaseException:
                if (backup/'previous').exists():os.replace(backup/'previous',target)
                raise
            return {'status':'installed','version':manifest['version'],'backup_id':backup_id,
                    'note':'Only Ziko integration code replaced. Restart HA, then review integration options.'}
        finally:shutil.rmtree(stage,ignore_errors=True)


def rollback(config,backup_id):
    config,_=check_config(config,True)
    if not re.fullmatch(r'\d{8}T\d{6}Z_[a-f0-9]{10}',backup_id):raise ValueError('Invalid backup ID')
    backup=config/BACKUPS/backup_id
    safe_tree(backup)
    marker=backup/'backup.json'
    if not marker.is_file():raise ValueError('Backup record missing')
    record=json.loads(marker.read_text())
    target=config/'custom_components'/DOMAIN
    if record.get('rolled_back'):return {'status':'already_rolled_back','backup_id':backup_id}
    with install_lock(config):
        if tree_hash(target)!=record.get('installed_digest'):
            raise ValueError('Installed code changed after this update; refusing to overwrite it')
        previous=backup/'previous'
        if record.get('had_previous') and tree_hash(previous)!=record.get('before_digest'):
            raise ValueError('Previous-code backup is missing or altered')
        os.replace(target,backup/'removed_update')
        if record.get('had_previous'):os.replace(previous,target)
        record['rolled_back']=True;write_json(marker,record)
    return {'status':'rolled_back','backup_id':backup_id,'note':'Only code rolled back. Existing HA storage and configuration were preserved; restart HA.'}


def main():
    parser=argparse.ArgumentParser(description='Ziko ellenőrzött helyi telepítő')
    parser.add_argument('archive',nargs='?',type=Path)
    parser.add_argument('--config',type=Path,default=Path('/config'))
    parser.add_argument('--apply',action='store_true',help='Ellenőrzés után telepítés, kódmentéssel')
    parser.add_argument('--rollback',metavar='BACKUP_ID')
    parser.add_argument('--restart',action='store_true',help='Siker után ha core check, majd újraindítás')
    parser.add_argument('--allow-untested',action='store_true')
    args=parser.parse_args()
    try:
        if args.rollback:result=rollback(args.config,args.rollback)
        elif args.archive:result=install(args.archive,args.config,args.apply,args.allow_untested)
        else:parser.error('Add meg a ZIP-et vagy a --rollback azonosítót')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if args.restart and (args.apply or args.rollback):
            if not shutil.which('ha'):raise ValueError('A ha CLI nem elérhető; a kód kész, indítsd újra a HA felületén')
            print('HA konfiguráció ellenőrzése…',flush=True)
            try:subprocess.run(['ha','core','check'],check=True,timeout=180)
            except (subprocess.SubprocessError,OSError):
                if result['status']=='installed':
                    print(json.dumps(rollback(args.config,result['backup_id']),ensure_ascii=False),flush=True)
                raise ValueError('HA-ellenőrzés nem sikerült; nincs automatikus újraindítás. Ellenőrizd az eredményt.')
            print('HA újraindítása…',flush=True)
            subprocess.run(['ha','core','restart'],check=True,timeout=180)
    except (ValueError,OSError,zipfile.BadZipFile,KeyError,TypeError,subprocess.SubprocessError) as err:
        parser.exit(1,f'Ziko: {err}\n')


if __name__=='__main__':main()
