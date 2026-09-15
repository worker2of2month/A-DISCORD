"""Build rigid structural collapse clips from the original tower, without editing it."""
import bmesh
import bpy
import hashlib
import json
import math
import random
import shutil
import sys
from pathlib import Path
from mathutils import Vector, Euler
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
MOD = ROOT.parents[3]
ORIGINAL = MOD / 'gfx/models/buildings/vorkerland_special'
sys.path.insert(0, str(ROOT.parent / 'STP_regulars'))
from export_verify import pdx, pdx_data, preview_gloss, validate_mesh
sys.path.insert(0,str(ROOT))
from bake_fire import bake_fire, apply_fire_material

GROUND = -18.897600173950195
FRAMES = 361
DAMAGE_FLOOR = 3.0


def setup_camera(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.world.color = (.13, .13, .13)
    scene.view_settings.view_transform = 'AgX'
    target = Vector((0, 0, -4))
    bpy.ops.object.camera_add(location=(98, -145, 93))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 139
    scene.camera = camera
    for loc, power in [((75, -95, 160), 220000), ((-100, -30, 80), 125000), ((30, 110, 130), 180000)]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        lamp = bpy.context.object
        lamp.data.energy = power
        lamp.data.shape = 'DISK'
        lamp.data.size = 90
        lamp.rotation_euler = (target - lamp.location).to_track_quat('-Z', 'Y').to_euler()


def split_region(source, xmin, xmax, ymin, ymax, zmin, zmax, fracture_planes=()):
    bm = bmesh.new()
    bm.from_mesh(source.data)
    for axis, value, below in [(0, xmin, True), (0, xmax, False), (1, ymin, True),
                               (1, ymax, False), (2, zmin, True), (2, zmax, False)]:
        normal = [0, 0, 0]
        normal[axis] = 1
        point = [0, 0, 0]
        point[axis] = value
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              plane_co=point, plane_no=normal, clear_inner=below,
                              clear_outer=not below, dist=.00001)
    for point, normal in fracture_planes:
        if not bm.faces:
            break
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              plane_co=point, plane_no=normal, clear_outer=True, dist=.00001)
    if not bm.faces:
        bm.free()
        return None
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    mesh = bpy.data.meshes.new('Tower structural section')
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('Tower section', mesh)
    bpy.context.scene.collection.objects.link(obj)
    for material in source.data.materials:
        obj.data.materials.append(material)
    return obj


def fractured_regions(source):
    base = split_region(source,-60,60,-60,60,GROUND-1,DAMAGE_FLOOR)
    yield -1, 0, base
    rng = random.Random(1642809)
    seeds = [Vector((x+rng.uniform(-2.7,2.7),y+rng.uniform(-2.7,2.7),rng.uniform(5,16)))
             for y in (-27,-15,-3,9,21) for x in (-26,-15,-4,7,18,29)]
    for tier,(bottom,top) in enumerate(((DAMAGE_FLOOR,10),(10,20))):
        for index,seed in enumerate(seeds):
            planes = [((seed+other)*.5,(other-seed).normalized())
                      for other_index,other in enumerate(seeds) if other_index != index]
            obj = split_region(source,-60,60,-60,60,bottom,top,planes)
            if obj is not None:
                yield tier,index,obj


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new('Tower studio')
    original_mesh = ORIGINAL / 'ADISCORD_vorkerland_pyramid.mesh'
    original_hash = hashlib.sha256(original_mesh.read_bytes()).hexdigest()
    pdx.import_meshfile(str(original_mesh), join_materials=False)
    originals = [obj for obj in scene.objects if obj.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in originals:
        obj.select_set(True)
        for material in obj.data.materials:
            preview_gloss(material)
    bpy.context.view_layer.objects.active = originals[0]
    bpy.ops.object.join()
    source = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pieces = []
    for tier, quadrant, obj in fractured_regions(source):
            name = f'section_{tier}_{quadrant}'
            obj.name = name
            points = [v.co.copy() for v in obj.data.vertices]
            center = Vector([sum(p[i] for p in points)/len(points) for i in range(3)])
            # Lay each wall patch toward the ground using a rigid rotation. PDX
            # export defaults to scalar scale, so never squash just one axis.
            normal = Vector((0,0,0))
            for face in obj.data.polygons:
                direction = face.normal if face.normal.z >= 0 else -face.normal
                normal += direction*face.area
            normal = normal.normalized() if normal.length > 1e-6 else Vector((0,0,1))
            # Each rigid section keeps its exterior UVs; a narrow shell closes its reverse side.
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            shell = obj.modifiers.new('Broken wall thickness', 'SOLIDIFY')
            shell.thickness = .20
            shell.offset = -1
            bpy.ops.object.modifier_apply(modifier=shell.name)
            offsets = [v.co.copy()-center for v in obj.data.vertices]
            damaged = (tier >= 0 and center.x > -6+3*math.sin(center.y*.23)
                       and center.y < 14+2*math.cos(center.x*.3))
            if not damaged:
                pieces.append({'object':obj, 'stationary':True})
                continue
            rng = random.Random(tier*19+quadrant)
            flatten = normal.rotation_difference(Vector((0,0,1))).to_matrix()
            turn = Euler((rng.uniform(-.42,.42), rng.uniform(-.42,.42), rng.uniform(-1.1,1.1)), 'XYZ').to_matrix()
            rotation = (turn @ flatten).to_euler('XYZ')
            uniform_scale = rng.uniform(.72,.93)
            scale = Vector((uniform_scale,)*3)
            matrix = rotation.to_matrix()
            transformed = [matrix @ Vector(tuple((v.co-center)[i]*scale[i] for i in range(3)))
                           for v in obj.data.vertices]
            target_xy = Vector((center.x+rng.uniform(-2.7,2.7),
                                center.y+rng.uniform(-2.7,2.7), 0))
            target_xy.z = DAMAGE_FLOOR + rng.uniform(.35,.9) + tier*.8 - min(p.z for p in transformed)
            pieces.append({'object':obj, 'name':name, 'center':center,
                           'offsets':offsets,
                           'contact_floor':min(DAMAGE_FLOOR+.02, min(v.co.z for v in obj.data.vertices)),
                           'translation':target_xy-center, 'rotation':rotation,
                           'scale':scale, 'delay':.25+(1-tier)*.55+rng.uniform(0,.6),
                           'duration':1.6+rng.uniform(0,1.1)})
    bpy.data.objects.remove(source, do_unlink=True)
    # Keep the lower body and undamaged upper crown rigidly anchored to one bone.
    stationary = [piece['object'] for piece in pieces if piece.get('stationary')]
    pieces = [piece for piece in pieces if not piece.get('stationary')]
    moving_sections = len(pieces)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in stationary:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = stationary[0]
    bpy.ops.object.join()
    pieces.append({'object':bpy.context.object,'name':'tower_shell','center':Vector((0,0,0)),
                   'translation':Vector((0,0,0)),'rotation':Euler((0,0,0)),
                   'scale':Vector((1,1,1)),'delay':0,'duration':1})
    concrete = pdx.create_shader(SimpleNamespace(shader=['PdxMeshAdvanced'],
        diff=['Tower_concrete_diffuse.dds'],n=['Tower_concrete_normal.dds'],
        spec=['Tower_concrete_specular.dds']), 'Broken concrete', str(ROOT))
    preview_gloss(concrete)
    rubble = []
    rng = random.Random(16428)
    for index in range(38):
        tall = index < 5
        dimensions = (rng.uniform(.8,1.3) if tall else rng.uniform(1.5,3.7),
                      rng.uniform(.8,1.3) if tall else rng.uniform(1.2,3.5),
                      rng.uniform(3,5.8) if tall else rng.uniform(.3,1.4))
        bpy.ops.mesh.primitive_cube_add(size=1, location=(rng.uniform(-3,17),rng.uniform(-15,8),DAMAGE_FLOOR+dimensions[2]/2+.05))
        obj = bpy.context.object
        obj.scale = dimensions
        obj.rotation_euler.z = rng.uniform(-math.pi,math.pi)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        for vertex in obj.data.vertices:
            vertex.co.x += rng.uniform(-.45,.45)
            vertex.co.y += rng.uniform(-.45,.45)
        obj.data.materials.append(concrete)
        rubble.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in rubble:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rubble[0]
    bpy.ops.object.join()
    pieces.append({'object':bpy.context.object,'name':'rubble_core','center':Vector((0,0,0)),
                   'translation':Vector((0,0,0)),'rotation':Euler((0,0,0)),
                   'scale':Vector((1,1,1)),'delay':0,'duration':1})
    bpy.ops.object.armature_add()
    rig = bpy.context.object
    rig.name = 'Unity_tower_rig'
    bpy.ops.object.mode_set(mode='EDIT')
    root = rig.data.edit_bones[0]
    root.name = 'tower_root'
    root.head, root.tail = (0,0,0), (0,1,0)
    for piece in pieces:
        bone = rig.data.edit_bones.new(piece['name'])
        bone.head = piece['center']
        bone.tail = bone.head + Vector((0,1,0))
        bone.parent = root
    bpy.ops.object.mode_set(mode='OBJECT')
    for piece in pieces:
        obj = piece['object']
        obj.vertex_groups.new(name=piece['name']).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        obj.modifiers.new('Tower rig', 'ARMATURE').object = rig
    bpy.ops.object.select_all(action='DESELECT')
    for piece in pieces:
        piece['object'].select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]['object']
    bpy.ops.object.join()
    tower = bpy.context.object
    tower.name = 'Unity_tower_destruction'
    bm = bmesh.new()
    bm.from_mesh(tower.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(tower.data)
    bm.free()
    # Keep material names/UVs and copy the author's own source DDS for the independent asset.
    for texture in ORIGINAL.glob('*.dds'):
        shutil.copyfile(texture, ROOT/texture.name)
    for material in tower.data.materials:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image_path = ROOT / Path(bpy.path.abspath(node.image.filepath)).name
                if image_path.is_file():
                    node.image.filepath = str(image_path)
    bake_fire(tower,pdx,preview_gloss)
    bpy.context.view_layer.objects.active = rig
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, FRAMES
    for frame in range(1, FRAMES+1):
        time = (frame-1)/30
        for piece in pieces:
            pose = rig.pose.bones[piece['name']]
            u = max(0, min(1, (time-piece['delay'])/piece['duration']))
            # Accelerate the fall, brake at contact, then settle with a decaying bounce.
            ease = u*u*(3-2*u)
            bounce = math.sin((time-piece['delay']-piece['duration'])*12) * .38 * math.exp(-4*max(0,time-piece['delay']-piece['duration'])) if u == 1 and 'offsets' in piece else 0
            pose.location = piece['translation']*ease + Vector((0,0,max(0,bounce)))
            pose.rotation_mode = 'XYZ'
            pose.rotation_euler = tuple(v*ease for v in piece['rotation'])
            pose.scale = tuple(1+(v-1)*ease for v in piece['scale'])
            # Rotation changes the lowest corner before the final pose is reached.
            # Clamp each sampled rigid section against the ground throughout its fall.
            if 'offsets' in piece:
                rotation_matrix = pose.rotation_euler.to_matrix()
                bottom = min((rotation_matrix @ Vector(tuple(point[i]*pose.scale[i] for i in range(3)))).z
                             for point in piece['offsets']) + piece['center'].z + pose.location.z
                pose.location.z += max(0, piece['contact_floor']-bottom)
            pose.keyframe_insert('location',frame=frame)
            pose.keyframe_insert('rotation_euler',frame=frame)
            pose.keyframe_insert('scale',frame=frame)
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    tower.select_set(True)
    bpy.context.view_layer.objects.active = tower
    pdx.export_meshfile(str(ROOT/'ADISCORD_unity_tower_destruction.mesh'), exp_selected=True)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(ROOT/'ADISCORD_unity_tower_collapse.anim'),frame_start=1,frame_end=FRAMES)
    setup_camera(scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Unity_tower_collapse.blend'))
    render_frames = () if '--no-render' in sys.argv else ((361,) if '--last-frame' in sys.argv else (1,46,91,151,241,361))
    for frame in render_frames:
        scene.frame_set(frame)
        scene.render.filepath = str(ROOT/f'tower_collapse_{frame:03}.png')
        bpy.ops.render.render(write_still=True)
    # A one-second static pose permits direct creation after loading a completed collapse.
    scene.frame_set(FRAMES)
    final_pose = {bone.name:(bone.location.copy(),bone.rotation_euler.copy(),bone.scale.copy()) for bone in rig.pose.bones}
    rig.animation_data_clear()
    for frame in (1,31):
        for bone in rig.pose.bones:
            bone.location, bone.rotation_euler, bone.scale = final_pose[bone.name]
            for prop in ('location','rotation_euler','scale'):
                bone.keyframe_insert(prop,frame=frame)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(ROOT/'ADISCORD_unity_tower_ruins.anim'),frame_start=1,frame_end=31)
    scene.frame_start,scene.frame_end = 1,31
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Unity_tower_ruins.blend'))
    report = {'original_sha256':original_hash,'original_unchanged':hashlib.sha256(original_mesh.read_bytes()).hexdigest()==original_hash,
              'design':'Irregular Voronoi fracture of an expanded upper sector, with surviving lower body and opposite crown.',
              'sections':len(pieces),'moving_sections':moving_sections,'bones':len(rig.data.bones),'collapse_frames':FRAMES,'fps':30,
              'mesh':validate_mesh(ROOT/'ADISCORD_unity_tower_destruction.mesh',len(rig.data.bones)),
              'ground_local_z':GROUND,'actor_height_offset':-GROUND*.15}
    (ROOT/'build_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


def refresh_material():
    """Re-export a baked scene when only the runtime material contract changes."""
    for name in ('collapse', 'ruins'):
        scene_path = ROOT/f'Unity_tower_{name}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
        scene = bpy.context.scene
        scene.frame_set(1)
        tower = scene.objects['Unity_tower_destruction']
        apply_fire_material(tower, pdx, preview_gloss)
        if name == 'collapse':
            bpy.ops.object.select_all(action='DESELECT')
            tower.select_set(True)
            bpy.context.view_layer.objects.active = tower
            pdx.export_meshfile(str(ROOT/'ADISCORD_unity_tower_destruction.mesh'), exp_selected=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))


if __name__ == '__main__':
    if '--refresh-material' in sys.argv:
        refresh_material()
    else:
        build()
