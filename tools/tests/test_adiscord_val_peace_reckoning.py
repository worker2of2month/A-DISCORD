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
RUS_TRIGGERS = "common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt"
REPUBLICS = ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA", "TMR", "VEL", "RLY")
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
            self.triggers.update({e.key: e.value for e in entries(RUS_TRIGGERS)})
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
        self.stack = []
        self.joined = []

    def number(self, value, scope):
        if value in self.temps:
            return self.temps[value]
        if value.startswith("global."):
            return self.globals.get(value.removeprefix("global."), 0)
        return super().number(value, scope)

    def resolve(self, value, scope):
        if value == "PREV":
            return self.stack[-1]
        if value == "ROOT":
            return "VAL"
        if value == "capital_scope":
            return self.data[scope].get("capital", "capital_" + scope)
        return self.scope(value, scope)

    @staticmethod
    def is_scope(key):
        return key not in ("NOT", "AND") and bool(re.fullmatch(r"[A-Z]{3}|\d+|FROM|PREV|capital_scope|event_target:\w+", key))

    def countries(self):
        return [tag for tag in list(self.data) if re.fullmatch(r"[A-Z]{3}", tag) and self.data[tag]["exists"]]

    def enter(self, rows, scope, target, run):
        self.stack.append(scope)
        try:
            return run(rows, target)
        finally:
            self.stack.pop()

    COMPARE = {
        "equals": lambda a, b: a == b,
        "greater_than_or_equals": lambda a, b: a >= b,
        "greater_than": lambda a, b: a > b,
        "less_than": lambda a, b: a < b,
        "less_than_or_equals": lambda a, b: a <= b,
    }

    def matches(self, rows, scope="VAL"):
        plain = []
        index = 0
        while index < len(rows):
            row = rows[index]
            index += 1
            if not row.key and row.value == "has_manpower":
                op, threshold = rows[index].value, float(rows[index + 1].value)
                index += 2
                current = self.data[scope]["manpower"]
                if not (current < threshold if op == "<" else current > threshold):
                    return False
            elif not row.key:
                plain.extend(rows[index - 1:index + 2])
                index += 2
            elif row.key == "is_neighbor_of":
                if row.value not in self.data[scope].get("neighbors", set()):
                    return False
            elif row.key == "free_building_slots":
                if self.data[scope].get("free_slots", 0) <= 0:
                    return False
            elif isinstance(row.value, list) and self.is_scope(row.key):
                if not self.enter(row.value, scope, self.resolve(row.key, scope), self.matches):
                    return False
            elif row.key == "has_global_flag":
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
            elif isinstance(value, list) and self.is_scope(key):
                self.enter(value, scope, self.resolve(key, scope), self.execute)
            elif key in self.intercept:
                self.calls.append((scope, key))
            elif key in ("set_temp_variable", "add_to_temp_variable"):
                name = scalar(value, "var")
                amount = self.number(scalar(value, "value"), scope)
                self.temps[name] = amount if key == "set_temp_variable" else self.temps.get(name, 0) + amount
            elif key == "set_variable" and scalar(value, "var").startswith("global."):
                self.globals[scalar(value, "var").removeprefix("global.")] = self.number(scalar(value, "value"), scope)
            elif key == "clamp_temp_variable":
                name = scalar(value, "var")
                self.temps[name] = max(float(scalar(value, "min")), min(float(scalar(value, "max")), self.temps.get(name, 0)))
            elif key in ("every_subject_country", "every_country"):
                limit = block(value, "limit") if any(e.key == "limit" for e in value) else []
                body = [e for e in value if e.key != "limit"]
                for tag in self.countries():
                    if key == "every_subject_country" and self.data[tag]["subject"] != scope:
                        continue
                    if self.enter(limit, scope, tag, self.matches):
                        self.enter(body, scope, tag, self.execute)
            elif key == "add_to_war":
                ally = self.resolve(scalar(value, "targeted_alliance"), scope)
                enemy = self.resolve(scalar(value, "enemy"), scope)
                self.joined.append((scope, ally, enemy))
                country["wars"].add(enemy)
                self.data[enemy]["wars"].add(scope)
            elif key == "declare_war_on":
                enemy = self.resolve(scalar(value, "target"), scope)
                self.joined.append((scope, scope, enemy))
                country["wars"].add(enemy)
                self.data[enemy]["wars"].add(scope)
            elif key == "create_faction_from_template":
                country.update(faction=scope, leader=True)
                country["faction_name"] = scalar(value, "name")
            elif key == "add_to_faction":
                self.data[self.resolve(value, scope)]["faction"] = country["faction"]
            elif key == "dismantle_faction":
                for tag in self.countries():
                    if self.data[tag]["faction"] == country["faction"] and tag != scope:
                        self.data[tag]["faction"] = None
                country.update(faction=None, leader=False)
            elif key == "puppet":
                self.data[self.resolve(scalar(value, "target"), scope)]["subject"] = scope
            elif key == "give_military_access":
                country.setdefault("access", set()).add(self.resolve(value, scope))
            elif key in ("add_stability", "add_war_support"):
                country[key] = country.get(key, 0) + float(value)
            elif key in ("ADISCORD_economy_initialize_country", "set_major"):
                pass
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


def contest_world(focuses=()):
    """A cabinet Kefreyt facing an AI Montar Empire before the contest begins."""
    world = ReckoningWorld()
    world.data["VAL"]["vars"]["VAL_peace_regime"] = 2
    world.data["VAL"]["focuses"].update(focuses)
    return world


def started(world, **leans):
    world.run("VAL_east_contest_begin")
    for tag, lean in leans.items():
        world.data[tag]["vars"]["VAL_east_lean"] = lean
    world.events.clear()
    return world


def rival_faction(world, *members):
    world.data["MON"].update(faction="MON", leader=True)
    for tag in members:
        world.data[tag]["faction"] = "MON"


def lean(world, tag):
    return world.data[tag]["vars"].get("VAL_east_lean")


def contest_decisions():
    return {e.key: e.value for e in block(entries(DECISIONS), "VAL_east_contest_category")}


def ai_weight(world, option, scope="VAL"):
    chance = block(option, "ai_chance")
    total = float(scalar(chance, "factor"))
    for modifier in (e.value for e in chance if e.key == "modifier"):
        if world.matches([e for e in modifier if e.key != "factor"], scope):
            total *= float(scalar(modifier, "factor"))
    return total


def options(event_id):
    return {scalar(e.value, "name"): e.value for e in country_event(event_id) if e.key == "option"}


class EastContestTests(unittest.TestCase):
    TOOLS = {
        "VAL_throne_crown_march": ("VAL_throne_crown_marches", "VAL_throne_offer_crown_march",
                                   "VAL_throne_accept_crown_march", "val_peace.97"),
        "VAL_cabinet_treaty_membership": ("VAL_cabinet_eastern_mission", "VAL_cabinet_offer_treaty_membership",
                                          "VAL_cabinet_accept_treaty_membership", "val_peace.98"),
        "VAL_charter_garrison_treaty": ("VAL_charter_garrison_contracts", "VAL_charter_offer_garrison_treaty",
                                        "VAL_charter_accept_garrison_treaty", "val_peace.99"),
        "VAL_captains_hire_companies": ("VAL_captains_company_markets", "VAL_captains_offer_hire_companies",
                                        "VAL_captains_accept_hire_companies", "val_peace.100"),
    }

    def test_begin_seeds_lean_with_focuses_completed_before_the_contest(self):
        world = contest_world(("VAL_east_trade_missions", "VAL_cabinet_eastern_mission",
                               "VAL_east_krutov_network", "VAL_east_shards"))
        world.temps["VAL_east_lean_delta"] = 5
        world.run("VAL_east_contest_shift_all")
        self.assertIsNone(lean(world, "SLA"))
        world.data["SLA"]["flags"].update({"VAL_nw_concession", "VAL_nw_sovereignty_recognized"})
        rival_faction(world, "RZA")
        world.data["MLR"]["neighbors"] = {"MON"}
        world.data["IRT"]["subject"] = "VAL"
        world.run("VAL_east_contest_begin")
        world.run("VAL_east_contest_begin")
        self.assertEqual(lean(world, "SLA"), 100)
        self.assertEqual(lean(world, "RZA"), 45)
        self.assertEqual(lean(world, "MLR"), 50)
        self.assertEqual(lean(world, "ERT"), 60)
        self.assertIsNone(lean(world, "IRT"))
        self.assertEqual(world.targets["VAL_east_rival"], "MON")
        self.assertEqual(world.globals["VAL_east_rival_kind"], 1)
        self.assertIn("VAL_east_contest_deadline", world.data["VAL"]["missions"])
        self.assertEqual(world.events, [("VAL", "val_peace.89")])
        plain = contest_world()
        started(plain)
        self.assertEqual(lean(plain, "ERT"), 50)

    def test_shift_effects_follow_their_roster_and_clamp(self):
        world = started(contest_world(), SLA=98, RZA=50, MLR=50)
        rival_faction(world, "RZA")
        world.data["MLR"]["flags"].add("VAL_nw_concession")
        world.temps["VAL_east_lean_delta"] = 5
        world.run("VAL_east_contest_shift_rival_members")
        world.run("VAL_east_contest_shift_partners")
        world.run("VAL_east_contest_shift_all")
        self.assertEqual((lean(world, "SLA"), lean(world, "RZA"), lean(world, "MLR"), lean(world, "ERT")),
                         (100, 60, 60, 55))

    def test_monthly_clock_starts_the_contest_or_settles_an_empty_east(self):
        world = contest_world()
        for _ in range(3):
            world.run("VAL_east_contest_monthly")
        self.assertNotIn("VAL_east_contest_started", world.global_flags)
        self.assertEqual(world.data["VAL"]["vars"]["VAL_east_contest_wait"], 3)
        world.run("VAL_east_contest_monthly")
        self.assertIn("VAL_east_contest_started", world.global_flags)
        self.assertNotIn("VAL_east_contest_wait", world.data["VAL"]["vars"])
        self.assertEqual(lean(world, "SLA"), 50)
        empty = contest_world()
        empty.data["MON"]["subject"] = "RUS"
        for _ in range(4):
            empty.run("VAL_east_contest_monthly")
        self.assertNotIn("VAL_east_contest_started", empty.global_flags)
        self.assertTrue({"VAL_east_final_resolved", "VAL_east_hegemon_VAL"} <= empty.global_flags)
        self.assertEqual(empty.events, [("VAL", "val_peace.88")])

    def test_monthly_pressure_reads_factions_counterpressure_flags_and_floor(self):
        for krutov, expected in ((False, (45, 42, 50, 48, 0)), (True, (47, 44, 50, 50, 0))):
            with self.subTest(krutov=krutov):
                world = started(contest_world(("VAL_east_krutov_network",) if krutov else ()),
                                SLA=50, RZA=50, MLR=50, ERT=50, TMR=3)
                rival_faction(world, "RZA")
                world.data["MLR"]["flags"].add("VAL_east_agents_exposed")
                world.data["ERT"]["flags"].add("VAL_east_garrisoned")
                world.run("VAL_east_contest_monthly")
                self.assertEqual(tuple(lean(world, t) for t in ("SLA", "RZA", "MLR", "ERT", "TMR")), expected)
        released = started(contest_world())
        released.data["IRT"]["subject"] = None
        released.data["IRT"]["vars"].pop("VAL_east_lean", None)
        released.run("VAL_east_contest_monthly")
        self.assertEqual(lean(released, "IRT"), 45)

    def test_camp_offers_are_guarded_and_answers_follow_the_spec(self):
        world = started(contest_world(), RZA=80, MLR=30)
        rival_faction(world, "RZA")
        world.run("VAL_east_contest_monthly")
        self.assertEqual(lean(world, "RZA"), 72)
        self.assertEqual(sorted(world.events), [("MLR", "val_peace.92"), ("RZA", "val_peace.90")])
        world.events.clear()
        world.data["RZA"]["vars"]["VAL_east_lean"] = 90
        world.run("VAL_east_contest_monthly")
        self.assertEqual(world.events, [])
        world.run("VAL_east_contest_refuse_leave", "RZA")
        self.assertEqual(lean(world, "RZA"), 60)
        self.assertIn("VAL_east_offer_cooldown", world.data["RZA"]["flags"])
        self.assertEqual(world.data["RZA"]["faction"], "MON")
        world.run("VAL_east_contest_accept_join", "MLR")
        self.assertEqual(world.data["MLR"]["faction"], "MON")
        self.assertEqual(world.events, [("VAL", "val_peace.91"), ("VAL", "val_peace.93")])
        world.run("VAL_east_contest_accept_join", "MLR")
        self.assertEqual(len(world.events), 2)

        leave = started(contest_world(("VAL_east_shards",)), RZA=70)
        rival_faction(leave, "RZA")
        leave.run("VAL_east_contest_monthly")
        self.assertEqual(leave.events, [("RZA", "val_peace.90")])
        leave.run("VAL_east_contest_accept_leave", "RZA")
        self.assertIsNone(leave.data["RZA"]["faction"])
        # Without a rival faction nothing invites a republic in the rival's camp.
        lone = started(contest_world(), MLR=20)
        lone.run("VAL_east_contest_monthly")
        self.assertEqual(lone.events, [])
        for event_id, refuse, accept in (("val_peace.90", "VAL_east_contest_refuse_leave", "VAL_east_contest_accept_leave"),
                                         ("val_peace.92", "VAL_east_contest_refuse_join", "VAL_east_contest_accept_join")):
            answers = options(event_id)
            self.assertEqual(scalar(block(answers[event_id + ".a"], "hidden_effect"), refuse), "yes")
            self.assertEqual(scalar(block(answers[event_id + ".b"], "hidden_effect"), accept), "yes")

    def test_binding_reads_camps_and_clears_the_contest(self):
        for shards in (False, True):
            with self.subTest(shards=shards):
                world = started(contest_world(("VAL_east_shards",) if shards else ()),
                                SLA=80, RZA=80, MLR=20, ERT=65, SCA=50)
                rival_faction(world, "RZA")
                world.data["SCA"]["flags"].add("VAL_nw_concession")
                world.data["IRT"]["subject"] = "VAL"
                world.data["VAL"]["vars"]["VAL_east_side"] = 1
                world.data["MON"]["vars"]["VAL_east_side"] = 2
                world.data["SLA"]["flags"].add("VAL_east_garrisoned")
                world.run("VAL_east_bind_sides")
                sides = {t: world.data[t]["vars"].get("VAL_east_side") for t in REPUBLICS}
                self.assertEqual(sides, {"SLA": 1, "RZA": 2, "MLR": 2, "ERT": 1 if shards else None, "IRT": 1,
                                         "SCA": None, "TMR": None, "VEL": None, "RLY": None})
                self.assertIn(("SLA", "VAL", "MON"), world.joined)
                self.assertIn(("MLR", "MON", "VAL"), world.joined)
                self.assertIn(("RZA", "MON", "VAL"), world.joined)
                self.assertFalse([t for t in REPUBLICS if lean(world, t) is not None])
                self.assertNotIn("VAL_east_contest_deadline", world.data["VAL"]["missions"])
                self.assertNotIn("VAL_east_garrisoned", world.data["SLA"]["flags"])
                self.assertIn("VAL_east_contest_closed", world.global_flags)

    def test_the_rival_can_declare_the_last_war_without_a_casus(self):
        world = started(contest_world(), SLA=80)
        world.intercept = {"VAL_east_prepare_champion"}
        world.data["VAL"]["wars"].add("MON")
        world.run("VAL_east_final_start_by_rival")
        self.assertNotIn("VAL_east_final_started", world.global_flags)
        world.data["VAL"]["wars"].clear()
        world.data["MON"]["wars"].clear()
        world.run("VAL_east_final_start_by_rival")
        world.run("VAL_east_final_start_by_rival")
        self.assertEqual([j for j in world.joined if j[0] == "MON"], [("MON", "MON", "VAL")])
        self.assertTrue({"VAL_east_final_started", "VAL_east_rival_declared", "VAL_east_contest_closed"}
                        <= world.global_flags)
        self.assertEqual(world.data["SLA"]["vars"]["VAL_east_side"], 1)
        self.assertEqual(world.data["MON"]["vars"]["VAL_east_side"], 2)
        self.assertEqual(world.data["VAL"]["missions"], {"VAL_east_deadline"})
        self.assertEqual(world.events, [("VAL", "val_peace.81"), ("news", "val_peace.82"), ("MON", "val_peace.83")])
        spirit = {k: v for k, v in world.data["VAL"]["vars"].items() if k.startswith("VAL_east_war_")}
        self.assertEqual(set(spirit.values()), {0})
        world.intercept = set()
        world.run("VAL_east_close_campaign")
        self.assertNotIn("VAL_east_rival_declared", world.global_flags)
        for event_id in ("val_peace.81", "val_peace.82", "val_peace.83"):
            texts = [scalar(e.value, "text") for e in country_event(event_id) if e.key == "desc"]
            self.assertTrue([t for t in texts if ".rival" in t], event_id)

    def test_every_terminal_path_closes_the_contest(self):
        def assert_closed(world, keep_leans=False):
            self.assertIn("VAL_east_contest_closed", world.global_flags)
            self.assertNotIn("VAL_east_contest_deadline", world.data["VAL"]["missions"])
            for tag in REPUBLICS:
                self.assertFalse({f for f in world.data[tag]["flags"] if f.startswith("VAL_east_")}, tag)
            if not keep_leans:
                self.assertFalse([t for t in REPUBLICS if lean(world, t) is not None])

        def prepared(**leans):
            world = started(contest_world(), **leans)
            for flag in ("VAL_east_offer_pending", "VAL_east_tool_cooldown", "VAL_east_agents_exposed"):
                world.data["SLA"]["flags"].add(flag)
            return world

        conceded = prepared(SLA=80, RZA=20, MLR=50)
        rival_faction(conceded)
        conceded.data["MLR"]["ai"] = False
        conceded.run("VAL_east_contest_concede")
        assert_closed(conceded)
        self.assertEqual((conceded.data["RZA"]["faction"], conceded.data["MLR"]["faction"],
                          conceded.data["SLA"]["faction"]), ("MON", None, None))
        self.assertAlmostEqual(conceded.data["VAL"]["add_stability"], -0.10)
        self.assertAlmostEqual(conceded.data["VAL"]["add_war_support"], -0.10)
        self.assertTrue({"VAL_east_final_resolved", "VAL_east_stalemate"} <= conceded.global_flags)
        self.assertEqual(conceded.events, [])

        retreat = prepared(SLA=80, ERT=50, MLR=20)
        retreat.run("VAL_east_contest_rival_backs_down", "MON")
        assert_closed(retreat, keep_leans=True)
        self.assertEqual((lean(retreat, "SLA"), lean(retreat, "ERT"), lean(retreat, "MLR")), (80, 70, 20))
        self.assertEqual(retreat.events, [("VAL", "val_peace.96")])
        retreat.data["VAL"]["vars"]["VAL_east_side"] = 1
        retreat.data["MON"]["vars"]["VAL_east_side"] = 2
        retreat.run("VAL_east_bind_sides")
        self.assertEqual(retreat.data["ERT"]["vars"]["VAL_east_side"], 1)
        self.assertIsNone(lean(retreat, "ERT"))

        vanished = prepared(SLA=80)
        vanished.data["MON"]["exists"] = False
        vanished.run("VAL_east_contest_monthly")
        assert_closed(vanished)
        self.assertIn("VAL_east_hegemon_VAL", vanished.global_flags)
        self.assertEqual(vanished.events, [("VAL", "val_peace.88")])

        subjugated = prepared(SLA=80)
        subjugated.data["VAL"]["subject"] = "MON"
        subjugated.run("VAL_east_final_close_external")
        assert_closed(subjugated)
        self.assertNotIn("VAL_east_final_resolved", subjugated.global_flags)

        effects = {e.key: e.value for e in entries(EFFECTS)}
        for name in ("VAL_east_bind_sides", "VAL_east_close_campaign", "VAL_east_settle_uncontested",
                     "VAL_east_contest_concede", "VAL_east_contest_reconcile"):
            self.assertIn("VAL_east_contest_close", {e.key for e in walk(effects[name])}, name)
        self.assertIn("VAL_east_contest_reconcile", {e.key for e in effects["VAL_east_final_close_external"]})
        monthly = (ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt").read_text(encoding="utf-8")
        self.assertIn("VAL_east_contest_monthly = yes", monthly[monthly.index("on_monthly_VAL"):])

    def test_arms_credit_pays_once_at_the_exact_price(self):
        world = started(contest_world(), SLA=50)
        world.target = "SLA"
        world.data["VAL"]["rifles"] = {"VAL": 2699.5}
        world.run("VAL_east_contest_grant_arms_credit")
        self.assertEqual(lean(world, "SLA"), 50)
        world.data["VAL"]["rifles"] = {"VAL": 5400}
        world.data["VAL"]["pp"] = 25
        world.run("VAL_east_contest_grant_arms_credit")
        world.data["VAL"]["pp"] = 100
        world.run("VAL_east_contest_grant_arms_credit")
        self.assertEqual(world.data["VAL"]["rifles"]["VAL"], 2700)
        self.assertEqual(world.data["VAL"]["pp"], 100)
        self.assertEqual(world.data["SLA"]["rifles"]["VAL"], 7700)
        self.assertEqual(lean(world, "SLA"), 65)
        self.assertIn("VAL_east_credit_cooldown", world.data["SLA"]["flags"])

    def test_share_and_instructors_debit_once_and_refund_exactly(self):
        decisions = contest_decisions()
        for slot in (1, 0):
            with self.subTest(slot=slot):
                world = started(contest_world(), SLA=50)
                world.target = "SLA"
                country = world.data["VAL"]
                country["vars"]["ADISCORD_economy_treasury"] = 149.99
                country["pp"] = 25
                world.run("VAL_east_contest_share_begin")
                self.assertNotIn("VAL_east_share_deposit", world.data["SLA"]["vars"])
                country["vars"]["ADISCORD_economy_treasury"] = 150
                world.run("VAL_east_contest_share_begin")
                country["vars"]["ADISCORD_economy_treasury"] = 300
                country["pp"] = 50
                world.run("VAL_east_contest_share_begin")
                self.assertEqual((country["vars"]["ADISCORD_economy_treasury"], country["pp"]), (300, 50))
                self.assertEqual(country["vars"]["ADISCORD_economy_current_month_action_costs"], 150)
                world.data["SLA"]["capital"] = "500"
                world.data["500"]["free_slots"] = slot
                world.run("VAL_east_contest_share_finish")
                world.run("VAL_east_contest_share_finish")
                self.assertEqual(world.data["500"]["buildings"]["industrial_complex"], slot)
                self.assertEqual(world.data["SLA"]["vars"].get("ADISCORD_economy_treasury", 0), 150 * (1 - slot))
                self.assertEqual(lean(world, "SLA"), 70)
                self.assertEqual((country["vars"]["ADISCORD_economy_treasury"], country["pp"]), (300, 50))

        lost = started(contest_world(), SLA=50)
        lost.target = "SLA"
        lost.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = 150
        lost.data["VAL"]["pp"] = 25
        lost.run("VAL_east_contest_share_begin")
        lost.data["SLA"]["subject"] = "MON"
        lost.execute(block(decisions["VAL_east_contest_share"], "cancel_effect"))
        lost.run("VAL_east_contest_share_finish")
        lost.run("VAL_east_contest_share_refund")
        self.assertEqual((lost.data["VAL"]["vars"]["ADISCORD_economy_treasury"], lost.data["VAL"]["pp"]), (150, 25))
        self.assertEqual(lost.data["VAL"]["vars"]["ADISCORD_economy_current_month_action_income"], 150)

        drill = started(contest_world(), SLA=50)
        drill.target = "SLA"
        drill.data["VAL"].update(pp=50, manpower=999.5)
        drill.run("VAL_east_contest_instructors_begin")
        self.assertEqual(drill.data["VAL"]["manpower"], 999.5)
        drill.data["VAL"]["manpower"] = 1000
        drill.run("VAL_east_contest_instructors_begin")
        drill.data["VAL"].update(pp=50, manpower=1000)
        drill.run("VAL_east_contest_instructors_begin")
        self.assertEqual((drill.data["VAL"]["pp"], drill.data["VAL"]["manpower"]), (50, 1000))
        drill.run("VAL_east_contest_instructors_finish")
        drill.run("VAL_east_contest_instructors_finish")
        self.assertEqual(drill.data["SLA"]["army_experience"], 10)
        self.assertEqual(lean(drill, "SLA"), 60)
        self.assertEqual((drill.data["VAL"]["pp"], drill.data["VAL"]["manpower"]), (50, 1000))
        drill.data["VAL"].update(pp=50, manpower=1000)
        drill.run("VAL_east_contest_instructors_begin")
        drill.data["SLA"]["wars"].add("VAL")
        drill.execute(block(decisions["VAL_east_contest_instructors"], "cancel_effect"))
        drill.run("VAL_east_contest_instructors_refund")
        self.assertEqual((drill.data["VAL"]["pp"], drill.data["VAL"]["manpower"]), (50, 1000))

    def test_exposure_targets_the_rival_faction_and_refunds_a_lost_target(self):
        world = started(contest_world(), RZA=50)
        rival_faction(world, "RZA")
        world.target = "RZA"
        world.run("VAL_east_contest_expose_begin")
        world.run("VAL_east_contest_expose_finish")
        self.assertEqual(lean(world, "RZA"), 65)
        self.assertIn("VAL_east_agents_exposed", world.data["RZA"]["flags"])
        world.target = "SLA"
        world.run("VAL_east_contest_expose_begin")
        world.data["SLA"]["subject"] = "MON"
        world.run("VAL_east_contest_expose_finish")
        world.run("VAL_east_contest_expose_refund")
        self.assertEqual(world.data["VAL"]["pp"], 1050)
        self.assertEqual(scalar(contest_decisions()["VAL_east_contest_expose_agents"], "cost"), "50")

    def test_regime_tools_pay_only_after_consent(self):
        def tool_world(**values):
            world = started(contest_world(), SLA=values.pop("lean"))
            world.target = "SLA"
            country = world.data["VAL"]
            country.update(pp=values.pop("pp", 0), manpower=values.pop("manpower", 0))
            country["rifles"] = {"VAL": values.pop("rifles", 0)}
            country["vars"]["ADISCORD_economy_treasury"] = values.pop("treasury", 0)
            world.data["SLA"].update(manpower=values.pop("republic_manpower", 0), rifles={})
            return world

        setups = {
            "VAL_throne_crown_march": dict(lean=80, pp=100, rifles=5400),
            "VAL_cabinet_treaty_membership": dict(lean=60, pp=75, treasury=100),
            "VAL_charter_garrison_treaty": dict(lean=50, pp=50, manpower=3000),
            "VAL_captains_hire_companies": dict(lean=50, treasury=150, republic_manpower=3000),
        }
        decisions = contest_decisions()
        for name, (focus, offer, accept, event_id) in self.TOOLS.items():
            with self.subTest(tool=name):
                self.assertIn(focus, {e.value for e in walk(block(decisions[name], "visible")) if isinstance(e.value, str)})
                self.assertEqual(scalar(block(block(decisions[name], "complete_effect"), "hidden_effect"), offer), "yes")
                answers = options(event_id)
                self.assertEqual(scalar(block(answers[event_id + ".b"], "hidden_effect"), accept), "yes")
                self.assertEqual(scalar(block(answers[event_id + ".a"], "hidden_effect"), "VAL_east_decline_tool"), "yes")

                world = tool_world(**dict(setups[name]))
                before = (world.data["VAL"]["pp"], world.data["VAL"]["manpower"],
                          dict(world.data["VAL"]["rifles"]), world.data["VAL"]["vars"]["ADISCORD_economy_treasury"])
                world.run(offer)
                self.assertEqual(world.events, [("SLA", event_id)])
                self.assertIn("VAL_east_tool_pending", world.data["SLA"]["flags"])
                after = (world.data["VAL"]["pp"], world.data["VAL"]["manpower"],
                         dict(world.data["VAL"]["rifles"]), world.data["VAL"]["vars"]["ADISCORD_economy_treasury"])
                self.assertEqual(before, after)
                world.run("VAL_east_decline_tool", "SLA")
                world.run(offer)
                self.assertEqual(world.events, [("SLA", event_id), ("VAL", "val_peace.101")])
                self.assertIn("VAL_east_tool_cooldown", world.data["SLA"]["flags"])

                broke = tool_world(**dict(setups[name]))
                broke.run(offer)
                broke.data["VAL"].update(pp=0, manpower=0, rifles={})
                broke.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = 0
                broke.run(accept, "SLA")
                self.assertIn("VAL_east_tool_cooldown", broke.data["SLA"]["flags"])
                self.assertIsNone(broke.data["SLA"]["subject"])

                paid = tool_world(**dict(setups[name]))
                paid.run(offer)
                paid.run(accept, "SLA")
                paid.run(accept, "SLA")
                self.assertEqual(paid.events[-1], ("VAL", "val_peace.101"))
                self.assertNotIn("VAL_east_tool_cooldown", paid.data["SLA"]["flags"])
                val, sla = paid.data["VAL"], paid.data["SLA"]
                self.assertEqual(val["pp"], 0)
                if name == "VAL_throne_crown_march":
                    self.assertEqual(sla["subject"], "VAL")
                    self.assertEqual((sum(val["rifles"].values()), sla["rifles"]["VAL"]), (0, 5400))
                elif name == "VAL_cabinet_treaty_membership":
                    self.assertEqual((val["faction"], val["leader"], sla["faction"]), ("VAL", True, "VAL"))
                    self.assertEqual(val["faction_name"], "VAL_east_defence_treaty")
                    self.assertEqual(val["vars"]["ADISCORD_economy_treasury"], 0)
                elif name == "VAL_charter_garrison_treaty":
                    self.assertEqual((val["manpower"], sla["access"], lean(paid, "SLA")), (0, {"VAL"}, 70))
                    self.assertIn("VAL_east_garrisoned", sla["flags"])
                else:
                    self.assertEqual((val["manpower"], sla["manpower"]), (3000, 0))
                    self.assertEqual((val["vars"]["ADISCORD_economy_treasury"], sla["vars"]["ADISCORD_economy_treasury"]),
                                     (0, 150))
                    self.assertEqual(lean(paid, "SLA"), 65)

    def test_deadline_sends_the_ultimatum_and_the_ai_compares_camps(self):
        category = contest_decisions()
        mission = category["VAL_east_contest_deadline"]
        self.assertEqual(scalar(mission, "days_mission_timeout"), "360")
        self.assertEqual(scalar(block(block(mission, "available"), "hidden_trigger"), "always"), "no")
        self.assertEqual(scalar(block(block(mission, "timeout_effect"), "hidden_effect"), "VAL_east_contest_ultimatum"), "yes")
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text(encoding="utf-8").split()
        self.assertIn("VAL_east_contest_deadline", tokens)

        human = started(contest_world())
        human.data["MON"]["ai"] = False
        human.run("VAL_east_contest_ultimatum")
        self.assertEqual(human.events, [("MON", "val_peace.95")])
        retreat = options("val_peace.95")
        self.assertEqual(scalar(block(retreat["val_peace.95.a"], "hidden_effect"), "VAL_east_contest_rival_backs_down"), "yes")

        event = country_event("val_peace.94")
        answers = options("val_peace.94")
        for leans, expected in ((dict(SLA=80, MLR=20), "val_peace.94.a"),
                                (dict(SLA=80, MLR=20, TMR=25), "val_peace.94.b"),
                                ({}, "val_peace.94.a")):
            with self.subTest(leans=leans):
                world = started(contest_world(), **leans)
                world.run("VAL_east_contest_ultimatum")
                self.assertEqual(world.events, [("VAL", "val_peace.94")])
                world.execute(block(event, "immediate"))
                weights = {name: ai_weight(world, answers[name]) for name in ("val_peace.94.a", "val_peace.94.b")}
                self.assertEqual([name for name, weight in weights.items() if weight > 0], [expected])
        reject = block(answers["val_peace.94.a"], "hidden_effect")
        self.assertEqual([e.key for e in reject], ["VAL_east_final_start_by_rival", "VAL_east_contest_close"])

    def test_decisions_follow_the_cost_contract_and_their_unlocking_focus(self):
        unlocks = {
            "VAL_east_contest_arms_credit": "VAL_east_question",
            "VAL_east_contest_share": "VAL_east_trade_missions",
            "VAL_east_contest_expose_agents": "VAL_east_krutov_network",
            "VAL_east_contest_instructors": "VAL_east_border_posts",
        }
        unlocks.update({name: focus for name, (focus, *_rest) in self.TOOLS.items()})
        decisions = contest_decisions()
        for name, focus in unlocks.items():
            with self.subTest(decision=name):
                decision = decisions[name]
                self.assertEqual([e.value for e in block(decision, "targets")], list(REPUBLICS))
                self.assertIn(focus, {e.value for e in walk(block(decision, "visible")) if isinstance(e.value, str)})
                available = {e.key for e in walk(block(decision, "available"))}
                self.assertTrue({"VAL_east_contestable", "VAL_east_contest_active"} <= available)
                if any(e.key == "custom_cost_text" for e in decision):
                    self.assertEqual(scalar(decision, "cost"), "0")
                    self.assertTrue(block(decision, "custom_cost_trigger"))
        categories = entries("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        category = block(categories, "VAL_east_contest_category")
        self.assertEqual(scalar(category, "visible_when_empty"), "yes")
        self.assertIn("VAL_east_contest_active", {e.key for e in walk(block(category, "visible"))})

    def test_contest_localisation_has_every_referenced_key(self):
        rows = {}
        for line in (ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml").read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r" ([\w.]+):\d+ ", line)
            if match:
                rows[match[1]] = line
        keys = {"VAL_east_contest_category", "VAL_east_contest_category_desc", "VAL_east_defence_treaty"}
        for name, decision in contest_decisions().items():
            keys |= {name, name + "_desc"}
            keys |= {e.value for e in walk(decision) if e.key in ("tooltip", "custom_effect_tooltip")}
            for cost in (e.value for e in decision if e.key == "custom_cost_text"):
                keys |= {cost, cost + "_blocked", cost + "_tooltip"}
        loc = (ROOT / "common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt").read_text(encoding="utf-8")
        keys |= set(re.findall(r"localization_key = (VAL_EAST_CONTEST_\w+)", loc))
        for number in range(89, 102):
            event = country_event(f"val_peace.{number}")
            keys |= {e.value for e in walk(event) if e.key in ("title", "text", "name", "custom_effect_tooltip")
                     and isinstance(e.value, str)}
            keys |= {e.value for e in event if e.key == "desc" and isinstance(e.value, str)}
        for event_id in ("val_peace.81", "val_peace.82", "val_peace.83"):
            keys |= {e.value for e in walk(country_event(event_id)) if e.key == "text"}
        self.assertFalse(sorted(key for key in keys if key not in rows))


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
    def test_regime_branches_keep_separate_lanes(self):
        focuses = tree_focuses()
        places = {}
        for name, focus in focuses.items():
            place = (scalar(focus, "x"), scalar(focus, "y"))
            self.assertNotIn(place, places, (name, places.get(place)))
            places[place] = name
        # Each regime and the east lane own a column range; several visible branches never overlap.
        lanes = {}
        for regime, root in REGIMES.items():
            gate = block(focuses[root], "allow_branch")
            self.assertEqual(len(gate), 1, root)
            lanes[root] = [int(scalar(f, "x")) for f in focuses.values()
                           if any(e.key == "allow_branch" for e in f)
                           and [e.key for e in block(f, "allow_branch")] == [e.key for e in gate]]
        lanes["east"] = [int(scalar(focuses[name], "x")) for name in focuses if name.startswith("VAL_east_")]
        spans = sorted((min(xs), max(xs), name) for name, xs in lanes.items())
        for (_, high, left), (low, _, right) in zip(spans, spans[1:]):
            self.assertGreaterEqual(low - high, 2, (left, right))

    def test_every_regime_reaches_its_casus_and_the_last_war(self):
        focuses = tree_focuses()
        question = [e.value for e in focuses["VAL_east_question"] if e.key == "prerequisite"]
        self.assertEqual([{p.value for p in group} for group in question], [{"VAL_peace_night_of_registers"}])
        final = [e.value for e in focuses["VAL_east_final"] if e.key == "prerequisite"]
        self.assertEqual([{p.value for p in group} for group in final],
                         [{"VAL_east_shards", "VAL_east_arsenal"}, set(CASUS)])
        gates = {scalar(e.value, "tooltip"): e.value for e in block(focuses["VAL_east_question"], "available")
                 if e.key == "custom_trigger_tooltip"}
        self.assertEqual(scalar(gates["VAL_east_khan_question_closed_tt"], "VAL_east_khan_question_closed"), "yes")
        self.assertEqual(scalar(gates["VAL_east_regime_chosen_tt"], "VAL_peace_regime_chosen"), "yes")
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
            keys = {e.value for e in walk(event) if e.key in ("title", "text", "name") and isinstance(e.value, str)}
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
