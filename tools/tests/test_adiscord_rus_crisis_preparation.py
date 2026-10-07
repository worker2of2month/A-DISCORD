"""Parsed target preparation contracts; native timers and UI need a fresh game."""

from copy import deepcopy
import unittest

from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture
from tools.tests.test_adiscord_stp_preparation import block, entries, scalar


TARGETS = ("NOD", "STP", "STS", "VAL")


class RusCrisisPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = block(entries("focus_trees/RUS/main/focuses.txt"), "focus_tree")
        cls.focuses = {
            scalar(row.value, "id"): row.value
            for row in tree if row.key == "focus"
        }
        cls.decisions = dict(
            (row.key, row.value)
            for row in block(
                entries("common/decisions/ADISCORD_vorkerland_decisions.txt"),
                "RUS_last_empire_crisis",
            )
        )
        cls.ideas = dict(
            (row.key, row.value)
            for row in block(
                block(entries("common/ideas/ADISCORD_vorkerland_ideas.txt"), "ideas"),
                "country",
            )
        )

    def warning(self, target):
        world = RusCrisisFixture(target)
        world.run("RUS_crisis_clear_roster")
        world.run("RUS_crisis_register_defender", target)
        world.variables["RUS", "RUS_crisis_phase"] = 1
        world.wars.clear()
        world.outside_predicates["RUS", "RUS_khan_governing"] = True
        world.missions = [
            ("RUS", "RUS_crisis_invasion_countdown"),
            (target, "RUS_crisis_defence_countdown"),
        ]
        return world

    def test_every_route_is_reachable_in_warning_without_general_staff(self):
        deadline = int(scalar(self.decisions["RUS_crisis_invasion_countdown"], "days_mission_timeout"))
        for target in TARGETS:
            with self.subTest(target=target):
                world = self.warning(target)
                missions = list(world.missions)
                days = 0
                for tier in range(1, 5):
                    name = f"RUS_crisis_{target.lower()}_{tier}"
                    rows = self.focuses[name]
                    self.assertTrue(world.matches(block(rows, "available"), ["RUS"]))
                    for prerequisite in (row.value for row in rows if row.key == "prerequisite"):
                        self.assertTrue(any(("RUS", row.value) in world.completed_focuses for row in prerequisite))
                    days += int(scalar(rows, "cost")) * 7
                    world.execute(block(rows, "completion_reward"), ["RUS"])
                    world.completed_focuses.add(("RUS", name))
                    if tier == 3:
                        self.assertIn(("RUS", f"RUS_crisis_{target.lower()}_preparation_1"), world.ideas)
                self.assertEqual(days, 77)
                self.assertLess(days, deadline)
                self.assertEqual(world.missions, missions)
                self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)
                self.assertEqual(world.ideas, {("RUS", f"RUS_crisis_{target.lower()}_preparation_2")})
                self.assertGreater(sum(world.equipment.values()), 0)
                self.assertEqual(world.army_experience, 15)
                self.assertEqual(world.command_power, 15)

    def test_unselected_routes_and_unrelated_wars_cannot_use_preparation(self):
        for target in TARGETS:
            world = self.warning(target)
            for other in TARGETS:
                rows = self.focuses[f"RUS_crisis_{other.lower()}_1"]
                self.assertEqual(world.matches(block(rows, "available"), ["RUS"]), target == other)
            world.variables["RUS", "RUS_crisis_phase"] = 2
            world.wars.add(frozenset(("RUS", "WKR")))
            gate = block(self.focuses[f"RUS_crisis_{target.lower()}_1"], "available")
            self.assertTrue(world.matches(gate, ["RUS"]))
            world.wars.add(frozenset(("RUS", target)))
            self.assertTrue(world.matches(gate, ["RUS"]))
            world.subjects["RUS"] = "WKR"
            self.assertFalse(world.matches(gate, ["RUS"]))

    def test_resupply_is_immediate_reusable_and_closes_with_its_campaign(self):
        for target in TARGETS:
            with self.subTest(target=target):
                world = self.warning(target)
                rows = self.decisions[f"RUS_crisis_resupply_{target.lower()}"]
                self.assertFalse(world.matches(block(rows, "visible"), ["RUS"]))
                world.completed_focuses.add(("RUS", f"RUS_crisis_{target.lower()}_1"))
                self.assertTrue(world.matches(block(rows, "visible"), ["RUS"]))
                self.assertEqual(scalar(rows, "cost"), "50")
                self.assertEqual(scalar(rows, "days_re_enable"), "30")
                self.assertEqual(scalar(rows, "fire_only_once"), "no")
                world.execute(block(rows, "complete_effect"), ["RUS"])
                delivered = dict(world.equipment)
                self.assertTrue(delivered)
                loaded = deepcopy(world)
                loaded.execute(block(rows, "complete_effect"), ["RUS"])
                self.assertEqual(loaded.equipment, {key: value * 2 for key, value in delivered.items()})
                for phase in (3, 4, 5):
                    world.variables["RUS", "RUS_crisis_phase"] = phase
                    self.assertFalse(world.matches(block(rows, "visible"), ["RUS"]))
                    self.assertFalse(world.matches(block(rows, "available"), ["RUS"]))
                    world.execute(block(rows, "complete_effect"), ["RUS"])
                    self.assertEqual(world.equipment, delivered)

    def test_operational_plans_only_modify_their_opponent_and_upgrade(self):
        for target in TARGETS:
            previous = None
            for tier in (1, 2):
                idea = self.ideas[f"RUS_crisis_{target.lower()}_preparation_{tier}"]
                self.assertNotIn("modifier", [row.key for row in idea])
                modifier = block(idea, "targeted_modifier")
                self.assertEqual(scalar(modifier, "tag"), target)
                values = tuple(float(scalar(modifier, key)) for key in (
                    "attack_bonus_against", "defense_bonus_against", "breakthrough_bonus_against",
                ))
                if previous:
                    self.assertTrue(all(after > before for before, after in zip(previous, values)))
                previous = values
                world = self.warning(target)
                self.assertFalse(world.matches(block(idea, "cancel"), ["RUS"]))
                world.variables["RUS", "RUS_crisis_phase"] = 5
                self.assertTrue(world.matches(block(idea, "cancel"), ["RUS"]))

    def test_every_terminal_outcome_clears_all_preparation_tiers(self):
        all_ideas = {
            ("RUS", f"RUS_crisis_{target.lower()}_preparation_{tier}")
            for target in TARGETS for tier in (1, 2)
        }
        for target in TARGETS:
            for outcome in ("victory", "defeat", "close"):
                with self.subTest(target=target, outcome=outcome):
                    world = RusCrisisFixture(target)
                    world.ideas.update(all_ideas)
                    if outcome == "victory":
                        world.capitulated.update(world.arrays["global.RUS_crisis_defenders"])
                        world.run("RUS_crisis_resolve_capitulation")
                    elif outcome == "defeat":
                        world.capitulated.add("RUS")
                        world.run("RUS_crisis_resolve_capitulation")
                    else:
                        world.run("RUS_crisis_close")
                    self.assertFalse(world.ideas & all_ideas)
                    self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], {
                        "victory": 3, "defeat": 4, "close": 5,
                    }[outcome])

    def test_ai_routes_have_all_four_steps_and_current_target_gate(self):
        plans = dict((row.key, row.value) for row in entries("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt"))
        for target in TARGETS:
            rows = plans[f"ADISCORD_rus_crisis_{target.lower()}_plan"]
            self.assertEqual(
                [row.value for row in block(rows, "ai_national_focuses")],
                [f"RUS_crisis_{target.lower()}_{tier}" for tier in range(1, 5)],
            )
            self.assertEqual(scalar(block(rows, "enable"), f"RUS_crisis_prepare_{target.lower()}"), "yes")
            self.assertEqual(scalar(block(rows, "abort"), f"RUS_crisis_prepare_{target.lower()}"), "no")


if __name__ == "__main__":
    unittest.main()
