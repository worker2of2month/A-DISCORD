"""Own city exports and the terrain placement of static ambient landmarks."""
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import struct
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[3]
DEST=MOD/'gfx/models/buildings/ADISCORD_city'
RETIRED_FILES=tuple(MOD/f'gfx/models/buildings/skyscraper{i}{suffix}'
                    for i in (1,2,3) for suffix in ('.mesh','_diff.dds'))
NAMES=('tower_admin','tower_business','tower_residential',
       'quarter_business','quarter_mixed','quarter_residential',
       'stelander_spire','stelander_twin','stelander_arcology')
START='# BEGIN ADISCORD Vorkensberg city\n'
END='# END ADISCORD Vorkensberg city\n'
TOWER=(3159.92992,725.68)


def convex_hull(points):
    points=sorted(set((round(x,6),round(z,6)) for x,z in points))
    def half(sequence):
        result=[]
        for p in sequence:
            while len(result)>1:
                a,b=result[-2:]
                if (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])>1e-9:break
                result.pop()
            result.append(p)
        return result[:-1]
    return half(points)+half(reversed(points))


def footprint_pixels(outline,x,z):
    polygon=[(a+x,b+z) for a,b in outline]
    axes=[(1,0),(0,1)]+[(b[1]-a[1],a[0]-b[0]) for a,b in zip(polygon,polygon[1:]+polygon[:1])]
    intervals=[(ax,az,min(px*ax+pz*az for px,pz in polygon),max(px*ax+pz*az for px,pz in polygon)) for ax,az in axes]
    for xx in range(math.ceil(min(p[0] for p in polygon)-.5),math.floor(max(p[0] for p in polygon)+.5)+1):
        for zz in range(math.ceil(min(p[1] for p in polygon)-.5),math.floor(max(p[1] for p in polygon)+.5)+1):
            if all(lo-.5*(abs(ax)+abs(az))<=xx*ax+zz*az<=hi+.5*(abs(ax)+abs(az)) for ax,az,lo,hi in intervals):
                yield xx,zz


def height_at(heights,x,z):
    ix,iz=math.floor(x),math.floor(z)
    fx,fz=x-ix,z-iz
    def value(xx,zz):
        return heights.getpixel((xx,heights.height-1-zz))/10
    return ((1-fz)*((1-fx)*value(ix,iz)+fx*value(ix+1,iz))+
            fz*((1-fx)*value(ix,iz+1)+fx*value(ix+1,iz+1)))


def footprint_samples(outline,x,z,yaw):
    angle=math.radians(yaw)
    polygon=[(x+a*math.cos(angle)-b*math.sin(angle),
              z+a*math.sin(angle)+b*math.cos(angle)) for a,b in outline]
    result=set(polygon)
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        count=math.ceil(math.dist(a,b)/.1)
        result.update((a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count) for i in range(count+1))
    for xx in range(math.floor(min(p[0] for p in polygon)*5),math.ceil(max(p[0] for p in polygon)*5)+1):
        for zz in range(math.floor(min(p[1] for p in polygon)*5),math.ceil(max(p[1] for p in polygon)*5)+1):
            point=(xx/5,zz/5)
            if all((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])>=-1e-6
                   for a,b in zip(polygon,polygon[1:]+polygon[:1])):
                result.add(point)
    return sorted(result)


def retained_clearances(landmarks=()):
    rows=[]
    text=clear_old_placements(remove_owned((MOD/'map/ambient_object.txt').read_text()))
    for a,b in spans(text,'type'):
        block=text[a:b]
        kind=re.search(r'type\s*=\s*"([^"]+)"',block)[1]
        radius={'french_city1_entity':1.1,'ADISCORD_congress_entity':2.3}.get(kind)
        if radius is None:continue
        for c,d in spans(block,'object'):
            position=list(map(float,re.search(r'position\s*=\s*\{([^}]+)',block[c:d])[1].split()))
            if kind=='ADISCORD_congress_entity' and landmarks:
                position=next(p['position'] for p in landmarks if p['entity']==kind)
            rows.append({'entity':kind,'center':[position[0],position[2]],'radius':radius})
    return rows


def river_crossing(rivers,samples,margin=2):
    # Include the full source pixel around the river centerline. Rendered banks
    # may extend beyond that pixel, so keep a separate pedestrian setback.
    distance=margin+math.sqrt(.5)
    x0,x1=min(p[0] for p in samples),max(p[0] for p in samples)
    z0,z1=min(p[1] for p in samples),max(p[1] for p in samples)
    for xx in range(math.floor(x0-distance),math.ceil(x1+distance)+1):
        for zz in range(math.floor(z0-distance),math.ceil(z1+distance)+1):
            if rivers.getpixel((xx,rivers.height-1-zz))<=11 and any(math.dist((xx,zz),p)<distance for p in samples):
                return [xx,zz]
    return None


def landmark_plan(heights,provinces,definitions,rivers,geometry):
    baseline=json.loads((ROOT/'integration_baseline.json').read_text())['map/ambient_object.txt']['text']
    registry=(MOD/'gfx/entities/mapitems_custom.gfx').read_text()
    registrations={re.search(r'\bname\s*=\s*"([^"]+)"',block)[1]:block
                   for a,b in spans(registry,'pdxmesh') for block in [registry[a:b]]}
    province_states={}
    for path in (MOD/'history/states').glob('*.txt'):
        text=path.read_text(encoding='utf-8-sig')
        state=int(re.search(r'\bid\s*=\s*(\d+)',text)[1])
        block=re.search(r'\bprovinces\s*=\s*\{([^}]+)',text)
        if block:province_states.update({int(v):state for v in re.findall(r'\d+',block[1])})
    land={tuple(map(int,r[1:4])) for r in csv.reader((MOD/'map/definition.csv').open(),delimiter=';')
          if len(r)>6 and r[0].isdigit() and r[4]=='land'}
    selected=[]
    offsets=sorted((math.hypot(dx,dz),dx,dz) for dx in range(-40,41) for dz in range(-40,41) if math.hypot(dx,dz)<=40)
    for a,b in spans(baseline,'type'):
        block=baseline[a:b]
        entity=re.search(r'type\s*=\s*"([^"]+)"',block)[1]
        name=entity.removeprefix('ADISCORD_').removesuffix('_entity')
        if name not in geometry:continue
        model=geometry[name]
        assert hashlib.sha256((MOD/model['path']).read_bytes()).hexdigest()==model['sha256']
        ambient_scale=float(re.search(r'\bscale\s*=\s*([\d.]+)',block)[1])
        gfx_scale=float(re.search(r'\bscale\s*=\s*([\d.]+)',registrations[f'ADISCORD_{name}_mesh'])[1])
        scale=ambient_scale*gfx_scale
        for index,(c,d) in enumerate(spans(block,'object')):
            obj=block[c:d]
            anchor=list(map(float,re.search(r'position\s*=\s*\{([^}]+)',obj)[1].split()))
            rotation=list(map(float,re.search(r'rotation\s*=\s*\{([^}]+)',obj)[1].split()))
            def transform(point):
                x,y,z=(v*scale for v in point)
                ax,ay,az=map(math.radians,rotation)
                y,z=y*math.cos(ax)-z*math.sin(ax),y*math.sin(ax)+z*math.cos(ax)
                x,z=x*math.cos(ay)+z*math.sin(ay),-x*math.sin(ay)+z*math.cos(ay)
                x,y=x*math.cos(az)-y*math.sin(az),x*math.sin(az)+y*math.cos(az)
                return x,y,z
            corners=[transform(v) for v in itertools.product(*zip(model['minimum'],model['maximum']))]
            lower=[min(v[i] for v in corners) for i in range(3)]
            upper=[max(v[i] for v in corners) for i in range(3)]
            assert abs(transform((0,1,0))[0])+abs(transform((0,1,0))[2])<1e-6,'Tilted landmarks require a 3D support hull'
            outline=convex_hull((p[0],p[2]) for a,b in model['outline'] for p in [transform((a,0,b))])
            radius=max(math.hypot(x,z) for x,z in outline)
            original_province=definitions[provinces.getpixel((round(anchor[0]),provinces.height-1-round(anchor[2])))][0]
            state=province_states[original_province]
            accepted=None
            for distance,dx,dz in offsets:
                x,z=anchor[0]+dx,anchor[2]+dz
                province=definitions[provinces.getpixel((round(x),provinces.height-1-round(z)))][0]
                if province_states.get(province)!=state:continue
                if any(math.dist((x,z),(p['position'][0],p['position'][2]))<radius+p['clearance']+.5 for p in selected):continue
                box=(math.floor(x+lower[0]),heights.height-1-math.ceil(z+upper[2]),
                     math.ceil(x+upper[0])+1,heights.height-math.floor(z+lower[2]))
                colors={provinces.getpixel((xx,provinces.height-1-zz)) for xx,zz in footprint_pixels(outline,x,z)}
                if any(color not in land for color in colors):continue
                if any(province_states.get(definitions[color][0])!=state for color in colors):continue
                bank=(box[0]-2,box[1]-2,box[2]+2,box[3]+2)
                if rivers.crop(bank).getextrema()[0]<=11:continue
                samples=footprint_samples(outline,x,z,0)
                terrain=[height_at(heights,xx,zz) for xx,zz in samples]
                if min(terrain)<9.5 or max(terrain)-min(terrain)>min(.55,(upper[1]-lower[1])*.30):continue
                center=height_at(heights,x,z)
                # Centered legacy meshes have no authored deep foundation.
                # Bury the lowest contact plane and bound the high-side cover.
                y=round(min(terrain)-center-lower[1]-.025,5)
                accepted={'entity':entity,'index':index,'position':[x,y,z],'rotation':rotation,
                          'anchor':anchor,'state':state,'province':province,'move_distance':distance,
                          'terrain_range':[min(terrain),max(terrain)],'center_height':center,
                          'footprint':outline,'footprint_states':[state],
                          'contact_world_y':center+y+lower[1],'clearance':radius,
                          'native_scale':scale,'model_sha256':model['sha256']}
                break
            assert accepted is not None,f'No level, dry site for {entity} {index}'
            selected.append(accepted)
    assert len(selected)==7
    return selected


def ground_landmarks(text,placements):
    for a,b in reversed(list(spans(text,'type'))):
        block=text[a:b]
        kind=re.search(r'type\s*=\s*"([^"]+)"',block)[1]
        rows=[p for p in placements if p['entity']==kind]
        if not rows:continue
        objects=list(spans(block,'object'))
        assert len(objects)==len(rows)
        for index,(c,d) in reversed(list(enumerate(objects))):
            obj=block[c:d]
            xyz=' '.join(f'{v:.5f}' for v in rows[index]['position'])
            obj=re.sub(r'(\bposition\s*=\s*\{)[^}]+',lambda match:match[1]+' '+xyz+' ',obj)
            obj=re.sub(r'[ \t]+(?=\r?$)','',obj,flags=re.M)
            block=block[:c]+obj+block[d:]
        text=text[:a]+block+text[b:]
    return text


def spans(text,key):
    """Balanced named objects; quoted strings and comments do not affect depth."""
    pattern=re.compile(r'\b'+re.escape(key)+r'\s*=\s*\{')
    for match in pattern.finditer(text):
        depth,quoted,comment=1,False,False
        for i in range(match.end(),len(text)):
            c=text[i]
            if comment:
                if c=='\n': comment=False
            elif c=='"': quoted=not quoted
            elif not quoted:
                if c=='#': comment=True
                elif c=='{': depth+=1
                elif c=='}':
                    depth-=1
                    if depth==0:
                        yield match.start(),i+1
                        break
        else:
            raise ValueError(f'Unclosed {key} block')


def remove_owned(text):
    return re.sub(re.escape(START)+r'.*?'+re.escape(END),'',text,flags=re.S).rstrip()+'\n'


def remove_retired_registry(text,kind):
    key='pdxmesh' if kind=='gfx' else 'entity'
    names=({f'skyscraper{i}_mesh' for i in (1,2,3)} if kind=='gfx' else
           {'skyscraper1_entity','skyscraper1_small_entity','skyscraper2_entity',
            'skyscraper2_large_entity','skyscraper3_entity','skyscraper3_small_entity'})
    for start,end in reversed(list(spans(text,key))):
        name=re.search(r'\bname\s*=\s*"([^"]+)"',text[start:end])
        if name and name[1] in names:
            text=text[:start]+text[end:]
    if kind=='gfx':
        for start,end in reversed(list(spans(text,'objectTypes'))):
            block=text[start:end]
            if re.search(r'\bname\s*=\s*"cityblock_mesh"',block):
                text=text[:start]+re.sub(r'(?m)^[ \t]+$', '',block)+text[end:]
    return text


def old_city_object(block):
    position=re.search(r'position\s*=\s*\{([^}]+)',block)
    if not position:return False
    x,_,z=map(float,position[1].split())
    return (3100<=x<=3210 and 680<=z<=770) or (3697<=x<=3777 and 927<=z<=1015)


def clear_old_placements(text):
    for start,end in reversed(list(spans(text,'type'))):
        block=text[start:end]
        kind=re.search(r'type\s*=\s*"([^"]+)"',block)
        if not kind or not kind[1].startswith(('cityblock','skyscraper')):continue
        for a,b in reversed(list(spans(block,'object'))):
            if old_city_object(block[a:b]):block=block[:a]+block[b:]
        if not list(spans(block,'object')):block=''
        else:block='\n'.join(line.rstrip() for line in block.splitlines() if line.strip())
        text=text[:start]+block+text[end:]
    return text.rstrip()+'\n'


def plan():
    from PIL import Image
    old=json.loads((ROOT/'existing_placement.json').read_text())['rows']
    heights=Image.open(MOD/'map/heightmap.bmp')
    provinces=Image.open(MOD/'map/provinces.bmp').convert('RGB')
    rivers=Image.open(MOD/'map/rivers.bmp')
    assert rivers.mode=='P' and rivers.size==heights.size
    rows=list(csv.reader((MOD/'map/definition.csv').open(),delimiter=';'))
    definitions={tuple(map(int,r[1:4])):(int(r[0]),r[6]) for r in rows if len(r)>6 and r[0].isdigit()}
    water={int(r[0]) for r in rows if len(r)>6 and r[0].isdigit() and r[4] in ('sea','lake')}
    geometry=json.loads((ROOT/'build_report.json').read_text())
    foundations={name:geometry[name]['foundation'] for name in NAMES}
    for name,base in foundations.items():
        assert hashlib.sha256((ROOT/f'ADISCORD_city_{name}.mesh').read_bytes()).hexdigest()==base['mesh_sha256'],'Reinspect the exported foundations'
    landmarks=landmark_plan(heights,provinces,definitions,rivers,geometry['landmarks'])
    retained=retained_clearances(landmarks)
    selected=[]
    rejected=[]
    def add(row,name):
        x,_,z=row['position']
        quarter=name.startswith('quarter')
        base=foundations[name]
        yaw=0 if quarter else (0,90,180,270)[len(selected)%4]
        radius=4.9 if quarter else (2.6 if name.startswith('stelander') else 2.25)
        if math.dist((x,z),TOWER)<10.0+radius:
            rejected.append({'position':[x,z],'reason':'Unity Tower plaza'})
            return
        if any(math.dist((x,z),(p['position'][0],p['position'][2]))<radius+p['clearance']+.3 for p in selected):
            rejected.append({'position':[x,z],'reason':'street clearance'})
            return
        if any(math.dist((x,z),p['center'])<radius+p['radius']+.3 for p in retained):
            rejected.append({'position':[x,z],'reason':'retained landmark clearance'})
            return
        samples=footprint_samples(base['outline'],x,z,yaw)
        if name.startswith('stelander') and any(definitions[provinces.getpixel((round(xx),provinces.height-1-round(zz)))][1] not in ('urban','vorkernsberg') for xx,zz in samples):
            rejected.append({'position':[x,z],'reason':'outside urban district'})
            return
        river=river_crossing(rivers,samples)
        if river:
            rejected.append({'position':[x,z],'reason':'river and bank clearance','river_cell':river})
            return
        terrain=[height_at(heights,xx,zz) for xx,zz in samples]
        if any(definitions[provinces.getpixel((round(xx),provinces.height-1-round(zz)))][0] in water for xx,zz in samples):
            rejected.append({'position':[x,z],'reason':'foundation crosses water'})
            return
        if min(terrain)<9.5 or max(terrain)-min(terrain)>min(.45,base['upper']-base['lower']-.15):
            rejected.append({'position':[x,z],'reason':'slope exceeds foundation','height_range':[min(terrain),max(terrain)]})
            return
        # Ambient Y is an offset above the center terrain. The exported plinth
        # top sits just above the highest sample; the lower face stays buried.
        center=height_at(heights,x,z)
        y=round(max(terrain)-center-base['upper']+.01,5)
        support=[center+y+base['lower'],center+y+base['upper']]
        assert support[0]<min(terrain)-.15 and support[1]>=max(terrain)+.0099
        selected.append({'model':name,'position':[x,y,z],'rotation':[0,yaw,0],
                         'terrain_range':[min(terrain),max(terrain)],'clearance':radius,
                         'center_height':center,'foundation_world_range':support,'footprint_samples':len(samples),
                         'original_entity':row['type'],'province':row['province']})
        if 'source_anchor' in row:selected[-1]['source_anchor']=row['source_anchor']
        return True
    for index,row in enumerate(r for r in old if r['vorkensberg'] and r['type'].startswith('skyscraper')):
        add(row,NAMES[index%3])
    blocks=[r for r in old if r['vorkensberg'] and r['type'].startswith('cityblock')]
    blocks.sort(key=lambda r:(r['terrain']!='vorkernsberg',math.dist((r['position'][0],r['position'][2]),TOWER)))
    for index,row in enumerate(blocks):
        distance=math.dist((row['position'][0],row['position'][2]),TOWER)
        kind='quarter_business' if distance<30 else ('quarter_mixed' if index%2 else 'quarter_residential')
        add(row,kind)
    # Fill flat gaps near the existing urban anchors. Limit the search to the
    # established city terrain, keeping the new footprint out of rural land.
    candidates=[]
    for x in range(3110,3203,2):
        for z in range(686,758,2):
            province,terrain=definitions[provinces.getpixel((x,provinces.height-1-z))]
            if terrain not in ('urban','vorkernsberg'):continue
            nearest=min(math.dist((x,z),(r['position'][0],r['position'][2])) for r in blocks)
            if nearest>6.5:continue
            candidates.append((nearest,x,z,province))
    for _,x,z,province in sorted(candidates):
        if sum(r['model'].startswith('quarter') for r in selected)>=26:break
        row={'position':[x,0,z],'province':province,'type':'urban infill'}
        distance=math.dist((x,z),TOWER)
        kind='quarter_business' if distance<30 else ('quarter_mixed' if (x+z)%4 else 'quarter_residential')
        add(row,kind)
    for index,row in enumerate(r for r in old if not r['vorkensberg'] and 3697<=r['position'][0]<=3777):
        if add(row,NAMES[6+index%3]):continue
        # Old near-shore placements can put the wider new foundations in water.
        # Move within the same immediate district to a dry, level site.
        candidates=sorted((math.hypot(dx,dz),dx,dz) for dx in range(-12,13) for dz in range(-12,13) if 0<math.hypot(dx,dz)<=12)
        for _,dx,dz in candidates:
            x,z=row['position'][0]+dx,row['position'][2]+dz
            province,terrain=definitions[provinces.getpixel((round(x),provinces.height-1-round(z)))]
            if terrain not in ('urban','vorkernsberg'):continue
            shifted={**row,'position':[x,0,z],'province':province,'source_anchor':row['position']}
            if add(shifted,NAMES[6+index%3]):break
    return {'height_mode':'terrain-relative Y; bilinear heightmap / 10, exported foundation and yaw',
            'foundation_top_clearance':.01,'foundation_burial_margin':.15,'retained_clearances':retained,
            'river_bank_setback':2,'maximum_foundation_exposure':.46,
            'landmarks':landmarks,
            'original_city_placements':sum(r['vorkensberg'] for r in old),
            'replaced_stelander_placements':5,'preserved_external_placements':1,
            'tower_clearance_radius':10.0,'objects':selected,'rejected':rejected,
            'counts':dict(Counter(p['model'] for p in selected))}


def registry(kind):
    if kind=='gfx':
        entries=[(n,n,1) for n in NAMES]
        return 'objectTypes = {\n'+''.join(f'\tpdxmesh = {{\n\t\tname = "ADISCORD_city_{alias}_mesh"\n\t\tfile = "gfx/models/buildings/ADISCORD_city/ADISCORD_city_{n}.mesh"\n\t\tscale = {scale}\n\t\tcull_distance = 600\n\t}}\n' for alias,n,scale in entries)+'}\n'
    return ''.join(f'entity = {{\n\tname = "ADISCORD_city_{n}_entity"\n\tpdxmesh = "ADISCORD_city_{n}_mesh"\n}}\n' for n in NAMES)


def restore_city_palette():
    data=bytearray((MOD/'map/cities.bmp').read_bytes())
    manifest=json.loads((ROOT/'city_palette_manifest.json').read_text())
    for change in manifest['changes']:
        assert data[change['offset']] in (change['before'],3,4)
        data[change['offset']]=change['before']
    return bytes(data),manifest


def ambient(report):
    result=''
    for name in NAMES:
        group=[r for r in report['objects'] if r['model']==name]
        if not group:continue
        result+=f'type = {{\n\ttype = "ADISCORD_city_{name}_entity"\n\tuse_animation = no\n\tscale = 1\n'
        for i,row in enumerate(group):
            xyz=' '.join(f'{v:.5f}' for v in row['position'])
            rot=' '.join(str(v) for v in row['rotation'])
            result+=f'\tobject = {{\n\t\tname = "ADISCORD_city_{name}_{i:02d}"\n\t\tposition = {{ {xyz} }}\n\t\trotation = {{ {rot} }}\n\t}}\n'
        result+='}\n'
    return result


def outputs():
    report=plan()
    files={DEST/f.name:f.read_bytes() for f in sorted(ROOT.glob('City_*.dds'))}
    files.update({DEST/f'ADISCORD_city_{n}.mesh':(ROOT/f'ADISCORD_city_{n}.mesh').read_bytes() for n in NAMES})
    for kind in ('gfx','asset'):
        path=MOD/f'gfx/entities/mapitems_custom.{kind}'
        files[path]=(remove_retired_registry(remove_owned(path.read_text()),kind)+'\n'+START+registry(kind)+END).encode()
    path=MOD/'map/ambient_object.txt'
    files[path]=(ground_landmarks(clear_old_placements(remove_owned(path.read_text())),report['landmarks'])+'\n'+START+ambient(report)+END).encode()
    data,manifest=restore_city_palette()
    files[MOD/'map/cities.bmp']=data
    path=MOD/'map/cities.txt'
    baseline=json.loads((ROOT/'integration_baseline.json').read_text())['map/cities.txt']['text']
    remaining=remove_owned(path.read_text())
    files[path]=(baseline if remaining==remove_owned(baseline) else remaining).encode()
    report['city_palette_manifest']=manifest
    return files,report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    files,report=outputs()
    changed=[str(p.relative_to(MOD)) for p,data in files.items() if not p.is_file() or p.read_bytes()!=data]
    obsolete=[p for p in RETIRED_FILES if p.is_file()]
    if args.apply:
        for path,data in files.items():
            if str(path.relative_to(MOD)) in changed:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
        for path in obsolete:
            assert path.resolve().parent==(MOD/'gfx/models/buildings').resolve()
            path.unlink()
        (ROOT/'city_palette_manifest.json').write_text(json.dumps(report.pop('city_palette_manifest'),indent=2))
        (ROOT/'placement_report.json').write_text(json.dumps(report,indent=2))
        (ROOT/'package_report.json').write_text(json.dumps({str(p.relative_to(MOD)):{'sha256':hashlib.sha256(d).hexdigest(),'bytes':len(d)} for p,d in files.items()},indent=2))
    print(json.dumps({'files':len(files),'changed':changed,'retired_files':list(map(lambda p:str(p.relative_to(MOD)),obsolete)),
                      'counts':report['counts'],'rejected':len(report['rejected']),'applied':args.apply}))
    if args.check and (changed or obsolete):raise SystemExit(1)


if __name__=='__main__':
    main()
