"""Kefreyt's postwar reckoning and the last war of the east, parsed and executed.

Native campaign behaviour, event windows and AI choices still need a cold load.
"""

import json
import re
import unittest
from collections import defaultdict
from itertools import product
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import block, entries, scalar, walk
from tools.tests.test_adiscord_val_new_world import ContractWorld


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = "common/scripted_effects/ADISCORD_VAL_effects.txt"
DECISIONS = "common/decisions/ADISCORD_VAL_decisions.txt"
EVENTS = "events/ADISCORD_VAL_contract_events.txt"
TREE = "focus_trees/VAL/new_world/focuses.txt"
PEACE = "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
REGIMES = {
    1: "VAL_peace_throne",
    2: "VAL_peace_cabinet",
    3: "VAL_peace_charter",
    4: "VAL_peace_captains",
}
CASUS = (
    "VAL_throne_two_crowns",
    "VAL_cabinet_defence_treaty",
    "VAL_charter_general_campaign",
    "VAL_captains_last_buyer",
)


class ReckoningWorld(ContractWorld):
    """Adds the balance, temporary values and global markers the reckoning reads."""

    _parsed = None

    def __init__(self):
        # Parsing the effect files dominates the cost; the parsed views are immutable.
        if ReckoningWorld._parsed is None:
            super().__init__()
            ReckoningWorld._parsed = (self.effects, self.triggers, self.data.default_factory)
        else:
            self.effects, self.triggers, factory = ReckoningWorld._parsed
            self.data = defaultdict(factory)
            self.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = 2000
            self.target = "176"
            self.targets = {}
            self.events = []
            self.dirty = set()
        self.temps = {}
        self.globals = {}
        self.global_flags = set()
        self.calls = []
        self.intercept = set()

    def number(self, value, scope):
        if value in self.temps:
            return self.temps[value]
        if value.startswith("global."):
            return self.globals.get(value.removeprefix("global."), 0)
        return super().number(value, scope)

    COMPARE = {
        "equals": lambda a, b: a == b,
        "greater_than_or_equals": lambda a, b: a >= b,
        "greater_than": lambda a, b: a > b,
        "less_than": lambda a, b: a < b,
        "less_than_or_equals": lambda a, b: a <= b,
    }

    def matches(self, rows, scope="VAL"):
        plain = []
        for row in rows:
            if row.key == "has_global_flag":
                if row.value not in self.global_flags:
                    return False
            elif row.key == "check_variable":
                left = self.number(scalar(row.value, "var"), scope)
                right = self.number(scalar(row.value, "value"), scope)
                if not self.COMPARE[scalar(row.value, "compare")](left, right):
                    return False
            elif row.key == "NOT":
                if self.matches(row.value, scope):
                    return False
            elif row.key in ("AND", "hidden_trigger"):
                if not self.matches(row.value, scope):
                    return False
            elif row.key == "OR":
                if not any(self.matches(group, scope) for group in self.condition_groups(row.value)):
                    return False
            elif row.key in self.triggers:
                if self.matches(self.triggers[row.key], scope) != (row.value == "yes"):
                    return False
            elif isinstance(row.value, list) and re.fullmatch(r"[A-Z]{3}", row.key):
                if not self.matches(row.value, row.key):
                    return False
            else:
                plain.append(row)
        return super().matches(plain, scope) if plain else True

    def execute(self, rows, scope="VAL"):
        taken = False
        for row in rows:
            key, value = row.key, row.value
            country = self.data[scope]
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                active = not taken and (key == "else" or self.matches(block(value, "limit"), scope))
                if active:
                    self.execute([e for e in value if e.key != "limit"], scope)
                taken |= active
            elif key in ("hidden_effect", "effect"):
                self.execute(value, scope)
            elif key in self.effects and key not in self.intercept:
                self.execute(self.effects[key], scope)
            elif isinstance(value, list) and re.fullmatch(r"[A-Z]{3}|\d+", key):
                self.execute(value, key)
            elif key in self.intercept:
                self.calls.append((scope, key))
            elif key in ("set_temp_variable", "add_to_temp_variable"):
                name = scalar(value, "var")
                amount = self.number(scalar(value, "value"), scope)
                self.temps[name] = amount if key == "set_temp_variable" else self.temps.get(name, 0) + amount
            elif key == "multiply_variable":
                name = scalar(value, "var")
                country["vars"][name] = country["vars"].get(name, 0) * self.number(scalar(value, "value"), scope)
            elif key == "add_power_balance_value":
                name = scalar(value, "id")
                if name in country["bop"]:
                    country["bop"][name] = max(-1.0, min(1.0, country["bop"][name] + float(scalar(value, "value"))))
            elif key == "set_power_balance":
                country["bop"][scalar(value, "id")] = float(scalar(value, "set_value"))
            elif key == "activate_mission":
                country["missions"].add(value)
            elif key == "set_global_flag":
                self.global_flags.add(value)
            elif key == "clr_global_flag":
                self.global_flags.discard(value)
            elif key == "news_event":
                self.events.append(("news", scalar(value, "id")))
            elif key == "remove_dynamic_modifier":
                country["modifiers"].discard(scalar(value, "modifier"))
            elif key in ("mark_focus_tree_layout_dirty",):
                pass
            else:
                super().execute([row], scope)

    def crisis(self, strike=20, balance=0.0):
        self.data["VAL"]["bop"]["VAL_peace_balance"] = balance
        self.data["VAL"]["vars"].update(VAL_peace_strike=strike, VAL_peace_arrears=0, VAL_peace_orders=0)
        return self


def country_event(event_id):
    return next(e.value for e in entries(EVENTS) if e.key in ("country_event", "news_event")
                and scalar(e.value, "id") == event_id)


def tree_focuses():
    return {scalar(e.value, "id"): e.value for e in block(entries(TREE), "focus_tree") if e.key == "focus"}


def exclusive_rivals(focus):
    return {e.value for group in (e.value for e in focus if e.key == "mutually_exclusive")
            for e in group if e.key == "focus"}


class ReckoningMechanicsTests(unittest.TestCase):
    def strike(self, world, delta):
        world.temps["VAL_peace_strike_delta"] = delta
        world.run("VAL_peace_apply_strike")
        return world.data["VAL"]["vars"]["VAL_peace_strike"]

    def test_rising_thresholds_notify_once_and_a_general_strike_opens_the_reckoning(self):
        world = ReckoningWorld().crisis(strike=44)
        self.assertEqual(self.strike(world, 6), 50)
        self.assertEqual(self.strike(world, -10), 40)
        self.assertEqual(self.strike(world, 45), 85)
        self.assertEqual(self.strike(world, 40), 100)
        self.assertEqual([e for _, e in world.events],
                         ["val_peace.21", "val_peace.21", "val_peace.22", "val_peace.23"])
        for event_id in ("val_peace.21", "val_peace.22", "val_peace.23"):
            self.assertEqual(scalar(country_event(event_id), "fire_only_once"), "yes")
        option = block(country_event("val_peace.23"), "option")
        self.assertEqual(scalar(block(option, "hidden_effect"), "VAL_peace_open_reckoning"), "yes")

    def test_crisis_modifier_follows_the_strike_and_the_workers_charter(self):
        world = ReckoningWorld().crisis(strike=100)
        world.run("VAL_peace_refresh")
        values = world.data["VAL"]["vars"]
        self.assertAlmostEqual(values["VAL_peace_factory_output"], -0.20)
        self.assertAlmostEqual(values["VAL_peace_stability"], -0.15)
        self.assertAlmostEqual(values["VAL_peace_military_income"], -0.25)
        self.assertAlmostEqual(values["VAL_peace_pp_gain"], -0.15)
        world.data["VAL"]["focuses"].add("VAL_peace_workers_charter")
        values["VAL_peace_orders"] = 9
        world.run("VAL_peace_refresh")
        self.assertAlmostEqual(values["VAL_peace_factory_output"], -0.23)
        self.assertEqual(values["VAL_peace_orders"], 5)
        self.assertAlmostEqual(values["VAL_peace_military_income"], 0.0)
        self.assertIn("VAL_peace_crisis", world.data["VAL"]["modifiers"])

    def test_monthly_strike_slows_with_the_answer_and_restored_works(self):
        for focus, works, expected in (
            (None, 0, 26), ("VAL_peace_workers_charter", 0, 22), ("VAL_peace_land_for_service", 0, 23),
            ("VAL_peace_shift_law", 0, 30), (None, 1, 24), (None, 2, 22),
        ):
            with self.subTest(focus=focus, works=works):
                world = ReckoningWorld().crisis(strike=20)
                if focus:
                    world.data["VAL"]["focuses"].add(focus)
                for state in ("176", "177")[:works]:
                    world.data[state]["flags"].add("RUS_reactor_works_restored")
                    world.data[state]["buildings"]["industrial_complex"] = 1
                world.run("VAL_peace_monthly")
                self.assertEqual(world.data["VAL"]["vars"]["VAL_peace_strike"], expected)
                self.assertEqual(world.data["VAL"]["vars"]["VAL_peace_arrears"], 1)

    def test_company_debt_drifts_the_balance_with_a_weekly_cap(self):
        for arrears, drift in ((0, 0.0), (1, 0.005), (2, 0.01), (3, 0.015), (4, 0.02), (9, 0.02)):
            with self.subTest(arrears=arrears):
                world = ReckoningWorld().crisis()
                world.data["VAL"]["vars"]["VAL_peace_arrears"] = arrears
                world.run("VAL_peace_weekly")
                self.assertAlmostEqual(world.data["VAL"]["bop"]["VAL_peace_balance"], drift)

    def test_payroll_debits_exactly_once_at_the_affordability_boundary(self):
        world = ReckoningWorld().crisis(strike=40, balance=0.2)
        values = world.data["VAL"]["vars"]
        values["ADISCORD_economy_treasury"] = 119.5
        world.data["VAL"]["pp"] = 25
        world.run("VAL_peace_pay_companies")
        self.assertEqual(values["ADISCORD_economy_treasury"], 119.5)
        values["ADISCORD_economy_treasury"] = 120
        values["VAL_peace_arrears"] = 3
        world.run("VAL_peace_pay_companies")
        self.assertEqual(values["ADISCORD_economy_treasury"], 0)
        self.assertEqual(world.data["VAL"]["pp"], 0)
        self.assertEqual(values["VAL_peace_arrears"], 0)
        self.assertAlmostEqual(world.data["VAL"]["bop"]["VAL_peace_balance"], 0.12)
        self.assertEqual(values["VAL_peace_strike"], 45)
        values["ADISCORD_economy_treasury"] = 100
        world.run("VAL_peace_pay_shifts")
        self.assertEqual(values["ADISCORD_economy_treasury"], 0)
        self.assertEqual(values["VAL_peace_strike"], 33)
        self.assertAlmostEqual(world.data["VAL"]["bop"]["VAL_peace_balance"], 0.16)
        world.run("VAL_peace_pay_shifts")
        self.assertEqual(values["VAL_peace_strike"], 33)

    def test_foreign_order_is_paid_once_and_delivers_after_the_reckoning(self):
        world = ReckoningWorld().crisis(strike=30)
        values = world.data["VAL"]["vars"]
        values["ADISCORD_economy_treasury"] = 0
        world.data["VAL"]["rifles"] = {"VAL": 10800}
        world.run("VAL_peace_begin_foreign_order")
        world.run("VAL_peace_begin_foreign_order")
        self.assertEqual(world.data["VAL"]["rifles"]["VAL"], 5400)
        self.assertEqual(world.data["VAL"]["pp"], 950)
        del world.data["VAL"]["bop"]["VAL_peace_balance"]
        world.run("VAL_peace_deliver_foreign_order")
        world.run("VAL_peace_deliver_foreign_order")
        self.assertEqual(values["ADISCORD_economy_treasury"], 200)
        self.assertEqual(values["VAL_peace_orders"], 0)
        self.assertNotIn("VAL_peace_order_deposit", values)

    def test_the_reckoning_always_offers_an_answer_and_the_coup_is_exclusive(self):
        options = [e.value for e in country_event("val_peace.40") if e.key == "option"]
        answers = {scalar(option, "name"): block(option, "trigger") for option in options}
        self.assertEqual(set(answers), {"val_peace.40.a", "val_peace.40.b", "val_peace.40.c", "val_peace.40.e"})
        balances = [round(-1 + 0.05 * step, 2) for step in range(41)]
        world = ReckoningWorld()
        country = world.data["VAL"]
        for balance, strike, answer, truth, told, file in product(
            balances, range(0, 101, 10),
            (None, "VAL_peace_land_for_service", "VAL_peace_workers_charter", "VAL_peace_shift_law"),
            (False, True), (False, True), (False, True),
        ):
            world.crisis(strike=strike, balance=balance)
            country["focuses"] = {answer} if answer else set()
            country["flags"] = set()
            for flag, enabled in (("VAL_peace_truth_public", truth), ("VAL_daughter_secret_told", told),
                                  ("VAL_peace_velsky_holds_file", file)):
                if enabled:
                    country["flags"].add(flag)
            # The truth becomes public only after Krutov already knew it.
            if truth and not told:
                continue
            available = {name for name, trigger in answers.items() if world.matches(trigger)}
            forced = balance >= 0.9
            with self.subTest(balance=balance, strike=strike, answer=answer, truth=truth, told=told, file=file):
                self.assertTrue(available)
                if forced:
                    self.assertEqual(available, {"val_peace.40.e"})
                else:
                    self.assertNotIn("val_peace.40.e", available)

    def test_the_balance_extremes_send_the_coup_or_expose_the_plot(self):
        balance = block(entries("common/bop/VAL.txt"), "VAL_peace_balance")
        ranges = {scalar(r.value, "id"): r.value for side in balance if side.key == "side"
                  for r in side.value if r.key == "range"}
        coup, exposed = ranges["VAL_peace_captains_coup"], ranges["VAL_peace_captains_exposed"]
        self.assertEqual((scalar(coup, "min"), scalar(coup, "max")), ("0.90", "1.00"))
        self.assertEqual((scalar(exposed, "min"), scalar(exposed, "max")), ("-1.00", "-0.90"))
        self.assertEqual(scalar(block(block(coup, "on_activate"), "if"), "VAL_peace_open_reckoning"), "yes")
        self.assertEqual(scalar(block(block(exposed, "on_activate"), "country_event"), "id"), "val_peace.13")

        world = ReckoningWorld().crisis(strike=50, balance=-0.95)
        country = world.data["VAL"]
        country["vars"]["VAL_peace_arrears"] = 3
        world.execute(block(block(country_event("val_peace.13"), "option"), "hidden_effect"))
        self.assertIn("VAL_peace_plot_exposed", country["flags"])
        self.assertEqual(country["vars"]["VAL_peace_arrears"], 0)
        self.assertEqual(country["vars"]["ADISCORD_economy_treasury"], 2150)

        # A plot exposed earlier in the reckoning cannot seize power at the other extreme.
        country["bop"]["VAL_peace_balance"] = 1.0
        forced = world.triggers["VAL_peace_captains_forced"]
        self.assertFalse(world.matches(forced))
        country["flags"].discard("VAL_peace_plot_exposed")
        self.assertTrue(world.matches(forced))
        teardown = {e.key: e.value for e in entries(EFFECTS)}["VAL_peace_close_crisis"]
        cleared = {e.value for e in teardown if e.key == "clr_country_flag"}
        self.assertIn("VAL_peace_plot_exposed", cleared)

    def test_regime_answers_add_pure_order_inputs_before_the_teardown_event(self):
        effects = {e.key: e.value for e in entries(EFFECTS)}
        for regime, name in enumerate(("throne", "cabinet", "charter", "captains"), start=1):
            with self.subTest(regime=name):
                world = ReckoningWorld().crisis()
                world.run(f"VAL_peace_adopt_{name}")
                values = world.data["VAL"]["vars"]
                self.assertEqual(values["VAL_peace_regime"], regime)
                self.assertIn("VAL_peace_order", world.data["VAL"]["modifiers"])
                self.assertEqual(world.events, [("VAL", "val_peace.41")])
                keys = [e.key for e in effects[f"VAL_peace_adopt_{name}"]]
                self.assertNotIn("VAL_peace_close_crisis", keys)
        install = [e.key for e in effects["VAL_peace_install_regime"]]
        self.assertEqual(install[0], "VAL_peace_close_crisis")
        teardown = country_event("val_peace.41")
        self.assertEqual(scalar(teardown, "hidden"), "yes")
        self.assertEqual(scalar(block(teardown, "immediate"), "VAL_peace_install_regime"), "yes")

    def test_closing_the_crisis_removes_only_crisis_state_and_completes_recovery(self):
        world = ReckoningWorld().crisis(strike=60, balance=0.3)
        world.intercept = {"VAL_peace_complete_recovery"}
        world.data["VAL"]["modifiers"].update({"VAL_peace_crisis", "VAL_peace_order"})
        world.data["VAL"]["missions"].add("VAL_peace_reckoning")
        world.run("VAL_peace_close_crisis")
        country = world.data["VAL"]
        self.assertNotIn("VAL_peace_balance", country["bop"])
        self.assertEqual(country["modifiers"], {"VAL_peace_order"})
        self.assertFalse({k for k in country["vars"] if k.startswith("VAL_peace_") and not k.startswith("VAL_peace_order")})
        self.assertEqual(world.calls, [("VAL", "VAL_peace_complete_recovery")])
        complete = [e.key for e in block(entries(EFFECTS), "VAL_peace_complete_recovery")]
        self.assertLess(complete.index("set_country_flag"), complete.index("VAL_advance_economic_recovery"))


class EastFinalWarTests(unittest.TestCase):
    RESOLUTIONS = {"VAL_east_resolve_val_victory", "VAL_east_resolve_rival_victory", "VAL_east_resolve_without_hegemon"}

    def war(self, rival_kind):
        world = ReckoningWorld()
        world.intercept = set(self.RESOLUTIONS)
        world.global_flags.add("VAL_east_final_started")
        world.globals["VAL_east_rival_kind"] = rival_kind
        rival = "MON" if rival_kind == 1 else "RUS"
        world.data["VAL"]["vars"]["VAL_east_side"] = 1
        world.data[rival]["vars"]["VAL_east_side"] = 2
        home = ("48", "24", "42", "56", "57")
        enemy = ("469", "460", "444", "425", "453") if rival_kind == 1 else ("66", "176", "177", "188", "192")
        for state in home:
            world.data[state].update(owner="VAL", controller="VAL")
        for state in enemy:
            world.data[state].update(owner=rival, controller=rival)
        return world, rival, home, enemy

    def resolve(self, world):
        world.calls = []
        world.run("VAL_east_final_resolve_by_control")
        return [name for _, name in world.calls]

    def test_control_scores_only_the_other_sides_key_states_and_ties_have_no_hegemon(self):
        for kind in (1, 2):
            with self.subTest(kind=kind):
                world, rival, home, enemy = self.war(kind)
                self.assertEqual(self.resolve(world), ["VAL_east_resolve_without_hegemon"])
                world.data[enemy[0]]["controller"] = "VAL"
                self.assertEqual(self.resolve(world), ["VAL_east_resolve_val_victory"])
                world.data[home[0]]["controller"] = rival
                self.assertEqual(self.resolve(world), ["VAL_east_resolve_without_hegemon"])
                world.data[home[1]]["controller"] = rival
                self.assertEqual(self.resolve(world), ["VAL_east_resolve_rival_victory"])
                # A side's own land never scores for it.
                world.data[enemy[1]]["owner"] = "VAL"
                world.data[enemy[1]]["controller"] = "VAL"
                self.assertEqual(self.resolve(world), ["VAL_east_resolve_rival_victory"])

    def test_resolution_requires_an_active_campaign_and_a_vanished_rival_loses(self):
        world, rival, _, _ = self.war(1)
        world.global_flags.add("VAL_east_final_resolved")
        self.assertEqual(self.resolve(world), [])
        world.global_flags.discard("VAL_east_final_resolved")
        world.data[rival]["exists"] = False
        self.assertEqual(self.resolve(world), ["VAL_east_resolve_val_victory"])

    def test_rival_selection_follows_the_khans_fate(self):
        triggers = ReckoningWorld()
        for phase, mon_free, rival in ((3, False, "khan"), (3, True, "khan"), (4, True, "montar"),
                                       (5, True, "montar"), (None, True, "montar"), (4, False, None)):
            with self.subTest(phase=phase, mon_free=mon_free):
                world = ReckoningWorld()
                if phase is not None:
                    world.data["RUS"]["vars"]["RUS_crisis_phase"] = phase
                if phase in (4, 5):
                    world.data["RUS"]["exists"] = False
                world.data["MON"]["subject"] = None if mon_free else "RUS"
                khan = world.matches(world.triggers["VAL_east_khan_victorious"])
                montar = world.matches(world.triggers["VAL_east_montar_available"])
                self.assertEqual(khan, rival == "khan")
                self.assertEqual(world.matches(world.triggers["VAL_east_rival_exists"]), rival is not None)
                if rival == "montar":
                    self.assertTrue(montar)
                self.assertTrue(world.matches(world.triggers["VAL_east_khan_question_closed"]))
        running = ReckoningWorld()
        running.data["RUS"]["vars"]["RUS_crisis_phase"] = 2
        self.assertFalse(running.matches(triggers.triggers["VAL_east_khan_question_closed"]))

    def test_capitulation_hooks_settle_after_the_khans_own_dissolution(self):
        text = (ROOT / PEACE).read_text(encoding="utf-8")
        capitulation = text[text.index("# BEGIN east_final:on_capitulation"):text.index("# END east_final:on_capitulation")]
        self.assertLess(text.index("# END west_final:on_capitulation"), text.index("# BEGIN east_final:on_capitulation"))
        self.assertLess(text.index("RUS_crisis_record_capitulation = yes"), text.index("# BEGIN east_final:on_capitulation"))
        self.assertIn("VAL_east_resolve_rival_victory = yes", capitulation)
        self.assertIn("VAL_east_resolve_val_victory = yes", capitulation)
        self.assertIn("VAL_east_record_khan_defeat = yes", capitulation)
        khan = capitulation[capitulation.index("tag = RUS"):capitulation.index("VAL_east_record_khan_defeat")]
        self.assertNotIn("skip_default_capitulation", khan)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            section = text[text.index(f"# BEGIN east_final:{hook}"):text.index(f"# END east_final:{hook}")]
            self.assertIn("VAL_east_final_close_external = yes", section)

    def test_every_terminal_path_closes_campaign_state(self):
        effects = {e.key: e.value for e in entries(EFFECTS)}
        for name in ("VAL_east_resolve_val_victory", "VAL_east_record_khan_defeat",
                     "VAL_east_resolve_rival_victory", "VAL_east_resolve_without_hegemon"):
            with self.subTest(name=name):
                calls = {e.key for e in walk(effects[name])}
                self.assertIn("VAL_east_close_campaign", calls)
                self.assertIn("VAL_east_end_wars", calls)
                self.assertIn("set_global_flag", calls)
        close = {e.key for e in walk(effects["VAL_east_close_campaign"])}
        self.assertIn("remove_mission", close)
        self.assertIn("remove_dynamic_modifier", close)
        self.assertIn("VAL_east_close_champion", close)
        champion = effects["VAL_east_close_champion"]
        self.assertIn("RUS_crisis_release_other_major", {e.key for e in walk(champion)})
        majors = block(entries("common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt"),
                       "RUS_crisis_other_major_required")
        self.assertIn("VAL_east_added_major", {e.value for e in walk(majors) if e.key == "has_country_flag"})

    def test_settlement_terms_follow_the_regimes_casus(self):
        settlement = block(entries(EFFECTS), "VAL_east_apply_settlement")
        text = "\n".join(str(e) for e in walk(settlement))
        self.assertIn("annex_country", text)
        self.assertIn("puppet", text)
        casus = {}
        for name in CASUS:
            reward = block(tree_focuses()[name], "completion_reward")
            casus[name] = int(scalar(block(block(reward, "hidden_effect"), "set_variable"), "value"))
        self.assertEqual(sorted(casus.values()), [1, 2, 3, 4])
        self.assertEqual(casus["VAL_captains_last_buyer"], 4)


class KhanVictoryTests(unittest.TestCase):
    def test_ai_khan_keeps_the_northern_crowns_as_vassals(self):
        effect = block(entries("common/scripted_effects/ADISCORD_RUS_scripted_effects.txt"), "RUS_crisis_annex_hegemony")
        loops = [e.value for e in effect if e.key == "for_each_scope_loop"]
        record, settle = loops[0], loops[1]
        guard = block(record, "if")
        self.assertEqual(scalar(block(guard, "limit"), "RUS_crisis_keeps_as_vassal"), "no")
        branches = [e for e in settle if e.key in ("if", "else")]
        vassal = next(e.value for e in branches if e.key == "if"
                      and any(c.key == "RUS_crisis_keeps_as_vassal" and c.value == "yes"
                              for c in block(e.value, "limit")))
        self.assertTrue([e for e in walk(vassal) if e.key == "puppet"])
        annex = next(e.value for e in branches if e.key == "else")
        self.assertTrue([e for e in walk(annex) if e.key == "annex_country"])
        world = ReckoningWorld()
        trigger = world.triggers.get("RUS_crisis_keeps_as_vassal") or block(
            entries("common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt"), "RUS_crisis_keeps_as_vassal")
        for tag, ai, expected in (("MON", True, True), ("RIN", True, True), ("VLD", True, True),
                                  ("TMR", True, False), ("MON", False, False)):
            with self.subTest(tag=tag, ai=ai):
                world.data["RUS"]["ai"] = ai
                self.assertEqual(world.matches(trigger, tag), expected)

    def test_the_ai_khan_never_reaches_the_orbital_strike(self):
        end = block(entries("common/scripted_effects/ADISCORD_RUS_scripted_effects.txt"), "RUS_crisis_end_world")
        self.assertEqual(scalar(block(block(end, "if"), "limit"), "is_ai"), "no")


class ReckoningTreeTests(unittest.TestCase):
    def test_regime_branches_stack_on_one_area_and_never_share_a_place_within_a_branch(self):
        places = {}
        for name, focus in tree_focuses().items():
            gate = block(focus, "allow_branch") if any(e.key == "allow_branch" for e in focus) else []
            key = tuple(sorted(e.key for e in gate))
            place = (scalar(focus, "x"), scalar(focus, "y"))
            self.assertNotIn((key, place), places, (name, places.get((key, place))))
            places[(key, place)] = name
        for regime, root in REGIMES.items():
            gate = block(tree_focuses()[root], "allow_branch")
            self.assertEqual(len(gate), 1, root)

    def test_every_regime_reaches_its_casus_and_the_last_war(self):
        focuses = tree_focuses()
        question = [e.value for e in focuses["VAL_east_question"] if e.key == "prerequisite"]
        self.assertEqual([{p.value for p in group} for group in question], [set(CASUS)])
        self.assertEqual(scalar(block(block(focuses["VAL_east_question"], "available"), "custom_trigger_tooltip"),
                                "VAL_east_khan_question_closed"), "yes")
        steel = [e.value for e in focuses["VAL_nw_steel_peace"] if e.key == "prerequisite"]
        self.assertEqual([[p.value for p in group] for group in steel], [["VAL_east_final"]])
        for regime, root in REGIMES.items():
            gate = scalar(block(focuses[root], "allow_branch"), next(e.key for e in block(focuses[root], "allow_branch")))
            branch = {name for name, focus in focuses.items() if any(e.key == "allow_branch" for e in focus)
                      and [e.key for e in block(focus, "allow_branch")] == [e.key for e in block(focuses[root], "allow_branch")]}
            with self.subTest(root=root):
                self.assertEqual(gate, "yes")
                self.assertEqual(len(branch & set(CASUS)), 1)
                pairs = [name for name in branch if exclusive_rivals(focuses[name])]
                self.assertGreaterEqual(len(pairs), 2)

    def test_crisis_focuses_bypass_after_the_regime_and_unlocks_are_usable(self):
        focuses = tree_focuses()
        decisions = {e.key: e.value for category in entries(DECISIONS) if isinstance(category.value, list)
                     for e in category.value if isinstance(e.value, list)}
        for name, focus in focuses.items():
            for unlock in (e.value for e in walk(block(focus, "completion_reward")) if e.key == "unlock_decision_tooltip"):
                if unlock.startswith(("VAL_peace_", "VAL_throne_", "VAL_cabinet_", "VAL_east_")):
                    with self.subTest(focus=name, decision=unlock):
                        self.assertIn(unlock, decisions)
                        visible = {e.value for e in walk(block(decisions[unlock], "visible")) if isinstance(e.value, str)}
                        self.assertIn(name, visible)
        crisis = ("VAL_peace_two_bills", "VAL_peace_land_for_service", "VAL_peace_workers_charter",
                  "VAL_peace_shift_law", "VAL_peace_archive", "VAL_peace_night_of_registers",
                  "VAL_peace_ash_shifts", "VAL_peace_water_convoys", "VAL_peace_gate_garrison",
                  "VAL_peace_tishin_list", "VAL_peace_captains_bill", "VAL_peace_registry_audit",
                  "VAL_peace_share_ledger", "VAL_peace_kilnet")
        for name in crisis:
            self.assertEqual(scalar(block(focuses[name], "bypass"), "VAL_peace_regime_chosen"), "yes", name)

    def test_events_are_registered_localised_and_fit_the_text_buffer(self):
        text = (ROOT / EVENTS).read_text(encoding="utf-8")
        ids = sorted(set(re.findall(r"^\tid = (val_peace\.\d+)$", text, re.M)), key=lambda i: int(i.split(".")[1]))
        registry = {e["id"] for e in json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))["events"]}
        self.assertLessEqual(set(ids), registry)
        languages = {}
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            rows = {}
            for line in raw.decode("utf-8-sig").splitlines():
                match = re.fullmatch(r' ([\w.]+):\d+ "(.*)"', line)
                if match:
                    rows[match[1]] = match[2]
            languages[language] = rows
        for event_id in ids:
            event = country_event(event_id)
            if scalar(event, "hidden") == "yes" if any(e.key == "hidden" for e in event) else False:
                continue
            keys = {e.value for e in walk(event) if e.key in ("title", "text", "name")}
            keys |= {e.value for e in event if e.key == "desc" and isinstance(e.value, str)}
            for key in keys:
                for language, rows in languages.items():
                    with self.subTest(key=key, language=language):
                        self.assertIn(key, rows)
                        rendered = rows[key].replace(r"\n", "\n")
                        self.assertLessEqual(len(rendered), 3000)
                        self.assertLessEqual(len(rendered.encode("utf-8")), 5500)
                        self.assertNotRegex(rows[key], "[–—«»]")
        for name in tree_focuses():
            for language, rows in languages.items():
                self.assertIn(name, rows, (language, name))
                self.assertIn(name + "_desc", rows, (language, name))

    def test_payroll_costs_are_debited_once_and_have_all_variants(self):
        rows = {}
        for line in (ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml").read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r" ([\w.]+):\d+ ", line)
            if match:
                rows[match[1]] = line
        for category in ("VAL_peace_payroll_category", "VAL_peace_order_category", "VAL_east_war_category"):
            for decision in block(entries(DECISIONS), category):
                with self.subTest(decision=decision.key):
                    self.assertIn(decision.key, rows)
                    costs = [e.value for e in decision.value if e.key == "custom_cost_text"]
                    for key in costs:
                        self.assertEqual(scalar(decision.value, "cost"), "0")
                        for suffix in ("", "_blocked", "_tooltip"):
                            self.assertIn(key + suffix, rows)
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text(encoding="utf-8").split()
        self.assertIn("VAL_peace_reckoning", tokens)
        self.assertIn("VAL_east_deadline", tokens)


if __name__ == "__main__":
    unittest.main()
