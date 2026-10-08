"""Reactor preparation contracts; native timers and UI need a fresh game."""

import unittest

from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture
from tools.tests.test_adiscord_stp_preparation import block, entries, scalar


MOBILIZATION = (
    "RUS_imperial_general_staff", "RUS_western_supply_lines",
    "RUS_imperial_arsenals", "RUS_aimaq_reserve", "RUS_break_the_hegemon",
)
PROGRAMME = (
    "RUS_register_conquered_lands", "RUS_empire_without_rivals",
    "RUS_postwar_roads", "RUS_imperial_academy", "RUS_tomorrow_above_ground",
)


class RusCrisisPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = block(entries("focus_trees/RUS/main/focuses.txt"), "focus_tree")
        cls.focuses = {scalar(row.value, "id"): row.value for row in tree if row.key == "focus"}
        cls.decisions = dict((row.key, row.value) for row in block(
            entries("common/decisions/ADISCORD_vorkerland_decisions.txt"), "RUS_last_empire_crisis",
        ))

    def programme(self, phase=1):
        world = RusCrisisFixture()
        world.variables["RUS", "RUS_crisis_phase"] = phase
        world.outside_predicates["RUS", "RUS_khan_governing"] = True
        return world

    def test_mobilization_fits_warning_and_programme_fits_launch(self):
        world = self.programme()
        world.completed_focuses.add(("RUS", "RUS_seat_the_khan_chancery"))
        elapsed = 0
        for name in MOBILIZATION + PROGRAMME:
            rows = self.focuses[name]
            self.assertTrue(world.matches(block(rows, "available"), ["RUS"]), name)
            for row in rows:
                if row.key == "prerequisite":
                    self.assertTrue(any(("RUS", parent.value) in world.completed_focuses for parent in row.value), name)
            elapsed += int(scalar(rows, "cost")) * 7
            world.completed_focuses.add(("RUS", name))
            if name == "RUS_break_the_hegemon":
                self.assertEqual(elapsed, 84)
                self.assertLess(elapsed, int(scalar(self.decisions["RUS_crisis_invasion_countdown"], "days_mission_timeout")))
        self.assertLess(elapsed, int(scalar(self.decisions["RUS_crisis_laser_countdown"], "days_mission_timeout")))

    def test_preparations_require_live_project_without_military_victory(self):
        for phase in (1, 2, 3, 4, 5, 6):
            world = self.programme(phase)
            for name in PROGRAMME:
                self.assertEqual(world.matches(block(self.focuses[name], "available"), ["RUS"]), phase in (1, 2, 3))
        for invalidation in ("reactor", "disabled", "subject", "ruler"):
            world = self.programme()
            if invalidation == "reactor":
                world.controllers["177"] = "VAL"
            elif invalidation == "disabled":
                world.flags["RUS"].add("RUS_crisis_laser_disabled")
            elif invalidation == "subject":
                world.subjects["RUS"] = "VAL"
            else:
                world.outside_predicates["RUS", "RUS_khan_governing"] = False
            for name in PROGRAMME:
                self.assertFalse(world.matches(block(self.focuses[name], "available"), ["RUS"]), (name, invalidation))

    def test_frontier_campaigns_resume_only_after_the_programme_is_closed(self):
        decision = self.decisions["RUS_imperial_frontier_campaign"]
        for phase, disabled, expected in (
            (None, False, True), (1, False, False), (2, False, False),
            (2, True, False), (3, False, False), (3, True, True),
            (4, True, False), (5, True, True), (6, True, False),
        ):
            with self.subTest(phase=phase, disabled=disabled):
                world = self.programme(phase)
                if phase is None:
                    world.variables.pop(("RUS", "RUS_crisis_phase"))
                world.wars.clear()
                world.owners["frontier"] = "RLY"
                world.neighbours.add(frozenset(("RUS", "RLY")))
                world.from_country = "RLY"
                if disabled:
                    world.flags["RUS"].add("RUS_crisis_laser_disabled")
                self.assertEqual(world.matches(block(decision, "available"), ["RUS"]), expected)
                if expected:
                    world.execute(block(decision, "complete_effect"), ["RUS"])
                    self.assertIn(frozenset(("RUS", "RLY")), world.wars)
                    self.assertEqual(world.variables.get(("RUS", "RUS_crisis_phase")), phase)

    def test_inventory_delivers_equipment_without_restarting_timers(self):
        world = self.programme()
        world.missions = [("RUS", "RUS_crisis_laser_countdown")]
        world.execute(block(self.focuses["RUS_register_conquered_lands"], "completion_reward"), ["RUS"])
        self.assertEqual(world.equipment, {("RUS", "support_equipment"): 300, ("RUS", "train_equipment_1"): 40})
        self.assertEqual(world.missions, [("RUS", "RUS_crisis_laser_countdown")])
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)

    def test_guard_survives_victory_but_not_closed_programme(self):
        for phase in (1, 2, 3, 4, 5, 6):
            world = self.programme(phase)
            world.ideas.add(("RUS", "RUS_crisis_reactor_guard"))
            world.run("RUS_crisis_clear_roster")
            self.assertEqual(("RUS", "RUS_crisis_reactor_guard") in world.ideas, phase in (1, 2, 3))
        world = self.programme(2)
        world.ideas.add(("RUS", "RUS_crisis_reactor_guard"))
        world.controllers["177"] = "VAL"
        world.run("RUS_crisis_disable_laser")
        self.assertNotIn(("RUS", "RUS_crisis_reactor_guard"), world.ideas)

    def test_ai_plan_uses_compact_route_and_old_branches_are_removed(self):
        plans = dict((row.key, row.value) for row in entries("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt"))
        plan = plans["ADISCORD_rus_last_sky_plan"]
        self.assertEqual([row.value for row in block(plan, "ai_national_focuses")], list(MOBILIZATION + PROGRAMME))
        for phase in (1, 2, 3, 4, 5, 6):
            world = self.programme(phase)
            self.assertEqual(world.matches(block(plan, "enable"), ["RUS"]), phase in (1, 2, 3))
        for tag in ("nod", "stp", "sts", "val"):
            for tier in range(1, 5):
                self.assertNotIn(f"RUS_crisis_{tag}_{tier}", self.focuses)
            self.assertNotIn(f"RUS_crisis_resupply_{tag}", self.decisions)

    def test_zeppelin_shared_stats_keep_unique_hulls(self):
        equipment = block(entries("common/units/equipment/ADISCORD_air_equipment.txt"), "equipments")
        archetype = block(equipment, "ADISCORD_zeppelin_equipment")
        model = block(equipment, "ADISCORD_zeppelin_equipment_1")
        subunit = block(block(entries("common/units/ADISCORD_land_units.txt"), "sub_units"), "ADISCORD_zeppelin")
        for key, value in {"soft_attack": 550, "hard_attack": 180, "defense": 300, "breakthrough": 350, "armor_value": 90, "ap_attack": 120, "air_attack": 48, "maximum_speed": 12, "reliability": 0.99, "fuel_consumption": 8}.items():
            self.assertEqual(float(scalar(archetype, key)), value, key)
        for key, value in {"max_strength": 200, "max_organisation": 80, "default_morale": 0.6, "supply_consumption": 1.2}.items():
            self.assertEqual(float(scalar(subunit, key)), value, key)
        self.assertEqual(scalar(model, "archetype"), "ADISCORD_zeppelin_equipment")
        self.assertEqual(scalar(block(subunit, "need"), "ADISCORD_zeppelin_equipment"), "1")
        self.assertEqual(scalar(archetype, "is_buildable"), "no")
        self.assertEqual(scalar(block(model, "can_be_produced"), "is_debug"), "yes")


if __name__ == "__main__":
    unittest.main()
