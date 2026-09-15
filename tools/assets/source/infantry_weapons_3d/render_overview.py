"""Render all eight shipped meshes at the same scale in a single Blender scene."""
import bpy
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from export_weapons import DEST, pdx, preview_gloss

bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
direction=Vector((8,-5,3)).normalized()
rotation=(-direction).to_track_quat('-Z','Y')
right=rotation@Vector((1,0,0))
up=rotation@Vector((0,1,0))
names=('ОВ-40 / ОВ-56','АВ-63 «Рёв»','АВ-68 «Срез»','АВ-70 «Контур»',
       'АВ-78 «Клык»','АВ-83 «Призма»','АВ-93 «Игла»','ИСК-00 «Предел»')
font=bpy.data.fonts.load('C:/Windows/Fonts/arial.ttf')
textmat=bpy.data.materials.new('Caption')
textmat.use_nodes=True
nodes=textmat.node_tree.nodes
nodes.clear()
emission=nodes.new('ShaderNodeEmission')
emission.inputs[0].default_value=(.8,.84,.87,1)
output=nodes.new('ShaderNodeOutputMaterial')
textmat.node_tree.links.new(emission.outputs[0],output.inputs[0])

def caption(text,position,size):
    data=bpy.data.curves.new('Caption','FONT')
    data.body=text
    data.font=font
    data.size=size
    obj=bpy.data.objects.new(text,data)
    scene.collection.objects.link(obj)
    obj.location=position
    obj.rotation_euler=rotation.to_euler()
    data.materials.append(textmat)

for level,name in enumerate(names):
    previous=set(bpy.data.objects)
    pdx.import_meshfile(str(DEST/f'infantry_{level}.mesh'))
    added=set(bpy.data.objects)-previous
    obj=next(o for o in added if o.type=='MESH')
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    mesh.transform(obj.matrix_world)
    for mat in mesh.materials:
        preview_gloss(mat)
    for item in added:
        bpy.data.objects.remove(item,do_unlink=True)
    static=bpy.data.objects.new(f'Generation {level}',mesh)
    scene.collection.objects.link(static)
    center=right*((level%2)*6.8-3.4)+up*(4.55-(level//2)*3.1)
    static.location=center-Vector((0,-.8,.2))
    caption(f'{level+1:02d}   {name}',center-right*2.75+up*.95+direction*.5,.25)

caption('A-DISCORD  /  ОБЩЕЕ ПЕХОТНОЕ ОРУЖИЕ',right*-6.15+up*6.2,.33)
caption('Экспортированные модели • единый масштаб • Blender, не HOI4',right*-6.15-up*6.7,.19)
bpy.ops.object.camera_add(location=direction*30)
cam=bpy.context.object
cam.rotation_euler=rotation.to_euler()
cam.data.type='ORTHO'
cam.data.ortho_scale=14.6
scene.camera=cam
for loc,power in ((direction*12+up*8+right*4,6500),(direction*8-right*9,4000)):
    bpy.ops.object.light_add(type='AREA',location=loc)
    light=bpy.context.object
    light.data.energy=power
    light.data.size=14
    light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
scene.world=bpy.data.worlds.new('Overview studio')
scene.world.color=(.06,.07,.08)
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1400
scene.render.resolution_y=1400
scene.render.resolution_percentage=100
scene.render.filepath=str(ROOT/'weapon_progression.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'weapon_progression.blend'))
bpy.ops.render.render(write_still=True)
