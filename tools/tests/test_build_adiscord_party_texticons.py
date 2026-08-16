from __future__ import annotations

import copy
import io
import hashlib
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.builders import build_adiscord_party_texticons as builder


EXPECTED_EXISTING = {
    "ivn_roar_of_freedom",
    "ivn_emergency_committee",
    "tva_wartime_technocratic_worker",
    "vad_vorkerland_imperial",
    "zao_independent_party",
    "pwr_independent_party",
    "vla_independent_party",
    "rom_independent_party",
    "sol_independent_party",
    "tru_independent_party",
}
EXPECTED_COUNTRIES = {f"{tag.lower()}_primary_party" for tag in {
    "BBV", "BCM", "BGT", "BHG", "BJK", "BLD", "BTL", "COF",
    "DAN", "EFL", "NAM", "PIV", "RUS", "TFF", "WIT", "YPR",
}}
EXPECTED_GENERIC = {
    "humanism": {"civic", "reform", "solidarity"},
    "utilitarism": {"planning", "productive_union", "public_benefit"},
    "chauvinism": {"national_front", "martial_league", "traditional_order"},
    "pragmatism": {"administrative_coalition", "commercial_bloc", "regional_establishment"},
    "anarchism": {"communal_federation", "artel_union", "frontier_movement"},
    "technocracy": {"scientific_collegium", "engineering_directorate", "systems_bureau"},
    "etatism": {"state_party", "military_committee", "emergency_administration"},
    "hedonism": {"aristocratic_houses", "guild_elite", "cultural_club"},
}
EXPECTED_PROTECTED = {
    "gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png": "a0e2b87a270e50c91e568b9d915746367a4e81ad92f746e48e731530d8cc518f",
    "gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png": "f703bd763cd3e4bbf44b9d34b14256337e481333867e261127b7c11e7c74b552",
    "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png": "5fdd08f8522281ff6948e43dd58ddc982a47100528216885a9a895b61084c76f",
}


def expected_asset_keys() -> set[str]:
    generic = {
        f"generic_{ideology}_{archetype}"
        for ideology, archetypes in EXPECTED_GENERIC.items()
        for archetype in archetypes
    }
    return EXPECTED_EXISTING | EXPECTED_COUNTRIES | generic | {"unknown_party"}


class PartyTexticonBuilderTests(unittest.TestCase):
    def test_catalog_covers_exact_generated_protected_and_assignment_contract(self) -> None:
        catalog_path = builder.ROOT / "tools/data/adiscord_party_texticons.json"
        self.assertTrue(catalog_path.is_file(), catalog_path)
        self.assertEqual({asset.key for asset in builder.ASSETS}, expected_asset_keys())
        self.assertEqual(len(builder.ASSETS), 51)
        self.assertEqual({asset.runtime_size for asset in builder.ASSETS}, {(32, 32)})
        self.assertEqual(
            {protected.output.as_posix(): protected.sha256 for protected in builder.PROTECTED},
            EXPECTED_PROTECTED,
        )
        self.assertEqual(len(builder.ASSIGNMENTS), 16)

        generated_fields = {
            value
            for asset in builder.ASSETS
            for value in (
                asset.key,
                asset.source.as_posix() if asset.source is not None else "",
                asset.output.as_posix(),
                asset.sprite,
            )
        }
        self.assertFalse(any("NOD" in value.upper() for value in generated_fields))

    def test_protected_legacy_pngs_remain_exact_25px_bytes(self) -> None:
        for relative, expected_hash in EXPECTED_PROTECTED.items():
            path = builder.ROOT / relative
            with self.subTest(path=relative), Image.open(path) as image:
                self.assertEqual(image.size, (25, 25))
                self.assertEqual(image.mode, "RGBA")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_hash)

    def test_render_icon_is_deterministic_rgba_with_clear_padding(self) -> None:
        self.assertIn("runtime_size", inspect.signature(builder.render_icon).parameters)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.png"
            image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((72, 36, 440, 476), fill=(190, 30, 20, 255))
            image.save(source)

            for runtime_size in ((25, 25), (32, 32)):
                with self.subTest(runtime_size=runtime_size):
                    first = builder.render_icon(source, runtime_size)
                    second = builder.render_icon(source, runtime_size)
                    self.assertEqual(first, second)
                    with Image.open(io.BytesIO(first)) as rendered:
                        self.assertEqual(rendered.mode, "RGBA")
                        self.assertEqual(rendered.size, runtime_size)
                        self.assertIsNotNone(rendered.getchannel("A").getbbox())
                        width, height = runtime_size
                        for corner in (
                            (0, 0),
                            (width - 1, 0),
                            (0, height - 1),
                            (width - 1, height - 1),
                        ):
                            self.assertEqual(rendered.getpixel(corner)[3], 0)

    def test_render_white_flag_is_deterministic_rgba_with_readable_motif(self) -> None:
        first = builder.render_white_flag((32, 32))
        second = builder.render_white_flag((32, 32))
        self.assertEqual(first, second)
        with Image.open(io.BytesIO(first)) as rendered:
            self.assertEqual(rendered.mode, "RGBA")
            self.assertEqual(rendered.size, (32, 32))
            alpha = rendered.getchannel("A")
            self.assertIsNotNone(alpha.getbbox())
            for corner in ((0, 0), (31, 0), (0, 31), (31, 31)):
                self.assertEqual(rendered.getpixel(corner)[3], 0)
            opaque = [
                rendered.getpixel((x, y))
                for y in range(32)
                for x in range(32)
                if alpha.getpixel((x, y)) > 0
            ]
            self.assertGreater(sum(min(pixel[:3]) >= 220 for pixel in opaque), 20)
            self.assertGreater(sum(max(pixel[:3]) <= 60 for pixel in opaque), 20)

    def test_every_master_render_has_a_transparent_outer_border(self) -> None:
        for asset in builder.ASSETS:
            if asset.source is None:
                continue
            with self.subTest(asset=asset.key):
                rendered = Image.open(
                    io.BytesIO(builder.render_icon(builder.ROOT / asset.source, asset.runtime_size))
                )
                self.assertEqual(rendered.size, (32, 32))
                self.assertEqual(rendered.mode, "RGBA")
                alpha = rendered.getchannel("A")
                border = [
                    *(alpha.getpixel((x, 0)) for x in range(32)),
                    *(alpha.getpixel((x, 31)) for x in range(32)),
                    *(alpha.getpixel((0, y)) for y in range(1, 31)),
                    *(alpha.getpixel((31, y)) for y in range(1, 31)),
                ]
                self.assertEqual(set(border), {0})

    def test_registry_has_exact_54_sprite_order_and_eager_entries(self) -> None:
        registry = builder.render_registry().decode("utf-8")
        names = re.findall(r'\bname\s*=\s*"([^"]+)"', registry)
        existing = [asset.sprite for asset in builder.ASSETS if asset.asset_class == "existing"]
        countries = [asset.sprite for asset in builder.ASSETS if asset.asset_class == "country"]
        generic = [asset.sprite for asset in builder.ASSETS if asset.asset_class == "generic"]
        expected = [
            "GFX_unknown_party_texticon",
            "GFX_WRK_worker_revolutionary_party_texticon",
            "GFX_STP_hedonist_party_texticon",
            "GFX_VAL_etatist_party_texticon",
            *existing,
            *countries,
            *generic,
        ]
        self.assertEqual(names, expected)
        self.assertEqual(len(names), 54)
        self.assertEqual(len(set(names)), 54)
        self.assertEqual(registry.count("legacy_lazy_load = no"), 54)
        self.assertNotIn("\r", registry)

    def test_contact_sheets_have_exact_paths_and_dimensions(self) -> None:
        reports = builder.render_contact_sheets()
        country = builder.ROOT / "docs/superpowers/reports/2026-08-16-adiscord-party-country-emblems-contact-sheet.png"
        generic = builder.ROOT / "docs/superpowers/reports/2026-08-16-adiscord-party-generic-emblems-contact-sheet.png"
        self.assertEqual(set(reports), {country, generic})
        with Image.open(io.BytesIO(reports[country])) as image:
            self.assertEqual(image.size, (1024, 1024))
        with Image.open(io.BytesIO(reports[generic])) as image:
            self.assertEqual(image.size, (960, 2048))

    def test_expected_outputs_exclude_protected_and_cover_complete_generated_set(self) -> None:
        outputs = builder.expected_outputs()
        expected_runtime = {builder.ROOT / asset.output for asset in builder.ASSETS}
        expected_registry = builder.ROOT / "interface/parties_texticons.gfx"
        expected_reports = {
            builder.ROOT / "docs/superpowers/reports/2026-08-16-adiscord-party-country-emblems-contact-sheet.png",
            builder.ROOT / "docs/superpowers/reports/2026-08-16-adiscord-party-generic-emblems-contact-sheet.png",
        }
        self.assertEqual(set(outputs), expected_runtime | {expected_registry} | expected_reports)
        self.assertEqual(len(expected_runtime), 51)
        self.assertEqual(len(outputs), 54)
        self.assertTrue({builder.ROOT / item.output for item in builder.PROTECTED}.isdisjoint(outputs))

    def test_catalog_loader_rejects_every_invalid_record_class(self) -> None:
        base = {
            "schema": 1,
            "generated_assets": [{
                "key": "test_party",
                "class": "country",
                "source_kind": "master",
                "source": "source.png",
                "output": "output.png",
                "sprite": "GFX_TEST_party_texticon",
                "runtime_size": [32, 32],
            }],
            "protected_legacy": [{
                "key": "protected_party",
                "output": "protected.png",
                "sprite": "GFX_PROTECTED_party_texticon",
                "sha256": hashlib.sha256(b"protected").hexdigest(),
                "runtime_size": [25, 25],
            }],
            "country_assignments": [{
                "party_key": "TEST_humanism_party",
                "sprite": "GFX_TEST_party_texticon",
            }],
        }
        invalid: list[tuple[str, dict[str, object]]] = []

        candidate = copy.deepcopy(base)
        candidate["schema"] = 2
        invalid.append(("schema", candidate))
        candidate = copy.deepcopy(base)
        del candidate["generated_assets"][0]["sprite"]
        invalid.append(("missing field", candidate))
        candidate = copy.deepcopy(base)
        candidate["generated_assets"][0]["class"] = "mystery"
        invalid.append(("unknown class", candidate))
        candidate = copy.deepcopy(base)
        candidate["generated_assets"][0]["source_kind"] = "mystery"
        invalid.append(("unknown source kind", candidate))
        candidate = copy.deepcopy(base)
        candidate["generated_assets"][0]["runtime_size"] = [25, 25]
        invalid.append(("generated size", candidate))
        for field, replacement in (
            ("key", "other_party"),
            ("source", "other_source.png"),
            ("output", "other_output.png"),
            ("sprite", "GFX_OTHER_party_texticon"),
        ):
            candidate = copy.deepcopy(base)
            duplicate = copy.deepcopy(candidate["generated_assets"][0])
            for unique_field, unique_value in (
                ("key", "other_party"),
                ("source", "other_source.png"),
                ("output", "other_output.png"),
                ("sprite", "GFX_OTHER_party_texticon"),
            ):
                duplicate[unique_field] = unique_value
            duplicate[field] = candidate["generated_assets"][0][field]
            candidate["generated_assets"].append(duplicate)
            invalid.append((f"duplicate {field}", candidate))
        candidate = copy.deepcopy(base)
        candidate["generated_assets"][0]["source"] = "missing.png"
        invalid.append(("missing master", candidate))
        candidate = copy.deepcopy(base)
        candidate["protected_legacy"][0]["output"] = "missing.png"
        invalid.append(("missing protected", candidate))
        candidate = copy.deepcopy(base)
        candidate["protected_legacy"][0]["sha256"] = "A" * 64
        invalid.append(("invalid hash", candidate))
        candidate = copy.deepcopy(base)
        candidate["country_assignments"][0]["sprite"] = "GFX_UNDECLARED_party_texticon"
        invalid.append(("undeclared assignment", candidate))
        candidate = copy.deepcopy(base)
        candidate["generated_assets"][0]["key"] = "nod_specific_party"
        invalid.append(("NOD generated record", candidate))

        for label, catalog in invalid:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "tools/data").mkdir(parents=True)
                (root / "source.png").write_bytes(b"source")
                (root / "other_source.png").write_bytes(b"source")
                (root / "protected.png").write_bytes(b"protected")
                (root / builder.CATALOG_PATH).write_text(json.dumps(catalog), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    builder.load_catalog(root)

    def test_protected_mismatch_blocks_check_and_apply_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools/data").mkdir(parents=True)
            source = root / "source.png"
            Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(source)
            protected = root / "protected.png"
            Image.new("RGBA", (25, 25), (20, 30, 40, 255)).save(protected)
            original_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
            catalog = {
                "schema": 1,
                "generated_assets": [{
                    "key": "test_party",
                    "class": "country",
                    "source_kind": "master",
                    "source": "source.png",
                    "output": "output.png",
                    "sprite": "GFX_TEST_party_texticon",
                    "runtime_size": [32, 32],
                }],
                "protected_legacy": [{
                    "key": "protected_party",
                    "output": "protected.png",
                    "sprite": "GFX_PROTECTED_party_texticon",
                    "sha256": original_hash,
                    "runtime_size": [25, 25],
                }],
                "country_assignments": [{
                    "party_key": "TEST_humanism_party",
                    "sprite": "GFX_TEST_party_texticon",
                }],
            }
            (root / builder.CATALOG_PATH).write_text(json.dumps(catalog), encoding="utf-8")
            protected.write_bytes(b"tampered")

            issues = builder.drift(root)
            self.assertTrue(any("protected party texticon" in issue for issue in issues))
            with self.assertRaises(RuntimeError):
                builder.apply(root)
            self.assertFalse((root / "output.png").exists())

    def test_runtime_outputs_are_current(self) -> None:
        self.assertEqual(builder.drift(), [])
        for asset in builder.ASSETS:
            with self.subTest(asset=asset.key), Image.open(builder.ROOT / asset.output) as image:
                self.assertEqual(image.mode, "RGBA")
                runtime_size = asset.runtime_size
                self.assertEqual(image.size, runtime_size)
                self.assertIsNotNone(image.getchannel("A").getbbox())
                width, height = runtime_size
                for corner in (
                    (0, 0),
                    (width - 1, 0),
                    (0, height - 1),
                    (width - 1, height - 1),
                ):
                    self.assertEqual(image.getpixel(corner)[3], 0)


if __name__ == "__main__":
    unittest.main()
