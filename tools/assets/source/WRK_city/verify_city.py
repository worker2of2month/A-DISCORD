"""Check bounded city integration, source preservation and foundation clearance."""
import hashlib
import argparse
import json
import math
import re
import struct
import subprocess
from pathlib import Path
from package_city import (ROOT,MOD,DEST,NAMES,RETIRED_FILES,outputs,
                          remove_owned,remove_retired_registry,clear_old_placements,spans,old_city_object,ground_landmarks)


def main(preview=False):
    files,placement=outputs()
    if not preview:
        assert all(p.is_file() and p.read_bytes()==data for p,data in files.items()),'Package drift'
    baseline=json.loads((ROOT/'integration_baseline.json').read_text())
    for rel,old in baseline.items():
        before=remove_owned(old['text'])
        after=remove_owned(files[MOD/rel].decode() if MOD/rel in files else (MOD/rel).read_text())
        if rel=='map/ambient_object.txt':
            before=clear_old_placements(before)
            after=clear_old_placements(after)
            before=ground_landmarks(before,placement['landmarks'])
            after=ground_landmarks(after,placement['landmarks'])
        elif rel.endswith(('.gfx','.asset')):
            # Registries also contain independently maintained landmark actors.
            # This builder must preserve its current input outside city entries.
            before=remove_owned((MOD/rel).read_text())
            kind=Path(rel).suffix[1:]
            before=remove_retired_registry(before,kind)
            after=remove_retired_registry(after,kind)
        assert before==after,rel+': unrelated content changed'
    sources=json.loads((ROOT/'material_sources.json').read_text())['source_sha256']
    originals=['city_4_04','city_4_03','western_buildings_4_02']
    assert all(not path.exists() for path in RETIRED_FILES),'Retired skyscraper files remain'
    for rel,expected in sources.items():
        assert hashlib.sha256((MOD/rel).read_bytes()).hexdigest()==expected
    for name in originals:
        rel=f'gfx/models/buildings/{name}.mesh'
        committed=subprocess.check_output(['git','show','HEAD:'+rel],cwd=MOD)
        assert (MOD/rel).read_bytes()==committed,rel+': original mesh changed'
    ambient=files[MOD/'map/ambient_object.txt'].decode()
    assert ground_landmarks(ambient,placement['landmarks'])==ambient,'Landmark placement is not idempotent'
    external=[]
    for a,b in spans(ambient,'type'):
        block=ambient[a:b]
        kind=re.search(r'type\s*=\s*"([^"]+)"',block)
        if kind and kind[1].startswith(('cityblock','skyscraper')):
            for c,d in spans(block,'object'):
                obj=block[c:d]
                assert not old_city_object(obj),'Legacy city model remains inside city'
                external.append(obj)
    assert len(external)==1
    registry=(MOD/'gfx/entities/mapitems_custom.gfx').read_text()
    entities=(MOD/'gfx/entities/mapitems_custom.asset').read_text()
    assert not re.search(r'skyscraper[123]_',registry+entities+ambient),'Retired skyscraper registration remains'
    for name in NAMES:
        assert len(re.findall(r'name\s*=\s*"ADISCORD_city_'+name+'_mesh"',registry))==1
        assert len(re.findall(r'name\s*=\s*"ADISCORD_city_'+name+'_entity"',entities))==1
    assert 'ADISCORD_city_STP_' not in registry+entities
    assert 'ADISCORD_city_' not in (MOD/'map/cities.txt').read_text()
    original=(MOD/'map/cities.bmp').read_bytes()
    palette=placement['city_palette_manifest']
    for change in palette['changes']:
        assert original[change['offset']]==change['before']
    assert hashlib.sha256(original).hexdigest()==palette['original_sha256'],'Original procedural city mask not restored'
    for i,p in enumerate(placement['objects']):
        lo,hi=p['terrain_range']
        bottom,top=p['foundation_world_range']
        assert bottom<lo-.15 and top>=hi+.0099
        for retained in placement['retained_clearances']:
            assert math.dist((p['position'][0],p['position'][2]),retained['center'])>=p['clearance']+retained['radius']+.3
        assert math.dist((p['position'][0],p['position'][2]),(3159.92992,725.68))>=10+p['clearance']
        for q in placement['objects'][i+1:]:
            assert math.dist((p['position'][0],p['position'][2]),(q['position'][0],q['position'][2]))>=p['clearance']+q['clearance']+.3
    textures={}
    for path in DEST.glob('*.dds'):
        data=path.read_bytes()
        assert data[:4]==b'DDS ' and data[84:88]==b'DXT5'
        h,w,mips=struct.unpack_from('<II',data,12)+struct.unpack_from('<I',data,28)
        assert w==h and mips==int(math.log2(w))+1
        expected=128+sum(max(1,(w//2**m+3)//4)*max(1,(h//2**m+3)//4)*16 for m in range(mips))
        assert len(data)==expected
        textures[path.name]={'size':[w,h],'mips':mips,'bytes':len(data)}
    geometry=json.loads((ROOT/'build_report.json').read_text())
    for model in geometry['landmarks'].values():
        assert hashlib.sha256((MOD/model['path']).read_bytes()).hexdigest()==model['sha256']
    for p in placement['landmarks']:
        lo,hi=p['terrain_range']
        assert -.02501<=p['contact_world_y']-lo<=-.02499
        assert hi-p['contact_world_y']<=.57501
    tris={n:sum(p['triangles'] for p in geometry[n]['parts']) for n in NAMES}
    report={'status':'offline checks pass','meshes':9,'textures':textures,'placements':placement['counts'],
            'total_placed_triangles':sum(tris[p['model']] for p in placement['objects']),
            'triangles_per_model':tris,'source_meshes_unchanged_from_HEAD':originals,
            'retired_skyscraper_files_removed':[str(p.relative_to(MOD)) for p in RETIRED_FILES],
            'source_texture_hashes_unchanged':list(sources),'external_placements_preserved':len(external),
            'unrelated_registry_and_ambient_content_preserved':True,
            'restored_city_palette_pixels':len(palette['changes']),'original_city_mask_sha256':palette['original_sha256'],
            'procedural_cities':'original mask and loader restored; new buildings are standalone ambient entities only',
            'landmark_placement':placement['landmarks'],'landmark_mesh_bytes_preserved':True,
            'runtime':'This validator checks files only. See the infantry_weapons_3d QA runtime report for observed engine behavior.'}
    (ROOT/('verification_preview.json' if preview else 'verification_report.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    main(parser.parse_args().preview)
