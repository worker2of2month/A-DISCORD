"""Export only the lower scarf drape, preserving all other native vertex data.

Run with Blender --background --python this_file -- --check or --apply.
With no action, --output writes a preview mesh without installing it.
"""

from pathlib import Path
import argparse
import copy
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name('STP_shabrat_infantry.blend')
TARGET = ROOT / 'gfx/models/units/STP_shabrat/STP_shabrat_infantry.mesh'


def tail_indices(mesh):
    points = mesh.attrib['p']
    keys = [tuple(round(v, 4) for v in points[i:i + 3]) for i in range(0, len(points), 3)]
    adjacency = {key: set() for key in keys}
    triangles = mesh.attrib['tri']
    for offset in range(0, len(triangles), 3):
        a, b, c = [keys[i] for i in triangles[offset:offset + 3]]
        adjacency[a].update((b, c))
        adjacency[b].update((a, c))
        adjacency[c].update((a, b))
    unseen = set(keys)
    matches = []
    while unseen:
        first = unseen.pop()
        component = {first}
        pending = [first]
        while pending:
            for key in adjacency[pending.pop()]:
                if key in unseen:
                    unseen.remove(key)
                    component.add(key)
                    pending.append(key)
        low = min(v[1] for v in component)
        high = max(v[1] for v in component)
        if (5.3 < low < 5.9 and 6.15 < high < 6.4
                and max(abs(v[0]) for v in component) < 0.4
                and max(v[2] for v in component) < -0.35):
            matches.append(component)
    assert len(matches) == 1, 'Expected one isolated lower scarf drape'
    return {i for i, key in enumerate(keys) if key in matches[0]}


def merge_tail(original, tail):
    removed = tail_indices(original)
    count = len(original.attrib['p']) // 3
    keep = [i for i in range(count) if i not in removed]
    mapping = {old: new for new, old in enumerate(keep)}
    result = copy.deepcopy(original)
    for key, stride in (('p', 3), ('n', 3), ('ta', 4), ('u0', 2)):
        result.attrib[key] = [
            v for i in keep for v in original.attrib[key][i * stride:(i + 1) * stride]
        ] + tail.attrib[key]
    triangles = original.attrib['tri']
    result.attrib['tri'] = []
    for offset in range(0, len(triangles), 3):
        face = triangles[offset:offset + 3]
        assert all(i in removed for i in face) or all(i not in removed for i in face)
        if face[0] not in removed:
            result.attrib['tri'].extend(mapping[i] for i in face)
    result.attrib['tri'].extend(i + len(keep) for i in tail.attrib['tri'])
    old_skin = original.find('skin').attrib
    new_skin = tail.find('skin').attrib
    stride = old_skin['bones'][0]
    assert new_skin['bones'][0] == stride
    for key in ('ix', 'w'):
        result.find('skin').attrib[key] = [
            v for i in keep for v in old_skin[key][i * stride:(i + 1) * stride]
        ] + new_skin[key]
    return result


def export_bytes():
    import bpy

    sys.path.insert(0, str(
        Path.home()
        / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'
    ))
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    gear = bpy.data.objects['Shabrat_scarf_tail']
    bpy.ops.object.select_all(action='DESELECT')
    gear.select_set(True)
    bpy.context.view_layer.objects.active = gear
    original = pdx_data.read_meshfile(str(TARGET))
    result = copy.deepcopy(original)
    target_shape = next(
        shape for shape in result.find('object') if 'equipment' in shape.tag
    )
    with tempfile.TemporaryDirectory(prefix='adiscord-scarf-') as directory:
        exported = Path(directory) / 'equipment.mesh'
        pdx.export_meshfile(str(exported), exp_selected=True, exp_locs=False)
        tree = pdx_data.read_meshfile(str(exported))
        source_shape = next(iter(tree.find('object')))
        replacement = source_shape.find('mesh')
        old_mesh = target_shape.find('mesh')
        bone_ids = {
            bone.tag: index for index, bone in enumerate(target_shape.find('skeleton'))
        }
        remap = [bone_ids[bone.tag] for bone in source_shape.find('skeleton')]
        skin = replacement.find('skin').attrib
        skin['ix'] = [remap[index] for index in skin['ix']]
        replacement = merge_tail(old_mesh, replacement)
        target_shape.remove(old_mesh)
        target_shape.insert(0, replacement)
        pdx_data.write_meshfile(str(exported), result)
        # Keep the native body, skeletons and locator tail byte-for-byte intact.
        old_bytes = TARGET.read_bytes()
        new_bytes = exported.read_bytes()
        shape_marker = b'[[Shabrat_equipmentShape\0'
        mesh_marker = b'[[[mesh\0'
        skeleton_marker = b'[[[skeleton\0'
        old_start = old_bytes.index(mesh_marker, old_bytes.index(shape_marker))
        old_end = old_bytes.index(skeleton_marker, old_start)
        new_start = new_bytes.index(mesh_marker, new_bytes.index(shape_marker))
        new_end = new_bytes.index(skeleton_marker, new_start)
        final = old_bytes[:old_start] + new_bytes[new_start:new_end] + old_bytes[old_end:]
        exported.write_bytes(final)
        reread = pdx_data.read_meshfile(str(exported))
        assert ET.tostring(original.find('locator')) == ET.tostring(reread.find('locator'))
        for before, after in zip(original.find('object'), reread.find('object'), strict=True):
            assert ET.tostring(before.find('skeleton')) == ET.tostring(after.find('skeleton'))
            if 'equipment' not in before.tag:
                assert ET.tostring(before) == ET.tostring(after)
        return exported.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true')
    action.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    data = export_bytes()
    changed = TARGET.read_bytes() != data
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    if args.apply and changed:
        TARGET.write_bytes(data)
    print(f'Resistance infantry: changed={changed}, applied={args.apply}')
    if args.check and changed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
