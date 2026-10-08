from __future__ import annotations

import re
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

        # The silent carrier is the one exception: play_song requires a station
        # registration, while factor 0 keeps it out of weighted shuffle.
        self.assertEqual(songs.count('song = "one_minute_of_silence"'), 1)
        self.assertEqual(songs.count('song = "two_minutes_of_silence"'), 1)
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
        visible_ids = re.findall(r'(?m)^\s*song\s*=\s*"([^"]+)"\s*$', visible_songs)
        self.assertTrue(visible_ids)
        for song in visible_ids:
            for localisation in (english_music, russian_music):
                self.assertRegex(
                    localisation,
                    rf'(?m)^\s*{re.escape(song)}:\d*\s*"[^"\r\n]+"\s*$',
                )
        self.assertNotIn('replace_path="music"', (ROOT / "descriptor.mod").read_text())
        self.assertFalse((ROOT / "music/_songs.txt").exists())
        self.assertFalse((ROOT / "music/music.asset").exists())
        assets = (ROOT / "music/ADISCORD_music.asset").read_text()
        self.assertNotIn('name = "maintheme"', assets)
        for item in PRESENTATIONS:
            if item.legacy_music_asset:
                song = item.dedicated_sound_effect.removesuffix("_sound_e")
                self.assertIn(f'name = "{song}"', assets)

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
        for event_id, request in ((7, 10), (8, 11), (9, 12), (10, 13), (11, 14), (12, 15)):
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
        order = (6, 16, 10, 11, 9, 14, 1, 12, 15, 13, 2, 3, 4, 5, 7, 8)
        self.assertEqual(set(order), set(range(1, len(PRESENTATIONS) + 1)))
        for index in order + order:
            request(index)
        self.assertEqual(queue, list(order[1:]))
        self.assertEqual(played, [PRESENTATIONS[5].name])
        for index in order:
            window = fields(windows[PRESENTATIONS[index - 1].name])
            execute(fields(window["effects"])["superevents_button_click"])
        self.assertEqual(played, [PRESENTATIONS[i - 1].name for i in order])
        self.assertEqual(queue, [])
        self.assertEqual(flags, set())
        # A closed presentation can be replayed; no permanent deduplication lock.
        request(16)
        self.assertEqual(len(played), len(order) + 1)

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

    def test_repository_contract_is_clean(self) -> None:
        self.assertEqual(collect_issues(), [])

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
        self.assertEqual(texture, "gfx/interface/superevents/NAM/namestnik lost.png")
        self.assertTrue((ROOT / texture).is_file())

        effects = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        timeout = blocks(effects, r"^ADISCORD_superevent_observer_tick\s*=\s*\{")[0]
        self.assertIn("flag = superevent_itora_vorkerland_war days > 6", timeout)
        self.assertIn("clr_global_flag = superevent_itora_vorkerland_war", timeout)

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

        def matches(conditions, flags, country_flags):
            for child in conditions:
                if child.key == "has_global_flag":
                    if child.value not in flags:
                        return False
                elif child.key == "WRK":
                    for scoped in child.value:
                        self.assertEqual(scoped.key, "has_country_flag")
                        if scoped.value not in country_flags.get("WRK", set()):
                            return False
                else:
                    self.fail(f"Unsupported quote condition: {child.key}")
            return True

        anton_outcome = "ADISCORD_vorkerland_worker_utilitarian_outcome"
        cases = (
            ("worker", {}, ""),
            ("worker", {"WRK": {anton_outcome}}, "_anton"),
            ("worker", {"IVN": {anton_outcome}}, ""),
            ("vlad", {}, "_vlad"),
            ("dorian", {}, "_dorian"),
            ("vlad", {"WRK": {anton_outcome}}, "_vlad"),
            ("dorian", {"WRK": {anton_outcome}}, "_dorian"),
            (None, {}, ""),
            (None, {"WRK": {anton_outcome}}, ""),
        )
        for winner, country_flags, suffix in cases:
            with self.subTest(winner=winner, country_flags=country_flags):
                flags = {f"ADISCORD_vorkerland_{winner}_won"} if winner else set()
                inactive = next(key for key, conditions in choices if matches(conditions, flags, country_flags))
                self.assertEqual(inactive, "superevent_inactive_quote")
                flags.add(name)
                selected = next(key for key, conditions in choices if matches(conditions, flags, country_flags))
                self.assertEqual(selected, f"{name}{suffix}_quote")

        quote_keys = {key for key, _ in choices if key.startswith(name)}
        self.assertEqual(len(quote_keys), 4)
        for language in ("russian", "english"):
            localisation = ROOT / f"localisation/{language}/ADISCORD_superevents_l_{language}.yml"
            contents = localisation.read_text(encoding="utf-8-sig")
            values = []
            for key in quote_keys:
                matches = re.findall(rf'^\s*{key}:\d* "([^"\r\n]+)"$', contents, re.MULTILINE)
                self.assertEqual(len(matches), 1, (language, key))
                self.assertIn(r"\n\n- ", matches[0])
                values.append(matches[0])
            self.assertEqual(len(set(values)), 4)

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
                "superevent_stelander_great",
                "superevent_rus_black_banner",
                "superevent_rus_restoration",
                "superevent_itora_vorkerland_war",
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
