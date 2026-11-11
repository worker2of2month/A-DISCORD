"""Native operation artwork coverage and dossier layout contracts."""

import hashlib
import json
import unittest

from PIL import Image

from tools.builders import build_adiscord_operation_art as art
from tools.builders import build_adiscord_intelligence_ui_assets as ui
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


def named_hierarchy(entries, parents=()):
    result = []
    for entry in entries:
        if not isinstance(entry.value, list):
            continue
        name = next((item.value for item in entry.value if item.key == "name"), None)
        path = parents + ((entry.key, name),) if name else parents
        if name:
            result.append(path)
        result.extend(named_hierarchy(entry.value, path))
    return result


class OperationArtTests(unittest.TestCase):
    def test_script_only_wars_have_no_coordinated_strike_operation(self):
        descriptor = (art.ROOT / "descriptor.mod").read_text(encoding="utf-8")
        self.assertIn('replace_path="common/operations"', descriptor)
        operations = [entry for path in art.overlaid_files("common/operations") for entry in art.read_entries(path)]
        self.assertNotIn("operation_coordinated_strike", {entry.key for entry in operations})
        self.assertNotIn("GFX_operations_coordinated_strike", art.native_bindings())

    def test_registered_owners_cover_all_art_and_ui_outputs(self):
        registry = json.loads((art.ROOT / "tools/data/generated_output_owners.json").read_text(encoding="utf-8"))
        entries = {row["id"]: row for row in registry["families"]}
        entry = entries["operation_art"]
        self.assertEqual(set(entry["output_globs"]), {row["path"] for row in art.load_manifest()["bindings"].values()})
        self.assertEqual(entry["check_command"], ["{python}", "-B", "-m", entry["owner_module"]])
        self.assertEqual(entry["apply_command"], entry["check_command"] + ["--apply"])
        self.assertEqual(set(entries["intelligence_ui_assets"]["output_globs"]), {
            path.relative_to(art.ROOT).as_posix() for path in ui.expected_outputs(include_preview=True)
        })

    def test_every_reachable_card_and_phase_has_matching_export(self):
        manifest = art.load_manifest()
        bindings = art.native_bindings()
        self.assertTrue(set(bindings).issubset(manifest["bindings"]))
        for sprite, binding in bindings.items():
            row = manifest["bindings"][sprite]
            self.assertEqual(row["path"], binding["path"], sprite)
            self.assertEqual(row["size"], binding["size"], sprite)
            self.assertIn(row["scene"], manifest["scenes"])
            path = art.ROOT / row["path"]
            with Image.open(path) as image:
                self.assertEqual(list(image.size), row["size"], sprite)
                self.assertEqual(image.mode, "RGBA")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])

    def test_selected_rescue_and_false_intelligence_variants(self):
        scenes = art.load_manifest()["scenes"]
        self.assertEqual(scenes["rescue"]["redaction"], "rescue_group")
        for name, scene in scenes.items():
            if name != "rescue":
                self.assertEqual(scene["redaction"], "agent_only", name)
        self.assertIn("Remove the whole miniature", scenes["false_intelligence"]["edits"][-1])

    def test_neutral_crt_does_not_turn_blacks_into_grey(self):
        source = Image.new("RGBA", (420, 352), (0, 0, 0, 255))
        overlay = Image.new("RGBA", (895, 510), (128, 128, 128, 60))
        image = art.finish_photo(source, overlay, (210, 176))
        self.assertEqual(image.size, (210, 176))
        self.assertEqual(image.getpixel((100, 100)), (0, 0, 0, 255))

    def test_operation_window_preserves_native_named_hierarchy(self):
        source = ui._verified_source("operationoverview.gui").decode("utf-8-sig")
        output = (ui.ROOT / "interface/operationoverview.gui").read_text(encoding="utf-8")
        self.assertEqual(named_hierarchy(parse_clausewitz(source)), named_hierarchy(parse_clausewitz(output)))
        self.assertIn('GFX_ADISCORD_intelligence_dossier_top', output)
        start, end = ui._named_block_bounds(output, "containerWindowType", "phase_title_title")
        self.assertRegex(output[start:end], r'position\s*=\s*\{ x=20 y=124 \}')


if __name__ == "__main__":
    unittest.main()
