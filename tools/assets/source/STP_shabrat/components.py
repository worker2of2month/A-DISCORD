import bpy,json
from pathlib import Path
ROOT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'STP.blend'))
o=next(o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render)
p=list(range(len(o.data.vertices)))
def find(a):
    while p[a]!=a: a=p[a]
    return a
for e in o.data.edges:
    a,b=map(find,e.vertices);p[a]=b
groups={}
for v in o.data.vertices: groups.setdefault(find(v.index),[]).append(v.index)
r=[]
for inds in groups.values():
    coords=[o.data.vertices[i].co for i in inds]
    r.append(dict(n=len(inds),ids=inds,min=[min(v[i] for v in coords) for i in range(3)],max=[max(v[i] for v in coords) for i in range(3)]))
(ROOT/'components.json').write_text(json.dumps(r))
print([(x['n'],x['min'],x['max']) for x in r])
