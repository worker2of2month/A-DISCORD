from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_superevents import (
    GFX,
    PRESENTATIONS,
    REQUIRED_FILES,
    RU_LOC,
    SCRIPTED_GUI,
    collect_issues,
)


ROOT = Path(__file__).resolve().parents[2]


def copy_contract_tree(destination: Path) -> None:
    for relative in REQUIRED_FILES:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class SupereventContractTests(unittest.TestCase):
    def test_repository_contract_is_clean(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_inventory_order_is_canonical(self) -> None:
        self.assertEqual(
            tuple(item.name for item in PRESENTATIONS),
            (
                "superevent_vorkerland_civilwar",
                "superevent_vorkerland_dirty_opening",
                "superevent_vorkerland_worker_victory",
                "superevent_vorkerland_utilitarian_victory",
                "superevent_vorkerland_vlad_victory",
                "superevent_vorkerland_dorian_victory",
                "superevent_stelander_empire",
                "superevent_stelander_party_victory",
                "superevent_stelander_shabrat_victory",
            ),
        )

    def test_stelander_victory_news_starts_presentation_before_choice(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block

        source = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8-sig")
        for event_id, side in ((71, "party"), (72, "shabrat")):
            event = _event_block(source, f"ADISCORD_STP_cw.{event_id}")
            immediate = event.split("option =", 1)[0]
            self.assertIn("fire_only_once = yes", event)
            self.assertIn("immediate =", immediate)
            self.assertIn(f"flag = superevent_stelander_{side}_victory", immediate)
            self.assertLess(
                immediate.index("ADISCORD_vorkerland_clear_superevent_flags = yes"),
                immediate.index("set_global_flag ="),
            )
            self.assertIn("ADISCORD_vorkerland_play_superevent_sound = yes", immediate)

    def test_stelander_music_starts_on_close_for_the_winning_player(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for side, tag in (("party", "STP"), ("shabrat", "STS")):
            window = blocks(source, rf"^\s*superevent_stelander_{side}_victory\s*=\s*\{{")[0]
            self.assertIn(f"{tag} = {{", window)
            self.assertIn("limit = { is_ai = no }", window)
            self.assertIn('scoped_play_song = "ADISCORD_stp_civil_war_end"', window)
            self.assertLess(window.index("clr_global_flag"), window.index("scoped_play_song"))
        music = ROOT / "music/ADISCORD_stp_civil_war_end.ogg"
        self.assertEqual(music.read_bytes()[:4], b"OggS")
        assets = (ROOT / "music/music.asset").read_text(encoding="utf-8-sig")
        self.assertIn('file = "ADISCORD_stp_civil_war_end.ogg"', assets)

    def test_missing_gfx_binding_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_contract_tree(root)
            path = root / GFX
            source = path.read_text(encoding="utf-8-sig")
            source = source.replace(
                'name = "GFX_superevent_vorkerland_worker_victory"',
                'name = "GFX_superevent_vorkerland_worker_victory_missing"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            self.assertTrue(
                any(
                    "missing or duplicate GFX sprite GFX_superevent_vorkerland_worker_victory"
                    in issue
                    for issue in collect_issues(root)
                )
            )

    def test_orphan_scripted_gui_binding_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_contract_tree(root)
            path = root / SCRIPTED_GUI
            source = path.read_text(encoding="utf-8-sig")
            source += (
                "\nsuperevent_orphan_test = {\n"
                '    window_name = "superevent_orphan_test"\n'
                "}\n"
            )
            path.write_text(source, encoding="utf-8")
            self.assertIn(
                "orphan scripted-GUI presentation superevent_orphan_test",
                collect_issues(root),
            )

    def test_missing_russian_localisation_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_contract_tree(root)
            path = root / RU_LOC
            source = path.read_text(encoding="utf-8-sig")
            source = source.replace(
                '  superevent_vorkerland_dirty_opening_title: "Падение Периметра"\n',
                "",
                1,
            )
            path.write_text("\ufeff" + source, encoding="utf-8")
            self.assertTrue(
                any(
                    "missing or duplicate Russian localisation key "
                    "superevent_vorkerland_dirty_opening_title"
                    in issue
                    for issue in collect_issues(root)
                )
            )


if __name__ == "__main__":
    unittest.main()
