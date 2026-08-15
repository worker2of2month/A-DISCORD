from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPRITES = {
    "GFX_IVN_roar_of_freedom_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png",
    "GFX_IVN_emergency_committee_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png",
    "GFX_TVA_wartime_technocratic_worker_party_texticon": "gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png",
    "GFX_VAD_vorkerland_imperial_party_texticon": "gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png",
    "GFX_ZAO_independent_party_texticon": "gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png",
    "GFX_PWR_independent_party_texticon": "gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png",
    "GFX_VLA_independent_party_texticon": "gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png",
    "GFX_ROM_independent_party_texticon": "gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png",
    "GFX_SOL_independent_party_texticon": "gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png",
    "GFX_TRU_independent_party_texticon": "gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class PartyTexticonContractTests(unittest.TestCase):
    def test_all_new_sprites_resolve_to_generated_icons(self) -> None:
        gfx = read("interface/parties_texticons.gfx")
        for sprite, texture in SPRITES.items():
            with self.subTest(sprite=sprite):
                block = re.search(
                    rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{sprite}"(?:(?!spriteType).)*\}}',
                    gfx,
                )
                self.assertIsNotNone(block)
                self.assertIn(f'texturefile = "{texture}"', block.group(0))
                self.assertIn("legacy_lazy_load = no", block.group(0))
                self.assertTrue((ROOT / texture).is_file())

    def test_requested_ivn_and_tva_names_have_unique_icons(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        collapse = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertIn('IVN_humanism_party: "£GFX_IVN_roar_of_freedom_party_texticon Рёв свободы"', parties)
        self.assertIn('IVN_etatism_party: "£GFX_IVN_emergency_committee_party_texticon Чрезвычайный комитет Иторы"', parties)
        self.assertIn('TVA_technocracy_party: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)
        self.assertIn('TVA_technocracy_party_long: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)

    def test_successor_helper_keys_cover_dependency_and_independence(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        for tag in ("VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"):
            self.assertIn(f"{tag}_pragmatism_party_independent:", parties)
        for key in (
            "VAD_vorkerland_imperial_party",
            "VAD_vorkerland_imperial_party_wrk_subject",
            "PWR_technocracy_party_wrk_subject",
            "ROM_etatism_party_wrk_subject",
            "TRU_chauvinism_party_wrk_subject",
        ):
            self.assertIn(f"{key}:", parties)
        for key in (
            "VAD_pragmatism_party",
            "ZAO_pragmatism_party",
            "PWR_pragmatism_party",
            "VLA_pragmatism_party",
            "ROM_pragmatism_party",
            "SOL_pragmatism_party",
            "TRU_pragmatism_party",
        ):
            line = next(line for line in parties.splitlines() if line.strip().startswith(f"{key}:"))
            self.assertIn("£GFX_WRK_worker_revolutionary_party_texticon", line)

    def test_russian_localisation_files_keep_utf8_bom(self) -> None:
        for relative in (
            "localisation/russian/parties_l_russian.yml",
            "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        ):
            self.assertTrue((ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"), relative)


if __name__ == "__main__":
    unittest.main()
