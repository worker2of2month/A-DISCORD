"""Inspect the existing city meshes at their current map scales."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[3]
sys.path.insert(0,str(ROOT.parent/'STP_regulars'))
from export_verify import pdx,pdx_data,preview_gloss

bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.world=bpy.data.worlds.new('City reference studio')
scene.world.color=(.15,.15,.15)
report={}
models=[('city_4_04',2.6),('city_4_03',1.6),('western_buildings_4_02',1.6)]
landmarks='--landmarks' in sys.argv
if landmarks:
    models=[('wasterland_special/ADISCORD_factory',8),('wasterland_special/ADISCORD_reactor',10),
            ('wasterland_special/ADISCORD_reactor_2',10),('stelander_special/ADISCORD_congress',3)]
for index,(name,scale) in enumerate(models):
    path=MOD/f'gfx/models/buildings/{name}.mesh'
    tree=pdx_data.read_meshfile(str(path))
    data=[]
    for shape in tree.find('object'):
        for mesh in shape.findall('mesh'):
            d=pdx_data.PDXData(mesh)
            data.append({'vertices':len(d.p)//3,'triangles':len(d.tri)//3,
                         'material':{k:getattr(d.material,k,None) for k in ('shader','diff','n','spec')}})
    previous=set(scene.objects)
    pdx.import_meshfile(str(path),join_materials=False)
    objects=[o for o in scene.objects if o not in previous and o.type=='MESH']
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    report[name]={'scale':scale,'min':list(low),'max':list(high),'map_size':list((high-low)*scale),'parts':data}
    for obj in objects:
        obj.scale*=scale
        obj.location+=Vector(((index%3-1)*32,(index//3)*28,-low.z*scale))
        for material in obj.data.materials:
            preview_gloss(material)
    bpy.ops.object.text_add(location=((index%3-1)*32-8,(index//3)*28-10,.1))
    label=bpy.context.object
    label.data.body=name
    label.data.size=1.5
    label.rotation_euler=(0,0,0)
target=Vector((0,10,6))
bpy.ops.object.camera_add(location=(72,-104,85))
camera=bpy.context.object
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=115
scene.camera=camera
for loc,power in [((20,-40,100),160000),((-70,50,80),120000)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    lamp=bpy.context.object
    lamp.data.energy=power
    lamp.data.size=75
scene.render.engine='CYCLES'
scene.cycles.samples=12
scene.render.resolution_x=1200
scene.render.resolution_y=780
scene.render.resolution_percentage=100
(ROOT/('landmark_models.json' if landmarks else 'existing_models.json')).write_text(json.dumps(report,indent=2))
scene.render.filepath=str(ROOT/('landmark_models.png' if landmarks else 'existing_models.png'))
bpy.ops.render.render(write_still=True)
print(json.dumps(report))
