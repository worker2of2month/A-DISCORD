"""Build the three field infantry sets on the existing 33-bone STP rig.

Run with Blender --background --factory-startup --python, optionally -- TAG.
Only source meshes and baked albedo are written here; package_regulars.py
converts the maps and installs the native files in the mod.
"""
import bmesh
import bpy
import inspect
import json
import math
import struct
import sys
import zlib
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).parent
BASE = ROOT.parent / 'STP_shabrat'
sys.path.insert(0, str(ROOT.parent))
from infantry_polish import tailored_fabric, curve_carrier, fitted_head_cloth, helmet_shell, fitted_armband, curved_guard
sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
from io_pdx_mesh.pdx_blender import blender_import_export as pdx

source = inspect.getsource(pdx.create_shader)
for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
    source = source.replace(line, '')
exec(compile(source, '<Blender 5 material compatibility>', 'exec'), pdx.__dict__)

VARIANTS = {
    'STP_party': dict(plate=(.10, .105, .075), canvas=(.23, .21, .13), helmet=(.12, .135, .09), trim=(.46, .33, .08)),
    'STS_regular': dict(plate=(.24, .20, .135), canvas=(.28, .23, .15), helmet=(.17, .19, .16), trim=(.48, .33, .08)),
    'VAL_regular': dict(plate=(.038, .062, .080), canvas=(.052, .069, .081), helmet=(.045, .067, .079), trim=(.25, .020, .016)),
}


def material(name, color, roughness=.82):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = roughness
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 110
    noise.inputs['Detail'].default_value = 2
    ramp = nodes.new('ShaderNodeValToRGB')
    for element, factor in zip(ramp.color_ramp.elements, (.83, 1.17)):
        element.color = tuple(c * factor for c in color) + (1,)
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    ao = nodes.new('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = .15
    ao.samples = 16
    links.new(ramp.outputs['Color'], ao.inputs['Color'])
    links.new(ao.outputs['Color'], shader.inputs['Base Color'])
    return mat


def bake_surface_maps(equipment, label):
    """Bake each surface into native specular/metal/gloss and tangent-normal channels."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 8
    scene.render.bake.margin = 12
    bpy.ops.object.select_all(action='DESELECT')
    equipment.select_set(True)
    bpy.context.view_layer.objects.active = equipment
    materials = list(equipment.data.materials)
    saved = []
    settings = {}
    for mat in materials:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        shader = nodes.get('Principled BSDF')
        name = mat.name.lower()
        if 'optic' in name:
            specular, metalness, roughness, relief = .55, .0, .20, .0003
        elif 'metal' in name or 'fitting' in name:
            specular, metalness, roughness, relief = .45, .55, .43, .001
        elif 'shell' in name or 'insert' in name or 'carrier' in name:
            specular, metalness, roughness, relief = .34, .0, .60, .0018
        else:
            specular, metalness, roughness, relief = .22, .0, .86, .005
        settings[mat.name] = [specular, metalness, roughness, relief]
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
        saved.append((mat, output.inputs['Surface'].links[0].from_socket,
                      shader.inputs['Roughness'].default_value))
        shader.inputs['Roughness'].default_value = roughness
        noise = next(n for n in nodes if n.type == 'TEX_NOISE')
        bump = nodes.new('ShaderNodeBump')
        bump.name = 'Baked surface grain'
        bump.inputs['Distance'].default_value = relief
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], shader.inputs['Normal'])

    def bake(kind):
        target = bpy.data.images.new(label+'_'+kind, 1024, 1024, alpha=True, float_buffer=True)
        target.colorspace_settings.name = 'Non-Color'
        for mat in materials:
            node = mat.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = target
            mat.node_tree.nodes.active = node
        bpy.ops.object.bake(type=kind)
        pixels = np.empty(1024*1024*4, dtype=np.float32)
        target.pixels.foreach_get(pixels)
        return pixels.reshape(-1,4)

    roughness = bake('ROUGHNESS')[:,0]
    normal = bake('NORMAL')
    for mat, _, _ in saved:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
        emission = nodes.new('ShaderNodeEmission')
        specular, metalness, _, _ = settings[mat.name]
        emission.inputs['Color'].default_value = (0, specular, metalness, 1)
        links.new(emission.outputs[0], output.inputs['Surface'])
    properties = bake('EMIT')
    properties[:,3] = 1-roughness
    packed_normal = np.zeros_like(normal)
    # UnpackRRxGNormal reads tangent X from G and inverted Y from A.
    packed_normal[:,0] = packed_normal[:,1] = normal[:,0]
    packed_normal[:,3] = 1-normal[:,1]
    for kind, pixels in (('specular',properties),('normal',packed_normal)):
        # These are independent data channels: PNG alpha must not premultiply RGB.
        rows=np.rint(np.clip(pixels,0,1)*255).astype(np.uint8).reshape(1024,1024,4)[::-1]
        def chunk(tag,data):
            return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
        payload=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',1024,1024,8,6,0,0,0))
        payload+=chunk(b'IDAT',zlib.compress(b''.join(b'\0'+row.tobytes() for row in rows)))+chunk(b'IEND',b'')
        (ROOT/f'{label}_gear_{kind}.png').write_bytes(payload)
    for mat, surface, roughness in saved:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
        links.new(surface, output.inputs['Surface'])
        nodes.get('Principled BSDF').inputs['Roughness'].default_value = roughness
    (ROOT/f'{label}_materials.json').write_text(json.dumps(settings,indent=2))


def build(label):
    bpy.ops.wm.open_mainfile(filepath=str(BASE / 'STP.blend'))
    scene = bpy.context.scene
    body = next(o for o in scene.objects if o.type == 'MESH' and not o.hide_render)
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    body.name = label + '_body'
    parts = json.loads((BASE / 'components.json').read_text())
    hat_ids = {i for part in parts if part['min'][2] > 6.94 for i in part['ids']}
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in hat_ids], context='VERTS')
    bm.to_mesh(body.data)
    bm.free()
    mat = body.data.materials[0]
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].links[0].from_node.image = bpy.data.images.load(str(ROOT / f'{label}_body_diffuse.dds'))
    for node in mat.node_tree.nodes:
        if node.type != 'TEX_IMAGE' or not node.image:
            continue
        for kind in ('normal', 'specular'):
            if kind in node.image.name:
                node.image = bpy.data.images.load(str(ROOT / f'{label}_body_{kind}.dds'))
    bsdf.inputs['Roughness'].default_value = .85
    colors = VARIANTS[label]
    plate = material('Protective carrier', colors['plate'])
    canvas = material('Canvas pouches', colors['canvas'])
    helmet = material('Helmet shell', colors['helmet'], .76)
    if label == 'VAL_regular':
        # A cloth cover carries the same subdued three-tone field palette.
        nodes = helmet.node_tree.nodes
        noise = next(n for n in nodes if n.type == 'TEX_NOISE')
        noise.inputs['Scale'].default_value = 5
        ramp = next(n for n in nodes if n.type == 'VALTORGB').color_ramp
        ramp.interpolation = 'CONSTANT'
        ramp.elements[0].position = .36
        ramp.elements[0].color = (.026, .036, .044, 1)
        ramp.elements[1].position = .59
        ramp.elements[1].color = (.075, .102, .129, 1)
        ramp.elements.new(.48).color = (.045, .067, .079, 1)
    trim = material('Identification trim', colors['trim'])
    webbing = material('Black webbing', (.023, .027, .030))
    steel = material('Oxidized metal', (.075, .081, .083), .5)
    binding = material('Woven edge binding', tuple(c*.64 for c in colors['canvas']))
    composite = material('Matte composite insert', tuple(c*.63 for c in colors['plate']))
    gear = []

    def finish(obj, name, mat, bone='back_mid'):
        obj.name = name
        obj.data.materials.append(mat)
        if not obj.vertex_groups:
            obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
        obj.modifiers.new('Infantry armature', 'ARMATURE').object = rig
        gear.append(obj)
        return obj

    def box(name, loc, size, mat, bone='back_mid', bevel=.03):
        soft={'Rifle magazine pouch','Side ammunition','Flank twin utility pouch','Pack side pocket',
              'First aid satchel','Canteen pouch','March pack'}
        if name in soft:
            from infantry_polish import cloth_bag
            sideways=name in ('Side ammunition','Flank twin utility pouch','Pack side pocket','First aid satchel','Canteen pouch')
            direction=(math.copysign(math.pi/2,-loc[0]) if sideways else 0 if name=='March pack' else math.pi)
            width,depth=(size[1],size[0]) if sideways else size[:2]
            parts=cloth_bag(width,depth,size[2],(-.28,.28) if name=='March pack' else ())
            offset=.16*(loc[0]/.8)**2 if loc[1]<-.78 and 4.45<loc[2]<5.7 else 0
            shell=None
            for part,kind,vertices,faces in parts:
                if label=='STS_regular' and name=='Rifle magazine pouch':
                    # A shallow tension fold sits below the flap without moving its seam.
                    vertices=[(x,y-.010*math.exp(-((z/size[2]-.05)/.13)**2)
                               *max(0,1-(2*x/width)**2)*max(0,y/(depth*.5)),z)
                              for x,y,z in vertices]
                points=[(loc[0]+x*math.cos(direction)-y*math.sin(direction),
                         loc[1]+offset+x*math.sin(direction)+y*math.cos(direction),loc[2]+z) for x,y,z in vertices]
                obj=mesh(name+' '+part,points,faces,mat if kind=='canvas' else binding,bone)
                for face in obj.data.polygons:face.use_smooth=True
                if shell is None:shell=obj
            return shell
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = bpy.context.object
        obj.scale = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if bevel:
            mod = obj.modifiers.new('Rounded edge', 'BEVEL')
            mod.width, mod.segments = bevel, 2
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if mat == canvas and min(size) > .12:
            tailored_fabric(obj)
        if name in ('Knee protector','Knee face','Shin guard'):
            curved_guard(obj)
        if loc[1] < -.78 and 4.45 < loc[2] < 5.7:
            obj.location.y += .16*(loc[0]/.8)**2
        return finish(obj, name, mat, bone)

    def mesh(name, verts, faces, mat, bone='back_mid'):
        data = bpy.data.meshes.new(name)
        data.from_pydata(verts, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        return finish(obj, name, mat, bone)

    def rings(name, rows, mat, bone='head', segments=24, cap=False, smooth=True):
        verts = []
        for rx, ry, cy, z, tilt in rows:
            for i in range(segments):
                a = math.tau * i / segments
                verts.append((rx * math.cos(a), cy + ry * math.sin(a), z + tilt * math.sin(a)))
        faces = []
        for j in range(len(rows) - 1):
            for i in range(segments):
                a, b = j * segments + i, j * segments + (i + 1) % segments
                faces.append((a, b, b + segments, a + segments))
        if cap:
            faces.append(tuple(range((len(rows) - 1) * segments, len(rows) * segments)))
        obj = mesh(name, verts, faces, mat, bone)
        for face in obj.data.polygons:
            face.use_smooth = smooth
        return obj

    def bound_outline(points, mat):
        # Closed round piping retains its silhouette under front-face culling.
        for (x1,z1),(x2,z2) in zip(points,points[1:]+points[:1]):
            start=Vector((x1,-.775+.16*(x1/.8)**2,z1))
            end=Vector((x2,-.775+.16*(x2/.8)**2,z2))
            delta=end-start
            bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.018,depth=delta.length,
                                               location=(start+end)*.5)
            obj=bpy.context.object
            obj.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
            bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            finish(obj,'Carrier cloth binding',mat)

    helmet_shell(mesh, helmet, canvas if label == 'STS_regular' else webbing, label)
    if label == 'STP_party':
        box('Helmet identification', (0,-.601,7.04), (.17,.018,.035), trim, 'head', .006)
    elif label == 'STS_regular':
        rings('Open neck scarf', [(.30,.34,-.02,6.02,.05),(.34,.36,-.03,6.13,.03)], canvas, 'back_mid')
    else:
        fitted_head_cloth(body, mesh, webbing, 'Fitted balaclava', hood=True)
        for x in (-.26,.26):
            box('Red collar tab', (x,-.38,6.025), (.18,.04,.085), trim, 'back_mid', .007)
    # Chin straps remain part of the head to avoid a separated seam in aiming poses.
    for side in (-1, 1):
        mesh('Helmet chin strap', [(side*.405,-.18,6.94),(side*.425,-.14,6.94),(side*.22,-.34,6.27),(side*.19,-.37,6.27)], [(0,1,2,3)], webbing, 'head')

    outline = ([(-.73,4.43),(.73,4.43),(.80,5.40),(.52,5.89),(-.52,5.89),(-.80,5.40)]
               if label == 'VAL_regular' else
               [(-.65,4.49),(.65,4.49),(.72,5.39),(.45,5.80),(-.45,5.80),(-.72,5.39)])
    verts = [(x,y,z) for y in (-.75,-.59) for x,z in outline]
    # The front is -Y: X/Z counter-clockwise faces point toward the viewer.
    faces = [tuple(range(6)),tuple(reversed(range(6,12)))] + [(i+6,(i+1)%6+6,(i+1)%6,i) for i in range(6)]
    curve_carrier(mesh('Front protective carrier', verts, faces, plate))
    if label=='STP_party':
        bound_outline(outline,binding)
    box('Rear carrier', (0,.54,5.12), (1.18,.23,1.25), plate)
    for x in (-.48,.48):
        half=.155 if label=='STS_regular' else .12
        mesh('Shoulder strap', [(x-half,-.72,5.53),(x+half,-.72,5.53),(x+half,-.24,6.01),(x-half,-.24,6.01),(x+half,.34,5.98),(x-half,.34,5.98),(x+half,.66,5.50),(x-half,.66,5.50)], [(0,1,2,3),(3,2,4,5),(5,4,6,7)], canvas if label=='STS_regular' else binding)
        box('Shoulder buckle', (x,-.775,5.66), (.25,.055,.12), steel, bevel=.013)
    if label=='STP_party':
        pouches=[(x,4.83,.53,.25,.60) for x in (-.315,.315)]
    elif label=='STS_regular':
        pouches=[(-.435,4.83,.37,.25,.63),(0,4.81,.37,.22,.59),(.435,4.84,.37,.24,.61)]
    else:
        pouches=[(x,4.86,.55,.31,.63) for x in (-.335,.335)]
        pouches += [(x,5.40,.22,.27,.37) for x in (-.52,.52)]
    for x,z,width,depth,height in pouches:
        box('Rifle magazine pouch', (x,-.845,z), (width,depth,height), canvas, bevel=.035)
    if label != 'VAL_regular':
        for z in (5.33,5.48):
            box('Carrier webbing', (0,-.846,z), (.85,.025,.045), webbing, bevel=.005)
    if label == 'STP_party':
        upper=[(-.38,5.28),(.38,5.28),(.38,5.64),(.23,5.78),(-.23,5.78),(-.38,5.64)]
        curve_carrier(mesh('Upper composite insert',[(x,y,z) for y in (-.84,-.78) for x,z in upper],faces,helmet))
        for side in (-1,1):
            box('Side ammunition', (side*.79,-.25,4.63), (.28,.38,.59), canvas, bevel=.04)
        box('Lower abdominal plate', (0,-.63,4.34), (.67,.13,.24), plate, 'Hip')
    elif label == 'STS_regular':
        box('Ochre chest identification', (.23,-.86,5.65), (.27,.026,.09), trim, bevel=.004)
    else:
        box('Central composite insert', (0,-.82,5.49), (.58,.12,.45), composite, bevel=.065)
        box('Lower padded carrier', (0,-.72,4.41), (1.15,.17,.18), plate)
        for side in (-1,1):
            box('Wide flank section', (side*.77,.03,5.02), (.20,1.02,.82), plate, bevel=.06)
            box('Flank twin utility pouch', (side*.91,-.21,4.90), (.29,.36,.62), canvas, bevel=.045)
            box('Pack side pocket', (side*.62,.81,5.05), (.29,.42,.82), canvas, bevel=.045)
        box('Upper padded yoke', (0,-.72,5.77), (.82,.13,.14), plate, bevel=.055)
    radio_x=-.60 if label!='VAL_regular' else -.63
    radio_z=5.52 if label!='VAL_regular' else 5.78
    box('Field radio', (radio_x,-.81,radio_z), (.19,.20,.34), webbing, bevel=.02)
    box('Short aerial', (radio_x,-.78,radio_z+.31), (.022,.022,.36), webbing, bevel=.004)
    box('First aid satchel', (.86,.17,4.19), (.37,.51,.56), canvas, 'Hip', .045)
    box('Canteen pouch', (-.85,.30,4.20), (.33,.39,.48), canvas, 'Hip', .07)
    box('March pack', (0,.83,5.12), (1.02,.63,1.27) if label=='VAL_regular' else (.92,.48,1.06), canvas, bevel=.075)
    if label != 'STS_regular':
        box('Groundsheet roll', (0,.85,4.42), (1.10,.42,.30), plate, bevel=.10)
    for side in (-1,1):
        bone = 'LeftLeg' if side == 1 else 'RightLeg'
        box('Knee protector', (side*.68,-.33,2.055), (.38,.19,.53), webbing, bone, .065)
        box('Knee face', (side*.68,-.44,2.075), (.27,.035,.31), helmet, bone, .04)
        if label == 'STP_party':
            box('Shin guard', (side*.60,-.31,1.46), (.31,.13,.49), plate, bone, .055)
    if label == 'STS_regular':
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=.286, depth=.16, location=(1.13,.125,5.53))
        obj=bpy.context.object
        obj.rotation_euler=Vector((.79,.05,-.63)).to_track_quat('Z','Y').to_euler()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        fitted_armband(obj, body)
        finish(obj,'Ochre recognition band',trim,'LeftArm')

    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=gear[0]
    bpy.ops.object.join()
    equipment=bpy.context.object
    equipment.name=label+'_gear'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    image=bpy.data.images.new(label+'_gear_diffuse',1024,1024,alpha=False)
    for mat in equipment.data.materials:
        node=mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image=image
        mat.node_tree.nodes.active=node
    scene.render.engine='CYCLES'
    scene.cycles.samples=8
    scene.render.bake.use_pass_direct=False
    scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True
    scene.render.bake.margin=12
    bpy.ops.object.bake(type='DIFFUSE')
    image.filepath_raw=str(ROOT/f'{label}_gear_diffuse.png')
    image.file_format='PNG'
    image.save()
    bake_surface_maps(equipment,label)
    scene.cycles.samples=24
    scene.render.resolution_x=850
    scene.render.resolution_y=1050
    scene.view_settings.view_transform='AgX'
    for light in bpy.data.lights:
        light.energy*=.55
    scene.world.color=(.12,.12,.12)
    target=Vector((0,-.06,3.67))
    scene.camera.location=(8,-18,7.5)
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.ortho_scale=8.7
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}.blend'))
    scene.render.filepath=str(ROOT/f'{label}_front.png')
    bpy.ops.render.render(write_still=True)
    scene.camera.location=(-8,18,7.5)
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(ROOT/f'{label}_back.png')
    bpy.ops.render.render(write_still=True)
    report={'body_triangles':sum(len(p.vertices)-2 for p in body.data.polygons),'gear_triangles':sum(len(p.vertices)-2 for p in equipment.data.polygons),'bones':len(rig.data.bones)}
    for obj in (body,equipment):
        assert all(v.groups for v in obj.data.vertices), obj.name
        assert all(g.name in rig.data.bones for g in obj.vertex_groups), obj.name
    (ROOT/f'{label}_build.json').write_text(json.dumps(report,indent=2))
    print(label,report)


if __name__ == '__main__':
    labels=[a for a in sys.argv[sys.argv.index('--')+1:] if not a.startswith('--')] if '--' in sys.argv else list(VARIANTS)
    for label in labels:
        if '--bake-materials' in sys.argv:
            bpy.ops.wm.open_mainfile(filepath=str(ROOT/f'{label}.blend'))
            bake_surface_maps(bpy.data.objects[label+'_gear'],label)
        else:
            build(label)
