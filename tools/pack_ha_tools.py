"""Build a manual-install ZIP from the explicit integration subtree only."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'custom_components' / 'ziko_ha_tools'


def build(output_dir):
    version = json.loads((INTEGRATION / 'manifest.json').read_text())['version']
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f'Ziko_HA_Tools_{version}.zip'
    files = [p for p in INTEGRATION.rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.png', '.js')
             and '__pycache__' not in p.parts]
    contents = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(files)}
    contents['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    contents['ZIKO_HA_TOOLS.md'] = (ROOT / 'ZIKO_HA_TOOLS.md').read_bytes()
    contents['install_ziko.py'] = (ROOT / 'tools' / 'install_ziko.py').read_bytes()
    for path in sorted((ROOT / 'install-kit').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            contents[path.relative_to(ROOT / 'install-kit').as_posix()] = path.read_bytes()
    manifest={'version':version,'minimum_ha':'2026.10.0',
              'files':{name:{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)} for name,data in contents.items()}}
    contents['ZIKO_PACKAGE.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for name,data in sorted(contents.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            target.writestr(info,data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(f'{digest}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT.parent / 'deliverables')
    print(build(parser.parse_args().output_dir))
