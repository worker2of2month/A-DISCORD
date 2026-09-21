"""Render installed TFR props as read-only references alongside our current prop."""
import bpy
import hashlib
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from export_weapons import pdx,preview_gloss,DEST

TFR=Path(r'Z:/SteamLibrary/steamapps/workshop/content/394360/3350890356/gfx/models/units')
OUTPUT=ROOT/'tfr_reference'
OUTPUT.mkdir(exist_ok=True)
FILES=[('TFR / AR15',TFR/'AR15.mesh'),('TFR / AK12',TFR/'AK12.mesh'),
       ('TFR / HK416',TFR/'GER_HK416.mesh'),('TFR / M14',TFR/'weapon_USA_rifle_M14.mesh'),
       ('A-Discord / current 3',DEST/'infantry_3.mesh')]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
direction=Vector((8,-3,2.5)).normalized()
rotation=(-direction).to_track_quat('-Z','Y')
right=rotation@Vector((1,0,0));up=rotation@Vector((0,1,0))
textmat=bpy.data.materials.new('Caption')
textmat.use_nodes=True
nodes=textmat.node_tree.nodes
nodes.clear()
em=nodes.new('ShaderNodeEmission');em.inputs[0].default_value=(.85,.87,.9,1)
out=nodes.new('ShaderNodeOutputMaterial');textmat.node_tree.links.new(em.outputs[0],out.inputs[0])
report=[]
for index,(label,path) in enumerate(FILES):
    previous=set(bpy.data.objects)
    pdx.import_meshfile(str(path),join_materials=False)
    added=set(bpy.data.objects)-previous
    meshes=[o for o in added if o.type=='MESH' and not any(m.get(pdx.PDX_SHADER)=='Collision' for m in o.data.materials)]
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    factor=5.3/max(hi-lo);center=(lo+hi)/2
    offset=up*(5.5-index*2.75)
    triangles=0
    for obj in meshes:
        data=bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        data.transform(obj.matrix_world)
        for vertex in data.vertices:vertex.co=(vertex.co-center)*factor+offset
        for mat in data.materials:
            if mat.use_nodes:preview_gloss(mat)
        copy=bpy.data.objects.new(label,data);scene.collection.objects.link(copy)
        triangles+=sum(len(p.vertices)-2 for p in data.polygons)
    for obj in added:bpy.data.objects.remove(obj,do_unlink=True)
    curve=bpy.data.curves.new('Caption','FONT');curve.body=label;curve.size=.22
    text=bpy.data.objects.new(label,curve);scene.collection.objects.link(text)
    text.location=offset-right*2.7+up*1.07+direction*.5;text.rotation_euler=rotation.to_euler();curve.materials.append(textmat)
    report.append({'label':label,'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                   'native_dimensions':list(hi-lo),'display_normalization':factor,'triangles':triangles})
bpy.ops.object.camera_add(location=direction*30)
cam=bpy.context.object;cam.rotation_euler=rotation.to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=14.2;scene.camera=cam
for loc,power in ((direction*12+up*8+right*4,6500),(direction*8-right*9,4000)):
    bpy.ops.object.light_add(type='AREA',location=loc)
    light=bpy.context.object;light.data.energy=power;light.data.size=14
    light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
scene.world=bpy.data.worlds.new('Reference studio');scene.world.color=(.06,.07,.08)
scene.render.engine='CYCLES';scene.cycles.samples=24
scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1100;scene.render.resolution_y=1700
scene.render.resolution_percentage=100
scene.render.filepath=str(OUTPUT/'TFR_comparison.png')
bpy.ops.render.render(write_still=True)
(OUTPUT/'reference_manifest.json').write_text(json.dumps(report,indent=2))
