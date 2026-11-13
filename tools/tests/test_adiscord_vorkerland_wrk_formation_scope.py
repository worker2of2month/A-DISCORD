from __future__ import annotations

import re
import unittest
from dataclasses import replace
from itertools import product
from pathlib import Path


from tools.lib.paths import source_section
from tools.tests.test_adiscord_stp_preparation import (
    event_target,
    matches_conditions,
    block as parsed_block,
    scalar,
    selected_effects,
    walk,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
PHASE_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
PHASE_EVENTS = ROOT / "events/ADISCORD_vorkerland_events.txt"
PHASE_TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
SCRIPTED_TRIGGERS = ROOT / "common/scripted_triggers"
ON_ACTIONS = ROOT / "common/on_actions"

# The global event target naming the country that currently is Vorkerland.
NATION = "ADISCORD_vorkerland_nation"
NATION_TARGET = f"event_target:{NATION}"
NATION_BINDING = f"save_global_event_target_as = {NATION}"
CLAIMANTS = ("WKR", "VAD", "TVA")
ROUTE_FLAGS = {
    "WKR": "ADISCORD_vorkerland_route_worker",
    "VAD": "ADISCORD_vorkerland_route_joint",
    "TVA": "ADISCORD_vorkerland_route_utilitarian",
}
ABSORBED_DISTRICTS = ("WTD", "EGC", "RIV", "YOR")
# Effects that replace the executing country, its research or its player.
COUNTRY_REPLACEMENT_EFFECTS = frozenset((
    "annex_country",
    "change_tag_from",
    "inherit_technology",
    "set_nationality",
))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def balanced_block(source: str, opening_brace: int) -> str:
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : index]
    raise AssertionError("unterminated Clausewitz block")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    return balanced_block(source, source.find("{", match.start()))


def event_block(source: str, event_id: str) -> str:
    id_match = re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", source)
    if id_match is None:
        raise AssertionError(f"missing event: {event_id}")
    event_start = source.rfind("country_event", 0, id_match.start())
    opening_brace = source.find("{", event_start, id_match.start())
    return balanced_block(source, opening_brace)


def without_comments(source: str) -> str:
    return re.sub(r"#[^\n]*", "", source)


def triggers_reading_the_country_target() -> list[str]:
    """Scripted triggers whose own body resolves the country target."""
    names = []
    for path in sorted(SCRIPTED_TRIGGERS.glob("*.txt")):
        source = without_comments(read(path))
        if NATION_TARGET not in source:
            continue
        for match in re.finditer(r"(?m)^(\w+)\s*=\s*\{", source):
            if NATION_TARGET in balanced_block(source, match.end() - 1):
                names.append(match[1])
    return names


def startup_blocks() -> list[tuple[str, str]]:
    """The on_startup block of every on_action file, in the order the files load."""
    blocks = []
    for path in sorted(ON_ACTIONS.glob("*.txt"), key=lambda item: item.name):
        source = without_comments(read(path))
        if re.search(r"(?m)^\s*on_startup\s*=\s*\{", source):
            blocks.append((path.name, named_block(source, "on_startup")))
    return blocks


def country_target_binding_sites() -> dict[str, int]:
    """Script files that save the country target, with the number of statements."""
    sites = {}
    for folder in ("common", "events"):
        for path in sorted((ROOT / folder).rglob("*.txt")):
            count = without_comments(
                path.read_text(encoding="utf-8-sig", errors="replace")
            ).count(NATION_BINDING)
            if count:
                sites[path.relative_to(ROOT).as_posix()] = count
    return sites


def unified_by(winner: str) -> dict:
    """Scenario facts for a campaign in which the winner is the Vorkerland country."""
    return {("event_target", NATION): winner}


def run_with_rebinding(items, facts, scope):
    """Select an effect's actions and move the country target where it is saved.

    selected_effects evaluates lazily, so every statement after the rebinding
    already reads the new binding from the scenario facts. A reference between
    clearing and saving finds the target unbound.
    """
    actions = []
    for inner, entry in selected_effects(items, facts, scope):
        if entry.key == "clear_global_event_target" and entry.value == NATION:
            facts[("event_target", NATION)] = None
        elif entry.key == "save_global_event_target_as" and entry.value == NATION:
            facts[("event_target", NATION)] = inner
        actions.append((inner, entry))
    return actions


class VorkerlandUnificationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_effects = read(PHASE_EFFECTS)
        cls.effects = source_section(cls.all_effects, 'phase_effects')
        cls.events = source_section(read(PHASE_EVENTS), 'phase_events')
        cls.triggers = read(PHASE_TRIGGERS)
        cls.parsed_triggers = {e.key: e.value for e in parse_clausewitz(cls.triggers)}

    def effect(self, name: str):
        return parse_clausewitz(named_block(self.all_effects, name))

    def expanded(self, items):
        """Inline scripted triggers so a scenario states only native facts."""
        result = []
        for entry in items:
            if entry.key in self.parsed_triggers:
                self.assertIn(entry.value, ("yes", "no"))
                result.append(replace(
                    entry,
                    key="AND" if entry.value == "yes" else "NOT",
                    value=self.expanded(self.parsed_triggers[entry.key]),
                ))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expanded(entry.value)))
            else:
                result.append(entry)
        return result

    def verified_facts(self, winner: str) -> dict:
        facts = {
            **unified_by(winner),
            (winner, "exists", "yes"): True,
            (winner, "is_subject", "no"): True,
            (winner, "controls_state", "32"): True,
            (winner, "has_country_flag", ROUTE_FLAGS[winner]): True,
            ("32", "is_owned_by", winner): True,
            ("32", "is_controlled_by", winner): True,
        }
        for rival in CLAIMANTS:
            if rival != winner:
                facts[(rival, "exists", "no")] = True
        return facts

    def assert_district_player_follows_the_nation(self, district: str) -> None:
        event = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.7"))
        immediate = parsed_block(event, "immediate")
        for nation in CLAIMANTS:
            with self.subTest(nation=nation, district=district):
                facts = {
                    **unified_by(nation),
                    (nation, "is_ai", "yes"): True,
                    (district, "exists", "yes"): True,
                    (district, "is_ai", "no"): True,
                }
                actions = list(selected_effects(immediate, facts, nation))
                self.assertEqual(
                    [(scope, e.key) for scope, e in actions],
                    [(nation, "country_event"), (nation, "change_tag_from")],
                )
                self.assertEqual(scalar(actions[0][1].value, "id"), "ADISCORD_vorkerland_phase.7")
                self.assertEqual(actions[1][1].value, district)
                facts[(nation, "is_ai", "yes")] = False
                actions = list(selected_effects(immediate, facts, nation))
                self.assertFalse(any(e.key == "change_tag_from" for _, e in actions))
                self.assertEqual(
                    (actions[0][0], actions[0][1].key),
                    (nation, "ADISCORD_vorkerland_finish_delayed_unification"),
                )

    def test_republic_defeat_follows_the_wartime_country(self) -> None:
        defeated = parse_clausewitz(
            named_block(self.triggers, "ADISCORD_vorkerland_wrk_defeated")
        )
        for exists, capitulated, expected in (
            (True, False, False),
            (True, True, True),
            (False, False, True),
        ):
            with self.subTest(exists=exists, capitulated=capitulated):
                facts = {
                    ("VAD", "country_exists", "WKR"): exists,
                    ("VAD", "country_exists", "WRK"): False,
                    ("WKR", "has_capitulated", "yes"): capitulated,
                }
                self.assertEqual(matches_conditions(defeated, facts, "VAD"), expected)

    def test_country_target_is_bound_at_startup_and_rebound_only_by_unification(self) -> None:
        # Across all scripts the target is saved once by a startup hook and
        # once by each of the three unifications.
        sites = country_target_binding_sites()
        effects = PHASE_EFFECTS.relative_to(ROOT).as_posix()
        self.assertEqual(sites.pop(effects, 0), len(CLAIMANTS))
        self.assertEqual(list(sites.values()), [1], sites)
        startup_file = next(iter(sites))
        self.assertEqual(Path(startup_file).parent.as_posix(), "common/on_actions")
        binding_blocks = [
            block for name, block in startup_blocks()
            if name == Path(startup_file).name and NATION_BINDING in block
        ]
        self.assertEqual(len(binding_blocks), 1)
        startup = parsed_block(parse_clausewitz(binding_blocks[0]), "effect")
        bound = [
            scope for scope, e in selected_effects(startup, {}, "")
            if e.key == "save_global_event_target_as" and e.value == NATION
        ]
        self.assertEqual(bound, ["WRK"])
        clear = f"clear_global_event_target = {NATION}"
        self.assertEqual(self.all_effects.count(clear), len(CLAIMANTS))
        for winner in CLAIMANTS:
            with self.subTest(winner=winner):
                unification = self.effect(f"ADISCORD_vorkerland_unify_under_{winner.lower()}")
                self.assertEqual(
                    [(e.key, e.value) for e in unification[:2]],
                    [
                        ("clear_global_event_target", NATION),
                        ("save_global_event_target_as", NATION),
                    ],
                )

    def test_startup_reads_the_country_target_only_after_binding_it(self) -> None:
        # Startup effects of all on_action files run in file-name order and
        # top to bottom, so nothing before the binding statement can resolve
        # the target: a scope on it is skipped and a tag comparison is false.
        readers = triggers_reading_the_country_target()
        self.assertIn("ADISCORD_vorkerland_is_not_wartime_claimant", readers)
        premature = []
        for name, startup in startup_blocks():
            bound_here = NATION_BINDING in startup
            if bound_here:
                startup = startup[: startup.index(NATION_BINDING)]
            if NATION_TARGET in startup:
                premature.append((name, NATION_TARGET))
            premature.extend(
                (name, reader) for reader in readers
                if re.search(rf"\b{re.escape(reader)}\b", startup)
            )
            if bound_here:
                break
        else:
            self.fail("no startup hook binds the country target")
        self.assertEqual(premature, [])

    def test_winner_keeps_its_tag_and_queues_settlement_on_itself(self) -> None:
        phase_seven = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.7"))
        accepted = parsed_block(phase_seven, "trigger")
        phase = "ADISCORD_vorkerland_phase_reunification"
        for winner, human in product(CLAIMANTS, (True, False)):
            with self.subTest(winner=winner, human=human):
                unification = self.effect(f"ADISCORD_vorkerland_unify_under_{winner.lower()}")
                facts = {
                    (winner, "is_ai", "no" if human else "yes"): True,
                    (winner, "has_global_flag", phase): True,
                    ("WRK", "has_global_flag", phase): True,
                }
                self.assertTrue(matches_conditions(accepted, facts, "WRK"))
                self.assertFalse(matches_conditions(accepted, facts, winner))

                actions = run_with_rebinding(unification, facts, winner)
                self.assertEqual(
                    [(scope, e.key) for scope, e in actions[:2]],
                    [
                        (winner, "clear_global_event_target"),
                        (winner, "save_global_event_target_as"),
                    ],
                )
                self.assertEqual(event_target(NATION_TARGET, facts), winner)
                # A human and an AI winner run the same statements, and none
                # of them replaces the executing country or moves its player.
                keys = {e.key for e in walk(unification)}
                self.assertFalse(keys & COUNTRY_REPLACEMENT_EFFECTS)
                self.assertNotIn("is_ai", keys)
                queued = [
                    (scope, scalar(e.value, "id"))
                    for scope, e in actions
                    if e.key == "country_event"
                ]
                self.assertEqual(queued, [(winner, "ADISCORD_vorkerland_phase.7")])
                self.assertEqual(actions[-1][1].key, "country_event")
                self.assertTrue(matches_conditions(accepted, facts, winner))
                self.assertFalse(matches_conditions(accepted, facts, "WRK"))

    def test_a_live_or_liberated_rival_blocks_every_victory_route(self) -> None:
        routes = {
            "WKR": ("worker", (27, 32, 33, 34, 35, 40, 79, 82)),
            "VAD": ("vlad", (32, 40, 75, 81)),
            "TVA": ("dorian", (32, 40, 36, 37, 38, 39)),
        }
        for winner, (route, states) in routes.items():
            candidate = self.expanded(
                self.parsed_triggers[f"ADISCORD_vorkerland_{route}_victory_candidate"]
            )
            facts = {(winner, "controls_state", str(state)): True for state in states}
            self.assertTrue(matches_conditions(candidate, facts, winner))
            for rival in routes.keys() - {winner}:
                with self.subTest(winner=winner, rival=rival):
                    facts[(winner, "country_exists", rival)] = True
                    facts[(rival, "has_capitulated", "yes")] = False
                    self.assertFalse(matches_conditions(candidate, facts, winner))
                    facts[(rival, "has_capitulated", "yes")] = True
                    self.assertTrue(matches_conditions(candidate, facts, winner))
                    facts[(rival, "has_capitulated", "yes")] = False
                    self.assertFalse(matches_conditions(candidate, facts, winner))
                    facts[(winner, "country_exists", rival)] = False

    def test_oitfort_handoff_cannot_invalidate_settlement(self) -> None:
        self.assert_district_player_follows_the_nation("WTD")

    def test_lost_victory_before_handoff_reopens_the_war_phase(self) -> None:
        event = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.6"))
        facts = {
            ("VAD", "has_global_flag", "ADISCORD_vorkerland_phase_reunification"): True,
            ("VAD", "ADISCORD_vorkerland_coalition_victory_ready", "yes"): False,
        }
        self.assertTrue(matches_conditions(parsed_block(event, "trigger"), facts, "VAD"))
        actions = run_with_rebinding(parsed_block(event, "immediate"), facts, "VAD")
        self.assertIn(("VAD", "ADISCORD_vorkerland_set_phase_central_showdown"), [
            (scope, e.key) for scope, e in actions
        ])
        self.assertFalse(any(e.key in ("transfer_state", "change_tag_from", "annex_country") for _, e in actions))
        # No claimant unifies the country, so the target stays with WRK.
        self.assertFalse(any(
            e.key.startswith("ADISCORD_vorkerland_unify_under_") for _, e in actions
        ))
        self.assertEqual(event_target(NATION_TARGET, facts), "WRK")

    def test_all_routes_annex_claimants_oitfort_and_zshat_with_troop_transfer(self) -> None:
        effects = {e.key: e.value for e in parse_clausewitz(self.effects)}
        finish = effects["ADISCORD_vorkerland_finish_delayed_unification"]
        settlement_prefix = "ADISCORD_vorkerland_settle_unification_under_"

        def settlements(facts, scope):
            return [
                e.key for _, e in selected_effects(finish, facts, scope)
                if e.key.startswith(settlement_prefix)
            ]

        for winner in CLAIMANTS:
            with self.subTest(winner=winner):
                rivals = [tag for tag in CLAIMANTS if tag != winner]
                facts = {
                    (winner, "has_country_flag", ROUTE_FLAGS[winner]): True,
                    ("WRK", "has_country_flag", ROUTE_FLAGS[winner]): True,
                    ("EGC", "has_country_flag", "ADISCORD_vorkerland_prep_treaty_signed"): True,
                }
                for tag in (*CLAIMANTS, *ABSORBED_DISTRICTS):
                    facts[(winner, "country_exists", tag)] = True
                # Only the country bound to the target settles its route.
                self.assertEqual(settlements(facts, winner), [])
                facts.update(unified_by(winner))
                self.assertEqual(settlements(facts, "WRK"), [])
                dispatch = settlements(facts, winner)
                self.assertEqual(dispatch, [settlement_prefix + winner.lower()])
                absorptions = (
                    "ADISCORD_vorkerland_absorb_wtd_after_reunification",
                    "ADISCORD_vorkerland_absorb_egc_after_reunification",
                    "ADISCORD_vorkerland_absorb_treaty_districts_after_reunification",
                    "ADISCORD_vorkerland_absorb_treaty_district",
                )

                def expand(items, scope, district):
                    for inner, entry in selected_effects(items, facts, scope):
                        if entry.key in absorptions:
                            yield from expand(effects[entry.key], inner, inner)
                        else:
                            yield inner, entry, district

                annexations = []
                for scope, entry, district in expand(effects[dispatch[0]], winner, winner):
                    self.assertNotEqual(entry.key, "change_tag_from")
                    if entry.key == "annex_country":
                        self.assertEqual(scope, winner)
                        self.assertEqual(scalar(entry.value, "transfer_troops"), "yes")
                        target = scalar(entry.value, "target")
                        annexations.append(district if target == "PREV" else target)
                self.assertCountEqual(annexations, [*rivals, *ABSORBED_DISTRICTS])

    def test_zshat_player_handoff_precedes_annexation(self) -> None:
        self.assert_district_player_follows_the_nation("EGC")

    def test_treaty_district_player_handoff_precedes_annexation(self) -> None:
        for tag in ("RIV", "YOR"):
            self.assert_district_player_follows_the_nation(tag)

    def test_treaty_district_absorption_clears_treaty_and_skips_absent_country(self) -> None:
        effects = {e.key: e.value for e in parse_clausewitz(self.effects)}
        district = effects["ADISCORD_vorkerland_absorb_treaty_district"]
        for flag in (
            "ADISCORD_vorkerland_prep_treaty_signed",
            "ADISCORD_vorkerland_prep_independence_guaranteed",
            "ADISCORD_vorkerland_reunification_ally",
        ):
            self.assertIn(flag, [e.value for e in district if e.key == "clr_country_flag"])
        self.assertIn("ADISCORD_vorkerland_prep_treaty_patron", [e.value for e in district if e.key == "clear_variable"])
        keys = [e.key for e in district]
        self.assertLess(keys.index("clear_variable"), keys.index(NATION_TARGET))
        absorb = effects["ADISCORD_vorkerland_absorb_treaty_districts_after_reunification"]
        for nation in CLAIMANTS:
            with self.subTest(nation=nation):
                facts = {
                    **unified_by(nation),
                    (nation, "country_exists", "RIV"): True,
                    (nation, "country_exists", "YOR"): False,
                }
                calls = [(scope, e.key) for scope, e in selected_effects(absorb, facts, nation)]
                self.assertIn(("RIV", "ADISCORD_vorkerland_absorb_treaty_district"), calls)
                self.assertNotIn(("YOR", "ADISCORD_vorkerland_absorb_treaty_district"), calls)
                annexed = [
                    (scope, scalar(e.value, "target"), scalar(e.value, "transfer_troops"))
                    for scope, e in selected_effects(district, facts, "RIV")
                    if e.key == "annex_country"
                ]
                self.assertEqual(annexed, [(nation, "PREV", "yes")])

    def test_zshat_settlement_controls_owned_districts_and_skips_absent_country(self) -> None:
        effect = parse_clausewitz(named_block(
            self.effects, "ADISCORD_vorkerland_absorb_egc_after_reunification"
        ))
        for nation in CLAIMANTS:
            with self.subTest(nation=nation):
                facts = {
                    **unified_by(nation),
                    (nation, "country_exists", "EGC"): True,
                    ("81", "is_owned_by", nation): True,
                    ("110", "is_owned_by", nation): True,
                    ("124", "is_owned_by", nation): False,
                }
                actions = list(selected_effects(effect, facts, nation))
                self.assertEqual(
                    [(scope, entry.value) for scope, entry in actions if entry.key == "set_state_controller_to"],
                    [("81", NATION_TARGET), ("110", NATION_TARGET)],
                )
                self.assertIn("ADISCORD_economy_mark_dirty", [entry.key for _, entry in actions])
                # Districts held by the retired tag are not the unified country's.
                retired = {
                    **unified_by(nation),
                    (nation, "country_exists", "EGC"): True,
                    ("81", "is_owned_by", "WRK"): True,
                }
                self.assertFalse(any(
                    entry.key == "set_state_controller_to"
                    for _, entry in selected_effects(effect, retired, nation)
                ))
                facts[(nation, "country_exists", "EGC")] = False
                self.assertEqual(list(selected_effects(effect, facts, nation)), [])

    def test_surviving_zshat_blocks_terminal_verification(self) -> None:
        gate = self.expanded(
            self.parsed_triggers["ADISCORD_vorkerland_reunification_verified"]
        )
        for winner in CLAIMANTS:
            facts = self.verified_facts(winner)
            self.assertTrue(matches_conditions(gate, facts, winner))
            for tag in ABSORBED_DISTRICTS:
                with self.subTest(winner=winner, surviving=tag):
                    blocked = {**facts, (winner, "country_exists", tag): True}
                    self.assertFalse(matches_conditions(gate, blocked, winner))

    def test_verification_accepts_only_the_unified_claimant(self) -> None:
        gate = self.expanded(
            self.parsed_triggers["ADISCORD_vorkerland_reunification_verified"]
        )
        for winner in CLAIMANTS:
            facts = self.verified_facts(winner)
            self.assertTrue(matches_conditions(gate, facts, winner))
            for rival in CLAIMANTS:
                if rival == winner:
                    continue
                with self.subTest(winner=winner, surviving=rival):
                    blocked = dict(facts)
                    del blocked[(rival, "exists", "no")]
                    self.assertFalse(matches_conditions(gate, blocked, winner))
            for missing in (
                (winner, "exists", "yes"),
                (winner, "is_subject", "no"),
                (winner, "controls_state", "32"),
                (winner, "has_country_flag", ROUTE_FLAGS[winner]),
                ("32", "is_owned_by", winner),
                ("32", "is_controlled_by", winner),
            ):
                with self.subTest(winner=winner, missing=missing):
                    blocked = dict(facts)
                    del blocked[missing]
                    self.assertFalse(matches_conditions(gate, blocked, winner))
            with self.subTest(winner=winner, capitulated=True):
                blocked = {**facts, (winner, "has_capitulated", "yes"): True}
                self.assertFalse(matches_conditions(gate, blocked, winner))
        # The retired tag can never pass, whatever it holds.
        retired = {
            ("WRK", "exists", "yes"): True,
            ("WRK", "is_subject", "no"): True,
            ("WRK", "controls_state", "32"): True,
            ("WRK", "has_country_flag", ROUTE_FLAGS["VAD"]): True,
            ("32", "is_owned_by", "WRK"): True,
            ("32", "is_controlled_by", "WRK"): True,
        }
        for claimant in CLAIMANTS:
            retired[(claimant, "exists", "no")] = True
        self.assertEqual(event_target(NATION_TARGET, retired), "WRK")
        self.assertFalse(matches_conditions(gate, retired, "WRK"))

    def test_worker_victory_is_checked_on_the_living_claimant(self) -> None:
        candidate = named_block(
            self.triggers, "ADISCORD_vorkerland_worker_victory_candidate"
        )
        self.assertRegex(candidate, r"(?m)^\s*tag = WKR\s*$")
        self.assertNotRegex(candidate, r"(?m)^\s*tag = WRK\s*$")

    def test_reunification_dispatch_does_not_use_the_callback_country(self) -> None:
        dispatch = named_block(
            self.effects, "ADISCORD_vorkerland_begin_reunification"
        )
        outer = named_block(dispatch, "if")
        gate = named_block(outer, "limit")
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_phase_reunification }",
            gate,
        )
        event = "country_event = { id = ADISCORD_vorkerland_phase.6 days = 1 }"
        branches = re.findall(r"\b(?:if|else_if)\s*=\s*\{", outer)
        self.assertEqual(len(branches), 3)
        normalized = " ".join(outer.split())
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(
                f"{tag} = {{ exists = yes is_subject = no NOT = {{ has_capitulated = yes }} }}",
                normalized,
            )
            self.assertIn(f"{tag} = {{ {event} }}", outer)
        self.assertEqual(outer.count(event), 3)

    def test_each_winner_keeps_its_own_country(self) -> None:
        for winner in CLAIMANTS:
            suffix = winner.lower()
            with self.subTest(winner=winner):
                unification = named_block(
                    self.effects, f"ADISCORD_vorkerland_unify_under_{suffix}"
                )
                settlement = named_block(
                    self.effects, f"ADISCORD_vorkerland_settle_unification_under_{suffix}"
                )
                block = unification + settlement
                normalized = " ".join(block.split())
                route = f"set_country_flag = {ROUTE_FLAGS[winner]}"

                self.assertEqual(block.count("transfer_state = 32"), 1)
                self.assertIn(f"32 = {{ set_state_controller_to = {winner} }}", unification)
                self.assertNotIn("set_state_controller_to = WRK", block)
                # Research, development, characters and the player stay with
                # the victor; nothing copies them to another country.
                for replaced in (
                    "inherit_technology",
                    "ADISCORD_copy_development_from_prev",
                    "change_tag_from",
                    "set_nationality",
                ):
                    self.assertNotIn(replaced, block)
                self.assertNotIn(f"annex_country = {{ target = {winner}", normalized)
                rival_annexations = [
                    f"if = {{ limit = {{ country_exists = {rival} }} "
                    f"annex_country = {{ target = {rival} transfer_troops = yes }} }}"
                    for rival in CLAIMANTS if rival != winner
                ]
                for annexation in rival_annexations:
                    self.assertEqual(normalized.count(annexation), 1)
                focus_tree = parsed_block(parse_clausewitz(unification), "load_focus_tree")
                self.assertEqual(scalar(focus_tree, "keep_completed"), "yes")
                self.assertEqual(scalar(focus_tree, "copy_completed_from"), "WRK")
                self.assertIn("focus_unlock = yes", settlement)
                self.assertIn("mark_focus_tree_layout_dirty = yes", settlement)

                self.assertLess(
                    unification.index(f"save_global_event_target_as = {NATION}"),
                    unification.index("transfer_state = 32"),
                )
                self.assertLess(
                    unification.index("transfer_state = 32"),
                    unification.index("load_focus_tree"),
                )
                self.assertLess(
                    unification.index(route),
                    unification.index("country_event = { id = ADISCORD_vorkerland_phase.7"),
                )
                normalized_settlement = " ".join(settlement.split())
                finalize = normalized_settlement.index(
                    "ADISCORD_vorkerland_finalize_unified_territory = yes"
                )
                for annexation in rival_annexations:
                    self.assertLess(normalized_settlement.index(annexation), finalize)
                # Finalizing the territory clears every route flag; the route
                # is recorded again before verification reads it.
                self.assertEqual(normalized_settlement.count(route), 1)
                self.assertLess(finalize, normalized_settlement.index(route))

    def test_claimant_and_retired_cores_pass_to_the_unified_country(self) -> None:
        finalize = self.effect("ADISCORD_vorkerland_finalize_unified_territory")
        self.assertEqual(
            [e.key for e in finalize if e.value == "yes"],
            [
                "ADISCORD_vorkerland_inherit_integrated_claimant_cores",
                "ADISCORD_vorkerland_inherit_retired_cores",
            ],
        )
        integrated = self.effect("ADISCORD_vorkerland_inherit_integrated_claimant_cores")
        states = [entry.key for entry in integrated]
        self.assertIn("32", states)
        self.assertEqual(len(states), len(set(states)))
        for entry in integrated:
            with self.subTest(state=entry.key):
                self.assertRegex(entry.key, r"^\d+$")
                self.assertEqual(
                    [(e.key, e.value) for e in entry.value],
                    [("ADISCORD_vorkerland_settle_claimant_core", "yes")],
                )

        settle = self.effect("ADISCORD_vorkerland_settle_claimant_core")
        consumed = [("remove_core_of", claimant) for claimant in CLAIMANTS]
        for nation, holder in product(CLAIMANTS, CLAIMANTS):
            with self.subTest(nation=nation, holder=holder):
                held = {
                    **unified_by(nation),
                    ("32", "is_owned_by", nation): True,
                    ("32", "is_core_of", holder): True,
                }
                # The unified country is itself a claimant tag, so its core is
                # added only after every claimant core has been removed.
                self.assertEqual(
                    [(e.key, e.value) for _, e in selected_effects(settle, held, "32")],
                    [*consumed, ("add_core_of", NATION_TARGET)],
                )
                lost = {**unified_by(nation), ("32", "is_core_of", holder): True}
                self.assertEqual(
                    [(e.key, e.value) for _, e in selected_effects(settle, lost, "32")],
                    consumed,
                )

        retired = parsed_block(
            self.effect("ADISCORD_vorkerland_inherit_retired_cores"), "every_state"
        )
        self.assertEqual(
            [(e.key, e.value) for e in parsed_block(retired, "limit")],
            [("is_core_of", "WRK")],
        )
        self.assertEqual(
            [(e.key, e.value) for e in retired if e.key != "limit"],
            [("add_core_of", NATION_TARGET), ("remove_core_of", "WRK")],
        )

    def test_only_the_worker_victory_keeps_its_reform_stage(self) -> None:
        crisis = [
            "WRK_ashes_of_the_crown",
            "WRK_hourglass_of_discord",
            "WRK_constitution_of_the_republic",
        ]
        scrub = self.effect("ADISCORD_vorkerland_scrub_precollapse_crisis")
        self.assertEqual({e.key for e in scrub}, {"remove_ideas"})
        scrubbed = [e.value for e in scrub]
        self.assertEqual(scrubbed[:3], crisis)
        # The scrub also removes the worker reform stages reached in the war.
        self.assertTrue(scrubbed[3:])
        worker = self.effect("ADISCORD_vorkerland_settle_unification_under_wkr")
        self.assertEqual([e.value for e in worker if e.key == "remove_ideas"], crisis)
        self.assertNotIn(
            "ADISCORD_vorkerland_scrub_precollapse_crisis", [e.key for e in walk(worker)]
        )
        for suffix in ("vad", "tva"):
            with self.subTest(winner=suffix.upper()):
                settlement = self.effect(f"ADISCORD_vorkerland_settle_unification_under_{suffix}")
                self.assertIn(
                    ("ADISCORD_vorkerland_scrub_precollapse_crisis", "yes"),
                    [(e.key, e.value) for e in settlement],
                )

    def test_worker_route_uses_authored_anton_fallback(self) -> None:
        unification = self.effect("ADISCORD_vorkerland_unify_under_wkr")
        settlement = self.effect("ADISCORD_vorkerland_settle_unification_under_wkr")
        outcome = "ADISCORD_vorkerland_worker_utilitarian_outcome"
        loyalists = ("WKR", "has_global_flag", "ADISCORD_vorkerland_worker_safe_with_loyalists")

        # The unification records the winner's chosen course as a receipt
        # that the settlement reads; a stale receipt is cleared.
        for executive, receipt in ((True, "set_country_flag"), (False, "clr_country_flag")):
            with self.subTest(executive=executive):
                facts = {("WKR", "WKR_executive_course", "yes"): executive}
                recorded = [
                    (scope, e.key)
                    for scope, e in run_with_rebinding(unification, facts, "WKR")
                    if e.value == outcome
                ]
                self.assertEqual(recorded, [("WKR", receipt)])

        appointments = ("WKR_appoint_executive", "WKR_appoint_chairman", "promote_character")
        cases = (
            ({("WKR", "has_country_flag", outcome): True, loyalists: True}, "WKR_appoint_executive"),
            ({loyalists: True}, "promote_character"),
            ({}, "WKR_appoint_chairman"),
        )
        for scenario, expected in cases:
            with self.subTest(appointment=expected, scenario=sorted(scenario)):
                facts = {**unified_by("WKR"), **scenario}
                seated = [
                    (scope, e) for scope, e in selected_effects(settlement, facts, "WKR")
                    if e.key in appointments
                ]
                self.assertEqual([(scope, e.key) for scope, e in seated], [("WKR", expected)])
                if expected == "promote_character":
                    self.assertEqual(scalar(seated[0][1].value, "character"), "WRK_Nikita_Worcker")

        executive = named_block(self.all_effects, "WKR_appoint_executive")
        chairman = named_block(self.all_effects, "WKR_appoint_chairman")
        anton = named_block(self.all_effects, "ADISCORD_vorkerland_promote_anton_bagley")
        self.assertIn("ADISCORD_vorkerland_promote_anton_bagley = yes", executive)
        self.assertIn("character = WRK_Anton_Bagley", anton)
        self.assertNotIn("WKR_Emergency_Coordination_Committee", chairman)
        self.assertIn("WKR_appoint_executive = yes", chairman)
        sources = (
            named_block(self.effects, "ADISCORD_vorkerland_unify_under_wkr"),
            named_block(self.effects, "ADISCORD_vorkerland_settle_unification_under_wkr"),
            executive,
            chairman,
            anton,
        )
        for source in sources:
            self.assertNotIn("WKR_Worker_Emergency_Presidium", source)
            self.assertNotIn("Lucas", source)

    def test_route_leaders_stay_with_their_winners(self) -> None:
        roster = self.effect("ADISCORD_vorkerland_adopt_retired_roster")
        self.assertEqual([e.key for e in roster], ["WRK"])
        moved = parsed_block(parsed_block(roster, "WRK"), "every_character")
        self.assertEqual([e.key for e in moved], ["set_nationality"])
        self.assertEqual(
            [(e.key, e.value) for e in moved[0].value],
            [("target_country", NATION_TARGET)],
        )
        for winner in CLAIMANTS:
            with self.subTest(winner=winner):
                suffix = winner.lower()
                actions = run_with_rebinding(
                    self.effect(f"ADISCORD_vorkerland_unify_under_{suffix}"), {}, winner
                )
                calls = [(scope, e.key) for scope, e in actions]
                adoption = calls.index((winner, "ADISCORD_vorkerland_adopt_retired_roster"))
                self.assertLess(calls.index((winner, "save_global_event_target_as")), adoption)
                self.assertLess(adoption, calls.index((winner, "country_event")))
                # Characters already serving the winner are never moved away.
                for name in (
                    f"ADISCORD_vorkerland_unify_under_{suffix}",
                    f"ADISCORD_vorkerland_settle_unification_under_{suffix}",
                ):
                    self.assertNotIn("set_nationality", named_block(self.effects, name))

        vad = self.effect("ADISCORD_vorkerland_settle_unification_under_vad")
        governments = (
            ("ADISCORD_vorkerland_joint_government_formed", "ADISCORD_vorkerland_appoint_joint_council"),
            ("ADISCORD_vorkerland_collegial_staff_formed", "VAD_appoint_collegial_staff"),
            (None, "promote_character"),
        )
        appointments = [appointment for _, appointment in governments]
        for flag, expected in governments:
            with self.subTest(government=flag):
                facts = unified_by("VAD")
                if flag is not None:
                    facts[("VAD", "has_global_flag", flag)] = True
                seated = [
                    (scope, e) for scope, e in selected_effects(vad, facts, "VAD")
                    if e.key in appointments
                ]
                self.assertEqual([(scope, e.key) for scope, e in seated], [("VAD", expected)])
                if expected == "promote_character":
                    self.assertEqual(scalar(seated[0][1].value, "character"), "WRK_Vlad_Petrichev")
        self.assertIn(
            "character = WRK_VAD_Joint_Council",
            named_block(self.all_effects, "ADISCORD_vorkerland_appoint_joint_council"),
        )
        self.assertIn(
            "character = WRK_Vlad_Petrichev",
            named_block(self.all_effects, "VAD_appoint_collegial_staff"),
        )

        tva = self.effect("ADISCORD_vorkerland_settle_unification_under_tva")
        promoted = [
            (scope, scalar(e.value, "character"), scalar(e.value, "ideology"))
            for scope, e in selected_effects(tva, unified_by("TVA"), "TVA")
            if e.key == "promote_character"
        ]
        self.assertEqual(promoted, [("TVA", "TVA_Dorian_Worx", "dorian_technocracy")])

    def test_claimant_war_command_spirits_expire_before_settlement_is_queued(self) -> None:
        contracts = {
            "WKR": (
                "ADISCORD_vorkerland_wkr_front_operations_bureau",
                "ADISCORD_vorkerland_wkr_republican_mission_commands",
                "ADISCORD_vorkerland_wkr_normative_campaign_tables",
            ),
            "VAD": (
                "ADISCORD_vorkerland_vad_restoration_war_cabinet_2",
                "ADISCORD_vorkerland_vad_dual_authority_protocol_2",
            ),
        }
        for tag, ideas in contracts.items():
            with self.subTest(tag=tag):
                unification = self.effect(f"ADISCORD_vorkerland_unify_under_{tag.lower()}")
                actions = [
                    (scope, e.key, e.value if isinstance(e.value, str) else None)
                    for scope, e in run_with_rebinding(unification, {}, tag)
                ]
                queued = [key for _, key, _ in actions].index("country_event")
                for idea in ideas:
                    removal = (tag, "remove_ideas", idea)
                    self.assertIn(removal, actions)
                    self.assertLess(actions.index(removal), queued)

    def test_phase_six_runs_each_unification_in_the_winner_scope(self) -> None:
        phase_six = event_block(self.events, "ADISCORD_vorkerland_phase.6")
        self.assertEqual(
            phase_six.count(
                "country_event = { id = ADISCORD_vorkerland_phase.7 days = 1 }"
            ),
            0,
        )
        immediate = parsed_block(parse_clausewitz(phase_six), "immediate")
        for winner in CLAIMANTS:
            effect = f"ADISCORD_vorkerland_unify_under_{winner.lower()}"
            with self.subTest(winner=winner):
                self.assertEqual(phase_six.count(f"{effect} = yes"), 1)
                self.assertIn(f"{winner} = {{\n\t\t\t\t{effect} = yes", phase_six)
                facts = {
                    (winner, "ADISCORD_vorkerland_coalition_victory_ready", "yes"): True,
                    (winner, "ADISCORD_vorkerland_has_live_marked_central_unifier", "no"): True,
                    (winner, "exists", "yes"): True,
                    (winner, "is_subject", "no"): True,
                }
                calls = [
                    (scope, e.key) for scope, e in selected_effects(immediate, facts, winner)
                ]
                self.assertEqual(calls, [(winner, effect)])

    def test_phase_six_prefers_the_marked_winner_over_tag_order(self) -> None:
        phase_six = event_block(self.events, "ADISCORD_vorkerland_phase.6")
        self.assertEqual(
            phase_six.count("ADISCORD_vorkerland_has_live_marked_central_unifier = no"),
            3,
        )
        for tag in ("WKR", "VAD", "TVA"):
            with self.subTest(winner=tag):
                self.assertRegex(
                    phase_six,
                    rf"{tag}\s*=\s*\{{\s*has_country_flag\s*=\s*ADISCORD_vorkerland_central_unifier\s*\}}",
                )
        marker = named_block(
            self.triggers, "ADISCORD_vorkerland_has_live_marked_central_unifier"
        )
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(
                f"{tag} = {{ exists = yes is_subject = no NOT = {{ has_capitulated = yes }} "
                "has_country_flag = ADISCORD_vorkerland_central_unifier }",
                marker,
            )

    def test_terminal_winner_replaces_stale_unifier_markers(self) -> None:
        contracts = {
            "ADISCORD_vorkerland_apply_worker_map": ("WKR", ("VAD", "TVA")),
            "ADISCORD_vorkerland_apply_vlad_map": ("VAD", ("WKR", "TVA")),
            "ADISCORD_vorkerland_apply_dorian_map": ("TVA", ("WKR", "VAD")),
        }
        for effect_name, (winner, losers) in contracts.items():
            with self.subTest(effect=effect_name):
                effect = named_block(self.all_effects, effect_name)
                self.assertRegex(
                    effect,
                    rf"{winner}\s*=\s*\{{[\s\S]*?set_country_flag\s*=\s*ADISCORD_vorkerland_central_unifier",
                )
                for loser in losers:
                    self.assertIn(
                        f"country_exists = {loser} }} {loser} = {{ clr_country_flag = "
                        "ADISCORD_vorkerland_central_unifier",
                        effect,
                    )

    def test_tva_formation_rebinds_tgd_but_absorbs_oitfort(self) -> None:
        tva = named_block(self.effects, "ADISCORD_vorkerland_settle_unification_under_tva")
        self.assertIn("country_exists = TGD", tva)
        self.assertIn("ADISCORD_vorkerland_joined_worx_directorate", tva)
        self.assertIn("puppet = TGD", tva)
        self.assertIn("freedom_level = 0.10", tva)
        self.assertIn("ADISCORD_vorkerland_absorb_wtd_after_reunification = yes", tva)
        self.assertNotIn("puppet = WTD", tva)
        self.assertNotIn("freedom_level = 0.15", tva)

    def test_worx_formation_preserves_claimant_colour(self) -> None:
        tva = named_block(self.effects, "ADISCORD_vorkerland_settle_unification_under_tva")
        cosmetic = "WRK_vorkerland_technocracy"
        self.assertGreater(
            tva.index(f"set_cosmetic_tag = {cosmetic}"),
            tva.index("ADISCORD_vorkerland_finalize_unified_territory = yes"),
        )
        palette = named_block(read(ROOT / "common/countries/cosmetic.txt"), cosmetic)
        original = read(ROOT / "common/countries/TVA.txt")
        colour = re.search(r"color\s*=\s*rgb\s*\{[^}]+\}", original).group()
        self.assertIn(colour, palette)

    def test_no_random_lucas_contract_leaks_into_formation(self) -> None:
        self.assertNotIn("Lucas", self.effects)
        self.assertNotIn("Lucas", self.events)


class VorkerlandNationTargetTests(unittest.TestCase):
    """Vorkerland as a country is addressed through its global event target.

    The winning claimant keeps its own tag, so a literal WRK reference would
    address the retired tag after the civil war.
    """

    NATION = "event_target:ADISCORD_vorkerland_nation"
    SCAN_DIRS = ("common", "events", "focus_trees")
    SKIPPED_PREFIXES = (
        "common/national_focus/",
        "common/country_tags/",
        "common/countries/",
        "common/units/",
        "common/names/",
        "focus_trees/Vorkerland/prewar/",
    )
    # Files and definitions that address the retired WRK object itself.
    LITERAL_FILES = {
        "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt",
        "common/scripted_effects/ADISCORD_technology_baseline_effects.txt",
    }
    LITERAL_BLOCKS = {
        "ADISCORD_vorkerland_prepare_initial_combatants",
        "ADISCORD_vorkerland_prepare_claimant_characters",
        "ADISCORD_vorkerland_reset_temporary_claimant_cores",
        "ADISCORD_vorkerland_inherit_wrk_prewar_preparations",
        "ADISCORD_vorkerland_repair_collapse_materialization",
        "ADISCORD_vorkerland_log_materialization_failure",
        "ADISCORD_vorkerland_set_phase_prewar",
        "ADISCORD_vorkerland_inherit_retired_cores",
        "ADISCORD_vorkerland_adopt_retired_roster",
        "ADISCORD_vorkerland_is_premature_wrk",
        "ADISCORD_vorkerland_wrk_release_is_forbidden",
        "ADISCORD_vorkerland_collapse_materialized",
        # Collapse-time and campaign-start definitions of the WRK object.
        "ADISCORD_vorkerland_prepare_conflict_country",
        "ADISCORD_vorkerland_finalize_conflict_spirits",
        "ADISCORD_vorkerland_repair_claimant_spirit_progression",
        "ADISCORD_vorkerland_leave_inherited_faction",
        "ADISCORD_vorkerland_relocate_legacy_armies",
        "ADISCORD_economy_apply_country_starting_profile",
    }
    VALUE_KEYS = (
        "tag", "original_tag", "country_exists", "is_owned_by", "is_controlled_by",
        "is_owned_and_controlled_by", "is_core_of", "add_core_of", "remove_core_of",
        "has_war_with", "has_war_together_with", "is_subject_of", "is_in_faction_with",
        "is_neighbor_of", "set_state_owner_to", "set_state_controller_to", "target",
        "white_peace", "targeted_alliance", "enemy", "puppet", "add_to_faction",
        "give_military_access",
    )

    @staticmethod
    def _code(line):
        quoted = False
        for index, char in enumerate(line):
            if char == '"':
                quoted = not quoted
            elif char == "#" and not quoted:
                return line[:index]
        return line

    def _scripts(self):
        for directory in self.SCAN_DIRS:
            for path in sorted((ROOT / directory).rglob("*.txt")):
                relative = path.relative_to(ROOT).as_posix()
                if relative.startswith(self.SKIPPED_PREFIXES) or relative in self.LITERAL_FILES:
                    continue
                yield relative, path.read_text(encoding="utf-8-sig").splitlines()

    def _names_all_claimants(self, lines, index):
        """True when line `index` compares the tag inside a list that also
        names WKR, VAD and TVA: such a list enumerates tag objects, and the
        winner is in it under its own tag."""
        claimants = {"WKR", "VAD", "TVA"}
        tag = re.compile(r"(?<![A-Za-z_])tag = ([A-Z]{3})(?![A-Za-z0-9_])")
        inline = re.compile(r"\{[^{}]*\}")
        code = self._code(lines[index])
        for group in inline.findall(code):
            if "tag = WRK" in group and claimants <= set(tag.findall(group)):
                return True
        if code.strip() != "tag = WRK":
            return False
        tags = set()
        for step in (-1, 1):
            depth = 0
            position = index + step
            while 0 <= position < len(lines):
                other = self._code(lines[position])
                opened = other.count("{")
                closed = other.count("}")
                if step == -1:
                    if opened > closed and depth == 0:
                        break
                    depth += closed - opened
                else:
                    if closed > opened and depth == 0:
                        break
                    depth += opened - closed
                if depth == 0 and opened == closed:
                    tags.update(tag.findall(inline.sub("", other)))
                position += step
        return claimants <= tags

    def _allowed_blocks(self, lines):
        """Yield (first, last, text) for every `allowed = { ... }` block."""
        depth = 0
        start = None
        start_depth = 0
        for index, raw in enumerate(lines):
            code = self._code(raw)
            if start is None and re.search(r"\ballowed\s*=\s*\{", code):
                start = index
                start_depth = depth
            depth += code.count("{") - code.count("}")
            if start is not None and depth <= start_depth:
                yield start, index, "\n".join(self._code(line) for line in lines[start:index + 1])
                start = None

    def test_no_script_addresses_the_country_by_the_retired_tag(self):
        scope = re.compile(r"(?<![A-Za-z0-9_:.])WRK\s*=\s*\{")
        value = re.compile(r"\b(?:" + "|".join(self.VALUE_KEYS) + r")\s*=\s*WRK(?![A-Za-z0-9_])")
        offenders = []
        for relative, lines in self._scripts():
            load_time = set()
            for first, last, _ in self._allowed_blocks(lines):
                load_time.update(range(first, last + 1))
            depth = 0
            block = None
            for index, raw in enumerate(lines):
                code = self._code(raw)
                if depth == 0:
                    head = re.match(r"([A-Za-z0-9_.@:]+)\s*=\s*\{", code)
                    block = head.group(1) if head else None
                depth += code.count("{") - code.count("}")
                if block in self.LITERAL_BLOCKS or index in load_time:
                    continue
                if self._names_all_claimants(lines, index):
                    continue
                # The startup statement that binds the target names WRK itself.
                if "save_global_event_target_as = ADISCORD_vorkerland_nation" in code:
                    continue
                # Asking which tag the target currently is names the tag literally.
                if self.NATION + " = {" in code:
                    code = re.sub(r"(?<![A-Za-z_])tag\s*=\s*WRK(?![A-Za-z0-9_])", "", code)
                if scope.search(code) or value.search(code):
                    offenders.append(f"{relative}:{index + 1}: {raw.strip()}")
        self.assertEqual(offenders, [], "address Vorkerland through " + self.NATION)

    def test_load_time_conditions_admit_every_tag_that_can_be_the_country(self):
        claimant = re.compile(r"\b(?:original_)?tag\s*=\s*(?:WKR|VAD|TVA)\b")
        negated = re.compile(r"\bNOT\s*=\s*\{[^{}]*\b(?:original_)?tag\s*=\s*WRK\b")
        literal = re.compile(r"\b(?:original_)?tag\s*=\s*WRK(?![A-Za-z0-9_])")
        offenders = []
        for relative, lines in self._scripts():
            for first, _, text in self._allowed_blocks(lines):
                if literal.search(text) and not claimant.search(text) and not negated.search(text):
                    offenders.append(f"{relative}:{first + 1}")
        self.assertEqual(offenders, [], "`allowed` is read once at load and must list the claimant tags")


if __name__ == "__main__":
    unittest.main()
