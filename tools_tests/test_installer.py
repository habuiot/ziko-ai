import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest


def installer():
    path=Path(__file__).parents[1]/'tools/install_ziko.py'
    assert path.exists(),'verified installer missing'
    spec=importlib.util.spec_from_file_location('install_ziko',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def package(tmp_path,files=None):
    files=files or {'custom_components/ziko_ha_tools/manifest.json':json.dumps({'domain':'ziko_ha_tools','version':'0.2.0'}).encode(),
        'custom_components/ziko_ha_tools/__init__.py':b'# new\n','custom_components/ziko_ha_tools/frontend/ziko-panel.js':b'// panel\n'}
    manifest={'version':'0.2.0','minimum_ha':'2026.10.0','files':{k:{'sha256':hashlib.sha256(v).hexdigest(),'size':len(v)} for k,v in files.items()}}
    path=tmp_path/'package.zip'
    with zipfile.ZipFile(path,'w') as z:
        for k,v in files.items():z.writestr(k,v)
        z.writestr('ZIKO_PACKAGE.json',json.dumps(manifest))
    return path


def config(tmp_path):
    root=tmp_path/'config';root.mkdir()
    (root/'.HA_VERSION').write_text('2026.10.0')
    (root/'configuration.yaml').write_text('default_config:\n')
    return root


def test_installer_check_is_read_only_and_install_rollback_preserve_config(tmp_path):
    mod=installer();root=config(tmp_path);archive=package(tmp_path)
    before=(root/'configuration.yaml').read_bytes()
    result=mod.install(archive,root,apply=False)
    assert result['status']=='ready' and not (root/'custom_components').exists()
    target=root/'custom_components/ziko_ha_tools';target.mkdir(parents=True)
    (target/'__init__.py').write_text('# old\n')
    result=mod.install(archive,root,apply=True)
    assert result['status']=='installed' and (target/'__init__.py').read_text()=='# new\n'
    assert (root/'configuration.yaml').read_bytes()==before
    rolled=mod.rollback(root,result['backup_id'])
    assert rolled['status']=='rolled_back' and (target/'__init__.py').read_text()=='# old\n'
    assert not (target/'frontend').exists()


def test_corruption_unknown_member_and_path_escape_never_change_target(tmp_path):
    mod=installer();root=config(tmp_path);archive=package(tmp_path)
    with zipfile.ZipFile(archive,'a') as z:z.writestr('../outside',b'bad')
    with pytest.raises(ValueError):mod.install(archive,root,apply=True)
    assert not (root/'custom_components').exists()
    archive=package(tmp_path)
    with zipfile.ZipFile(archive,'a') as z:z.writestr('unknown.py',b'bad')
    with pytest.raises(ValueError):mod.install(archive,root,apply=True)
    assert not (root/'custom_components').exists()


def test_symlink_target_and_changed_code_refuse_install_or_rollback(tmp_path):
    mod=installer();root=config(tmp_path);archive=package(tmp_path)
    outside=tmp_path/'outside';outside.mkdir()
    (root/'custom_components').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError):mod.install(archive,root,apply=True)
    (root/'custom_components').unlink()
    result=mod.install(archive,root,apply=True)
    target=root/'custom_components/ziko_ha_tools'
    (target/'__init__.py').write_text('# manually changed')
    with pytest.raises(ValueError):mod.rollback(root,result['backup_id'])
    assert (target/'__init__.py').read_text()=='# manually changed'


def test_unsupported_ha_version_and_tampered_checksum_deny_install(tmp_path):
    mod=installer();root=config(tmp_path);archive=package(tmp_path)
    (root/'.HA_VERSION').write_text('2026.9.9')
    with pytest.raises(ValueError):mod.install(archive,root,apply=True)
    (root/'.HA_VERSION').write_text('2026.10.0')
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()}
    files['custom_components/ziko_ha_tools/__init__.py']=b'# tampered'
    with zipfile.ZipFile(archive,'w') as z:
        for n,v in files.items():z.writestr(n,v)
    with pytest.raises(ValueError):mod.install(archive,root,apply=True)


def test_builder_includes_panel_and_verified_installer_manifest(tmp_path):
    from tools.pack_ha_tools import build
    archive=build(tmp_path)
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist())
        assert 'custom_components/ziko_ha_tools/frontend/ziko-panel.js' in names
        assert {'install_ziko.py','START.sh','KEZDD_ITT.md','ZIKO_PACKAGE.json','Ziko_prompt_v2.txt'}<=names
        manifest=json.loads(z.read('ZIKO_PACKAGE.json'))
        assert set(manifest['files'])==names-{'ZIKO_PACKAGE.json'}
        assert all(hashlib.sha256(z.read(n)).hexdigest()==record['sha256'] for n,record in manifest['files'].items())
        assert not any(n.startswith(('ziko_ai/','src/','.storage/')) for n in names)
