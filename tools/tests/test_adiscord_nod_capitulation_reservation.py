from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
STP_ON_ACTIONS = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"
GENERIC_ON_ACTIONS = ROOT / "common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*\{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    opening = text.index("{", match.start(), match.end())
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        ch = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[match.start(): index + 1]
    raise AssertionError(f"unterminated block {name}")


class NodrulCapitulationReservationTests(unittest.TestCase):
    def test_northern_marker_survives_until_generic_router(self) -> None:
        source = read(STP_ON_ACTIONS)
        immediate = named_block(source, "on_capitulation_immediate")
        late = named_block(source, "on_capitulation")
        marker = "STP_cw_northern_capitulation_pending"

        self.assertNotIn(f"ROOT = {{ clr_country_flag = {marker} }}", immediate)
        self.assertIn(
            f"set_country_flag = {{ flag = {marker} value = 1 days = 2 }}",
            immediate,
        )
        self.assertIn(f"ROOT = {{ has_country_flag = {marker} }}", late)
        self.assertNotIn(f"ROOT = {{ clr_country_flag = {marker} }}", late)
        self.assertIn("set_global_flag = skip_default_capitulation", late)

    def test_generic_annex_router_refuses_reserved_northern_capitulation(self) -> None:
        generic = named_block(read(GENERIC_ON_ACTIONS), "on_capitulation")
        marker_guard = (
            "NOT = { ROOT = { has_country_flag = "
            "STP_cw_northern_capitulation_pending } }"
        )
        self.assertIn(marker_guard, generic)
        self.assertIn("clr_global_flag = skip_default_capitulation", generic)


if __name__ == "__main__":
    unittest.main()
