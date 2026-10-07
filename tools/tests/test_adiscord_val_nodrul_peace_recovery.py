from pathlib import Path
import unittest
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt"
ON_ACTIONS = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_VAL_decisions.txt"
EVENTS = ROOT / "events/ADISCORD_VAL_contract_events.txt"
VAL_ON_ACTIONS = ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"


class FinalSettlementFixture:
    """Run the production finalizer with native capitulation visibility delayed."""

    def __init__(self, first, last):
        self.tags = ("VAL", "NOD", "STP", "STS", "YPR", "AIN")
        self.flags = {tag: set() for tag in self.tags}
        self.flags[first].add("VAL_final_defeat_pending")
        self.flags[last].update(("VAL_final_defeat_pending", "VAL_final_capitulation_immediate"))
        self.flags[last].add("VAL_coalition_capitulation_current")
        self.capitulated = {first}
        self.members = {first, last}
        self.installed = []
        self.reserved = False
        self.effects = {e.key: e.value for e in parse_clausewitz(EFFECTS.read_text(encoding="utf-8"))}
        self.triggers = {e.key: e.value for e in parse_clausewitz(TRIGGERS.read_text(encoding="utf-8"))}
        self.root = last
        self.previous = None
        self.neutral = set()
        self.subjects = {}
        self.majors = {"VAL", "NOD", "STP", "STS"}

    def matches(self, entries, scope):
        def match(entry):
            key, value = entry.key, entry.value
            if key in ("AND", "limit"):
                return self.matches(value, scope)
            if key == "OR":
                return any(self.matches([item], scope) for item in value)
            if key == "NOT":
                return not any(self.matches([item], scope) for item in value)
            if key in self.tags or key == "ROOT":
                return self.matches(value, self.root if key == "ROOT" else key)
            if key in self.triggers:
                return self.matches(self.triggers[key], scope) == (value == "yes")
            if key == "has_country_flag":
                return value in self.flags[scope]
            if key == "is_debug":
                return value == "no"
            if key == "tag":
                return scope == (self.root if value == "ROOT" else value)
            if key == "any_other_country":
                previous = self.previous
                self.previous = scope
                result = any(t != scope and self.matches(value, t) for t in self.tags)
                self.previous = previous
                return result
            if key == "exists":
                return (scope in self.members or scope == "VAL") == (value == "yes")
            if key == "has_capitulated":
                return (scope in self.capitulated) == (value == "yes")
            if key == "is_subject":
                return (scope in self.installed or scope in self.subjects) == (value == "yes")
            if key == "is_subject_of":
                return self.subjects.get(scope) == value
            if key == "is_major":
                return (scope in self.majors) == (value == "yes")
            if key == "is_in_faction_with":
                target = self.previous if value == "PREV" else value
                return scope in self.members and target in self.members
            if key == "has_war_with":
                return scope in self.members and scope not in self.neutral and value == "VAL"
            raise AssertionError(f"Unmodelled settlement predicate: {key}")
        return all(match(entry) for entry in entries)

    def execute(self, entries, scope):
        branch_taken = False
        for entry in entries:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    branch_taken = False
                limit = next((item.value for item in value if item.key == "limit"), [])
                if not branch_taken and self.matches(limit, scope):
                    branch_taken = True
                    self.execute([item for item in value if item.key != "limit"], scope)
            elif key in self.tags or key == "ROOT":
                self.execute(value, self.root if key == "ROOT" else key)
            elif key == "set_country_flag":
                self.flags[scope].add(value)
            elif key == "clr_country_flag":
                self.flags[scope].discard(value)
            elif key == "set_global_flag":
                assert value == "skip_default_capitulation"
                self.reserved = True
            elif key in ("VAL_install_stelander_administration", "VAL_install_nodrul_administration"):
                self.installed.append(scope)
            elif key == "VAL_transfer_party_controlled_ainholm_to_frontier":
                assert "VAL_final_party_controlled_ainholm" not in self.flags["STP"]
            elif key in ("VAL_finalize_reserved_settlements", "VAL_clear_final_defeat_receipt"):
                self.execute(self.effects[key], scope)
            elif key == "log":
                pass
            else:
                raise AssertionError(f"Unmodelled settlement effect: {key}")

    def late_callback(self):
        text = ON_ACTIONS.read_text(encoding="utf-8")
        late = text.split("# BEGIN kefreyt:on_capitulation\n", 1)[1].split("# END kefreyt:on_capitulation", 1)[0]
        entries = parse_clausewitz(late)
        start = next(i for i, entry in enumerate(entries) if "VAL_final_defeat_pending" in repr(entry))
        end = next(i for i, entry in enumerate(entries) if entry.key == "VAL_queue_frontier_reconciliation")
        self.execute(entries[start:end], self.root)

    def uncapitulate(self, country):
        self.capitulated.discard(country)
        text = ON_ACTIONS.read_text(encoding="utf-8")
        hook = named_block(text, "on_uncapitulation")
        entries = parse_clausewitz(hook)[0].value
        effect = next(entry.value for entry in entries if entry.key == "effect")
        previous_root = self.root
        self.root = country
        self.execute(effect, country)
        self.root = previous_root


def named_block(text: str, name: str) -> str:
    marker = f"{name} = {{"
    start = text.index(marker)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unclosed block: {name}")


class KefreytNodrulPeaceRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EFFECTS.read_text(encoding="utf-8")
        cls.reconcile = named_block(cls.source, "VAL_final_crisis_reconcile")

    def test_late_callback_settles_both_allies_before_clearing_current_receipt(self):
        for first, last in (("STP", "NOD"), ("NOD", "STP"), ("STS", "NOD"), ("NOD", "STS")):
            with self.subTest(first=first, last=last):
                fixture = FinalSettlementFixture(first, last)
                fixture.late_callback()
                self.assertCountEqual(fixture.installed, (first, last))
                self.assertTrue(fixture.reserved)
                self.assertNotIn("VAL_final_capitulation_immediate", fixture.flags[last])

    def test_liberated_ally_blocks_settlement_after_its_receipt_expires(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.uncapitulate("STP")
        fixture.late_callback()
        self.assertEqual(fixture.installed, [])
        self.assertNotIn("VAL_final_defeat_pending", fixture.flags["STP"])
        self.assertIn("VAL_final_defeat_pending", fixture.flags["NOD"])

    def test_liberated_ally_cannot_reuse_a_stale_unexpired_receipt(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.flags["STP"].add("VAL_final_capitulation_immediate")
        fixture.uncapitulate("STP")
        fixture.late_callback()
        self.assertEqual(fixture.installed, [])
        self.assertNotIn("VAL_final_defeat_pending", fixture.flags["STP"])

    def test_recorded_defeats_survive_delayed_native_status_for_both_members(self):
        for first, last in (("STP", "NOD"), ("NOD", "STP"), ("STS", "NOD")):
            with self.subTest(first=first, last=last):
                fixture = FinalSettlementFixture(first, last)
                fixture.capitulated.clear()
                fixture.late_callback()
                self.assertCountEqual(fixture.installed, (first, last))

    def test_recorded_defeat_survives_reconciliation_while_an_ally_fights(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.capitulated.clear()
        fixture.flags["NOD"].clear()
        fixture.root = "VAL"
        fixture.execute(fixture.effects["VAL_finalize_reserved_settlements"], "VAL")
        self.assertEqual(fixture.installed, [])
        self.assertIn("VAL_final_defeat_pending", fixture.flags["STP"])

    def test_country_that_left_the_war_cannot_reuse_a_recorded_defeat(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.neutral.add("STP")
        fixture.late_callback()
        self.assertEqual(fixture.installed, ["NOD"])
        self.assertNotIn("VAL_final_defeat_pending", fixture.flags["STP"])

    def test_foreign_subject_cannot_be_taken_with_an_old_defeat_receipt(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.subjects["STP"] = "YPR"
        fixture.late_callback()
        self.assertEqual(fixture.installed, ["NOD"])
        self.assertNotIn("VAL_final_defeat_pending", fixture.flags["STP"])

    def test_native_liberation_preserves_an_already_committed_transaction(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.flags["STP"].update((
            "VAL_final_settlement_commit",
            "VAL_final_party_controlled_ainholm",
        ))
        fixture.uncapitulate("STP")
        self.assertEqual(fixture.flags["STP"], {"VAL_final_settlement_commit"})

    def test_external_peace_and_annexation_clear_only_the_affected_receipt(self):
        source = ON_ACTIONS.read_text(encoding="utf-8")
        for hook, scope in (("on_peace", "STP"), ("on_annex", "VAL")):
            with self.subTest(hook=hook):
                fixture = FinalSettlementFixture("STP", "NOD")
                section = source.split(f"# BEGIN kefreyt:{hook}\n", 1)[1]
                section = section.split(f"# END kefreyt:{hook}", 1)[0]
                entries = parse_clausewitz(section)
                if hook == "on_annex":
                    self.assertEqual(entries[0].key, "FROM")
                    entries = entries[0].value
                    scope = "STP"
                receipts = [entry for entry in entries if entry.key == "VAL_clear_final_defeat_receipt"]
                self.assertEqual(len(receipts), 1)
                fixture.execute(receipts, scope)
                self.assertNotIn("VAL_final_defeat_pending", fixture.flags["STP"])
                self.assertIn("VAL_final_defeat_pending", fixture.flags["NOD"])

    def test_unbeaten_stelander_does_not_force_an_old_save_armistice(self):
        self.assertNotIn("Save-safe repair", self.reconcile)
        self.assertNotIn("white_peace = VAL", self.reconcile)

    def test_additional_faction_ally_blocks_until_its_own_last_callback(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.members.add("YPR")
        fixture.late_callback()
        self.assertEqual(fixture.installed, [])
        fixture.capitulated.add("NOD")
        fixture.root = "YPR"
        fixture.flags["YPR"].add("VAL_coalition_capitulation_current")
        fixture.late_callback()
        self.assertCountEqual(fixture.installed, ("STP", "NOD"))

    def test_neutral_faction_ally_does_not_block(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.members.add("YPR")
        fixture.neutral.add("YPR")
        fixture.late_callback()
        self.assertCountEqual(fixture.installed, ("STP", "NOD"))

    def test_nodrul_colony_does_not_delay_settlement_until_native_conference(self):
        for first, last in (("STP", "NOD"), ("NOD", "STP")):
            for immediate in (True, False):
                with self.subTest(last=last, immediate=immediate):
                    fixture = FinalSettlementFixture(first, last)
                    fixture.members.add("AIN")
                    fixture.subjects["AIN"] = "NOD"
                    if immediate:
                        fixture.execute(fixture.effects["VAL_finalize_reserved_settlements"], "VAL")
                    else:
                        fixture.late_callback()
                    self.assertCountEqual(fixture.installed, (first, last))

    def test_independent_or_major_ainholm_still_requires_defeat(self):
        for subject, major in ((False, False), (True, True)):
            with self.subTest(subject=subject, major=major):
                fixture = FinalSettlementFixture("STP", "NOD")
                fixture.members.add("AIN")
                if subject:
                    fixture.subjects["AIN"] = "NOD"
                if major:
                    fixture.majors.add("AIN")
                fixture.late_callback()
                self.assertEqual(fixture.installed, [])

    def test_nodrul_colony_exception_does_not_ignore_liberated_stelander(self):
        fixture = FinalSettlementFixture("STP", "NOD")
        fixture.members.add("AIN")
        fixture.subjects["AIN"] = "NOD"
        fixture.uncapitulate("STP")
        fixture.late_callback()
        self.assertEqual(fixture.installed, [])

    def test_minor_colony_leaves_war_before_nodrul_autonomy_retry(self):
        install = named_block(self.source, "VAL_install_nodrul_administration")
        self.assertIn("AIN = { exists = yes is_subject_of = NOD is_major = no }", install)
        queue = install.index("VAL_queue_ainholm_colony = yes")
        self.assertLess(queue, install.index("VAL_end_administration_wars = yes"))
        self.assertLess(queue, install.index("id = val_contract.353 days = 1"))
        finish = named_block(self.source, "VAL_finish_nodrul_administration")
        self.assertIn(
            "NOT = { has_country_flag = VAL_ainholm_colony_pending is_subject_of = VAL }",
            finish,
        )

    def test_stelander_handoff_uses_native_scope_without_event_targets(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        from tools.tests.test_adiscord_val_campaign_contracts import selected_effects

        install = named_block(self.source, "VAL_install_stelander_administration")
        restore = named_block(self.source, "VAL_restore_stelander_conquered_administrations")
        self.assertNotIn("event_target:", install + restore)
        entries = block(parse_clausewitz(install), "VAL_install_stelander_administration")
        for country in ("STP", "STS"):
            with self.subTest(country=country):
                facts = {
                    (country, "tag", country): True,
                    (country, "has_cosmetic_tag", "STL_VAL_administration"): True,
                    ("VAL", "exists", "yes"): True,
                    ("VAL", "has_capitulated", "no"): True,
                    ("VAL", "is_subject", "no"): True,
                }
                calls = list(selected_effects(entries, facts, country))
                autonomy = [(scope, scalar(e.value, "target")) for scope, e in calls if e.key == "set_autonomy"]
                self.assertEqual(autonomy, [("VAL", "PREV")])
                restoration = [scope for scope, e in calls if e.key == "VAL_restore_stelander_conquered_administrations"]
                self.assertEqual(restoration, ["VAL"] if country == "STS" else [])

    def test_new_stelander_leader_role_promotes_atomically(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk

        install = block(parse_clausewitz(self.source), "VAL_install_stelander_administration")
        for character in ("STP_VAL_Andrei_Rudnev", "STS_VAL_Andrei_Rudnev"):
            with self.subTest(character=character):
                branches = [
                    e.value for e in walk(install)
                    if e.key == "if" and any(
                        child.key == "add_country_leader_role"
                        and scalar(child.value, "character") == character
                        for child in e.value
                    )
                ]
                self.assertEqual(len(branches), 1)
                role = block(branches[0], "add_country_leader_role")
                self.assertEqual(scalar(role, "promote_leader"), "yes")
                self.assertNotIn("promote_character", [e.key for e in walk(branches[0])])
                parents = [
                    e.value for e in walk(install)
                    if isinstance(e.value, list) and any(
                        child.key == "if" and child.value == branches[0]
                        for child in e.value
                    )
                ]
                self.assertEqual(len(parents), 1)
                existing_role = block(block(parents[0], "else"), "promote_character")
                self.assertEqual(scalar(existing_role, "character"), character)

    def test_missed_final_capitulation_is_recovered(self) -> None:
        self.assertIn("VAL_nod_campaign_stelander_ready = yes", self.reconcile)
        self.assertGreaterEqual(
            self.reconcile.count(
                "has_country_flag = VAL_final_war_member has_capitulated = yes"
            ),
            3,
        )
        self.assertGreaterEqual(
            self.reconcile.count("set_country_flag = VAL_final_defeat_pending"), 3
        )
        self.assertIn("VAL_finalize_reserved_settlements = yes", self.reconcile)

    def test_joint_shabrat_campaign_recovers_from_receipt_after_war_cleanup(
        self,
    ) -> None:
        self.assertIn(
            "has_country_flag = VAL_joint_nod_campaign_with_sts", self.reconcile
        )
        self.assertIn(
            "NOT = { has_country_flag = VAL_joint_nod_settlement_completed }",
            self.reconcile,
        )
        self.assertIn(
            "has_country_flag = VAL_joint_nod_campaign_target", self.reconcile
        )
        self.assertIn("has_capitulated = yes", self.reconcile)
        self.assertNotIn(
            "NOD = { exists = yes has_war_with = VAL has_war_with = STS has_capitulated = yes }",
            self.reconcile,
        )
        self.assertIn("VAL_settle_joint_nod_shabrat_victory = yes", self.reconcile)

    def test_frontier_partner_can_receive_nodrul_capitulation_credit(self) -> None:
        router = ON_ACTIONS.read_text(encoding="utf-8")
        router = router.split("# BEGIN kefreyt:on_capitulation_immediate", 1)[1]
        router = router.split("# END kefreyt:on_capitulation_immediate", 1)[0]
        compact_router = " ".join(router.split())
        self.assertIn(
            "OR = { FROM = { VAL_final_campaign_ally = yes } capital_scope = { controller = { VAL_final_campaign_ally = yes } } }",
            compact_router,
        )

        ally = named_block(
            TRIGGERS.read_text(encoding="utf-8"), "VAL_final_campaign_ally"
        )
        self.assertIn("tag = VAL", ally)
        self.assertIn("is_subject_of = VAL", ally)
        self.assertIn("tag = TFF", ally)
        self.assertIn("is_subject_of = TFF", ally)
        self.assertIn("VAL_frontier_partner_available = yes", ally)
        self.assertIn("has_country_flag = VAL_nod_frontier_agreement", ally)

        triggers = TRIGGERS.read_text(encoding="utf-8")
        available = named_block(triggers, "VAL_final_crisis_available")
        launchable = named_block(triggers, "VAL_can_launch_final_campaign")
        for block in (available, launchable):
            self.assertIn("is_subject_of = STP", block)
            self.assertIn("STP = { is_subject_of = VAL }", block)

    def test_party_victory_nested_nodrul_is_released_before_final_war(self) -> None:
        release = named_block(
            self.source, "VAL_release_party_nodrul_for_final_campaign"
        )
        self.assertIn(
            "NOD = { exists = yes has_capitulated = no is_subject_of = STP }", release
        )
        self.assertIn(
            "STP = { exists = yes has_capitulated = no is_subject_of = VAL }", release
        )
        self.assertIn("target = NOD", release)
        self.assertIn("autonomy_state = autonomy_free", release)
        self.assertIn("end_wars = no", release)

        launch = named_block(self.source, "VAL_final_crisis_launch")
        execute = named_block(self.source, "VAL_final_crisis_execute_launch")
        self.assertIn("VAL_release_party_nodrul_for_final_campaign = yes", launch)
        self.assertIn("id = val_rework.122 days = 1", launch)
        self.assertNotIn("declare_war_on = { target = STP", launch)
        self.assertIn(
            "declare_war_on = { target = NOD type = annex_everything }", execute
        )

        decision = named_block(
            DECISIONS.read_text(encoding="utf-8"), "VAL_campaign_against_nod"
        )
        self.assertIn("AND = { tag = NOD is_subject_of = STP }", decision)
        self.assertIn("VAL_release_party_nodrul_for_final_campaign = yes", decision)

        all_events = EVENTS.read_text(encoding="utf-8")
        marker = "id = val_rework.122"
        start = all_events.index(marker)
        event_start = all_events.rfind("country_event = {", 0, start)
        event = named_block(all_events[event_start:], "country_event")
        self.assertIn("VAL_final_party_nod_release_pending", event)
        self.assertIn("VAL_final_crisis_execute_launch = yes", event)

    def test_party_victory_settlement_breaks_stale_stp_overlordship(self) -> None:
        install = named_block(self.source, "VAL_install_nodrul_administration")
        self.assertIn("is_subject_of = STP", install)
        self.assertIn("STP = { is_subject_of = VAL }", install)
        self.assertIn("autonomy_state = autonomy_free", install)
        self.assertLess(
            install.index("autonomy_state = autonomy_free"),
            install.index("VAL_nodrul_administration_pending"),
        )

    def test_nodrul_administration_keeps_its_own_colour_identity(self) -> None:
        install = named_block(self.source, "VAL_install_nodrul_administration")
        finish = named_block(self.source, "VAL_finish_nodrul_administration")
        autonomy = (
            ROOT / "common/autonomous_states/ADISCORD_contract_clients.txt"
        ).read_text(encoding="utf-8")
        cosmetic = (ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8")

        self.assertIn("set_cosmetic_tag = NOD_VAL_administration", install)
        self.assertLess(
            install.index("set_cosmetic_tag = NOD_VAL_administration"),
            install.index("VAL_nodrul_administration_pending"),
        )
        self.assertIn("set_cosmetic_tag = NOD_VAL_administration", finish)
        self.assertIn("id = autonomy_VAL_contract_administration", autonomy)
        contract = named_block(autonomy, "autonomy_state")
        self.assertIn(
            "use_overlord_color = no",
            autonomy[autonomy.index("id = autonomy_VAL_contract_administration") :],
        )
        self.assertIn("NOD_VAL_administration = { color = rgb { 63 56 96 }", cosmetic)

    def test_ainholm_is_the_only_colony_in_the_new_northern_settlement(self) -> None:
        queue = named_block(self.source, "VAL_queue_ainholm_colony")
        complete = named_block(self.source, "VAL_complete_ainholm_colony")
        coalition = named_block(self.source, "VAL_settle_northern_coalition_victory")
        nodrul = named_block(self.source, "VAL_finish_nodrul_administration")
        joint = named_block(self.source, "VAL_settle_joint_nod_shabrat_victory")

        self.assertIn("tag = AIN", complete)
        self.assertIn("autonomy_state = autonomy_colony", complete)
        self.assertIn("VAL_ainholm_colony_pending", queue)
        self.assertIn("id = val_contract.355 days = 1", queue)
        self.assertIn("VAL_queue_ainholm_colony = yes", coalition)
        self.assertIn("VAL_queue_ainholm_colony = yes", nodrul)
        self.assertIn("VAL_queue_ainholm_colony = yes", joint)

        for block in (
            coalition,
            named_block(self.source, "VAL_partition_nodrul_settlement"),
        ):
            self.assertNotIn("autonomy_state = autonomy_colony", block)

        events = EVENTS.read_text(encoding="utf-8")
        self.assertIn("id = val_contract.355", events)
        self.assertIn("VAL_complete_ainholm_colony = yes", events)

    def test_northern_coalition_defensive_war_adopts_scripted_campaign(self) -> None:
        adopt = named_block(
            self.source, "VAL_adopt_northern_coalition_defensive_campaign"
        )
        self.assertIn("has_completed_focus = VAL_Northern_Settlement", adopt)
        self.assertIn(
            "NOT = { has_country_flag = VAL_northern_coalition_settlement_completed }",
            adopt,
        )
        for tag in ("YPR", "COF", "TFF"):
            self.assertGreaterEqual(adopt.count(f"{tag} = {{"), 2)
        self.assertEqual(adopt.count("has_war_with = VAL"), 3)
        self.assertEqual(
            adopt.count("set_country_flag = VAL_northern_coalition_campaign_member"), 3
        )
        self.assertEqual(adopt.count("set_major = yes"), 3)
        self.assertIn(
            "set_country_flag = VAL_northern_coalition_campaign_active", adopt
        )
        self.assertIn("VAL_call_subjects_to_wars = yes", adopt)

        lifecycle = named_block(
            VAL_ON_ACTIONS.read_text(encoding="utf-8"), "on_war_relation_added"
        )
        self.assertIn(
            "VAL_adopt_northern_coalition_defensive_campaign = yes", lifecycle
        )

    def test_northern_coalition_has_one_focus_and_one_scripted_settlement(self) -> None:
        focuses = read_focus_source(ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt", encoding="utf-8")
        triggers = TRIGGERS.read_text(encoding="utf-8")
        self.assertEqual(focuses.count("id = VAL_Break_The_Northern_Coalition"), 1)

        start = focuses.index("id = VAL_Break_The_Northern_Coalition")
        end = focuses.find("\n\tfocus = {", start)
        focus = focuses[start : end if end != -1 else len(focuses)]
        self.assertIn("prerequisite = { focus = VAL_Northern_Settlement }", focus)
        self.assertIn("VAL_can_attack_northern_coalition = yes", focus)
        self.assertIn("VAL_begin_northern_coalition_campaign = yes", focus)

        gate = named_block(triggers, "VAL_can_attack_northern_coalition")
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn(f"{tag} = {{", gate)

        start_effect = named_block(self.source, "VAL_begin_northern_coalition_campaign")
        settlement = named_block(self.source, "VAL_settle_northern_coalition_victory")
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn(f"target = {tag}", settlement)
        self.assertEqual(
            settlement.count("autonomy_state = autonomy_VAL_contract_administration"), 3
        )
        self.assertIn("target = YPR", start_effect)
        join_effect = named_block(self.source, "VAL_join_northern_coalition_war")
        self.assertIn("targeted_alliance = YPR", join_effect)

        router = ON_ACTIONS.read_text(encoding="utf-8")
        self.assertIn("VAL_northern_coalition_campaign_member", router)
        self.assertIn("VAL_northern_coalition_capitulation_reserved", router)
        self.assertIn("VAL_settle_northern_coalition_victory = yes", router)

        late_start = router.index(
            "# BEGIN kefreyt_northern_reservations:on_capitulation"
        )
        late_end = router.index(
            "# END kefreyt_northern_reservations:on_capitulation", late_start
        )
        late_router = router[late_start:late_end]
        self.assertIn(
            "VAL_northern_coalition_campaign_victory_ready = yes", late_router
        )
        self.assertIn("VAL_settle_northern_coalition_victory = yes", late_router)

        victory = named_block(triggers, "VAL_northern_coalition_campaign_victory_ready")
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn(
                f"{tag} = {{ VAL_northern_coalition_defeat_reserved = yes }}",
                victory,
            )
        immediate_start = router.index(
            "# BEGIN kefreyt_northern_reservations:on_capitulation_immediate"
        )
        immediate_end = router.index(
            "# END kefreyt_northern_reservations:on_capitulation_immediate",
            immediate_start,
        )
        immediate_router = router[immediate_start:immediate_end]
        self.assertLess(
            immediate_router.index("VAL_northern_coalition_capitulation_reserved"),
            immediate_router.index(
                "VAL_northern_coalition_campaign_victory_ready = yes"
            ),
        )
        self.assertIn("VAL_settle_northern_coalition_victory = yes", immediate_router)
        self.assertEqual(
            settlement.count(
                "clr_country_flag = VAL_northern_coalition_capitulation_reserved"
            ),
            3,
        )

    def test_nodrul_can_launch_a_direct_postwar_war_over_subject_sts(self) -> None:
        triggers = TRIGGERS.read_text(encoding="utf-8")
        gate = named_block(triggers, "VAL_nod_can_attack_sts_overlord")
        self.assertIn("has_global_flag = STP_cw_union_wars_finished", gate)
        self.assertIn("is_subject_of = VAL", gate)
        self.assertIn("NOT = { is_in_faction_with = VAL }", gate)

        launch = named_block(self.source, "VAL_nod_launch_sts_overlord_war")
        self.assertIn(
            "declare_war_on = { target = VAL type = annex_everything }", launch
        )
        self.assertIn("has_war_with = VAL", launch)
        self.assertIn("set_country_flag = VAL_nod_overlord_sts_war_active", launch)
        self.assertIn("VAL_call_subjects_to_wars = yes", launch)

        weekly = (ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("VAL_nod_can_attack_sts_overlord = yes", weekly)
        self.assertIn("VAL_nod_launch_sts_overlord_war = yes", weekly)

    def test_nod_intervention_against_val_subject_has_limited_peace_both_ways(
        self,
    ) -> None:
        router = ON_ACTIONS.read_text(encoding="utf-8")
        self.assertIn("VAL_settle_nod_overlord_sts_victory = yes", router)
        self.assertIn("VAL_settle_nod_overlord_sts_defeat = yes", router)
        self.assertIn("VAL_nod_overlord_sts_capitulation_reserved", router)
        self.assertIn(
            "STS = { exists = yes is_subject_of = VAL has_war_with = NOD }", router
        )

        victory = named_block(self.source, "VAL_settle_nod_overlord_sts_victory")
        defeat = named_block(self.source, "VAL_settle_nod_overlord_sts_defeat")
        self.assertIn("VAL_install_nodrul_administration = yes", victory)
        self.assertIn("STP_cw_abort_northern_campaign_external_defeat = yes", victory)
        self.assertIn("STP_cw_end_nod_intervention = yes", victory)
        self.assertIn("target = STS", defeat)
        self.assertIn("autonomy_state = autonomy_free", defeat)
        self.assertIn("white_peace = NOD", defeat)
        self.assertNotIn("annex_country", defeat)
        self.assertNotIn("transfer_state", defeat)

    def test_nodrul_settlement_closes_bezhaysk_war_before_capitulation(self) -> None:
        install = named_block(self.source, "VAL_install_nodrul_administration")
        settle = named_block(self.source, "VAL_settle_nodrul_bezhaysk_war")
        self.assertIn("VAL_settle_nodrul_bezhaysk_war = yes", install)
        self.assertIn("has_war_with = BJK", settle)
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_campaign_active", settle)
        self.assertNotIn("has_completed_focus = VAL_Bezhaysk_Operation", settle)
        self.assertIn("white_peace = BJK", settle)


if __name__ == "__main__":
    unittest.main()
