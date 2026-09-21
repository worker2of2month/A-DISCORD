"""Build a skinned Shabrat infantry prototype on the existing STP body rig."""
import bpy, bmesh, json, math, sys, inspect
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from infantry_polish import tailored_fabric, curve_carrier, fitted_head_cloth, fitted_armband, curved_guard
sys.path.insert(0, r'C:\Users\Admin\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default')
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
source=inspect.getsource(pdx.create_shader).replace('    new_shader.shadow_method = "CLIP"','').replace('    new_shader.blend_method = "CLIP"','')
exec(compile(source,'<Blender 5 material compatibility>','exec'),pdx.__dict__)

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'STP.blend'))
scene=bpy.context.scene
body=next(o for o in scene.objects if o.type=='MESH' and not o.hide_render)
rig=next(o for o in scene.objects if o.type=='ARMATURE')
body.name='Shabrat_body'; body.data.name='Shabrat_bodyShape'
parts=json.loads((ROOT/'components.json').read_text())
hat_ids={i for part in parts if part['min'][2]>6.94 for i in part['ids']}
bm=bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[bm.verts[i] for i in hat_ids],context='VERTS')
bm.to_mesh(body.data); bm.free()
material=body.data.materials[0]
albedo=bpy.data.images.load(str(ROOT/'Shabrat_body_diffuse.dds'),check_existing=True)
bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
bsdf.inputs['Base Color'].links[0].from_node.image=albedo
material.name='Shabrat_body_material'
for n in material.node_tree.nodes:
    if n.type=='TEX_IMAGE' and n.image and '__normal' in n.image.name:
        n.image=bpy.data.images.load(str(ROOT/'Shabrat_body_normal.dds'),check_existing=True)
    if n.type=='TEX_IMAGE' and n.image and '__specular' in n.image.name:
        n.image=bpy.data.images.load(str(ROOT/'Shabrat_body_specular.dds'),check_existing=True)

def fabric(name,color,roughness=.82,noise=.12):
    m=bpy.data.materials.new(name);m.use_nodes=True
    n=m.node_tree.nodes; l=m.node_tree.links; s=n.get('Principled BSDF')
    s.inputs['Roughness'].default_value=roughness
    tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=60;tex.inputs['Detail'].default_value=2
    ramp=n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[1].position=.85
    ramp.color_ramp.elements[0].color=tuple(c*(1-noise) for c in color)+(1,)
    ramp.color_ramp.elements[1].color=tuple(min(1,c*(1+noise)) for c in color)+(1,)
    l.new(tex.outputs['Fac'],ramp.inputs[0])
    ao=n.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=.15;ao.samples=16
    l.new(ramp.outputs['Color'],ao.inputs['Color']);l.new(ao.outputs['Color'],s.inputs['Base Color'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.16;bump.inputs['Distance'].default_value=.015
    l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],s.inputs['Normal'])
    return m

coyote=fabric('Canvas / field sand',(.24,.205,.14))
dark=fabric('Webbing / graphite',(.065,.073,.078))
cloth=fabric('Scarf / faded stone',(.29,.305,.29))
knit=fabric('Cap / charcoal knit',(.055,.065,.075),noise=.3)
ochre=fabric('Recognition / ochre tape',(.46,.335,.13))
ivory=fabric('Recognition / linen',(.62,.60,.50))
metal=fabric('Clips / dark alloy',(.11,.125,.13),.48,.05)
gear=[]

def finish(o,name,mat,bone):
    o.name=name;o.data.materials.append(mat)
    if not o.vertex_groups:
        vg=o.vertex_groups.new(name=bone);vg.add(list(range(len(o.data.vertices))),1,'REPLACE')
    mod=o.modifiers.new('Infantry armature','ARMATURE');mod.object=rig
    gear.append(o)
    return o

def box(name,loc,scale,mat,bone='back_mid',bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Soft stitched edges','BEVEL');mod.width=bevel;mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if mat == coyote and min(scale) > .12:
        tailored_fabric(o)
    if name in ('Knee protector','Knee face'):
        curved_guard(o)
    if loc[1] < -.78 and 4.45 < loc[2] < 5.7:
        o.location.y += .16*(loc[0]/.8)**2
    return finish(o,name,mat,bone)

def mesh(name,verts,faces,mat,bone):
    d=bpy.data.meshes.new(name);d.from_pydata(verts,[],faces);d.update()
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o)
    return finish(o,name,mat,bone)

def ring_surface(name,rings,mat,bone,segments=20,cap=False):
    # Each ring: radius x/y, center y, z; optional front-to-back height offset.
    verts=[]
    for rx,ry,cy,z,tilt in rings:
        for i in range(segments):
            a=2*math.pi*i/segments
            verts.append((rx*math.cos(a),cy+ry*math.sin(a),z+tilt*math.sin(a)))
    faces=[]
    for j in range(len(rings)-1):
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    if cap: faces.append(tuple(range((len(rings)-1)*segments,len(rings)*segments)))
    o=mesh(name,verts,faces,mat,bone)
    for p in o.data.polygons:p.use_smooth=True
    return o

ring_surface('Soft field cap',[(.407,.47,-.08,6.965,0),(.435,.49,-.08,7.035,0),(.42,.47,-.07,7.13,0),(.32,.36,-.05,7.29,0),(.11,.15,-.04,7.36,0)],knit,'head',cap=True)
ring_surface('Turned cap cuff',[(.425,.487,-.08,6.96,0),(.44,.502,-.08,7.055,0),(.424,.484,-.08,7.08,0)],dark,'head')
fitted_head_cloth(body, mesh, cloth, 'Wrapped face scarf', loose=True)
mesh('Scarf folded tail',[(-.25,-.46,6.2),(.27,-.46,6.2),(.22,-.69,5.90),(.04,-.73,5.72),(-.19,-.69,5.87)],[(0,1,2,3,4)],cloth,'head')

# Chest carrier: clipped shoulder corners and a tapered lower edge.
outline=[(-.66,4.48),(.66,4.48),(.72,5.38),(.47,5.74),(-.47,5.74),(-.72,5.38)]
verts=[(x,y,z) for y in (-.755,-.58) for x,z in outline]
faces=[tuple(reversed(range(6))),tuple(range(6,12))]+[(i,(i+1)%6,(i+1)%6+6,i+6) for i in range(6)]
curve_carrier(mesh('Chest carrier',verts,faces,coyote,'back_mid'))
box('Rear carrier',(0,.535,5.1),(1.15,.24,1.23),coyote)
for x in (-.49,.49):
    o=mesh('Shoulder harness',[(x-.11,-.73,5.51),(x+.11,-.73,5.51),(x+.11,-.27,5.99),(x-.11,-.27,5.99),(x+.11,.34,5.97),(x-.11,.34,5.97),(x+.11,.69,5.47),(x-.11,.69,5.47)],[(0,1,2,3),(3,2,4,5),(5,4,6,7)],dark,'back_mid')
    box('Harness keeper',(x,-.79,5.61),(.24,.07,.13),metal,bevel=.018)
for x in (-.43,0,.43):
    box('Magazine pouch',(x,-.855,4.75),(.36,.24,.57),coyote,bevel=.045)
    box('Pouch lid',(x,-1.005,4.985),(.37,.055,.155),coyote,bevel=.02)
    box('Pouch pull',(x,-1.04,4.93),(.075,.03,.17),dark,bevel=.01)
for z in (5.19,5.35):
    box('Chest webbing',(0,-.858,z),(1.02,.027,.048),dark,bevel=.008)
box('Field radio',(-.55,-.855,5.42),(.19,.19,.36),dark,bevel=.025)
box('Radio aerial',(-.55,-.84,5.79),(.025,.025,.48),dark,bevel=.006)
box('Utility satchel',(.88,.19,4.12),(.41,.56,.64),coyote,'Hip',.06)
box('Satchel flap',(.90,-.105,4.31),(.41,.045,.21),dark,'Hip',.02)
box('Small back pack',(0,.86,5.02),(.88,.53,.93),coyote,bevel=.09)
box('Back pack lid',(0,1.15,5.29),(.88,.06,.24),dark,bevel=.025)
for x in (-.28,.28):box('Back pack strap',(x,1.16,4.97),(.105,.06,.71),dark)
for side in (-1,1):
    bone='LeftLeg' if side==1 else 'RightLeg'
    box('Knee protector',(side*.68,-.325,2.04),(.39,.19,.53),dark,bone,.075)
    box('Knee face',(side*.68,-.439,2.06),(.26,.038,.29),coyote,bone,.04)

bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.295,depth=.18,location=(1.13,.125,5.53))
o=bpy.context.object;o.rotation_euler=Vector((.79,.05,-.63)).to_track_quat('Z','Y').to_euler()
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
fitted_armband(o,body)
finish(o,'Ochre armband',ochre,'LeftArm')
for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
for x in (1.07,1.2):
    o=box('Armband recognition stitch',(x,-.205,5.52),(.055,.025,.16),ivory,'LeftArm',.004)
    o.rotation_euler.y=.65

# The additions share one texture atlas and retain their rigid bone assignments.
bpy.ops.object.select_all(action='DESELECT')
for o in gear:o.select_set(True)
bpy.context.view_layer.objects.active=gear[0]
bpy.ops.object.join()
equipment=bpy.context.object;equipment.name='Shabrat_equipment';equipment.data.name='Shabrat_equipmentShape'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(island_margin=.025)
bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new('Shabrat_gear_diffuse',1024,1024,alpha=False)
for m in equipment.data.materials:
    node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
    m.node_tree.nodes.active=node
scene.render.engine='CYCLES';scene.cycles.samples=8
scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False;scene.render.bake.use_pass_color=True;scene.render.bake.margin=12
bpy.ops.object.bake(type='DIFFUSE')
image.filepath_raw=str(ROOT/'Shabrat_gear_diffuse.png');image.file_format='PNG';image.save()

# Save the editable source with procedural materials before preparing export.
scene.cycles.samples=40
scene.render.resolution_x=1000;scene.render.resolution_y=1100
scene.view_settings.view_transform='AgX'
for light in bpy.data.lights:light.energy*=.55
scene.world.color=(.12,.12,.12)
scene.render.filepath=str(ROOT/'Shabrat_front.png')
target=Vector((0,-.06,3.67));cam=scene.camera
cam.location=(8,-18,7.5);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=8.7
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Shabrat_rebel.blend'))
bpy.ops.render.render(write_still=True)
cam.location=(-8,18,7.5);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(ROOT/'Shabrat_back.png')
bpy.ops.render.render(write_still=True)
report={'body_vertices':len(body.data.vertices),'body_triangles':sum(len(p.vertices)-2 for p in body.data.polygons),'gear_vertices':len(equipment.data.vertices),'gear_triangles':sum(len(p.vertices)-2 for p in equipment.data.polygons),'bones':len(rig.data.bones),'unweighted_vertices':{o.name:sum(not v.groups for v in o.data.vertices) for o in (body,equipment)}}
(ROOT/'build_report.json').write_text(json.dumps(report,indent=2))
