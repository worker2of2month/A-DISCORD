from tools.lib.on_actions import read_country_on_actions, read_scripted_peace
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
STP_ON_ACTIONS = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"
GUARD_ON_ACTIONS = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
GENERIC_ON_ACTIONS = ROOT / "common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"


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
    def test_existing_router_marks_managed_northern_capitulation(self) -> None:
        immediate = named_block(read_country_on_actions(STP_ON_ACTIONS, 'stelander'), "on_capitulation_immediate")
        self.assertIn(
            "ROOT = { set_country_flag = STP_cw_northern_capitulation_pending }",
            immediate,
        )

    def test_durable_guard_bridges_immediate_and_generic_callbacks(self) -> None:
        source = read_scripted_peace(Path(GUARD_ON_ACTIONS).with_name('09_ADISCORD_scripted_peace_on_actions.txt'), 'northern_reservation')
        immediate = named_block(source, "on_capitulation_immediate")
        late = named_block(source, "on_capitulation")
        pending = "STP_cw_northern_capitulation_pending"
        reserved = "STP_cw_northern_capitulation_reserved"

        self.assertIn(f"ROOT = {{ has_country_flag = {pending} }}", immediate)
        self.assertIn(
            f"set_country_flag = {{ flag = {reserved} value = 1 days = 2 }}",
            " ".join(immediate.split()),
        )
        self.assertIn(f"ROOT = {{ has_country_flag = {reserved} }}", late)
        self.assertIn("set_global_flag = skip_default_capitulation", late)

    def test_generic_annex_router_still_honors_reservation_bus(self) -> None:
        generic = named_block(read(GENERIC_ON_ACTIONS), "on_capitulation")
        self.assertIn("NOT = { has_global_flag = skip_default_capitulation }", generic)
        self.assertIn("clr_global_flag = skip_default_capitulation", generic)

    def test_nodrul_defeat_cedes_border_states_and_ainholm_claims(self) -> None:
        source = read(EFFECTS)
        defeat = named_block(source, "STP_cw_settle_northern_defeat")
        ainholm = named_block(source, "STP_cw_cede_ainholm_to_frontier")
        self.assertIn("YPR = { transfer_state = 17 }", defeat)
        self.assertIn("YPR = { transfer_state = 18 }", defeat)
        self.assertIn("STP_cw_cede_ainholm_to_frontier = yes", defeat)
        self.assertIn("TFF = { transfer_state = 118 }", ainholm)
        self.assertIn("TFF = { transfer_state = 119 }", ainholm)
        self.assertIn("tag = AIN", ainholm)
        self.assertIn("tag = NOD", ainholm)
        self.assertNotIn("annex_country", defeat + ainholm)
        self.assertNotIn("every_owned_state", defeat + ainholm)


if __name__ == "__main__":
    unittest.main()
