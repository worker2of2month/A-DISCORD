"""Factory entity loading, native state effects and shared-registry isolation."""

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tools.builders import build_adiscord_factory_models as builder
from tools.lib import generated_outputs


class FactoryModelTests(unittest.TestCase):
    def test_factory_ownership_entry_is_valid_independently(self):
        registry = json.loads((builder.ROOT / generated_outputs.REGISTRY_PATH).read_text())
        entry = next(item for item in registry['families'] if item['id'] == 'factory_models')
        self.assertEqual(registry['apply_sequence'].count('factory_models'), 1)
        self.assertEqual(entry['source_inputs'], [p.as_posix() for p in builder.INPUTS])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            path.write_text(json.dumps({'schema': 1, 'families': [entry], 'apply_sequence': ['factory_models']}))
            with patch.object(generated_outputs, 'REGISTRY_PATH', path):
                self.assertEqual(generated_outputs.load_registry(builder.ROOT)['families'], [entry])

    def test_native_packages_have_distinct_meshes_and_one_shared_material(self):
        self.assertEqual(builder.stale_outputs(), [])
        report = json.loads((builder.ROOT / builder.REPORT).read_text())
        self.assertTrue(report['native_reimport'])
        self.assertEqual(set(report['models']), {'civilian', 'military'})
        hashes = []
        for kind, model in report['models'].items():
            with self.subTest(kind=kind):
                self.assertEqual(model['materials'], 1)
                self.assertLess(model['triangles'], 3500)
                self.assertEqual(model['entity'], 'building_' + builder.KINDS[kind])
                x, y, z = model['bounds_blender_xyz']
                self.assertLess(x[1] - x[0], 2.3)
                self.assertLess(y[1] - y[0], 1.8)
                self.assertGreater(z[1], .9)
                hashes.append(report['files'][builder.model_name(kind) + '.mesh'])
        self.assertEqual(len(set(hashes)), 2)

    def test_loaded_entities_define_working_and_damaged_states_once(self):
        text = (builder.ROOT / 'gfx/entities/zz_ADISCORD_building_entities.asset').read_text()
        for kind, building in builder.KINDS.items():
            entity = builder.entity_text(kind)
            self.assertIn(entity, text)
            self.assertIn('default_state = "idle"', entity)
            self.assertEqual(entity.count('particle = "factory_smoke_particle"'), 1)
            self.assertEqual(entity.count('particle = "building_damaged_particle"'), 2)
            locators = re.findall(r'locator\s*=\s*\{\s*name\s*=\s*"([^"]+)"', entity)
            events = re.findall(r'node\s*=\s*"([^"]+)"', entity)
            self.assertCountEqual(locators, events)
            occurrences = []
            for path in (builder.ROOT / 'gfx/entities').glob('*.asset'):
                source = path.read_text(encoding='utf-8-sig')
                occurrences.extend(re.findall(r'\bname\s*=\s*"building_' + building + '"', source))
            self.assertEqual(len(occurrences), 1)

    def test_section_generation_preserves_other_models_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = b'# Unrelated authored content\r\nentity = { name = "keep_me" }\r\n'
            paths = ('gfx/entities/mapitems_custom.gfx', 'gfx/entities/zz_ADISCORD_building_entities.asset')
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
            with patch.object(builder, 'ROOT', root):
                first = builder.section_outputs()
                for path, content in first.items():
                    self.assertTrue(content.startswith(original))
                    self.assertNotIn(b'\n', content.replace(b'\r\n', b''))
                    path.write_bytes(content)
                self.assertEqual(builder.section_outputs(), first)
                path = root / paths[0]
                path.write_bytes(path.read_bytes() + first[path][len(original):])
                with self.assertRaisesRegex(ValueError, 'Duplicate factory section'):
                    builder.section_outputs()

    def test_native_locator_axes_keep_chimney_height_vertical(self):
        self.assertEqual(builder.native_position((10, -5, 20)), (.7, 1.4, -.35))
        report = json.loads((builder.ROOT / builder.REPORT).read_text())
        for kind, model in report['models'].items():
            for point in model['smoke_native_xyz']:
                self.assertAlmostEqual(point[1], model['bounds_blender_xyz'][2][1], places=5)
            for x, y, z in model['damage_native_xyz']:
                bx, bz, by = model['bounds_blender_xyz']
                self.assertTrue(bx[0] < x < bx[1])
                self.assertTrue(by[0] < y < by[1])
                self.assertTrue(bz[0] < z < bz[1])


if __name__ == '__main__':
    unittest.main()
