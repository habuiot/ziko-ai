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
    files = [p for p in INTEGRATION.rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.png')
             and '__pycache__' not in p.parts]
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for path in sorted(files):
            target.write(path, path.relative_to(ROOT).as_posix())
        target.write(ROOT / 'ZIKO_HA_TOOLS.md', 'ZIKO_HA_TOOLS.md')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(f'{digest}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT.parent / 'deliverables')
    print(build(parser.parse_args().output_dir))
