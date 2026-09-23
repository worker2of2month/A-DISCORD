import importlib.util
import json
import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/eventwindow.gui"
GFX = ROOT / "interface/eventwindow.gfx"
EVENT_PICTURES_GFX = ROOT / "interface/ADISCORD_eventpictures.gfx"
DEBUG_EVENTS = ROOT / "events/ADISCORD_scenario_debug_events.txt"
DEBUG_LOCALISATION = ROOT / "localisation/russian/ADISCORD_scenario_debug_l_russian.yml"
OWNERS = ROOT / "tools/data/generated_output_owners.json"
BUILDER = ROOT / "tools/builders/build_adiscord_event_ui_assets.py"


def _balanced_block(text: str, opening_brace: int) -> str:
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening_brace, len(text)):
        character = text[index]
        if escaped:
            escaped = False
            continue
        if character == "\\" and quoted:
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[opening_brace : index + 1]
    raise AssertionError("unterminated GUI block")


def _named_block(text: str, type_name: str, name: str) -> str:
    for match in re.finditer(rf"\b{re.escape(type_name)}\s*=\s*\{{", text):
        opening_brace = text.find("{", match.start())
        block = _balanced_block(text, opening_brace)
        depth = 0
        direct_text: list[str] = []
        quoted = False
        escaped = False
        for character in block:
            if escaped:
                escaped = False
                if depth == 1:
                    direct_text.append(character)
                continue
            if character == "\\" and quoted:
                escaped = True
                if depth == 1:
                    direct_text.append(character)
                continue
            if character == '"':
                quoted = not quoted
            if not quoted and character == "{":
                depth += 1
                continue
            if not quoted and character == "}":
                depth -= 1
                continue
            if depth == 1:
                direct_text.append(character)
        if re.search(
            rf'\bname\s*=\s*"{re.escape(name)}"',
            "".join(direct_text),
        ):
            return block
    raise AssertionError(f"missing {type_name} named {name}")


def _xy(block: str, assignment: str) -> tuple[int, int]:
    match = re.search(
        rf"\b{re.escape(assignment)}\s*=\s*\{{\s*x\s*=\s*(-?\d+)\s+y\s*=\s*(-?\d+)",
        block,
    )
    if not match:
        raise AssertionError(f"missing {assignment} x/y in block")
    return int(match.group(1)), int(match.group(2))


def _size(block: str) -> tuple[int, int]:
    match = re.search(
        r"\bsize\s*=\s*\{\s*width\s*=\s*(\d+)\s+height\s*=\s*(\d+)",
        block,
    )
    if not match:
        raise AssertionError("missing width/height size in block")
    return int(match.group(1)), int(match.group(2))


def _integer(block: str, assignment: str) -> int:
    match = re.search(rf"\b{re.escape(assignment)}\s*=\s*(\d+)", block)
    if not match:
        raise AssertionError(f"missing integer assignment {assignment}")
    return int(match.group(1))


def _localisation_value(text: str, key: str) -> str:
    match = re.search(
        rf'^\s*{re.escape(key)}:\s*"([^"]*)"\s*$',
        text,
        flags=re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"missing localisation key {key}")
    return match.group(1).replace("\\n", "\n")


def _event_block(text: str, event_id: str) -> str:
    for match in re.finditer(r"\bcountry_event\s*=\s*\{", text):
        opening_brace = text.find("{", match.start())
        block = _balanced_block(text, opening_brace)
        if re.search(rf"\bid\s*=\s*{re.escape(event_id)}\b", block):
            return block
    raise AssertionError(f"missing country_event {event_id}")


class EventWindowUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gui = GUI.read_text(encoding="utf-8-sig")
        cls.gfx = GFX.read_text(encoding="utf-8-sig")
        cls.event_pictures = EVENT_PICTURES_GFX.read_text(encoding="utf-8-sig")
        cls.debug_events = DEBUG_EVENTS.read_text(encoding="utf-8-sig")
        cls.debug_localisation = DEBUG_LOCALISATION.read_text(encoding="utf-8-sig")
        cls.window = _named_block(cls.gui, "containerWindowType", "EventWindow")

    def test_ordinary_window_uses_native_adaptive_sections(self):
        self.assertEqual(_xy(self.window, "position"), (-307, -327))
        self.assertEqual(_size(self.window), (615, 654))
        root_background = _named_block(self.window, "background", "Background")
        self.assertIn('spriteType = "GFX_tiled_window_transparent"', root_background)

        top = _named_block(self.window, "containerWindowType", "top_Window")
        middle = _named_block(self.window, "containerWindowType", "midsection")
        bottom = _named_block(self.window, "containerWindowType", "bottom_Window")
        self.assertEqual(_xy(top, "position"), (0, 0))
        self.assertEqual(_size(top), (615, 100))
        self.assertEqual(_xy(middle, "position"), (0, 100))
        self.assertEqual(_size(middle), (615, 28))
        self.assertEqual(_xy(bottom, "position"), (0, 128))
        self.assertEqual(_size(bottom), (615, 372))
        self.assertEqual(
            _xy(bottom, "position")[1],
            _xy(middle, "position")[1] + _size(middle)[1],
        )
        for section in (top, middle, bottom):
            self.assertRegex(section, r"\bmoveable\s*=\s*yes\b")

    def test_picture_text_and_options_have_one_clear_reading_order(self):
        top = _named_block(self.window, "containerWindowType", "top_Window")
        middle = _named_block(self.window, "containerWindowType", "midsection")
        bottom = _named_block(self.window, "containerWindowType", "bottom_Window")

        title = _named_block(top, "instantTextBoxType", "Title")
        picture = _named_block(bottom, "iconType", "event_picture")
        self.assertNotIn('name = "event_picture"', top)
        description = _named_block(middle, "instantTextBoxType", "Description")
        options = _named_block(bottom, "gridBoxType", "options_grid")
        option_entry = _named_block(self.gui, "containerWindowType", "event_option_entry")
        option_name = _named_block(option_entry, "instantTextBoxType", "Name")

        self.assertEqual(_xy(title, "position"), (54, 39))
        self.assertIn("maxWidth = 507", title)
        self.assertIn('font = "hoi_24header"', title)
        self.assertEqual(_xy(picture, "position"), (308, 100))
        self.assertRegex(picture, r"\bcenterposition\s*=\s*yes\b")
        self.assertEqual(_xy(description, "position"), (54, 14))
        self.assertIn("maxWidth = 487", description)
        self.assertIn("maxHeight = 230", description)
        self.assertIn('font = "hoi_16mbs"', description)
        self.assertEqual(_xy(options, "position"), (157, 204))
        self.assertEqual(_size(options), (300, 156))
        self.assertIn("slotsize = { width = 300 height = 39 }", options)
        self.assertEqual(_size(option_entry), (300, 39))
        self.assertIn('font = "hoi_18mbs"', option_name)
        self.assertIn("maxWidth = 290", option_name)
        self.assertIn("maxHeight = 35", option_name)

    def test_description_base_padding_and_four_option_slots_fit_the_sections(self):
        middle = _named_block(self.window, "containerWindowType", "midsection")
        bottom = _named_block(self.window, "containerWindowType", "bottom_Window")
        description = _named_block(middle, "instantTextBoxType", "Description")
        options = _named_block(bottom, "gridBoxType", "options_grid")

        self.assertRegex(middle, r"\bclipping\s*=\s*no\b")
        _, description_y = _xy(description, "position")
        self.assertLessEqual(
            _size(middle)[1] - description_y,
            24,
        )
        _, options_y = _xy(options, "position")
        slot_match = re.search(r"slotsize\s*=\s*\{\s*width\s*=\s*300\s+height\s*=\s*(\d+)", options)
        self.assertIsNotNone(slot_match)
        self.assertLessEqual(options_y + int(slot_match.group(1)) * 4, _size(bottom)[1])

        # Match the native expanding COUNTRY Description. A scrollbar
        # can clip the painted text while the handler still reserves its full height.
        # This checks the chosen configuration, not the engine's runtime geometry.
        self.assertNotRegex(description, r"\bfixedsize\s*=\s*yes\b")
        self.assertNotRegex(description, r"\bscrollbarType\s*=")

    def test_picture_has_a_local_nonnegative_anchor_before_the_options(self):
        top = _named_block(self.window, "containerWindowType", "top_Window")
        bottom = _named_block(self.window, "containerWindowType", "bottom_Window")
        picture = _named_block(bottom, "iconType", "event_picture")
        options = _named_block(bottom, "gridBoxType", "options_grid")
        self.assertNotIn('name = "event_picture"', top)
        _, picture_center_y = _xy(picture, "position")
        self.assertRegex(picture, r"\bcenterposition\s*=\s*yes\b")
        picture_y = picture_center_y - 184 / 2
        self.assertGreaterEqual(picture_y, 0)
        self.assertLessEqual(picture_y + 184, _xy(options, "position")[1])

    def test_actual_country_picture_sizes_are_centered_inside_the_frame(self):
        from tools.builders.build_adiscord_technology_system import BASE_GAME
        from tools.lib.adiscord_ui_contracts import native_sprite_blocks

        bottom = _named_block(self.window, "containerWindowType", "bottom_Window")
        picture = _named_block(bottom, "iconType", "event_picture")
        self.assertRegex(picture, r"\bcenterposition\s*=\s*yes\b")
        self.assertNotRegex(picture, r"\b(?:scale|size)\s*=")
        center_x, center_y = _xy(picture, "position")
        sprites = native_sprite_blocks(BASE_GAME, {
            "GFX_report_event_generic_read_write",
            "GFX_news_event_hol_polderen",
        })
        sprites["GFX_event_adiscord_ui_test"] = _named_block(
            self.event_pictures, "spriteType", "GFX_event_adiscord_ui_test",
        )
        expected = {
            "GFX_report_event_generic_read_write": ((210, 176), (203, 12, 413, 188)),
            "GFX_news_event_hol_polderen": ((396, 153), (110, 23.5, 506, 176.5)),
            "GFX_event_adiscord_ui_test": ((507, 184), (54.5, 8, 561.5, 192)),
        }
        for sprite, (expected_size, expected_bounds) in expected.items():
            with self.subTest(sprite=sprite):
                texture = re.search(r'texturefile\s*=\s*"([^"]+)"', sprites[sprite]).group(1)
                path = ROOT / texture
                if not path.is_file():
                    path = BASE_GAME / texture
                with Image.open(path) as image:
                    width, height = image.size
                self.assertEqual((width, height), expected_size)
                bounds = (center_x - width / 2, center_y - height / 2,
                          center_x + width / 2, center_y + height / 2)
                self.assertEqual(bounds, expected_bounds)
                left, top, right, bottom_y = bounds
                # The 507px artwork has a half-pixel centre. Integer GUI x=308
                # permits only the corresponding half-pixel raster rounding.
                left_gap, right_gap = left - 54, 561 - right
                self.assertGreaterEqual(min(left_gap, right_gap), -0.5)
                self.assertLessEqual(abs(left_gap - right_gap), 1)
                self.assertGreaterEqual(top, 8)
                self.assertLessEqual(bottom_y, 192)
                self.assertLess(bottom_y, _xy(_named_block(bottom, "gridBoxType", "options_grid"), "position")[1])

    def test_debug_matrix_covers_short_long_and_extreme_overflow_text(self):
        short_text = _localisation_value(
            self.debug_localisation,
            "ADISCORD_event_ui_test.2.desc",
        )
        long_text = _localisation_value(
            self.debug_localisation,
            "ADISCORD_event_ui_test.3.desc",
        )
        overflow_text = _localisation_value(
            self.debug_localisation,
            "ADISCORD_event_ui_test.5.desc",
        )

        self.assertLessEqual(len(short_text), 80)
        self.assertGreaterEqual(len(long_text), 700)
        self.assertGreaterEqual(len(overflow_text), 1200)
        long_words = re.findall(r"[A-Za-zА-Яа-яЁё]+", long_text.lower())
        self.assertGreaterEqual(len(set(long_words)), 40)
        self.assertIn("\n\n", long_text)

        expected_option_counts = {1: 4, 2: 1, 3: 4, 4: 1, 5: 1}
        for number, expected_count in expected_option_counts.items():
            with self.subTest(event=number):
                block = _event_block(
                    self.debug_events,
                    f"ADISCORD_event_ui_test.{number}",
                )
                self.assertEqual(
                    len(re.findall(r"\boption\s*=", block)),
                    expected_count,
                )

    def test_generated_surfaces_have_exact_visible_dimensions(self):
        expected_sizes = {
            "gfx/interface/event_popup_bg.png": (615, 650),
            "gfx/interface/event_popup_top.png": (615, 100),
            "gfx/interface/event_popup_middle.png": (615, 64),
            "gfx/interface/event_popup_bottom.png": (615, 372),
            "gfx/interface/event_option_entry_adiscord.png": (300, 35),
            "gfx/interface/events/preview/ADISCORD_event_window_preview.png": (1600, 900),
            "gfx/event_pictures/event_adiscord_ui_test.png": (507, 184),
        }
        for relative_path, expected_size in expected_sizes.items():
            path = ROOT / relative_path
            with self.subTest(path=relative_path):
                self.assertTrue(path.is_file(), f"missing generated output: {relative_path}")
                with Image.open(path) as image:
                    self.assertEqual(image.size, expected_size)

    def test_each_adaptive_section_owns_an_opaque_piece_of_the_shell(self):
        for relative_path in (
            "gfx/interface/event_popup_top.png",
            "gfx/interface/event_popup_middle.png",
            "gfx/interface/event_popup_bottom.png",
        ):
            with self.subTest(path=relative_path):
                with Image.open(ROOT / relative_path) as image:
                    alpha = image.convert("RGBA").getchannel("A")
                self.assertGreaterEqual(alpha.getextrema()[0], 220)

    def test_option_asset_leaves_four_pixels_between_rows(self):
        option_entry = _named_block(self.gui, "containerWindowType", "event_option_entry")
        _, slot_height = _size(option_entry)
        with Image.open(ROOT / "gfx/interface/event_option_entry_adiscord.png") as image:
            _, background_height = image.size
        self.assertEqual(slot_height - background_height, 4)

    def test_gfx_and_debug_events_bind_the_dedicated_test_picture(self):
        self.assertIn('name = "GFX_event_popup_top"', self.gfx)
        self.assertIn('name = "GFX_event_popup_middle"', self.gfx)
        self.assertIn('name = "GFX_event_popup_bottom"', self.gfx)
        self.assertIn('name = "GFX_event_adiscord_ui_test"', self.event_pictures)
        self.assertIn(
            'texturefile = "gfx/event_pictures/event_adiscord_ui_test.png"',
            self.event_pictures,
        )
        self.assertEqual(
            self.debug_events.count("picture = GFX_event_adiscord_ui_test"),
            5,
        )

    def test_event_asset_builder_is_registered_and_deterministic(self):
        self.assertTrue(BUILDER.is_file(), "missing event UI asset builder")
        registry = json.loads(OWNERS.read_text(encoding="utf-8"))
        owner = next(
            (entry for entry in registry["families"] if entry["id"] == "event_ui_assets"),
            None,
        )
        self.assertIsNotNone(owner, "event_ui_assets is not registered")
        self.assertIn("event_ui_assets", registry["apply_sequence"])
        self.assertEqual(
            owner["owner_module"],
            "tools.builders.build_adiscord_event_ui_assets",
        )
        self.assertEqual(owner["ownership_mode"], "exclusive")

        spec = importlib.util.spec_from_file_location("adiscord_event_ui_builder", BUILDER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        outputs = module.expected_outputs()
        self.assertEqual(
            {path.relative_to(ROOT).as_posix() for path in outputs},
            set(owner["output_globs"]),
        )

    def test_nonstandard_event_windows_remain_available(self):
        for window_name in (
            "EventWindow_Operative",
            "EventWindow_leader",
            "EventWindow_News",
        ):
            with self.subTest(window=window_name):
                _named_block(self.gui, "containerWindowType", window_name)

    def test_every_visible_event_has_art_for_its_window_format(self):
        from tools.validators.validate_adiscord_event_ids import (
            _mask_comments_and_strings, _brace_depths, _closing_brace,
        )

        sprite_text = self.event_pictures + (ROOT / "interface/ADISCORD_event_art.gfx").read_text(encoding="utf-8")
        checked = 0
        for path in sorted((ROOT / "events").glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            masked = _mask_comments_and_strings(text)
            depths = _brace_depths(masked)
            for match in re.finditer(r"\b(country_event|news_event)\s*=\s*\{", masked):
                if depths[match.start()] != 0:
                    continue
                end = _closing_brace(masked, masked.index("{", match.start()))
                fields = {}
                for field in re.finditer(r"\b(id|hidden|picture)\s*=\s*([^\s{}]+)", masked[match.end():end]):
                    if depths[match.end() + field.start()] == 1:
                        fields[field[1]] = field[2]
                if fields.get("hidden") == "yes":
                    continue
                with self.subTest(event=fields.get("id"), path=path.name):
                    self.assertIn("picture", fields, "visible event uses an unformatted engine fallback")
                    kind = match[1].split("_")[0]
                    expected = (507, 184) if kind == "country" else (396, 153)
                    sprite = _named_block(sprite_text, "spriteType", fields["picture"])
                    texture = re.search(r'texturefile\s*=\s*"([^"]+)"', sprite, re.I)[1]
                    if kind == "news":
                        self.assertEqual(Path(texture).parent.as_posix(),
                                         "gfx/event_pictures/standard/news")
                        self.assertRegex(Path(texture).name, r"^[a-z0-9]+(?:_[a-z0-9]+)*\.png$")
                    with Image.open(ROOT / texture) as artwork:
                        self.assertEqual(artwork.size, expected)
                        self.assertEqual(artwork.convert("RGBA").getchannel("A").getextrema(), (255, 255))
                    checked += 1
        self.assertGreater(checked, 100, "event audit unexpectedly skipped the main story files")

    def test_news_art_uses_preserved_authored_sources(self):
        from PIL import ImageOps
        from tools.builders.build_adiscord_event_pictures import ART, NEWS_SCENES, formatted_art

        for scene, (_, formats) in ART.items():
            if "news" not in formats:
                continue
            with self.subTest(scene=scene):
                name = NEWS_SCENES.get(scene, scene)
                with Image.open(ROOT / "gfx/event_pictures/source/news" / (name + ".png")) as source:
                    expected = ImageOps.fit(source.convert("RGB"), (396, 153),
                                            method=Image.Resampling.LANCZOS)
                self.assertEqual(formatted_art(scene, "news").tobytes(), expected.tobytes())

    def test_event_artwork_builder_is_current_and_owned(self):
        from tools.builders.build_adiscord_event_pictures import expected_outputs
        registry = json.loads(OWNERS.read_text(encoding="utf-8"))
        family = next(item for item in registry["families"] if item["id"] == "event_pictures")
        self.assertLess(registry["apply_sequence"].index("event_ui_assets"),
                        registry["apply_sequence"].index("event_pictures"))
        for path, expected in expected_outputs().items():
            with self.subTest(path=path):
                self.assertTrue(any(path.relative_to(ROOT).match(pattern) for pattern in family["output_globs"]))
                self.assertEqual(path.read_bytes(), expected)

    def test_shared_option_template_still_fits_every_event_window(self):
        for window_name in (
            "EventWindow",
            "EventWindow_Operative",
            "EventWindow_leader",
            "EventWindow_News",
        ):
            with self.subTest(window=window_name):
                window = _named_block(self.gui, "containerWindowType", window_name)
                options = _named_block(window, "gridBoxType", "options_grid")
                self.assertRegex(options, r"slotsize\s*=\s*\{\s*width\s*=\s*300\b")



class StelanderNewsArtworkTests(unittest.TestCase):
    def test_public_war_reports_use_native_news_picture_dimensions(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        events = parse_clausewitz((ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8-sig"))
        expected = {f"ADISCORD_STP_cw.{number}" for number in (70, 71, 72, 73, 80, 81, 82)}
        pictures = {}
        for event in events:
            if event.key != "news_event":
                continue
            values = {entry.key: entry.value for entry in event.value if isinstance(entry.value, str)}
            if values.get("id") in expected:
                self.assertNotIn(values["id"], pictures)
                pictures[values["id"]] = values["picture"]
        self.assertEqual(set(pictures), expected)
        for event_id, name in pictures.items():
            self.assertTrue(name.startswith("GFX_news_event_"), f"{event_id}: country report sprite in news window")
        sprites = (ROOT / "interface/ADISCORD_event_art.gfx").read_text(encoding="utf-8")
        for event_id, name in pictures.items():
            sprite = _named_block(sprites, "spriteType", name)
            texture = re.search(r'texturefile\s*=\s*"([^"]+)"', sprite).group(1)
            path = ROOT / texture
            with Image.open(path) as bitmap:
                self.assertEqual(bitmap.width, 396, event_id)
                self.assertEqual(bitmap.height, 153, event_id)

if __name__ == "__main__":
    unittest.main()
