from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", match.start())
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    raise AssertionError(f"unterminated block: {name}")


def event_block(source: str, event_id: str) -> str:
    for match in re.finditer(r"(?m)^\s*country_event\s*=\s*\{", source):
        opening = source.find("{", match.start())
        depth = 0
        quoted = False
        escaped = False
        for index in range(opening, len(source)):
            char = source[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = source[match.start():index + 1]
                    if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", candidate):
                        return candidate
                    break
    raise AssertionError(f"missing event: {event_id}")


def focus_block(source: str, focus_id: str) -> str:
    marker = f"id = {focus_id}"
    pos = source.index(marker)
    start = source.rfind("focus = {", 0, pos)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"unterminated focus: {focus_id}")


class SouthernTsaygenRevengeTests(unittest.TestCase):
    def test_collapse_seizes_a_real_kefreyt_core_and_notifies_val(self) -> None:
        state = read("history/states/168-168.txt")
        self.assertIn("owner = VAL", state)
        self.assertIn("add_core_of = VAL", state)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_ert")
        self.assertIn("168 = { add_core_of = ERT set_state_owner_to = ERT set_state_controller_to = ERT }", setup)

        events = read("events/ADISCORD_vorkerland_events.txt")
        collapse = event_block(events, "ADISCORD_vorkerland_collapse.13")
        self.assertIn("ADISCORD_vorkerland_setup_ert = yes", collapse)
        self.assertIn("country_event = { id = val_rework.120 hours = 6 }", collapse)
        self.assertIn("168 = { is_core_of = VAL is_owned_by = ERT }", collapse)

    def test_loss_event_frames_the_claim_as_revenge(self) -> None:
        events = read("events/ADISCORD_VAL_contract_events.txt")
        block = event_block(events, "val_rework.120")
        self.assertIn("title = val_rework.120.t", block)
        self.assertIn("168 = { is_core_of = VAL is_owned_by = ERT }", block)
        self.assertIn("add_war_support = 0.03", block)

        for language in ("english", "russian"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), language)
            loc = path.read_text(encoding="utf-8-sig")
            self.assertIn("val_rework.120.t:", loc)
            self.assertIn("val_rework.120.d:", loc)
            self.assertIn("val_rework.120.a:", loc)

    def test_focus_returns_tsaygen_before_crossing_the_perimeter(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        revenge = focus_block(focuses, "VAL_Return_Southern_Tsaygen")
        self.assertIn("prerequisite = { focus = VAL_Foreign_Broker_Licences }", revenge)
        self.assertIn("VAL_southern_tsaygen_revenge_available = yes", revenge)
        self.assertIn("bypass = { has_global_flag = ADISCORD_vorkerland_dirty_opened owns_state = 168 }", revenge)
        self.assertIn("declare_war_on = { target = ERT type = take_state_focus generator = { 168 } }", revenge)

        perimeter = focus_block(focuses, "VAL_frontier_return_irem")
        self.assertIn("prerequisite = { focus = VAL_Return_Southern_Tsaygen }", perimeter)
        self.assertNotIn("prerequisite = { focus = VAL_Foreign_Broker_Licences }", perimeter)

    def test_revenge_war_has_its_own_live_gate_and_limited_settlement(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(triggers, "VAL_southern_tsaygen_revenge_available")
        for token in (
            "has_war = no",
            "168 = { is_core_of = VAL is_owned_by = ERT is_controlled_by = ERT }",
            "ERT = { exists = yes has_capitulated = no is_subject = no is_in_faction = no }",
        ):
            self.assertIn(token, gate)

        managed = named_block(triggers, "VAL_wasteland_capitulation_managed")
        self.assertIn("has_completed_focus = VAL_Return_Southern_Tsaygen", managed)
        self.assertIn("has_completed_focus = VAL_frontier_return_irem", managed)

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle = named_block(effects, "VAL_settle_wasteland_capitulation")
        revenge_result = settle.split("has_completed_focus = VAL_Return_Southern_Tsaygen", 1)[1]
        self.assertIn("VAL = { transfer_state = 168 }", revenge_result)
        older_result = settle.split("has_completed_focus = VAL_frontier_return_irem", 1)[1].split(
            "has_completed_focus = VAL_Return_Southern_Tsaygen", 1
        )[0]
        self.assertIn("VAL = { transfer_state = 169 }", older_result)

    def test_late_ultimatum_is_a_fallback_not_the_primary_claim(self) -> None:
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        demand = named_block(decisions, "VAL_frontier_demand_ERT")
        self.assertIn("has_completed_focus = VAL_Return_Southern_Tsaygen", demand)
        self.assertNotIn("has_completed_focus = VAL_frontier_return_irem", demand)

        for language in ("english", "russian"):
            loc = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            self.assertIn("VAL_Return_Southern_Tsaygen:", loc)
            self.assertIn("VAL_Return_Southern_Tsaygen_desc:", loc)
            self.assertIn("VAL_return_southern_tsaygen_war_tt:", loc)


if __name__ == "__main__":
    unittest.main()
