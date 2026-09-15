"""Diagnose culling on a closed primitive through the city mesh builder."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build_city import Builder,MATERIALS,NAMES,model,pdx

def triangle_key(points):
    return tuple(sorted(tuple(round(x,5) for x in p) for p in points))

bpy.ops.wm.read_factory_settings(use_empty=True)
mats=[bpy.data.materials.new(n) for n in MATERIALS]
report={}
for name in NAMES:
    builder=model(name)
    assert all(0<=v<=1 for face in builder.uvs for uv in face for v in uv),name+': UV depends on texture repeat'
    obj=builder.object(mats)
    source_normals={}
    for face in builder.faces:
        a,b,c=(Vector(builder.vertices[i]) for i in face[:3])
        normal=(b-a).cross(c-a).normalized()
        for i in face:source_normals[i]=normal
    assert len(obj.data.vertices)==len(builder.vertices)
    assert all((v.co-Vector(source)).length<1e-5 for v,source in zip(obj.data.vertices,builder.vertices))
    inverted=[{'face':p.index,'normal':list(p.normal),'center':list(p.center)}
              for p in obj.data.polygons if p.normal.dot(source_normals[p.vertices[0]])<-.9]
    report[name]={'triangles':len(obj.data.polygons),'inward_triangles':len(inverted),'examples':inverted[:8]}
    if '--native' in sys.argv:
        expected={triangle_key(obj.data.vertices[i].co for i in p.vertices):p.normal.copy()
                  for p in obj.data.polygons}
        before=set(bpy.context.scene.objects)
        pdx.import_meshfile(str(ROOT/f'ADISCORD_city_{name}.mesh'),join_materials=False)
        checked=0
        for native in set(bpy.context.scene.objects)-before:
            if native.type!='MESH':continue
            for face in native.data.polygons:
                points=[native.matrix_world@native.data.vertices[i].co for i in face.vertices]
                normal=(points[1]-points[0]).cross(points[2]-points[0]).normalized()
                assert normal.dot(expected[triangle_key(points)])>.99,(name,points)
                checked+=1
        assert checked==len(obj.data.polygons)
        report[name]['native_roundtrip_triangles']=checked
(ROOT/'orientation_probe.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
assert all(not r['inward_triangles'] for r in report.values()),'City mesh contains reversed authored face winding'
