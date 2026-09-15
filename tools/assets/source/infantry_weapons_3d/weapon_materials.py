"""Projected material grain and contact shading baked into the game diffuse."""
from pathlib import Path
import bpy

ROOT = Path(__file__).parent


def material(name, color, metallic=0, surface=None):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    nodes, links = result.node_tree.nodes, result.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = .54
    if surface is None:
        return result
    position = nodes.new('ShaderNodeNewGeometry')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs['Position'], split.inputs[0])
    combine = nodes.new('ShaderNodeCombineXYZ')
    links.new(split.outputs['Y'], combine.inputs['X'])
    links.new(split.outputs['Z'], combine.inputs['Y'])
    scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
    scale.inputs[3].default_value = {'wood':.55,'steel':1.3,'polymer':2.5,'ceramic':1.5}[surface]
    links.new(combine.outputs[0], scale.inputs[0])
    repeat = nodes.new('ShaderNodeVectorMath'); repeat.operation = 'FRACTION'
    links.new(scale.outputs[0], repeat.inputs[0])
    tile = nodes.new('ShaderNodeVectorMath'); tile.operation = 'MULTIPLY_ADD'
    tile.inputs[1].default_value = (.475, .475, 0)
    offsets = {'steel':(.0125,.5125,0), 'wood':(.5125,.5125,0),
               'polymer':(.0125,.0125,0), 'ceramic':(.5125,.0125,0)}
    tile.inputs[2].default_value = offsets[surface]
    links.new(repeat.outputs[0], tile.inputs[0])
    image = nodes.new('ShaderNodeTexImage')
    image.image = bpy.data.images.load(str(ROOT/'Weapon_material_atlas.png'), check_existing=True)
    links.new(tile.outputs[0], image.inputs[0])
    tint = nodes.new('ShaderNodeMixRGB'); tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1
    # Atlas colors carry real grain; these factors preserve generation palettes.
    base = .13 if surface == 'wood' else .065
    tint.inputs[2].default_value = (*[min(2.5, c/base) for c in color],1)
    links.new(image.outputs[0], tint.inputs[1])
    ao = nodes.new('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = .16
    ao.samples = 16
    contact = nodes.new('ShaderNodeMixRGB'); contact.blend_type = 'MULTIPLY'
    contact.inputs[0].default_value = .72
    links.new(tint.outputs[0], contact.inputs[1])
    links.new(ao.outputs['Color'], contact.inputs[2])
    edge = nodes.new('ShaderNodeValToRGB')
    edge.color_ramp.elements[0].position = .40
    edge.color_ramp.elements[0].color = (.56,.56,.56,1)
    edge.color_ramp.elements[1].position = .58
    edge.color_ramp.elements[1].color = (1.20,1.20,1.20,1)
    links.new(position.outputs['Pointiness'], edge.inputs[0])
    wear = nodes.new('ShaderNodeMixRGB'); wear.blend_type = 'MULTIPLY'
    wear.inputs[0].default_value = .5
    links.new(contact.outputs[0], wear.inputs[1])
    links.new(edge.outputs[0], wear.inputs[2])
    links.new(wear.outputs[0], shader.inputs['Base Color'])
    return result
