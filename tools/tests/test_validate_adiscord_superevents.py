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
    def test_fifo_duplicates_and_close_execute_the_scripted_effects(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        definitions = {entry.key: entry.value for entry in parse_clausewitz(source)}
        flags, queue, variables, played = set(), [], {}, []

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
                elif key in definitions and value == "yes":
                    execute(definitions[key])
                else:
                    self.fail(f"Unsupported queue effect: {key}")

        def request(index):
            variables["ADISCORD_superevent_request"] = index
            execute(definitions["ADISCORD_superevent_enqueue"])

        gui = parse_clausewitz((ROOT / SCRIPTED_GUI).read_text(encoding="utf-8"))[0].value
        windows = fields(gui)
        for index in (6, 9, 1, 6, 9, 1):
            request(index)
        self.assertEqual(queue, [9, 1])
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in (6, 9, 1):
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in (6, 9, 1)])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(6)
        self.assertEqual(len(played), 4)

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

    def test_presentation_playback_uses_only_one_music_channel(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("sound_effect =", playback)
        self.assertNotIn("one_minute_of_silence", playback)
        for item in PRESENTATIONS:
            song = item.dedicated_sound_effect.removesuffix("_sound_e")
            self.assertIn(f'play_song = "{song}"', playback)

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
            self.assertIn(f"ADISCORD_superevent_request = {8 if side == 'party' else 9}", immediate)
            self.assertNotIn("ADISCORD_vorkerland_clear_superevent_flags = yes", immediate)
            self.assertIn("ADISCORD_superevent_enqueue = yes", immediate)

    def test_stelander_music_waits_for_audio_instead_of_shabrat_close(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        window = blocks(source, r"^\s*superevent_stelander_shabrat_victory\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", window)
        self.assertIn("clr_global_flag = superevent_stelander_shabrat_victory", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        tail = playback
        self.assertIn("limit = { has_global_flag = superevent_stelander_shabrat_victory }", tail)
        self.assertIn("STS = {", tail)
        self.assertIn("limit = { is_ai = no }", tail)
        self.assertIn('scoped_play_song = "ADISCORD_stp_civil_war_end_after_superevent"', tail)
        party = blocks(source, r"^\s*superevent_stelander_party_victory\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", party)
        focuses = (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig")
        focus = next(b for b in blocks(focuses, r"^\s*focus\s*=\s*\{") if "id = STP_pw_party_new_republic\n" in b)
        reward = blocks(focus, r"^\s*completion_reward\s*=\s*\{")[0]
        self.assertIn('scoped_play_song = "ADISCORD_stp_civil_war_end"', reward)
        self.assertIn("limit = { is_ai = no }", reward)
        music = ROOT / "music/ADISCORD_stp_civil_war_end.ogg"
        self.assertEqual(music.read_bytes()[:4], b"OggS")
        assets = (ROOT / "music/music.asset").read_text(encoding="utf-8-sig")
        self.assertIn('file = "ADISCORD_stp_civil_war_end.ogg"', assets)
        station = (ROOT / "music/_songs.txt").read_text(encoding="utf-8-sig")
        self.assertIn('song = "ADISCORD_stp_civil_war_end"', station)
        lead_in = next(b for b in blocks(station, r"^\s*music\s*=\s*\{")
                       if 'song = "ADISCORD_stp_civil_war_end_after_superevent"' in b)
        self.assertIn("chance = { base = 0 }", lead_in)
        self.assertIn('file = "ADISCORD_stp_civil_war_end_after_superevent.ogg"', assets)
        localisation = (ROOT / "localisation/russian/ADISCORD_music_l_russian.yml").read_bytes()
        self.assertTrue(localisation.startswith(b"\xef\xbb\xbf"))
        for key in ("ADISCORD_stp_civil_war_end", "ADISCORD_stp_civil_war_end_after_superevent"):
            self.assertRegex(localisation.decode("utf-8-sig"), rf'(?m)^ {key}: "[^"\r\n]+"\r?$')

    def test_combined_postwar_track_contains_cue_gap_and_theme(self) -> None:
        import struct
        import wave

        def ogg_duration(path: Path) -> float:
            data = path.read_bytes()
            header = data.index(b"\x01vorbis")
            rate = struct.unpack_from("<I", data, header + 12)[0]
            offset = 0
            samples = 0
            while offset < len(data):
                self.assertEqual(data[offset:offset + 4], b"OggS")
                granule = struct.unpack_from("<Q", data, offset + 6)[0]
                if granule != 0xffffffffffffffff:
                    samples = max(samples, granule)
                segments = data[offset + 26]
                size = sum(data[offset + 27:offset + 27 + segments])
                offset += 27 + segments + size
            return samples / rate

        with wave.open(str(ROOT / "sound/superevents/superevent_stelander_party_victory_sound.wav")) as sound:
            duration = sound.getnframes() / sound.getframerate()
        original = ogg_duration(ROOT / "music/ADISCORD_stp_civil_war_end.ogg")
        delayed = ogg_duration(ROOT / "music/ADISCORD_stp_civil_war_end_after_superevent.ogg")
        self.assertGreaterEqual(delayed - original, duration + 0.49)
        self.assertLess(delayed - original, duration + 0.51)

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
