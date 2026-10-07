exec(open('_tmp_rus_regional.py', encoding='utf-8-sig').read().split("p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'")[0])
import ast
import textwrap

p = 'tools/tests/test_adiscord_rus_last_empire.py'
s = read(p)
s = s.replace('"TMR", "VEL", "RLY", "SHL", "NAM", "WRK", "IVN"}', '"TMR", "VEL", "RLY", "SHL", "NAM", "WRK", "IVN", "MON", "VLD"}')
s = s.replace('            if key == "OVERLORD":', '''            if key == "any_of_scopes":
                name = self.array_key(scalar(value, "array"), current)
                gate = [e for e in value if e.key != "array"]
                return any(self.matches(gate, stack + [item]) for item in self.arrays.get(name, []))
            if key == "capital_scope":
                capital = next((s for s, owner in self.owners.items() if owner == current), None)
                return capital is not None and self.matches(value, stack + [capital])
            if key == "controller":
                owner = self.controllers.get(current)
                return owner is not None and self.matches(value, stack + [owner])
            if key == "is_controlled_by":
                return self.controllers.get(current) == self.resolve(value, stack)
            if key == "has_event_target":
                return "event_target:" + value in self.targets
            if key == "OVERLORD":''')
s = s.replace('"every_subject_country", "every_enemy_country"):', '"every_subject_country", "every_enemy_country", "every_allied_country"):')
s = s.replace('                    "every_subject_country": [tag for tag, owner in self.subjects.items() if owner == current],', '''                    "every_subject_country": [tag for tag, owner in self.subjects.items() if owner == current],
                    "every_allied_country": [tag for tag, faction in self.factions.items() if tag != current and faction == self.factions.get(current)],''')
s = s.replace('            elif key == "set_variable":\n                self.variables', '''            elif key == "remove_from_array":
                name = self.array_key(scalar(value, "array"), current)
                self.arrays[name].remove(self.resolve(scalar(value, "value"), stack))
            elif key == "clear_global_event_target":
                self.targets.pop("event_target:" + value, None)
            elif key == "set_variable":
                self.variables''')
s = s.replace('"STP_khan_coalition_armistice") and key not in self.effects:', ') and key not in self.effects:')

def method(name, body):
    global s
    tree = ast.parse(s)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = s.splitlines(True)
    new = textwrap.indent(textwrap.dedent(body).strip(), '    ') + '\n' if body else ''
    s = ''.join(lines[:node.lineno - 1]) + new + ''.join(lines[node.end_lineno:])

method('peaceful_empire', '''
def peaceful_empire(self):
    world = RusCrisisFixture()
    world.run("RUS_crisis_clear_roster")
    world.variables.clear()
    world.wars.clear()
    world.outside_predicates["RUS", "RUS_khan_governing"] = True
    for tag in ("MON", "VLD", "TMR"):
        world.owners[tag + "_capital"] = tag
        world.controllers[tag + "_capital"] = tag
    return world
''')
method('test_ally_subject_is_mandatory_and_all_roster_members_are_annexed', '''
def test_ally_subject_is_mandatory_and_all_roster_members_are_annexed(self):
    for target in ("VAL", "STS", "STP", "NOD", "SHL", "NAM", "MON", "VLD", "TMR"):
        for last in (target, "WKR", "RLY"):
            with self.subTest(target=target, last=last):
                world = self.peaceful_empire()
                world.owners["ally_subject"] = "RLY"
                world.owners["main_subject"] = "VEL"
                world.owners["target"] = target
                world.factions = {target: "defenders", "WKR": "defenders"}
                world.subjects = {"RLY": "WKR", "VEL": target}
                if target in ("VAL", "STS", "STP", "NOD"):
                    self.complete_hegemon_victory(world, target)
                elif target in ("SHL", "NAM"):
                    self.regional_victor(world, target)
                world.variables["RUS", "RUS_crisis_phase"] = 1
                world.run("RUS_crisis_launch")
                expected = {"MON", "VLD", "TMR", target, "WKR", "RLY", "VEL"}
                if target == "NOD":
                    expected.update(("VAL", "STP", "STS"))
                self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), expected)
                self.assertTrue(all(frozenset(("RUS", tag)) in world.wars for tag in expected))
                world.capitulated.update(expected - {last})
                for state, owner in world.owners.items():
                    if owner in expected - {last}:
                        world.controllers[state] = "RUS"
                world.run("RUS_crisis_resolve_capitulation")
                self.assertFalse(world.annexed)
                world.root, world.from_country = last, "RUS"
                world.run("RUS_crisis_record_capitulation", last)
                self.assertEqual(set(world.annexed), {("RUS", tag) for tag in expected})
                self.assertTrue(all(world.owners[state] == "RUS" for state in ("ally_subject", "main_subject", "target")))
                self.assertFalse(world.majors - {"VAL"})
''')
method('test_project_exposure_stops_existing_wars_and_never_restarts_timers', '''
def test_project_exposure_preserves_wars_factions_and_never_restarts_timers(self):
    from copy import deepcopy

    world = self.peaceful_empire()
    world.peace_mode = "pair"
    world.wars.update((frozenset(("VAL", "STP")), frozenset(("STS", "NOD"))))
    world.subjects["NOD"] = "VAL"
    world.factions = {"VAL": "old_east", "NOD": "old_east", "STS": "old_north"}
    before = dict(world.owners), set(world.wars), dict(world.factions), set(world.majors)
    world.run("RUS_crisis_check_start")
    self.assertEqual((world.owners, world.wars, world.factions, world.majors), before)
    self.assertFalse(world.declarations)
    self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
    self.assertEqual({tag for tag, flags in world.flags.items() if "RUS_crisis_warned" in flags}, {"MON", "VLD", "TMR"})
    missions = list(world.missions)
    loaded = deepcopy(world)
    loaded.run("RUS_crisis_check_start")
    loaded.run("RUS_crisis_begin")
    self.assertEqual(loaded.missions, missions)
    self.assertEqual(loaded.variables["RUS", "RUS_crisis_phase"], 1)
''')
method('test_only_the_coalition_host_declares_and_every_ally_joins_that_war', '''
def test_only_one_host_declares_and_existing_blocs_share_the_war(self):
    world = self.peaceful_empire()
    world.factions = {"MON": "montar", "WKR": "montar", "VLD": "vald", "TMR": "timer"}
    world.wars.add(frozenset(("VLD", "STS")))
    factions, wars = dict(world.factions), set(world.wars)
    world.run("RUS_crisis_begin")
    world.run("RUS_crisis_launch")
    self.assertEqual(world.declarations, [("MON", "RUS")])
    self.assertEqual(set(world.joins), {("VLD", "MON", "RUS"), ("TMR", "MON", "RUS"), ("WKR", "MON", "RUS")})
    self.assertEqual(world.factions, factions)
    self.assertTrue(wars <= world.wars)
    before = list(world.declarations), list(world.joins)
    world.run("RUS_crisis_launch")
    self.assertEqual((world.declarations, world.joins), before)
    world.run("RUS_crisis_close")
    self.assertEqual(world.factions, factions)
''')
method('test_regional_neutral_cleanup_precedes_new_major_ownership', '''
def test_parallel_major_owners_release_in_every_order(self):
    from itertools import permutations

    for order in permutations(("west", "south", "rus")):
        world = self.peaceful_empire()
        for region in ("west", "south"):
            self.load_regional_lifecycle(world, region)
        world.majors.discard("MON")
        world.flags["MON"].add("ADISCORD_west_added_major")
        world.majors.add("MON")
        world.run("RUS_crisis_register_defender", "MON")
        self.assertIn("RUS_crisis_added_major", world.flags["MON"])
        register = self.block(world.effects["ADISCORD_south_register_member"], "if")
        world.execute([next(row for row in world.effects["ADISCORD_south_register_member"] if row.key == "if")], ["MON"])
        self.assertIn("ADISCORD_south_added_major", world.flags["MON"])
        for index, owner in enumerate(order):
            if owner == "rus":
                world.run("RUS_crisis_clear_defender", "MON")
            else:
                effect_name = "ADISCORD_" + owner + "_close_member_state"
                world.execute([world.effects[effect_name][0]], ["MON"])
            self.assertEqual("MON" in world.majors, index < 2, order)
        self.assertFalse(world.flags["MON"] & {"RUS_crisis_added_major", "ADISCORD_west_added_major", "ADISCORD_south_added_major"})
''')
method('test_unstarted_regional_crises_wait_while_the_coalition_exists', '''
def test_independent_regional_crises_continue_until_the_epilogue(self):
    for region in ("west", "south"):
        world = self.peaceful_empire()
        self.load_regional_lifecycle(world, region)
        world.global_flags.update(("ADISCORD_fresh_campaign_contract_v1", "ADISCORD_vorkerland_collapse_finished", "ADISCORD_nam_resource_war_resolved"))
        world.owners["wrk_capital"] = "WRK"
        world.flags["WRK"].add("ADISCORD_vorkerland_central_unifier")
        gate = world.triggers[f"ADISCORD_{region}_crisis_open"]
        for phase in (1, 2, 4):
            world.variables["RUS", "RUS_crisis_phase"] = phase
            self.assertTrue(world.matches(gate, ["RUS"]))
        world.global_flags.add("RUS_crisis_world_ended")
        self.assertFalse(world.matches(gate, ["RUS"]))
''')
method('test_delayed_nod_invasion_cannot_break_the_coalition', '''
def test_eastern_hegemon_must_finish_its_wars_and_remain_sovereign_at_entry(self):
    for target in ("VAL", "STP", "STS", "NOD"):
        for invalidation in ("war", "subject", "capitulated", None):
            with self.subTest(target=target, invalidation=invalidation):
                world = self.peaceful_empire()
                gate = world.triggers["RUS_crisis_coalition_candidate"]
                self.assertFalse(world.matches(gate, [target]))
                self.complete_hegemon_victory(world, target)
                self.assertTrue(world.matches(gate, [target]))
                world.run("RUS_crisis_begin")
                if invalidation == "war":
                    world.wars.add(frozenset((target, "WKR")))
                elif invalidation == "subject":
                    world.subjects[target] = "WKR"
                elif invalidation == "capitulated":
                    world.capitulated.add(target)
                world.run("RUS_crisis_launch")
                self.assertEqual(frozenset((target, "RUS")) in world.wars, invalidation is None)
                self.assertEqual("RUS_crisis_defender" in world.flags[target], invalidation is None)
''')
method('test_pending_treaty_blocks_exposure_without_consuming_start', '''
def test_unrelated_pending_treaty_and_empty_roster_do_not_stop_the_programme(self):
    world = self.peaceful_empire()
    for tag in ("MON", "VLD", "TMR"):
        world.subjects[tag] = "WKR"
    world.flags["VAL"].add("ADISCORD_south_settlement_pending")
    world.run("RUS_crisis_check_start")
    self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)
    world.run("RUS_crisis_launch")
    world.run("RUS_crisis_resolve_capitulation")
    self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
    self.assertFalse(world.annexed)
    world.run("RUS_crisis_end_world")
    self.assertIn("RUS_crisis_world_ended", world.global_flags)
''')
s = s.replace('def test_delayed_peace_callbacks_do_not_reward_a_coalition_armistice(self):', 'def test_peace_callbacks_preserve_the_other_war_of_two_interveners(self):')
s = s.replace('            self.assertFalse(world.matches(gate, ["STP"]))\n            world.flags["STP"].clear()', '            self.assertTrue(world.matches(gate, ["STP"]))\n            world.flags["STP"].clear()')
s = s.replace('def test_truce_rejects_delayed_friendly_war_but_keeps_war_against_khan(self):', 'def test_only_terminal_epilogue_rejects_new_wars(self):')
s = s.replace('        self.assertNotIn(frozenset(("VAL", "STP")), world.wars)\n        self.assertIn(frozenset(("VAL", "RUS")), world.wars)', '''        self.assertIn(frozenset(("VAL", "STP")), world.wars)
        self.assertIn(frozenset(("MON", "RUS")), world.wars)
        world.global_flags.add("RUS_crisis_world_ended")
        world.run("RUS_crisis_enforce_truce", "VAL")
        self.assertNotIn(frozenset(("VAL", "STP")), world.wars)''')
s = s.replace('phase in (None, 1, 2))\n                self.assertEqual(world.matches(self.block(focus, "bypass"), ["RUS"]), phase == 3)', 'phase in (None, 1, 2, 3))\n                self.assertNotIn("bypass", [row.key for row in focus])')
s = s.replace('self.assertCountEqual(enabled(world, "RUS", "prepare_for_war"), ("VAL", "STS", "STP", "NOD"))', 'self.assertCountEqual(enabled(world, "RUS", "prepare_for_war"), (target, "MON", "VLD", "TMR"))')
s = s.replace('self.assertEqual(enabled(world, neutral, "prepare_for_war"), ["RUS"])', 'self.assertEqual(enabled(world, neutral, "prepare_for_war"), [])')
s = s.replace('enemies = {"VAL", "STS", "STP", "NOD"}\n                self.assertCountEqual', 'enemies = {target, "MON", "VLD", "TMR"}\n                if target == "NOD":\n                    enemies.update(("VAL", "STP", "STS"))\n                self.assertCountEqual')
s = s.replace('        world.factions = {"VAL": "league", "NOD": "league"}', '        world.factions = {"VAL": "league", "NOD": "league"}\n        self.complete_hegemon_victory(world, "VAL")')
s = s.replace('self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"VAL", "NOD", "STP", "STS", "WKR"})', 'self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"VAL", "NOD"})')
# Existing military-victory fixtures explicitly model occupation by the victor.
lines = s.splitlines(True)
for index in range(len(lines) - 1, -1, -1):
    line = lines[index]
    if ('world.capitulated.update(("VAL", "NOD"))' in line or 'world.capitulated.add("NOD")' in line):
        indent = line[:len(line) - len(line.lstrip())]
        lines[index + 1:index + 1] = [indent + 'world.controllers.update({"168": "RUS", "10": "RUS"})\n']
s = ''.join(lines)
write(p, s)
