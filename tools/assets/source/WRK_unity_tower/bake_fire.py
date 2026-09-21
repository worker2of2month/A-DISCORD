"""Bake localized fire damage and broken glazing into one native texture atlas."""
import bpy
import math
import subprocess
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent


def math_node(nodes, links, operation, a, b):
    node = nodes.new('ShaderNodeMath')
    node.operation = operation
    for index,value in enumerate((a,b)):
        if isinstance(value,(float,int)):
            node.inputs[index].default_value = value
        else:
            links.new(value,node.inputs[index])
    return node.outputs[0]


def fire_factor(nodes,links):
    position = nodes.new('ShaderNodeNewGeometry').outputs['Position']
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position,split.inputs[0])
    height = nodes.new('ShaderNodeMapRange')
    height.clamp = True
    links.new(split.outputs['Z'],height.inputs['Value'])
    height.inputs['From Min'].default_value = -9
    height.inputs['From Max'].default_value = 10
    shift = nodes.new('ShaderNodeVectorMath')
    shift.operation = 'SUBTRACT'
    links.new(position,shift.inputs[0])
    shift.inputs[1].default_value = (7,-5,0)
    stretch = nodes.new('ShaderNodeVectorMath')
    stretch.operation = 'MULTIPLY'
    links.new(shift.outputs['Vector'],stretch.inputs[0])
    stretch.inputs[1].default_value = (1/37,1/33,0)
    radius = nodes.new('ShaderNodeVectorMath')
    radius.operation = 'LENGTH'
    links.new(stretch.outputs['Vector'],radius.inputs[0])
    radial = nodes.new('ShaderNodeMapRange')
    radial.clamp = True
    links.new(radius.outputs['Value'],radial.inputs['Value'])
    radial.inputs['From Min'].default_value = .05
    radial.inputs['From Max'].default_value = 1.25
    radial.inputs['To Min'].default_value = 1
    radial.inputs['To Max'].default_value = 0
    noise = nodes.new('ShaderNodeTexNoise')
    links.new(position,noise.inputs['Vector'])
    noise.inputs['Scale'].default_value = .42
    noise.inputs['Detail'].default_value = 3
    noise.inputs['Roughness'].default_value = .72
    mottling = math_node(nodes,links,'ADD',.42,math_node(nodes,links,'MULTIPLY',noise.outputs['Fac'],.9))
    coverage = math_node(nodes,links,'MULTIPLY',height.outputs['Result'],radial.outputs['Result'])
    return math_node(nodes,links,'MINIMUM',.95,math_node(nodes,links,'MULTIPLY',coverage,mottling))


def bake_fire(tower,pdx,preview_gloss):
    scene = bpy.context.scene
    bpy.ops.object.select_all(action='DESELECT')
    tower.select_set(True)
    bpy.context.view_layer.objects.active = tower
    source_uv = tower.data.uv_layers.active.name
    tower.data.uv_layers.new(name='FireAtlas')
    tower.data.uv_layers.active_index = len(tower.data.uv_layers)-1
    tower.data.uv_layers.active.active_render = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.0015)
    bpy.ops.object.mode_set(mode='OBJECT')
    atlas = bpy.data.images.new('Tower fire atlas',width=4096,height=4096,alpha=True)
    broken_windows = bpy.data.images.load(str(ROOT/'Fire_windows.png'),check_existing=True)
    for material in set(tower.data.materials):
        nodes,links = material.node_tree.nodes,material.node_tree.links
        uv = nodes.new('ShaderNodeUVMap')
        uv.uv_map = source_uv
        for node in list(nodes):
            if node.type == 'TEX_IMAGE' and node.image:
                if node.image.name.startswith('ADISCORD_vorkerland_pyramid_windows'):
                    node.image = broken_windows
                links.new(uv.outputs['UV'],node.inputs['Vector'])
        shader = nodes.get('Principled BSDF')
        source = shader.inputs['Base Color'].links[0].from_socket
        factor = fire_factor(nodes,links)
        char = nodes.new('ShaderNodeMixRGB')
        char.blend_type = 'MULTIPLY'
        char.inputs[0].default_value = 1
        links.new(source,char.inputs[1])
        char.inputs[2].default_value = (.12,.085,.065,1)
        mix = nodes.new('ShaderNodeMixRGB')
        links.new(factor,mix.inputs[0])
        links.new(source,mix.inputs[1])
        links.new(char.outputs[0],mix.inputs[2])
        emission = nodes.new('ShaderNodeEmission')
        links.new(mix.outputs[0],emission.inputs['Color'])
        output = next(node for node in nodes if node.type=='OUTPUT_MATERIAL')
        links.new(emission.outputs[0],output.inputs['Surface'])
        target = nodes.new('ShaderNodeTexImage')
        target.image = atlas
        nodes.active = target
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 1
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = 2
    bpy.ops.object.bake(type='EMIT',use_clear=True)
    atlas.filepath_raw = str(ROOT/'Tower_fire_diffuse.png')
    atlas.file_format = 'PNG'
    atlas.save()
    subprocess.run(['python','-B',str(ROOT/'package_tower.py'),'--prepare-baked'],check=True)
    for layer in list(tower.data.uv_layers):
        if layer.name != 'FireAtlas':
            tower.data.uv_layers.remove(layer)
    apply_fire_material(tower, pdx, preview_gloss)


def apply_fire_material(tower, pdx, preview_gloss):
    # Standalone skinned actors have no unit-atlas coordinates.
    material = pdx.create_shader(SimpleNamespace(shader=['PdxMeshStandard'],
        diff=['Tower_fire_diffuse.dds'],n=['Tower_fire_normal.dds'],spec=['Tower_fire_specular.dds']),
        'Tower fire damage',str(ROOT))
    preview_standard(material)
    tower.data.materials.clear()
    tower.data.materials.append(material)
    for face in tower.data.polygons:
        face.material_index = 0


def preview_standard(material):
    """Map the Standard RGB normal and specular intensity for the Blender preview."""
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    normal_texture = next(node for node in nodes if node.type == 'TEX_IMAGE'
                          and node.image and 'normal' in node.image.name.lower())
    normal_map = shader.inputs['Normal'].links[0].from_node
    separate = nodes.new('ShaderNodeSeparateColor')
    combine = nodes.new('ShaderNodeCombineColor')
    invert = nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.inputs[0].default_value = 1
    links.new(normal_texture.outputs['Color'], separate.inputs['Color'])
    links.new(separate.outputs['Red'], combine.inputs['Red'])
    links.new(separate.outputs['Green'], invert.inputs[1])
    links.new(invert.outputs[0], combine.inputs['Green'])
    links.new(separate.outputs['Blue'], combine.inputs['Blue'])
    links.new(combine.outputs['Color'], normal_map.inputs['Color'])
    specular_texture = next(node for node in nodes if node.type == 'TEX_IMAGE'
                            and node.image and 'specular' in node.image.name.lower())
    # Keep the texture connected to the slot used by the PDX exporter.
    roughness = nodes.new('ShaderNodeMath')
    roughness.operation = 'MULTIPLY_ADD'
    roughness.inputs[1].default_value = 0
    roughness.inputs[2].default_value = .8
    links.new(specular_texture.outputs['Alpha'], roughness.inputs[0])
    links.new(roughness.outputs[0], shader.inputs['Roughness'])
    links.new(specular_texture.outputs['Alpha'], shader.inputs['Specular IOR Level'])
    for link in list(shader.inputs['Metallic'].links):
        links.remove(link)
    shader.inputs['Metallic'].default_value = 0
