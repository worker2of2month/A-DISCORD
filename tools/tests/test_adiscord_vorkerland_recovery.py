from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lib.focus_sources import read_focus_source
from tools.tests.test_vorkerland_preparation import Script, TRIGGERS, parse
from tools.validators.validate_adiscord_vorkerland_recovery import (
    NATION_TARGET,
    NATION_TARGET_BIND,
    NATION_TARGET_CLEAR,
    NATION_TARGET_NAME,
    PHASE_FLAGS,
    PLAYER_PREFERENCE_FLAGS,
    ROUTE_FLAGS,
    collect_issues,
    event_block,
    event_blocks,
    named_block,
    named_blocks,
    validate_bounded_retry,
    validate_campaign_state,
    validate_new_save_materialization,
    validate_premature_wrk_recovery,
    validate_retired_legacy_events,
    validate_phase_controller,
    validate_reunification_formation,
    validate_wkr_semantics,
)


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def issue_report(issues: list[str]) -> str:
    return "\n" + "\n".join(f"- {issue}" for issue in issues)


EFFECTS_FILE = "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
TRIGGERS_FILE = "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
EVENTS_FILE = "events/ADISCORD_vorkerland_events.txt"
ON_ACTIONS_FILE = "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
BINDING_ON_ACTIONS_FILE = "common/on_actions/00_ADISCORD_on_actions.txt"
WRK_HISTORY_FILE = "history/countries/WRK - WorkerLand.txt"
CLAIMANTS = ("WKR", "VAD", "TVA")


def serve_mutations(*mutations):
    """Serve gameplay files to the validator with one block rewritten in each.

    Every mutation is `(relative, locate, replacements)`. `locate` returns the
    block inside the file's source; each replacement must hit that block, so
    a stale anchor fails instead of testing nothing.
    """
    served = {}
    for relative, locate, replacements in mutations:
        target = (ROOT / relative).resolve()
        original = read_focus_source(target)
        block = locate(original)
        changed = block
        for old, new in replacements:
            if not block or old not in changed:
                raise AssertionError(
                    f"mutation anchor is missing in {relative}: {old!r}"
                )
            changed = changed.replace(old, new, 1)
        served[target] = original.replace(block, changed, 1)

    def reader(path, *args, **kwargs):
        mutated = served.get(Path(path).resolve())
        if mutated is not None:
            return mutated
        return read_focus_source(path, *args, **kwargs)

    return patch(
        "tools.validators.validate_adiscord_vorkerland_recovery.read_focus_source",
        side_effect=reader,
    )


def serve_mutation(relative: str, locate, replacements):
    """Serve one gameplay file to the validator with one block rewritten."""
    return serve_mutations((relative, locate, replacements))


def whole_file(source: str) -> str:
    return source


def effect(name: str):
    return lambda source: named_block(source, name)


def event(event_id: str):
    return lambda source: event_block(source, event_id)


class RecoveryValidatorHelperTests(unittest.TestCase):
    def test_structural_helpers_follow_balanced_blocks(self) -> None:
        source = """
outer = {
    inner = { token = yes }
}
country_event = {
    id = ADISCORD_vorkerland_phase.5
    immediate = { token = yes }
}
"""
        self.assertIn("inner = { token = yes }", named_block(source, "outer"))
        self.assertIn(
            "immediate = { token = yes }",
            event_block(source, "ADISCORD_vorkerland_phase.5"),
        )

    def test_multiline_wrk_scope_exposes_the_nested_prewar_setter(self) -> None:
        startup = """
on_startup = {
    effect = {
        if = {
            limit = { WRK = { exists = yes } }
            WRK = {
                ADISCORD_vorkerland_set_phase_prewar = yes
                country_event = { id = ADISCORD_vorkerland_phase.1 }
            }
        }
    }
}
"""
        wrk_scopes = named_blocks(startup, "WRK")
        self.assertTrue(
            any(
                "ADISCORD_vorkerland_set_phase_prewar = yes" in scope
                for scope in wrk_scopes
            )
        )


class WkrTagSemanticTests(unittest.TestCase):
    def test_wkr_tag_country_flags_and_names(self) -> None:
        issues = validate_wkr_semantics()
        self.assertEqual(issues, [], issue_report(issues))


class NewSaveMaterializationTests(unittest.TestCase):
    def test_atomic_split_handoff_annex_and_strict_postconditions(self) -> None:
        issues = validate_new_save_materialization()
        self.assertEqual(issues, [], issue_report(issues))

    def test_startup_choice_selects_control_then_invokes_atomic_collapse(self) -> None:
        phase_events = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'phase_events'
        )
        choice = event_block(phase_events, "ADISCORD_vorkerland_phase.1")
        self.assertIn("fire_only_once = yes", choice)
        choice_trigger = named_block(choice, "trigger")
        self.assertIn(f"tag = {NATION_TARGET}", choice_trigger)
        self.assertNotIn("tag = WRK", choice_trigger)
        self.assertIn("ADISCORD_vorkerland_collapse_not_started = yes", choice_trigger)

        options = named_blocks(choice, "option")
        self.assertEqual(len(options), 3)
        collapse_dispatch = "country_event = { id = ADISCORD_vorkerland_collapse.1 }"
        expected_flags = (*PLAYER_PREFERENCE_FLAGS, PLAYER_PREFERENCE_FLAGS[1])
        for option, selected_flag in zip(options, expected_flags):
            for preference_flag in PLAYER_PREFERENCE_FLAGS:
                self.assertEqual(
                    option.count(f"clr_global_flag = {preference_flag}"),
                    1,
                    preference_flag,
                )
            self.assertEqual(option.count(f"set_global_flag = {selected_flag}"), 1)
            self.assertEqual(option.count(collapse_dispatch), 1)
        for option in options:
            self.assertNotIn("ADISCORD_vorkerland_prewar_compact_ratified", option)

        startup = named_block(
            read_country_on_actions(
                "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
                'vorkerland_collapse',
            ),
            "on_startup",
        )
        delayed_choices = [
            block
            for block in named_blocks(startup, "country_event")
            if "id = ADISCORD_vorkerland_phase.1" in block
        ]
        self.assertEqual(len(delayed_choices), 1)
        self.assertIn("days = 350", delayed_choices[0])
        self.assertIn("random_days = 30", delayed_choices[0])
        direct_collapses = [
            block
            for block in named_blocks(startup, "country_event")
            if re.search(r"\bid\s*=\s*ADISCORD_vorkerland_collapse\.1\b", block)
        ]
        self.assertEqual(direct_collapses, [])

    def test_fresh_campaign_binds_the_nation_target_to_wrk_before_any_reader(
        self,
    ) -> None:
        # WRK's own history binds the target: history is applied before any
        # startup hook, and it is the only place a start may bind unguarded.
        history = read(WRK_HISTORY_FILE)
        self.assertEqual(history.count(NATION_TARGET_BIND), 1)
        binding_position = history.index(NATION_TARGET_BIND)
        self.assertEqual(history[:binding_position].count("{"), 0)
        self.assertNotIn(NATION_TARGET, history[:binding_position])
        self.assertNotIn(NATION_TARGET_CLEAR, history)

        startup = named_block(read(BINDING_ON_ACTIONS_FILE), "on_startup")
        self.assertEqual(startup.count(NATION_TARGET_BIND), 1)
        self.assertNotIn(NATION_TARGET_CLEAR, startup)
        binder = next(
            block for block in named_blocks(startup, "if") if NATION_TARGET_BIND in block
        )
        self.assertEqual(
            " ".join(binder.split()),
            f"if = {{ limit = {{ NOT = {{ has_event_target = {NATION_TARGET_NAME} }} }} "
            f"WRK = {{ {NATION_TARGET_BIND} }} }}",
        )

        # The history statement runs in WRK scope. The startup hook binds WRK
        # only when no target exists and leaves a claimant's target alone.
        script = Script()
        script.event_targets.clear()
        script.run(parse(NATION_TARGET_BIND), "WRK")
        self.assertEqual(script.event_targets[NATION_TARGET_NAME], "WRK")
        script.event_targets.clear()
        script.run(parse(binder), "IVN")
        self.assertEqual(script.event_targets[NATION_TARGET_NAME], "WRK")
        script.event_targets[NATION_TARGET_NAME] = "VAD"
        script.run(parse(binder), "IVN")
        self.assertEqual(script.event_targets[NATION_TARGET_NAME], "VAD")

        collapse_startup = named_block(
            read_country_on_actions(ON_ACTIONS_FILE, 'vorkerland_collapse'),
            "on_startup",
        )
        self.assertNotIn(NATION_TARGET_BIND, collapse_startup)
        choice_owners = [
            scope
            for scope in (
                *named_blocks(collapse_startup, "WRK"),
                *named_blocks(collapse_startup, NATION_TARGET),
            )
            if "id = ADISCORD_vorkerland_phase.1" in scope
        ]
        self.assertEqual(len(choice_owners), 1)

        guard = f"limit = {{ NOT = {{ has_event_target = {NATION_TARGET_NAME} }} }}"
        unbound_history = (WRK_HISTORY_FILE, whole_file, [(NATION_TARGET_BIND, "")])
        unbound_startup = (
            BINDING_ON_ACTIONS_FILE,
            effect("on_startup"),
            [(NATION_TARGET_BIND, "")],
        )
        nested_history = (
            WRK_HISTORY_FILE,
            whole_file,
            [
                (NATION_TARGET_BIND, ""),
                ("oob = ", f"NAM = {{ {NATION_TARGET_BIND} }} oob = "),
            ],
        )
        unguarded_startup = (
            BINDING_ON_ACTIONS_FILE,
            effect("on_startup"),
            [(guard, "limit = { always = yes }")],
        )
        late_startup = (
            BINDING_ON_ACTIONS_FILE,
            effect("on_startup"),
            [("effect = {", "effect = { set_global_flag = ADISCORD_test_marker")],
        )
        literal_choice = (
            EVENTS_FILE,
            event("ADISCORD_vorkerland_phase.1"),
            [(f"tag = {NATION_TARGET}", "tag = WRK")],
        )
        cases = (
            (
                (unbound_history, unbound_startup),
                "a fresh campaign must bind the nation target to WRK",
            ),
            (
                (nested_history,),
                "WRK history must bind the nation target once, at its top level, "
                "before reading it",
            ),
            (
                (unguarded_startup,),
                "startup may bind the nation target to WRK once, only while it is unbound",
            ),
            (
                (late_startup,),
                "the nation target binding must be the first startup effect",
            ),
            (
                (literal_choice,),
                "phase event .1 must be scoped exactly to the pre-collapse nation target",
            ),
        )
        for mutations, expected in cases:
            with self.subTest(expected=expected), serve_mutations(*mutations):
                issues = validate_new_save_materialization()
                self.assertIn(expected, issues, issue_report(issues))

        # Either binding alone starts the campaign with the target in place.
        for mutation in (unbound_history, unbound_startup):
            with self.subTest(removed=mutation[0]), serve_mutations(mutation):
                issues = validate_new_save_materialization()
                self.assertNotIn(
                    "a fresh campaign must bind the nation target to WRK", issues
                )

    def test_prewar_compact_preserves_local_preparation_and_free_claimant_choice(
        self,
    ) -> None:
        phase_effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        resolver = named_block(
            phase_effects, "ADISCORD_vorkerland_resolve_prewar_compact"
        )
        for token in (
            f"{NATION_TARGET} = {{ has_country_flag = ADISCORD_vorkerland_wrk_compact_committed }}",
            "EYR = {",
            "EGC = {",
            "RIV = {",
            "YOR = {",
            "set_global_flag = ADISCORD_vorkerland_prewar_compact_ratified",
        ):
            self.assertEqual(resolver.count(token), 1)
        self.assertNotIn("country_event", resolver)

        collapse = event_block(
            source_section(
                read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events'
            ),
            "ADISCORD_vorkerland_collapse.1",
        )
        immediate = named_block(collapse, "immediate")
        self.assertEqual(
            immediate.count(
                "has_global_flag = ADISCORD_vorkerland_prewar_compact_ratified"
            ),
            0,
        )
        self.assertEqual(
            immediate.count("ADISCORD_vorkerland_prep_resolve_fate = yes"),
            1,
        )
        self.assertNotIn("ADISCORD_vorkerland_form_joint_government = yes", immediate)

    def test_human_handoff_is_exact_ai_safe_and_clears_preferences_before_annex(
        self,
    ) -> None:
        collapse_events = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events'
        )
        collapse = event_block(collapse_events, "ADISCORD_vorkerland_collapse.1")
        immediate = named_block(collapse, "immediate")
        handoffs = [
            block
            for block in named_blocks(immediate, "if")
            if "limit = { is_ai = no }" in block and "change_tag_from = WRK" in block
        ]
        self.assertEqual(len(handoffs), 1)
        handoff = handoffs[0]
        for claimant in ("WKR", "VAD", "TVA"):
            self.assertEqual(
                handoff.count(f"{claimant} = {{ change_tag_from = WRK }}"), 1
            )
        self.assertEqual(immediate.count("change_tag_from = WRK"), 3)

        worker_branches = [
            block
            for block in named_blocks(handoff, "if")
            if "ADISCORD_vorkerland_preference_worker" in named_block(block, "limit")
            and "WKR = { change_tag_from = WRK }" in block
        ]
        self.assertEqual(len(worker_branches), 1)
        worker_limit = named_block(worker_branches[0], "limit")
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_preference_worker", worker_limit
        )
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            self.assertIn(
                f"NOT = {{ has_global_flag = {preference_flag} }}", worker_limit
            )

        handoff_end = immediate.find(handoff) + len(handoff)
        annex_position = immediate.find("annex_country = {", handoff_end)
        self.assertGreater(annex_position, handoff_end)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            clear_position = immediate.find(f"clr_global_flag = {preference_flag}")
            self.assertGreater(clear_position, handoff_end)
            self.assertLess(clear_position, annex_position)

        fate = named_block(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "ADISCORD_vorkerland_prep_resolve_fate")
        self.assertEqual(immediate.count("ADISCORD_vorkerland_prep_resolve_fate = yes"), 1)
        fate_rolls = [
            block
            for block in named_blocks(fate, "random_list")
            if "ADISCORD_vorkerland_worker_safe_with_loyalists" in block
        ]
        self.assertEqual(len(fate_rolls), 1)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            self.assertNotIn(preference_flag, fate)

    def test_wars_wait_for_structure_and_a_completed_identity_assertion(self) -> None:
        collapse_events = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events'
        )
        outbreak = event_block(collapse_events, "ADISCORD_vorkerland_collapse.2")
        outbreak_trigger = named_block(outbreak, "trigger")
        for token in (
            "has_global_flag = ADISCORD_vorkerland_collapse_materialized_verified",
            "ADISCORD_vorkerland_collapse_materialized = yes",
            "has_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2",
        ):
            self.assertIn(token, outbreak_trigger)

        collapse = event_block(collapse_events, "ADISCORD_vorkerland_collapse.1")
        immediate = named_block(collapse, "immediate")
        self.assertNotIn(
            "country_event = { id = ADISCORD_vorkerland_collapse.2 days = 1 }",
            immediate,
        )

        phase_effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        verifier = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )
        self.assertEqual(
            verifier.count(
                "country_event = { id = ADISCORD_vorkerland_collapse.2 days = 1 }"
            ),
            1,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            outbreak_trigger,
        )

    def test_bounded_materialization_repair_is_complete_and_war_safe(self) -> None:
        phase_effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        repair = named_block(
            phase_effects, "ADISCORD_vorkerland_repair_collapse_materialization"
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started }",
            repair,
        )
        for tag, states in {
            "WKR": (32, 33, 40, 200, 201),
            "VAD": (75, 106, 107, 121),
            "TVA": (36, 37, 38, 39, 324),
        }.items():
            for state in states:
                self.assertRegex(repair, rf"\btransfer_state\s*=\s*{state}\b")
                self.assertIn(
                    f"{state} = {{ set_state_controller_to = {tag} }}", repair
                )
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_reset_temporary_claimant_cores = yes"),
            1,
        )
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_ensure_claimant_home_cores = yes"),
            1,
        )
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_repair_claimant_identities = yes"),
            1,
        )

        verifier = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )
        self.assertEqual(
            verifier.count("ADISCORD_vorkerland_repair_collapse_materialization = yes"),
            2,
        )
        self.assertEqual(
            verifier.count(
                "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
            ),
            2,
        )

    def test_identity_cache_is_a_separate_postcondition(self) -> None:
        triggers = source_section(
            read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"),
            'phase_triggers',
        )
        structural = named_block(triggers, "ADISCORD_vorkerland_collapse_materialized")
        identities = named_block(
            triggers, "ADISCORD_vorkerland_claimant_identities_materialized"
        )
        self.assertNotIn("has_country_leader", structural)
        for token in (
            "character = WRK_Nikita_Worcker",
            "character = WRK_Anton_Bagley",
            "character = WRK_Vlad_Petrichev",
            "character = WRK_VAD_Joint_Council",
            "character = TVA_Dorian_Worx",
            "has_government = pragmatism",
            "has_country_leader_ideology = neo_vorkerism",
            "has_government = utilitarism",
            "has_government = technocracy",
        ):
            self.assertIn(token, identities)

        effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        verifier = named_block(
            effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2",
            verifier,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            verifier,
        )

    def test_identity_cache_has_bounded_non_blocking_repair(self) -> None:
        effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        events = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'phase_events'
        )
        identity_event = event_block(events, "ADISCORD_vorkerland_phase.14")
        for token in (
            "ADISCORD_vorkerland_repair_claimant_identities = yes",
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            "set_global_flag = ADISCORD_vorkerland_claimant_identities_verified_v2",
            "set_global_flag = ADISCORD_vorkerland_claimant_identity_retry_v2",
            "set_global_flag = ADISCORD_vorkerland_claimant_identity_degraded_v2",
            "country_event = { id = ADISCORD_vorkerland_phase.14 days = 2 }",
        ):
            self.assertIn(token, identity_event)
        self.assertNotIn(
            "ADISCORD_vorkerland_collapse_materialization_failed", identity_event
        )

        identity_repair = named_block(
            effects, "ADISCORD_vorkerland_repair_claimant_identities"
        )
        self.assertEqual(
            identity_repair.count(
                "set_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2"
            ),
            1,
        )
        certificate = [
            block
            for block in named_blocks(identity_repair, "if")
            if "set_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2"
            in block
        ]
        self.assertEqual(len(certificate), 1)
        certificate_limit = named_block(certificate[0], "limit")
        for token in (
            "tag = WKR",
            "country_exists = WKR",
            "country_exists = VAD",
            "country_exists = TVA",
        ):
            self.assertIn(token, certificate_limit)

    def test_nikita_uses_an_explicit_transferred_country_leader_role(self) -> None:
        collapse_effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'collapse_effects',
        )
        helper = named_block(
            collapse_effects, "ADISCORD_vorkerland_promote_nikita_worcker"
        )
        for token in (
            "add_country_leader_role = {",
            "character = WRK_Nikita_Worcker",
            "promote_leader = yes",
            "ideology = neo_vorkerism",
            "set_country_flag = ADISCORD_vorkerland_nikita_wkr_role_added_v2",
        ):
            self.assertIn(token, helper)

    def test_choice_localisation_explains_control_only_and_names_vlad_and_armi(
        self,
    ) -> None:
        english = source_section(
            read("localisation/english/ADISCORD_vorkerland_l_english.yml"),
            'recovery_l_english',
        )
        russian_path = ROOT / "localisation/russian/ADISCORD_vorkerland_l_russian.yml"
        russian = russian_path.read_text(encoding="utf-8-sig")
        for fragment in (
            "country controlled by the player",
            "Worcker's fate",
            "Vlad and Armi",
        ):
            self.assertIn(fragment, english)
        for fragment in (
            "только страну под управлением игрока",
            "судьба Уоркера",
            "Влада и Арми",
        ):
            self.assertIn(fragment, russian)
        self.assertTrue(russian_path.read_bytes().startswith(b"\xef\xbb\xbf"))


class PhaseControllerTests(unittest.TestCase):
    def test_exact_seven_phase_and_wartime_claimant_contract(self) -> None:
        self.assertEqual(len(PHASE_FLAGS), 7)
        self.assertNotIn(
            "ADISCORD_vorkerland_phase_worx_client_administration", PHASE_FLAGS
        )
        self.assertNotIn("ADISCORD_vorkerland_phase_worx_fragmentation", PHASE_FLAGS)
        issues = validate_phase_controller()
        self.assertEqual(issues, [], issue_report(issues))

    def test_phase_controller_reaches_vorkerland_through_the_nation_target(self) -> None:
        refresh_scope = f"{NATION_TARGET} = {{ focus_unlock = yes"
        preparation = "ADISCORD_vorkerland_begin_central_preparation = {"
        cases = (
            (
                effect("ADISCORD_vorkerland_refresh_focus_lifecycle"),
                [(refresh_scope, "WRK = { focus_unlock = yes")],
                (
                    "lifecycle focus refresh must dirty the nation target focus layout",
                    "lifecycle focus refresh must reach Vorkerland through the nation target",
                ),
            ),
            (
                effect("ADISCORD_vorkerland_refresh_focus_lifecycle"),
                [(f"limit = {{ {NATION_TARGET} = {{ exists = yes }} }}", "limit = { always = yes }")],
                ("lifecycle focus refresh must guard the nation target scope by existence",),
            ),
            (
                effect("ADISCORD_vorkerland_finalize_unified_territory"),
                [("ADISCORD_vorkerland_inherit_retired_cores = yes", "")],
                (
                    "ADISCORD_vorkerland_inherit_retired_cores must be called once, by "
                    "the unification finalizer",
                ),
            ),
            (
                effect("ADISCORD_vorkerland_begin_central_preparation"),
                [(preparation, f"{preparation}\n\t{NATION_TARGET} = {{ add_stability = 0.01 }}")],
                (
                    "active-war effect ADISCORD_vorkerland_begin_central_preparation "
                    "still scopes the dormant WRK tag",
                ),
            ),
        )
        for locate, replacements, expected in cases:
            with self.subTest(expected=expected[0]), serve_mutation(
                EFFECTS_FILE, locate, replacements
            ):
                issues = validate_phase_controller()
                for diagnostic in expected:
                    self.assertIn(diagnostic, issues, issue_report(issues))

    def test_phase_event_file_owns_hidden_wave_verifiers_in_exact_id_set(self) -> None:
        events = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'phase_events'
        )
        actual_ids = [event_id for event_id, _ in event_blocks(events)]
        expected_ids = {
            *(f"ADISCORD_vorkerland_phase.{number}" for number in range(1, 10)),
            "ADISCORD_vorkerland_phase.14",
        }
        self.assertEqual(set(actual_ids), expected_ids)
        self.assertEqual(len(actual_ids), len(expected_ids))

        for event_number, callback in (
            (8, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch = yes"),
            (9, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry = yes"),
        ):
            verifier = event_block(events, f"ADISCORD_vorkerland_phase.{event_number}")
            self.assertEqual(verifier.count("hidden = yes"), 1)
            self.assertEqual(verifier.count("is_triggered_only = yes"), 1)
            self.assertEqual(named_block(verifier, "immediate").count(callback), 1)

    def test_startup_has_no_old_materialization_bridges(self) -> None:
        startup = named_block(
            read_country_on_actions(
                "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
                'vorkerland_collapse',
            ),
            "on_startup",
        )
        for token in (
            "ADISCORD_vorkerland_materialization_bridge_v1_scheduled",
            "ADISCORD_vorkerland_materialization_bridge_v2_scheduled",
            "ADISCORD_vorkerland_materialization_prewar_failed_bridge_v1_scheduled",
            "ADISCORD_vorkerland_materialized_outbreak_bridge_v1_scheduled",
            "load_focus_tree = { tree = ADISCORD_vorkerland_wkr_focus",
            "load_focus_tree = { tree = ADISCORD_vorkerland_vad_focus",
            "load_focus_tree = { tree = ADISCORD_vorkerland_tva_focus",
        ):
            self.assertNotIn(token, startup)

    def test_startup_does_not_requeue_failed_or_dropped_materialization(self) -> None:
        startup = named_block(
            read_country_on_actions(
                "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
                'vorkerland_collapse',
            ),
            "on_startup",
        )
        for token in (
            "ADISCORD_vorkerland_phase.2",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_failed",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_retry",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_final_retry",
            "clr_global_flag = ADISCORD_vorkerland_collapse_war_outbreak_scheduled",
        ):
            self.assertNotIn(token, startup)

    def test_materialization_verifier_cannot_run_after_wars_start(self) -> None:
        triggers = source_section(
            read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"),
            'phase_triggers',
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_collapse_materialized_for_active_war_recovery",
            triggers,
        )
        phase_two = event_block(
            source_section(
                read("events/ADISCORD_vorkerland_events.txt"), 'phase_events'
            ),
            "ADISCORD_vorkerland_phase.2",
        )
        phase_two_trigger = named_block(phase_two, "trigger")
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started }",
            phase_two_trigger,
        )


class BoundedRetryTests(unittest.TestCase):
    def test_three_required_edges_launch_together_and_are_postcondition_driven(
        self,
    ) -> None:
        issues = validate_bounded_retry()
        self.assertEqual(issues, [], issue_report(issues))

    def test_terminal_regional_failures_share_one_degraded_path(self) -> None:
        effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        call = "ADISCORD_vorkerland_degrade_regional_launch = yes"
        self.assertEqual(effects.count(call), 2)
        for owner in (
            "ADISCORD_vorkerland_verify_regional_war_launch",
            "ADISCORD_vorkerland_verify_regional_consolidation",
        ):
            self.assertEqual(named_block(effects, owner).count(call), 1, owner)

        degrade = named_block(effects, "ADISCORD_vorkerland_degrade_regional_launch")
        for flag in (
            "ADISCORD_vorkerland_regional_war_launch_final_retry",
            "ADISCORD_vorkerland_regional_war_launch_scheduled",
        ):
            self.assertEqual(degrade.count(f"clr_global_flag = {flag}"), 1)
        for flag in (
            "ADISCORD_vorkerland_regional_war_launch_failed",
            "ADISCORD_vorkerland_regional_war_launch_degraded",
        ):
            self.assertEqual(degrade.count(f"set_global_flag = {flag}"), 1)
        self.assertEqual(
            degrade.count(
                "WKR = { country_event = { id = ADISCORD_vorkerland_phase.3 days = 1 } }"
            ),
            1,
        )

        verify = named_block(
            effects, "ADISCORD_vorkerland_verify_regional_consolidation"
        )
        degraded_branch = named_blocks(verify, "if")[0]
        degraded_limit = named_block(degraded_branch, "limit")
        for guard in (
            "has_global_flag = ADISCORD_vorkerland_regional_war_launch_failed",
            "has_global_flag = ADISCORD_vorkerland_phase_regional_consolidation",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
        ):
            self.assertIn(guard, degraded_limit)
        for effect in (
            "clr_global_flag = ADISCORD_vorkerland_regional_war_launch_failed",
            "set_global_flag = ADISCORD_vorkerland_northern_wars_began",
            "ADISCORD_vorkerland_schedule_northern_escalation = yes",
            "ADISCORD_vorkerland_begin_central_preparation = yes",
        ):
            self.assertIn(effect, degraded_branch)
        self.assertIn(
            "ADISCORD_vorkerland_regional_consolidation_complete = yes",
            named_blocks(verify, "else_if")[0],
        )


class ReunificationFormationTests(unittest.TestCase):
    def test_winner_unifies_under_its_own_tag_after_loser_subject_release(self) -> None:
        issues = validate_reunification_formation()
        self.assertEqual(issues, [], issue_report(issues))

    def test_phase_six_unifies_in_the_scope_of_each_surviving_claimant(self) -> None:
        phase_six = event_block(
            source_section(read(EVENTS_FILE), 'phase_events'),
            "ADISCORD_vorkerland_phase.6",
        )
        self.assertEqual(named_blocks(phase_six, "WRK"), [])
        self.assertNotIn(NATION_TARGET, phase_six)
        for winner in CLAIMANTS:
            with self.subTest(winner=winner):
                call = f"ADISCORD_vorkerland_unify_under_{winner.lower()} = yes"
                callers = [
                    " ".join(scope.split())
                    for scope in named_blocks(phase_six, winner)
                    if call in scope
                ]
                self.assertEqual(callers, [f"{winner} = {{ {call} }}"])
                self.assertEqual(phase_six.count(call), 1)

    def test_unification_rebinds_the_nation_target_and_keeps_the_winner(self) -> None:
        effects = source_section(read(EFFECTS_FILE), 'phase_effects')
        for winner in CLAIMANTS:
            losers = [tag for tag in CLAIMANTS if tag != winner]
            unify = named_block(
                effects, f"ADISCORD_vorkerland_unify_under_{winner.lower()}"
            )
            settle = named_block(
                effects,
                f"ADISCORD_vorkerland_settle_unification_under_{winner.lower()}",
            )
            with self.subTest(winner=winner):
                statements = [
                    line.strip()
                    for line in unify.splitlines()[1:]
                    if line.strip() and not line.strip().startswith("#")
                ]
                self.assertEqual(
                    statements[:2], [NATION_TARGET_CLEAR, NATION_TARGET_BIND]
                )
                self.assertEqual(
                    statements[-2:],
                    ["country_event = { id = ADISCORD_vorkerland_phase.7 hours = 1 }", "}"],
                )
                for removed in (
                    "change_tag_from",
                    "annex_country",
                    "inherit_technology",
                    "ADISCORD_copy_development_from_prev",
                    "set_nationality",
                    "ADISCORD_vorkerland_transfer_military_staff_to_wrk",
                ):
                    self.assertNotIn(removed, unify)
                self.assertIn("transfer_state = 32", unify)
                self.assertIn(f"32 = {{ set_state_controller_to = {winner} }}", unify)
                focus_tree = named_block(unify, "load_focus_tree")
                self.assertIn("keep_completed = yes", focus_tree)
                self.assertIn("copy_completed_from = WRK", focus_tree)
                self.assertEqual(
                    unify.count("ADISCORD_vorkerland_adopt_retired_roster = yes"), 1
                )

                self.assertNotIn("change_tag_from", settle)
                self.assertNotIn(f"target = {winner}", settle)
                for loser in losers:
                    self.assertEqual(
                        settle.count(
                            f"annex_country = {{ target = {loser} transfer_troops = yes }}"
                        ),
                        1,
                    )
                for absorb in ("wtd", "egc", "treaty_districts"):
                    self.assertEqual(
                        settle.count(
                            f"ADISCORD_vorkerland_absorb_{absorb}_after_reunification = yes"
                        ),
                        1,
                    )

    def test_reunification_postcondition_follows_the_nation_target(self) -> None:
        postcondition = TRIGGERS["ADISCORD_vorkerland_reunification_verified"]

        def unified(winner: str, route: str) -> Script:
            script = Script()
            script.event_targets[NATION_TARGET_NAME] = winner
            for tag in (*CLAIMANTS, "WRK", "WTD", "EGC", "RIV", "YOR"):
                script.scopes[tag].exists = tag == winner
            script.scopes["32"].owner = winner
            script.scopes["32"].controller = winner
            script.scopes[winner].flags.add(route)
            return script

        for winner, route in zip(CLAIMANTS, ROUTE_FLAGS):
            with self.subTest(winner=winner):
                self.assertTrue(unified(winner, route).conditions(postcondition, winner))

                unbound = unified(winner, route)
                unbound.event_targets[NATION_TARGET_NAME] = "WRK"
                self.assertFalse(unbound.conditions(postcondition, winner))

                rival = next(tag for tag in CLAIMANTS if tag != winner)
                contested = unified(winner, route)
                contested.scopes[rival].exists = True
                self.assertFalse(contested.conditions(postcondition, winner))

                subject = unified(winner, route)
                subject.scopes[winner].subject = "IVN"
                self.assertFalse(subject.conditions(postcondition, winner))

                occupied = unified(winner, route)
                occupied.scopes["32"].controller = rival
                self.assertFalse(occupied.conditions(postcondition, winner))

                routeless = unified(winner, route)
                routeless.scopes[winner].flags.clear()
                self.assertFalse(routeless.conditions(postcondition, winner))

                for administration in ("WTD", "EGC", "RIV", "YOR"):
                    lingering = unified(winner, route)
                    lingering.scopes[administration].exists = True
                    self.assertFalse(
                        lingering.conditions(postcondition, winner), administration
                    )

        # A re-created WRK cannot satisfy the postcondition even with the capital.
        restored = unified("WRK", ROUTE_FLAGS[0])
        self.assertFalse(restored.conditions(postcondition, "WRK"))

    def test_validator_rejects_a_handoff_to_another_tag(self) -> None:
        nation_gate = f"WKR = {{ OR = {{ exists = no tag = {NATION_TARGET} }} }}"
        claimant_cores = "ADISCORD_vorkerland_inherit_integrated_claimant_cores = yes"
        retired_cores = "ADISCORD_vorkerland_inherit_retired_cores = yes"
        queue = "country_event = { id = ADISCORD_vorkerland_phase.7 hours = 1 }"
        cases = (
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_unify_under_wkr"),
                [(queue, f"{queue}\n\tchange_tag_from = WKR")],
                (
                    "ADISCORD_vorkerland_unify_under_wkr must keep WKR on its own tag, "
                    "found change_tag_from",
                    "ADISCORD_vorkerland_unify_under_wkr must end by queueing the "
                    "phase.7 settlement",
                ),
            ),
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_unify_under_tva"),
                [
                    (f"\t{NATION_TARGET_BIND}\n", ""),
                    ("transfer_state = 32", f"transfer_state = 32\n\t{NATION_TARGET_BIND}"),
                ],
                (
                    "ADISCORD_vorkerland_unify_under_tva must open by clearing the "
                    "nation target and rebinding it to TVA",
                ),
            ),
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_unify_under_vad"),
                [("32 = { set_state_controller_to = VAD }", "32 = { set_state_controller_to = WRK }")],
                (
                    "ADISCORD_vorkerland_unify_under_vad must take state 32 and then "
                    "hand its control to VAD",
                ),
            ),
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_settle_unification_under_vad"),
                [
                    (
                        "ADISCORD_vorkerland_absorb_wtd_after_reunification = yes",
                        "annex_country = { target = VAD transfer_troops = yes }\n"
                        "\tADISCORD_vorkerland_absorb_wtd_after_reunification = yes",
                    )
                ],
                (
                    "ADISCORD_vorkerland_settle_unification_under_vad must annex only "
                    "the defeated claimants ['WKR', 'TVA'], found ['TVA', 'VAD', 'WKR']",
                ),
            ),
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_finalize_unified_territory"),
                [
                    (claimant_cores, "PLACEHOLDER = yes"),
                    (retired_cores, claimant_cores),
                    ("PLACEHOLDER = yes", retired_cores),
                ],
                (
                    "formation finalizer must settle claimant cores, then inherit the "
                    "retired WRK cores",
                ),
            ),
            (
                EFFECTS_FILE,
                effect("ADISCORD_vorkerland_adopt_retired_roster"),
                [(f"target_country = {NATION_TARGET}", "target_country = WRK")],
                (
                    "ADISCORD_vorkerland_adopt_retired_roster must move every WRK "
                    "character to the nation target",
                ),
            ),
            (
                TRIGGERS_FILE,
                effect("ADISCORD_vorkerland_reunification_verified"),
                [(nation_gate, "NOT = { country_exists = WKR }")],
                (
                    "reunification postcondition must let WKR survive only as the "
                    "nation target",
                    "reunification postcondition must not test WRK or a claimant by "
                    "literal existence",
                ),
            ),
            (
                TRIGGERS_FILE,
                effect("ADISCORD_vorkerland_reunification_verified"),
                [("ADISCORD_vorkerland_is_main_claimant = yes", "")],
                (
                    "reunification postcondition is missing nation-target guard "
                    "ADISCORD_vorkerland_is_main_claimant = yes",
                ),
            ),
            (
                EVENTS_FILE,
                event("ADISCORD_vorkerland_phase.6"),
                [
                    (
                        "VAD = {\n\t\t\t\tADISCORD_vorkerland_unify_under_vad = yes",
                        "WRK = {\n\t\t\t\tADISCORD_vorkerland_unify_under_vad = yes",
                    )
                ],
                (
                    "formation event must not scope WRK or the nation target a claimant "
                    "has yet to take",
                    "formation event must run only ADISCORD_vorkerland_unify_under_vad "
                    "= yes in the VAD scope",
                ),
            ),
            (
                EVENTS_FILE,
                event("ADISCORD_vorkerland_phase.7"),
                [(f"tag = {NATION_TARGET}", "tag = WRK")],
                ("phase event .7 must fire only for the nation target",),
            ),
        )
        for relative, locate, replacements, expected in cases:
            with self.subTest(expected=expected[0]), serve_mutation(
                relative, locate, replacements
            ):
                issues = validate_reunification_formation()
                for diagnostic in expected:
                    self.assertIn(diagnostic, issues, issue_report(issues))


class PrematureWrkRecoveryTests(unittest.TestCase):
    def test_release_guards_and_package_routing_are_coherent(self) -> None:
        issues = validate_premature_wrk_recovery()
        self.assertEqual(issues, [], issue_report(issues))

    def test_fresh_release_with_mixed_winners_restores_exact_packages(self) -> None:
        effects = read(
            "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
        )
        wkr_router = named_block(
            effects, "ADISCORD_vorkerland_restore_premature_wrk_packages_to_wkr"
        )
        tva_router = named_block(
            effects, "ADISCORD_vorkerland_restore_premature_wrk_packages_to_tva"
        )
        for district, states in (
            ("RIV", (79, 306, 308, 309, 327)),
            ("SWB", (35,)),
        ):
            with self.subTest(winner="WKR", district=district):
                self.assertIn(
                    f"{district} = {{ has_country_flag = "
                    "ADISCORD_vorkerland_central_minor_winner_wkr }",
                    wkr_router,
                )
                for state_id in states:
                    self.assertRegex(
                        wkr_router,
                        rf"(?s){state_id}\s*=\s*\{{\s*is_owned_by\s*=\s*WRK\s*\}}"
                        rf".*?transfer_state\s*=\s*{state_id}\b"
                        rf".*?set_state_controller_to\s*=\s*WKR",
                    )
        for district, states in (("REV", (82, 323)), ("OSV", (318, 320))):
            with self.subTest(winner="TVA", district=district):
                self.assertIn(
                    f"{district} = {{ has_country_flag = "
                    "ADISCORD_vorkerland_central_minor_winner_tva }",
                    tva_router,
                )
                for state_id in states:
                    self.assertRegex(
                        tva_router,
                        rf"(?s){state_id}\s*=\s*\{{\s*is_owned_by\s*=\s*WRK\s*\}}"
                        rf".*?transfer_state\s*=\s*{state_id}\b"
                        rf".*?set_state_controller_to\s*=\s*TVA",
                    )

    def test_human_handoff_precedes_false_wrk_annex(self) -> None:
        effects = read(
            "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
        )
        dissolve = named_block(
            effects, "ADISCORD_vorkerland_dissolve_premature_wrk_as_claimant"
        )
        route_end = max(
            dissolve.index(
                f"ADISCORD_vorkerland_restore_premature_wrk_packages_to_{tag} = yes"
            )
            for tag in ("wkr", "vad", "tva")
        )
        release_subjects = dissolve.index(
            "WRK = { ADISCORD_vorkerland_release_losing_claimant_subjects = yes }"
        )
        handoff = dissolve.index("change_tag_from = WRK")
        annex = dissolve.index("annex_country = { target = WRK transfer_troops = yes }")
        self.assertLess(route_end, release_subjects)
        self.assertLess(release_subjects, handoff)
        self.assertLess(handoff, annex)

    def test_inverse_subject_hook_routes_to_one_living_claimant(self) -> None:
        effects = read(
            "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
        )
        dispatcher = named_block(
            effects,
            "ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant",
        )
        calls = [
            dispatcher.index(
                f"{tag} = {{ ADISCORD_vorkerland_dissolve_premature_wrk_as_claimant = yes }}"
            )
            for tag in ("WKR", "VAD", "TVA")
        ]
        self.assertEqual(calls, sorted(calls))
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        for hook_name in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
            hook = named_block(on_actions, hook_name)
            self.assertIn(
                "ADISCORD_vorkerland_release_requires_interception = yes", hook
            )
            self.assertIn(
                "ADISCORD_vorkerland_intercept_premature_wrk_release = yes", hook
            )
        capitulation = named_block(on_actions, "on_capitulation")
        self.assertIn(
            "ROOT = { ADISCORD_vorkerland_is_premature_wrk = yes }", capitulation
        )
        self.assertIn("set_global_flag = skip_default_capitulation", capitulation)
        self.assertIn(
            "ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant = yes",
            capitulation,
        )

    def test_release_hooks_delegate_once_to_shared_interceptor(self) -> None:
        release_path = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        self.assertTrue(release_path.is_file())
        release_effects = release_path.read_text(encoding="utf-8-sig")
        interceptor = named_block(
            release_effects,
            "ADISCORD_vorkerland_intercept_premature_wrk_release",
        )
        for token in (
            "set_global_flag = ADISCORD_vorkerland_premature_wrk_release_intercepted_v1",
            "FROM = { ADISCORD_vorkerland_dissolve_premature_wrk_as_claimant = yes }",
            "ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant = yes",
        ):
            self.assertIn(token, interceptor)

        triggers = source_section(
            read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"),
            'collapse_triggers',
        )
        release_guard = named_block(
            triggers,
            "ADISCORD_vorkerland_release_requires_interception",
        )
        self.assertIn("ADISCORD_vorkerland_is_premature_wrk = yes", release_guard)
        self.assertIn(
            "FROM = { ADISCORD_vorkerland_is_premature_wrk = yes }",
            release_guard,
        )

        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        call = "ADISCORD_vorkerland_intercept_premature_wrk_release = yes"
        for hook_name in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
            hook = named_block(on_actions, hook_name)
            self.assertEqual(hook.count(call), 1, hook_name)
            self.assertIn(
                "ADISCORD_vorkerland_release_requires_interception = yes", hook
            )
            self.assertNotIn(
                "set_global_flag = ADISCORD_vorkerland_premature_wrk_release_intercepted_v1",
                hook,
            )

        puppet = named_block(on_actions, "on_puppet")
        release_puppet = named_block(on_actions, "on_release_as_puppet")
        release_free = named_block(on_actions, "on_release_as_free")
        puppet_normal = named_block(named_block(puppet, "effect"), "else")
        release_puppet_normal = named_block(
            named_block(release_puppet, "effect"), "else"
        )
        release_free_normal = named_block(named_block(release_free, "effect"), "else")
        for normal in (puppet_normal, release_puppet_normal, release_free_normal):
            self.assertRegex(
                normal,
                r"limit = \{ OR = \{ tag = ROM tag = TRU tag = ZAO tag = SOL \} \}",
            )
            self.assertIn(
                "ADISCORD_vorkerland_sync_independence_cosmetic = yes",
                normal,
            )
        self.assertIn(
            "ADISCORD_vorkerland_sync_republics_from_ruins = yes", puppet_normal
        )
        self.assertIn(
            "ADISCORD_vorkerland_wrk_activate_vla_auxiliaries = yes", puppet_normal
        )
        # VLA serves its wartime patron WKR first, then whichever claimant
        # holds the nation target; the retired WRK tag takes no auxiliaries.
        nation_patron = f"tag = VLA is_subject_of = {NATION_TARGET}"
        self.assertIn("tag = VLA is_subject_of = WKR", puppet_normal)
        self.assertIn(nation_patron, puppet_normal)
        self.assertNotIn("is_subject_of = WRK", puppet_normal)
        self.assertLess(
            puppet_normal.find("tag = VLA is_subject_of = WKR"),
            puppet_normal.find(nation_patron),
        )
        self.assertIn(
            f"{NATION_TARGET} = {{ ADISCORD_vorkerland_wrk_activate_vla_auxiliaries = yes }}",
            puppet_normal,
        )
        self.assertIn(
            "ADISCORD_vorkerland_sync_republics_from_ruins = yes",
            release_puppet_normal,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_wrk_activate_vla_auxiliaries = yes",
            release_puppet_normal,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_sync_republics_from_ruins = yes", release_free_normal
        )

    def test_old_save_claimant_inference_is_absent(self) -> None:
        combined = "\n".join(
            (
                source_section(
                    read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"),
                    'collapse_triggers',
                ),
                read(
                    "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
                ),
                read_country_on_actions(
                    "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
                    'vorkerland_collapse',
                ),
            )
        )
        for token in (
            "ADISCORD_vorkerland_repair_premature_wrk",
            "ADISCORD_vorkerland_premature_wrk_records_wkr_claimant",
            "ADISCORD_vorkerland_premature_wrk_records_vad_claimant",
            "ADISCORD_vorkerland_premature_wrk_records_tva_claimant",
            "ADISCORD_vorkerland_premature_wrk_recorded_wkr",
            "ADISCORD_vorkerland_premature_wrk_recorded_vad",
            "ADISCORD_vorkerland_premature_wrk_recorded_tva",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


class CampaignStateOwnershipTests(unittest.TestCase):
    def test_doctrine_refresh_is_checked_in_each_owner_not_by_total_call_count(self) -> None:
        from tools.validators import validate_adiscord_vorkerland_recovery as validator

        self.assertTrue(hasattr(validator, "validate_focus_doctrine_refreshes"))
        source = "\n".join(read(f"focus_trees/Vorkerland/{tag}/focuses.txt")
                           for tag in ("wkr", "vad", "tva"))
        extra = "focus = { id = extra_refresh completion_reward = { ADISCORD_vorkerland_refresh_doctrine_dynamic_state = yes } }"
        self.assertEqual(validator.validate_focus_doctrine_refreshes(source + extra), [])
        focus_id = "VAD_doctrine_of_the_officer_estates"
        block = next(block for block in named_blocks(source, "focus")
                     if re.search(rf"\bid\s*=\s*{focus_id}\b", block))
        broken = source.replace(block, block.replace("ADISCORD_vorkerland_refresh_doctrine_dynamic_state = yes", ""))
        issues = validator.validate_focus_doctrine_refreshes(broken + extra)
        self.assertEqual(len(issues), 1)
        self.assertIn(focus_id, issues[0])

    def test_event_driven_campaign_state_contract_is_clean(self) -> None:
        issues = validate_campaign_state()
        self.assertEqual(issues, [], issue_report(issues))

    def test_claimant_monthly_hooks_carry_the_western_clock_for_the_nation_only(
        self,
    ) -> None:
        on_actions = read_country_on_actions(ON_ACTIONS_FILE, 'vorkerland_collapse')
        clock = "ADISCORD_west_crisis_month = yes"
        factory_scaling = "ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes"
        for tag in CLAIMANTS:
            with self.subTest(tag=tag):
                hook = named_block(on_actions, f"on_monthly_{tag}")
                clocks = [block for block in named_blocks(hook, "if") if clock in block]
                self.assertEqual(len(clocks), 1)
                self.assertEqual(hook.count(clock), 1)
                guard = named_block(clocks[0], "limit")
                self.assertIn(f"tag = {NATION_TARGET}", guard)
                self.assertIn("ADISCORD_west_crisis_open = yes", guard)
                self.assertEqual(hook.count(factory_scaling), 0 if tag == "TVA" else 1)

        cases = (
            (
                "on_monthly_TVA",
                [(clock, f"{clock}\n\t\t\t\t{factory_scaling}")],
                "TVA programmes must not use a monthly factory-scaling hook",
            ),
            (
                "on_monthly_TVA",
                [
                    (
                        f"{clock}\n\t\t\t}}",
                        f"{clock}\n\t\t\t}}\n\t\t\tVAD_monthly_district_unrest = yes",
                    )
                ],
                "on_monthly_TVA may carry only the western crisis clock",
            ),
            (
                "on_monthly_TVA",
                [(f"tag = {NATION_TARGET}", "tag = TVA")],
                "on_monthly_TVA must run the western crisis clock once, for the nation "
                "target only",
            ),
            (
                "on_monthly_WKR",
                [(f"tag = {NATION_TARGET}", "ADISCORD_vorkerland_is_live_claimant = no")],
                "on_monthly_WKR must run the western crisis clock once, for the nation "
                "target only",
            ),
        )
        for hook_name, replacements, expected in cases:
            with self.subTest(expected=expected), serve_mutation(
                ON_ACTIONS_FILE, effect(hook_name), replacements
            ):
                issues = validate_campaign_state()
                self.assertIn(expected, issues, issue_report(issues))


class RetiredLegacyEventTests(unittest.TestCase):
    def test_old_save_scheduler_events_are_removed(self) -> None:
        issues = validate_retired_legacy_events()
        self.assertEqual(issues, [], issue_report(issues))


class VorkerlandRecoveryValidatorTests(unittest.TestCase):
    def test_integrated_recovery_contract(self) -> None:
        issues = collect_issues()
        self.assertEqual(issues, [], issue_report(issues))


if __name__ == "__main__":
    unittest.main()
