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


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise AssertionError(f"unclosed block {name}")


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


class PartyIdentityLifecycleTests(unittest.TestCase):
    def test_sync_effect_covers_exact_successors_and_never_changes_politics(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt")
        sync = named_block(effects, "ADISCORD_vorkerland_sync_party_identity")
        self.assertEqual(set(re.findall(r"\btag\s*=\s*([A-Z]{3})", sync)), {"VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"})
        self.assertIn("OR = { is_subject_of = WRK is_subject_of = WKR }", sync)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_started", sync)
        for ideology in ("pragmatism", "technocracy", "etatism", "chauvinism"):
            self.assertIn(f"ideology = {ideology}", sync)
        for forbidden in ("set_politics", "set_popularities", "add_popularity", "elections_allowed", "promote_character", "country_leader"):
            self.assertNotIn(forbidden, sync)
        self.assertNotIn("tag = NAM", sync)
        self.assertNotIn("tag = DAN", sync)

    def test_fresh_collapse_and_autonomy_entry_points_are_bounded(self) -> None:
        history = read("history/countries/WRK - WorkerLand.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt")
        self.assertIn("ADISCORD_vorkerland_sync_all_party_identities = yes", history)
        apply_cosmetics = events.index("ADISCORD_vorkerland_apply_claimant_cosmetics = yes")
        sync_parties = events.index("ADISCORD_vorkerland_sync_all_party_identities = yes", apply_cosmetics)
        repair_identities = events.index("ADISCORD_vorkerland_repair_claimant_identities = yes", apply_cosmetics)
        self.assertLess(apply_cosmetics, sync_parties)
        self.assertLess(sync_parties, repair_identities)
        for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
            block = named_block(on_actions, hook)
            self.assertIn("ADISCORD_vorkerland_sync_party_identity = yes", block)
        for recurring in ("on_daily", "on_weekly", "on_monthly"):
            self.assertNotIn(recurring, on_actions)


if __name__ == "__main__":
    unittest.main()
