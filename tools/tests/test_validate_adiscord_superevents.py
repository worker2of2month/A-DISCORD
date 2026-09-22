from __future__ import annotations

import re
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
    def test_radio_excludes_superevents_and_preserves_mod_music(self):
        playlists = list((ROOT / "music").glob("*.txt"))
        songs = "\n".join(path.read_text(encoding="utf-8-sig") for path in playlists)

        # Presentation audio is played directly from ADISCORD_music.asset.
        # It must never be registered as a radio song, otherwise HOI4 exposes
        # it in the music-player track list even with chance factor 0.
        for item in PRESENTATIONS:
            self.assertNotIn(f'song = "{item.name}"', songs, item.name)

        guard = (ROOT / "music/ADISCORD_superevent_songs.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("music_station =", guard)
        self.assertNotIn("song =", guard)

        self.assertNotIn('song = "one_minute_of_silence"', songs)
        self.assertNotIn('_after_superevent', songs)
        self.assertEqual(songs.count('song = "ADISCORD_stp_civil_war_end"'), 1)
        self.assertIn('music_station = "adiscord_music"', songs)
        visible_songs = (ROOT / "music/ADISCORD_songs.txt").read_text(
            encoding="utf-8-sig"
        )
        for item in PRESENTATIONS:
            self.assertNotIn(f'song = "{item.name}"', visible_songs)

        # Every radio-visible identifier must resolve to a human title in both
        # shipped languages. Otherwise HOI4 renders the raw script key in the
        # station list (for example ADISCORD_ksb_muzic_war).
        english_music = (ROOT / "localisation/english/ADISCORD_music_l_english.yml").read_text(
            encoding="utf-8-sig"
        )
        russian_music = (ROOT / "localisation/russian/ADISCORD_music_l_russian.yml").read_text(
            encoding="utf-8-sig"
        )
        visible_ids = re.findall(r'(?m)^\\s*song\\s*=\\s*"([^"]+)"\\s*        self.assertNotIn(
            'replace_path="music"', (ROOT / "descriptor.mod").read_text()
        )
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        self.assertNotIn('name = "maintheme"', assets)
        for item in PRESENTATIONS:
            self.assertIn(f'name = "{item.name}"', assets)

    def test_nam_war_and_last_empire_are_registered_presentations(self):
        self.assertIn("superevent_nam_resource_war", {item.name for item in PRESENTATIONS})
        self.assertIn("superevent_rus_last_empire", {item.name for item in PRESENTATIONS})

    def test_new_presentations_follow_hostilities_and_guarded_proclamation(self):
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        war = blocks(nam, r"^ADISCORD_nam_resource_war_begin_hostilities\s*=\s*\{")[0]
        peace = blocks(nam, r"^ADISCORD_nam_resource_war_resolve_peaceful_withdrawal\s*=\s*\{")[0]
        self.assertLess(war.index("declare_war_on"), war.index("ADISCORD_nam_show_resource_war_superevent"))
        self.assertNotIn("ADISCORD_nam_show_resource_war_superevent", peace)
        empire = blocks(effects, r"^ADISCORD_vorkerland_rus_proclaim_last_empire\s*=\s*\{")[0]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_last_empire_proclaimed }", empire)
        self.assertLess(empire.index("set_cosmetic_tag"), empire.index("ADISCORD_vorkerland_show_last_empire_superevent"))
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for event_id, request in ((7, 10), (8, 11)):
            event = _event_block(events, f"ADISCORD_superevent.{event_id}")
            self.assertIn(f"ADISCORD_superevent_request = {request}", event)
            self.assertIn("ADISCORD_superevent_enqueue = yes", event)
            for forbidden in ("declare_war_on", "set_cosmetic_tag", "add_manpower"):
                self.assertNotIn(forbidden, event)

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
        for index in (6, 10, 11, 9, 1, 6, 10, 11, 9, 1):
            request(index)
        self.assertEqual(queue, [10, 11, 9, 1])
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in (6, 10, 11, 9, 1):
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in (6, 10, 11, 9, 1)])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(6)
        self.assertEqual(len(played), 6)

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
                "superevent_nam_resource_war",
                "superevent_rus_last_empire",
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

    def test_postwar_music_plays_from_each_sides_opening_focus(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for name in ("superevent_stelander_shabrat_victory", "superevent_stelander_party_victory"):
            window = blocks(source, rf"^\s*{name}\s*=\s*\{{")[0]
            self.assertNotIn("scoped_play_song", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", playback)
        focuses = (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig")
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
, visible_songs)
        for song in visible_ids:
            for language, localisation in (("English", english_music), ("Russian", russian_music)):
                self.assertRegex(
                    localisation,
                    rf'(?m)^\\s*{re.escape(song)}(?::\\d+)?:\\s*"[^"\\r\\n]+"\\s*        self.assertNotIn(
            'replace_path="music"', (ROOT / "descriptor.mod").read_text()
        )
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        self.assertNotIn('name = "maintheme"', assets)
        for item in PRESENTATIONS:
            self.assertIn(f'name = "{item.name}"', assets)

    def test_nam_war_and_last_empire_are_registered_presentations(self):
        self.assertIn("superevent_nam_resource_war", {item.name for item in PRESENTATIONS})
        self.assertIn("superevent_rus_last_empire", {item.name for item in PRESENTATIONS})

    def test_new_presentations_follow_hostilities_and_guarded_proclamation(self):
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        war = blocks(nam, r"^ADISCORD_nam_resource_war_begin_hostilities\s*=\s*\{")[0]
        peace = blocks(nam, r"^ADISCORD_nam_resource_war_resolve_peaceful_withdrawal\s*=\s*\{")[0]
        self.assertLess(war.index("declare_war_on"), war.index("ADISCORD_nam_show_resource_war_superevent"))
        self.assertNotIn("ADISCORD_nam_show_resource_war_superevent", peace)
        empire = blocks(effects, r"^ADISCORD_vorkerland_rus_proclaim_last_empire\s*=\s*\{")[0]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_last_empire_proclaimed }", empire)
        self.assertLess(empire.index("set_cosmetic_tag"), empire.index("ADISCORD_vorkerland_show_last_empire_superevent"))
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for event_id, request in ((7, 10), (8, 11)):
            event = _event_block(events, f"ADISCORD_superevent.{event_id}")
            self.assertIn(f"ADISCORD_superevent_request = {request}", event)
            self.assertIn("ADISCORD_superevent_enqueue = yes", event)
            for forbidden in ("declare_war_on", "set_cosmetic_tag", "add_manpower"):
                self.assertNotIn(forbidden, event)

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
        for index in (6, 10, 11, 9, 1, 6, 10, 11, 9, 1):
            request(index)
        self.assertEqual(queue, [10, 11, 9, 1])
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in (6, 10, 11, 9, 1):
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in (6, 10, 11, 9, 1)])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(6)
        self.assertEqual(len(played), 6)

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
                "superevent_nam_resource_war",
                "superevent_rus_last_empire",
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

    def test_postwar_music_plays_from_each_sides_opening_focus(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for name in ("superevent_stelander_shabrat_victory", "superevent_stelander_party_victory"):
            window = blocks(source, rf"^\s*{name}\s*=\s*\{{")[0]
            self.assertNotIn("scoped_play_song", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", playback)
        focuses = (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig")
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
,
                    f"{language} music localisation is missing {song}",
                )
        for localisation in (english_music, russian_music):
            self.assertRegex(
                localisation,
                r'(?m)^\\s*adiscord_music(?::\\d+)?:\\s*"A-DISCORD"\\s*        self.assertNotIn(
            'replace_path="music"', (ROOT / "descriptor.mod").read_text()
        )
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        self.assertNotIn('name = "maintheme"', assets)
        for item in PRESENTATIONS:
            self.assertIn(f'name = "{item.name}"', assets)

    def test_nam_war_and_last_empire_are_registered_presentations(self):
        self.assertIn("superevent_nam_resource_war", {item.name for item in PRESENTATIONS})
        self.assertIn("superevent_rus_last_empire", {item.name for item in PRESENTATIONS})

    def test_new_presentations_follow_hostilities_and_guarded_proclamation(self):
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        war = blocks(nam, r"^ADISCORD_nam_resource_war_begin_hostilities\s*=\s*\{")[0]
        peace = blocks(nam, r"^ADISCORD_nam_resource_war_resolve_peaceful_withdrawal\s*=\s*\{")[0]
        self.assertLess(war.index("declare_war_on"), war.index("ADISCORD_nam_show_resource_war_superevent"))
        self.assertNotIn("ADISCORD_nam_show_resource_war_superevent", peace)
        empire = blocks(effects, r"^ADISCORD_vorkerland_rus_proclaim_last_empire\s*=\s*\{")[0]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_last_empire_proclaimed }", empire)
        self.assertLess(empire.index("set_cosmetic_tag"), empire.index("ADISCORD_vorkerland_show_last_empire_superevent"))
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for event_id, request in ((7, 10), (8, 11)):
            event = _event_block(events, f"ADISCORD_superevent.{event_id}")
            self.assertIn(f"ADISCORD_superevent_request = {request}", event)
            self.assertIn("ADISCORD_superevent_enqueue = yes", event)
            for forbidden in ("declare_war_on", "set_cosmetic_tag", "add_manpower"):
                self.assertNotIn(forbidden, event)

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
        for index in (6, 10, 11, 9, 1, 6, 10, 11, 9, 1):
            request(index)
        self.assertEqual(queue, [10, 11, 9, 1])
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in (6, 10, 11, 9, 1):
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in (6, 10, 11, 9, 1)])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(6)
        self.assertEqual(len(played), 6)

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
                "superevent_nam_resource_war",
                "superevent_rus_last_empire",
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

    def test_postwar_music_plays_from_each_sides_opening_focus(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for name in ("superevent_stelander_shabrat_victory", "superevent_stelander_party_victory"):
            window = blocks(source, rf"^\s*{name}\s*=\s*\{{")[0]
            self.assertNotIn("scoped_play_song", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", playback)
        focuses = (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig")
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
,
            )
        self.assertNotIn(
            'replace_path="music"', (ROOT / "descriptor.mod").read_text()
        )
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        self.assertNotIn('name = "maintheme"', assets)
        for item in PRESENTATIONS:
            self.assertIn(f'name = "{item.name}"', assets)

    def test_nam_war_and_last_empire_are_registered_presentations(self):
        self.assertIn("superevent_nam_resource_war", {item.name for item in PRESENTATIONS})
        self.assertIn("superevent_rus_last_empire", {item.name for item in PRESENTATIONS})

    def test_new_presentations_follow_hostilities_and_guarded_proclamation(self):
        from tools.validators.validate_adiscord_superevents import blocks, _event_block

        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        war = blocks(nam, r"^ADISCORD_nam_resource_war_begin_hostilities\s*=\s*\{")[0]
        peace = blocks(nam, r"^ADISCORD_nam_resource_war_resolve_peaceful_withdrawal\s*=\s*\{")[0]
        self.assertLess(war.index("declare_war_on"), war.index("ADISCORD_nam_show_resource_war_superevent"))
        self.assertNotIn("ADISCORD_nam_show_resource_war_superevent", peace)
        empire = blocks(effects, r"^ADISCORD_vorkerland_rus_proclaim_last_empire\s*=\s*\{")[0]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_last_empire_proclaimed }", empire)
        self.assertLess(empire.index("set_cosmetic_tag"), empire.index("ADISCORD_vorkerland_show_last_empire_superevent"))
        events = (ROOT / "events/ADISCORD_superevents.txt").read_text(encoding="utf-8")
        for event_id, request in ((7, 10), (8, 11)):
            event = _event_block(events, f"ADISCORD_superevent.{event_id}")
            self.assertIn(f"ADISCORD_superevent_request = {request}", event)
            self.assertIn("ADISCORD_superevent_enqueue = yes", event)
            for forbidden in ("declare_war_on", "set_cosmetic_tag", "add_manpower"):
                self.assertNotIn(forbidden, event)

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
        for index in (6, 10, 11, 9, 1, 6, 10, 11, 9, 1):
            request(index)
        self.assertEqual(queue, [10, 11, 9, 1])
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in (6, 10, 11, 9, 1):
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in (6, 10, 11, 9, 1)])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(6)
        self.assertEqual(len(played), 6)

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
                "superevent_nam_resource_war",
                "superevent_rus_last_empire",
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

    def test_postwar_music_plays_from_each_sides_opening_focus(self) -> None:
        from tools.validators.validate_adiscord_superevents import blocks

        source = (ROOT / SCRIPTED_GUI).read_text(encoding="utf-8-sig")
        for name in ("superevent_stelander_shabrat_victory", "superevent_stelander_party_victory"):
            window = blocks(source, rf"^\s*{name}\s*=\s*\{{")[0]
            self.assertNotIn("scoped_play_song", window)
        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig")
        playback = blocks(effects, r"^\s*ADISCORD_vorkerland_play_superevent_sound\s*=\s*\{")[0]
        self.assertNotIn("scoped_play_song", playback)
        focuses = (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig")
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
