"""Prepare source DDS and install/check the separate regular infantry package."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent
MOD = ROOT.parents[3]
DEST = MOD / 'gfx/models/units/ADISCORD_regulars'
LABELS = ('STP_party', 'STS_regular', 'VAL_regular')
FACTIONS = json.loads((ROOT / 'factions.json').read_text())
LABELS += tuple(FACTIONS)
GAME = Path('Z:/SteamLibrary/steamapps/common/Hearts of Iron IV')
sys.path.insert(0, str(ROOT.parent / 'STP_shabrat'))
from package_shabrat import dds_mips, resize_channels
sys.path.insert(0, str(ROOT.parent / 'WRK_city'))
from package_city import spans
sys.path.insert(0, str(ROOT.parent))
from repair_val_idle import idle_group, START as IDLE_START, END as IDLE_END

START = '# BEGIN ADISCORD infantry forms\n'
END = '# END ADISCORD infantry forms\n'
NOD_POSES_START = '# BEGIN ADISCORD NOD field poses\n'
NOD_POSES_END = '# END ADISCORD NOD field poses\n'


def unowned(text):
    return re.sub(re.escape(START)+r'.*?'+re.escape(END),'',text,flags=re.S).rstrip()+'\n'


def named_blocks(text, kind):
    return {re.search(r'\bname\s*=\s*"([^"]+)"',text[a:b])[1]:text[a:b]
            for a,b in spans(text,kind)}


def nod_field_poses(parent):
    # Smoking parks the weapon through the carrier. Field drills remain upright
    # so sloped map terrain cannot separate a prone body from its contact plane.
    idle=idle_group(parent,'head')
    states=[idle[a:b] for a,b in spans(idle,'state') if '"long_idle03"' not in idle[a:b]]
    assert len(states)==4
    states.extend(('state = { name = "training" animation = "idle" animation_blend_time = 0.3 looping = no chance = 1 }',
                   'state = { name = "training" animation = "aim_exercise" animation_blend_time = 0.3 looping = no chance = 2 }'))
    return NOD_POSES_START+'\n'.join('\t'+state for state in states)+'\n'+NOD_POSES_END


def bindings():
    gfx_path=MOD/'gfx/entities/ADISCORD_country_infantry.gfx'
    gfx=unowned(gfx_path.read_text())
    existing=named_blocks(gfx,'pdxmesh')
    templates={'rifle':existing['STP_shabrat_infantry_mesh'],
               'mg':existing['STP_shabrat_mg_infantry_mesh']}
    definitions=[]
    for label in LABELS:
        for pose in ('rifle','mg'):
            name=f'ADISCORD_{label}'+('_rifle_mesh' if pose=='rifle' else '_mesh')
            if name in existing:
                continue
            block=templates[pose]
            block=re.sub(r'\bname\s*=\s*"[^"]+"',f'name = "{name}"',block,count=1)
            block=re.sub(r'\bfile\s*=\s*"[^"]+"',f'file = "gfx/models/units/ADISCORD_regulars/{label}.mesh"',block,count=1)
            definitions.append(block)
    gfx+='\n'+START+'objectTypes = {\n'+'\n'.join(definitions)+'\n}\n'+END
    path=MOD/'gfx/entities/zz_ADISCORD_country_infantry.asset'
    source=unowned(path.read_text())
    regular={'STP':'STP_party','STS':'STS_regular','VAL':'VAL_regular'}
    old_mesh={'STP':('STP_infantry_hedonist_mesh','STP_infantry_hedonist_mg_mesh'),
              'STS':('STP_shabrat_infantry_mesh','STP_shabrat_mg_infantry_mesh'),
              'VAL':('VAL_infantry_mesh','VAL_infantry_mg_mesh')}
    for a,b in reversed(list(spans(source,'entity'))):
        block=source[a:b]
        name=re.search(r'\bname\s*=\s*"([^"]+)"',block)[1]
        match=re.fullmatch(r'(STP|STS|VAL|NOD)_infantry(?:_([2-8]))?_entity',name)
        if not match:continue
        tag,level=match.groups()
        if tag=='NOD':
            block=re.sub(re.escape(NOD_POSES_START)+r'.*?'+re.escape(NOD_POSES_END),'',block,flags=re.S)
            parent='infantry_2_entity' if level else 'infantry_rifle_entity'
            block=block[:block.rfind('}')]+nod_field_poses(parent)+'}'
        body=(('ADISCORD_NOD_line_mesh' if level else 'ADISCORD_NOD_line_rifle_mesh') if tag=='NOD' else
              f'ADISCORD_{regular[tag]}'+('_mesh' if level else '_rifle_mesh'))
        block=re.sub(r'\n[ \t]*pdxmesh\s*=\s*"[^"]+"','',block)
        if tag=='VAL':
            block=block.replace('node="back_mid|head|head"','node="head"')
        block=block[:block.rfind('}')]+f'\tpdxmesh = "{body}"\n}}'
        source=source[:a]+block+source[b:]
    rows=[]
    for tag in regular:
        for level in range(8):
            suffix='_'+str(level+1) if level else ''
            row=f'entity = {{ clone = "{tag}_infantry{suffix}_entity" name = "{tag}_ADISCORD_militia{suffix}_entity" pdxmesh = "{old_mesh[tag][bool(level)]}"'
            if tag=='VAL':
                parent='infantry_2_entity' if level else 'infantry_rifle_entity'
                row+='\n'+IDLE_START+idle_group(parent,'back_mid|head|head')+IDLE_END
            rows.append(row+' }')
    cosmetics={'WRK_line':('WRK_vorkerland_emergency','WRK_vorkerland_utilitarian_republic'),
               'VAD_line':('VAD_vorkerland_restoration','WRK_vorkerland_joint_government')}
    for label,config in FACTIONS.items():
        for level in range(8):
            suffix='_'+str(level+1) if level else ''
            family=f'ADISCORD_{label}_infantry{suffix}_entity'
            body=f'ADISCORD_{label}'+('_mesh' if level else '_rifle_mesh')
            rows.append(f'entity = {{ clone = "STP_infantry{suffix}_entity" name = "{family}" pdxmesh = "{body}" }}')
            for tag in (*config['tags'],*cosmetics.get(label,())):
                if tag=='NOD':continue
                rows.append(f'entity = {{ clone = "{family}" name = "{tag}_infantry{suffix}_entity" }}')
                if tag=='SRP':
                    for role in ('ADISCORD_militia','mountaineers'):
                        rows.append(f'entity = {{ clone = "{family}" name = "SRP_{role}{suffix}_entity" }}')
    # Confederate uniforms cover regular and militia display entities at every weapon tier.
    for tag in ('WRK', 'NAM', 'DAN', 'ZAO', 'PWR', 'VLA', 'ROM', 'SOL', 'TRU', 'WCG', 'EYR', 'EGC', 'RIV', 'YOR'):
        for level in range(8):
            suffix='_'+str(level+1) if level else ''
            for role in ('infantry', 'ADISCORD_militia', 'mountaineers'):
                rows.append(f'entity = {{ clone = "ADISCORD_WRK_line_infantry{suffix}_entity" name = "{tag}_confederation_{role}{suffix}_entity" }}')
    source+='\n'+START+'\n'.join(rows)+'\n'+END
    return {gfx_path:gfx.encode(),path:source.encode()}


def prepare(labels=LABELS):
    for label in labels:
        for part in ('body', 'gear'):
            # Gear UVs are rebuilt with the mesh, so use its matching bake.
            source = ROOT / (f'{label}_gear_diffuse.png' if part == 'gear'
                             else f'{label}_body_source.png')
            if not source.is_file():
                source = ROOT / f'{label}_{part}_diffuse.png'
            if not source.is_file() and part == 'gear':
                continue
            Image.open(source).convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS).save(
                ROOT / f'{label}_{part}_diffuse.dds', pixel_format='DXT5')
            if part == 'body':
                specular=(GAME/f'gfx/models/units/{FACTIONS[label]["donor"]}_infantry_spec.dds'
                          if label in FACTIONS else ROOT.parent/'STP_shabrat/Shabrat_body_specular.dds')
            else:
                specular=ROOT/f'{label}_gear_specular.png'
            if specular.is_file():
                resize_channels(Image.open(specular).convert('RGBA'),(1024,1024)).save(
                    ROOT/f'{label}_{part}_specular.dds',pixel_format='DXT5')
        normal = (GAME / f'gfx/models/units/{FACTIONS[label]["donor"]}_infantry_normal.dds'
                  if label in FACTIONS else ROOT.parent / 'STP_shabrat/Shabrat_body_normal.dds')
        target=ROOT / f'{label}_body_normal.dds'
        if Image.open(normal).size in ((512,512),(1024,1024)):
            target.write_bytes(normal.read_bytes())
        else:
            resize_channels(Image.open(normal).convert('RGBA'),(512,512)).save(target,pixel_format='DXT5')
        gear_normal=ROOT/f'{label}_gear_normal.png'
        if gear_normal.is_file():
            Image.open(gear_normal).convert('RGBA').save(ROOT/f'{label}_gear_normal.dds',pixel_format='DXT5')



def package(apply=False, preview=None):
    files = bindings()
    for label in LABELS:
        name = label + '.mesh'
        files[DEST/name] = (ROOT / name).read_bytes()
        for part in ('body', 'gear'):
            for kind in ('diffuse', 'normal', 'specular'):
                name = f'{label}_{part}_{kind}.dds'
                files[DEST/name] = dds_mips(ROOT / name,packed_channels=kind!='diffuse')
    if apply:
        DEST.mkdir(parents=True, exist_ok=True)
    changed = [path for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    if preview:
        preview=Path(preview).resolve()
        assert preview!=MOD.resolve() and MOD.resolve() not in preview.parents
        for path,data in files.items():
            target=preview/path.relative_to(MOD)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
    if apply:
        for path in changed:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(files[path])
        report = {str(path.relative_to(MOD)): {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                  for path, data in files.items()}
        (ROOT / 'package_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'files': len(files), 'changed': [str(p.relative_to(MOD)) for p in changed], 'applied': apply}, indent=2))
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--labels', nargs='+', choices=LABELS)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.labels or LABELS)
    else:
        changes = package(args.apply,args.preview)
        if args.check and changes:
            raise SystemExit(1)
