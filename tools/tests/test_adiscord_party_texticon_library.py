from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from PIL import Image

from tools.builders import build_adiscord_party_texticons as builder


ROOT = Path(__file__).resolve().parents[2]
PARTIES_LOCALISATION = ROOT / "localisation/russian/parties_l_russian.yml"
ENTRY_PATTERN = re.compile(r'(?m)^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s*"([^"\r\n]*)"\s*$')
EXPECTED_COUNTRY_NAMES = {
    "BBV_chauvinism_party": "Союз Копья Вашаита",
    "BCM_chauvinism_party": "Межанский Стяг",
    "BGT_chauvinism_party": "Крайтский Орден",
    "BHG_chauvinism_party": "Хачоевская Дружина",
    "BJK_chauvinism_party": "Столичный Стяг Бежайска",
    "BLD_chauvinism_party": "Дворянский Щит Ландроса",
    "BTL_etatism_party": "Республиканский Совет Порядка",
    "COF_anarchism_party": "Вольные Друиды",
    "DAN_etatism_party": "Командование Группы",
    "EFL_chauvinism_party": "Партия Единой Земли",
    "NAM_etatism_party": "Администрация Автономной Зоны",
    "PIV_hedonism_party": "Клуб Сахарных Баронов",
    "RUS_etatism_party": "Держава Хана",
    "TFF_anarchism_party": "Вольные Рейнджеры",
    "WIT_hedonism_party": "Союз Ночных Ламп",
    "YPR_utilitarism_party": "Юборский Комитет Производства",
}


def party_entries() -> dict[str, str]:
    text = PARTIES_LOCALISATION.read_text(encoding="utf-8-sig")
    matches = ENTRY_PATTERN.findall(text)
    entries = dict(matches)
    if len(entries) != len(matches):
        raise AssertionError("parties localisation contains duplicate keys")
    return entries


class PartyTexticonLibraryContractTests(unittest.TestCase):
    def test_country_assignment_pairs_use_their_declared_sprite_prefixes(self) -> None:
        entries = party_entries()
        self.assertEqual(len(builder.ASSIGNMENTS), 16)
        for assignment in builder.ASSIGNMENTS:
            for key in (assignment.party_key, f"{assignment.party_key}_long"):
                with self.subTest(key=key):
                    self.assertIn(key, entries)
                    self.assertTrue(
                        entries[key].startswith(f"£{assignment.sprite} "),
                        f"{key}: {entries[key]!r}",
                    )

    def test_country_assignment_names_match_authored_parties(self) -> None:
        entries = party_entries()
        selected: dict[str, str] = {}
        for assignment in builder.ASSIGNMENTS:
            for key in (assignment.party_key, f"{assignment.party_key}_long"):
                self.assertIn(key, entries)
                selected[key] = re.sub(r"^£GFX_[^ ]+ ", "", entries[key], count=1)
        self.assertEqual(len(selected), 32)
        expected = dict(EXPECTED_COUNTRY_NAMES)
        expected.update({
            key + "_long": value for key, value in EXPECTED_COUNTRY_NAMES.items()
        })
        expected["RUS_etatism_party_long"] = "Государственная партия Хана"
        self.assertDictEqual(selected, expected)

    def test_parties_localisation_keeps_utf8_bom(self) -> None:
        self.assertTrue(PARTIES_LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_all_forty_new_masters_are_large_transparent_rgba_sources(self) -> None:
        masters = [
            asset
            for asset in builder.ASSETS
            if asset.asset_class in {"country", "generic"}
        ]
        self.assertEqual(len(masters), 40)
        self.assertEqual(
            {asset.asset_class for asset in masters},
            {"country", "generic"},
        )
        for asset in masters:
            self.assertIsNotNone(asset.source)
            path = ROOT / asset.source
            with self.subTest(asset=asset.key), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertGreaterEqual(min(image.size), 512)
                alpha = image.getchannel("A")
                self.assertIsNotNone(alpha.getbbox())
                self.assertLess(alpha.getextrema()[0], 255)
                width, height = image.size
                for corner in (
                    (0, 0),
                    (width - 1, 0),
                    (0, height - 1),
                    (width - 1, height - 1),
                ):
                    self.assertEqual(image.getpixel(corner)[3], 0)

    def test_all_fifty_two_generated_runtime_pngs_are_exact_32px_rgba(self) -> None:
        self.assertEqual(len(builder.ASSETS), 52)
        for asset in builder.ASSETS:
            path = ROOT / asset.output
            with self.subTest(asset=asset.key), Image.open(path) as image:
                self.assertEqual(image.size, (32, 32))
                self.assertEqual(image.mode, "RGBA")
                self.assertIsNotNone(image.getchannel("A").getbbox())
                for corner in ((0, 0), (31, 0), (0, 31), (31, 31)):
                    self.assertEqual(image.getpixel(corner)[3], 0)

    def test_all_three_protected_pngs_match_exact_hashes_and_dimensions(self) -> None:
        self.assertEqual(len(builder.PROTECTED), 3)
        self.assertEqual(builder.protected_issues(), [])
        for protected in builder.PROTECTED:
            path = ROOT / protected.output
            with self.subTest(protected=protected.key), Image.open(path) as image:
                self.assertEqual(image.size, (25, 25))
                self.assertEqual(image.mode, "RGBA")
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), protected.sha256
            )

    def test_all_fifty_five_gfx_sprites_resolve_once_to_catalog_paths(self) -> None:
        text = (ROOT / builder.REGISTRY_PATH).read_text(encoding="utf-8")
        blocks = re.findall(r"(?s)spriteType\s*=\s*\{(.*?)\}", text)
        self.assertEqual(len(blocks), 55)
        actual: dict[str, str] = {}
        for block in blocks:
            name_match = re.search(r'\bname\s*=\s*"([^"]+)"', block)
            texture_match = re.search(r'\btexturefile\s*=\s*"([^"]+)"', block)
            self.assertIsNotNone(name_match)
            self.assertIsNotNone(texture_match)
            self.assertIn("legacy_lazy_load = no", block)
            name = name_match.group(1)
            self.assertNotIn(name, actual)
            actual[name] = texture_match.group(1)

        expected = {
            item.sprite: item.output.as_posix()
            for item in (*builder.ASSETS, *builder.PROTECTED)
        }
        self.assertEqual(actual, expected)
        for texture in actual.values():
            self.assertTrue((ROOT / texture).is_file(), texture)

    def test_nod_keeps_stp_sprite_and_has_no_specific_asset(self) -> None:
        localisation = PARTIES_LOCALISATION.read_text(encoding="utf-8-sig")
        entries = dict(
            re.findall(
                r'(?m)^\s*(NOD_hedonism_party(?:_long)?):(?:\d+)?\s*"([^"\r\n]+)"\s*$',
                localisation,
            )
        )
        self.assertEqual(
            set(entries), {"NOD_hedonism_party", "NOD_hedonism_party_long"}
        )
        for value in entries.values():
            self.assertTrue(value.startswith("£GFX_STP_hedonist_party_texticon "))
        self.assertFalse(
            any(
                "NOD" in item.sprite.upper()
                for item in (*builder.ASSETS, *builder.PROTECTED)
            )
        )
        self.assertFalse(
            any("/NOD/" in item.output.as_posix().upper() for item in builder.ASSETS)
        )

    def test_playable_parties_and_minor_governments_have_names_and_icons(self) -> None:
        playable = set(
            "STP STS SRP VAL WRK WKR TVA SHL IVN IVC NAM RUS NOD VAD ZAO "
            "IBA EGC EYR RIV YOR".split()
        )
        ideologies = (
            "humanism utilitarism chauvinism pragmatism anarchism "
            "technocracy etatism hedonism"
        ).split()
        sprites = set()
        for path in (ROOT / "interface").glob("*.gfx"):
            sprites.update(re.findall(
                r'\bname\s*=\s*"(GFX_[^"]+)"',
                path.read_text(encoding="utf-8-sig"),
            ))
        required = []
        for path in (ROOT / "history/countries").glob("*.txt"):
            tag = path.name[:3]
            # These territorial placeholders intentionally conceal their politics.
            if tag in {"RSV", "EXZ"}:
                continue
            ruling = re.search(
                r"ruling_party\s*=\s*(\w+)",
                path.read_text(encoding="utf-8-sig"),
            )
            if ruling:
                required.extend(
                    f"{tag}_{ideology}_party"
                    for ideology in (ideologies if tag in playable else [ruling[1]])
                )
        language_icons = {}
        for language in ("russian", "english"):
            entries = {}
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                text = path.read_text(encoding="utf-8-sig")
                for key, value in ENTRY_PATTERN.findall(text):
                    entries[key] = value
            for base in required:
                icons = []
                for key in (base, base + "_long"):
                    with self.subTest(language=language, key=key):
                        self.assertIn(key, entries)
                        match = re.fullmatch(r"£(GFX_\w+) (\S.*)", entries[key])
                        self.assertIsNotNone(match, entries[key])
                        self.assertIn(match[1], sprites)
                        self.assertNotEqual(match[1], "GFX_unknown_party_texticon")
                        icons.append(match[1])
                self.assertEqual(icons[0], icons[1], base)
                language_icons[language, base] = icons[0]
        for base in required:
            self.assertEqual(
                language_icons["russian", base],
                language_icons["english", base],
                base,
            )
        self.assertEqual(
            len([asset for asset in builder.ASSETS if asset.asset_class == "generic"]),
            24,
        )

    def test_generated_contact_sheets_have_exact_dimensions(self) -> None:
        expected = {
            ROOT / builder.COUNTRY_REPORT_PATH: (1024, 1024),
            ROOT / builder.GENERIC_REPORT_PATH: (960, 2048),
        }
        for path, dimensions in expected.items():
            with self.subTest(path=path.name), Image.open(path) as image:
                self.assertEqual(image.size, dimensions)


if __name__ == "__main__":
    unittest.main()
