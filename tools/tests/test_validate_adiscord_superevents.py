from __future__ import annotations

import re
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

from tools.validators.validate_adiscord_superevents import (
    GFX,
    PRESENTATIONS,
    PRESENTATIONS_BY_ID,
    REQUIRED_FILES,
    RU_LOC,
    SCRIPTED_GUI,
    collect_issues,
    console_gateway_issues,
)


ROOT = Path(__file__).resolve().parents[2]


def copy_contract_tree(destination: Path) -> None:
    for relative in REQUIRED_FILES:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    art = Path("gfx/interface/superevents")
    shutil.copytree(ROOT / art, destination / art)
    # The binding validator checks paths. The duration test opens the real PCM files.
    audio = Path("sound/superevents")
    (destination / audio).mkdir(parents=True, exist_ok=True)
    for wav in (ROOT / audio).glob("*.wav"):
        (destination / audio / wav.name).touch()


class SupereventContractTests(unittest.TestCase):
    def test_quotes_require_reviewed_text_and_traceable_sources(self):
        from copy import deepcopy
        from tools.validators.validate_adiscord_superevents import (
            EN_LOC, QUOTE_SOURCES, SCRIPTED_LOC, quotation_issues,
        )

        manifest = json.loads((ROOT / QUOTE_SOURCES).read_text(encoding="utf-8"))
        loc = {
            "russian": (ROOT / RU_LOC).read_text(encoding="utf-8-sig"),
            "english": (ROOT / EN_LOC).read_text(encoding="utf-8-sig"),
        }
        scripted = (ROOT / SCRIPTED_LOC).read_text(encoding="utf-8")
        self.assertEqual(quotation_issues(loc, manifest, scripted), [])
        key = "superevent_south_cities_quote"
        changed = dict(loc)
        changed["russian"] = loc["russian"].replace("Народ, подчиняющийся законам", "Приказом правительства")
        self.assertIn(
            f"russian quote: {key} differs from its reviewed citation",
            quotation_issues(changed, manifest, scripted),
        )
        changed["russian"] = loc["russian"].replace('законам, должен', 'законам, "должен')
        self.assertIn(
            f"russian quote: invalid quoted value for {key}",
            quotation_issues(changed, manifest, scripted),
        )
        missing = deepcopy(manifest)
        del missing["quotes"][key]
        self.assertIn(f"quote sources: no reviewed quotation for {key}", quotation_issues(loc, missing, scripted))
        incomplete = deepcopy(manifest)
        incomplete["quotes"][key]["location"] = ""
        self.assertIn(f"quote sources: incomplete citation for {key}", quotation_issues(loc, incomplete, scripted))

    def test_export_never_uses_graded_runtime_as_an_unprocessed_original(self):
        from unittest.mock import patch
        from tools.builders import build_adiscord_superevent_art as art

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "template.psd").write_bytes(b"template fixture")
            (root / "runtime.png").write_bytes(b"graded artwork fixture")
            row = {
                "runtime_file": "runtime.png",
                "source_sha256": art.digest(b"unprocessed artwork fixture"),
                "runtime_sha256": art.digest(b"graded artwork fixture"),
            }
            manifest = {
                "template": {"file": "template.psd", "sha256": art.digest(b"template fixture")},
                "exports": {"fixture": row},
            }
            with patch.object(art, "ROOT", root), patch.object(art, "apply_template") as apply:
                self.assertEqual(art.planned_outputs(manifest, root), {})
                apply.assert_not_called()
                (root / "runtime.png").write_bytes(b"modified graded artwork fixture")
                with self.assertRaisesRegex(ValueError, "Original artwork required"):
                    art.planned_outputs(manifest, root)
                apply.assert_not_called()

    def test_all_live_scenes_are_covered_by_the_art_effect_inventory(self):
        from PIL import Image
        from tools.validators.validate_adiscord_superevents import ART_SOURCES

        manifest = json.loads((ROOT / ART_SOURCES).read_text(encoding="utf-8"))
        covered = {row["runtime_file"] for row in manifest["exports"].values()}
        covered.update(manifest["retained"])
        covered.add("gfx/interface/superevents/IVN/superevent_itora_stalk_portal_background.png")
        live = {row["texture"] for row in manifest["bindings"].values()}
        self.assertFalse(live - covered)
        for row in manifest["exports"].values():
            with self.subTest(texture=row["runtime_file"]):
                with Image.open(ROOT / row["runtime_file"]) as image:
                    self.assertEqual(image.size, (1001, 639))
                    self.assertEqual(image.getchannel("A").getbbox(), (48, 82, 956, 592))

    def test_valid_foreign_assets_cannot_replace_an_endings_scene_or_theme(self):
        from tools.validators.validate_adiscord_superevents import (
            ART_SOURCES, SOUND_EFFECTS, SOUNDS, presentation_asset_issues,
        )

        manifest = json.loads((ROOT / ART_SOURCES).read_text(encoding="utf-8"))
        gfx = (ROOT / GFX).read_text(encoding="utf-8")
        effects = (ROOT / SOUND_EFFECTS).read_text(encoding="utf-8")
        sounds = (ROOT / SOUNDS).read_text(encoding="utf-8")
        self.assertEqual(presentation_asset_issues(gfx, effects, sounds, manifest), [])
        wrong_scene = gfx.replace(
            "STP/superevent_stelander_tikhoreva.png",
            "STP/superevent_stelander_shabrat_victory.png",
        )
        self.assertIn(
            "superevent_stelander_tikhoreva: texture differs from its approved scene",
            presentation_asset_issues(wrong_scene, effects, sounds, manifest),
        )
        wrong_theme = effects.replace(
            "sound = superevent_stelander_party_victory_houses_sound",
            "sound = superevent_stelander_shabrat_victory_sound",
        )
        self.assertIn(
            "superevent_stelander_party_victory_houses: sound effect differs from its approved theme",
            presentation_asset_issues(gfx, wrong_theme, sounds, manifest),
        )
        wrong_audio = sounds.replace(
            "superevents/superevent_stelander_tikhoreva_sound.wav",
            "superevents/superevent_stelander_shabrat_victory_sound.wav",
        )
        self.assertIn(
            "superevent_stelander_tikhoreva: sample differs from its approved audio file",
            presentation_asset_issues(gfx, effects, wrong_audio, manifest),
        )

    def test_council_proclamation_preserves_settlement_and_selects_one_card(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar, block

        decisions = parse_clausewitz(
            (ROOT / "common/decisions/ADISCORD_VAL_decisions.txt").read_text(encoding="utf-8")
        )
        decision = next(
            row.value for category in decisions for row in category.value
            if row.key == "VAL_proclaim_commonwealth"
        )
        payload = block(block(decision, "complete_effect"), "hidden_effect")
        predicates = {
            row.key: row.value for row in parse_clausewitz(
                (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
            )
        }

        def matches(row, leader):
            if row.key == "OR":
                return any(matches(child, leader) for child in row.value)
            if row.key == "has_country_leader":
                self.assertEqual(scalar(row.value, "ruling_only"), "yes")
                return scalar(row.value, "character") == leader
            self.assertEqual(row.value, "yes")
            return all(matches(child, leader) for child in predicates[row.key])

        for leader, expected in (
            ("VAL_Commanders_Council", "ADISCORD_superevent.73"),
            ("VAL_Gleb_Osten", "ADISCORD_superevent.73"),
            ("VAL_Tamara_Greitz", "ADISCORD_superevent.73"),
            ("VAL_Arkadi_Lemm", "ADISCORD_superevent.73"),
            ("VAL_Mikhail_Velsky", "ADISCORD_superevent.73"),
            ("VAL_Valera_Solgalov", "ADISCORD_superevent.9"),
        ):
            with self.subTest(leader=leader):
                calls = []
                matched = False
                for row in payload:
                    if row.key == "VAL_adopt_commonwealth":
                        calls.append((row.key, row.value))
                    elif row.key == "if":
                        matched = all(matches(child, leader) for child in block(row.value, "limit"))
                        if matched:
                            calls.append(("country_event", scalar(block(row.value, "country_event"), "id")))
                    elif row.key == "else":
                        if not matched:
                            calls.append(("country_event", scalar(block(row.value, "country_event"), "id")))
                    else:
                        self.fail(f"Unexpected proclamation effect: {row.key}")
                self.assertEqual(calls, [("VAL_adopt_commonwealth", "yes"), ("country_event", expected)])

    def test_every_presentation_has_a_console_entry_point(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar, block

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        self.assertEqual(console_gateway_issues(source), [])
        for entry in parse_clausewitz(source):
            if entry.key != "country_event":
                continue
            event_id = scalar(entry.value, "id")
            if not event_id.startswith("ADISCORD_superevent."):
                continue
            # These two entry points also select the campaign-specific presentation.
            if event_id in ("ADISCORD_superevent.1", "ADISCORD_superevent.7"):
                continue
            with self.subTest(event_id=event_id):
                self.assertEqual(scalar(entry.value, "hidden"), "yes")
                self.assertEqual(scalar(entry.value, "is_triggered_only"), "yes")
                immediate = block(entry.value, "immediate")
                self.assertEqual(
                    [row.key for row in immediate],
                    ["set_temp_variable", "ADISCORD_superevent_enqueue"],
                )
                request = scalar(block(immediate, "set_temp_variable"), "ADISCORD_superevent_request")
                self.assertIn(int(request), PRESENTATIONS_BY_ID)

    def test_conditional_nam_selector_cannot_replace_a_dedicated_console_entry(self):
        from tools.validators.validate_adiscord_superevents import _event_block

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        source = source.replace(_event_block(source, "ADISCORD_superevent.29"), "")
        self.assertEqual(console_gateway_issues(source), [
            "superevent_nam_resource_war: missing a dedicated ADISCORD_superevent.* entry point"
        ])

    def test_console_entry_rejects_an_unknown_presentation(self):
        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        source = source.replace("ADISCORD_superevent_request = 71", "ADISCORD_superevent_request = 9999")
        self.assertIn(
            "ADISCORD_superevent.72: unknown presentation request 9999",
            console_gateway_issues(source),
        )

    def test_stalk_portal_audio_adds_effects_only_during_visual_flashes(self):
        import array
        import math
        from tools.builders.build_adiscord_superevent_animation import FRAME_COUNT, FPS

        def read_pcm(path):
            with wave.open(str(path)) as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (2, 2, 44100))
                self.assertEqual(audio.getnframes(), FRAME_COUNT * 44100 // FPS)
                return array.array("h", audio.readframes(audio.getnframes()))

        actual = read_pcm(ROOT / "sound/superevents/superevent_itora_stalk_portal_sound.wav")
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / "music.wav"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-i",
                str(ROOT / "tools/assets/source/superevents/IVN/light_in_realitys_shadow_excerpt.flac"),
                "-af", "afade=t=in:d=2,afade=t=out:st=50:d=6,volume=0.85",
                "-t", "56", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(baseline),
            ], check=True)
            music = read_pcm(baseline)
        self.assertLess(max(abs(sample) for sample in actual), 32767)
        flashes = {5, 12, 16, 21, 31, 39, 44, 50}
        for second in range(56):
            start = second * 88200
            residual = [a - b for a, b in zip(actual[start:start + 88200], music[start:start + 88200])]
            if second in flashes:
                self.assertGreater(math.sqrt(sum(value * value for value in residual) / len(residual)), 300, second)
            else:
                self.assertLessEqual(max(abs(value) for value in residual), 1, second)

    def test_stalk_portal_animation_cycles_eight_paintings_between_flashes(self):
        from PIL import Image
        from hashlib import sha256
        from tools.builders.build_adiscord_superevent_animation import STRIP_WIDTHS
        from tools.validators.validate_adiscord_superevents import blocks

        gfx = (ROOT / "interface/superevents.gfx").read_text(encoding="utf-8-sig")
        gui = (ROOT / "interface/superevents.gui").read_text(encoding="utf-8-sig")
        window = next(
            block for block in blocks(gui, r"^\s*containerWindowType\s*=\s*\{")
            if re.search(r'\bname\s*=\s*"superevent_itora_stalk_portal"', block)
        )
        with Image.open(ROOT / "gfx/interface/superevents/IVN/superevent_itora_stalk_portal_background.png") as backdrop:
            self.assertEqual(backdrop.size, (1001, 639))
            self.assertEqual(backdrop.getchannel("A").getbbox(), (48, 82, 956, 592))
            fallback = backdrop.convert("RGB").crop((48, 82, 956, 592))
        expected_portal = (16, 44)
        expected_masks = (5, 12, 21, 31, 39, 50)
        painting_seconds = set(range(56)) - set(expected_portal) - set(expected_masks)
        self.assertEqual(len(painting_seconds), 48)
        offset = 0
        frame_digests = [sha256() for _ in range(56)]
        scripted_gui = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for index, width in enumerate(STRIP_WIDTHS):
            name = f"GFX_ADISCORD_stalk_portal_strip_{index}"
            sprite = next(
                block for block in blocks(gfx, r"^\s*frameAnimatedSpriteType\s*=\s*\{")
                if f'name = "{name}"' in block
            )
            for token in ("noOfFrames = 56", "animation_rate_fps = 1", "looping = no", "play_on_show = yes"):
                self.assertIn(token, sprite)
            icon = next(
                block for block in blocks(window, r"^\s*iconType\s*=\s*\{")
                if f'quadTextureSprite = "{name}"' in block
            )
            self.assertIn(f"position = {{ x = {48 + offset} y = 82 }}", icon)
            self.assertIn('loadType = "INGAME"', sprite)
            self.assertIn("legacy_lazy_load = no", sprite)
            visibility = blocks(scripted_gui, rf"^\s*stalk_portal_strip_{index}_visible\s*=\s*\{{")[0]
            self.assertIn("has_global_flag = superevent_itora_stalk_portal", visibility)
            texture = re.search(r'textureFile\s*=\s*"([^"]+)"', sprite).group(1)
            self.assertTrue((ROOT / texture).read_bytes().startswith(b"DDS "))
            with Image.open(ROOT / texture) as atlas:
                self.assertEqual(atlas.size, (width * 56, 510))
                self.assertLessEqual(atlas.width, 4096)
                pixels = atlas.convert("RGB")
                frames = [
                    pixels.crop((second * width, 0, (second + 1) * width, 510)).tobytes()
                    for second in range(56)
                ]
            fallback_strip = fallback.crop((offset, 0, offset + width, 510)).tobytes()
            self.assertEqual(frames[0], fallback_strip)
            for second, frame in enumerate(frames):
                frame_digests[second].update(frame)
            offset += width
        self.assertEqual(offset, 908)
        digests = [digest.hexdigest() for digest in frame_digests]
        painting_hashes = []
        for group in range(8):
            seconds = [second for second in painting_seconds if second // 7 == group]
            self.assertTrue(seconds)
            self.assertEqual(len({digests[second] for second in seconds}), 1)
            painting_hashes.append(digests[seconds[0]])
        self.assertEqual(len(set(painting_hashes)), 8)
        self.assertEqual(digests[16], digests[44])
        self.assertNotIn(digests[16], painting_hashes)
        self.assertEqual(digests[-1], painting_hashes[-1])
        self.assertTrue(all(digests[second] not in painting_hashes for second in expected_masks))

    def test_map_portal_starts_once_and_covers_the_full_camera_zoom(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.validators.validate_adiscord_superevents import _event_block
        from tools.tests.test_adiscord_stp_preparation import scalar, block

        entities = parse_clausewitz((ROOT / "gfx/entities/mapitems_custom.asset").read_text(encoding="utf-8"))
        for name, idle, active in (
            ("ADISCORD_portal_test_entity", "closed", "open"),
            ("ADISCORD_portal_burst_entity", "spent", "burst"),
        ):
            entity = next(row.value for row in entities if row.key == "entity" and scalar(row.value, "name") == name)
            self.assertEqual(scalar(entity, "default_state"), idle)
            self.assertGreaterEqual(float(scalar(entity, "cull_radius")), 300)
            states = {scalar(row.value, "name"): row.value for row in entity if row.key == "state"}
            self.assertFalse(any(row.key == "event" for row in states[idle]))
            self.assertEqual(scalar(states[active], "looping"), "no")
            particle_events = [row.value for row in states[active] if row.key == "event"]
            self.assertEqual(len(particle_events), 1)
            self.assertEqual(scalar(particle_events[0], "trigger_once"), "yes")
        source = (ROOT / "events/ADISCORD_scenario_debug_events.txt").read_text(encoding="utf-8")
        opening = parse_clausewitz(_event_block(source, "ADISCORD_portal_test.1"))[0].value
        state = block(block(opening, "immediate"), "218")
        creations = [row.value for row in state if row.key == "create_entity"]
        self.assertEqual({scalar(row, "id") for row in creations}, {"610777", "610778"})
        self.assertTrue(all(float(scalar(row, "min_zoom")) > 3000 for row in creations))
        self.assertEqual(sum(row.key == "set_entity_animation" for row in state), 2)
        cleanup = parse_clausewitz(_event_block(source, "ADISCORD_portal_test.2"))[0].value
        self.assertEqual(scalar(block(block(cleanup, "immediate"), "218"), "destroy_entity"), "610778")
        meshes = (ROOT / "gfx/entities/mapitems_custom.gfx").read_text(encoding="utf-8")
        from tools.validators.validate_adiscord_superevents import blocks
        mesh = next(row for row in blocks(meshes, r"^\s*pdxmesh\s*=\s*\{") if 'name = "ADISCORD_portal_test_mesh"' in row)
        self.assertIn("cull_distance = 10000.0", mesh)

    def test_imperium_runtime_exports_match_the_card_and_audio_contract(self):
        from PIL import Image
        import array

        with Image.open(ROOT / "gfx/interface/superevents/IVN/superevent_itora_legion_victory.png") as art:
            self.assertEqual(art.size, (1001, 639))
            self.assertEqual(art.getbbox(), (48, 82, 956, 592))
        for folder, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            flag = ROOT / "gfx/flags" / folder / "IVN_unified_legion.tga"
            with Image.open(flag) as image:
                self.assertEqual(image.size, size)
            self.assertEqual(flag.read_bytes()[16], 32)
        with wave.open(str(ROOT / "sound/superevents/superevent_itora_legion_victory_sound.wav")) as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (2, 2, 44100))
            self.assertEqual(audio.getnframes(), 56 * 44100)
            samples = array.array("h", audio.readframes(audio.getnframes()))
        self.assertLess(max(abs(sample) for sample in samples), 32767)
        for start, end in ((0, 4), (4, 8), (8, 10), (10, 52)):
            segment = samples[start * 88200:end * 88200]
            self.assertGreater(sum(abs(sample) for sample in segment) / len(segment), 100)

    def test_legion_victory_presentation_keeps_preview_separate_from_settlement(self):
        from tools.validators.validate_adiscord_superevents import _event_block
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects

        source = (ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt").read_text(encoding="utf-8")
        definitions = {entry.key: entry.value for entry in parse_clausewitz(source)}
        for winner in ("legion", "cabinet", "directory", "communes", "marches"):
            facts = {("IVN", "has_global_flag", f"IVN_civil_war_won_by_{winner}"): True}
            selected = list(selected_effects(definitions["IVN_resolve_marches_revolt"], facts, "IVN"))
            calls = [row for _, row in selected if row.key == "IVN_show_legion_victory_superevent"]
            self.assertEqual(len(calls), int(winner == "legion"), winner)
        event_source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = parse_clausewitz(_event_block(event_source, "ADISCORD_superevent.23"))[0].value
        immediate = block(event, "immediate")
        self.assertEqual([entry.key for entry in immediate], ["set_temp_variable", "ADISCORD_superevent_enqueue"])
        self.assertEqual(scalar(block(immediate, "set_temp_variable"), "ADISCORD_superevent_request"), "72")
        self.assertEqual(PRESENTATIONS_BY_ID[72].name, "superevent_itora_legion_victory")

    def test_committee_victory_presentation_keeps_preview_separate_from_settlement(self):
        from tools.validators.validate_adiscord_superevents import _event_block
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects

        source = (ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt").read_text(encoding="utf-8")
        definitions = {entry.key: entry.value for entry in parse_clausewitz(source)}
        for winner in ("legion", "cabinet", "directory", "communes", "marches"):
            facts = {("IVN", "has_global_flag", f"IVN_civil_war_won_by_{winner}"): True}
            selected = list(selected_effects(definitions["IVN_resolve_marches_revolt"], facts, "IVN"))
            calls = [row for _, row in selected if row.key == "IVN_show_committee_victory_superevent"]
            self.assertEqual(len(calls), int(winner == "cabinet"), winner)
        event_source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = parse_clausewitz(_event_block(event_source, "ADISCORD_superevent.24"))[0].value
        immediate = block(event, "immediate")
        self.assertEqual([entry.key for entry in immediate], ["set_temp_variable", "ADISCORD_superevent_enqueue"])
        self.assertEqual(scalar(block(immediate, "set_temp_variable"), "ADISCORD_superevent_request"), "73")
        self.assertEqual(PRESENTATIONS_BY_ID[73].name, "superevent_itora_committee_victory")

    def test_stalk_portal_is_a_dormant_presentation_without_campaign_entry_point(self):
        from tools.validators.validate_adiscord_superevents import _event_block
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block, scalar

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = parse_clausewitz(_event_block(source, "ADISCORD_superevent.25"))[0].value
        self.assertEqual(scalar(event, "is_triggered_only"), "yes")
        immediate = block(event, "immediate")
        self.assertEqual([entry.key for entry in immediate], ["set_temp_variable", "ADISCORD_superevent_enqueue"])
        self.assertEqual(scalar(block(immediate, "set_temp_variable"), "ADISCORD_superevent_request"), "74")
        self.assertEqual(PRESENTATIONS_BY_ID[74].name, "superevent_itora_stalk_portal")
        callers = []
        for folder in ("common", "events"):
            for path in (ROOT / folder).rglob("*.txt"):
                if path == ROOT / "events/ADISCORD_superevents.txt":
                    continue
                if "ADISCORD_superevent.25" in path.read_text(encoding="utf-8-sig"):
                    callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])

    def test_nam_veyran_proclamation_queues_a_card_for_human_and_ai(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        tree = parse_clausewitz(read_focus_source(ROOT / "common/national_focus/ADISCORD_NAM_postwar.txt"))[0].value
        focus = next(row.value for row in tree
                     if row.key == "focus" and scalar(row.value, "id") == "NAM_veyran_union_charter")
        reward = block(focus, "completion_reward")
        for ai in (True, False):
            effects = list(selected_effects(reward, {("NAM", "is_ai"): ai}, "NAM"))
            requests = [scalar(row.value, "ADISCORD_superevent_request")
                        for _, row in effects if row.key == "set_temp_variable"]
            self.assertEqual(requests, ["71"])
            self.assertEqual(sum(row.key == "ADISCORD_superevent_enqueue" for _, row in effects), 1)
            self.assertEqual([row.value for _, row in effects if row.key == "set_cosmetic_tag"],
                             ["NAM_veyran_union"])
            self.assertFalse(any(row.key in ("scoped_play_song", "play_song", "sound_effect")
                                 for _, row in effects))
        self.assertEqual(PRESENTATIONS_BY_ID[71].name, "superevent_nam_veyran_proclamation")
        for path in (ROOT / "music").glob("*.asset"):
            self.assertNotIn('name = "ADISCORD_nam_veyran_proclamation"', path.read_text(encoding="utf-8-sig"))
        self.assertFalse((ROOT / "music/ADISCORD_nam_veyran_proclamation.ogg").exists())

    def test_stelander_personal_victories_select_the_winner_and_keep_previews_safe(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.validators.validate_adiscord_superevents import _event_block

        source = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8")
        event = parse_clausewitz(_event_block(source, "ADISCORD_STP_cw.72"))[0].value
        for receiver in ("STS", "STP", "VAL"):
            for leader, expected in (("STP_grigory_sotnikov", "20"), ("STP_maksim_shabrat", "9")):
                facts = {("STS", "ruling_leader"): leader}
                effects = list(selected_effects(block(event, "immediate"), facts, receiver))
                requests = [scalar(row.value, "ADISCORD_superevent_request")
                            for _, row in effects if row.key == "set_temp_variable"]
                self.assertEqual(requests, [expected], (receiver, leader))
                self.assertEqual(sum(row.key == "ADISCORD_superevent_enqueue" for _, row in effects), 1)

        event = parse_clausewitz(_event_block(source, "ADISCORD_STP_pc.72"))[0].value
        self.assertEqual(scalar(block(event, "trigger"), "STP_pc_sword_directory_current"), "yes")
        self.assertEqual(scalar(event, "fire_only_once"), "yes")
        effects = list(selected_effects(block(event, "immediate"), {}, "STS"))
        requests = [scalar(row.value, "ADISCORD_superevent_request")
                    for _, row in effects if row.key == "set_temp_variable"]
        self.assertEqual(requests, ["21"])

        definitions = {
            node.key: node.value for node in parse_clausewitz(
                (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
            ) if node.key.startswith("STP_pc_charter_")
        }

        def executable_nodes(entries, stack=()):
            for node in entries:
                if node.key in {"effect_tooltip", "custom_effect_tooltip", "trigger", "limit", "ai_chance"}:
                    continue
                yield node
                if isinstance(node.value, list):
                    yield from executable_nodes(node.value, stack)
                elif node.key in definitions:
                    self.assertEqual(node.value, "yes")
                    self.assertNotIn(node.key, stack)
                    yield from executable_nodes(definitions[node.key], stack + (node.key,))

        for story, candidate, request in ((68, "sotnikov", "22"), (69, "shabrat", "23"), (70, "tikhoreva", "24")):
            event = parse_clausewitz(_event_block(source, f"ADISCORD_STP_pc.{story}"))[0].value
            immediate = next((node.value for node in event if node.key == "immediate"), [])
            self.assertNotIn("ADISCORD_superevent_enqueue", {node.key for node in executable_nodes(immediate)})
            for answer in ("a", "b"):
                option = next(node.value for node in event if node.key == "option"
                              and scalar(node.value, "name") == f"ADISCORD_STP_pc.{story}.{answer}")
                actual = list(executable_nodes(option))
                requests = []
                for node in actual:
                    if node.key != "set_temp_variable":
                        continue
                    values = {row.key: row.value for row in node.value}
                    if "ADISCORD_superevent_request" in values:
                        requests.append(values["ADISCORD_superevent_request"])
                    elif values.get("var") == "ADISCORD_superevent_request":
                        requests.append(values["value"])
                expected_requests = [] if candidate == "shabrat" else [request]
                self.assertEqual(requests, expected_requests, (candidate, answer))
                self.assertEqual(sum(node.key == "ADISCORD_superevent_enqueue" for node in actual), len(expected_requests))
                if candidate == "shabrat":
                    self.assertTrue(any(node.key == "unlock_decision_tooltip"
                                        and node.value == "STP_pc_proclaim_stelander_union"
                                        for node in actual))
                self.assertTrue(any(node.key == "add_ideas" and node.value.startswith(f"STP_pc_charter_{candidate}_legacy_")
                                    for node in actual), (candidate, answer))
            provisional = next(node.value for node in event if node.key == "option"
                               and scalar(node.value, "name").endswith((".provisional", ".c")))
            self.assertNotIn("ADISCORD_superevent_enqueue", {node.key for node in executable_nodes(provisional)})

        sotnikov = block(definitions["STP_pc_charter_sotnikov_confirm_legacy"], "if")
        self.assertEqual(scalar(block(sotnikov, "limit"), "STP_pc_charter_sotnikov_legacy_unclaimed"), "yes")
        award_checks = [block(node.value, "limit") for node in sotnikov if node.key == "if"]
        self.assertTrue(any(any(row.key == "STP_pc_charter_sotnikov_legacy_unclaimed" and row.value == "no"
                                for row in check) for check in award_checks))
        for ending in ("districts", "nation"):
            award = block(definitions[f"STP_pc_charter_shabrat_award_{ending}"], "if")
            self.assertEqual(scalar(block(award, "limit"), f"STP_pc_charter_shabrat_{ending}_ready"), "yes")
        tikhoreva = block(definitions["STP_pc_charter_tikhoreva_confirm_legacy"], "if")
        celebration = "STP_pc_charter_tikhoreva_celebrated"
        self.assertEqual(scalar(block(block(tikhoreva, "limit"), "NOT"), "has_country_flag"), celebration)
        self.assertEqual(scalar(tikhoreva, "set_country_flag"), celebration)

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for number in range(17, 22):
            event = parse_clausewitz(_event_block(source, f"ADISCORD_superevent.{number}"))[0].value
            effects = block(event, "immediate")
            self.assertEqual([row.key for row in effects], ["set_temp_variable", "ADISCORD_superevent_enqueue"])
            self.assertEqual(scalar(block(effects, "set_temp_variable"), "ADISCORD_superevent_request"), str(number + 3))

    def test_radio_excludes_superevents_and_preserves_mod_music(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        playlists = list((ROOT / "music").glob("*.txt"))
        songs = "\n".join(path.read_text(encoding="utf-8-sig") for path in playlists)

        for item in PRESENTATIONS:
            self.assertNotIn(f'song = "{item.name}"', songs, item.name)

        guard = (ROOT / "music/ADISCORD_superevent_songs.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("music_station =", guard)
        self.assertNotIn("song =", guard)

        # The silent carrier is the one exception: play_song requires a station
        # registration, while factor 0 keeps it out of weighted shuffle.
        self.assertEqual(songs.count('song = "one_minute_of_silence"'), 1)
        self.assertEqual(songs.count('song = "two_minutes_of_silence"'), 1)
        self.assertNotIn('_after_superevent', songs)
        self.assertEqual(songs.count('song = "ADISCORD_stp_civil_war_end"'), 1)
        self.assertIn('music_station = "adiscord_music"', songs)
        self.assertIn('music_station = "adiscord_special"', songs)
        free = (ROOT / "music/ADISCORD_songs.txt").read_text(encoding="utf-8")
        for entry in parse_clausewitz(free):
            if entry.key == "music":
                chance = next(row.value for row in entry.value if row.key == "chance")
                self.assertEqual([row.key for row in chance], ["base"])
                self.assertGreater(float(chance[0].value), 0)

        # Every radio-visible identifier must resolve to a human title in both
        # shipped languages. Otherwise HOI4 renders the raw script key in the
        # station list (for example ADISCORD_ksb_muzic_war).
        english_music = (ROOT / "localisation/english/ADISCORD_music_l_english.yml").read_text(
            encoding="utf-8-sig"
        )
        russian_music = (ROOT / "localisation/russian/ADISCORD_music_l_russian.yml").read_text(
            encoding="utf-8-sig"
        )
        visible_ids = re.findall(r'(?m)^\s*song\s*=\s*"([^"]+)"\s*$', songs)
        self.assertTrue(visible_ids)
        self.assertEqual(len(visible_ids), len(set(visible_ids)))
        for song in visible_ids:
            for localisation in (english_music, russian_music):
                self.assertRegex(
                    localisation,
                    rf'(?m)^\s*{re.escape(song)}:\d*\s*"[^"\r\n]+"\s*$',
                )
        self.assertIn('replace_path="music"', (ROOT / "descriptor.mod").read_text())
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        from tools.validators.validate_adiscord_superevents import blocks

        main_theme = [
            block for block in blocks(assets, r"^music\s*=\s*\{")
            if 'name = "maintheme"' in block
        ]
        self.assertEqual(len(main_theme), 1)
        main_theme_file = re.search(r'file\s*=\s*"([^"]+)"', main_theme[0])
        self.assertIsNotNone(main_theme_file)
        self.assertTrue((ROOT / "music" / main_theme_file.group(1)).is_file())
        for item in PRESENTATIONS:
            song = item.dedicated_sound_effect.removesuffix("_sound_e")
            self.assertNotIn(f'name = "{song}"', assets)
            self.assertFalse((ROOT / "music" / f"{song}.ogg").exists())

    def test_nam_war_and_last_empire_are_registered_presentations(self):
        self.assertIn("superevent_nam_resource_war", {item.name for item in PRESENTATIONS})
        self.assertIn("superevent_rus_last_empire", {item.name for item in PRESENTATIONS})

    def test_great_stelander_uses_its_dedicated_audio(self) -> None:
        presentation = next(
            item for item in PRESENTATIONS if item.name == "superevent_stelander_great"
        )
        self.assertEqual(
            presentation.dedicated_sound_effect, "superevent_stelander_great_sound_e"
        )

    def test_new_presentations_follow_hostilities_and_guarded_proclamation(self):
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        effects = (ROOT / "common/scripted_effects/ADISCORD_RUS_scripted_effects.txt").read_text(encoding="utf-8")
        war = blocks(nam, r"^ADISCORD_nam_resource_war_begin_hostilities\s*=\s*\{")[0]
        settlements = blocks(nam, r"^ADISCORD_nam_resource_war_resolve_\w+\s*=\s*\{")
        self.assertTrue(settlements)
        self.assertLess(war.index("declare_war_on"), war.index("ADISCORD_nam_show_resource_war_superevent"))
        # Only the actual outbreak announces the war; no settlement replays it.
        for settlement in settlements:
            self.assertNotIn("ADISCORD_nam_show_resource_war_superevent", settlement)
        empire = blocks(effects, r"^ADISCORD_vorkerland_rus_proclaim_last_empire\s*=\s*\{")[0]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_last_empire_proclaimed }", empire)
        self.assertLess(empire.index("set_cosmetic_tag"), empire.index("ADISCORD_vorkerland_show_last_empire_superevent"))
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for event_id, request in ((7, 10), (8, 11), (9, 12), (10, 13), (11, 14), (12, 15)):
            event = _event_block(events, f"ADISCORD_superevent.{event_id}")
            self.assertIn(f"ADISCORD_superevent_request = {request}", event)
            self.assertIn("ADISCORD_superevent_enqueue = yes", event)
            for forbidden in ("declare_war_on", "set_cosmetic_tag", "add_manpower"):
                self.assertNotIn(forbidden, event)

    def test_war_mandate_and_victor_select_one_queued_presentation(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.validators.validate_adiscord_superevents import _event_block

        def presentation(source, event_id, facts):
            event = parse_clausewitz(_event_block(source, event_id))[0].value
            effects = list(selected_effects(block(event, "immediate"), facts, "VAL"))
            requests = [
                int(scalar(row.value, "ADISCORD_superevent_request"))
                for _, row in effects if row.key == "set_temp_variable"
            ]
            self.assertEqual(len(requests), 1)
            self.assertEqual(sum(row.key == "ADISCORD_superevent_enqueue" for _, row in effects), 1)
            return PRESENTATIONS_BY_ID[requests[0]].name

        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        nam = "superevent_nam_resource_war"
        for mandate, expected in (("service", nam + "_service"), ("district", nam + "_district"), ("pragmatic", nam)):
            facts = {("NAM", f"NAM_prewar_{mandate}_mandate", "yes"): True}
            self.assertEqual(presentation(events, "ADISCORD_superevent.7", facts), expected)

        events = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8")
        party = "superevent_stelander_party_victory"
        for outcome, suffix in enumerate(("", "_houses", "_festival", "_staff", "_wallets", "_silence", "_regent")):
            facts = {("STP", "variable", "STP_pv_outcome"): outcome}
            self.assertEqual(presentation(events, "ADISCORD_STP_cw.71", facts), party + suffix)

        for course in range(4):
            facts = {("STS", "variable", "STP_hw_course"): course}
            self.assertEqual(presentation(events, "ADISCORD_STP_cw.72", facts), "superevent_stelander_shabrat_victory")
            facts["STS", "ruling_leader"] = "STP_grigory_sotnikov"
            self.assertEqual(presentation(events, "ADISCORD_STP_cw.72", facts), "superevent_stelander_sotnikov_civilwar")

    def test_regional_victories_snapshot_the_winners_course(self):
        from tools.tests.test_adiscord_stp_preparation import scalar, selected_effects
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        selectors = {}
        for region in ("south", "west"):
            source = ROOT / f"common/scripted_effects/ADISCORD_{region}_final_war_effects.txt"
            selectors.update({row.key: row.value for row in parse_clausewitz(source.read_text(encoding="utf-8"))})

        def check(selector, tag, expected, facts):
            with self.subTest(expected=expected):
                effects = list(selected_effects(selectors[selector], facts, tag))
                requests = [
                    int(scalar(row.value, "ADISCORD_superevent_request"))
                    for _, row in effects if row.key == "set_temp_variable"
                ]
                self.assertEqual(len(requests), 1)
                self.assertEqual(PRESENTATIONS_BY_ID[requests[0]].name, "superevent_" + expected)
                self.assertEqual(sum(row.key == "ADISCORD_superevent_enqueue" for _, row in effects), 1)

        for course, name in enumerate(("conclave", "houses", "cities", "nur", "regency", "commune")):
            check("ADISCORD_south_show_shahrabad_victory", "SHL", "south_" + name,
                  {("SHL", "variable", "SHL_political_course"): course})

        selector = "ADISCORD_south_show_svetlogorye_victory"
        for subject, name, endings in (
            (3, "service", (("ladder_ending_iron", "iron"), ("ladder_ending_service", "civil_service"))),
            (4, "charter", (("charter_ending_federation", "federation"), ("charter_ending_oil_union", "oil_union"))),
            (5, "contracts", (("prag_ending_republic", "contract_republic"), ("prag_ending_directorate", "directorate"))),
        ):
            facts = {("NAM", "variable", "global.ADISCORD_south_subject_type"): subject}
            check(selector, "NAM", "south_" + name, facts)
            for focus, ending in endings:
                check(selector, "NAM", "south_" + ending, {**facts, ("NAM", "has_completed_focus", "NAM_" + focus): True})
        humanists = {("NAM", "has_country_flag", "NAM_exile_humanist"): True}
        rump = {("NAM", "has_focus_tree", "NAM_defeated_focus"): True}
        check(selector, "NAM", "south_boards", {**humanists, ("NAM", "has_country_flag", "NAM_corp_takeover"): True})
        check(selector, "NAM", "south_free_islands", humanists)
        check(selector, "NAM", "south_radical", {("NAM", "has_country_flag", "NAM_exile_radical"): True})
        check(selector, "NAM", "south_revenge", {**rump, ("NAM", "has_completed_focus", "NAM_defeat_revenge"): True})
        check(selector, "NAM", "south_rump", rump)
        check(selector, "NAM", "south_nam", {})

        selector = "ADISCORD_west_show_vorkerland_victory"
        worker = {("WRK", "has_country_flag", "ADISCORD_vorkerland_route_worker"): True}
        joint = {("WRK", "has_country_flag", "ADISCORD_vorkerland_route_joint"): True}
        check(selector, "WRK", "west_worker", worker)
        check(selector, "WRK", "west_anton", {**worker, ("WRK", "ruling_leader"): "WRK_Anton_Bagley"})
        check(selector, "WRK", "west_council", {**joint, ("WRK", "ruling_leader"): "WRK_VAD_Joint_Council"})
        check(selector, "WRK", "west_petrichev", joint)
        check(selector, "WRK", "west_world_empire", {**joint, ("WRK", "has_cosmetic_tag", "WRK_vorkerland_world_empire"): True})
        check(selector, "WRK", "west_dorian", {("WRK", "has_global_flag", "ADISCORD_vorkerland_joint_government_formed"): True})
        for terms, subject, name in ((2, 0, "committee"), (2, 3, "shield"), (2, 4, "emergency"), (1, 0, "revanche")):
            check("ADISCORD_west_show_itoran_victory", "IVN", "west_" + name, {
                ("IVN", "variable", "global.ADISCORD_west_terms"): terms,
                ("IVN", "variable", "global.ADISCORD_west_subject_type"): subject,
            })

        defense = selectors["ADISCORD_south_final_resolve_north_victory"]
        for active, leader, victory in ((True, True, True), (True, False, False), (False, True, False)):
            facts = {
                ("EFL", "ADISCORD_south_final_active", "yes"): active,
                ("EFL", "ADISCORD_south_north_leader_exists", "yes"): leader,
            }
            selected = [row for _, row in selected_effects(defense, facts, "EFL")]
            cards = [PRESENTATIONS_BY_ID[int(scalar(row.value, "ADISCORD_superevent_request"))].name
                     for row in selected if row.key == "set_temp_variable"]
            self.assertEqual(cards, ["superevent_south_restitution"] if victory else [])
            self.assertEqual(sum(row.key == "ADISCORD_superevent_enqueue" for row in selected), int(victory))

    def test_fifo_duplicates_and_close_execute_the_scripted_effects(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        definitions = {entry.key: entry.value for entry in parse_clausewitz(source)}
        flags, queue, variables, played = set(), [], {}, []
        map_openings = []

        def fields(body):
            return {entry.key: entry.value for entry in body}

        def number(value):
            if value == "global.ADISCORD_superevent_queue^num":
                return len(queue)
            if value == "global.ADISCORD_superevent_queue^0":
                return queue[0]
            return variables[value] if value in variables else int(value)

        def condition(entry):
            key, value = entry.key, entry.value
            if key == "has_global_flag":
                return value in flags
            if key in ("OR", "AND", "NOT"):
                results = [condition(child) for child in value]
                return any(results) if key == "OR" else (not all(results) if key == "NOT" else all(results))
            data = fields(value)
            if key == "is_in_array":
                self.assertEqual(data["array"], "global.ADISCORD_superevent_queue")
                return number(data["value"]) in queue
            if key == "check_variable":
                if "var" in data:
                    left, right = number(data["var"]), number(data["value"])
                    self.assertEqual(data["compare"], "greater_than")
                    return left > right
                key, value = next(iter(data.items()))
                return number(key) == number(value)
            self.fail(f"Unsupported queue condition: {key}")

        def execute(body):
            matched = False
            for entry in body:
                key, value = entry.key, entry.value
                if key in ("if", "else_if"):
                    if key == "if":
                        matched = False
                    data = fields(value)
                    if not matched and all(condition(child) for child in data["limit"]):
                        execute([child for child in value if child.key != "limit"])
                        matched = True
                elif key == "set_global_flag":
                    flags.add(value)
                elif key == "clr_global_flag":
                    flags.discard(value)
                elif key == "set_temp_variable":
                    for name, amount in fields(value).items():
                        variables[name] = number(amount)
                elif key in ("add_to_array", "remove_from_array"):
                    data = fields(value)
                    self.assertEqual(data["array"], "global.ADISCORD_superevent_queue")
                    if key == "add_to_array":
                        queue.append(number(data["value"]))
                    else:
                        queue.pop(number(data["index"]))
                elif key == "ADISCORD_vorkerland_play_superevent_sound":
                    self.assertEqual(len(flags), 1)
                    played.append(next(iter(flags)))
                elif key == "country_event":
                    self.assertEqual(fields(value), {"id": "ADISCORD_portal_test.1"})
                    self.assertEqual(flags, {"superevent_itora_stalk_portal"})
                    map_openings.append(len(played))
                elif key in definitions and value == "yes":
                    execute(definitions[key])
                else:
                    self.fail(f"Unsupported queue effect: {key}")

        def request(index):
            variables["ADISCORD_superevent_request"] = index
            execute(definitions["ADISCORD_superevent_enqueue"])

        gui = parse_clausewitz((ROOT / SCRIPTED_GUI).read_text(encoding="utf-8"))[0].value
        windows = fields(gui)
        order = (6, 32, 24, 36, 20, 31, 23, 21, 29, 22, 18, 17, 16, 27, 10, 11, 9, 14, 1, 12, 26, 15, 13, 2, 28, 3, 4, 5, 7, 30, 8)
        order += tuple(sorted((i for i in PRESENTATIONS_BY_ID if i >= 37), reverse=True))
        self.assertEqual(set(order), set(PRESENTATIONS_BY_ID))
        for index in order + order:
            request(index)
        self.assertEqual(queue, list(order[1:]))
        self.assertEqual(played, [PRESENTATIONS_BY_ID[6].name])
        self.assertEqual(map_openings, [])
        for index in order:
            window = fields(windows[PRESENTATIONS_BY_ID[index].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS_BY_ID[i].name for i in order])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        self.assertEqual(map_openings, [order.index(74)])
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(61)
        self.assertEqual(len(played), len(order) + 1)
        request(74)
        request(74)
        self.assertEqual(len(map_openings), 1)
        window = fields(windows[PRESENTATIONS_BY_ID[61].name])
        execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(len(map_openings), 2)
        self.assertEqual(played[-1], "superevent_itora_stalk_portal")
        request(74)
        self.assertEqual(len(map_openings), 2)
        self.assertEqual(queue, [])

    def test_requests_do_not_replace_an_active_presentation(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8-sig")
        self.assertNotIn("ADISCORD_vorkerland_clear_superevent_flags = yes", source)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        dispatch = blocks(effects, r"^\s*ADISCORD_superevent_dispatch_next\s*=\s*\{")[0]
        for item in PRESENTATIONS:
            self.assertIn(f"has_global_flag = {item.name}", dispatch)
        self.assertIn("global.ADISCORD_superevent_queue^0", dispatch)
        self.assertIn("index = 0", dispatch)
        self.assertNotIn("days =", dispatch)
        gui = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        self.assertEqual(gui.count("ADISCORD_superevent_dispatch_next = yes"), len(PRESENTATIONS))

    def test_presentation_audio_uses_gui_sound_effects_without_radio_registration(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(
            encoding="utf-8-sig"
        )
        playback = blocks(
            effects,
            r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{",
        )[0]
        self.assertNotIn("scoped_sound_effect", playback)
        self.assertEqual(playback.count('play_song = "one_minute_of_silence"'), 1)
        self.assertEqual(playback.count('play_song = "two_minutes_of_silence"'), 1)
        self.assertNotIn('play_song = "superevent_', playback)

        sound_effects = (ROOT / "sound/superevents_effects.asset").read_text(encoding="utf-8-sig")
        shabrat_effect = next(
            block
            for block in blocks(sound_effects, r"^\s*soundeffect\s*=\s*\{")
            if "name = superevent_stelander_shabrat_victory_sound_e" in block
        )
        self.assertIn("volume = 0.80", shabrat_effect)

        gui = (ROOT / "interface/superevents.gui").read_text(encoding="utf-8-sig")
        windows = blocks(gui, r"^\s*containerWindowType\s*=\s*\{")
        for item in PRESENTATIONS:
            window = next(
                block
                for block in windows
                if f'name = "{item.name}"' in block
            )
            self.assertEqual(window.count("show_sound ="), 1, item.name)
            self.assertIn(
                f"show_sound = {item.dedicated_sound_effect}",
                window,
                item.name,
            )

        playlists = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "music").glob("*.txt")
        )
        for item in PRESENTATIONS:
            self.assertNotIn(f'song = "{item.name}"', playlists, item.name)

    def test_silence_selection_covers_actual_gui_audio_duration(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        long_branch = blocks(playback, r"^\s*if\s*=\s*\{")[0]
        short_branch = blocks(playback, r"^\s*else\s*=\s*\{")[0]
        self.assertIn('play_song = "two_minutes_of_silence"', long_branch)
        self.assertIn('play_song = "one_minute_of_silence"', short_branch)
        selected_long = set(re.findall(r"has_global_flag\s*=\s*(\w+)", long_branch))

        sounds = (ROOT / "sound/superevents_sound.asset").read_text(encoding="utf-8")
        sound_paths = dict(re.findall(r'name = "(\w+)"\s+file = "([^"]+)"', sounds))
        sound_effects = (ROOT / "sound/superevents_effects.asset").read_text(encoding="utf-8")
        effect_sounds = {}
        for block in blocks(sound_effects, r"^\s*soundeffect\s*=\s*\{"):
            name = re.search(r"\bname\s*=\s*(\w+)", block)[1]
            effect_sounds[name] = re.search(r"\bsound\s*=\s*(\w+)", block)[1]

        gui = (ROOT / "interface/superevents.gui").read_text(encoding="utf-8")
        expected_long = set()
        for window in blocks(gui, r"^\s*containerWindowType\s*=\s*\{"):
            name = re.search(r'name\s*=\s*"([^"]+)"', window)[1]
            sound_effect = re.search(r"show_sound\s*=\s*(\w+)", window)[1]
            path = ROOT / "sound" / sound_paths[effect_sounds[sound_effect]]
            with wave.open(str(path)) as audio:
                duration = audio.getnframes() / audio.getframerate()
            self.assertLessEqual(duration, 120, name)
            if duration > 60:
                expected_long.add(name)
        self.assertEqual(selected_long, expected_long)

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"), "requires FFmpeg")
    def test_silent_carriers_have_exact_duration_and_zero_samples(self) -> None:
        for name, duration in (("one_minute_of_silence", 60), ("two_minutes_of_silence", 120)):
            with self.subTest(name=name):
                path = ROOT / "music" / f"{name}.ogg"
                probe = subprocess.check_output([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(path),
                ], text=True)
                self.assertAlmostEqual(float(probe), duration, places=3)
                samples = subprocess.check_output([
                    "ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-",
                ])
                self.assertTrue(samples)
                self.assertFalse(any(samples))

    @unittest.skipUnless(shutil.which("ffmpeg"), "requires FFmpeg")
    def test_nam_who_starts_at_end_of_tower_sound(self) -> None:
        tower = ROOT / "sound/superevents/superevent_vorkerland_civilwar_sound.wav"
        with wave.open(str(tower)) as audio:
            duration = audio.getnframes() / audio.getframerate()
        song = ROOT / "music/ADISCORD_nam_who.ogg"
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(song),
             "-t", str(duration + 1), "-af", "silencedetect=noise=-60dB:d=0.1",
             "-f", "null", "-"],
            check=True, capture_output=True, text=True,
        )
        self.assertRegex(result.stderr, r"silence_start: 0\s")
        onset = re.search(r"silence_end: ([\d.]+)", result.stderr)
        self.assertIsNotNone(onset)
        # Allow for the song's own quiet opening after the silent lead-in.
        self.assertAlmostEqual(float(onset[1]), duration, delta=0.15)

    def test_repository_contract_is_clean(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_itora_war_dispatch_reaches_human_and_observer(self) -> None:
        from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture
        from tools.tests.test_adiscord_south_final_war import flatten
        from tools.tests.test_adiscord_stp_preparation import scalar

        for human in (None, "WKR"):
            world = RusCrisisFixture()
            if human:
                world.ai_countries.discard(human)
            world.run("ADISCORD_vorkerland_show_itora_war_superevent", "VAL")
            self.assertEqual(world.events, [(human or "VAL", "ADISCORD_superevent.13")])
            calls = [row.value for row in flatten(world.effects["ADISCORD_vorkerland_show_itora_war_superevent"]) if row.key == "country_event"]
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(scalar(call, "hours") == "1" for call in calls))

    def test_itora_civilwar_is_shown_only_by_the_revolt(self) -> None:
        references = []
        for directory in ("common", "events", "focus_trees"):
            for path in (ROOT / directory).rglob("*.txt"):
                source = path.read_text(encoding="utf-8-sig")
                if re.search(r"\bADISCORD_superevent\.14\b", source):
                    references.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            references,
            ["common/scripted_effects/ADISCORD_IVN_scripted_effects.txt", "events/ADISCORD_superevents.txt"],
        )
        effects = (ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt").read_text(encoding="utf-8")
        self.assertEqual(effects.count("IVN_show_civil_war_superevent = yes"), 1)
        start = effects[effects.index("IVN_cw_begin_hostilities = {"):]
        start = start[:start.index("\n}\n")]
        self.assertIn("IVN_show_civil_war_superevent = yes", start)

    def test_itora_civilwar_dispatch_reaches_human_and_observer(self) -> None:
        from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture
        from tools.tests.test_adiscord_south_final_war import flatten
        from tools.tests.test_adiscord_stp_preparation import scalar

        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        itora = parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt").read_text(encoding="utf-8"))
        for human in (None, "IVC"):
            world = RusCrisisFixture()
            world.effects.update({entry.key: entry.value for entry in itora})
            world.countries.add("IVC")
            world.ai_countries.add("IVC")
            world.owners["95"] = "IVC"
            world.controllers["95"] = "IVC"
            if human:
                world.ai_countries.discard(human)
            world.run("IVN_show_civil_war_superevent", "IVN")
            self.assertEqual(world.events, [(human or "IVN", "ADISCORD_superevent.14")])
            calls = [row.value for row in flatten(world.effects["IVN_show_civil_war_superevent"]) if row.key == "country_event"]
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(scalar(call, "hours") == "1" for call in calls))

    def test_itora_war_console_presentation_has_no_campaign_effects(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block, blocks
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = _event_block(source, "ADISCORD_superevent.13")
        fields = {entry.key: entry.value for entry in parse_clausewitz(event)[0].value}
        self.assertEqual(set(fields), {"id", "hidden", "is_triggered_only", "immediate"})
        self.assertEqual(fields["hidden"], "yes")
        self.assertEqual(fields["is_triggered_only"], "yes")
        self.assertEqual(
            [entry.key for entry in fields["immediate"]],
            ["set_temp_variable", "ADISCORD_superevent_enqueue"],
        )
        self.assertIn("ADISCORD_superevent_request = 16", event)

        gfx = (ROOT / GFX).read_text(encoding="utf-8")
        sprite = next(
            block
            for block in blocks(gfx, r"^\s*spriteType\s*=\s*\{")
            if 'name = "GFX_superevent_itora_vorkerland_war"' in block
        )
        texture = re.search(r'textureFile = "([^"]+)"', sprite)[1]
        self.assertEqual(texture, "gfx/interface/superevents/WRK/superevent_itora_vorkerland_war.png")
        self.assertTrue((ROOT / texture).is_file())

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        timeout = blocks(effects, r"^ADISCORD_superevent_observer_tick\s*=\s*\{")[0]
        self.assertIn("flag = superevent_itora_vorkerland_war days > 6", timeout)
        self.assertIn("clr_global_flag = superevent_itora_vorkerland_war", timeout)

    def test_itora_civilwar_console_presentation_has_no_campaign_effects(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block, blocks
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = _event_block(source, "ADISCORD_superevent.14")
        fields = {entry.key: entry.value for entry in parse_clausewitz(event)[0].value}
        self.assertEqual(set(fields), {"id", "hidden", "is_triggered_only", "immediate"})
        self.assertEqual(fields["hidden"], "yes")
        self.assertEqual(fields["is_triggered_only"], "yes")
        self.assertEqual(
            [entry.key for entry in fields["immediate"]],
            ["set_temp_variable", "ADISCORD_superevent_enqueue"],
        )
        self.assertIn("ADISCORD_superevent_request = 17", event)

        gfx = (ROOT / GFX).read_text(encoding="utf-8")
        sprite = next(
            block
            for block in blocks(gfx, r"^\s*spriteType\s*=\s*\{")
            if 'name = "GFX_superevent_itora_civilwar"' in block
        )
        texture = re.search(r'textureFile = "([^"]+)"', sprite)[1]
        self.assertEqual(texture, "gfx/interface/superevents/IVN/superevent_itora_civilwar.png")
        self.assertTrue((ROOT / texture).is_file())

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        timeout = blocks(effects, r"^ADISCORD_superevent_observer_tick\s*=\s*\{")[0]
        self.assertIn("flag = superevent_itora_civilwar days > 6", timeout)
        self.assertIn("clr_global_flag = superevent_itora_civilwar", timeout)

    def test_khan_defeat_console_presentation_has_no_campaign_effects(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block, blocks
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = _event_block(source, "ADISCORD_superevent.15")
        fields = {entry.key: entry.value for entry in parse_clausewitz(event)[0].value}
        self.assertEqual(set(fields), {"id", "hidden", "is_triggered_only", "immediate"})
        self.assertEqual(fields["hidden"], "yes")
        self.assertEqual(fields["is_triggered_only"], "yes")
        self.assertEqual(
            [entry.key for entry in fields["immediate"]],
            ["set_temp_variable", "ADISCORD_superevent_enqueue"],
        )
        self.assertIn("ADISCORD_superevent_request = 18", event)

        gfx = (ROOT / GFX).read_text(encoding="utf-8")
        sprite = next(
            block
            for block in blocks(gfx, r"^\s*spriteType\s*=\s*\{")
            if 'name = "GFX_superevent_rus_khan_defeated"' in block
        )
        texture = re.search(r'textureFile = "([^"]+)"', sprite)[1]
        self.assertEqual(texture, "gfx/interface/superevents/RUS/superevent_rus_khan_defeated.png")
        self.assertTrue((ROOT / texture).is_file())

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        timeout = blocks(effects, r"^ADISCORD_superevent_observer_tick\s*=\s*\{")[0]
        self.assertIn("flag = superevent_rus_khan_defeated days > 6", timeout)
        self.assertIn("clr_global_flag = superevent_rus_khan_defeated", timeout)

    def test_itora_war_quote_follows_the_recorded_civil_war_winner(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        name = "superevent_itora_vorkerland_war"
        path = ROOT / "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
        getters = parse_clausewitz(path.read_text(encoding="utf-8"))
        getter = next(
            entry.value
            for entry in getters
            if any(child.key == "name" and child.value == "GetSupereventQuote" for child in entry.value)
        )
        choices = []
        for entry in getter:
            if entry.key != "text":
                continue
            fields = {child.key: child.value for child in entry.value}
            key = fields["localization_key"]
            if not key.startswith(name) and key != "superevent_inactive_quote":
                continue
            conditions = fields.get("trigger", [])
            choices.append((key, conditions))

        # Global event target naming the country that currently is Vorkerland:
        # WRK until a claimant unifies it, then that claimant's own tag.
        nation_scope = "event_target:ADISCORD_vorkerland_nation"
        unifiers = {"worker": "WKR", "vlad": "VAD", "dorian": "TVA", None: "WRK"}

        def matches(conditions, flags, country_flags, nation):
            for child in conditions:
                if child.key == "has_global_flag":
                    if child.value not in flags:
                        return False
                elif child.key == nation_scope:
                    for scoped in child.value:
                        self.assertEqual(scoped.key, "has_country_flag")
                        if scoped.value not in country_flags.get(nation, set()):
                            return False
                else:
                    self.fail(f"Unsupported quote condition: {child.key}")
            return True

        anton_outcome = "ADISCORD_vorkerland_worker_utilitarian_outcome"
        cases = (
            ("worker", {}, ""),
            ("worker", {"WKR": {anton_outcome}}, "_anton"),
            ("worker", {"IVN": {anton_outcome}}, ""),
            # The retired tag is no longer read once a claimant holds the target.
            ("worker", {"WRK": {anton_outcome}}, ""),
            ("vlad", {}, "_vlad"),
            ("dorian", {}, "_dorian"),
            ("vlad", {"VAD": {anton_outcome}}, "_vlad"),
            ("dorian", {"TVA": {anton_outcome}}, "_dorian"),
            (None, {}, ""),
            (None, {"WRK": {anton_outcome}}, ""),
        )
        for winner, country_flags, suffix in cases:
            with self.subTest(winner=winner, country_flags=country_flags):
                nation = unifiers[winner]
                flags = {f"ADISCORD_vorkerland_{winner}_won"} if winner else set()
                inactive = next(
                    key for key, conditions in choices if matches(conditions, flags, country_flags, nation)
                )
                self.assertEqual(inactive, "superevent_inactive_quote")
                flags.add(name)
                selected = next(
                    key for key, conditions in choices if matches(conditions, flags, country_flags, nation)
                )
                self.assertEqual(selected, f"{name}{suffix}_quote")

        quote_keys = {key for key, _ in choices if key.startswith(name)}
        self.assertEqual(len(quote_keys), 4)
        for language in ("russian", "english"):
            localisation = ROOT / f"localisation/{language}/ADISCORD_superevents_l_{language}.yml"
            contents = localisation.read_text(encoding="utf-8-sig")
            values = []
            for key in quote_keys:
                # Values may contain escaped ASCII quotes around titles.
                matches = re.findall(rf'^\s*{key}:\d* "((?:[^"\\\r\n]|\\.)+)"$', contents, re.MULTILINE)
                self.assertEqual(len(matches), 1, (language, key))
                self.assertIn(r"\n\n- ", matches[0])
                values.append(matches[0])
            self.assertEqual(len(set(values)), 4)

    def test_joint_victory_is_news_without_a_superevent_queue_entry(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block

        self.assertNotIn(19, PRESENTATIONS_BY_ID)
        for relative in (
            "events/ADISCORD_superevents.txt",
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
            "common/scripted_guis/superevents.txt",
            "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt",
            "interface/superevents.gui",
            "interface/superevents.gfx",
            "sound/superevents_effects.asset",
            "sound/superevents_category.asset",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("superevent_vorkerland_joint_victory", source, relative)
        events = (ROOT / "events/ADISCORD_vorkerland_events.txt").read_text(encoding="utf-8")
        event = _event_block(events, "ADISCORD_vorkerland_postwar.7")
        self.assertTrue(event.lstrip().startswith("news_event = {"))
        self.assertIn("major = yes", event)
        self.assertIn("is_triggered_only = yes", event)
        self.assertIn("fire_only_once = yes", event)
        for forbidden in ("immediate", "hidden = yes", "ADISCORD_superevent", "country_event"):
            self.assertNotIn(forbidden, event)

    def test_joint_victory_selection_and_announced_guard_execute_source(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        finalizer = blocks(source, r"^ADISCORD_vorkerland_finalize_reunification\s*=\s*\{")[0]
        outer = parse_clausewitz(finalizer)[0].value[0].value
        route = next(entry.value for entry in outer if entry.key == "else_if"
                     and any(child.key == "limit" and any(
                         condition.key == "has_country_flag"
                         and condition.value == "ADISCORD_vorkerland_route_joint"
                         for condition in child.value) for child in entry.value))
        self.assertIn("ADISCORD_vorkerland_reunification_verified = yes", finalizer)

        def matches(body, flags):
            for entry in body:
                if entry.key == "has_global_flag":
                    valid = entry.value in flags
                elif entry.key == "NOT":
                    valid = not matches(entry.value, flags)
                else:
                    self.fail(f"Unsupported victory condition: {entry.key}")
                if not valid:
                    return False
            return True

        def execute(body, flags, shown):
            matched = False
            for entry in body:
                if entry.key == "if":
                    limit = next(child.value for child in entry.value if child.key == "limit")
                    matched = matches(limit, flags)
                    if matched:
                        execute([child for child in entry.value if child.key != "limit"], flags, shown)
                elif entry.key == "else_if":
                    if not matched:
                        limit = next(child.value for child in entry.value if child.key == "limit")
                        matched = matches(limit, flags)
                        if matched:
                            execute([child for child in entry.value if child.key != "limit"], flags, shown)
                elif entry.key == "else":
                    if not matched:
                        execute(entry.value, flags, shown)
                elif entry.key == "set_global_flag":
                    flags.add(entry.value)
                elif entry.key == "country_event":
                    event = {child.key: child.value for child in entry.value}
                    delay = next(f"{unit}={event[unit]}" for unit in ("days", "hours") if unit in event)
                    scheduled.append((event["id"], delay))
                elif entry.key.startswith("ADISCORD_vorkerland_show_"):
                    shown.append(entry.key)
                    show = blocks(source, rf"^{entry.key}\s*=\s*\{{")[0]
                    self.assertIn("set_global_flag = ADISCORD_vorkerland_central_victory_announced", show)
                    flags.add("ADISCORD_vorkerland_central_victory_announced")
                else:
                    self.fail(f"Unsupported victory effect: {entry.key}")

        # The collegial staff is a non-imperial course: it has no restoration
        # superevent, but its victory still closes the announcement.
        flags = {"ADISCORD_vorkerland_collegial_staff_formed"}
        shown = []
        scheduled = []
        execute([entry for entry in route if entry.key != "limit"], flags, shown)
        self.assertEqual(shown, [])
        self.assertEqual(scheduled, [])
        self.assertIn("ADISCORD_vorkerland_central_victory_announced", flags)

        for joint in (False, True):
            for announced in (False, True):
                with self.subTest(joint=joint, announced=announced):
                    flags = set()
                    if joint:
                        flags.add("ADISCORD_vorkerland_joint_government_formed")
                    if announced:
                        flags.add("ADISCORD_vorkerland_central_victory_announced")
                    shown = []
                    scheduled = []
                    payload = [entry for entry in route if entry.key != "limit"]
                    execute(payload, flags, shown)
                    expected = ("ADISCORD_vorkerland_show_joint_victory_news" if joint
                                else "ADISCORD_vorkerland_show_vlad_victory_superevent")
                    self.assertEqual(shown, [] if announced else [
                        expected
                    ])
                    first_shown = list(shown)
                    self.assertEqual(scheduled, [
                        ("ADISCORD_vorkerland_postwar.4", "hours=1")
                    ] if joint and not announced else [])
                    first_scheduled = list(scheduled)
                    execute(payload, flags, shown)
                    self.assertEqual(shown, first_shown)
                    self.assertEqual(scheduled, first_scheduled)

    def test_joint_news_dispatch_stays_in_the_winning_country(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        show = blocks(source, r"^ADISCORD_vorkerland_show_joint_victory_news\s*=\s*\{")[0]
        self.assertIn("news_event = { id = ADISCORD_vorkerland_postwar.7 }", show)
        self.assertNotIn("random_country", show)
        self.assertNotIn("ADISCORD_superevent_enqueue", show)

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
                "superevent_nam_resource_war",
                "superevent_rus_last_empire",
                "superevent_val_commonwealth",
                "superevent_val_council_proclamation",
                "superevent_south_war",
                "superevent_stelander_great",
                "superevent_rus_black_banner",
                "superevent_rus_restoration",
                "superevent_itora_vorkerland_war",
                "superevent_itora_civilwar",
                "superevent_rus_khan_defeated",
                "superevent_stelander_sotnikov_civilwar",
                "superevent_stelander_sotnikov_directory",
                "superevent_stelander_sotnikov_charter",
                "superevent_stelander_shabrat_republic",
                "superevent_stelander_tikhoreva",
                "superevent_nam_resource_war_service",
                "superevent_nam_resource_war_district",
                "superevent_stelander_party_victory_houses",
                "superevent_stelander_party_victory_staff",
                "superevent_stelander_party_victory_wallets",
                "superevent_stelander_party_victory_silence",
                "superevent_stelander_party_victory_regent",
                "superevent_stelander_party_victory_festival",
                "superevent_south_houses",
                "superevent_south_cities",
                "superevent_south_nur",
                "superevent_south_regency",
                "superevent_south_commune",
                "superevent_south_conclave",
                "superevent_south_service",
                "superevent_south_charter",
                "superevent_south_contracts",
                "superevent_south_rump",
                "superevent_south_revenge",
                "superevent_south_radical",
                "superevent_south_free_islands",
                "superevent_south_boards",
                "superevent_south_restitution",
                "superevent_west_worker",
                "superevent_west_petrichev",
                "superevent_west_veyran",
                "superevent_west_dorian",
                "superevent_west_anton",
                "superevent_west_shield",
                "superevent_west_emergency",
                "superevent_west_revanche",
                "superevent_west_committee",
                "superevent_vorkerland_world_empire",
                "superevent_south_iron",
                "superevent_south_civil_service",
                "superevent_south_federation",
                "superevent_south_oil_union",
                "superevent_south_contract_republic",
                "superevent_south_directorate",
                "superevent_south_nam",
                "superevent_west_council",
                "superevent_west_world_empire",
                "superevent_nam_veyran_proclamation",
                "superevent_itora_legion_victory",
                "superevent_itora_committee_victory",
                "superevent_itora_stalk_portal",
            ),
        )

    def test_stelander_victory_news_starts_presentation_before_choice(self) -> None:
        from tools.validators.validate_adiscord_superevents import _event_block, blocks

        source = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8-sig")
        for event_id, side in ((71, "party"), (72, "shabrat")):
            event = _event_block(source, f"ADISCORD_STP_cw.{event_id}")
            immediate = event.split("option =", 1)[0]
            self.assertIn("fire_only_once = no", event)
            self.assertIn("immediate =", immediate)
            self.assertIn(f"ADISCORD_superevent_request = {8 if side == 'party' else 9}", immediate)
            self.assertNotIn("ADISCORD_vorkerland_clear_superevent_flags = yes", immediate)
            self.assertIn("ADISCORD_superevent_enqueue = yes", immediate)

        effects = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(
            encoding="utf-8"
        )
        flag = "ADISCORD_news_stelander_civil_war_result_published"
        for effect, event_ids in (
            ("STP_cw_settle_union_victory", (71, 72)),
            ("STP_cw_settle_nod_victory", (71,)),
        ):
            settlement = blocks(effects, rf"^{effect}\s*=\s*\{{")[0]
            guarded = blocks(
                settlement,
                rf"\bif\s*=\s*\{{\s*limit\s*=\s*\{{\s*NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{flag}\b",
            )
            self.assertEqual(len(guarded), 1, effect)
            publication = guarded[0]
            self.assertLess(
                publication.index(f"set_global_flag = {flag}"),
                publication.index("news_event ="),
            )
            for event_id in event_ids:
                self.assertIn(f"id = ADISCORD_STP_cw.{event_id}", publication)

    def test_postwar_music_plays_from_each_sides_opening_focus(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for name in ("superevent_stelander_shabrat_victory", "superevent_stelander_party_victory"):
            window = blocks(source, rf"^\s*{name}\s*=\s*\{{")[0]
            self.assertNotIn("scoped_play_song", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", playback)
        focuses = read_focus_source(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt")
        assets = (ROOT / "music/ADISCORD_music.asset").read_text(encoding="utf-8-sig")
        for focus_id, song in (("STP_pc_after_victory", "ADISCORD_stp_civil_war_end"),
                               ("STP_pw_party_new_republic", "ADISCORD_stp_party_postwar")):
            focus = next(b for b in blocks(focuses, r"^\s*focus\s*=\s*\{") if f"id = {focus_id}\n" in b)
            reward = blocks(focus, r"^\s*completion_reward\s*=\s*\{")[0]
            self.assertIn(f'scoped_play_song = "{song}"', reward)
            self.assertIn("limit = { is_ai = no }", reward)
            self.assertEqual((ROOT / "music" / f"{song}.ogg").read_bytes()[:4], b"OggS")
            self.assertIn(f'file = "{song}.ogg"', assets)
        self.assertNotIn("_after_superevent", assets)
        self.assertFalse(list((ROOT / "music").glob("*_after_superevent.ogg")))

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

    def test_removed_texture_leaves_a_broken_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_contract_tree(root)
            texture = "gfx/interface/superevents/NAM/superevent_resource_war.png"
            (root / texture).unlink()
            issues = collect_issues(root)
            self.assertIn(f"GFX_superevent_nam_resource_war: missing texture {texture}", issues)
            self.assertFalse(
                any("GFX_superevent_rus_khan_defeated: missing texture" in issue for issue in issues)
            )
            khan_texture = "gfx/interface/superevents/RUS/superevent_rus_khan_defeated.png"
            (root / khan_texture).unlink()
            self.assertIn(
                f"GFX_superevent_rus_khan_defeated: missing texture {khan_texture}",
                collect_issues(root),
            )
            self.assertFalse(
                any("GFX_superevent_itora_civilwar: missing texture" in issue for issue in issues)
            )
            texture = "gfx/interface/superevents/IVN/superevent_itora_civilwar.png"
            (root / texture).unlink()
            self.assertIn(
                f"GFX_superevent_itora_civilwar: missing texture {texture}",
                collect_issues(root),
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



    def test_every_presentation_requires_its_window_visibility_and_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_contract_tree(root)
            path = root / SCRIPTED_GUI
            source = path.read_text(encoding="utf-8")
            for item in PRESENTATIONS:
                name = item.name
                mutations = (
                    (f'window_name = "{name}"', 'window_name = "missing"',
                     f"scripted GUI {name}: missing window binding"),
                    (f"has_global_flag = {name}", "has_global_flag = missing",
                     f"scripted GUI {name}: missing visibility flag"),
                    (f"clr_global_flag = {name}", "clr_global_flag = missing",
                     f"scripted GUI {name}: close must clear its flag before dispatch"),
                )
                for before, after, diagnostic in mutations:
                    with self.subTest(presentation=name, field=before):
                        self.assertIn(before, source)
                        path.write_text(source.replace(before, after, 1), encoding="utf-8")
                        self.assertTrue(any(diagnostic in issue for issue in collect_issues(root)))

    def test_great_stelander_focus_proclaims_before_queuing_once(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        focuses = read_focus_source(ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt")
        focus = next(b for b in blocks(focuses, r"^\s*focus\s*=\s*\{")
                     if "id = STP_pw_party_great_stelander\n" in b)
        self.assertIn("STP_pw_party_proclaim_great_stelander = yes", focus)
        effects = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
        proclamation = blocks(effects, r"^STP_pw_party_proclaim_great_stelander\s*=\s*\{")[0]
        guard = blocks(proclamation, r"^\s*limit\s*=\s*\{")[0]
        for gate in ("tag = STP", "STP_pw_party_northern_march_resolved = yes",
                     "is_subject = no", "has_war = no",
                     "NOT = { has_cosmetic_tag = STP_great_stelander }"):
            self.assertIn(gate, guard)
        self.assertLess(proclamation.index("set_cosmetic_tag = STP_great_stelander"),
                        proclamation.index("id = ADISCORD_superevent.10"))
        self.assertEqual(proclamation.count("id = ADISCORD_superevent.10"), 1)
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        event = _event_block(events, "ADISCORD_superevent.10")
        self.assertIn("hidden = yes", event)
        self.assertIn("ADISCORD_superevent_request = 13", event)
        self.assertIn("ADISCORD_superevent_enqueue = yes", event)


if __name__ == "__main__":
    unittest.main()
