from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative)


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
                return source[match.start() : index + 1]
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
                    candidate = source[match.start() : index + 1]
                    if re.search(
                        rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", candidate
                    ):
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
                return source[start : index + 1]
    raise AssertionError(f"unterminated focus: {focus_id}")


class SouthernTsaygenRevengeTests(unittest.TestCase):
    def test_collapse_seizes_a_real_kefreyt_core_and_notifies_val(self) -> None:
        state = read("history/states/168-168.txt")
        self.assertIn("owner = VAL", state)
        self.assertIn("add_core_of = VAL", state)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_ert")
        self.assertIn(
            "168 = { add_core_of = ERT set_state_owner_to = ERT set_state_controller_to = ERT }",
            setup,
        )

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
            path = (
                ROOT
                / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            )
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), language)
            loc = path.read_text(encoding="utf-8-sig")
            self.assertIn("val_rework.120.t:", loc)
            self.assertIn("val_rework.120.d:", loc)
            self.assertIn("val_rework.120.a:", loc)

    def test_focus_returns_tsaygen_before_crossing_the_perimeter(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        revenge = focus_block(focuses, "VAL_Return_Southern_Tsaygen")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", revenge)
        self.assertIn("prerequisite = { focus = VAL_Foreign_Broker_Licences }", revenge)
        self.assertIn("VAL_southern_tsaygen_revenge_available = yes", revenge)
        self.assertIn(
            "bypass = { has_global_flag = ADISCORD_vorkerland_dirty_opened owns_state = 168 }",
            revenge,
        )
        self.assertIn(
            "unlock_decision_tooltip = VAL_operation_return_southern_tsaygen", revenge
        )
        self.assertNotIn("declare_war_on", revenge)

        perimeter = focus_block(focuses, "VAL_frontier_return_irem")
        self.assertIn(
            "prerequisite = { focus = VAL_Return_Southern_Tsaygen }", perimeter
        )
        self.assertNotIn(
            "prerequisite = { focus = VAL_Foreign_Broker_Licences }", perimeter
        )
        self.assertIn("owns_state = 168", perimeter)
        self.assertIn(
            "unlock_decision_tooltip = VAL_operation_cross_perimeter", perimeter
        )

    def test_revenge_war_has_its_own_live_gate_and_limited_settlement(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(triggers, "VAL_southern_tsaygen_revenge_available")
        for token in (
            "has_war = no",
            "168 = { is_core_of = VAL is_owned_by = ERT is_controlled_by = ERT }",
            "ERT = { exists = yes has_capitulated = no is_subject = no is_in_faction = no }",
        ):
            self.assertIn(token, gate)
        self.assertIn("VAL_frontier_idle = yes", gate)

        perimeter_gate = named_block(triggers, "VAL_wasteland_invasion_available")
        self.assertIn("has_war = no", perimeter_gate)
        self.assertIn("owns_state = 168", perimeter_gate)
        self.assertNotIn("VAL_frontier_idle", perimeter_gate)

        managed = named_block(triggers, "VAL_wasteland_capitulation_managed")
        self.assertIn("has_completed_focus = VAL_Return_Southern_Tsaygen", managed)
        self.assertIn("has_completed_focus = VAL_frontier_return_irem", managed)

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle = named_block(effects, "VAL_settle_wasteland_capitulation")
        revenge_result = settle.split(
            "has_completed_focus = VAL_Return_Southern_Tsaygen", 1
        )[1]
        self.assertIn("VAL = { transfer_state = 168 }", revenge_result)
        older_result = settle.split(
            "has_completed_focus = VAL_frontier_return_irem", 1
        )[1].split("has_completed_focus = VAL_Return_Southern_Tsaygen", 1)[0]
        self.assertIn("VAL = { transfer_state = 169 }", older_result)

    def test_parallel_local_war_cannot_take_kefreyts_capitulation(self) -> None:
        # ERT can capitulate while it also fights SCA. The native winner (FROM)
        # may then be SCA, which must not annex the land Kefreyt occupied.
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        managed = named_block(triggers, "VAL_wasteland_capitulation_managed")
        self.assertNotIn(
            "\tFROM = { OR = { tag = VAL is_subject_of = VAL } }", managed
        )
        self.assertIn(
            "capital_scope = { controller = { OR = { tag = VAL is_subject_of = VAL } } }",
            managed,
        )
        self.assertIn("FROM = { NOT = { tag = VAL } NOT = { is_subject_of = VAL } }", managed)
        self.assertIn(
            "any_owned_state = { controller = { OR = { tag = VAL is_subject_of = VAL } } }",
            managed,
        )

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle = named_block(effects, "VAL_settle_wasteland_capitulation")
        last_claim = settle.rfind("transfer_state = 207")
        third_party = settle.find("has_war_with = event_target:VAL_wasteland_defeated")
        self.assertGreater(third_party, last_claim)
        tail = settle[third_party:]
        self.assertIn("CONTROLLER = { transfer_state = PREV }", tail)
        self.assertIn(
            "limit = { NOT = { tag = VAL } NOT = { is_subject_of = VAL } }\n"
            "\t\twhite_peace = event_target:VAL_wasteland_defeated",
            tail,
        )

    def test_perimeter_war_ends_without_ert_capitulation(self) -> None:
        # ERT can stay in its SCA war indefinitely; holding 169 must end Kefreyt's war.
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        military = named_block(decisions, "VAL_military_operations")
        secure = named_block(military, "VAL_operation_secure_perimeter")
        self.assertIn("has_completed_focus = VAL_frontier_return_irem", secure)
        self.assertIn("169 = { VAL_frontier_controlled = yes }", secure)
        self.assertIn("VAL_settle_perimeter_war = yes", secure)

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle = named_block(effects, "VAL_settle_perimeter_war")
        self.assertLess(settle.index("transfer_state = 169"), settle.index("white_peace = ERT"))

    def test_sector_holder_war_delivers_the_sector_to_the_administration(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        sector = named_block(triggers, "VAL_is_southern_sector_state")
        for state in (167, 170, 171, 184, 185, 203):
            self.assertIn(f"state = {state}", sector)
        # 169 is the administration's own bridgehead; 168 is Kefreyt's core.
        self.assertNotIn("state = 169", sector)
        self.assertNotIn("state = 168", sector)
        holder = named_block(triggers, "VAL_is_southern_sector_holder")
        for tag in ("SCA", "IRT", "RZA", "MLR"):
            self.assertIn(f"tag = {tag}", holder)
        gate = named_block(triggers, "VAL_southern_sector_war_ready")
        self.assertIn("VAL_wasteland_administration_ready = yes", gate)
        self.assertIn("any_enemy_country", gate)
        managed = named_block(triggers, "VAL_wasteland_capitulation_managed")
        self.assertIn("VAL = { has_completed_focus = VAL_Southern_Expansion }", managed)

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        military = named_block(decisions, "VAL_military_operations")
        war = named_block(military, "VAL_operation_reclaim_southern_sector")
        self.assertIn("targets = { SCA IRT RZA MLR }", war)
        self.assertIn(
            "declare_war_on = { target = FROM type = take_state_focus generator = { 167 170 171 184 185 203 } }",
            war,
        )
        self.assertIn("VAL_call_subjects_to_wars = yes", war)
        secure = named_block(military, "VAL_operation_secure_southern_sector")
        self.assertIn("FROM = { VAL_settle_southern_sector_war = yes }", secure)
        # An eastern-belt war without sector land must not offer this peace.
        self.assertIn(
            "FROM = { any_owned_state = { VAL_is_southern_sector_state = yes } }",
            named_block(secure, "visible"),
        )
        self.assertIn(
            "VAL_assign_southern_sector_to_administration = yes",
            named_block(military, "VAL_operation_assign_southern_sector"),
        )

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        transfer = named_block(effects, "VAL_transfer_southern_sector_state")
        self.assertIn("WCA = { transfer_state = PREV }", transfer)
        self.assertIn("VAL = { transfer_state = PREV }", transfer)
        limited = named_block(effects, "VAL_settle_southern_sector_war")
        self.assertLess(
            limited.index("VAL_transfer_southern_sector_state = yes"),
            limited.index("white_peace = PREV"),
        )
        settle = named_block(effects, "VAL_settle_wasteland_capitulation")
        # The fixed sectors go to the puppet even where a third party occupies
        # them; only the remaining land falls to the occupier in the tail.
        southern = settle.split("has_completed_focus = VAL_Southern_Expansion", 1)[1]
        southern = southern.split("has_completed_focus = VAL_frontier_return_irem", 1)[0]
        self.assertIn("VAL_is_southern_sector_state = yes", southern)
        self.assertIn("state = 169", southern)
        self.assertNotIn("is_controlled_by", southern)
        eastern = settle.split("has_completed_focus = VAL_Eastern_Expansion", 1)[1]
        eastern = eastern.split("# Any holder other than ERT", 1)[0]
        self.assertNotIn("is_controlled_by", eastern)
        holders = settle.split("# Any holder other than ERT", 1)[1].split("# The same capitulation", 1)[0]
        self.assertNotIn("is_controlled_by", holders)
        # The eastern IRT settlement keeps its own focus gate.
        self.assertIn("has_completed_focus = VAL_Eastern_Expansion", settle)
        self.assertNotIn("WCA = { transfer_state = 168 }", settle)
        southern = settle.split("has_completed_focus = VAL_Southern_Expansion", 1)[1]
        self.assertIn("VAL = { transfer_state = 168 }", southern.split("else_if", 1)[0])
        self.assertGreaterEqual(
            settle.count("VAL = { VAL_assign_southern_sector_to_administration = yes }"), 2
        )

        for language in ("english", "russian"):
            loc = read(
                f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            )
            for key in (
                "VAL_operation_secure_perimeter",
                "VAL_operation_secure_perimeter_desc",
                "VAL_perimeter_held_tt",
                "VAL_secure_perimeter_tt",
                "VAL_operation_reclaim_southern_sector",
                "VAL_operation_reclaim_southern_sector_desc",
                "VAL_declares_war_southern_sector_tt",
                "VAL_operation_secure_southern_sector",
                "VAL_operation_secure_southern_sector_desc",
                "VAL_southern_sector_holdings_secured_tt",
                "VAL_secure_southern_sector_tt",
                "VAL_operation_assign_southern_sector",
                "VAL_operation_assign_southern_sector_desc",
                "VAL_southern_sector_held_tt",
                "VAL_assign_southern_sector_tt",
            ):
                self.assertIn(f" {key}:0 \"", loc, f"{language}: {key}")

    def test_late_ultimatum_is_a_fallback_not_the_primary_claim(self) -> None:
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        demand = named_block(decisions, "VAL_frontier_demand_ERT")
        self.assertIn("has_completed_focus = VAL_Return_Southern_Tsaygen", demand)
        self.assertNotIn("has_completed_focus = VAL_frontier_return_irem", demand)

        for language in ("english", "russian"):
            loc = read(
                f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            )
            self.assertIn("VAL_Return_Southern_Tsaygen:", loc)
            self.assertIn("VAL_Return_Southern_Tsaygen_desc:", loc)
            self.assertIn("VAL_return_southern_tsaygen_war_tt:", loc)

    def test_southern_wars_are_launched_from_military_operations(self) -> None:
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        military = named_block(decisions, "VAL_military_operations")
        expected = {
            "VAL_operation_return_southern_tsaygen": "generator = { 168 }",
            "VAL_operation_cross_perimeter": "generator = { 169 }",
            "VAL_operation_expand_southern_bridgehead": "generator = { 167 170 171 184 185 203 }",
            "VAL_operation_eastern_security_belt": "generator = { 178 180 181 182 183 193 206 207 }",
        }
        for decision_id, war_goal in expected.items():
            block = named_block(military, decision_id)
            if decision_id == "VAL_operation_return_southern_tsaygen":
                self.assertIn("VAL_begin_southern_tsaygen_campaign = yes", block)
                effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
                start = named_block(effects, "VAL_begin_southern_tsaygen_campaign")
                self.assertIn("VAL_southern_tsaygen_revenge_available = yes", start)
                self.assertIn("var = VAL_frontier_target value = 4", start)
                self.assertIn("VAL_frontier_start_war = yes", start)
                continue
            self.assertIn(war_goal, block)
            self.assertIn("VAL_call_subjects_to_wars = yes", block)

        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for focus_id in (
            "VAL_Return_Southern_Tsaygen",
            "VAL_frontier_return_irem",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        ):
            self.assertNotIn("declare_war_on", focus_block(focuses, focus_id))


if __name__ == "__main__":
    unittest.main()
