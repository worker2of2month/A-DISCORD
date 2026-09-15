"""Reject missing/stale WebGL captures; visual judgement remains a human review."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--family',choices=('city','weapon','infantry','hq'))
parser.add_argument('--infantry-root',type=Path)
parser.add_argument('--hq-root',type=Path)
args=parser.parse_args()
groups={
    'city':('WRK_city','gfx/models/buildings/ADISCORD_city',9),
    'weapon':('infantry_weapons_3d','gfx/models/units/ADISCORD_weapons',8),
    'infantry':('STP_regulars','gfx/models/units/ADISCORD_regulars',10),
    'hq':('STP_regulars','gfx/models/units/ADISCORD_headquarters',5),
}
report={}
for family,(source,runtime,count) in groups.items():
    if args.family and args.family!=family:continue
    runtime_root=args.infantry_root if family=='infantry' and args.infantry_root else MOD/runtime
    if family=='hq' and args.hq_root:runtime_root=args.hq_root
    directory=ROOT/source/'jorodox_visual'
    captures=sorted(directory.glob(f'{family}_*.json'))
    assert len(captures)==count*2
    names={}
    for path in captures:
        data=json.loads(path.read_text())
        mesh=runtime_root/data['filename']
        assert hashlib.sha256(mesh.read_bytes()).hexdigest()==data['sha256'],str(path)+': stale mesh'
        assert data['materialSide']=='FrontSide' and data['webglError']==0
        assert data['textureAddress']=='Wrap (native pdxmesh.shader)'
        assert data['textures'],str(path)+': missing material hashes'
        for url,digest in data['textures'].items():
            texture=runtime_root/Path(url).name
            assert hashlib.sha256(texture.read_bytes()).hexdigest()==digest,str(texture)+': stale texture'
        png=path.with_suffix('.png')
        picture=Image.open(png)
        assert picture.size==(1100,740) and len(picture.getcolors(1100*740))>100
        names.setdefault(data['filename'],[]).append(data['side'])
    assert len(names)==count and all(sorted(sides)==['front','reverse'] for sides in names.values())
    report[family]={'meshes':count,'captures':len(captures),'current_mesh_hashes':True,
                    'FrontSide':True,'webgl_errors':0,
                    'limitation':'Actual JoroDox loaders rendered in a local WebGL harness; Phong fallback is not HOI4 entity/lighting proof'}
destination=ROOT/'jorodox_visual_report.json'
if args.family:
    filename='jorodox_hq_visual_report.json' if args.family=='hq' else 'jorodox_visual_report.json'
    destination=ROOT/groups[args.family][0]/filename
destination.write_text(json.dumps(report,indent=2))
print(json.dumps(report))
