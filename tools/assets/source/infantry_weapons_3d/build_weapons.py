"""Author independent game-scale weapons and short bolt/recoil animation clips."""
import bmesh
import bpy
import inspect
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).parent
sys.path.insert(0,str(Path.home()/'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
source=inspect.getsource(pdx.create_shader)
for line in ('    new_shader.shadow_method = "CLIP"','    new_shader.blend_method = "CLIP"'):
    source=source.replace(line,'')
exec(compile(source,'<Blender 5 material compatibility>','exec'),pdx.__dict__)


def build_animations(level, rig):
    scene=bpy.context.scene
    scene.frame_start=1
    scene.frame_end=79
    scene.render.fps=30
    bpy.context.view_layer.objects.active=rig
    clips={}
    # Native attack starts at 1.15 s for the bolt rifle, 0.5 s for automatics.
    # Support fire starts immediately; the bolt rifle ejects its case later.
    for suffix,offset in (('support',0),('fire',35 if level==0 else 15),('idle',0)):
        rig.animation_data_clear()
        shots=(offset+1,) if level==0 else tuple(offset+x for x in (1,4,7))
        ejections=(37 if suffix=='support' else 67,) if level==0 else shots
        if suffix=='idle':
            shots=ejections=()
        bolt=rig.pose.bones['bolt']
        root=rig.pose.bones['weapon_root']
        for frame in range(1,80):
            bolt.location=(0,.10 if frame in ejections else 0,0)
            root.location=(0,.035 if frame in shots else 0,0)
            bolt.keyframe_insert('location',frame=frame)
            root.keyframe_insert('location',frame=frame)
        scene.frame_set(1)
        pdx.export_animfile(str(ROOT/f'infantry_{level}_{suffix}.anim'),frame_start=1,frame_end=79)
        clips[suffix]={'fire_frames':shots,'ejection_frames':ejections}
    return clips


def build(level):
    label=f"infantry_{level}"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.object.armature_add()
    rig=bpy.context.object
    rig.name=label+'_rig'
    bpy.ops.object.mode_set(mode='EDIT')
    root=rig.data.edit_bones[0]
    root.name='weapon_root'
    root.head=(0,0,0)
    root.tail=(0,1,0)
    bolt=rig.data.edit_bones.new('bolt')
    bolt.head=(0,-.48,.45)
    bolt.tail=(0,.02,.45)
    bolt.parent=root
    bpy.ops.object.mode_set(mode='OBJECT')

    sys.path.insert(0,str(ROOT))
    from weapon_materials import material as mat
    metal=mat('Parkerized receiver',(.058,.064,.069),.55,'steel')
    edge=mat('Hardware steel',(.115,.123,.13),.65,'steel')
    grip=mat('Grip polymer',(.042,.045,.042),0,'polymer')
    furniture=mat('Field furniture',[(.17,.135,.10),(.15,.115,.081),(.065,.072,.060),(.066,.074,.059),(.145,.135,.096),(.068,.083,.092),(.073,.085,.087),(.080,.092,.10)][level],0,'wood' if level<2 else ('polymer' if level<5 else 'ceramic'))
    lens=mat('Optical glass',(.025,.13,.16),.30)
    recess=mat('Vent recesses',(.009,.011,.012))
    parts=[]

    def finish(obj,name,material,bone='weapon_root'):
        obj.name=name
        obj.data.materials.append(material)
        obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        obj.modifiers.new('Weapon rig','ARMATURE').object=rig
        parts.append(obj)
        return obj

    def box(name,loc,size,material,bevel=.02,bone='weapon_root'):
        bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
        obj=bpy.context.object
        obj.scale=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        if bevel:
            mod=obj.modifiers.new('Machined bevel','BEVEL')
            mod.width=bevel
            mod.segments=2
            bpy.ops.object.modifier_apply(modifier=mod.name)
        return finish(obj,name,material,bone)

    def profile(name,outline,width,material):
        verts=[(x,y,z) for x in (-width/2,width/2) for y,z in outline]
        n=len(outline)
        faces=[tuple(reversed(range(n))),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata(verts,[],faces)
        mesh.update()
        bm=bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        obj=bpy.data.objects.new(name,mesh)
        scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True)
        mod=obj.modifiers.new('Profile edge rounding','BEVEL')
        mod.width=min(.038,width*.18)
        mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return finish(obj,name,material)

    def cylinder(name,loc,radius,length,material):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=length,location=loc,rotation=(math.pi/2,0,0))
        obj=bpy.context.object
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        return finish(obj,name,material)

    sys.path.insert(0,str(ROOT))
    from weapon_geometry import build_geometry
    muzzle_y=build_geometry(level,box,profile,cylinder,finish,metal,edge,grip,furniture,lens,recess)

    def fit(point):
        x,y,z=point
        # Hand contact locations stay fixed along the weapon axis. Furniture
        # becomes narrower while the exposed bore and optics retain roundness.
        def smooth(a,b,value):
            t=max(0,min(1,(value-a)/(b-a)))
            return t*t*(3-2*t)
        stock=smooth(.12,.30,y)*(1-smooth(.50,.62,z))
        forearm=smooth(-2.50,-2.35,y)*(1-smooth(-1.25,-1.10,y))*(1-smooth(.56,.66,z))
        grip=smooth(-.18,-.08,y)*(1-smooth(.29,.40,y))*(1-smooth(.25,.35,z))
        x *= .84-(.84-(.59 if level == 0 else .63))*max(stock,forearm,grip)
        if y > .65:
            y = .65+(y-.65)*.82
        if y < -2.48:
            y = -2.48+(y+2.48)*(.72 if level == 1 else .88)
        return Vector((x,y,z))

    for obj in parts:
        matrix=obj.matrix_world.copy()
        inverse=matrix.inverted()
        for vertex in obj.data.vertices:
            vertex.co=inverse@fit(matrix@vertex.co)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    weapon=bpy.context.object
    weapon.name=label
    weapon.data.name=label+'Shape'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bm=bmesh.new()
    bm.from_mesh(weapon.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.to_mesh(weapon.data)
    bm.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    image=bpy.data.images.new(label+'_diffuse',512,512,alpha=False)
    for material in weapon.data.materials:
        node=material.node_tree.nodes.new('ShaderNodeTexImage')
        node.image=image
        material.node_tree.nodes.active=node
    scene.render.engine='CYCLES'
    scene.cycles.samples=24
    scene.render.bake.use_pass_direct=False
    scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True
    scene.render.bake.margin=8
    bpy.ops.object.bake(type='DIFFUSE')
    image.filepath_raw=str(ROOT/f'{label}_diffuse.png')
    image.file_format='PNG'
    image.save()
    for name,loc in (('muzzle',(0,muzzle_y,.43)),('cartridge',(.20,-.61,.49))):
        bpy.ops.object.empty_add(type='PLAIN_AXES',location=fit(loc))
        bpy.context.object.name=name
    clips=build_animations(level,rig)
    bpy.ops.object.camera_add(location=(5,-4,2.7))
    cam=bpy.context.object
    target=Vector((0,-.80,.20))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO'
    cam.data.ortho_scale=6.5
    scene.camera=cam
    for loc,energy,size in (((3,-2,5),650,5),((-2,0,3),450,4)):
        bpy.ops.object.light_add(type='AREA',location=loc)
        light=bpy.context.object
        light.data.energy=energy
        light.data.shape='DISK'
        light.data.size=size
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Weapon studio')
    scene.world.color=(.1,.1,.1)
    scene.view_settings.view_transform='AgX'
    scene.render.resolution_x=1050
    scene.render.resolution_y=650
    scene.cycles.samples=24
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}.blend'))
    scene.render.filepath=str(ROOT/f'{label}.png')
    bpy.ops.render.render(write_still=True)
    (ROOT/f'{label}_build.json').write_text(json.dumps({'triangles':len(weapon.data.polygons),'bones':2,'clips':clips,'animation_frames':79},indent=2))


if __name__=='__main__':
    for level in range(8):
        if '--animations-only' in sys.argv:
            label=f'infantry_{level}'
            bpy.ops.wm.open_mainfile(filepath=str(ROOT/f'{label}.blend'))
            clips=build_animations(level,bpy.data.objects[label+'_rig'])
            report=json.loads((ROOT/f'{label}_build.json').read_text())
            report.pop('fire_frames',None)
            report['clips']=clips
            (ROOT/f'{label}_build.json').write_text(json.dumps(report,indent=2))
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}.blend'))
        elif '--level' not in sys.argv or level==int(sys.argv[sys.argv.index('--level')+1]):
            build(level)
