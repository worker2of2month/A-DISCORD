"""Check the NAM naval package; --apply rebuilds or installs verified staging.

Use --staging PATH to install an already built headquarters/marines/aircraft
package. Without staging, --apply builds into the system temporary directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets/source'))
from tools.assets.source import build_country_aircraft as aircraft
from tools.assets.source import build_headquarters as headquarters
from tools.assets.source import build_specialists as specialists

REPORT = ROOT / 'docs/development/model-verification/NAM_naval_package.json'
NAMES = tuple(name for name in aircraft.NAMES if name.startswith('NAM_'))
SOURCES = (
    'tools/builders/build_adiscord_nam_models.py',
    'tools/assets/source/build_headquarters.py',
    'tools/assets/source/build_specialists.py',
    'tools/assets/source/build_country_aircraft.py',
    'tools/assets/source/build_country_cas.py',
    'tools/assets/source/build_shl_palace.py',
    'tools/assets/source/build_crimson_sentinel.py',
    'tools/assets/source/country_vehicles/package_vehicles.py',
    'tools/assets/source/build_northern_infantry.py',
    'tools/assets/source/infantry_polish.py',
    'gfx/leaders/NAM/portrait_NAM_generic_land_01.png',
    'gfx/leaders/NAM/portrait_NAM_generic_land_02.png',
    'gfx/leaders/NAM/portrait_NAM_Grigory_Levashov.png',
    'gfx/models/units/ADISCORD_regulars/NAM_field.mesh',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = [ROOT / path for path in SOURCES]
    paths.extend(sorted((ROOT / 'gfx/models/units/ADISCORD_regulars').glob('NAM_field_*.dds')))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def outputs():
    paths = []
    for directory, pattern in (
        ('gfx/models/units/ADISCORD_headquarters', 'NAM_hq*'),
        ('gfx/models/units/ADISCORD_specialists', 'NAM_marine*'),
        ('gfx/models/units/ADISCORD_country_vehicles', 'NAM_*fighter*'),
        ('gfx/models/units/ADISCORD_country_vehicles', 'NAM_*cas*'),
        ('tools/assets/source/country_vehicles', 'NAM_*fighter.blend'),
        ('tools/assets/source/country_vehicles', 'NAM_*cas.blend'),
    ):
        paths.extend(sorted((ROOT / directory).glob(pattern)))
    paths.extend(ROOT / path for path in (
        'tools/assets/source/NAM_hq.blend', 'tools/assets/source/NAM_marine.blend',
        'docs/development/model-verification/NAM_headquarters.json',
        'docs/development/model-verification/NAM_marines.json',
    ))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def check():
    if not REPORT.is_file():
        return ['NAM package manifest is missing']
    report = json.loads(REPORT.read_text())
    issues = []
    if report['sources'] != sources():
        issues.append('NAM authoring inputs changed; rebuild required')
    aircraft_report = json.loads((ROOT / 'docs/development/model-verification/aircraft_verification.json').read_text())
    if report['aircraft'] != {name: aircraft_report.get(name) for name in NAMES}:
        issues.append('NAM aircraft verification rows changed')
    for path, expected in report['outputs'].items():
        if not (ROOT / path).is_file() or digest(ROOT / path) != expected:
            issues.append(path)
    for path, expected in {**headquarters.bindings('NAM'), **specialists.bindings()}.items():
        if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected:
            issues.append(str(path))
    return issues


def rebuild(staging, blender):
    def python(script, folder, *args):
        subprocess.run([sys.executable, '-B', str(ROOT / script), '--output',
                        str(staging / folder), *args], cwd=ROOT, check=True)

    def native(script, folder, *args):
        subprocess.run([str(blender), '--background', '--factory-startup',
                        '--threads', '4', '--python-exit-code', '1', '--python', str(ROOT / script),
                        '--', '--output', str(staging / folder), *args], cwd=ROOT, check=True)

    for script, folder, options in (
        ('tools/assets/source/build_headquarters.py', 'headquarters', ('--tag', 'NAM')),
        ('tools/assets/source/build_specialists.py', 'marines', ()),
    ):
        native(script, folder, '--build', *options)
        python(script, folder, *options)
        native(script, folder, '--verify', *options)
    script = 'tools/assets/source/build_country_aircraft.py'
    python(script, 'aircraft', '--prepare', '--names', *NAMES)
    native(script, 'aircraft', '--build', '--names', *NAMES)


def install(staging):
    # Validate every package before the first runtime write.
    aircraft.package(staging / 'aircraft', names=NAMES)
    prepared = {}
    for folder, module, key, name in (
        ('headquarters', headquarters, 'hashes', 'NAM_hq'),
        ('marines', specialists, 'files', 'NAM_marine'),
    ):
        report = json.loads((staging / folder / 'verification.json').read_text())
        if report['generator_sha256'] != digest(Path(module.__file__)):
            raise ValueError(f'Stale generator verification: {name}')
        content = headquarters.package_files(staging / folder, 'NAM') if folder == 'headquarters' else specialists.files(staging / folder)
        for path, data in content.items():
            if path.parent == module.DEST and report[key].get(path.name) != hashlib.sha256(data).hexdigest():
                raise ValueError(f'Unverified native export: {path}')
        prepared.update(content)
        if not (staging / folder / f'{name}.blend').is_file():
            raise ValueError(f'Missing editable source: {name}')
    for path, data in prepared.items():
        target = ROOT / path
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    aircraft.package(staging / 'aircraft', apply=True, names=NAMES)
    aircraft_report = json.loads((ROOT / 'docs/development/model-verification/aircraft_verification.json').read_text())
    payload = {
        'sources': sources(), 'outputs': outputs(),
        'aircraft': {name: aircraft_report[name] for name in NAMES},
        'visual_reference': 'NAM general portraits; NAM line infantry body and equipment',
        'native_reimport': True, 'hoi4_runtime_verified': False,
    }
    content = (json.dumps(payload, indent=2) + '\n').encode()
    if not REPORT.is_file() or REPORT.read_bytes() != content:
        REPORT.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Check installed outputs (default)')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--staging', type=Path)
    parser.add_argument('--blender', type=Path)
    args = parser.parse_args()
    issues = check()
    if args.apply and (issues or args.staging):
        staging = args.staging or Path(tempfile.gettempdir()) / 'adiscord-nam-models'
        if not args.staging:
            blender = args.blender or shutil.which('blender')
            if not blender:
                blender = Path('C:/Program Files/Blender Foundation/Blender 4.5/blender.exe')
            rebuild(staging, blender)
        install(staging)
        issues = check()
    print(json.dumps({'issues': issues, 'applied': args.apply}, indent=2))
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
