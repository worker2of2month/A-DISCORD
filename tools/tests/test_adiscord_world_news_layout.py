from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/eventwindow.gui"


def balanced_block(text: str, opening: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening : index + 1]
    raise AssertionError("unclosed GUI block")


def named_block(text: str, type_name: str, name: str) -> str:
    for match in re.finditer(rf"\b{re.escape(type_name)}\s*=\s*\{{", text):
        opening = text.find("{", match.start())
        block = balanced_block(text, opening)
        if re.search(rf'\bname\s*=\s*"?{re.escape(name)}"?', block):
            return block
    raise AssertionError(f"missing {type_name} {name}")


def xy(block: str, assignment: str = "position") -> tuple[int, int]:
    match = re.search(
        rf"\b{re.escape(assignment)}\s*=\s*\{{\s*x\s*=\s*(-?\d+)\s+y\s*=\s*(-?\d+)",
        block,
    )
    if not match:
        raise AssertionError(f"missing {assignment}")
    return int(match.group(1)), int(match.group(2))


class WorldNewsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gui = GUI.read_text(encoding="utf-8-sig")
        cls.news = named_block(cls.gui, "containerWindowType", "EventWindow_News")
        cls.top = named_block(cls.news, "containerWindowType", "top_Window")
        cls.middle = named_block(cls.news, "containerWindowType", "midsection")

    def test_world_news_picture_fills_the_newspaper_width(self) -> None:
        picture = named_block(self.top, "iconType", "event_picture")
        self.assertEqual(xy(picture), (100, 150))
        self.assertIn("scale = 1.26", picture)
        self.assertNotIn('name ="event_picture_overlay"', self.top)
        self.assertNotIn('name = "event_picture_overlay"', self.top)

    def test_news_text_starts_below_the_enlarged_picture(self) -> None:
        title = named_block(self.top, "instantTextBoxType", "Title")
        description = named_block(self.middle, "instantTextBoxType", "Description")
        title_y = xy(title)[1]
        description_global_y = 121 + xy(description)[1]

        self.assertEqual(title_y, 345)
        self.assertEqual(xy(description)[1], 260)
        # 153px native NEWS art scaled by 1.26 ends at 342.78.
        self.assertGreaterEqual(title_y, 343)
        self.assertGreaterEqual(description_global_y, title_y + 32)


if __name__ == "__main__":
    unittest.main()
