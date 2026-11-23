"""Static contracts of the southern final war between Svetlogorye and Shahrabad.

The checks cover script wiring only: side lists, terminal cleanup, flag order
and path focuses. Engine war, faction and peace behaviour needs a game run.
"""

from pathlib import Path
from dataclasses import replace
import json
import re
import unittest

from PIL import Image

from tools.lib.focus_sources import read_focus_source
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions, selected_effects, walk

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_south_final_war_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_south_final_war_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_south_final_war_events.txt"
PEACE = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
REGIONAL = ("EFL", "AZH", "WEF", "KDR", "RHM", "SDR", "MZR", "KYZ", "GLP")
CHAMPIONS = ("NAM", "SHL")
CANDIDATES = ("NAM", "SHL", "EFL", "AZH")
# Crisis deadline by pull level: 1 March 2166, 15 days earlier per unit.
DEADLINES = ("2166.3.1", "2166.2.14", "2166.1.30", "2166.1.15", "2165.12.31", "2165.12.16", "2165.12.1")
# A preparation opened on OPENED without an earlier anchor gets the 540-day
# window, so DEADLINES[level] is its deadline after `level` pulls counted
# before the opening. Svetlogorye's victory sets 1095 days instead.
OPENED = "2164.9.7"
SHORT_WINDOW = 540
VICTORY_WINDOW = 1095
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
FURNACE_ADMINISTRATIONS = {"SFD", "SCD", "SMD", "SOD", "SDA"}
FURNACE_DIRECT_TERRITORY = {
    262, 263, 264, 268, 269, 273, 276, 277, 278, 279, 280, 281, 282, 283,
    284, 285, 286, 297, 298, 299, 300, 301, 302, 304, 305, 706, 708,
}


class FurnaceAdministrationModel:
    """Bounded ownership interpreter; it does not emulate native country creation."""

    def __init__(self):
        self.effects = definitions(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt")
        self.triggers = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        self.owners = {}
        self.controllers = {}
        self.subjects = {}
        self.cores = set()
        self.targets = {}
        self.calls = []
        self.course = 3
        self.active_war = False

    def resolve(self, value):
        if value.startswith("event_target:"):
            return self.targets[value.split(":", 1)[1]]
        return value

    def exists(self, tag):
        return tag == "SHL" or tag in self.owners.values()

    def condition(self, entry, scope):
        key, value = entry.key, entry.value
        if key in ("OR", "AND", "NOT", "hidden_trigger"):
            checks = [self.condition(child, scope) for child in value]
            return {"OR": any(checks), "AND": all(checks),
                    "NOT": not any(checks), "hidden_trigger": all(checks)}[key]
        if key in FURNACE_ADMINISTRATIONS or key == "SHL":
            return self.matches(value, key)
        if key == "SHL_country_operable":
            return scope == "SHL"
        if key == "ADISCORD_south_final_active":
            return self.active_war == (value == "yes")
        if key in self.triggers:
            return self.matches(self.triggers[key], scope) == (value == "yes")
        if key == "tag":
            return scope == value
        if key == "exists":
            return self.exists(scope) == (value == "yes")
        if key == "is_subject":
            return (scope in self.subjects) == (value == "yes")
        if key == "is_subject_of":
            return self.subjects.get(scope) == value
        if key == "is_owned_by":
            return self.owners.get(scope) == value
        if key == "is_controlled_by":
            return self.controllers.get(scope) == value
        if key == "check_variable":
            assert scalar(value, "var") == "SHL_political_course"
            assert scalar(value, "compare") == "equals"
            return self.course == int(scalar(value, "value"))
        raise AssertionError(f"Unsupported administration condition: {key}")

    def matches(self, items, scope):
        return all(self.condition(item, scope) for item in items)

    def execute(self, items, scope="SHL", previous=None):
        for entry in items:
            key, value = entry.key, entry.value
            if key == "if":
                if self.matches(block(value, "limit"), scope):
                    self.execute([item for item in value if item.key != "limit"], scope, previous)
            elif key in self.effects:
                self.execute(self.effects[key], scope, previous)
            elif key in FURNACE_ADMINISTRATIONS or key == "SHL" or key.isdigit() or key.startswith("event_target:"):
                self.execute(value, self.resolve(key), scope)
            elif key == "save_event_target_as":
                self.targets[value] = scope
            elif key == "add_core_of":
                self.cores.add((scope, self.resolve(value)))
            elif key == "transfer_state":
                assert value == "PREV"
                self.owners[previous] = scope
                self.controllers[previous] = scope
            elif key == "set_autonomy":
                assert scalar(value, "target") == "PREV"
                assert self.exists(previous)
                self.subjects[previous] = scope
                self.calls.append((key, previous, scalar(value, "autonomy_state")))
            elif key in ("ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty", "ADISCORD_release_non_participating_minor_optimization",
                         "ADISCORD_south_bind_to_champion"):
                self.calls.append((key, scope))
            else:
                raise AssertionError(f"Unsupported administration effect: {key}")

    def run(self):
        self.execute(self.effects["SHL_form_furnace_administrations"])

    def acquire(self, *states):
        for state in states:
            self.owners[str(state)] = "SHL"
            self.controllers[str(state)] = "SHL"


class FurnaceAdministrationTests(unittest.TestCase):
    def test_rayhan_is_recruited_only_as_great_road_governor(self):
        character = "SHL_Samir_Rayhan"
        countries = ROOT / "history/countries"
        recruits = [p.name[:3] for p in countries.glob("*.txt")
                    if re.search(rf"(?m)^recruit_character = {character}$", p.read_text(encoding="utf-8-sig"))]
        self.assertEqual(recruits, ["SCD"])
        characters = definitions(ROOT / "common/characters/ADISCORD_southern_desert_characters.txt")["characters"]
        governor = block(characters, character)
        self.assertFalse({"corps_commander", "field_marshal"} & {entry.key for entry in governor})
        self.assertEqual(scalar(block(governor, "country_leader"), "ideology"), "service_etatism")
        self.assertEqual(scalar(block(block(governor, "portraits"), "civilian"), "large"),
                         "GFX_portrait_SHL_Samir_Rayhan")

    def test_geography_covers_the_south_once_and_crosses_old_borders(self):
        model = FurnaceAdministrationModel()
        historical = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            owner = re.search(r"\bowner\s*=\s*(\w+)", text)
            state = re.search(r"\bid\s*=\s*(\d+)", text)
            if owner and owner[1] in set(REGIONAL) | set(CHAMPIONS):
                historical[state[1]] = owner[1]
        model.acquire(*historical)
        model.run()
        for state, owner in historical.items():
            if owner == "SHL" or int(state) in FURNACE_DIRECT_TERRITORY:
                self.assertEqual(model.owners[state], "SHL", state)
            else:
                self.assertIn(model.owners[state], FURNACE_ADMINISTRATIONS, state)
                self.assertIn((state, model.owners[state]), model.cores)
                self.assertEqual(model.controllers[state], model.owners[state])
        for tag in FURNACE_ADMINISTRATIONS:
            territory = {state for state, owner in model.owners.items() if owner == tag}
            origins = {historical[state] for state in territory}
            self.assertTrue(origins, tag)
            for origin in origins:
                self.assertNotEqual(territory, {state for state, owner in historical.items() if owner == origin}, tag)
        self.assertEqual(model.subjects, dict.fromkeys(FURNACE_ADMINISTRATIONS, "SHL"))
        source = body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", "SHL_form_furnace_administrations")
        states = re.findall(r"(\d+) = \{ SHL_transfer_furnace_administration_land = yes \}", source)
        self.assertEqual(len(states), len(set(states)))

    def test_incremental_conquest_preserves_existing_offices_and_is_idempotent(self):
        model = FurnaceAdministrationModel()
        model.acquire(265, 246)
        model.run()
        self.assertEqual(model.owners, {"265": "SFD", "246": "SMD"})
        self.assertEqual(len([call for call in model.calls if call[0] == "set_autonomy"]), 2)
        model.acquire(267, 245, 234)
        model.run()
        self.assertEqual([model.owners[str(state)] for state in (267, 245, 234)], ["SFD", "SMD", "SCD"])
        snapshot = (model.owners.copy(), model.controllers.copy(), model.subjects.copy(), model.cores.copy())
        model.run()
        self.assertEqual(snapshot, (model.owners, model.controllers, model.subjects, model.cores))
        self.assertEqual(len([call for call in model.calls if call[0] == "set_autonomy"]), 3)

    def test_foreign_occupation_liberation_and_other_courses_are_not_overwritten(self):
        model = FurnaceAdministrationModel()
        model.acquire(265, 267, 258)
        model.controllers["265"] = "MZR"
        model.owners["258"] = "RHM"
        model.owners["705"] = "SFD"
        model.controllers["705"] = "SFD"
        before = (model.owners.copy(), model.controllers.copy())
        model.run()
        self.assertEqual(before, (model.owners, model.controllers))
        self.assertEqual(model.subjects, {})
        for course in (1, 2, 4, 5):
            model = FurnaceAdministrationModel()
            model.course = course
            model.acquire(265, 258, 688)
            model.run()
            self.assertEqual(set(model.owners.values()), {"SHL"})
        model = FurnaceAdministrationModel()
        model.subjects["SHL"] = "NAM"
        model.acquire(280)
        model.run()
        self.assertEqual(model.owners["280"], "SHL")

    def test_new_offices_join_active_war_and_settlement_dispatch_is_deferred(self):
        model = FurnaceAdministrationModel()
        model.active_war = True
        model.acquire(265)
        model.run()
        self.assertIn(("ADISCORD_south_bind_to_champion", "SFD"), model.calls)
        peace = PEACE.read_text(encoding="utf-8")
        section = peace.split("# BEGIN shahrabad:on_annex", 1)[1].split("# END shahrabad:on_annex", 1)[0]
        self.assertIn("ROOT = { SHL_queue_furnace_administrations = yes }", section)
        queue = body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", "SHL_queue_furnace_administrations")
        self.assertIn("hours = 1", queue)
        self.assertIn("NOT = { has_country_flag = SHL_furnace_administrations_pending }", queue)
        settlement = body(EFFECTS, "ADISCORD_south_apply_settlement")
        self.assertLess(settlement.index("ADISCORD_south_settle_member"), settlement.index("SHL_form_furnace_administrations"))

    def test_direct_rule_expansion_and_office_capitals_remain_in_their_territories(self):
        model = FurnaceAdministrationModel()
        model.acquire(*FURNACE_DIRECT_TERRITORY, 705, 702, 246, 704, 688)
        model.run()
        model.run()
        for state in FURNACE_DIRECT_TERRITORY:
            self.assertEqual(model.owners[str(state)], "SHL", state)
            self.assertFalse(any(core_state == str(state) for core_state, _ in model.cores))
        for tag in FURNACE_ADMINISTRATIONS:
            history = ROOT / f"history/countries/{tag} - Furnace Administration.txt"
            capital = re.search(r"capital = (\d+)", history.read_text(encoding="utf-8"))[1]
            self.assertEqual(model.owners[capital], tag)

    def test_assets_have_native_sizes_and_distinct_flags(self):
        from PIL import Image
        from tools.builders.build_adiscord_shl_administration_assets import outputs, SIZES

        for path, expected in outputs().items():
            self.assertEqual((ROOT / path).read_bytes(), expected, str(path))
        for folder, size in SIZES.items():
            pixels = set()
            for tag in FURNACE_ADMINISTRATIONS:
                with Image.open(ROOT / "gfx/flags" / folder / f"{tag}.tga") as image:
                    self.assertEqual(image.size, size)
                    pixels.add(image.tobytes())
            self.assertEqual(len(pixels), len(FURNACE_ADMINISTRATIONS))
        with Image.open(ROOT / "gfx/interface/autonomy/autonomy_SHL_furnace_administration_icon.png") as image:
            self.assertEqual(image.size, (35, 36))
            self.assertEqual(image.getextrema()[3], (0, 255))


def definitions(path):
    return {e.key: e.value for e in parse_clausewitz(path.read_text(encoding="utf-8"))}


def body(path, name):
    text = path.read_text(encoding="utf-8")
    start = re.search(rf"(?m)^{re.escape(name)} = \{{", text)
    if start is None:
        raise AssertionError("Missing definition: " + name)
    depth = 0
    for index in range(start.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[start.end():index]
    raise AssertionError("Unbalanced definition: " + name)


def scope_calls(source, effect):
    return set(re.findall(rf"\b([A-Z]{{3}}) = \{{ {re.escape(effect)} = yes \}}", source))


SHL_TREES = tuple(
    ROOT / f"focus_trees/SHL/{name}/focuses.txt"
    for name in ("main", "houses", "cities", "directorate", "regency", "commune", "shared")
)


def focus_blocks(path):
    """id -> body of the authored focuses; a shared layer has top-level shared_focus blocks."""
    entries = parse_clausewitz(read_focus_source(path))
    tree = next((e.value for e in entries if e.key == "focus_tree"), entries)
    result = {}
    for entry in tree:
        if entry.key in ("focus", "shared_focus") and isinstance(entry.value, list):
            identifier = next(e.value for e in entry.value if e.key == "id")
            result[identifier] = entry.value
    return result


def shl_focus_blocks():
    result = {}
    for path in SHL_TREES:
        result.update(focus_blocks(path))
    return result


SHL_COURSE_SECTIONS = {"houses": "1", "cities": "2", "directorate": "3", "regency": "4", "commune": "5"}


def shl_tree_course(path):
    """Course value of one SHL course section of the single tree, or None for the main tree."""
    header = path.read_text(encoding="utf-8").split("\n", 1)[0]
    if not header.startswith("# @section "):
        return None
    return SHL_COURSE_SECTIONS[header[len("# @section "):].strip()]


def flatten(items):
    for item in items:
        yield item
        if isinstance(item.value, list):
            yield from flatten(item.value)


def day_number(date):
    """Day count of a script date in the game calendar, which has no leap years."""
    year, month, day = (int(part) for part in date.split("."))
    return year * 365 + sum(MONTH_DAYS[: month - 1]) + day - 1


def script_date(number):
    year, rest = divmod(number, 365)
    month = 0
    while rest >= MONTH_DAYS[month]:
        rest -= MONTH_DAYS[month]
        month += 1
    return f"{year}.{month + 1}.{rest + 1}"


def numeric_date(date):
    year, month, day = (int(part) for part in date.split("."))
    return year * 10000 + month * 100 + day


# Engine variable effects; division and modulo work on the integral day counts
# of the calendar code.
VARIABLE_OPERATIONS = {
    "set": lambda old, value: value,
    "add_to": lambda old, value: old + value,
    "subtract_from": lambda old, value: old - value,
    "multiply": lambda old, value: old * value,
    "divide": lambda old, value: old / value,
    "modulo": lambda old, value: old % value,
    "clamp": None,
}


def field_value(entry, name):
    """A named field of a block entry, or None for short forms such as `check_variable = { x > 1 }`."""
    if not isinstance(entry.value, list):
        return None
    return next((field.value for field in entry.value if field.key == name), None)


class ScenarioFacts(dict):
    """Scenario facts whose variable reads also see temp and cross-scope values.

    Temp variables of one effect execution are visible in every scope, as in
    the engine; a reference such as global.X or NAM.X names its holder.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.temps = {}

    def get(self, key, default=None):
        if isinstance(key, tuple) and len(key) == 3 and key[1] in ("variable", "has_variable"):
            name = key[2]
            if name in self.temps:
                return True if key[1] == "has_variable" else self.temps[name]
            if "." in name:
                holder, name = name.split(".", 1)
                return super().get(("GLB" if holder == "global" else holder, key[1], name), default)
        return super().get(key, default)


class SouthFinalWarContractTests(unittest.TestCase):
    def test_war_entry_grants_reserves_to_current_ai_champions_by_difficulty(self):
        effects = definitions(EFFECTS)
        prepare = "ADISCORD_south_prepare_champion"
        reserve = "ADISCORD_south_issue_campaign_reserve"
        start = block(effects["ADISCORD_south_begin_hostilities"], "if")
        recipients = [e for e in start if isinstance(e.value, list)
                      and any(item.key == prepare for item in walk(e.value))]
        self.assertCountEqual([e.key for e in recipients], CANDIDATES)
        for recipient in recipients:
            tag = recipient.key
            for leader in ("NAM", "EFL", "AZH"):
                facts = {(tag, "has_country_flag", "ADISCORD_south_north_leader"): tag == leader}
                calls = [e.key for _, e in selected_effects(recipient.value, facts, tag)]
                self.assertEqual(calls.count(prepare), int(tag in ("SHL", leader)))
            for level in range(5):
                for ai in (False, True):
                    facts = {(tag, "numeric", "difficulty"): level, (tag, "is_ai", "yes"): ai}
                    calls = [e.key for _, e in selected_effects(effects[prepare], facts, tag)]
                    self.assertEqual(calls.count(reserve), max(0, level - 2) if ai else 0)
        package = effects[reserve]
        self.assertEqual(scalar(package, "add_manpower"), "20000")
        equipment = {scalar(e.value, "type"): int(scalar(e.value, "amount"))
                     for e in package if e.key == "add_equipment_to_stockpile"}
        self.assertEqual(equipment, {
            "infantry_equipment_0": 18000,
            "ADISCORD_squad_weapons_equipment_0": 160,
            "motorized_equipment_1": 120,
        })

    def test_veyr_approaches_match_the_physical_naran_hamad_border(self):
        from tools.builders import build_adiscord_strategic_regions as regions

        types, colors = regions.load_province_definitions()
        neighbors = regions.load_province_adjacency(types, colors, include_special_adjacencies=False)

        def provinces(state_id):
            state = definitions(ROOT / f"history/states/{state_id}-{state_id}.txt")["state"]
            return {int(entry.value) for entry in block(state, "provinces")}

        hamad = provinces(258)
        physical = {p: neighbors[p] & hamad for p in provinces(264) if neighbors[p] & hamad}
        shl = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        gate = block(shl["SHL_rakhma_border_crossing_open"], "OR")
        scripted = {}
        for crossing in gate:
            route = block(crossing.value, "can_build_railway")
            province = int(scalar(route, "target_province"))
            self.assertEqual(scalar(route, "start_province"), "16713")
            staging = block(crossing.value, f"var:global.province_controllers^{province}")
            self.assertEqual(scalar(staging, "SHL_rakhma_staging_controller"), "yes")
            weight = block(route, "controller_priority")
            closed = block(weight, "modifier")
            self.assertEqual(scalar(closed, "SHL_rakhma_transit_controller"), "no")
            self.assertLess(int(scalar(weight, "base")) + int(scalar(closed, "add")), 0)
            self.assertNotIn(province, scripted)
            scripted[province] = {int(e.value) for e in flatten(block(crossing.value, "RHM"))
                                  if e.key == "controls_province"}
        self.assertEqual(scripted, physical)

    def test_shared_settlement_variables_have_native_global_writers(self):
        entries = list(flatten(parse_clausewitz(EFFECTS.read_text(encoding="utf-8"))))
        self.assertFalse(any(entry.key == "set_global_variable" for entry in entries))
        written = {
            field.value
            for entry in entries
            if entry.key == "set_variable"
            for field in entry.value
            if field.key == "var"
        }
        for name in ("declarer_side", "winner_side", "terms", "subject_type"):
            self.assertIn(f"global.ADISCORD_south_{name}", written)
            self.assertNotIn(f"ADISCORD_south_{name}", written)

    def test_every_regional_state_is_woken_bound_offered_and_settled(self):
        for name in (
            "ADISCORD_south_wake_regional_countries",
            "ADISCORD_south_offer_side_choices",
            "ADISCORD_south_faction_partners_follow",
        ):
            calls = set(re.findall(r"\b([A-Z]{3}) = \{", body(EFFECTS, name)))
            self.assertEqual(calls, set(REGIONAL), name)
        bound = scope_calls(body(EFFECTS, "ADISCORD_south_assign_bound_sides"), "ADISCORD_south_bind_to_champion")
        self.assertEqual(bound, set(REGIONAL) | {"NAM"} | FURNACE_ADMINISTRATIONS)
        for name, effect in (
            ("ADISCORD_south_end_final_wars", "ADISCORD_south_end_member_wars"),
            ("ADISCORD_south_mark_losers", "ADISCORD_south_mark_loser"),
            ("ADISCORD_south_clear_participants", "ADISCORD_south_clear_participant"),
            ("ADISCORD_south_apply_settlement", "ADISCORD_south_settle_member"),
        ):
            self.assertEqual(scope_calls(body(EFFECTS, name), effect), set(REGIONAL) | set(CHAMPIONS) | FURNACE_ADMINISTRATIONS, name)
        regional = body(TRIGGERS, "ADISCORD_south_regional_country")
        self.assertEqual(set(re.findall(r"tag = ([A-Z]{3})", regional)), set(REGIONAL))

    def test_minors_are_released_before_any_side_or_war(self):
        for name in ("ADISCORD_south_join_shl_side", "ADISCORD_south_join_north_side", "ADISCORD_south_prepare_champion"):
            source = body(EFFECTS, name).strip()
            self.assertTrue(source.startswith("ADISCORD_release_non_participating_minor_optimization = yes"), name)
        start = body(EFFECTS, "ADISCORD_south_begin_hostilities")
        self.assertLess(start.index("ADISCORD_south_wake_regional_countries = yes"), start.index("declare_war_on"))

    def test_resolution_flag_precedes_every_white_peace(self):
        for name in ("ADISCORD_south_final_resolve_shl_victory", "ADISCORD_south_final_resolve_north_victory", "ADISCORD_south_final_resolve_without_hegemon"):
            source = body(EFFECTS, name)
            self.assertLess(source.index("set_global_flag = ADISCORD_south_final_resolved"), source.index("ADISCORD_south_end_final_wars = yes"), name)
        repel = body(EFFECTS, "ADISCORD_south_final_repel")
        self.assertLess(repel.index("clr_global_flag = ADISCORD_south_final_started"), repel.index("ADISCORD_south_end_final_wars = yes"))

    def test_every_terminal_path_releases_campaign_status(self):
        for name in (
            "ADISCORD_south_final_resolve_shl_victory",
            "ADISCORD_south_final_resolve_north_victory",
            "ADISCORD_south_final_repel",
            "ADISCORD_south_final_resolve_without_hegemon",
        ):
            self.assertIn("ADISCORD_south_close_campaign_state = yes", body(EFFECTS, name), name)
        close = body(EFFECTS, "ADISCORD_south_close_member_state")
        self.assertIn("RUS_crisis_release_other_major = yes", close)
        self.assertLess(close.index("clr_country_flag = ADISCORD_south_added_major"), close.index("RUS_crisis_release_other_major = yes"))
        self.assertIn("ADISCORD_south_remove_path_spirit = yes", close)
        self.assertEqual(scope_calls(body(EFFECTS, "ADISCORD_south_close_campaign_state"), "ADISCORD_south_close_member_state"), {"NAM", "SHL", "EFL", "AZH"})
        spirits = set(re.findall(r"add_ideas = (ADISCORD_south_\w+)", body(EFFECTS, "ADISCORD_south_add_path_spirit")))
        removed = set(re.findall(r"remove_ideas = (ADISCORD_south_\w+)", body(EFFECTS, "ADISCORD_south_remove_path_spirit")))
        # The deadline penalty is timed, but a settled war ends it with the campaign spirits.
        self.assertEqual(spirits | {"ADISCORD_south_unprepared_war"}, removed)

    def test_only_svetlogorye_can_win_the_north_side(self):
        north = body(EFFECTS, "ADISCORD_south_final_resolve_north_victory")
        self.assertIn("ADISCORD_south_north_is_nam = yes", north)
        self.assertIn("ADISCORD_south_final_repel = yes", north)
        self.assertNotIn("ADISCORD_south_hegemon_EFL", EFFECTS.read_text(encoding="utf-8"))
        self.assertNotIn("ADISCORD_south_hegemon_AZH", EFFECTS.read_text(encoding="utf-8"))

    def test_uprising_never_survives_the_settlement(self):
        settlement = body(EFFECTS, "ADISCORD_south_apply_settlement")
        self.assertIn("annex_country = { target = SLF transfer_troops = no }", settlement)

    def test_northern_settlement_opens_the_shahrabad_seal_once(self):
        call = "SHL = { SHL_seal_open_chapter = yes }"
        settlement = body(EFFECTS, "ADISCORD_south_apply_settlement")
        self.assertEqual(settlement.count(call), 1)
        self.assertLess(settlement.rindex("ADISCORD_south_settle_member"), settlement.index(call))
        self.assertNotIn("SHL_seal_open_chapter", body(EFFECTS, "ADISCORD_south_final_repel"))
        # The chapter guards itself: only a Svetlogorye hegemony over its subject opens it, once.
        opening = body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", "SHL_seal_open_chapter")
        for condition in ("has_global_flag = ADISCORD_south_hegemon_NAM", "is_subject_of = NAM",
                          "NOT = { has_country_flag = SHL_seal_chapter_open }"):
            self.assertIn(condition, opening)
        self.assertLess(opening.index("set_country_flag = SHL_seal_chapter_open"), opening.index("SHL_seal_lease_by_terms = yes"))

    def test_each_course_has_one_final_focus(self):
        # Each final lives in the course tree that SHL_political_course selects.
        expected = {
            "SHL_south_oil_for_furnaces": ("1", "SHL_south_great_road"),
            "SHL_south_war_of_charters": ("2", "SHL_south_free_road"),
            "SHL_south_last_pour": ("3", "SHL_south_iron_march"),
            "SHL_south_war_of_arms": ("4", "SHL_south_veyr_debt"),
            "SHL_south_oil_uprising": ("5", "SHL_south_oil_underground"),
        }
        owners = {}
        for path in SHL_TREES:
            if path.parent.name == "shared":
                continue
            for identifier in focus_blocks(path):
                owners[identifier] = shl_tree_course(path)
        for identifier, (course, parent) in expected.items():
            focus = shl_focus_blocks()[identifier]
            text = repr(focus)
            prerequisites = [e.value for e in focus if e.key == "prerequisite"]
            self.assertEqual([[(i.key, i.value) for i in p] for p in prerequisites], [[("focus", parent)]], identifier)
            self.assertEqual(owners[identifier], course, identifier)
            self.assertEqual(owners[parent], course, parent)
            # The section's hidden course check cancels a final in progress after
            # a course switch; it never names another course.
            available = next(e.value for e in focus if e.key == "available")
            hidden = [e.value for e in available if e.key == "hidden_trigger" and "SHL_political_course" in repr(e.value)]
            self.assertEqual(len(hidden), 1, identifier)
            self.assertNotIn("SHL_political_course", repr([e for e in available if e.key != "hidden_trigger"]), identifier)
            self.assertEqual([(e.key, scalar(e.value, "var"), scalar(e.value, "value")) for e in hidden[0]],
                             [("check_variable", "SHL_political_course", course)], identifier)
            self.assertIn("ADISCORD_south_prepare_offensive", text, identifier)
        nam = focus_blocks(ROOT / "focus_trees/NAM/postwar/focuses.txt")
        for identifier, path in (("NAM_south_seal_over_furnaces", "NAM_service_state"), ("NAM_south_oil_charter", "NAM_federal_charter")):
            available = repr(next(e.value for e in nam[identifier] if e.key == "available"))
            self.assertIn(path, available, identifier)
            self.assertIn("ADISCORD_south_final_focus_available", available, identifier)

    def test_champion_capitulation_owns_the_settlement(self):
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN south_final:on_capitulation"):text.index("# END south_final:on_capitulation")]
        self.assertIn("set_global_flag = skip_default_capitulation", section)
        self.assertIn("ADISCORD_south_final_resolve_north_victory = yes", section)
        self.assertIn("ADISCORD_south_final_resolve_shl_victory = yes", section)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            section = text[text.index(f"# BEGIN south_final:{hook}"):text.index(f"# END south_final:{hook}")]
            self.assertIn("ADISCORD_south_final_close_external = yes", section, hook)

    def test_clock_has_one_periodic_driver(self):
        shl = (ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt").read_text(encoding="utf-8")
        self.assertEqual(shl.count("ADISCORD_south_crisis_cycle = yes"), 1)
        self.assertIn("ADISCORD_south_crisis_cycle = yes", body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", "SHL_run_cycle"))
        self.assertNotIn("ADISCORD_south_crisis_add_campaign", shl)
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            self.assertNotIn("ADISCORD_south_crisis", path.read_text(encoding="utf-8-sig"), path.name)

    def test_events_are_registered_and_localised(self):
        source = EVENTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"\bid = (ADISCORD_south\.\d+)", source))
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        registered = {e["id"] for e in registry["events"] if e["namespace"] == "ADISCORD_south"}
        self.assertEqual(defined, registered)
        keys = set(re.findall(r"(?:title|desc|name|text) = (ADISCORD_south\.[\w.]+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            self.assertEqual(sorted(keys - present), [], language)

    def test_campaign_focuses_bypass_exactly_their_targets(self):
        offers = ("ADISCORD_south_demand_submission", "ADISCORD_south_demand_annexation", "ADISCORD_south_offer_alliance")
        target_gate = "ADISCORD_south_campaign_target_valid"

        def closes_when_war_starts(conditions):
            return any(
                inner.key == "has_global_flag" and inner.value == "ADISCORD_south_final_started"
                for entry in flatten(conditions)
                if entry.key == "NOT"
                for inner in flatten(entry.value)
            )

        self.assertTrue(closes_when_war_starts(definitions(TRIGGERS)[target_gate]))
        checked = set()
        for path in (
            *SHL_TREES,
            ROOT / "focus_trees/NAM/postwar/focuses.txt",
            ROOT / "focus_trees/NAM/defeated/focuses.txt",
        ):
            for identifier, focus in focus_blocks(path).items():
                reward = next(e.value for e in focus if e.key == "completion_reward")
                targets = {e.key for e in flatten(reward) if e.key in REGIONAL and isinstance(e.value, list)
                           and any(i.key in offers for i in flatten(e.value))}
                if not targets:
                    continue
                checked.add(identifier)
                bypass = block(focus, "bypass")
                # A bypass may list extra story conditions (partner flag, war
                # started) inside OR; every demand target must still appear.
                bypass_scopes = {e.key for e in flatten(bypass) if e.key in REGIONAL}
                self.assertEqual(targets, bypass_scopes, identifier)
                available = block(focus, "available")
                if not closes_when_war_starts(available):
                    gated = {e.key for e in flatten(available) if e.key in REGIONAL and
                             any(c.key == target_gate and c.value == "yes" for c in flatten(e.value))}
                    self.assertEqual(gated, targets, identifier)
        self.assertTrue({
            "SHL_south_trade_protectorates", "SHL_south_great_road", "SHL_h_kerdan_trading_house",
            "SHL_south_free_road", "SHL_south_water_and_sea", "SHL_south_last_ration",
            "SHL_south_iron_march", "SHL_south_toll_debtors", "SHL_south_veyr_debt",
            "NAM_south_desert_offices", "NAM_kadir_oil_charter",
        }.issubset(checked))

    def test_answers_always_clear_the_pending_offer(self):
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
            self.assertTrue(body(EFFECTS, name).rstrip().endswith("clear_variable = ADISCORD_south_offer_kind"), name)
        refuse = body(EFFECTS, "ADISCORD_south_refuse_offer")
        self.assertIn("check_variable = { var = ADISCORD_south_offer_kind value = 1 compare = equals }", refuse)
        self.assertIn("check_variable = { var = ADISCORD_south_offer_kind value = 2 compare = equals }", refuse)
        self.assertIn("ADISCORD_south_offer_answer_valid = yes", refuse)
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN south_final:on_annex"):text.index("# END south_final:on_annex")]
        self.assertIn("ADISCORD_south_note_campaign_annexation = yes", section)

    def test_refusal_war_settles_on_the_refused_terms(self):
        refuse = body(EFFECTS, "ADISCORD_south_refuse_offer")
        war = refuse.index("declare_war_on")
        for champion in ("SHL", "NAM"):
            for kind in (1, 2):
                record = f"set_country_flag = {{ flag = ADISCORD_south_refused_{champion} value = {kind} }}"
                self.assertLess(refuse.index(record), war, record)
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN south_final:on_capitulation"):text.index("# END south_final:on_capitulation")]
        guard = section.index("NOT = { has_global_flag = skip_default_capitulation }")
        self.assertLess(section.index("ADISCORD_south_final_resolve_shl_victory = yes"), guard)
        self.assertLess(guard, section.index("ADISCORD_south_refusal_capitulation = yes"))
        peace = text[text.index("# BEGIN south_final:on_peace"):text.index("# END south_final:on_peace")]
        self.assertIn("ADISCORD_south_close_refusal_wars = yes", peace)
        dispatch = body(EFFECTS, "ADISCORD_south_refusal_capitulation")
        self.assertEqual(dispatch.count("set_global_flag = skip_default_capitulation"), 4)
        self.assertNotIn("annex_country", dispatch)
        for champion in ("SHL", "NAM"):
            self.assertIn(f"ADISCORD_south_refusal_side_fallen_{champion} = yes", dispatch)
        impose = body(EFFECTS, "ADISCORD_south_impose_refused_terms")
        self.assertLess(impose.index("ADISCORD_south_refusal_annexed value = THIS"), impose.index("white_peace"))
        self.assertEqual(impose.count("annex_country"), 1)
        member = body(EFFECTS, "ADISCORD_south_submit_refusal_member")
        self.assertLess(member.index("white_peace"), member.index("ADISCORD_south_leave_previous_alliance = yes"))
        self.assertLess(member.index("ADISCORD_south_leave_previous_alliance = yes"), member.index("ADISCORD_south.47"))
        self.assertNotIn("puppet", member)
        source = EVENTS.read_text(encoding="utf-8")
        start = source.index("id = ADISCORD_south.47")
        settle = source[start:source.index("\ncountry_event = {", start) if "\ncountry_event = {" in source[start:] else len(source)]
        self.assertLess(settle.index("ADISCORD_south_finalize_submission = yes"), settle.index("ADISCORD_south_restore_peacetime_control = yes"))
        self.assertEqual(settle.count("ADISCORD_south_restore_peacetime_control = yes"), 2)
        self.assertEqual(settle.count("days < 7"), 2)
        recheck = source[source.index("id = ADISCORD_south.48"):]
        for champion in ("SHL", "NAM"):
            self.assertIn(f"ADISCORD_south_refusal_side_fallen_{champion} = yes", recheck)
        for hook in ("on_peace", "on_puppet"):
            section = text[text.index(f"# BEGIN south_final:{hook}"):text.index(f"# END south_final:{hook}")]
            self.assertIn("ADISCORD_south_close_refusal_wars = yes" if hook == "on_peace" else "ADISCORD_south_recheck_held_refusals = yes", section)
        self.assertIn("ADISCORD_south_recheck_held_refusals = yes", body(EFFECTS, "ADISCORD_south_close_refusal_wars"))
        self.assertIn("ADISCORD_south_recheck_held_refusals = yes", body(EFFECTS, "ADISCORD_south_note_campaign_annexation"))
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
            self.assertIn("ADISCORD_south_offer_war_clear = yes", body(EFFECTS, name), name)
        offer = source[source.index("id = ADISCORD_south.40"):source.index("id = ADISCORD_south.41")]
        self.assertEqual(offer.count("ADISCORD_south_offer_war_clear = yes"), 2)
        self.assertEqual(offer.count("ADISCORD_south_offer_war_clear = no"), 1)
        self.assertIsNone(re.search(r"\bADISCORD_south_campaign_target\b", EFFECTS.read_text(encoding="utf-8")))

    def test_commune_uprising_joins_shahrabad_at_war_start(self):
        start = body(EFFECTS, "ADISCORD_south_begin_hostilities")
        self.assertLess(start.index("ADISCORD_south_offer_side_choices = yes"), start.index("ADISCORD_south_raise_oil_uprising = yes"))
        uprising = body(EFFECTS, "ADISCORD_south_raise_oil_uprising")
        self.assertIn("set_variable = { var = ADISCORD_south_side value = 1 }", uprising)
        self.assertIn("targeted_alliance = SHL", uprising)
        self.assertIn("NAM_district_compact", uprising)

    def test_course_mandates_and_wartime_programmes_serve_the_final_war(self):
        shl = body(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt", "SHL_campaign_open")
        self.assertIn("ADISCORD_south_final_active = yes", shl)
        start = body(EFFECTS, "ADISCORD_south_begin_hostilities")
        self.assertIn("SHL_use_campaign_reserve = yes", start)
        self.assertIn("SHL_clean_campaign = yes", body(EFFECTS, "ADISCORD_south_close_campaign_state"))
        nam = body(ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt", "NAM_wartime_programmes_open")
        self.assertIn("ADISCORD_south_final_active = yes", nam)
        self.assertIn("ADISCORD_south_north_leader", nam)
        decisions = definitions(ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt")
        national = {e.key: e.value for e in decisions["NAM_national_programmes"]}
        for name in ("NAM_emergency_arsenal", "NAM_counterinsurgency", "NAM_relief_batch"):
            self.assertIn("NAM_wartime_programmes_open", repr(block(national[name], "available")))

    def test_front_requests_follow_the_current_opposing_side(self):
        policies = definitions(ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt")
        for name in ("ADISCORD_south_coalition_front", "ADISCORD_south_successor_front"):
            request, = (entry.value for entry in policies[name] if entry.key == "ai_strategy"
                        and scalar(entry.value, "type") == "front_unit_request")
            self.assertEqual(scalar(block(request, "country_trigger"), "ADISCORD_south_enemy_front_country"), "yes")
            self.assertGreater(int(scalar(request, "value")), 0)
        for name, entries in policies.items():
            self.assertEqual(scalar(entries, "abort_when_not_enabled"), "yes", name)

    def test_debug_commands_and_decisions_share_guarded_handlers(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(
            (ROOT / "events/ADISCORD_scenario_debug_events.txt").read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        decisions = definitions(ROOT / "common/decisions/ADISCORD_scenario_debug_decisions.txt")
        category = decisions["ADISCORD_scenario_debug_category"]
        for index, short in enumerate(("start_war", "win_nam", "win_shl"), 1):
            name = "ADISCORD_south_debug_" + short
            event = events[f"ADISCORD_south_debug.{index}"]
            self.assertEqual(scalar(event, "hidden"), "yes")
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual([(e.key, e.value) for e in block(event, "immediate")], [(name, "yes")])
            decision = block(category, name)
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(scalar(block(decision, "ai_will_do"), "factor"), "0")
            self.assertIn((name, "yes"), [(e.key, e.value) for e in flatten(block(decision, "complete_effect"))])
            for language in ("russian", "english"):
                raw = (ROOT / f"localisation/{language}/ADISCORD_scenario_debug_l_{language}.yml").read_bytes()
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
                line = next(line for line in raw.decode("utf-8-sig").splitlines() if line.startswith(" " + name + ":"))
                self.assertIn('"§RDEBUG:§! ', line)

    def test_normal_and_debug_start_share_the_complete_hostilities_payload(self):
        effects = definitions(EFFECTS)
        normal = block(effects["ADISCORD_south_final_war_start"], "if")
        self.assertEqual([(e.key, e.value) for e in block(normal, "limit")],
                         [("ADISCORD_south_final_can_start", "yes"), ("ADISCORD_south_declarer_valid", "yes")])
        self.assertEqual([(e.key, e.value) for e in normal if e.key != "limit"],
                         [("ADISCORD_south_begin_hostilities", "yes")])
        common = block(effects["ADISCORD_south_begin_hostilities"], "if")
        self.assertIn("ADISCORD_south_crisis_open", repr(block(common, "limit")))
        self.assertIn("ADISCORD_south_participants_ready", repr(block(common, "limit")))
        self.assertIn("ADISCORD_south_declarer_valid", repr(block(common, "limit")))
        self.assertEqual(scalar(common, "set_global_flag"), "ADISCORD_south_final_started")
        self.assertEqual(sum(e.key == "ADISCORD_south_assign_bound_sides" for e in flatten(common)), 1)
        self.assertEqual(sum(e.key == "ADISCORD_south_record_key_states" for e in flatten(common)), 1)

    def test_war_has_no_deadline_and_only_capitulation_settles_it(self):
        effects = definitions(EFFECTS)
        hostilities = flatten(effects["ADISCORD_south_begin_hostilities"])
        delayed = [e for e in hostilities if e.key == "country_event" and any(item.key == "days" for item in e.value)]
        # The only delayed call is the next-day contest cleanup after the side choice.
        self.assertEqual([(scalar(e.value, "id"), scalar(e.value, "days")) for e in delayed], [("ADISCORD_south.75", "1")])
        events = EVENTS.read_text(encoding="utf-8")
        self.assertNotIn("ADISCORD_south_final_resolve_by_control", events)
        for language in ("russian", "english"):
            raw = (ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml").read_text(encoding="utf-8-sig")
            line = next(line for line in raw.splitlines() if line.startswith(" ADISCORD_south_status_war:"))
            self.assertNotIn("900", line, language)

    def test_champions_record_and_restore_prior_trees_when_still_in_the_war_tree(self):
        from tools.builders.build_adiscord_focus_trees import SHARED_HISTORY_SOURCES, SOURCES
        effects = definitions(EFFECTS)
        hostilities = flatten(effects["ADISCORD_south_begin_hostilities"])
        self.assertEqual(sum(e.key == "ADISCORD_south_load_war_tree" for e in hostilities), 2)
        self.assertIn(("ADISCORD_south_restore_prior_tree", "yes"),
                      [(e.key, e.value) for e in flatten(effects["ADISCORD_south_close_member_state"])])
        self.assertEqual(scope_calls(body(EFFECTS, "ADISCORD_south_close_campaign_state"), "ADISCORD_south_close_member_state"),
                         {"NAM", "SHL", "EFL", "AZH"})
        for terminal in ("ADISCORD_south_final_resolve_shl_victory", "ADISCORD_south_final_resolve_north_victory",
                         "ADISCORD_south_final_repel", "ADISCORD_south_final_resolve_without_hegemon"):
            self.assertIn("ADISCORD_south_close_campaign_state = yes", body(EFFECTS, terminal), terminal)

        def tree_values(source, check):
            pairs = {}
            for entry in flatten(source):
                if entry.key not in ("if", "else_if"):
                    continue
                limit = block(entry.value, "limit")
                trees = [e.value for e in flatten(limit) if e.key == check] if check == "has_focus_tree" else [
                    scalar(e.value, "value") for e in flatten(limit)
                    if e.key == "check_variable" and scalar(e.value, "var") == "ADISCORD_south_prior_tree"]
                loads = [scalar(e.value, "tree") for e in entry.value if e.key == "load_focus_tree"]
                values = [scalar(e.value, "value") for e in entry.value
                          if e.key == "set_variable" and scalar(e.value, "var") == "ADISCORD_south_prior_tree"]
                if len(trees) == 1 and (loads or values):
                    pairs[trees[0]] = (values or loads)[0]
            return pairs

        recorded = tree_values(effects["ADISCORD_south_load_war_tree"], "has_focus_tree")
        recorded.pop("SHL_focus")
        restored = tree_values(effects["ADISCORD_south_restore_prior_tree"], "check_variable")
        restored["6"] = scalar(block(next(e.value for e in flatten(effects["ADISCORD_south_restore_prior_tree"])
                                          if e.key == "else"), "load_focus_tree"), "tree")
        self.assertEqual({value: tree for tree, value in recorded.items()}, restored)
        # Every tree a champion can hold, and both war trees, keep completions across a swap.
        by_tree = {}
        for source in SOURCES:
            path = ROOT / "focus_trees" / source
            text = path.read_text(encoding="utf-8")
            match = re.search(r"(?m)^focus_tree = \{\s*\n\s*id = (\w+)", text)
            if match:
                by_tree[match[1]] = source
        for tree in (*restored.values(), "SHL_focus", "SHL_south_war_focus", "NAM_south_war_focus"):
            self.assertIn(by_tree[tree], SHARED_HISTORY_SOURCES, tree)
        for tree, tag in (("SHL_south_war_focus", "SHL"), ("NAM_south_war_focus", "NAM")):
            source = parse_clausewitz((ROOT / "focus_trees" / by_tree[tree]).read_text(encoding="utf-8"))
            weight = block(block(block(source, "focus_tree"), "country"), "modifier")
            self.assertEqual(scalar(weight, "add"), "200", tree)
            self.assertEqual(scalar(weight, "original_tag"), tag, tree)
            self.assertEqual(scalar(weight, "ADISCORD_south_final_active"), "yes", tree)

    def test_effect_files_have_no_bom(self):
        for path in (EFFECTS, TRIGGERS, EVENTS):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)


class SouthLifecycleTests(unittest.TestCase):
    """Execute bounded clock/objective accounting; native war and event UI remain manual."""

    def setUp(self):
        self.triggers = definitions(TRIGGERS)
        self.triggers.update(definitions(ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt"))
        self.effects = definitions(EFFECTS)
        self.facts = ScenarioFacts()
        self.arrays = {}
        self.calls = []
        self.start_scopes = []
        self.event_root = "SHL"
        self.event_sender = "SHL"
        self.targets = {}
        self.facts[("fixture", "resolve_previous_scope")] = True
        self.facts[("700", "controller")] = "NAM"
        self.facts[("699", "controller")] = "SHL"
        self.facts[("700", "neighbors")] = ("699",)
        self.facts[("699", "neighbors")] = ("700",)
        for tag in ("NAM", "SHL", "EFL", "AZH"):
            self.facts.update({(tag, "exists", "yes"): True, (tag, "is_subject", "no"): True,
                               (tag, "has_capitulated", "no"): True, (tag, "has_war", "no"): True,
                               (tag, "is_in_faction", "no"): True})
        self.set_date(OPENED)
        # on_startup stores the day number of 1 January 2160.
        self.variable("ADISCORD_south_day0", day_number("2160.1.1"))
        for tag, names in {
            "SHL": ("SHL_conclave_army", "SHL_metal_market", "SHL_conclave_rules"),
            "NAM": ("NAM_svetlogorye", "NAM_oil_exchange", "NAM_ladder_of_seals", "NAM_south_desert_offices",
                    "NAM_pw_transport_commission", "NAM_pw_southern_army", "NAM_pw_freight_schedule"),
        }.items():
            for name in names:
                self.facts[(tag, "has_completed_focus", name)] = True
        self.facts[("SHL", "has_country_flag", "SHL_furnaces_initialized")] = True
        for flag in ("ADISCORD_fresh_campaign_contract_v1", "ADISCORD_nam_resource_war_resolved"):
            self.flag(flag)
        self.scheduled = []

    def open_preparation(self, age=180):
        """Open the preparation, age it and enter the early window of its deadline."""
        self.execute("ADISCORD_south_begin_preparation")
        self.assertTrue(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_preparation_started")))
        self.flag("ADISCORD_south_preparation_started", age=age)
        self.enter_early_window()

    def deadline_day(self, suffix=""):
        return self.facts.get(("GLB", "variable", f"ADISCORD_south_deadline{suffix}_day"))

    def enter_early_window(self):
        """Move the calendar to the first day an early start may open its warning."""
        self.set_date(script_date(int(self.deadline_day("_warning"))))

    def anchor(self, window):
        """Set the deadline anchor as a settlement does before it opens the preparation."""
        self.facts.temps["ADISCORD_south_deadline_window"] = window
        self.execute("ADISCORD_south_set_deadline")
        self.facts.temps.clear()

    def ensure_early_window(self):
        """Fixtures that set the preparation flags directly still need an anchor."""
        if self.deadline_day() is None:
            self.anchor(0)
        self.enter_early_window()

    def set_date(self, date):
        for tag in CANDIDATES:
            self.facts[(tag, "numeric", "date")] = numeric_date(date)
        self.variable("num_days", day_number(date))

    def today(self):
        value = self.facts[("SHL", "numeric", "date")]
        return f"{value // 10000}.{value // 100 % 100}.{value % 100}"

    def advance(self, days):
        """Move the calendar and age every set global flag by the same number of days."""
        self.set_date(script_date(day_number(self.today()) + days))
        for key in list(self.facts):
            if key[0] == "GLB" and key[1] == "has_global_flag" and self.facts[key]:
                self.facts[("GLB", "flag_days", key[2])] = self.facts.get(("GLB", "flag_days", key[2]), 0) + days

    def pull(self):
        return self.facts.get(("GLB", "variable", "ADISCORD_south_crisis_pull"), 0)

    def flag(self, name, present=True, age=0):
        self.facts[("GLB", "has_global_flag", name)] = present
        self.facts[("GLB", "flag_days", name)] = age

    def variable(self, name, value, scope="GLB"):
        self.facts[(scope, "variable", name)] = value
        self.facts[(scope, "has_variable", name)] = True

    def expand(self, entries):
        result = []
        for index, entry in enumerate(entries):
            if index >= 2 and entries[index - 2].key == "" and entries[index - 2].value == "date":
                year, month, day = entry.value.split(".")
                entry = replace(entry, value=str(int(year) * 10000 + int(month) * 100 + int(day)))
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"))
                predicate = replace(entry, key="AND", value=self.expand(self.triggers[entry.key]))
                result.append(predicate if entry.value == "yes" else replace(entry, key="NOT", value=[predicate]))
            elif entry.key == "has_global_flag":
                result.append(replace(entry, key="GLB", value=[entry]))
            elif entry.key in ("set_variable", "check_variable") and field_value(entry, "value") in ("ROOT", "FROM"):
                # HOI4 stores country scope references in variables as numeric tag IDs.
                country = self.event_root if scalar(entry.value, "value") == "ROOT" else self.event_sender
                tag_id = str((*CHAMPIONS, *REGIONAL).index(country) + 1)
                fields = [replace(field, value=tag_id) if field.key == "value" else field for field in entry.value]
                result.append(replace(entry, value=fields))
            elif entry.key == "check_variable" and (field_value(entry, "var") or "").startswith("global."):
                fields = [replace(e, value=e.value.removeprefix("global.")) if isinstance(e.value, str) else e
                          for e in entry.value]
                result.append(replace(entry, key="GLB", value=[replace(entry, value=fields)]))
            elif entry.key in ("ROOT", "FROM") or entry.key.startswith("event_target:"):
                target = (self.event_root if entry.key == "ROOT" else self.event_sender if entry.key == "FROM"
                          else self.targets[entry.key.split(":", 1)[1]])
                result.append(replace(entry, key=target, value=self.expand(entry.value)))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            elif entry.value in ("ROOT", "FROM"):
                result.append(replace(entry, value=self.event_root if entry.value == "ROOT" else self.event_sender))
            else:
                result.append(entry)
        return result

    def matches(self, entries, scope="SHL"):
        return matches_conditions(self.expand(entries), self.facts, scope)

    def trigger_matches(self, name, scope="SHL"):
        return self.matches(self.triggers[name], scope)

    def test_second_wave_follows_the_current_ai_champions_and_their_war(self):
        event_id = "ADISCORD_south.7"
        event, = [e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event" and scalar(e.value, "id") == event_id]
        trigger = block(event, "trigger")
        self.assertEqual(scalar(block(event, "immediate"), "ADISCORD_south_raise_second_wave"), "yes")
        prepare = self.effects["ADISCORD_south_prepare_champion"]
        for level in range(5):
            self.facts[("SHL", "numeric", "difficulty")] = level
            calls = [e.value for _, e in selected_effects(prepare, self.facts, "SHL")
                     if e.key == "country_event" and scalar(e.value, "id") == event_id]
            self.assertEqual([scalar(call, "days") for call in calls], ["45"] if level >= 2 else [])
        self.flag("ADISCORD_south_final_started")
        self.variable("ADISCORD_south_side", 1, "SHL")
        for tag in CANDIDATES:
            self.facts.update({
                (tag, "numeric", "difficulty"): 3, (tag, "is_ai", "yes"): True,
                (tag, "owns_state", "700"): True, (tag, "controls_state", "700"): True,
                (tag, "numeric", "has_manpower"): 0, (tag, "equipment", "infantry_equipment"): 0,
                (tag, "equipment", "ADISCORD_squad_weapons_equipment"): 0,
                (tag, "has_war_with", "SHL"): True,
            })
        for north in ("NAM", "EFL", "AZH"):
            self.facts[(north, "has_country_flag", "ADISCORD_south_north_leader")] = True
            for tag in CANDIDATES:
                self.assertEqual(self.matches(trigger, tag), tag in ("SHL", north))
            for scope, key, value in (
                (north, "has_war_with", "SHL"), (north, "has_capitulated", "no"),
                ("SHL", "is_subject", "no"),
            ):
                self.facts[(scope, key, value)] = False
                self.assertFalse(self.matches(trigger, north))
                self.assertFalse(self.matches(trigger, "SHL"))
                self.facts[(scope, key, value)] = True
            for level in range(5):
                for ai in (False, True):
                    self.facts[(north, "numeric", "difficulty")] = level
                    self.facts[(north, "is_ai", "yes")] = ai
                    self.assertEqual(self.matches(trigger, north), ai and level >= 2)
            self.flag("ADISCORD_south_final_resolved")
            self.assertFalse(self.matches(trigger, north))
            self.flag("ADISCORD_south_final_resolved", False)
            self.facts[(north, "has_country_flag", "ADISCORD_south_north_leader")] = False

    def test_second_wave_delivers_ten_militias_and_charges_only_for_regulars(self):
        wave = self.effects["ADISCORD_south_raise_second_wave"]
        regular = "Southern Reserve Regiment"
        militia = "Southern Reserve Militia"
        templates = {scalar(e.value, "name"): [b.key for b in block(e.value, "regiments")]
                     for e in wave if e.key == "division_template"}
        self.assertEqual(templates, {regular: ["infantry"] * 4, militia: ["ADISCORD_militia"] * 3})
        place = scalar(block(wave, "random_owned_controlled_state"), "save_event_target_as")
        self.targets[place] = "699"
        manpower = ("SHL", "numeric", "has_manpower")
        rifles = ("SHL", "equipment", "infantry_equipment")
        squads = ("SHL", "equipment", "ADISCORD_squad_weapons_equipment")
        for level, men, guns, weapons, expected in (
            (2, 0, 0, 0, 0), (2, 0, 14400, 128, 4), (2, 0, 14400, 127.99, 3),
            (2, 32000, 28800, 256, 4), (2, 0, 14399.99, 128, 3),
            (3, 32000, 28800, 256, 7), (4, 28000, 25200, 224, 7),
            (3, 0, 25200, 224, 7), (4, 28000, 25199.99, 224, 6),
            (3, 28000, 25200, 223.99, 6), (4, 4000, 3600, 32, 1), (3, 4000, 3600, 31.99, 0),
            (4, 0, 0, 0, 0),
        ):
            self.facts[("SHL", "numeric", "difficulty")] = level
            self.facts.update({manpower: men, rifles: guns, squads: weapons})
            counts = {regular: 0, militia: 0}
            for scope, e in selected_effects(self.expand(wave), self.facts, "SHL"):
                if e.key == "set_temp_variable":
                    self.variable(scalar(e.value, "var"), int(scalar(e.value, "value")), scope)
                elif e.key == "add_manpower":
                    self.facts[(scope, "numeric", "has_manpower")] += int(e.value)
                elif e.key == "add_equipment_to_stockpile":
                    self.facts[(scope, "equipment", scalar(e.value, "type"))] += int(scalar(e.value, "amount"))
                elif e.key == "create_unit":
                    self.assertEqual((scope, scalar(e.value, "owner")), ("699", "PREV"))
                    unit = parse_clausewitz(scalar(e.value, "division"))
                    for field in ("start_equipment_factor", "start_manpower_factor"):
                        self.assertEqual(float(scalar(unit, field)), 1)
                    counts[scalar(unit, "division_template")] += 1
            self.assertEqual(counts, {regular: expected, militia: 10})
            grant = 30000 if level == 2 else 100000
            self.assertEqual(self.facts[manpower], men + grant - 4000 * expected)
            self.assertEqual(self.facts[rifles], guns - 3600 * expected)
            self.assertEqual(self.facts[squads], weapons - 32 * expected)

    def test_expedition_offer_checks_the_price_of_the_requested_force(self):
        available = block(south_decisions()["ADISCORD_south_request_expedition"], "available")
        self.flag("ADISCORD_south_final_started")
        for champion, side, focus in (
            ("SHL", 1, "SHL_sw_buy_the_sands"),
            ("NAM", 2, "NAM_sw_protectorate_offers"),
        ):
            self.variable("ADISCORD_south_side", side, champion)
            self.variable("ADISCORD_south_side", side, "EFL")
            pending = (champion, "has_country_flag", "ADISCORD_south_expedition_pending")
            self.facts[(champion, "has_country_flag", "ADISCORD_south_north_leader")] = side == 2
            for count in (2, 3):
                self.facts[(champion, "has_completed_focus", focus)] = count == 3
                men, rifles = 3000 * count, 500 * count
                for manpower, stock, ready in (
                    (men, rifles, True),
                    (men - 0.5, rifles, False),
                    (men, rifles - 0.5, False),
                ):
                    with self.subTest(champion=champion, count=count, manpower=manpower, stock=stock):
                        self.facts[("EFL", "numeric", "has_manpower")] = manpower
                        self.facts[("EFL", "equipment", "infantry_equipment")] = stock
                        self.event_root, self.event_sender = champion, "EFL"
                        self.facts[pending] = False
                        checks = [entry for _, entry in selected_effects(self.expand(available), self.facts, champion)]
                        self.assertEqual(matches_conditions(checks, self.facts, champion), ready)
                        self.event_root, self.event_sender = "EFL", champion
                        self.facts[pending] = True
                        self.assertEqual(self.trigger_matches("ADISCORD_south_expedition_possible", "EFL"), ready)

    def test_normalisation_protects_both_neighbours_in_southern_negotiations(self):
        for normalised in (False, True):
            self.facts[("NAM", "has_completed_focus", "NAM_normalisation")] = normalised
            for tag in ("EFL", "AZH", "KDR"):
                self.facts[(tag, "tag", tag)] = True
                self.assertEqual(self.trigger_matches("NAM_neighbour_sovereignty_recognised", tag),
                                 normalised and tag in ("EFL", "AZH"))

    def regional_country(self, country, leader=None):
        for key, value in (("exists", "yes"), ("has_capitulated", "no"), ("is_subject", "no"), ("has_war", "no")):
            self.facts[(country, key, value)] = True
        self.facts[(country, "is_in_faction", "no")] = leader is None
        if leader:
            self.facts[(country, "faction_leader")] = leader
            self.facts[(country, "is_in_faction_with", leader)] = True
            self.facts[(leader, "is_faction_leader", "yes")] = True
            self.facts[(leader, "is_in_faction", "no")] = False

    def test_diplomatic_decisions_require_the_current_leaders_target_focus(self):
        decisions = south_decisions()
        invitation = decisions["ADISCORD_south_invite_to_coalition"]
        influence = decisions["ADISCORD_south_build_coalition_influence"]
        advisers = decisions["ADISCORD_south_send_advisers"]
        protection = decisions["ADISCORD_south_offer_protectorate"]
        for decision in (invitation, influence, advisers, protection):
            self.assertEqual({node.value for node in block(decision, "targets")}, set(REGIONAL))
        self.regional_country("KDR")
        self.regional_country("WEF")
        # The fixture's etatist desert offices would already address Kadir.
        self.facts[("NAM", "has_completed_focus", "NAM_south_desert_offices")] = False
        self.execute("ADISCORD_south_begin_preparation")
        for leader, ally, focus, sign in (("NAM", "RHM", "NAM_insured_caravans", 1),
                                         ("SHL", "MZR", "SHL_south_throne_and_crests", -1)):
            self.regional_country(ally, leader)
            self.variable("ADISCORD_south_coalition_influence", sign * 60, "KDR")
            self.facts[(ally, "has_completed_focus", focus)] = True
            self.event_sender = "KDR"
            for completed in (False, True):
                self.facts[(leader, "has_completed_focus", focus)] = completed
                for envoy in (leader, ally):
                    self.event_root = envoy
                    # The invitation keeps the leader's addressed focus.
                    self.assertEqual(self.matches(block(invitation, "visible"), envoy), completed,
                                     (leader, envoy, completed))
                    # Delegations need only the open contest, and only the champion sends them.
                    self.assertEqual(self.matches(block(influence, "visible"), envoy), envoy == leader,
                                     (leader, envoy, completed))
            self.facts[(leader, "has_completed_focus", focus)] = False

        # On its post-war tree Svetlogorye sends delegations after its foreign
        # office and advisers after its legations.
        self.event_root = "NAM"
        self.event_sender = "KDR"
        self.facts[("NAM", "has_focus_tree", "NAM_postwar_focus")] = True
        for office, legations in ((False, False), (True, False), (True, True)):
            with self.subTest(office=office, legations=legations):
                self.facts[("NAM", "has_completed_focus", "NAM_foreign_office")] = office
                self.facts[("NAM", "has_completed_focus", "NAM_south_legations")] = legations
                self.assertEqual(self.matches(block(influence, "visible"), "NAM"), office)
                self.assertEqual(self.matches(block(advisers, "visible"), "NAM"), legations)
        # Outside the contest window nobody sends them.
        self.flag("ADISCORD_south_preparation_started", False)
        for champion in ("NAM", "SHL"):
            self.event_root = champion
            self.assertFalse(self.matches(block(influence, "visible"), champion), champion)
        self.flag("ADISCORD_south_preparation_started")

        self.event_sender = "KDR"
        self.facts[("NAM", "has_completed_focus", "NAM_insured_caravans")] = True
        self.variable("ADISCORD_south_coalition_influence", 60, "KDR")
        for predecessor, leader in (("NAM", "EFL"), ("EFL", "AZH")):
            self.facts[(predecessor, "is_subject", "no")] = False
            self.facts[(predecessor, "is_subject_of", leader)] = True
            self.event_root = leader
            self.assertFalse(self.matches(block(invitation, "visible"), leader))
            self.facts[(leader, "has_completed_focus", "ADISCORD_south_restitution_contact_kdr")] = True
            self.assertTrue(self.matches(block(invitation, "visible"), leader))

    def test_northern_contacts_unlock_exactly_the_addressed_country(self):
        desert = {"WEF", "KDR", "RHM", "SDR"}
        coast = {"MZR", "KYZ", "GLP"}
        contacts = {
            "NAM_eflor_accord": {"EFL", "AZH"},
            "NAM_border_citizenship": {"EFL", "AZH"},
            "NAM_defeat_open_border": {"EFL"},
            "NAM_defeat_road_south": {"AZH"},
            "NAM_south_desert_envoys": desert,
            "NAM_south_coast_envoys": coast,
            "NAM_south_congress": desert | coast,
            "NAM_south_fenn_guarantee": {"WEF"},
            "NAM_insured_caravans": {"KDR"},
            "NAM_south_desert_offices": {"KDR"},
            "NAM_kadir_oil_charter": {"KDR"},
            "NAM_south_oil_for_water": {"RHM"},
            "NAM_common_fuel_market": {"SDR"},
            "NAM_pw_export_guarantees": {"KYZ"},
            "NAM_contract_bureau": {"KYZ"},
            "NAM_common_citizenship": coast,
            "NAM_island_concession": {"GLP"},
            "NAM_pw_veyr_convoys": {"GLP"},
        }
        self.assertEqual(set().union(*contacts.values()), set(REGIONAL))
        sources = "".join(path.read_text(encoding="utf-8") for path in (ROOT / "focus_trees/NAM").rglob("*.txt"))
        for focus in contacts:
            self.assertRegex(sources, rf"\bid = {focus}\b", focus)
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        trigger = "ADISCORD_south_north_invitation_unlocked"
        for focus, targets in contacts.items():
            with self.subTest(leader="NAM", focus=focus):
                self.facts[("NAM", "has_completed_focus", focus)] = True
                opened = {tag for tag in REGIONAL if self.trigger_matches(trigger, tag)}
                self.assertEqual(opened, targets)
                self.facts[("NAM", "has_completed_focus", focus)] = False
        for leader in ("EFL", "AZH"):
            predecessor = "NAM" if leader == "EFL" else "EFL"
            self.facts[(predecessor, "is_subject", "no")] = False
            self.facts[(predecessor, "is_subject_of", leader)] = True
            self.facts[("NAM", "has_completed_focus", "NAM_south_congress")] = True
            for target in REGIONAL:
                if leader == target:
                    continue
                focus = f"ADISCORD_south_restitution_contact_{target.lower()}"
                with self.subTest(leader=leader, target=target, focus=focus):
                    self.facts[(leader, "has_completed_focus", focus)] = True
                    opened = {tag for tag in REGIONAL if self.trigger_matches(trigger, tag)}
                    self.assertEqual(opened, {target})
                    self.facts[(leader, "has_completed_focus", focus)] = False

    def test_focus_alliance_cannot_import_a_war_with_either_camp(self):
        self.regional_country("KDR")
        self.regional_country("WEF", "NAM")
        self.regional_country("SDR", "SHL")
        for champion in ("NAM", "SHL"):
            for enemy in ("NAM", "SHL", "WEF", "SDR"):
                with self.subTest(champion=champion, enemy=enemy):
                    self.event_root, self.event_sender = champion, champion
                    war = ("KDR", "has_war_with", enemy)
                    self.facts[war] = True
                    self.execute("ADISCORD_south_offer_alliance", "KDR")
                    self.assertFalse(self.facts.get(("KDR", "has_variable", "ADISCORD_south_offer_kind")))
                    self.assertEqual(self.calls, [])
                    self.facts[war] = False
                    self.execute("ADISCORD_south_offer_alliance", "KDR")
                    self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_offer_kind")], 3)
                    self.assertTrue(self.calls)
                    self.calls.clear()
                    self.event_root, self.event_sender = "KDR", champion
                    self.assertTrue(self.trigger_matches("ADISCORD_south_offer_answer_valid", "KDR"))
                    self.facts[war] = True
                    self.assertFalse(self.trigger_matches("ADISCORD_south_offer_answer_valid", "KDR"))
                    self.execute("ADISCORD_south_accept_offer", "KDR")
                    self.assertFalse(self.facts[("KDR", "has_variable", "ADISCORD_south_offer_kind")])
                    self.assertEqual(self.calls, [])
                    self.facts[war] = False

    def test_map_distinguishes_leaders_from_allies_and_northern_successors(self):
        self.facts[("KDR", "exists", "yes")] = True
        self.facts[("KDR", "is_subject_of", "SHL")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_country_shl", "KDR"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_map_country_shl_leader", "KDR"))
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_country_shl_leader", "SHL"))
        for leader, next_leader in (("NAM", "EFL"), ("EFL", "AZH")):
            self.assertTrue(self.trigger_matches("ADISCORD_south_map_country_north_leader", leader))
            self.assertFalse(self.trigger_matches("ADISCORD_south_map_country_north_leader", next_leader))
            self.facts[(leader, "is_subject", "no")] = False
            self.facts[(leader, "is_subject_of", next_leader)] = True
            self.assertTrue(self.trigger_matches("ADISCORD_south_map_country_north", leader))
            self.assertFalse(self.trigger_matches("ADISCORD_south_map_country_north_leader", leader))
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_country_north_leader", "AZH"))

    def test_map_binds_each_flag_to_its_own_influence_marker_and_caption(self):
        gui = definitions(ROOT / "interface/ADISCORD_south_final_war.gui")["guiTypes"]
        window = block(gui, "containerWindowType")
        widgets = {scalar(e.value, "name"): e.value for e in window
                   if e.key in ("containerWindowType", "iconType", "instantTextBoxType")}
        scripted = definitions(ROOT / "common/scripted_guis/ADISCORD_south_final_war_scripted_gui.txt")
        panel = block(scripted["scripted_gui"], "ADISCORD_south_map_panel")
        self.assertEqual(scalar(panel, "window_name"), scalar(window, "name"))
        properties = block(panel, "properties")
        triggers = block(panel, "triggers")
        textures = ROOT / "gfx/interface/south_influence"
        with Image.open(textures / "influence_marker.png") as marker_image:
            tip_offset = marker_image.width // 2
        with Image.open(textures / "influence_track.png") as track_image:
            rail = track_image.convert("RGB")
        tick_positions = [x for x in range(rail.width) if rail.getpixel((x, 2)) == (218, 210, 178)]
        orange, blue = (158, 82, 34), (38, 83, 133)
        for tag in (*CHAMPIONS, *REGIONAL):
            with self.subTest(tag=tag):
                flag = f"ADISCORD_south_map_flag_{tag}"
                self.assertEqual(scalar(widgets[flag], "pdx_tooltip"), f"ADISCORD_south_map_{tag}_tt")
                marker = f"ADISCORD_south_map_marker_{tag}"
                track = f"ADISCORD_south_map_track_{tag}"
                origin = widgets[marker + "_origin"]
                marker_widget = block(origin, "iconType")
                self.assertEqual(scalar(marker_widget, "name"), marker)
                marker_pos = block(marker_widget, "position")
                track_pos = block(widgets[track], "position")
                flag_pos = block(widgets[flag], "position")
                self.assertEqual(scalar(flag_pos, "x"), scalar(track_pos, "x"))
                self.assertLess(int(scalar(flag_pos, "y")), int(scalar(track_pos, "y")))
                self.assertEqual(scalar(block(origin, "position"), "y"), scalar(track_pos, "y"))
                self.assertEqual(scalar(marker_pos, "y"), "0")
                self.assertEqual(scalar(marker_pos, "x"), "0")
                for name in (track, marker):
                    scoped = block(block(triggers, name + "_visible"), tag)
                    self.assertEqual(scalar(scoped, "ADISCORD_south_map_influence_contested"), "yes")

                position_var = scalar(block(properties, marker), "x")
                self.assertEqual(position_var, f"{tag}.ADISCORD_south_coalition_influence?0")
                neutral_tip = int(scalar(block(origin, "position"), "x")) - int(scalar(track_pos, "x")) + tip_offset
                self.assertEqual([neutral_tip + offset for offset in (-60, 0, 60)], tick_positions)
                for score_value in (-100, -20, 15, 62, 74, 100):
                    color = rail.getpixel((neutral_tip + score_value, 5))
                    self.assertEqual(color, orange if score_value < 0 else blue)
                caption = scalar(widgets[f"ADISCORD_south_map_gap_{tag}"], "text")
                for lang in ("russian", "english"):
                    self.assertIn(f"[{tag}.ADISCORDSouthMapStanding]", loc_value(lang, caption))

    def test_map_shows_home_front_strain_from_zero_until_the_front_closes(self):
        gui = definitions(ROOT / "interface/ADISCORD_south_final_war.gui")["guiTypes"]
        window = block(gui, "containerWindowType")
        row = next(e.value for e in window if e.key == "instantTextBoxType"
                   and scalar(e.value, "name") == "ADISCORD_south_map_strain")
        scripted = definitions(ROOT / "common/scripted_guis/ADISCORD_south_final_war_scripted_gui.txt")
        panel = block(scripted["scripted_gui"], "ADISCORD_south_map_panel")
        triggers = block(panel, "triggers")
        strain = "ADISCORD_south_war_strain"
        for points in (None, 0, 73, 100, None):
            self.facts[("NAM", "has_variable", strain)] = points is not None
            if points is not None:
                self.variable(strain, points, "NAM")
            self.assertEqual(self.matches(block(triggers, "ADISCORD_south_map_strain_visible"), "NAM"), points is not None)
            self.assertEqual(self.matches(block(triggers, "ADISCORD_south_map_heading_visible"), "NAM"), points is None)
        for language in ("russian", "english"):
            self.assertIn(f"[?{strain}|0]/100", loc_value(language, scalar(row, "text")))
            detail = loc_value(language, scalar(row, "pdx_tooltip"))
            for field in ("stability", "war_support", "factory"):
                self.assertIn(f"[?ADISCORD_south_strain_{field}|=+1%]", detail)

    def test_map_reports_current_balance_and_existing_allies(self):
        scripted = parse_clausewitz(SCRIPTED_LOC.read_text(encoding="utf-8"))
        displays = {scalar(e.value, "name"): e.value for e in scripted}

        def selected(name):
            return next(scalar(e.value, "localization_key") for e in displays[name]
                        if e.key == "text" and all(self.matches(item.value, "KDR")
                        for item in e.value if item.key == "trigger"))

        self.regional_country("KDR")
        self.event_root, self.event_sender = "NAM", "KDR"
        invitation = south_decisions()["ADISCORD_south_invite_to_coalition"]
        for points, color in ((None, None), (-100, "O"), (-60, "O"), (0, None), (59, "C"),
                              (60, "C"), (62, "C"), (74, "C"), (100, "C")):
            if points is not None:
                self.variable("ADISCORD_south_coalition_influence", points, "KDR")
            for language in ("russian", "english"):
                caption = loc_value(language, selected("ADISCORDSouthMapStanding"))
                self.assertEqual(caption, "[ADISCORDSouthDiplomaticBalance]")
                value = loc_value(language, selected("ADISCORDSouthDiplomaticBalance"))
                expected = f"§{color}[?ADISCORD_south_coalition_influence|0]§!" if color else "0"
                self.assertEqual(value, expected)
            self.assertTrue(self.matches(block(invitation, "visible"), "NAM"))
            self.assertEqual(self.matches(block(invitation, "available"), "NAM"), (points or 0) >= 60)
        for leader, color in (("NAM", "C"), ("SHL", "O")):
            self.regional_country("KDR", leader)
            self.variable("ADISCORD_south_coalition_influence", 62, "KDR")
            self.event_root = leader
            self.assertFalse(self.matches(block(invitation, "visible"), leader))
            for language, ally in (("russian", "Союзник"), ("english", "Ally")):
                self.assertEqual(loc_value(language, selected("ADISCORDSouthMapStanding")),
                                 f"§{color}{ally}§! [ADISCORDSouthDiplomaticBalance]")
            self.facts[("KDR", "is_in_faction_with", leader)] = False

    def test_map_contested_status_follows_targets_and_campaign_lifecycle(self):
        trigger = "ADISCORD_south_map_influence_contested"
        self.regional_country("KDR")
        self.assertTrue(self.trigger_matches(trigger, "KDR"))
        self.assertTrue(self.trigger_matches(trigger, "EFL"))
        for leader in CHAMPIONS:
            self.assertFalse(self.trigger_matches(trigger, leader))
        self.facts[("NAM", "is_subject", "no")] = False
        self.assertFalse(self.trigger_matches(trigger, "EFL"))
        for field, value in (("exists", "yes"), ("is_subject", "no"), ("has_capitulated", "no")):
            self.facts[("KDR", field, value)] = False
            self.assertFalse(self.trigger_matches(trigger, "KDR"), field)
            self.facts[("KDR", field, value)] = True
        self.facts[("KDR", "has_war_with", "SHL")] = True
        self.assertFalse(self.trigger_matches(trigger, "KDR"))
        self.facts[("KDR", "has_war_with", "SHL")] = False
        for flag in ("ADISCORD_south_final_started", "ADISCORD_south_final_resolved"):
            self.flag(flag)
            self.assertFalse(self.trigger_matches(trigger, "KDR"), flag)
            self.flag(flag, False)

    def test_rival_advisers_deliver_only_after_a_valid_mission(self):
        decision = south_decisions()["ADISCORD_south_send_advisers"]
        self.assertEqual(scalar(decision, "days_remove"), "40")
        self.assertEqual(scalar(decision, "days_re_enable"), "35")
        self.regional_country("KDR")
        # No champion has addressed Kadir: the mission needs only the open contest.
        self.facts[("NAM", "has_completed_focus", "NAM_south_desert_offices")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.event_sender = "KDR"
        score = ("KDR", "variable", "ADISCORD_south_coalition_influence")
        experience = ("KDR", "army_experience")
        seeded = self.facts[score]
        self.assertEqual(seeded, -10, "Kadir's home lean")
        self.assertEqual(self.facts[("SHL", "variable", "ADISCORD_south_adviser_push")], 5)
        for sender in ("NAM", "SHL"):
            self.event_root = sender
            power = (sender, "numeric", "has_political_power")
            self.facts[power] = 19.99
            self.execute_entries(block(decision, "complete_effect"), sender)
            self.assertEqual(self.facts[power], 19.99)
            self.facts[power] = 40
            self.assertTrue(self.matches(block(decision, "available"), sender))
            self.execute_entries(block(decision, "complete_effect"), sender)
            self.execute_entries(block(decision, "complete_effect"), sender)
            self.assertEqual(self.facts[power], 20)
            self.assertFalse(self.matches(block(decision, "available"), sender))
            self.assertFalse(self.matches(block(decision, "cancel_trigger"), sender))
        self.assertEqual(self.facts[score], seeded)
        self.assertNotIn(experience, self.facts)
        self.execute_entries(block(decision, "remove_effect"), "SHL")
        self.assertEqual(self.facts[score], seeded - 5)
        self.assertEqual(self.facts[experience], 5)
        self.event_root = "NAM"
        self.facts[("KDR", "has_war_with", "SHL")] = True
        self.assertTrue(self.matches(block(decision, "cancel_trigger"), "NAM"))
        self.execute_entries(block(decision, "cancel_effect"), "NAM")
        self.execute_entries(block(decision, "remove_effect"), "NAM")
        self.assertEqual(self.facts[score], seeded - 5)
        self.assertEqual(self.facts[experience], 5)
        self.assertFalse(self.facts[("KDR", "has_variable", "ADISCORD_south_north_advisers")])

    def test_allied_advisers_need_a_rival_lead_only_at_dispatch(self):
        decision = south_decisions()["ADISCORD_south_send_advisers"]
        self.execute("ADISCORD_south_begin_preparation")
        for leader, ally, sign in (("NAM", "KDR", 1), ("SHL", "WEF", -1)):
            with self.subTest(leader=leader, ally=ally):
                self.regional_country(ally, leader)
                self.event_root, self.event_sender = leader, ally
                power = (leader, "numeric", "has_political_power")
                self.facts[power] = 20
                score = "ADISCORD_south_coalition_influence"
                for balance in (1, 0):
                    self.variable(score, balance * sign, ally)
                    self.assertFalse(self.matches(block(decision, "visible"), leader))
                    self.execute_entries(block(decision, "complete_effect"), leader)
                    self.assertEqual(self.facts[power], 20)

                self.variable(score, -sign, ally)
                self.assertTrue(self.matches(block(decision, "visible"), leader))
                self.execute_entries(block(decision, "complete_effect"), leader)
                self.assertEqual(self.facts[power], 0)
                self.variable(score, sign, ally)
                self.assertTrue(self.matches(block(decision, "visible"), leader))
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), leader))
                self.execute_entries(block(decision, "remove_effect"), leader)
                self.assertEqual(self.facts[(ally, "army_experience")], 5)
                self.assertEqual(self.facts[(ally, "variable", score)], 6 * sign)
                self.assertFalse(self.matches(block(decision, "visible"), leader))

    def test_delegations_to_allies_require_a_current_rival_lead(self):
        decision = south_decisions()["ADISCORD_south_build_coalition_influence"]
        self.execute("ADISCORD_south_begin_preparation")
        for leader, ally, sign in (("NAM", "KDR", 1), ("SHL", "WEF", -1)):
            self.regional_country(ally, leader)
            self.event_root, self.event_sender = leader, ally
            score = (ally, "variable", "ADISCORD_south_coalition_influence")
            power = (leader, "numeric", "has_political_power")
            self.facts[power] = 25
            for balance in (62, 0, -1, 0, 1, -1):
                with self.subTest(leader=leader, balance=balance):
                    self.variable(score[-1], sign * balance, ally)
                    self.assertEqual(self.matches(block(decision, "visible"), leader), balance < 0)
                    if balance >= 0:
                        self.execute_entries(block(decision, "complete_effect"), leader)
                        self.assertEqual(self.facts[score], sign * balance)
                        self.assertEqual(self.facts[power], 25)
            self.execute_entries(block(decision, "complete_effect"), leader)
            self.assertEqual(self.facts[power], 0)
            self.assertGreater(self.facts[score] * sign, 0)
            self.assertFalse(self.matches(block(decision, "visible"), leader))
            self.facts[(ally, "is_in_faction_with", leader)] = False
            self.regional_country(ally)
            self.assertTrue(self.matches(block(decision, "visible"), leader))

    def test_delegations_compete_for_one_target_and_charge_only_valid_sends(self):
        decisions = south_decisions()
        delegates = decisions["ADISCORD_south_build_coalition_influence"]
        invitation = decisions["ADISCORD_south_invite_to_coalition"]
        campaign = block(delegates, "complete_effect")
        self.assertEqual(scalar(delegates, "cost"), "0")
        self.regional_country("KDR")
        self.regional_country("RHM", "NAM")
        self.facts[("NAM", "has_completed_focus", "NAM_insured_caravans")] = True
        self.facts[("SHL", "has_completed_focus", "SHL_south_throne_and_crests")] = True
        self.execute("ADISCORD_south_begin_preparation")
        self.event_sender = "KDR"
        influence = ("KDR", "variable", "ADISCORD_south_coalition_influence")
        for leader, side, sign in (("NAM", "north", 1), ("SHL", "shl", -1)):
            with self.subTest(leader=leader):
                self.event_root = leader
                treasury = (leader, "numeric", "has_political_power")
                cooldown = ("KDR", "has_country_flag", f"ADISCORD_south_{side}_envoys_recent")
                self.assertEqual(self.facts[(leader, "variable", "ADISCORD_south_envoy_push")], 10)
                self.variable(influence[-1], 50 * sign, "KDR")
                self.assertFalse(self.matches(block(invitation, "available"), leader))
                self.facts[treasury] = 24.99
                self.assertFalse(self.matches(block(delegates, "custom_cost_trigger"), leader))
                self.execute_entries(campaign, leader)
                self.assertEqual(self.facts[treasury], 24.99)
                self.assertEqual(self.facts[influence], 50 * sign)
                self.facts[treasury] = 25
                self.assertTrue(self.matches(block(delegates, "custom_cost_trigger"), leader))
                self.execute_entries(campaign, leader)
                self.assertEqual(self.facts[treasury], 0)
                self.assertEqual(self.facts[influence], 60 * sign)
                self.assertTrue(self.facts[cooldown])
                self.assertEqual(self.facts[("KDR", "flag_duration", cooldown[-1])], 56)
                self.assertTrue(self.matches(block(invitation, "available"), leader))

                self.facts[treasury] = 25
                self.assertFalse(self.matches(block(delegates, "available"), leader))
                self.execute_entries(campaign, leader)
                self.assertEqual(self.facts[treasury], 25)
                self.assertEqual(self.facts[influence], 60 * sign)
                if leader == "NAM":
                    # A faction partner acts through its champion.
                    self.event_root = "RHM"
                    self.assertFalse(self.matches(block(delegates, "visible"), "RHM"))
                opponent = "SHL" if leader == "NAM" else "NAM"
                self.event_root = opponent
                self.facts[(opponent, "numeric", "has_political_power")] = 25
                self.assertTrue(self.matches(block(delegates, "available"), opponent))
                self.execute_entries(campaign, opponent)
                self.assertEqual(self.facts[influence], 50 * sign)
                self.event_root = leader
                self.assertFalse(self.matches(block(invitation, "available"), leader))

                self.variable(influence[-1], 95 * sign, "KDR")
                self.facts[cooldown] = False
                self.execute_entries(campaign, leader)
                self.assertEqual(self.facts[influence], 100 * sign)
                self.facts[treasury] = 25
                self.facts[cooldown] = False
                self.assertFalse(self.matches(block(delegates, "available"), leader))
                self.execute_entries(campaign, leader)
                self.assertEqual(self.facts[treasury], 25)
                for flag in ("north", "shl"):
                    self.facts[("KDR", "has_country_flag", f"ADISCORD_south_{flag}_envoys_recent")] = False

    def test_envoy_reserves_one_recipient_and_consent_names_the_actual_leader(self):
        invitation = south_decisions()["ADISCORD_south_invite_to_coalition"]
        self.execute("ADISCORD_south_begin_preparation")
        self.calls.clear()
        self.event_root, self.event_sender = "WEF", "KDR"
        for tag in ("WEF", "KDR"):
            for key, value in (("exists", "yes"), ("is_subject", "no"), ("has_capitulated", "no")):
                self.facts[(tag, key, value)] = True
        self.facts[("WEF", "is_in_faction_with", "SHL")] = True
        self.facts[("KDR", "is_in_faction_with", "NAM")] = True
        self.facts[("KDR", "faction_leader")] = "NAM"
        self.facts[("SHL", "has_completed_focus", "SHL_south_throne_and_crests")] = True
        self.variable("ADISCORD_south_coalition_influence", -60, "KDR")
        send = block(block(invitation, "complete_effect"), "hidden_effect")
        self.execute_entries(send, "WEF")
        self.assertEqual(self.calls, [("KDR", "country_event", "ADISCORD_south.67", "WEF",
                                      {"ADISCORD_south_inviting_leader": "SHL"})])
        self.assertTrue(self.facts[("KDR", "has_variable", "ADISCORD_south_coalition_envoy")])
        self.assertFalse(self.matches(block(invitation, "available"), "WEF"))
        self.execute_entries(send, "WEF")
        self.assertEqual(len(self.calls), 1)

        self.event_root, self.event_sender = "KDR", "WEF"
        reject, accept = [e.value for e in self.event(67) if e.key == "option"]
        guard = block(accept, "trigger")
        self.assertTrue(self.matches(guard, "KDR"))
        payload = self.expand(block(accept, "hidden_effect"))
        def join_orders():
            return [(scope, e.value) for scope, e in selected_effects(payload, self.facts, "KDR")
                    if e.key == "add_to_faction"]
        self.assertEqual(join_orders(), [("SHL", "KDR")])
        self.event_root, self.event_sender = "NAM", "KDR"
        self.facts[("NAM", "has_completed_focus", "NAM_insured_caravans")] = True
        self.facts[("NAM", "numeric", "has_political_power")] = 25
        delegates = south_decisions()["ADISCORD_south_build_coalition_influence"]
        self.assertTrue(self.matches(block(delegates, "available"), "NAM"))
        self.execute_entries(block(delegates, "complete_effect"), "NAM")
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_coalition_influence")], -50)
        self.event_root, self.event_sender = "KDR", "WEF"
        self.assertFalse(self.matches(guard, "KDR"))
        self.assertEqual(join_orders(), [])
        self.variable("ADISCORD_south_coalition_influence", -60, "KDR")
        self.facts[("KDR", "has_war_with", "SHL")] = True
        self.assertFalse(self.matches(guard, "KDR"))
        self.assertEqual(join_orders(), [])
        self.facts[("KDR", "has_war_with", "SHL")] = False
        self.facts[("WEF", "is_in_faction_with", "SHL")] = False
        self.facts[("WEF", "is_in_faction_with", "NAM")] = True
        self.assertFalse(self.matches(guard, "KDR"))
        self.assertEqual(join_orders(), [])
        self.variable("ADISCORD_south_offer_kind", 2, "KDR")
        self.execute_entries(block(reject, "hidden_effect"), "KDR")
        self.assertFalse(self.facts[("KDR", "has_variable", "ADISCORD_south_coalition_envoy")])
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_offer_kind")], 2)
        self.assertTrue(self.facts[("KDR", "is_in_faction_with", "NAM")])

    def test_declining_an_open_invitation_blocks_the_camp_for_ninety_days(self):
        decision = south_decisions()["ADISCORD_south_invite_to_coalition"]
        self.regional_country("KDR")
        self.regional_country("RHM", "NAM")
        self.facts[("NAM", "has_completed_focus", "NAM_insured_caravans")] = True
        self.variable("ADISCORD_south_coalition_influence", 60, "KDR")
        self.event_root, self.event_sender = "RHM", "KDR"
        self.execute_entries(block(decision, "complete_effect"), "RHM")
        self.event_root, self.event_sender = "KDR", "RHM"
        reject = next(e.value for e in self.event(67) if e.key == "option")
        self.execute_entries(block(reject, "hidden_effect"), "KDR")
        self.assertEqual(self.facts[("KDR", "flag_duration", "ADISCORD_south_north_offer_declined")], 90)
        for sender in ("NAM", "RHM"):
            self.event_root, self.event_sender = sender, "KDR"
            self.assertFalse(self.matches(block(decision, "available"), sender))
            self.execute_entries(block(decision, "complete_effect"), sender)
        self.assertEqual(len(self.calls), 1)

    def test_northern_invitation_cannot_pull_shahrabads_war_into_the_coalition(self):
        decision = south_decisions()["ADISCORD_south_invite_to_coalition"]
        self.regional_country("KDR")
        self.regional_country("SDR", "SHL")
        self.event_root, self.event_sender = "NAM", "KDR"
        self.facts[("NAM", "has_completed_focus", "NAM_insured_caravans")] = True
        self.variable("ADISCORD_south_coalition_influence", 60, "KDR")
        for enemy in ("SHL", "SDR"):
            self.facts[("KDR", "has_war_with", enemy)] = True
            self.execute_entries(block(decision, "complete_effect"), "NAM")
            self.assertEqual(self.calls, [], enemy)
            self.assertFalse(self.facts.get(("KDR", "has_variable", "ADISCORD_south_coalition_envoy")))
            self.facts[("KDR", "has_war_with", enemy)] = False
        self.execute_entries(block(decision, "complete_effect"), "NAM")
        self.assertEqual([(scope, kind, event) for scope, kind, event, *_ in self.calls],
                         [("KDR", "country_event", "ADISCORD_south.67")])
        self.event_root, self.event_sender = "KDR", "NAM"
        answer = next(e.value for e in self.event(67) if e.key == "option" and
                      scalar(e.value, "name") == "ADISCORD_south.67.b")
        self.assertTrue(self.matches(block(answer, "trigger"), "KDR"))
        self.facts[("KDR", "has_war_with", "SHL")] = True
        self.assertFalse(self.matches(block(answer, "trigger"), "KDR"))
        self.assertFalse(any(e.key == "add_to_faction" for _, e in
                             selected_effects(self.expand(block(answer, "hidden_effect")), self.facts, "KDR")))

    def test_wartime_defection_requires_opposing_camps_and_uses_the_leaders_programme(self):
        decision = south_decisions()["ADISCORD_south_court_defector"]
        self.flag("ADISCORD_south_final_started")
        self.facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")] = True
        for tag, side in (("SHL", 1), ("WEF", 1), ("NAM", 2), ("KDR", 2)):
            self.facts[(tag, "exists", "yes")] = True
            self.facts[(tag, "is_subject", "no")] = True
            self.facts[(tag, "has_capitulated", "no")] = True
            self.variable("ADISCORD_south_side", side, tag)
        for envoy, target, leader, programme in (
            ("WEF", "KDR", "SHL", "SHL_sw_southern_league"),
            ("KDR", "WEF", "NAM", "NAM_sw_league_of_the_north"),
        ):
            with self.subTest(envoy=envoy):
                self.event_root, self.event_sender = envoy, target
                self.facts[(envoy, "has_war_with", target)] = True
                self.assertFalse(self.matches(block(decision, "visible"), envoy))
                self.facts[(leader, "has_completed_focus", programme)] = True
                self.assertTrue(self.matches(block(decision, "allowed"), envoy))
                self.assertTrue(self.matches(block(decision, "visible"), envoy))
                self.facts[(target, "has_country_flag", "ADISCORD_south_defected")] = True
                self.assertFalse(self.matches(block(decision, "visible"), envoy))
                self.facts[(target, "has_country_flag", "ADISCORD_south_defected")] = False
                self.facts[(leader, "has_completed_focus", programme)] = False

    def test_map_shades_follow_control_in_war_and_ownership_after_peace(self):
        self.flag("ADISCORD_south_final_started")
        self.variable("ADISCORD_south_side", 1, "SHL")
        self.variable("ADISCORD_south_side", 2, "NAM")
        self.variable("ADISCORD_south_side", 2, "EFL")
        self.facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")] = True
        self.facts[("NAM", "has_capitulated", "no")] = False
        self.facts[("699", "owner")] = "SHL"
        self.facts[("699", "controller")] = "EFL"
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_state_north", "699"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_map_state_north_leader", "699"))
        self.facts[("699", "controller")] = "NAM"
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_state_north_leader", "699"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_map_state_shl_leader", "699"))
        self.flag("ADISCORD_south_final_resolved")
        self.assertTrue(self.trigger_matches("ADISCORD_south_map_state_shl_leader", "699"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_map_state_north_leader", "699"))

    def execute(self, name, scope="SHL"):
        self.execute_entries(self.effects[name], scope)

    def resolve(self, reference, scope):
        """Numeric value of a literal, temp, global, scoped or own variable reference."""
        try:
            return float(reference)
        except ValueError:
            holder, _, name = reference.partition(".")
            if name and holder in ("ROOT", "FROM"):
                reference = f"{self.event_root if holder == 'ROOT' else self.event_sender}.{name}"
            return self.facts.get((scope, "variable", reference), 0)

    def change_variable(self, entry, scope):
        operation = entry.key.removesuffix("_variable").removesuffix("_temp")
        name = scalar(entry.value, "var")
        if entry.key.endswith("_temp_variable"):
            old = self.facts.temps.get(name, 0)
        else:
            holder = "GLB" if name.startswith("global.") else scope
            name = name.removeprefix("global.")
            old = self.facts.get((holder, "variable", name), 0)
        if operation == "clamp":
            bounds = {e.key: self.resolve(e.value, scope) for e in entry.value if e.key in ("min", "max")}
            value = min(bounds.get("max", old), max(bounds.get("min", old), old))
        else:
            value = VARIABLE_OPERATIONS[operation](old, self.resolve(scalar(entry.value, "value"), scope))
        if entry.key.endswith("_temp_variable"):
            self.facts.temps[name] = value
        else:
            self.variable(name, value, holder)

    def execute_entries(self, entries, scope):
        terminals = {"ADISCORD_south_final_resolve_shl_victory", "ADISCORD_south_final_resolve_north_victory",
                     "ADISCORD_south_final_resolve_without_hegemon", "ADISCORD_south_final_repel",
                     "ADISCORD_south_final_war_start"}
        for current, entry in selected_effects(self.expand(entries), self.facts, scope):
            if entry.key == "ADISCORD_south_final_war_start":
                if self.trigger_matches("ADISCORD_south_final_can_start", current) and self.trigger_matches("ADISCORD_south_declarer_valid", current):
                    self.calls.append(entry.key)
                    self.start_scopes.append(current)
            elif entry.key in terminals:
                self.calls.append(entry.key)
            elif entry.key in self.effects:
                self.execute(entry.key, current)
            elif entry.key in ("set_global_flag", "clr_global_flag"):
                self.flag(entry.value, entry.key == "set_global_flag")
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                if isinstance(entry.value, list):
                    flag = scalar(entry.value, "flag")
                    self.facts[(current, "flag_duration", flag)] = int(scalar(entry.value, "days"))
                else:
                    flag = entry.value
                self.facts[(current, "has_country_flag", flag)] = entry.key == "set_country_flag"
            elif entry.key == "add_political_power":
                self.facts[(current, "numeric", "has_political_power")] += float(entry.value)
            elif entry.key == "army_experience":
                self.facts[(current, "army_experience")] = self.facts.get((current, "army_experience"), 0) + int(entry.value)
            elif entry.key.removesuffix("_variable").removesuffix("_temp") in VARIABLE_OPERATIONS:
                self.change_variable(entry, current)
            elif entry.key == "round_variable":
                holder = "GLB" if entry.value.startswith("global.") else current
                name = entry.value.removeprefix("global.")
                self.variable(name, float(int(self.facts.get((holder, "variable", name), 0) + 0.5)), holder)
            elif entry.key == "clear_variable":
                holder = "GLB" if entry.value.startswith("global.") else current
                name = entry.value.removeprefix("global.")
                self.facts.pop((holder, "variable", name), None)
                self.facts[(holder, "has_variable", name)] = False
            elif entry.key == "add_to_array":
                self.assertEqual(scalar(entry.value, "value"), "THIS")
                self.arrays.setdefault(scalar(entry.value, "array"), []).append(current)
            elif entry.key == "clear_array":
                self.arrays[entry.value] = []
            elif entry.key == "for_each_scope_loop":
                for target in list(self.arrays.get(scalar(entry.value, "array"), [])):
                    self.execute_entries([e for e in entry.value if e.key != "array"], target)
            elif entry.key == "capital_scope":
                self.execute_entries(entry.value, self.facts[(current, "capital")])
            elif entry.key in ("activate_mission", "remove_mission"):
                self.facts[(current, "mission", entry.value)] = entry.key == "activate_mission"
                self.calls.append((current, entry.key, entry.value))
            elif entry.key == "add_timed_idea":
                idea = scalar(entry.value, "idea")
                self.facts[(current, "has_idea", idea)] = True
                self.calls.append((current, entry.key, idea, int(scalar(entry.value, "days"))))
            elif entry.key == "remove_ideas":
                self.facts[(current, "has_idea", entry.value)] = False
            elif entry.key == "save_event_target_as":
                self.targets[entry.value] = current
            elif entry.key == "country_event":
                self.calls.append((current, "country_event", scalar(entry.value, "id"), self.event_root, dict(self.targets)))
                delay = {e.key: int(e.value) for e in entry.value if e.key in ("days", "hours")}
                self.scheduled.append((current, scalar(entry.value, "id"), delay))
            elif entry.key == "add_to_war":
                self.calls.append((current, "add_to_war", scalar(entry.value, "targeted_alliance"), scalar(entry.value, "enemy")))
            elif entry.key == "ADISCORD_economy_mark_dirty":
                self.calls.append((current, entry.key))
            elif entry.key == "add_equipment_to_stockpile":
                stock = (current, "equipment", scalar(entry.value, "type"))
                self.facts[stock] = self.facts.get(stock, 0) + float(scalar(entry.value, "amount"))
            elif entry.key in ("add_fuel", "add_stability", "add_war_support", "add_command_power"):
                self.facts[(current, entry.key)] = self.facts.get((current, entry.key), 0) + float(entry.value)
            elif entry.key == "add_power_balance_value":
                self.calls.append((current, entry.key))
            elif entry.key == "custom_effect_tooltip":
                continue
            else:
                self.assertIn(entry.key, ("news_event", "mark_focus_tree_layout_dirty", "ADISCORD_release_non_participating_minor_optimization"), entry.key)

    def test_debug_start_skips_calendar_focuses_and_warning_but_uses_shl_as_declarer(self):
        for tag in ("NAM", "SHL"):
            self.facts[(tag, "numeric", "date")] = 21600101
        for key in list(self.facts):
            if key[1] == "has_completed_focus":
                self.facts[key] = False
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_oil_peace")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "SHL"))
        self.assertTrue(self.trigger_matches("ADISCORD_south_debug_start_ready", "SHL"))
        for scope in ("NAM", "SHL"):
            chosen = list(selected_effects(self.expand(self.effects["ADISCORD_south_debug_start_war"]), self.facts, scope))
            self.assertEqual([(current, entry.key) for current, entry in chosen],
                             [("SHL", "ADISCORD_south_begin_hostilities")])

    def test_debug_start_cannot_replace_lifecycle_or_restart_a_settled_war(self):
        for blocked in ("resource_open", "story", "started", "resolved", "world_ended",
                        "nam_missing", "nam_subject", "nam_war", "shl_missing", "shl_subject", "shl_war", "shl_uninitialized"):
            self.setUp()
            if blocked == "resource_open":
                self.flag("ADISCORD_nam_resource_war_resolved", False)
            elif blocked == "story":
                self.flag("ADISCORD_nam_resource_war_island_exile")
            elif blocked in ("started", "resolved"):
                self.flag("ADISCORD_south_final_" + blocked)
            elif blocked == "world_ended":
                self.flag("RUS_crisis_world_ended")
            elif blocked == "shl_uninitialized":
                self.facts[("SHL", "has_country_flag", "SHL_furnaces_initialized")] = False
            else:
                tag, condition = blocked.split("_")
                predicate, value = {"missing": ("exists", "yes"), "subject": ("is_subject", "no"),
                                    "war": ("has_war", "no")}[condition]
                self.facts[(tag.upper(), predicate, value)] = False
            self.assertFalse(self.trigger_matches("ADISCORD_south_debug_start_ready"), blocked)
            chosen = list(selected_effects(self.expand(self.effects["ADISCORD_south_debug_start_war"]), self.facts, "NAM"))
            self.assertEqual(chosen, [], blocked)

    def test_debug_victories_require_the_current_campaign_and_real_winner(self):
        for active, resolved, nam_leads, shl_exists in ((True, False, True, True), (False, False, True, True),
                                                     (True, True, True, True), (True, False, False, True),
                                                     (True, False, True, False)):
            self.flag("ADISCORD_south_final_started", active)
            self.flag("ADISCORD_south_final_resolved", resolved)
            self.facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")] = nam_leads
            self.facts[("SHL", "exists", "yes")] = shl_exists
            for short, production, exists in (("win_nam", "north", nam_leads), ("win_shl", "shl", shl_exists)):
                chosen = list(selected_effects(self.expand(self.effects["ADISCORD_south_debug_" + short]), self.facts, "NAM"))
                expected = ["ADISCORD_south_final_resolve_" + production + "_victory"] if active and not resolved and exists else []
                self.assertEqual([entry.key for _, entry in chosen], expected, (short, active, resolved, exists))

    def test_preparation_age_and_focus_readiness_block_every_starter(self):
        self.variable("ADISCORD_south_crisis", 100)
        self.execute("ADISCORD_south_begin_preparation")
        self.ensure_early_window()
        self.flag("ADISCORD_south_crisis_warned", age=84)
        for age, expected in ((179, False), (180, True)):
            self.flag("ADISCORD_south_preparation_started", age=age)
            for tag in ("NAM", "SHL", "EFL", "AZH"):
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), expected)
            self.calls.clear()
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, expected)
        for tag, focus in (("NAM", "NAM_svetlogorye"), ("NAM", "NAM_oil_exchange"), ("SHL", "SHL_conclave_army"), ("SHL", "SHL_metal_market")):
            self.facts[(tag, "has_completed_focus", focus)] = False
            for declarer in ("NAM", "SHL", "EFL", "AZH"):
                self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", declarer), (tag, focus, declarer))
            self.facts[(tag, "has_completed_focus", focus)] = True

    def test_focus_completion_opens_warning_without_new_postwar_timer(self):
        self.open_preparation()
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_crisis_warned")])
        self.assertNotIn("ADISCORD_south_final_war_start", self.calls)
        for age in (0, 55, 56):
            self.flag("ADISCORD_south_crisis_warned", age=age)
            self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start"), age >= 56)

    def test_cancelled_resource_entry_has_attainable_main_tree_milestones(self):
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        self.flag("ADISCORD_nam_resource_war_resolved", False)
        self.flag("ADISCORD_nam_resource_war_retry_used")
        for name in ("NAM_seal_courts", "NAM_civilian_combine", "NAM_officer_courses"):
            self.facts[("NAM", "has_completed_focus", name)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.flag("ADISCORD_nam_resource_war_scheduled")
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))

    def test_offensive_focus_fits_warning_and_selects_northern_declarer(self):
        self.open_preparation()
        self.execute("ADISCORD_south_crisis_cycle")
        for path in (ROOT / "focus_trees/NAM/postwar/focuses.txt", ROOT / "focus_trees/NAM/defeated/focuses.txt",
                     ROOT / "focus_trees/NAM/mainland_directory/focuses.txt", *SHL_TREES):
            for name, focus in focus_blocks(path).items():
                if "ADISCORD_south_prepare_offensive" not in repr(block(focus, "completion_reward")):
                    continue
                self.assertIn("ADISCORD_south_final_focus_available", repr(block(focus, "available")), name)
                self.assertLessEqual(float(scalar(focus, "cost")) * 7, 56, name)
        self.assertTrue(self.trigger_matches("ADISCORD_south_final_focus_available", "NAM"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "NAM"))
        self.execute("ADISCORD_south_prepare_offensive", "NAM")
        self.assertTrue(self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")])
        for age in (42, 55, 56):
            self.calls.clear()
            self.flag("ADISCORD_south_crisis_warned", age=age)
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, age >= 56)
        dispatcher = body(EFFECTS, "ADISCORD_south_dispatch_prepared_war")
        self.assertIn("has_country_flag = ADISCORD_south_offensive_order", dispatcher)
        self.assertIn("NAM = { ADISCORD_south_final_war_start = yes }", dispatcher)
        self.assertEqual(self.start_scopes, ["NAM"])
        self.execute("ADISCORD_south_suspend_preparation")
        self.assertFalse(self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")])
        self.open_preparation()
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.start_scopes.clear()
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, [])
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, ["SHL"], "A historical or bypassed focus cannot repeat an expired order")

    def test_shl_order_starts_after_warning_instead_of_waiting_for_automatic_attack(self):
        self.open_preparation()
        self.execute("ADISCORD_south_crisis_cycle")
        self.execute("ADISCORD_south_prepare_offensive", "SHL")
        self.assertEqual(self.start_scopes, [])
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, ["SHL"])

    def test_missing_focus_is_not_replaced_by_preparation_age_or_spare_equipment(self):
        # Before the crisis deadline only the focuses open the warning.
        self.execute("ADISCORD_south_begin_preparation")
        self.facts[("SHL", "has_completed_focus", "SHL_conclave_army")] = False
        self.variable("ADISCORD_south_crisis", 100)
        self.set_date("2166.2.28")
        self.flag("ADISCORD_south_preparation_started", age=3000)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_crisis_warned"), False))
        self.facts[("SHL", "has_completed_focus", "SHL_conclave_army")] = True
        self.facts[("NAM", "numeric", "has_manpower")] = 0
        self.facts[("SHL", "equipment", "infantry_equipment")] = 0
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_crisis_warned")])

    def test_every_rom_course_waits_for_its_diplomatic_preparation(self):
        for capstone, foreign in (("NAM_ladder_of_seals", "NAM_south_desert_offices"),
                                  ("NAM_common_fuel_market", "NAM_south_oil_for_water"),
                                  ("NAM_balanced_accounts", "NAM_prag_partner_supply")):
            for key in list(self.facts):
                if key[0] == "NAM" and key[1] == "has_completed_focus":
                    self.facts[key] = False
            for name in ("NAM_svetlogorye", "NAM_oil_exchange", capstone,
                         "NAM_pw_transport_commission", "NAM_pw_southern_army", "NAM_pw_freight_schedule"):
                self.facts[("NAM", "has_completed_focus", name)] = True
            self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"), capstone)
            self.facts[("NAM", "has_completed_focus", foreign)] = True
            self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"), capstone)

    def test_focus_routes_and_successors_have_reachable_alternatives(self):
        self.facts[("NAM", "has_completed_focus", "NAM_ladder_of_seals")] = False
        self.facts[("NAM", "has_completed_focus", "NAM_common_fuel_market")] = True
        self.facts[("NAM", "has_completed_focus", "NAM_south_oil_for_water")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = False
        for focus in ("NAM_rad_great_war_plan", "NAM_hum_union_call"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
            self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"), focus)
            self.facts[("NAM", "has_completed_focus", focus)] = False
        for focus in ("NAM_defeat_revenge", "NAM_defeat_second_chapter"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_second_chapter")] = False
        for focus in ("NAM_defeat_rump_cabinet", "NAM_defeat_harbour_economy", "NAM_defeat_road_south"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_both_focus_ready"))
        self.facts[("EFL", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_both_focus_ready"))
        self.facts[("AZH", "exists", "yes")] = False
        self.assertFalse(self.trigger_matches("ADISCORD_south_both_focus_ready"))

    def test_compromise_preparation_waits_for_diplomacy_before_the_warning(self):
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        for name in ("NAM_defeat_rump_cabinet", "NAM_defeat_harbour_economy",
                     "NAM_defeat_open_border", "NAM_defeat_oil_union", "NAM_defeat_oil_peace"):
            self.facts[("NAM", "has_completed_focus", name)] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_road_south")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        tree = focus_blocks(ROOT / "focus_trees/NAM/defeated/focuses.txt")
        offensive = tree["NAM_defeat_southern_charter"]
        for prerequisite in (entry.value for entry in offensive if entry.key == "prerequisite"):
            self.assertTrue(any(self.facts.get(("NAM", "has_completed_focus", child.value), False)
                                for child in prerequisite))
        self.assertLessEqual(float(scalar(offensive, "cost")) * 7, 56)

    def test_northern_successors_require_resource_war_settlement(self):
        self.facts[("NAM", "exists", "yes")] = False
        self.flag("ADISCORD_nam_resource_war_resolved", False)
        self.flag("ADISCORD_nam_resource_war_retry_used")
        for leader in ("EFL", "AZH"):
            with self.subTest(leader=leader):
                self.facts[("EFL", "exists", "yes")] = leader == "EFL"
                self.assertTrue(self.trigger_matches("ADISCORD_south_declarer_valid", leader))
                self.assertFalse(self.trigger_matches("ADISCORD_south_north_focus_ready", leader))
                self.flag("ADISCORD_nam_resource_war_resolved")
                self.assertTrue(self.trigger_matches("ADISCORD_south_north_focus_ready", leader))
                self.flag("ADISCORD_nam_resource_war_resolved", False)

    def test_oil_peace_blocks_northern_offensives_without_stopping_shahrabad(self):
        tree = focus_blocks(ROOT / "focus_trees/NAM/defeated/focuses.txt")
        self.assertEqual(scalar(block(tree["NAM_defeat_oil_peace"], "mutually_exclusive"), "focus"), "NAM_defeat_southern_charter")
        self.assertEqual(scalar(block(tree["NAM_defeat_southern_charter"], "mutually_exclusive"), "focus"), "NAM_defeat_oil_peace")
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_oil_peace")] = True
        self.open_preparation()
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.assertTrue(self.trigger_matches("ADISCORD_south_preparing_country", "NAM"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_focus_available", "NAM"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "NAM"))
        self.assertTrue(self.trigger_matches("ADISCORD_south_final_can_start", "SHL"))
        self.execute("ADISCORD_south_prepare_offensive", "NAM")
        self.assertFalse(self.facts.get(("NAM", "has_country_flag", "ADISCORD_south_offensive_order"), False))
        self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")] = True
        self.execute("ADISCORD_south_dispatch_prepared_war")
        self.assertEqual(self.start_scopes, ["SHL"], "An invalid northern order must not block the southern attack")

    def test_prewar_production_needs_a_viable_opponent_on_both_sides(self):
        gate = "ADISCORD_south_preparing_country"
        self.open_preparation()
        self.assertTrue(self.trigger_matches(gate, "SHL"))
        self.facts[("SHL", "has_capitulated", "no")] = False
        self.assertFalse(self.trigger_matches(gate, "NAM"))
        self.facts[("SHL", "has_capitulated", "no")] = True
        for tag in ("NAM", "EFL", "AZH"):
            self.assertTrue(self.trigger_matches(gate, tag))
            self.facts[(tag, "is_subject", "no")] = False
            self.assertFalse(self.trigger_matches(gate, tag))
        self.assertFalse(self.trigger_matches(gate, "SHL"))

    def test_northern_successors_wait_for_minimum_preparation_and_every_shl_milestone(self):
        self.facts[("NAM", "exists", "yes")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.ensure_early_window()
        self.flag("ADISCORD_south_crisis_warned", age=84)
        for leader in ("EFL", "AZH"):
            with self.subTest(leader=leader):
                self.facts[("EFL", "exists", "yes")] = leader == "EFL"
                for age, expected in ((179, False), (180, True)):
                    self.flag("ADISCORD_south_preparation_started", age=age)
                    for starter in (leader, "SHL"):
                        self.assertEqual(self.trigger_matches("ADISCORD_south_final_focus_available", starter), expected)
                        self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", starter), expected)
                    self.calls.clear()
                    self.execute("ADISCORD_south_crisis_cycle")
                    self.assertEqual("ADISCORD_south_final_war_start" in self.calls, expected)
                for focus in ("SHL_conclave_rules", "SHL_metal_market", "SHL_conclave_army"):
                    self.facts[("SHL", "has_completed_focus", focus)] = False
                    for starter in (leader, "SHL"):
                        self.assertFalse(self.trigger_matches("ADISCORD_south_final_focus_available", starter), focus)
                        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", starter), focus)
                    self.calls.clear()
                    self.execute("ADISCORD_south_crisis_cycle")
                    self.assertNotIn("ADISCORD_south_final_war_start", self.calls, focus)
                    self.facts[("SHL", "has_completed_focus", focus)] = True

    def test_repeated_initialization_preserves_age_and_does_not_reactivate_missions(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_preparation_started", age=200)
        self.calls.clear()
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.facts[("GLB", "flag_days", "ADISCORD_south_preparation_started")], 200)
        self.assertEqual(self.calls, [])
        self.execute("ADISCORD_south_suspend_preparation")
        for tag in ("NAM", "SHL", "EFL", "AZH"):
            self.assertFalse(self.facts[(tag, "mission", "ADISCORD_south_preparation")])
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.facts[("GLB", "flag_days", "ADISCORD_south_preparation_started")], 0)

    def test_first_land_contact_starts_one_clock_for_both_coalitions(self):
        clock = "ADISCORD_south_preparation_started"
        # Svetlogorye's victory anchored the deadline; it passed before the first contact.
        self.set_date("2163.1.1")
        self.anchor(VICTORY_WINDOW)
        self.set_date("2167.1.1")
        for state, controller in (("700", "KDR"), ("699", "WEF")):
            self.facts[(state, "controller")] = controller
            self.facts[(controller, "exists", "yes")] = True
        self.facts[("700", "owner")] = "NAM"
        self.facts[("699", "owner")] = "SHL"
        self.facts[("KDR", "is_subject_of", "NAM")] = True
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", clock), False))
        self.assertFalse(self.scheduled)
        self.assertFalse(self.start_scopes)

        self.facts[("WEF", "is_in_faction_with", "SHL")] = True
        self.execute("ADISCORD_south_begin_preparation")
        self.assertTrue(self.facts[("GLB", "has_global_flag", clock)])
        self.assertEqual([target for target, event, _ in self.scheduled
                          if event == "ADISCORD_south.6"], ["SHL", "NAM"])
        self.scheduled.clear()
        self.advance(179)
        self.facts[("WEF", "is_in_faction_with", "SHL")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.execute("ADISCORD_south_check_deadline")
        self.assertFalse(self.deadline_passed())
        self.assertEqual(self.facts[("GLB", "flag_days", clock)], 179)
        self.assertFalse(self.scheduled)
        self.advance(1)
        self.execute("ADISCORD_south_check_deadline")
        self.assertTrue(self.deadline_passed())

    def test_strait_adjacency_and_isolated_coasts_do_not_start_the_clock(self):
        for south_state, north_state in (("28", "44"), ("65", "179"), ("225", "690")):
            with self.subTest(south=south_state, north=north_state):
                self.setUp()
                self.facts[("699", "neighbors")] = ()
                self.facts[("700", "neighbors")] = ()
                self.facts[(south_state, "controller")] = "SHL"
                self.facts[(north_state, "controller")] = "NAM"
                self.facts[(north_state, "neighbors")] = (south_state,)
                self.facts[(south_state, "neighbors")] = (north_state,)
                self.assertFalse(self.trigger_matches("ADISCORD_south_sides_share_border"))

    def test_unopposed_settlement_has_a_separate_clock_while_no_northern_government_exists(self):
        for tag in ("NAM", "EFL", "AZH"):
            self.facts[(tag, "exists", "yes")] = False
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_unopposed_since")])
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_preparation_started"), False))
        self.advance(179)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_final_resolved"), False))
        self.advance(1)
        cycle = self.expand(self.effects["ADISCORD_south_crisis_cycle"])
        chosen = {(e.key, e.value) for _, e in selected_effects(cycle, self.facts, "SHL")
                  if isinstance(e.value, str)}
        self.assertIn(("set_global_flag", "ADISCORD_south_unopposed"), chosen)
        self.assertFalse(self.start_scopes)
        self.facts[("EFL", "exists", "yes")] = True
        self.execute("ADISCORD_south_begin_preparation")
        self.assertFalse(self.facts[("GLB", "has_global_flag", "ADISCORD_south_unopposed_since")])
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_preparation_started"), False))

    def test_exile_return_and_great_war_block_every_clock_and_first_strike(self):
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.flag("ADISCORD_south_preparation_started", age=2000)
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.variable("ADISCORD_south_crisis", 100)
        self.facts.update({("RHM", "exists", "yes"): True, ("RHM", "is_subject", "no"): True,
                           ("RHM", "has_capitulated", "no"): True})
        for phase in ("islands", "return", "consolidation", "great_war", "complete"):
            self.flag("NAM_war_of_return_started", phase == "return")
            self.flag("NAM_war_of_return_won", phase in ("consolidation", "great_war", "complete"))
            self.flag("NAM_great_war_started", phase == "great_war")
            self.flag("NAM_great_war_won", phase == "complete")
            if phase == "complete":
                self.ensure_early_window()
            self.calls.clear()
            for tag in ("NAM", "SHL"):
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), phase == "complete", phase)
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, phase == "complete", phase)
        # The council's desert question lapsed: the freeze ends with an emirate still independent.
        self.flag("NAM_great_war_won", False)
        self.assertTrue(self.trigger_matches("NAM_great_war_target_left", "NAM"))
        for lapsed in (False, True):
            self.flag("NAM_mdr_desert_lapsed", lapsed)
            self.calls.clear()
            for tag in ("NAM", "SHL"):
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), lapsed, ("lapsed", lapsed))
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, lapsed, ("lapsed", lapsed))
        self.flag("NAM_mdr_desert_lapsed", False)
        self.facts[("RHM", "exists", "yes")] = False
        self.facts[("EFL", "exists", "yes")] = False
        self.facts[("AZH", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_crisis_open"), "No remaining great-war opponents")

    def test_directory_mazar_uses_the_shared_queue(self):
        tree = focus_blocks(ROOT / "focus_trees/NAM/mainland_directory/focuses.txt")
        effects = definitions(EFFECTS)
        for name, shared in (("NAM_mdr_mazar_alliance", "ADISCORD_south_offer_alliance"),
                             ("NAM_mdr_mazar_protectorate", "ADISCORD_south_demand_submission")):
            with self.subTest(focus=name):
                self.assertIn(shared, effects)
                focus = tree[name]
                self.assertIn("NAM_mdr_south_open", [e.key for e in walk(block(focus, "available"))])
                # MZR blocks inside a limit (MZR = { exists = yes }) are conditions, not calls.
                calls = [e.value for e in walk(block(focus, "completion_reward"))
                         if e.key == "MZR" and isinstance(e.value, list)
                         and shared in [row.key for row in e.value]]
                self.assertIn("yes", [scalar(call, shared) for call in calls])
        # The Directory's chancery spent a season with the khan: Mazar answers both offers more readily.
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        accept = next(e.value for e in events["ADISCORD_south.40"]
                      if e.key == "option" and scalar(e.value, "name") == "ADISCORD_south.40.a")
        courted = [row.value for row in block(accept, "ai_chance") if row.key == "modifier"
                   and ("tag", "MZR") in [(e.key, e.value) for e in row.value]]
        self.assertEqual(len(courted), 1)
        self.assertEqual(scalar(courted[0], "add"), "25")
        self.assertEqual(scalar(block(courted[0], "FROM"), "has_completed_focus"), "NAM_mdr_mazar_question")
        self.assertEqual(scalar(block(courted[0], "FROM"), "tag"), "NAM")
        # A country that submits to the council of boards becomes a company district, whatever mandate flag is set.
        for mandate in ("service", "pragmatic", "district"):
            self.triggers[f"NAM_prewar_{mandate}_mandate"] = parse_clausewitz(f"has_country_flag = test_{mandate}_mandate")
            self.facts[("NAM", "has_country_flag", f"test_{mandate}_mandate")] = True
        self.facts[("EFL", "tag", "EFL")] = True
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_NAM")] = True
        for corporate in (False, True):
            with self.subTest(corporate=corporate):
                self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = corporate
                chosen = [(scope, e.key) for scope, e in self.submission_effects("EFL")]
                self.assertEqual(("EFL", "NAM_wor_federal_district_join") in chosen, corporate)
                self.assertEqual(any(key == "set_autonomy" for _, key in chosen), not corporate)
                self.assertIn(("NAM", "puppet"), chosen)
                if corporate:
                    self.assertLess(chosen.index(("NAM", "puppet")), chosen.index(("EFL", "NAM_wor_federal_district_join")))
        for language in ("russian", "english"):
            keys = loc_keys(language)
            for key in ("ADISCORD_south.40.d_submit_directory", "ADISCORD_south.40.d_alliance_directory",
                        "ADISCORD_south.40.t_directory_protection", "ADISCORD_south.40.d_directory_protection"):
                self.assertIn(key, keys, (language, key))

    def test_directory_path_spirit_and_terms(self):
        effects = definitions(EFFECTS)
        self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
        for shares, spirit in ((True, "ADISCORD_south_path_NAM_shares"), (False, "ADISCORD_south_path_NAM_boards")):
            with self.subTest(shares=shares):
                self.facts[("NAM", "has_completed_focus", "NAM_mdr_mainland_shares")] = shares
                chosen = [e.value for _, e in selected_effects(self.expand(effects["ADISCORD_south_add_path_spirit"]),
                                                               self.facts, "NAM") if e.key == "add_ideas"]
                self.assertEqual(chosen, [spirit])
        self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = False
        chosen = [e.value for _, e in selected_effects(self.expand(effects["ADISCORD_south_add_path_spirit"]),
                                                       self.facts, "NAM") if e.key == "add_ideas"]
        self.assertEqual(chosen, [], "Only the council of boards takes the Directory's spirits")
        removed = [e.value for e in effects["ADISCORD_south_remove_path_spirit"] if e.key == "remove_ideas"]
        ideas = definitions(ROOT / "common/ideas/ADISCORD_south_final_war_ideas.txt")
        country = block(ideas["ideas"], "country")
        for spirit in ("ADISCORD_south_path_NAM_boards", "ADISCORD_south_path_NAM_shares"):
            self.assertIn(spirit, removed)
            idea = block(country, spirit)
            self.assertEqual(scalar(block(idea, "allowed"), "original_tag"), "NAM")
            for hook in ("on_add", "on_remove"):
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in walk(block(idea, hook))], (spirit, hook))
            for language in ("russian", "english"):
                self.assertTrue({spirit, spirit + "_desc"} <= loc_keys(language), (spirit, language))

        # North victory: the council sequesters every loser on both courses and loads its
        # dominion tree; the republic keeps its terms and loads the heritage tree.
        victory = block(effects["ADISCORD_south_final_resolve_north_victory"], "if")
        settlement = [e for e in victory if e.key != "limit"]
        self.flag("ADISCORD_south_hegemon_NAM")
        for corporate, shares in ((False, False), (True, True), (True, False)):
            with self.subTest(corporate=corporate, shares=shares):
                self.facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = corporate
                self.facts[("NAM", "has_completed_focus", "NAM_mdr_mainland_shares")] = shares
                chosen = list(selected_effects(self.expand(settlement), self.facts, "GLB"))
                values = {}
                for _, entry in chosen:
                    if entry.key == "set_variable":
                        values[scalar(entry.value, "var")] = scalar(entry.value, "value")
                terms = values["global.ADISCORD_south_terms"]
                subject_type = values["global.ADISCORD_south_subject_type"]
                self.assertEqual((terms, subject_type), ("2", "7") if corporate else ("2", "0"))
                loads = [scalar(e.value, "tree") for scope, e in chosen if e.key == "load_focus_tree"]
                self.assertEqual(loads, [] if corporate else ["NAM_south_heritage_focus"])
                keys = [e.key for _, e in chosen]
                self.assertEqual("NAM_hgm_begin" in keys, corporate)
                if corporate:
                    self.assertIn(("NAM", "NAM_hgm_begin"), [(scope, e.key) for scope, e in chosen])
                    self.assertLess(keys.index("NAM_hgm_begin"), keys.index("ADISCORD_south_close_campaign_state"))
                self.assertLess(keys.index("ADISCORD_south_show_svetlogorye_victory"), keys.index("ADISCORD_south_close_campaign_state"))
        # Terms 1 annexes every loser; subject type 7 sequesters each for the partition.
        self.variable("ADISCORD_south_subject_type", 7)
        chosen = [e.key for _, e in selected_effects(self.expand(effects["ADISCORD_south_apply_subject_type"]), self.facts, "SHL")]
        self.assertEqual(chosen, ["NAM_ptn_sequester"])
        self.variable("ADISCORD_south_terms", 1)
        self.event_root = "NAM"
        self.facts[("SHL", "has_country_flag", "ADISCORD_south_settlement_pending")] = True
        chosen = [e.key for _, e in selected_effects(self.expand(effects["ADISCORD_south_settle_member"]), self.facts, "SHL")]
        self.assertIn("annex_country", chosen)
        self.assertNotIn("ADISCORD_south_apply_subject_type", chosen)
        for key in ("ADISCORD_south.31.d_nam_partition",):
            for language in ("russian", "english"):
                self.assertIn(key, loc_keys(language), (language, key))
            self.assertIn(f"text = {key}", EVENTS.read_text(encoding="utf-8"))
        for key in ("ADISCORD_south.31.d_nam_directory_shares", "ADISCORD_south.31.d_nam_directory_union"):
            for language in ("russian", "english"):
                self.assertNotIn(key, loc_keys(language), (language, key))
            self.assertNotIn(key, EVENTS.read_text(encoding="utf-8"))

    def test_north_victory_partitions_for_the_council(self):
        effects = definitions(EFFECTS)
        victory = block(effects["ADISCORD_south_final_resolve_north_victory"], "if")
        steps = [e for e in victory if e.key != "limit"]
        keys = [e.key for e in steps]
        # The resolved flag precedes every peace; the losers are marked and the campaign
        # closes only after the NAM block that loads the next tree.
        self.assertLess(keys.index("set_global_flag"), keys.index("ADISCORD_south_end_final_wars"))
        nam_blocks = [index for index, e in enumerate(steps) if e.key == "NAM"]
        load_block = next(index for index in nam_blocks
                          if "ADISCORD_south_show_svetlogorye_victory" in [e.key for e in steps[index].value])
        self.assertLess(keys.index("ADISCORD_south_mark_losers"), load_block)
        self.assertLess(load_block, keys.index("ADISCORD_south_close_campaign_state"))
        branches = [e for e in steps[load_block].value if e.key in ("if", "else_if", "else")]
        self.assertEqual([e.key for e in branches], ["if", "else"])
        guard, = block(branches[0].value, "limit")
        self.assertEqual(guard.key, "NOT")
        self.assertEqual([(e.key, e.value) for e in guard.value], [("has_country_flag", "NAM_corp_takeover")])
        self.assertEqual(scalar(block(branches[0].value, "load_focus_tree"), "tree"), "NAM_south_heritage_focus")
        self.assertEqual([(e.key, e.value) for e in branches[1].value], [("NAM_hgm_begin", "yes")])
        # One subject type row for the council on both courses; the terms stay at puppets.
        council = [e.value for e in steps if e.key == "if"
                   and "NAM_corp_takeover" in repr(block(e.value, "limit"))]
        self.assertEqual(len(council), 1)
        self.assertEqual([(e.key, scalar(e.value, "var"), scalar(e.value, "value")) for e in council[0] if e.key != "limit"],
                         [("set_variable", "global.ADISCORD_south_subject_type", "7")])
        self.assertNotIn("NAM_mdr_mainland_shares", repr(victory))
        self.assertNotIn("subject_type value = 6", body(EFFECTS, "ADISCORD_south_apply_subject_type"))
        # Day 1: each loser is sequestered; a sequestered Shahrabad skips the seal and the
        # table opens after the Svetlogorsk annexation and the administrations, before the
        # participants are cleared.
        settle = effects["ADISCORD_south_apply_settlement"]
        settle_keys = [e.key for e in settle]
        seal = [e.value for e in settle if e.key == "if" and "SHL_seal_open_chapter" in repr(e.value)]
        self.assertEqual(len(seal), 1)
        self.assertIn("SHL = { NOT = { has_country_flag = NAM_ptn_sequestered } }",
                      body(EFFECTS, "ADISCORD_south_apply_settlement"))
        self.assertEqual(scalar(block(seal[0], "SHL"), "SHL_seal_open_chapter"), "yes")
        table = [index for index, e in enumerate(settle) if e.key == "if" and "NAM_ptn_open_table" in repr(e.value)]
        self.assertEqual(len(table), 1)
        slf = next(index for index, e in enumerate(settle) if e.key == "if" and "SLF" in repr(block(e.value, "limit")))
        furnaces = next(index for index, e in enumerate(settle) if e.key == "if"
                        and "SHL_form_furnace_administrations" in repr(e.value))
        self.assertLess(slf, table[0])
        self.assertLess(furnaces, table[0])
        self.assertLess(table[0], settle_keys.index("ADISCORD_south_clear_participants"))
        self.variable("ADISCORD_south_subject_type", 7)
        self.assertEqual([e.key for _, e in selected_effects(self.expand([settle[table[0]]]), self.facts, "NAM")],
                         ["NAM_ptn_open_table"])
        self.variable("ADISCORD_south_subject_type", 0)
        self.assertEqual(list(selected_effects(self.expand([settle[table[0]]]), self.facts, "NAM")), [])
        for sequestered in (False, True):
            self.facts[("SHL", "has_country_flag", "NAM_ptn_sequestered")] = sequestered
            opened = [e.key for _, e in selected_effects(self.expand(settle), self.facts, "NAM")
                      if e.key == "SHL_seal_open_chapter"]
            self.assertEqual(opened, [] if sequestered else ["SHL_seal_open_chapter"], sequestered)
        # The news names the partition and the dominion tree.
        news, = [e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                 if e.key == "news_event" and scalar(e.value, "id") == "ADISCORD_south.31"]
        partition = [d for d in news if d.key == "desc" and scalar(d.value, "text") == "ADISCORD_south.31.d_nam_partition"]
        self.assertEqual(len(partition), 1)
        self.facts[("GLB", "has_global_flag", "ADISCORD_south_hegemon_NAM")] = True
        for subject_type in (0, 3, 7):
            self.variable("ADISCORD_south_subject_type", subject_type)
            self.assertEqual(self.matches(block(partition[0].value, "trigger"), "NAM"), subject_type == 7, subject_type)
        option = block(news, "option")
        rows = [e for e in option if e.key in ("if", "else_if", "else")]
        self.assertEqual([e.key for e in rows], ["if", "else_if"])
        self.assertEqual(scalar(block(block(rows[1].value, "limit"), "hidden_trigger"), "has_focus_tree"),
                         "NAM_southern_dominion_focus")
        self.assertEqual(scalar(rows[1].value, "custom_effect_tooltip"), "NAM_hgm_dominion_unlocked_tt")

    def test_charter_relieves_strain(self):
        member = definitions(EFFECTS)["ADISCORD_south_strain_cycle_member"]
        relief = next(e.value for e in walk(member) if e.key == "if"
                      and any(row.key == "subtract_from_temp_variable" for row in e.value))
        limit = block(relief, "limit")
        for tag, focus, expected in (("NAM", "NAM_mdr_northern_charter", True),
                                     ("NAM", "NAM_sw_district_compact_at_war", True),
                                     ("SHL", "NAM_mdr_northern_charter", False),
                                     ("NAM", None, False)):
            with self.subTest(tag=tag, focus=focus):
                self.setUp()
                for key in list(self.facts):
                    if key[1] == "has_completed_focus":
                        self.facts[key] = False
                if focus:
                    self.facts[(tag, "has_completed_focus", focus)] = True
                self.assertEqual(self.matches(limit, tag), expected)
        self.assertEqual([e.value for e in relief if e.key == "subtract_from_temp_variable"
                          and scalar(e.value, "var") == "ADISCORD_south_strain_delta"], [relief[-1].value])
        self.assertEqual(scalar(relief[-1].value, "value"), "1")

    def test_directory_readiness_invitations_and_rising(self):
        triggers = definitions(TRIGGERS)
        readiness = block(triggers["ADISCORD_south_nam_focus_ready"], "OR")
        branch, = [e.value for e in readiness if e.key == "AND"
                   and ("has_completed_focus", "NAM_mdr_southern_districts") in [(row.key, row.value) for row in e.value]]
        self.assertEqual(sorted(e.value for e in block(branch, "OR")),
                         ["NAM_mdr_national_war", "NAM_mdr_southern_charter"])
        counted = block(branch, "calc_true_if")
        self.assertEqual(scalar(counted, "amount"), "2")
        self.assertEqual(sorted(e.value for e in counted if e.key == "has_completed_focus"),
                         ["NAM_mdr_army_of_the_south", "NAM_mdr_arsenal_of_the_directory",
                          "NAM_mdr_northern_charter", "NAM_mdr_rear_of_the_south"])
        tree = focus_blocks(ROOT / "focus_trees/NAM/mainland_directory/focuses.txt")
        named = {e.value for e in walk(branch) if e.key == "has_completed_focus"}
        self.assertLessEqual(named, set(tree))
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        self.facts[("NAM", "has_completed_focus", "NAM_mdr_southern_charter")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"),
                         "Without the South open no capstone makes the Directory ready")
        # The chancery opens every contact; Fenn also needs the guarantee.
        trigger = "ADISCORD_south_north_invitation_unlocked"
        self.facts[("NAM", "has_completed_focus", "NAM_mdr_southern_chancery")] = True
        self.assertEqual({tag for tag in REGIONAL if self.trigger_matches(trigger, tag)}, set(REGIONAL) - {"WEF"})
        self.facts[("NAM", "has_completed_focus", "NAM_mdr_fenn_guarantee")] = True
        self.assertEqual({tag for tag in REGIONAL if self.trigger_matches(trigger, tag)}, set(REGIONAL))
        self.facts[("NAM", "has_completed_focus", "NAM_mdr_southern_chancery")] = False
        self.assertEqual({tag for tag in REGIONAL if self.trigger_matches(trigger, tag)}, set())
        # The elected home districts deny the underground its rising, as the district compact does.
        uprising = definitions(EFFECTS)["ADISCORD_south_raise_oil_uprising"]
        outer = block(uprising, "if")
        compact = next(e.value for e in outer if e.key == "if")
        for flag, focus, expected in ((False, False, False), (True, False, True), (False, True, True)):
            self.facts[("NAM", "has_country_flag", "NAM_district_compact")] = flag
            self.facts[("NAM", "has_completed_focus", "NAM_mdr_home_districts")] = focus
            self.assertEqual(self.matches(block(compact, "limit"), "GLB"), expected, (flag, focus))
        for language in ("russian", "english"):
            self.assertIn("ADISCORD_south.44.d_directory", loc_keys(language))

    def test_directory_stages_on_the_mainland_road(self):
        policies = definitions(ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt")
        island = block(policies["ADISCORD_south_nam_staging_reserve"], "enable")
        self.assertIn("NAM_corp_takeover", [e.value for e in block(island, "NOT") if e.key == "has_country_flag"])
        enabled = {}
        for name, states in (("ADISCORD_south_nam_directory_staging", ["240"]),
                             ("ADISCORD_south_nam_directory_resan_staging", ["240", "269"])):
            policy = policies[name]
            self.assertEqual(scalar(block(policy, "allowed"), "tag"), "NAM")
            self.assertEqual(scalar(policy, "abort_when_not_enabled"), "yes")
            enable = block(policy, "enable")
            self.assertEqual([e.value for e in enable if not e.key], ["difficulty", ">", "2"])
            self.assertEqual(scalar(enable, "ADISCORD_south_ai_border_preparation"), "yes")
            self.assertEqual(scalar(enable, "has_country_flag"), "NAM_corp_takeover")
            reserve = block(policy, "ai_strategy")
            self.assertEqual(scalar(reserve, "type"), "put_unit_buffers")
            self.assertEqual([e.value for e in block(reserve, "states")], states)
            self.assertEqual(float(scalar(reserve, "ratio")), 0.15)
            enabled[name] = [e for e in enable if e.key in ("240", "269", "NOT")]
        # Exactly one of the two reserves holds, so the Directory never buffers twice.
        # EFL and MZR are the Directory's districts here; GLP and SHL are not.
        for damir in ("NAM", "EFL", "GLP"):
            for resan in ("NAM", "MZR", "SHL"):
                for node in (0, 1):
                    facts = {("fixture", "resolve_previous_scope"): True, ("240", "controller"): damir,
                             ("269", "controller"): resan, ("240", "numeric", "supply_node"): node,
                             ("EFL", "is_subject_of", "NAM"): True, ("MZR", "is_subject_of", "NAM"): True}
                    held = [name for name, rows in enabled.items() if matches_conditions(rows, facts, "NAM")]
                    damir_ours = damir in ("NAM", "EFL")
                    resan_ours = resan in ("NAM", "MZR")
                    expected = [] if not (damir_ours and node) else (
                        ["ADISCORD_south_nam_directory_resan_staging"] if resan_ours else ["ADISCORD_south_nam_directory_staging"])
                    self.assertEqual(held, expected, (damir, resan, node))

    def test_dead_exile_releases_fallback_but_living_capitulated_exile_does_not(self):
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.facts[("NAM", "has_capitulated", "no")] = False
        self.assertFalse(self.trigger_matches("ADISCORD_south_crisis_open"))
        self.facts[("NAM", "exists", "yes")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.assertTrue(self.trigger_matches("ADISCORD_south_crisis_open"))
        self.execute("ADISCORD_south_select_north_leader")
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_north_leader")])
        self.assertFalse(self.facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")])
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start"))
        self.flag("ADISCORD_south_preparation_started", age=1460)
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.ensure_early_window()
        self.assertTrue(self.trigger_matches("ADISCORD_south_final_can_start"))

    def objectives(self, north="NAM", capital="700"):
        self.facts[(north, "has_country_flag", "ADISCORD_south_north_leader")] = True
        self.variable("ADISCORD_south_side", 2, north)
        self.variable("ADISCORD_south_side", 1, "SHL")
        self.facts[(north, "capital")] = capital
        self.facts[("SHL", "capital")] = "699"
        for state in ("67", "688", capital):
            self.facts[(state, "controller")] = north
        for state in ("699", "707"):
            self.facts[(state, "controller")] = "SHL"
        self.execute("ADISCORD_south_record_key_states")

    def test_subjugated_nam_joins_its_champion_and_counts_for_objectives_and_settlement(self):
        for north, capital in (("EFL", "68"), ("AZH", "69")):
            for overlord in (north, "SHL"):
                for already_fighting in (False, True):
                    with self.subTest(north=north, overlord=overlord, already_fighting=already_fighting):
                        self.setUp()
                        self.facts[("NAM", "is_subject", "no")] = False
                        self.facts[("NAM", "is_subject", "yes")] = True
                        self.facts[("NAM", "is_subject_of", overlord)] = True
                        self.objectives(north, capital)
                        enemy = north if overlord == "SHL" else "SHL"
                        side = 1 if overlord == "SHL" else 2
                        self.facts[("NAM", "has_war_with", enemy)] = already_fighting
                        self.execute("ADISCORD_south_assign_bound_sides")
                        self.assertEqual(self.facts.get(("NAM", "variable", "ADISCORD_south_side")), side)
                        expected_calls = [] if already_fighting else [("NAM", "add_to_war", overlord, enemy)]
                        self.assertEqual(self.calls, expected_calls)
                        self.calls.clear()
                        self.execute("ADISCORD_south_assign_bound_sides")
                        self.assertEqual(self.calls, [], "An assigned participant must not join again")

                        self.facts[("688", "controller")] = "NAM"
                        self.execute("ADISCORD_south_record_key_states")
                        self.assertEqual(self.facts[("688", "variable", "ADISCORD_south_initial_side")], side)
                        for winner in (1, 2):
                            self.variable("ADISCORD_south_winner_side", winner)
                            selected = list(selected_effects(self.expand(self.effects["ADISCORD_south_mark_loser"]), self.facts, "NAM"))
                            pending = [(tag, item.value) for tag, item in selected if item.key == "set_country_flag"]
                            expected = [] if winner == side else [("NAM", "ADISCORD_south_settlement_pending")]
                            self.assertEqual(pending, expected)
                            release = [item.value for _, item in selected if item.key == "overlord"]
                            self.assertEqual(len(release), int(winner != side))
                            if release:
                                autonomy = block(release[0], "set_autonomy")
                                self.assertEqual(scalar(autonomy, "target"), "PREV")
                                self.assertEqual(scalar(autonomy, "autonomy_state"), "autonomy_free")

    def test_bound_assignment_preserves_nam_leadership_and_ignores_absent_nam(self):
        for exists in (False, True):
            with self.subTest(exists=exists):
                self.setUp()
                self.facts[("NAM", "exists", "yes")] = exists
                if exists:
                    self.objectives()
                else:
                    self.objectives("EFL", "68")
                self.execute("ADISCORD_south_assign_bound_sides")
                self.assertEqual(self.calls, [])
                self.assertEqual(self.facts.get(("NAM", "variable", "ADISCORD_south_side")), 2 if exists else None)

    def test_static_front_never_creates_a_hegemon_for_either_declarer(self):
        for north, capital in (("NAM", "700"), ("EFL", "688"), ("AZH", "69")):
            for declarer in (1, 2):
                self.setUp()
                self.objectives(north, capital)
                self.variable("ADISCORD_south_declarer_side", declarer)
                self.execute("ADISCORD_south_final_resolve_by_control")
                self.assertEqual(self.calls, ["ADISCORD_south_final_repel"], (north, declarer))
                roster = self.arrays["global.ADISCORD_south_key_states"]
                self.assertEqual(len(roster), len(set(roster)))

    def test_only_enemy_key_captures_score_and_recovery_removes_the_point(self):
        self.objectives()
        for state, controller, result in (("67", "SHL", "shl_victory"), ("699", "NAM", "north_victory")):
            original = self.facts[(state, "controller")]
            self.facts[(state, "controller")] = controller
            self.calls.clear()
            self.execute("ADISCORD_south_final_resolve_by_control")
            self.assertEqual(self.calls, ["ADISCORD_south_final_resolve_" + result])
            self.facts[(state, "controller")] = original
            self.calls.clear()
            self.execute("ADISCORD_south_final_resolve_by_control")
            self.assertEqual(self.calls, ["ADISCORD_south_final_repel"])
        self.facts[("67", "controller")] = "SHL"
        self.facts[("699", "controller")] = "NAM"
        self.calls.clear()
        self.execute("ADISCORD_south_final_resolve_by_control")
        self.assertEqual(self.calls, ["ADISCORD_south_final_repel"], "Equal captures")

    def test_neutral_key_and_late_alliance_cannot_manufacture_progress(self):
        self.objectives()
        self.facts[("688", "controller")] = "WEF"
        self.execute("ADISCORD_south_record_key_states")
        self.assertNotIn("688", self.arrays["global.ADISCORD_south_key_states"])
        self.variable("ADISCORD_south_side", 1, "WEF")
        self.execute("ADISCORD_south_final_resolve_by_control")
        self.assertEqual(self.calls, ["ADISCORD_south_final_repel"])
        roster = list(self.arrays["global.ADISCORD_south_key_states"])
        self.execute("ADISCORD_south_clear_key_states")
        self.assertEqual(self.arrays["global.ADISCORD_south_key_states"], [])
        for state in roster:
            self.assertFalse(self.facts[(state, "has_variable", "ADISCORD_south_initial_side")])

    def test_mission_cannot_succeed_early_or_lose_its_clock_on_liberation(self):
        decisions = definitions(ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt")
        mission = block(decisions["ADISCORD_south_final_war_category"], "ADISCORD_south_preparation")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "56")
        self.assertFalse(self.matches(block(mission, "available")))
        self.flag("ADISCORD_south_preparation_started", age=150)
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.assertFalse(self.matches(block(mission, "visible")))
        self.assertFalse(self.matches(block(mission, "cancel_trigger")))
        self.flag("ADISCORD_south_final_started")
        self.assertTrue(self.matches(block(mission, "cancel_trigger")))

    def test_every_diplomatic_focus_and_delayed_reply_respects_the_story_gate(self):
        # NAM's own southern campaign waits for its exile story; Shahrabad's
        # consolidation chains send their demands at once and the answer
        # effects below defer them while NAM's story is pending.
        for path in (ROOT / "focus_trees/NAM/postwar/focuses.txt", ROOT / "focus_trees/NAM/defeated/focuses.txt"):
            for name, focus in focus_blocks(path).items():
                reward = repr(block(focus, "completion_reward"))
                if any(effect in reward for effect in ("ADISCORD_south_demand_submission", "ADISCORD_south_offer_alliance", "ADISCORD_south_demand_annexation", "ADISCORD_south_offer_economic_contract")):
                    self.assertIn("ADISCORD_south_nam_story_clear", repr(block(focus, "available")), name)
        for path in (ROOT / "focus_trees/NAM/postwar/focuses.txt", ROOT / "focus_trees/NAM/defeated/focuses.txt", *SHL_TREES):
            for name, focus in focus_blocks(path).items():
                reward = repr(block(focus, "completion_reward"))
                if "ADISCORD_south_prepare_offensive" in reward:
                    if name == "NAM_defeat_southern_charter":
                        # Auto-completion would bind the mutually exclusive economic settlement.
                        self.assertFalse(any(entry.key == "bypass" for entry in focus))
                        self.assertEqual(scalar(block(focus, "mutually_exclusive"), "focus"), "NAM_defeat_oil_peace")
                        second_chapter = focus_blocks(path)["NAM_defeat_second_chapter"]
                        alternatives = {entry.value for entry in block(second_chapter, "prerequisite")}
                        self.assertTrue({name, "NAM_defeat_oil_peace"} <= alternatives)
                    else:
                        self.assertIn("ADISCORD_south_final_started", repr(block(focus, "bypass")), name)
                    self.assertIn("ADISCORD_south_final_focus_available", repr(block(focus, "available")), name)
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer", "ADISCORD_south_finalize_submission"):
            self.assertIn("ADISCORD_south_nam_story_clear", body(EFFECTS, name))
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.assertIn("ADISCORD_south_offer_target", repr(events["ADISCORD_south.46"]))
        self.assertIn("ADISCORD_south_nam_story_clear", repr(events["ADISCORD_south.46"]))
        self.assertIn("28", repr(events["ADISCORD_south.41"]))

    def test_ai_rakhma_ultimatum_waits_at_dispatch_and_at_the_answer(self):
        shl = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        for key in ("SHL_demand_would_engage_rakhma", "SHL_would_join_refusing_side",
                    "SHL_has_unreachable_regional_defender", "SHL_rakhma_transit_controller",
                    "SHL_rakhma_staging_controller"):
            self.triggers[key] = shl[key]
        self.facts["RHM", "exists", "yes"] = True
        self.facts["RHM", "has_capitulated", "no"] = True
        self.facts["GLP", "gives_military_access_to", "SHL"] = True
        self.assertTrue(self.trigger_matches("SHL_rakhma_transit_controller", "GLP"))
        self.assertFalse(self.trigger_matches("SHL_rakhma_staging_controller", "GLP"))
        self.facts["GLP", "has_war_with", "RHM"] = True
        self.assertTrue(self.trigger_matches("SHL_rakhma_staging_controller", "GLP"))
        self.facts["GLP", "has_war_with", "SHL"] = True
        self.assertFalse(self.trigger_matches("SHL_rakhma_staging_controller", "GLP"))

        self.facts["SDR", "is_in_faction_with", "RHM"] = True
        for sponsor, recipient, kind, ai, route, allowed in (
            ("SHL", "RHM", 1, True, False, False),
            ("SHL", "RHM", 2, True, True, True),
            ("SHL", "SDR", 2, True, False, False),
            ("SHL", "KDR", 2, True, False, True),
            ("SHL", "RHM", 3, True, False, True),
            ("SHL", "RHM", 1, False, False, True),
            ("NAM", "RHM", 2, True, False, True),
        ):
            self.variable("ADISCORD_south_offer_kind", kind, recipient)
            self.facts["SHL", "is_ai", "yes"] = ai
            self.facts["SHL", "SHL_rakhma_front_reachable", "no"] = not route
            for root, sender in ((sponsor, "SHL"), (recipient, sponsor)):
                with self.subTest(root=root, sender=sender, recipient=recipient, kind=kind):
                    self.event_root, self.event_sender = root, sender
                    self.assertEqual(self.trigger_matches("ADISCORD_south_offer_war_clear", recipient), allowed)

    def test_regional_demands_check_each_defender_before_a_shl_refusal_war(self):
        shl = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        for key in ("SHL_demand_would_engage_rakhma", "SHL_would_join_refusing_side",
                    "SHL_has_unreachable_regional_defender"):
            self.triggers[key] = shl[key]
        for tag in ("SDR", "MZR", "KDR", "GLP", "KYZ"):
            self.facts[tag, "exists", "yes"] = True
            self.facts[tag, "has_capitulated", "no"] = True
        self.facts["SHL", "is_ai", "yes"] = True
        for recipient, partner in (("MZR", "SDR"), ("SDR", "MZR"), ("KDR", "SDR"), ("SDR", "KDR"),
                                   ("GLP", "KYZ"), ("KYZ", "GLP")):
            for own_route, pact, ally_route, expected in (
                (False, False, True, False), (False, True, True, False), (True, False, False, True),
                (True, True, False, False), (True, True, True, True),
            ):
                self.facts[recipient, "is_in_faction_with", partner] = pact
                self.facts[partner, "is_in_faction_with", recipient] = pact
                self.facts[recipient, "SHL_regional_front_reachable", "no"] = not own_route
                self.facts[partner, "SHL_regional_front_reachable", "no"] = not ally_route
                self.variable("ADISCORD_south_offer_kind", 1 if recipient == "KDR" else 2, recipient)
                for self.event_root, self.event_sender in (("SHL", "NAM"), (recipient, "SHL")):
                    with self.subTest(recipient=recipient, own_route=own_route, pact=pact,
                                      ally_route=ally_route, root=self.event_root):
                        self.assertEqual(self.trigger_matches("ADISCORD_south_offer_war_clear", recipient),
                                         expected)
            self.facts[recipient, "SHL_regional_front_reachable", "no"] = True
            self.event_root, self.event_sender = recipient, "SHL"
            self.variable("ADISCORD_south_offer_kind", 3, recipient)
            self.assertTrue(self.trigger_matches("ADISCORD_south_offer_war_clear", recipient))
            self.variable("ADISCORD_south_offer_kind", 1, recipient)
            self.event_sender = "NAM"
            self.assertTrue(self.trigger_matches("ADISCORD_south_offer_war_clear", recipient))
            self.facts[partner, "is_in_faction_with", recipient] = False
            self.facts[recipient, "is_in_faction_with", partner] = False

    @staticmethod
    def war_branch(effect):
        """The branch that starts the war; a branch handing the strike to the appeal comes first."""
        return next(e.value for e in effect if e.key in ("if", "else_if")
                    and not any(child.key == "ADISCORD_south_shl_strike_or_appeal" for child in e.value))

    def test_shl_border_war_starts_require_reachable_opponents(self):
        shl = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        effects = definitions(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt")
        for name in ("SHL_would_join_refusing_side", "SHL_has_unreachable_regional_defender",
                     "SHL_can_seize_qanats", "SHL_can_strike_veyr", "SHL_can_launch_keizan_offensive",
                     "SHL_unreachable_keizan_signatory"):
            self.triggers[name] = shl[name]
        for condition in ("SHL_country_operable", "SHL_qanat_dispute_open", "SHL_veyr_dispute_open",
                          "SHL_qanat_counterpart", "SHL_glp_counterpart", "SHL_keizan_can_threaten"):
            self.facts["SHL", condition, "yes"] = True
        for tag, focus, effect in (("GLP", "SHL_key_to_sea", "SHL_start_glp_war"),
                                   ("KYZ", "SHL_right_to_water", "SHL_start_qanat_war")):
            self.facts[tag, "exists", "yes"] = True
            self.facts[tag, "has_capitulated", "no"] = True
            self.facts[tag, "has_war", "no"] = True
            self.facts["SHL", "has_completed_focus", focus] = True
            self.facts["SHL", "is_ai", "yes"] = True
            limit = block(self.war_branch(effects[effect]), "limit")
            for reachable in (False, True):
                self.facts[tag, "SHL_regional_front_reachable", "no"] = not reachable
                self.assertEqual(self.matches(limit), reachable, tag)

        self.variable("SHL_keizan_state", 5, "SHL")
        limit = block(self.war_branch(effects["SHL_start_kyz_war"]), "limit")
        self.facts["GLP", "has_country_flag", "SHL_kyz_pact_signed"] = True
        self.facts["GLP", "SHL_kyz_partner_eligible", "yes"] = True
        for offensive, keizan_open, veyr_open, expected in (
            (True, False, True, False), (True, True, False, False),
            (True, True, True, True), (False, False, False, True),
        ):
            self.facts["SHL", "has_country_flag", "SHL_kyz_offensive"] = offensive
            self.facts["KYZ", "SHL_regional_front_reachable", "no"] = not keizan_open
            self.facts["GLP", "SHL_regional_front_reachable", "no"] = not veyr_open
            self.assertEqual(self.matches(limit), expected)

    def test_southern_front_orders_follow_each_active_war(self):
        profiles = definitions(ROOT / "common/ai_strategy/ADISCORD_SHL_ai.txt")
        profile = profiles["ADISCORD_SHL_regional_front"]
        order = block(profile, "ai_strategy")
        target = block(order, "country_trigger")
        opponents = {"GLP", "KYZ", "KDR", "RHM", "SDR", "MZR"}
        self.assertNotIn("state_trigger", [entry.key for entry in order])
        self.assertFalse(self.matches(target, "NAM"))
        for name in ("ADISCORD_SHL_limited_front_glp", "ADISCORD_SHL_limited_front_kyz"):
            for entry in profiles[name]:
                if entry.key == "ai_strategy" and scalar(entry.value, "type") == "front_control":
                    self.assertGreater(int(scalar(order, "priority")), int(scalar(entry.value, "priority")))
        for key, value in (("execution_type", "rush_weak"), ("execute_order", "yes"),
                           ("manual_attack", "yes"), ("ordertype", "front")):
            self.assertEqual(scalar(order, key), value)
        self.facts["SHL", "is_ai", "yes"] = True
        for opponent in opponents:
            self.assertTrue(self.matches(target, opponent))
            self.facts["SHL", "has_war_with", opponent] = True
            self.assertTrue(self.matches(block(profile, "enable")))
            self.facts["SHL", "has_war_with", opponent] = False
            self.assertFalse(self.matches(block(profile, "enable")))

    def test_regional_land_route_distinguishes_staging_from_neutral_transit(self):
        shl = definitions(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt")
        route = shl["SHL_regional_front_reachable"]
        self.assertEqual(scalar(block(route, "set_temp_variable"), "SHL_land_opponent"), "THIS")
        alternatives = block(route, "OR")
        direct = block(block(alternatives, "AND"), "can_build_railway")
        neighbor = block(block(alternatives, "any_controlled_state"), "any_neighbor_state")
        transit = block(neighbor, "can_build_railway")
        self.assertEqual(scalar(neighbor, "ADISCORD_south_land_neighbor"), "yes")
        self.assertEqual(scalar(block(neighbor, "controller"), "SHL_regional_launch_controller"), "yes")
        self.assertEqual(scalar(direct, "start_state"), "SHL.capital")
        self.assertEqual(scalar(direct, "target_state"), "THIS.capital")
        self.assertEqual(scalar(transit, "start_state"), "SHL.capital")
        self.assertEqual(scalar(transit, "target_state"), "THIS")

        for key in ("SHL_regional_launch_controller", "SHL_regional_transit_controller",
                    "SHL_rakhma_transit_controller"):
            self.triggers[key] = shl[key]

        def forbidden(query, country, enemy):
            weight = block(query, "controller_priority")
            modifier = block(weight, "modifier")
            self.assertLess(int(scalar(weight, "base")) + int(scalar(modifier, "add")), 0)
            rules = self.expand([entry for entry in modifier if entry.key != "add"])

            def bind(entries):
                for e in entries:
                    key = enemy if e.key == "var:SHL_land_opponent" else e.key
                    value = list(bind(e.value)) if isinstance(e.value, list) else e.value
                    yield replace(e, key=key, value=enemy if value == "var:SHL_land_opponent" else value)

            return matches_conditions(list(bind(rules)), self.facts, country)

        self.facts["GLP", "gives_military_access_to", "SHL"] = True
        for enemy in ("SDR", "MZR", "KDR"):
            self.assertFalse(forbidden(direct, "SHL", enemy))
            self.assertFalse(forbidden(direct, enemy, enemy))
            self.assertTrue(forbidden(direct, "GLP", enemy))
            self.assertFalse(forbidden(transit, "GLP", enemy))
            self.facts["GLP", "has_war_with", enemy] = True
            self.assertFalse(forbidden(direct, "GLP", enemy))
            self.facts["GLP", "has_war_with", enemy] = False
            self.facts["GLP", "is_in_faction_with", enemy] = True
            self.assertTrue(forbidden(transit, "GLP", enemy))
            self.facts["GLP", "is_in_faction_with", enemy] = False

    def test_deferred_offers_preserve_each_recipient_sender_and_unattended_exit(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.execute("ADISCORD_south_queue_offer", "EFL")
        self.execute("ADISCORD_south_queue_offer", "AZH")
        first, second = self.calls
        self.assertEqual(first[-1]["ADISCORD_south_offer_target"], "EFL")
        self.assertEqual(second[-1]["ADISCORD_south_offer_target"], "AZH")
        for packet in (first, second):
            self.targets = dict(packet[-1])
            recipient = self.targets["ADISCORD_south_offer_target"]
            self.variable("ADISCORD_south_offer_kind", 1, recipient)
            self.flag("ADISCORD_nam_resource_war_island_exile")
            self.event_root = "SHL"
            self.calls.clear()
            self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
            self.assertEqual(self.calls[0][:4], ("SHL", "country_event", "ADISCORD_south.46", "SHL"))
            self.assertEqual(self.calls[0][-1], packet[-1])
            self.assertTrue(self.facts[(recipient, "has_variable", "ADISCORD_south_offer_kind")])
            self.flag("ADISCORD_nam_resource_war_island_exile", False)
            self.calls.clear()
            self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
            self.assertEqual(self.calls[0][:4], (recipient, "country_event", "ADISCORD_south.40", "SHL"))
            # If the story changes while the visible event is open, both an
            # immediate click and an unattended choice have one safe response.
            self.flag("ADISCORD_nam_resource_war_island_exile")
            self.event_root = recipient
            options = [e.value for e in events["ADISCORD_south.40"] if e.key == "option"
                       and self.matches(block(e.value, "trigger"), recipient)]
            self.assertEqual([scalar(o, "name") for o in options], ["ADISCORD_south.40.closed"])
            self.calls.clear()
            self.execute_entries(block(options[0], "hidden_effect"), recipient)
            self.assertEqual(self.calls[0][:3], ("SHL", "country_event", "ADISCORD_south.46"))
            self.assertTrue(self.facts[(recipient, "has_variable", "ADISCORD_south_offer_kind")])

    def test_accepted_submission_waits_without_erasing_its_choice(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = True
        self.execute_entries(block(events["ADISCORD_south.41"], "immediate"), "EFL")
        self.assertEqual(self.calls[0][:3], ("EFL", "country_event", "ADISCORD_south.41"))
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")])

    def test_accepted_contract_blocks_replacement_and_expires_on_new_settlement(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        for sender in ("SHL", "NAM"):
            for invalid in ("foreign_faction", "subject", "capitulated", "sender_gone", "war"):
                self.setUp()
                self.event_root = sender
                receipt = "ADISCORD_south_submits_to_" + sender
                self.facts[("EFL", "has_country_flag", receipt)] = True
                self.assertFalse(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))
                self.flag("ADISCORD_nam_resource_war_island_exile")
                if invalid == "foreign_faction":
                    self.facts[("EFL", "is_in_faction", "no")] = False
                elif invalid == "subject":
                    self.facts[("EFL", "is_subject", "no")] = False
                elif invalid == "capitulated":
                    self.facts[("EFL", "has_capitulated", "no")] = False
                elif invalid == "sender_gone":
                    self.facts[(sender, "exists", "yes")] = False
                else:
                    self.facts[("EFL", "has_war_with", sender)] = True
                self.assertFalse(self.trigger_matches("ADISCORD_south_submission_pending_valid", "EFL"), (sender, invalid))
                self.execute_entries(block(events["ADISCORD_south.41"], "immediate"), "EFL")
                self.assertEqual(self.calls, [], (sender, invalid))
                self.assertFalse(self.facts[("EFL", "has_country_flag", receipt)])
        self.setUp()
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))

    def test_stale_offers_close_at_dispatch_and_at_visible_answer(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        for invalid in ("subject", "capitulated", "ally", "war", "sender_gone", "resolved"):
            for kind in (1, 2, 3):
                self.setUp()
                self.targets["ADISCORD_south_offer_target"] = "EFL"
                self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                if invalid in ("subject", "capitulated"):
                    key = "is_subject" if invalid == "subject" else "has_capitulated"
                    self.facts[("EFL", key, "no")] = False
                elif invalid in ("ally", "war"):
                    key = "is_in_faction_with" if invalid == "ally" else "has_war_with"
                    self.facts[("EFL", key, "SHL")] = True
                elif invalid == "sender_gone":
                    self.facts[("SHL", "exists", "yes")] = False
                else:
                    self.flag("ADISCORD_south_final_resolved")
                self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
                self.assertEqual(self.calls, [], (invalid, kind))
                self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
                self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                self.event_root = "EFL"
                options = [e.value for e in events["ADISCORD_south.40"] if e.key == "option"
                           and self.matches(block(e.value, "trigger"), "EFL")]
                self.assertEqual([scalar(o, "name") for o in options], ["ADISCORD_south.40.closed"])
                self.execute_entries(block(options[0], "hidden_effect"), "EFL")
                self.assertEqual(self.calls, [], (invalid, kind))
                self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
                for effect in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
                    self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                    self.execute(effect, "EFL")
                    self.assertEqual(self.calls, [], (effect, invalid, kind))

    def test_protection_offer_follows_the_mandate_and_refusal_stays_peaceful(self):
        decision = south_decisions()["ADISCORD_south_offer_protectorate"]
        self.assertNotIn("ADISCORD_south_offer_economic_contract", south_decisions())
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "custom_cost_text"), "ADISCORD_south_cost_protectorate")
        self.assertEqual(body(DECISIONS, "\tADISCORD_south_offer_protectorate").count("add_political_power = -50"), 1)
        self.event_root = "EFL"
        self.event_sender = "NAM"
        self.facts[("NAM", "tag", "NAM")] = True
        self.variable("ADISCORD_south_offer_kind", 4, "EFL")
        # Svetlogorye as the champion offers protection on any mandate.
        self.assertTrue(self.trigger_matches("ADISCORD_south_offer_answer_valid", "EFL"))
        self.facts[("NAM", "is_subject", "no")] = False
        self.facts[("NAM", "is_subject_of", "AZH")] = True
        self.event_root, self.event_sender = "KDR", "AZH"
        self.regional_country("KDR")
        self.variable("ADISCORD_south_offer_kind", 4, "KDR")
        self.assertFalse(self.trigger_matches("ADISCORD_south_offer_answer_valid", "KDR"), "Azhar cannot offer protection")
        self.facts[("NAM", "is_subject", "no")] = True
        self.facts[("NAM", "is_subject_of", "AZH")] = False
        self.event_root, self.event_sender = "EFL", "NAM"
        self.execute("ADISCORD_south_refuse_offer", "EFL")
        self.assertEqual([call for call in self.calls if call[1] in ("country_event", "add_to_war")], [])
        for champion in ("SHL", "NAM"):
            self.assertFalse(self.facts.get(("EFL", "has_country_flag", "ADISCORD_south_refused_" + champion), False))
        self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
        self.variable("ADISCORD_south_offer_kind", 4, "EFL")
        self.calls.clear()
        self.execute("ADISCORD_south_accept_offer", "EFL")
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_NAM")])
        self.assertFalse(self.facts.get(("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL"), False))
        self.assertEqual([call[:3] for call in self.calls if call[1] == "country_event"],
                         [("EFL", "country_event", "ADISCORD_south.41")])
        # The finalizer gives the subject type of the current mandate.
        for mandate in ("service", "pragmatic", "district"):
            self.triggers[f"NAM_prewar_{mandate}_mandate"] = parse_clausewitz(f"has_country_flag = test_{mandate}_mandate")
        for mandate, autonomy, notice in (("service", "autonomy_NAM_namestnik_office", []),
                                          ("pragmatic", "autonomy_NAM_economic_contract", [("NAM", "ADISCORD_south.42")]),
                                          ("district", "autonomy_NAM_oil_charter", []),
                                          (None, "autonomy_puppet", [])):
            with self.subTest(mandate=mandate):
                for other in ("service", "pragmatic", "district"):
                    self.facts[("NAM", "has_country_flag", f"test_{other}_mandate")] = other == mandate
                chosen = list(selected_effects(self.expand(self.effects["ADISCORD_south_finalize_submission"]), self.facts, "EFL"))
                self.assertEqual([scalar(e.value, "autonomy_state") for _, e in chosen if e.key == "set_autonomy"], [autonomy])
                keys = [e.key for _, e in chosen]
                self.assertEqual([(scope, scalar(e.value, "id")) for scope, e in chosen if e.key == "country_event"], notice)
                if notice:
                    self.assertLess(keys.index("set_autonomy"), keys.index("country_event"))

    def test_economic_offer_answer_waits_to_announce_the_signed_contract(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        answer = next(e.value for e in events["ADISCORD_south.40"]
                      if e.key == "option" and scalar(e.value, "name") == "ADISCORD_south.40.a")
        self.event_root = "EFL"
        self.event_sender = "NAM"
        self.variable("ADISCORD_south_offer_kind", 4, "EFL")
        chosen = list(selected_effects(self.expand(block(answer, "hidden_effect")), self.facts, "EFL"))
        self.assertFalse(any(e.key == "country_event" for _, e in chosen))
        self.assertTrue(any(e.key == "ADISCORD_south_accept_offer" for _, e in chosen))

    def submission_effects(self, recipient):
        self.event_root = recipient

        def recipient_for_prev(items):
            # The finalizer runs in the recipient's scope, so PREV inside a champion block is ROOT.
            return [replace(e, key="ROOT" if e.key == "PREV" else e.key,
                            value=recipient_for_prev(e.value) if isinstance(e.value, list) else e.value)
                    for e in items]

        finalizer = self.expand(recipient_for_prev(self.effects["ADISCORD_south_finalize_submission"]))
        return list(selected_effects(finalizer, self.facts, recipient))

    def test_submission_finalizer_uses_the_same_current_contract_guard(self):
        for sender in CHAMPIONS:
            with self.subTest(sender=sender):
                self.setUp()
                self.facts[("EFL", "tag", "EFL")] = True
                self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_" + sender)] = True
                chosen = self.submission_effects("EFL")
                self.assertEqual([(scope, scalar(e.value, "target")) for scope, e in chosen if e.key == "puppet"],
                                 [(sender, "PREV")])
                self.assertEqual([(scope, scalar(e.value, "autonomy_state")) for scope, e in chosen
                                  if e.key == "set_autonomy"], [(sender, "autonomy_puppet")])
                keys = [e.key for _, e in chosen]
                self.assertLess(keys.index("set_autonomy"), keys.index("NAM_board_sync_district_status"))
                self.assertEqual([(scope, e.value) for scope, e in chosen if e.key == "clr_country_flag"],
                                 [("EFL", "ADISCORD_south_submits_to_SHL"), ("EFL", "ADISCORD_south_submits_to_NAM"),
                                  ("EFL", "ADISCORD_south_protectorate_terms")])
                self.facts[("EFL", "has_war_with", sender)] = True
                self.assertFalse(any(e.key in ("puppet", "set_autonomy", "NAM_apply_border_protocol")
                                     for _, e in self.submission_effects("EFL")))

    def test_offer_texts_name_the_subject_type_the_finalizer_applies(self):
        finalizer = body(EFFECTS, "ADISCORD_south_finalize_submission")
        for mandate in ("NAM_prewar_service_mandate", "NAM_prewar_district_mandate"):
            self.assertIn(f"limit = {{ {mandate} = yes }}", finalizer)
        offer = self.event(40)
        expected = {
            "ADISCORD_south.40.d_submit_nam_namestnik": [("NAM_prewar_district_mandate", "no")],
            "ADISCORD_south.40.d_submit_nam_charter": [("NAM_prewar_district_mandate", "yes")],
            "ADISCORD_south.40.t_contract": [("NAM_prewar_service_mandate", "no"), ("NAM_prewar_district_mandate", "no")],
            "ADISCORD_south.40.d_contract": [("NAM_prewar_service_mandate", "no"), ("NAM_prewar_district_mandate", "no")],
            "ADISCORD_south.40.t_writ": [("NAM_prewar_service_mandate", "yes")],
            "ADISCORD_south.40.d_writ": [("NAM_prewar_service_mandate", "yes")],
            "ADISCORD_south.40.t_charter": [("NAM_prewar_district_mandate", "yes")],
            "ADISCORD_south.40.d_charter": [("NAM_prewar_district_mandate", "yes")],
        }
        for entry in offer:
            if entry.key in ("title", "desc") and scalar(entry.value, "text") in expected:
                text = scalar(entry.value, "text")
                scope = block(block(entry.value, "trigger"), "FROM")
                self.assertEqual([(e.key, e.value) for e in scope if e.key.startswith("NAM_prewar")],
                                 expected.pop(text), text)
        self.assertEqual(expected, {})
        source = EVENTS.read_text(encoding="utf-8")
        start = source.index("\tid = ADISCORD_south.40\n")
        self.assertNotIn("has_completed_focus = NAM_service_state", source[start:source.index("\n}\n", start)])
        self.assertNotIn("has_completed_focus = NAM_federal_charter", source[start:source.index("\n}\n", start)])

    def test_military_offer_rechecks_the_recipient_after_leaving_its_faction(self):
        effects = definitions(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        accept = block(effects["NAM_neighbour_accept_command"], "if")
        dispatch = block(accept, "country_event")
        self.assertEqual(scalar(dispatch, "days"), "1")
        parsed_events = parse_clausewitz(
            (ROOT / "events/ADISCORD_nam_resource_war_events.txt").read_text(encoding="utf-8"))
        delivery = next(e.value for e in parsed_events if e.key == "country_event"
                        and scalar(e.value, "id") == scalar(dispatch, "id"))
        immediate = block(delivery, "immediate")
        settle = block(immediate, "if")
        self.assertEqual(scalar(block(settle, "limit"), "NAM_neighbour_military_answer_open"), "yes")
        self.assertEqual(scalar(settle, "NAM_neighbour_establish_command"), "yes")
        self.assertEqual(scalar(immediate, "clr_country_flag"), "NAM_neighbour_command_offer")
        for number, guard, effect in (
            ("410", "NAM_neighbour_alliance_offer_open", "NAM_neighbour_accept_alliance"),
            ("411", "NAM_neighbour_military_answer_open", "NAM_neighbour_accept_command"),
        ):
            notice = next(e.value for e in parsed_events if e.key == "country_event"
                          and scalar(e.value, "id") == "ADISCORD_nam_resource_war." + number)
            options = [e.value for e in notice if e.key == "option"]
            for valid in (True, False):
                choices = [o for o in options if scalar(block(o, "trigger"), guard) == ("yes" if valid else "no")]
                self.assertEqual(len(choices), 2 if valid else 1)
                self.assertEqual(sum(any(e.key == effect for e in walk(o)) for o in choices), int(valid))
                for choice in choices:
                    self.assertFalse(any(e.key in ("puppet", "annex_country", "declare_war_on") for e in walk(choice)))

    # ----- Crisis deadline -----

    def unready(self, *tags):
        for key in list(self.facts):
            if key[0] in tags and key[1] == "has_completed_focus":
                self.facts[key] = False

    def event(self, number):
        return next(e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                    if e.key == "country_event" and scalar(e.value, "id") == f"ADISCORD_south.{number}")

    def pass_deadline(self, age=180):
        """Open the preparation, then let the watch step meet the base deadline."""
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_preparation_started", age=age)
        self.set_date(DEADLINES[0])
        self.calls.clear()
        self.scheduled.clear()
        self.execute("ADISCORD_south_deadline_watch_step")

    def deadline_passed(self):
        return self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_crisis_deadline_passed"), False)

    def shown_deadline(self, language):
        """The deadline text as the scripted localisation renders it now."""
        shown = {scalar(e.value, "name"): e.value for e in parse_clausewitz(SCRIPTED_LOC.read_text(encoding="utf-8"))
                 if e.key == "defined_text"}

        def pick(name):
            texts = [e.value for e in shown[name] if e.key == "text"]
            chosen = next(text for text in texts
                          if not any(e.key == "trigger" for e in text) or self.matches(block(text, "trigger")))
            return loc_value(language, scalar(chosen, "localization_key"))

        text = pick("ADISCORDSouthDeadlineDate").replace("[ADISCORDSouthDeadlineMonth]", pick("ADISCORDSouthDeadlineMonth"))
        for field in ("d", "y"):
            value = self.facts.get(("GLB", "variable", f"ADISCORD_south_deadline_{field}"), 0)
            text = text.replace(f"[?global.ADISCORD_south_deadline_{field}|0]", str(int(value)))
        return text

    def test_deadline_anchor_follows_the_window_counted_pulls_and_floor(self):
        # Every check compares today with one stored day; no date tables remain.
        for name in ("ADISCORD_south_deadline_reached", "ADISCORD_south_deadline_date_near",
                     "ADISCORD_south_deadline_date_in_ai_window", "ADISCORD_south_early_window_open"):
            source = body(TRIGGERS, name)
            self.assertNotRegex(source, r"\b\d{4}\.\d+\.\d+\b", name)
            self.assertIn("var = global.num_days", source, name)
        offsets = {"": 0, "_near": 31, "_ai": 120, "_pull_guard": 135, "_warning": 180}
        # Without an anchor the opening sets 540 days, less 15 for every pull counted before.
        for level, deadline in enumerate(DEADLINES):
            with self.subTest(level=level):
                self.setUp()
                self.variable("ADISCORD_south_crisis_pull", level)
                self.execute("ADISCORD_south_begin_preparation")
                self.assertEqual(self.deadline_day(), day_number(deadline))
                self.assertEqual(day_number(DEADLINES[0]) - day_number(OPENED), SHORT_WINDOW)
                for suffix, offset in offsets.items():
                    self.assertEqual(self.deadline_day(suffix), day_number(deadline) - offset, suffix)
        # Svetlogorye's victory anchors 1095 days before it opens the preparation; the opening keeps it.
        self.setUp()
        self.anchor(VICTORY_WINDOW)
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.deadline_day(), day_number(OPENED) + VICTORY_WINDOW)
        self.anchor(SHORT_WINDOW)
        self.assertEqual(self.deadline_day(), day_number(OPENED) + VICTORY_WINDOW, "One anchor per story campaign")
        self.setUp()
        self.variable("ADISCORD_south_crisis_pull", 6)
        self.anchor(VICTORY_WINDOW)
        self.assertEqual(self.deadline_day(), day_number(OPENED) + VICTORY_WINDOW - 90)
        # Never closer than 180 days from the day the anchor is set.
        self.setUp()
        self.variable("ADISCORD_south_crisis_pull", 6)
        self.anchor(200)
        self.assertEqual(self.deadline_day(), day_number(OPENED) + 180)
        # The settlements set the long window themselves, before their opening call.
        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        for settlement in ("ADISCORD_nam_resource_war_resolve_nam_victory", "ADISCORD_nam_resource_war_resolve_standoff"):
            with self.subTest(settlement=settlement):
                source = body(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt", settlement)
                window = source.index("var = ADISCORD_south_deadline_window value = 1095")
                self.assertLess(window, source.index("ADISCORD_south_set_deadline = yes"))
                self.assertLess(source.index("ADISCORD_south_set_deadline = yes"), source.index("ADISCORD_south_begin_preparation = yes"))
        self.assertEqual(nam.count("ADISCORD_south_deadline_window value = 1095"), 2)

    def test_early_window_is_the_same_floor_for_both_champions(self):
        self.open_preparation(age=400)
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.set_date(script_date(int(self.deadline_day("_warning")) - 1))
        for tag in ("NAM", "SHL"):
            self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", tag), tag)
        self.enter_early_window()
        for tag in ("NAM", "SHL"):
            self.assertTrue(self.trigger_matches("ADISCORD_south_final_can_start", tag), tag)
        self.assertIn("ADISCORD_south_early_window_open = yes", body(TRIGGERS, "ADISCORD_south_preparation_can_finish"))

    def test_deadline_is_reached_on_its_day_and_shown_as_a_calendar_date(self):
        self.assertFalse(self.trigger_matches("ADISCORD_south_deadline_reached"), "No anchor, no deadline")
        for language, expected in (("russian", "примерно через три года после мира Светлогорья"),
                                   ("english", "about three years after Svetlogorye's peace")):
            self.assertEqual(self.shown_deadline(language), expected, language)
        self.execute("ADISCORD_south_begin_preparation")
        deadline = self.deadline_day()
        self.set_date(script_date(int(deadline) - 1))
        self.assertFalse(self.trigger_matches("ADISCORD_south_deadline_reached"))
        self.set_date(script_date(int(deadline)))
        self.assertTrue(self.trigger_matches("ADISCORD_south_deadline_reached"))
        self.assertEqual(self.shown_deadline("russian"), "1 марта 2166 г.")
        self.assertEqual(self.shown_deadline("english"), "1 March 2166")
        # Year and month boundaries of the 365-day calendar.
        for date, russian, english in (("2166.12.31", "31 декабря 2166 г.", "31 December 2166"),
                                       ("2167.1.1", "1 января 2167 г.", "1 January 2167"),
                                       ("2167.2.28", "28 февраля 2167 г.", "28 February 2167"),
                                       ("2167.3.1", "1 марта 2167 г.", "1 March 2167")):
            with self.subTest(date=date):
                self.setUp()
                self.set_date(script_date(day_number(date) - SHORT_WINDOW))
                self.execute("ADISCORD_south_begin_preparation")
                self.assertEqual(self.deadline_day(), day_number(date))
                self.assertEqual(self.shown_deadline("russian"), russian)
                self.assertEqual(self.shown_deadline("english"), english)
        startup = (ROOT / "common/on_actions/00_ADISCORD_on_actions.txt").read_text(encoding="utf-8")
        self.assertEqual(startup.count("set_variable = { var = global.ADISCORD_south_day0 value = global.num_days }"), 1)
        self.assertIn("NOT = { has_variable = global.ADISCORD_south_day0 }", startup)

    def test_pull_counts_before_the_anchor_and_respects_the_cap_guard_and_spheres(self):
        # The crisis is not open yet; Shahrabad's earlier victories still count.
        self.flag("ADISCORD_nam_resource_war_resolved", False)
        self.execute("ADISCORD_south_pull_clock_war")
        self.assertEqual(self.pull(), 2)
        self.execute("ADISCORD_south_pull_clock_campaign")
        self.assertEqual(self.pull(), 5)
        self.execute("ADISCORD_south_pull_clock_war")
        self.assertEqual(self.pull(), 6, "The cap is six units, 90 days")
        self.execute("ADISCORD_south_pull_clock_campaign")
        self.assertEqual(self.pull(), 6)
        self.assertIsNone(self.deadline_day(), "A counted unit sets no anchor")
        # With an anchor a unit moves it by 15 days while more than 135 days remain.
        for level in range(6):
            with self.subTest(level=level):
                self.setUp()
                self.execute("ADISCORD_south_begin_preparation")
                self.variable("ADISCORD_south_crisis_pull", level)
                deadline = self.deadline_day()
                self.set_date(script_date(int(deadline) - 135))
                self.execute("ADISCORD_south_pull_clock_unit")
                self.assertEqual((self.pull(), self.deadline_day()), (level, deadline))
                self.set_date(script_date(int(deadline) - 136))
                self.execute("ADISCORD_south_pull_clock_unit")
                self.assertEqual((self.pull(), self.deadline_day()), (level + 1, deadline - 15))
                self.assertEqual(self.deadline_day("_warning"), deadline - 15 - 180)
                self.assertGreater(self.deadline_day() - day_number(self.today()), 120)
        # A campaign meeting the guard partway keeps only the units that fit.
        self.setUp()
        self.execute("ADISCORD_south_begin_preparation")
        deadline = self.deadline_day()
        self.set_date(script_date(int(deadline) - 165))
        self.execute("ADISCORD_south_pull_clock_campaign")
        self.assertEqual((self.pull(), self.deadline_day()), (2, deadline - 30))
        # The spheres agreement freezes the deadline.
        self.flag("ADISCORD_south_spheres_agreed")
        self.set_date(OPENED)
        self.execute("ADISCORD_south_pull_clock_war")
        self.assertEqual((self.pull(), self.deadline_day()), (2, deadline - 30))

    def test_no_pull_after_the_war_starts_or_the_south_is_settled(self):
        for flag in ("ADISCORD_south_final_started", "ADISCORD_south_final_resolved"):
            with self.subTest(flag=flag):
                self.setUp()
                self.flag(flag)
                self.execute("ADISCORD_south_pull_clock_war")
                self.execute("ADISCORD_south_pull_clock_campaign")
                self.assertEqual(self.pull(), 0)
        self.assertNotIn("clear_variable = global.ADISCORD_south_crisis_pull", EFFECTS.read_text(encoding="utf-8"),
                         "A repelled campaign keeps the date it already reached")
        hostilities = definitions(EFFECTS)["ADISCORD_south_begin_hostilities"]
        common = [(e.key, e.value) for e in block(hostilities, "if") if e.key != "limit"]
        suspend = [key for key, _ in common].index("ADISCORD_south_suspend_preparation")
        penalty = next(index for index, (key, value) in enumerate(common)
                       if key == "if" and ("ADISCORD_south_mark_unprepared", "yes") in [(e.key, e.value) for e in value])
        self.assertLess(penalty, suspend, "The deadline marker is read before suspension clears it")
        self.assertEqual([(e.key, e.value) for e in block(common[penalty][1], "limit")],
                         [("has_global_flag", "ADISCORD_south_crisis_deadline_passed")])

    def test_deadline_needs_the_date_and_180_days_of_preparation(self):
        self.execute("ADISCORD_south_begin_preparation")
        for date, age, expected in (("2166.2.28", 3000, False), ("2166.3.1", 179, False),
                                    ("2166.3.1", 180, True), ("2170.1.1", 180, True)):
            with self.subTest(date=date, age=age):
                self.flag("ADISCORD_south_crisis_deadline_passed", False)
                self.flag("ADISCORD_south_preparation_started", age=age)
                self.set_date(date)
                self.calls.clear()
                self.execute("ADISCORD_south_check_deadline")
                self.assertEqual(self.deadline_passed(), expected)
                self.assertEqual([call[:3] for call in self.calls if call[1] == "country_event"],
                                 [("SHL", "country_event", "ADISCORD_south.4")] if expected else [])
        self.calls.clear()
        self.execute("ADISCORD_south_check_deadline")
        self.assertEqual(self.calls, [], "The deadline is marked once")

    def test_passed_deadline_starts_the_war_without_focuses_or_warning(self):
        dispatcher = self.event(4)
        self.assertEqual(scalar(dispatcher, "hidden"), "yes")
        self.assertEqual(scalar(dispatcher, "is_triggered_only"), "yes")
        self.assertEqual([(e.key, e.value) for e in block(dispatcher, "immediate")],
                         [("ADISCORD_south_dispatch_prepared_war", "yes")])
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        for number in (4, 5, 6):
            entry = next(e for e in registry["events"] if e["id"] == f"ADISCORD_south.{number}")
            self.assertEqual((entry["owner"], entry["status"]), ("events/ADISCORD_south_final_war_events.txt", "active"))
        for case in ("shahrabad", "nam_order", "oil_peace", "cycle"):
            with self.subTest(case=case):
                self.setUp()
                self.unready("SHL", "NAM")
                self.execute("ADISCORD_south_begin_preparation")
                self.flag("ADISCORD_south_preparation_started", age=180)
                self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "SHL"))
                self.set_date(DEADLINES[0])
                if case in ("nam_order", "oil_peace"):
                    self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")] = True
                if case == "oil_peace":
                    self.facts[("NAM", "has_completed_focus", "NAM_defeat_oil_peace")] = True
                self.calls.clear()
                if case == "cycle":
                    # A deadline met on the furnace tick starts the war in that cycle.
                    self.execute("ADISCORD_south_crisis_cycle")
                    self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_crisis_warned"), False))
                else:
                    self.execute("ADISCORD_south_deadline_watch_step")
                    self.assertEqual([call[:3] for call in self.calls if call[1] == "country_event"],
                                     [("SHL", "country_event", "ADISCORD_south.4")])
                    if case == "oil_peace":
                        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "NAM"))
                    self.execute_entries(block(dispatcher, "immediate"), "SHL")
                self.assertTrue(self.deadline_passed())
                self.assertEqual(self.start_scopes, ["NAM" if case == "nam_order" else "SHL"])

    def test_deadline_war_waits_for_other_wars_and_starts_on_the_next_cycle(self):
        for blocker in ("shl_war", "kyz", "glp", "north_war"):
            with self.subTest(blocker=blocker):
                self.setUp()
                self.pass_deadline()
                self.assertTrue(self.deadline_passed())
                if blocker == "shl_war":
                    self.facts[("SHL", "has_war", "no")] = False
                elif blocker == "north_war":
                    self.facts[("NAM", "has_war", "no")] = False
                else:
                    self.variable("SHL_war_" + blocker, 1, "SHL")
                self.execute_entries(block(self.event(4), "immediate"), "SHL")
                self.execute("ADISCORD_south_crisis_cycle")
                self.assertEqual(self.start_scopes, [], blocker)
                self.assertTrue(self.deadline_passed())
                if blocker == "shl_war":
                    self.facts[("SHL", "has_war", "no")] = True
                elif blocker == "north_war":
                    self.facts[("NAM", "has_war", "no")] = True
                else:
                    self.variable("SHL_war_" + blocker, 0, "SHL")
                self.execute("ADISCORD_south_crisis_cycle")
                self.assertEqual(self.start_scopes, ["SHL"], blocker)

    def test_penalty_reaches_only_unprepared_champions_and_ends_with_the_campaign(self):
        for unready, nam_exists, resolved, expected in (
            ((), True, True, set()),
            (("SHL",), True, True, {"SHL"}),
            (("NAM",), True, True, {"NAM"}),
            (("SHL", "NAM"), True, True, {"SHL", "NAM"}),
            ((), False, True, set()),
            ((), False, False, {"EFL"}),
        ):
            with self.subTest(unready=unready, nam_exists=nam_exists, resolved=resolved):
                self.setUp()
                self.unready(*unready)
                self.facts[("NAM", "exists", "yes")] = nam_exists
                self.flag("ADISCORD_nam_resource_war_resolved", resolved)
                self.execute("ADISCORD_south_mark_unprepared")
                penalised = {call[0] for call in self.calls if call[1] == "add_timed_idea"}
                self.assertEqual(penalised, expected)
                self.assertTrue(all(call[2:] == ("ADISCORD_south_unprepared_war", 180)
                                    for call in self.calls if call[1] == "add_timed_idea"))
                for tag in expected:
                    self.execute("ADISCORD_south_remove_path_spirit", tag)
                    self.assertFalse(self.facts[(tag, "has_idea", "ADISCORD_south_unprepared_war")])
                    self.assertIn((tag, "ADISCORD_economy_mark_dirty"), self.calls)
        ideas = next(e.value for e in parse_clausewitz(
            (ROOT / "common/ideas/ADISCORD_south_final_war_ideas.txt").read_text(encoding="utf-8")) if e.key == "ideas")
        idea = block(block(ideas, "country"), "ADISCORD_south_unprepared_war")
        self.assertEqual(scalar(idea, "picture"), "generic_army_problems")
        self.assertEqual({e.value for e in flatten(block(idea, "allowed")) if e.key == "original_tag"}, set(CANDIDATES))
        for hook in ("on_add", "on_remove"):
            self.assertIn(("ADISCORD_economy_mark_dirty", "yes"), [(e.key, e.value) for e in flatten(block(idea, hook))], hook)
        self.assertEqual({e.key: float(e.value) for e in block(idea, "modifier")},
                         {"army_org_factor": -0.10, "industrial_capacity_factory": -0.10, "war_support_factor": -0.05})
        # Only a deadline start penalises; the early focus route does not.
        start = body(EFFECTS, "ADISCORD_south_begin_hostilities")
        self.assertEqual(start.count("ADISCORD_south_mark_unprepared = yes"), 1)

    def test_suspension_keeps_the_anchor_and_only_story_campaigns_clear_it(self):
        self.pass_deadline()
        deadline = self.deadline_day()
        self.execute("ADISCORD_south_suspend_preparation")
        self.assertFalse(self.deadline_passed())
        self.assertEqual(self.deadline_day(), deadline, "A repelled war keeps the deadline it reached")
        self.calls.clear()
        self.execute("ADISCORD_south_check_deadline")
        self.assertEqual(self.calls, [], "No deadline without a running preparation")
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.deadline_day(), deadline)
        self.execute("ADISCORD_south_check_deadline")
        self.assertFalse(self.deadline_passed(), "A reopened preparation receives its own 180 days")
        self.flag("ADISCORD_south_preparation_started", age=180)
        self.execute("ADISCORD_south_check_deadline")
        self.assertTrue(self.deadline_passed())
        # A new story campaign starts a new calendar and a fresh contest.
        self.execute("ADISCORD_south_suspend_preparation")
        self.flag("ADISCORD_south_influence_seeded")
        self.execute("ADISCORD_south_clear_deadline")
        for suffix in ("", "_near", "_ai", "_pull_guard", "_warning"):
            self.assertIsNone(self.deadline_day(suffix), suffix)
        self.assertFalse(self.facts[("GLB", "has_global_flag", "ADISCORD_south_influence_seeded")])
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.deadline_day(), day_number(self.today()) + SHORT_WINDOW)
        self.assertNotIn("ADISCORD_south_clear_deadline", body(EFFECTS, "ADISCORD_south_suspend_preparation"))
        effects = EFFECTS.read_text(encoding="utf-8")
        self.assertEqual(effects.count("ADISCORD_south_clear_deadline = yes"), 0)
        nam = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8")
        # The island-exile settlement, the return-war start and the great-war start.
        self.assertEqual(nam.count("ADISCORD_south_clear_deadline = yes"), 3)

    def test_deadline_watch_is_one_bounded_chain_that_hits_the_date(self):
        watch = self.event(5)
        self.assertEqual(scalar(watch, "hidden"), "yes")
        self.assertEqual(scalar(watch, "is_triggered_only"), "yes")
        self.assertEqual([(e.key, e.value) for e in block(watch, "immediate")],
                         [("ADISCORD_south_deadline_watch_step", "yes")])
        step = body(EFFECTS, "ADISCORD_south_deadline_watch_step")
        self.assertNotRegex(step, r"\b(every|any|random)_\w+ = \{")
        for name in ("ADISCORD_south_deadline_reached", "ADISCORD_south_deadline_date_near", "ADISCORD_south_deadline_due",
                     "ADISCORD_south_deadline_watch_daily"):
            self.assertNotRegex(body(TRIGGERS, name), r"\b(every|any|random)_\w+ = \{", name)
        for name in ("ADISCORD_south_suspend_preparation", "ADISCORD_south_begin_hostilities", "ADISCORD_south_clear_preparation"):
            self.assertNotIn("ADISCORD_south_deadline_watch", body(EFFECTS, name), "Only the chain clears its flag")
        # The 540-day window, then a victory anchor that is close when the border is
        # first reached: the 180-day minimum decides.
        late = script_date(day_number("2165.10.1") + 180)
        for opened, anchored, fired in ((OPENED, None, DEADLINES[0]), ("2165.10.1", "2163.1.1", late)):
            with self.subTest(opened=opened):
                self.setUp()
                if anchored:
                    self.set_date(anchored)
                    self.anchor(VICTORY_WINDOW)
                self.set_date(opened)
                self.execute("ADISCORD_south_begin_preparation")
                self.assertEqual([entry for entry in self.scheduled if entry[1] == "ADISCORD_south.5"],
                                 [("SHL", "ADISCORD_south.5", {"days": 1})])
                self.assertEqual([entry[0] for entry in self.scheduled if entry[1] == "ADISCORD_south.6"], ["SHL", "NAM"])
                self.scheduled.clear()
                self.execute("ADISCORD_south_watch_deadline")
                self.execute("ADISCORD_south_crisis_cycle")
                self.assertEqual([entry for entry in self.scheduled if entry[1] == "ADISCORD_south.5"], [],
                                 "A pending chain is never duplicated")
                delay, steps, daily = 1, 0, 0
                while delay:
                    self.advance(delay)
                    self.scheduled.clear()
                    self.execute("ADISCORD_south_deadline_watch_step")
                    steps += 1
                    following = [entry for entry in self.scheduled if entry[1] == "ADISCORD_south.5"]
                    self.assertLessEqual(len(following), 1)
                    self.assertEqual(self.facts[("GLB", "has_global_flag", "ADISCORD_south_deadline_watch")], bool(following))
                    delay = following[0][2]["days"] if following else 0
                    self.assertIn(delay, (0, 1, 28))
                    daily += delay == 1
                    self.assertLess(steps, 100)
                self.assertEqual(self.today(), fired)
                self.assertTrue(self.deadline_passed())
                self.assertEqual([entry[1] for entry in self.scheduled], ["ADISCORD_south.4"])
                self.assertLessEqual(daily, 31)
        for stop in ("suspended", "started", "resolved"):
            with self.subTest(stop=stop):
                self.setUp()
                self.execute("ADISCORD_south_begin_preparation")
                if stop == "suspended":
                    self.execute("ADISCORD_south_suspend_preparation")
                else:
                    self.flag("ADISCORD_south_final_" + stop)
                self.scheduled.clear()
                self.execute("ADISCORD_south_deadline_watch_step")
                self.assertEqual(self.scheduled, [], stop)
                self.assertFalse(self.facts[("GLB", "has_global_flag", "ADISCORD_south_deadline_watch")], stop)
        # A chain lost with Shahrabad is replaced only after a missed step.
        self.setUp()
        self.execute("ADISCORD_south_begin_preparation")
        for age, expected in ((29, 0), (30, 1)):
            self.flag("ADISCORD_south_deadline_watch", age=age)
            self.scheduled.clear()
            self.execute("ADISCORD_south_watch_deadline")
            self.assertEqual(len(self.scheduled), expected, age)

    def test_preparation_announces_the_date_to_both_sides(self):
        announcement = self.event(6)
        self.assertNotIn("hidden", [e.key for e in announcement])
        self.assertEqual(scalar(announcement, "is_triggered_only"), "yes")
        option = block(announcement, "option")
        self.assertEqual(scalar(option, "custom_effect_tooltip"), "ADISCORD_south_deadline_rules_tt")
        self.assertIn("ADISCORD_south_unprepared_war", repr(block(option, "effect_tooltip")))
        self.facts[("NAM", "exists", "yes")] = False
        self.facts[("700", "controller")] = "EFL"
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual([entry[0] for entry in self.scheduled if entry[1] == "ADISCORD_south.6"], ["SHL", "EFL"])
        self.scheduled.clear()
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.scheduled, [], "Only the opening announces the date")
        notice_scopes = [
            actor.key for hidden in walk(self.effects["ADISCORD_south_begin_preparation"])
            if hidden.key == "hidden_effect" for actor in hidden.value
            if isinstance(actor.value, list) and any(e.key == "ADISCORD_south_announce_deadline" for e in actor.value)
        ]
        self.assertCountEqual(notice_scopes, CANDIDATES)

    def test_deadline_text_replaces_the_mission(self):
        self.assertNotIn("ADISCORD_south_crisis_clock", south_decisions())
        for path in (EFFECTS, TRIGGERS, DECISIONS, SCRIPTED_LOC, ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt",
                     ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("ADISCORD_south_crisis_clock", text, path.name)
            self.assertNotIn("days_mission_timeout@ADISCORD_south", text, path.name)
        dated = ("ADISCORD_south_status_crisis", "ADISCORD_south_status_preparation", "ADISCORD_south_status_warning",
                 "ADISCORD_south_status_deadline", "ADISCORD_south_deadline_passed_tt", "ADISCORD_south_warning_notice_tt",
                 "ADISCORD_south_preparation_timeout_tt", "ADISCORD_south_clock_pull_war_tt", "ADISCORD_south_deadline_rules_tt")
        for language in ("russian", "english"):
            keys = loc_keys(language)
            for key in ("ADISCORD_south_crisis_clock", "ADISCORD_south_crisis_clock_desc", "ADISCORD_south_crisis_clock_timeout_tt"):
                self.assertNotIn(key, keys, (language, key))
            for key in (*dated, "ADISCORD_south_unprepared_war", "ADISCORD_south_unprepared_war_desc",
                        "ADISCORD_south.6.t", "ADISCORD_south.6.d", "ADISCORD_south.6.a"):
                self.assertIn(key, keys, (language, key))
            for key in dated:
                self.assertIn("[ADISCORDSouthDeadlineDate]", loc_value(language, key), (language, key))
            for key in ("ADISCORD_south.6.d", "ADISCORD_south_unprepared_war_desc"):
                self.assertNotRegex(loc_value(language, key), r"\d|§|£", (language, key))
            for key in ("ADISCORD_south_status_crisis", "ADISCORD_south_preparation_ready_tt", "ADISCORD_south_status_preparation"):
                self.assertNotIn("2165", loc_value(language, key), (language, key))

    def test_shahrabad_victories_pull_the_clock_and_say_so(self):
        shl = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
        effects = definitions(shl)
        def nested_keys(items):
            for entry in items:
                yield entry.key
                if isinstance(entry.value, list):
                    yield from nested_keys(entry.value)

        # The victory effects only fire the report; each answer pulls the date its
        # future-tense tooltip has just shown, so the text never shows a moved date.
        for name, report in (
            ("SHL_qanat_war_victory", "ADISCORD_SHL.57"),
            ("SHL_glp_war_victory", "ADISCORD_SHL.66"),
            ("SHL_kyz_war_victory", "ADISCORD_SHL.73"),
        ):
            guarded = block(effects[name], "if")
            self.assertNotIn("ADISCORD_south_pull_clock_war", list(nested_keys(guarded)), name)
            self.assertIn(report, [scalar(e.value, "id") for e in guarded if e.key == "country_event"], name)
        self.assertIn(("ADISCORD_south_pull_clock_campaign", "yes"), [(e.key, e.value) for e in effects["SHL_cons_campaign_won"]])
        self.assertEqual(body(EFFECTS, "ADISCORD_south_pull_clock_war").count("ADISCORD_south_pull_clock_unit = yes"), 2)
        self.assertEqual(body(EFFECTS, "ADISCORD_south_pull_clock_campaign").count("ADISCORD_south_pull_clock_unit = yes"), 3)
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(
            (ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8")) if e.key == "country_event"}
        for event in ("ADISCORD_SHL.57", "ADISCORD_SHL.66", "ADISCORD_SHL.73"):
            for option in (e.value for e in events[event] if e.key == "option"):
                self.assertIn(("custom_effect_tooltip", "ADISCORD_south_clock_pull_war_tt"),
                              [(e.key, e.value) for e in option], event)
                hidden = [(e.key, e.value) for e in block(option, "hidden_effect")]
                self.assertEqual(hidden.count(("ADISCORD_south_pull_clock_war", "yes")), 1, event)

    def test_ai_moves_to_the_border_in_the_last_120_days(self):
        strategies = definitions(ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt")
        for north in ("NAM", "EFL", "AZH"):
            for actor, target in (("SHL", north), (north, "SHL")):
                name = f"ADISCORD_south_deadline_{actor.lower()}_border_{target.lower()}"
                strategy = strategies[name]
                self.assertEqual(scalar(block(strategy, "allowed"), "tag"), actor)
                self.assertEqual(scalar(strategy, "abort_when_not_enabled"), "yes")
                self.assertIn(("ADISCORD_south_ai_border_preparation", "yes"), [(e.key, e.value) for e in block(strategy, "enable")])
                order = block(strategy, "ai_strategy")
                self.assertEqual((scalar(order, "type"), scalar(order, "id")), ("prepare_for_war", target))
        for level in (0, 6):
            self.setUp()
            self.variable("ADISCORD_south_crisis_pull", level)
            self.execute("ADISCORD_south_begin_preparation")
            self.facts[("NAM", "is_ai", "yes")] = True
            self.assertEqual(self.deadline_day(), day_number(DEADLINES[level]))
            for age, before, expected in ((60, 121, False), (60, 120, True), (59, 120, False), (60, -30, True)):
                with self.subTest(level=level, age=age, before=before):
                    self.flag("ADISCORD_south_preparation_started", age=age)
                    self.set_date(script_date(int(self.deadline_day()) - before))
                    self.assertEqual(self.trigger_matches("ADISCORD_south_ai_border_preparation", "NAM"), expected)
        self.flag("ADISCORD_south_final_started")
        self.assertFalse(self.trigger_matches("ADISCORD_south_ai_border_preparation", "NAM"))

    def test_focus_route_stages_both_current_champions_before_the_calendar_window(self):
        gate = "ADISCORD_south_ai_border_preparation"
        self.open_preparation(age=60)
        for tag in CANDIDATES:
            self.facts[(tag, "is_ai", "yes")] = True
            self.facts[(tag, "numeric", "difficulty")] = 4
        # Ready champions on higher difficulty stage from the early window, not before it.
        self.set_date(script_date(int(self.deadline_day("_warning")) - 1))
        self.assertFalse(self.trigger_matches(gate, "NAM"))
        self.assertFalse(self.trigger_matches(gate, "SHL"))
        self.enter_early_window()
        for level in range(5):
            for tag in CANDIDATES:
                self.facts[(tag, "numeric", "difficulty")] = level
                self.assertEqual(self.trigger_matches(gate, tag), level > 2 and tag in ("NAM", "SHL"))
        self.facts[("SHL", "has_completed_focus", "SHL_conclave_army")] = False
        self.assertFalse(self.trigger_matches(gate, "NAM"))
        self.flag("ADISCORD_south_crisis_warned")
        self.facts[("SHL", "numeric", "difficulty")] = 2
        self.assertTrue(self.trigger_matches(gate, "SHL"))
        self.facts[("NAM", "has_war", "no")] = False
        self.assertFalse(self.trigger_matches(gate, "SHL"))
        self.facts[("NAM", "is_subject", "no")] = False
        self.assertTrue(self.trigger_matches(gate, "EFL"))
        self.assertFalse(self.trigger_matches(gate, "AZH"))
        self.facts[("EFL", "is_subject", "no")] = False
        self.assertTrue(self.trigger_matches(gate, "AZH"))
        self.facts[("AZH", "is_ai", "yes")] = False
        self.assertFalse(self.trigger_matches(gate, "AZH"))
        self.flag("ADISCORD_south_final_resolved")
        self.assertFalse(self.trigger_matches(gate, "SHL"))

    # ----- Influence contest -----

    def contest_country(self, tag, lean=0):
        self.regional_country(tag)
        self.variable("ADISCORD_south_coalition_influence", lean, tag)

    def ledger(self, tag):
        return self.facts.get((tag, "variable", "ADISCORD_south_coalition_influence"))

    def push(self, tag, delta, toward="north"):
        self.facts.temps["ADISCORD_south_push_delta"] = delta
        self.execute(f"ADISCORD_south_push_influence_{toward}", tag)
        self.facts.temps.clear()

    def test_seeds_add_to_the_ledger_once_and_redeem_returns_the_seeded_debt(self):
        self.contest_country("KDR", 5)
        self.facts[("KDR", "has_country_flag", "ADISCORD_south_indebted_to_SHL")] = True
        self.contest_country("WEF")
        self.execute("ADISCORD_south_begin_preparation")
        # Kadir: home -10 and Shahrabad's credit -15, added to the existing 5.
        self.assertEqual(self.ledger("KDR"), -20)
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_home_lean")], -25)
        self.assertTrue(self.facts[("KDR", "has_country_flag", "ADISCORD_south_seed_debt")])
        self.assertEqual(self.ledger("WEF"), 10)
        for champion in ("NAM", "SHL"):
            self.assertEqual(self.facts[(champion, "variable", "ADISCORD_south_influence_power")], 10)
            self.assertEqual(self.facts[(champion, "variable", "ADISCORD_south_envoy_push")], 10)
            self.assertEqual(self.facts[(champion, "variable", "ADISCORD_south_adviser_push")], 5)
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_influence_seeded")])
        self.execute("ADISCORD_south_seed_influence")
        self.assertEqual(self.ledger("KDR"), -45, "A direct second seed adds again")
        self.variable("ADISCORD_south_coalition_influence", -20, "KDR")
        self.flag("ADISCORD_south_preparation_started", False)
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.ledger("KDR"), -20, "A reopened preparation of the same contest does not seed")
        self.execute("ADISCORD_south_redeem_shl_debt", "KDR")
        self.assertFalse(self.facts[("KDR", "has_country_flag", "ADISCORD_south_indebted_to_SHL")])
        self.assertFalse(self.facts[("KDR", "has_country_flag", "ADISCORD_south_seed_debt")])
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_home_lean")], -10)
        self.execute("ADISCORD_south_redeem_shl_debt", "KDR")
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_home_lean")], -10)
        callers = [path for path in (ROOT / "focus_trees").rglob("*.txt")
                   if "ADISCORD_south_redeem_shl_debt" in path.read_text(encoding="utf-8")]
        self.assertEqual([path.name for path in callers], ["pragmatic.txt"])

    def test_contest_cycle_drifts_and_ties_in_one_fixed_tag_pass(self):
        cycle = body(EFFECTS, "ADISCORD_south_contest_cycle")
        for source in (cycle, body(EFFECTS, "ADISCORD_south_contest_drift")):
            self.assertNotRegex(source, r"\b(every|any|random)_\w+ = \{")
        self.assertEqual({tag for tag in REGIONAL if f"{tag} = {{ ADISCORD_south_contest_drift = yes }}" in cycle}, set(REGIONAL))
        self.assertEqual(body(EFFECTS, "ADISCORD_south_crisis_cycle").count("ADISCORD_south_contest_cycle = yes"), 1)
        self.effects["NAM_add_treasury"] = parse_clausewitz(
            "add_to_variable = { var = test_treasury value = NAM_treasury_amount }")
        self.contest_country("KDR")
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.ledger("KDR"), -10)
        for start, expected in ((20, 17), (-8, -10), (-30, -27)):
            self.variable("ADISCORD_south_coalition_influence", start, "KDR")
            self.execute("ADISCORD_south_contest_drift", "KDR")
            self.assertEqual(self.ledger("KDR"), expected, start)
        # Ties after the drift: Svetlogorye's tie and an oil client against Shahrabad's embassy.
        self.variable("ADISCORD_south_coalition_influence", -10, "KDR")
        self.variable("ADISCORD_south_north_tie", 2, "KDR")
        self.facts[("KDR", "has_country_flag", "NAM_oil_client")] = True
        self.facts[("KDR", "has_country_flag", "SHL_embassy")] = True
        self.execute("ADISCORD_south_contest_drift", "KDR")
        self.assertEqual(self.ledger("KDR"), -8)
        # A held economic contract pays every cycle, twice as much under the trade coalition.
        self.variable("ADISCORD_south_tool_kind", 2, "KDR")
        self.execute("ADISCORD_south_contest_drift", "KDR")
        self.assertEqual(self.facts[("NAM", "variable", "test_treasury")], 20)
        self.facts[("NAM", "has_completed_focus", "NAM_south_trade_coalition")] = True
        self.execute("ADISCORD_south_contest_drift", "KDR")
        self.assertEqual(self.facts[("NAM", "variable", "test_treasury")], 60)
        # Shahrabad gains one point of power every second cycle.
        power = ("SHL", "variable", "ADISCORD_south_influence_power")
        self.execute("ADISCORD_south_contest_cycle")
        self.execute("ADISCORD_south_contest_cycle")
        self.assertEqual(self.facts[power], 11)

    def test_push_helpers_need_the_window_a_free_country_and_an_open_sphere(self):
        self.contest_country("KDR")
        self.push("KDR", 10)
        self.assertEqual(self.ledger("KDR"), 0, "No contest before the preparation")
        self.execute("ADISCORD_south_begin_preparation")
        self.push("KDR", 10)
        self.assertEqual(self.ledger("KDR"), 0)
        self.push("KDR", 200)
        self.assertEqual(self.ledger("KDR"), 100)
        self.push("KDR", 120, "shl")
        self.assertEqual(self.ledger("KDR"), -20)
        self.facts[("KDR", "is_subject_of", "SHL")] = True
        self.push("KDR", 10)
        self.assertEqual(self.ledger("KDR"), -20, "A bound country is out of the contest")
        self.facts[("KDR", "is_subject_of", "SHL")] = False
        self.execute("ADISCORD_south_accept_spheres")
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_sphere")], 1)
        self.push("KDR", 10)
        self.assertEqual(self.ledger("KDR"), -20, "Shahrabad's agreed sphere does not move")
        self.push("KDR", 10, "shl")
        self.assertEqual(self.ledger("KDR"), -30)
        self.flag("ADISCORD_south_final_started")
        self.push("KDR", 10, "shl")
        self.assertEqual(self.ledger("KDR"), -30, "The war closes the contest")

    def test_path_tool_escrow_settles_exactly_once(self):
        decisions = south_decisions()
        self.effects["NAM_add_treasury"] = parse_clausewitz(
            "add_to_variable = { var = test_treasury value = NAM_treasury_amount }")
        self.effects["NAM_groups_refresh"] = []
        for name, kind in (("ADISCORD_south_nam_writ", 1), ("ADISCORD_south_nam_contract", 2),
                           ("ADISCORD_south_nam_charter", 3)):
            decision = decisions[name]
            self.assertEqual((scalar(decision, "cost"), scalar(decision, "days_remove")), ("0", "30"), name)
            self.assertEqual(body(DECISIONS, "\t" + name).count("add_political_power = -"), 1, name)
            self.assertEqual(body(DECISIONS, "\t" + name).count(f"var = ADISCORD_south_tool_escrow value = {kind} }}"), 1, name)
        writ = decisions["ADISCORD_south_nam_writ"]
        self.contest_country("KDR")
        self.execute("ADISCORD_south_begin_preparation")
        self.variable("ADISCORD_south_coalition_influence", 39, "KDR")
        self.event_root, self.event_sender = "NAM", "KDR"
        self.facts[("NAM", "numeric", "has_political_power")] = 100
        self.facts[("NAM", "equipment", "infantry_equipment")] = 6000
        self.assertFalse(self.matches(block(writ, "available"), "NAM"), "Lean below 40")
        self.variable("ADISCORD_south_coalition_influence", 40, "KDR")
        self.assertTrue(self.matches(block(writ, "available"), "NAM"))
        self.execute_entries(block(writ, "complete_effect"), "NAM")
        self.execute_entries(block(writ, "complete_effect"), "NAM")
        self.assertEqual(self.facts[("NAM", "numeric", "has_political_power")], 50, "One debit per offer")
        self.assertEqual(self.facts[("NAM", "equipment", "infantry_equipment")], 3000)
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_tool_escrow")], 1)
        self.assertFalse(self.matches(block(writ, "available"), "NAM"), "A pending escrow blocks a second offer")
        # Acceptance delivers the guard's rifles, the push and the tie once.
        self.execute("ADISCORD_south_deliver_tool", "KDR")
        self.execute("ADISCORD_south_deliver_tool", "KDR")
        self.assertEqual(self.facts[("KDR", "equipment", "infantry_equipment")], 3000)
        self.assertEqual(self.ledger("KDR"), 48)
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_tool_kind")], 1)
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_north_tie")], 2)
        self.assertFalse(self.facts[("KDR", "has_variable", "ADISCORD_south_tool_escrow")])
        # A refusal returns everything except political power and turns the country away.
        for settle in ("refuse", "cancel", "close"):
            with self.subTest(settle=settle):
                self.contest_country("WEF", 50)
                self.variable("ADISCORD_south_tool_escrow", 2, "WEF")
                self.facts[("NAM", "variable", "test_treasury")] = 0
                if settle == "refuse":
                    self.execute("ADISCORD_south_refuse_tool", "WEF")
                    self.assertEqual(self.ledger("WEF"), 45)
                    self.assertEqual(self.facts[("WEF", "flag_duration", "ADISCORD_south_tool_refused")], 56)
                elif settle == "cancel":
                    self.event_sender = "WEF"
                    contract = decisions["ADISCORD_south_nam_contract"]
                    self.execute_entries(block(contract, "cancel_effect"), "NAM")
                else:
                    self.execute("ADISCORD_south_close_coalition_diplomacy", "WEF")
                self.assertEqual(self.facts[("NAM", "variable", "test_treasury")], 300)
                self.assertFalse(self.facts[("WEF", "has_variable", "ADISCORD_south_tool_escrow")])
                self.execute("ADISCORD_south_refund_tool_escrow", "WEF")
                self.assertEqual(self.facts[("NAM", "variable", "test_treasury")], 300, "Refunded once")

    def test_war_start_clears_the_ledger_only_after_the_side_choice(self):
        self.assertNotIn("ADISCORD_south_close_coalition_diplomacy", body(EFFECTS, "ADISCORD_south_bind_to_champion"))
        for join in ("ADISCORD_south_join_shl_side", "ADISCORD_south_join_north_side"):
            source = body(EFFECTS, join)
            self.assertLess(source.index("var = ADISCORD_south_side"), source.index("ADISCORD_south_close_coalition_diplomacy = yes"), join)
        hostilities = body(EFFECTS, "ADISCORD_south_begin_hostilities")
        self.assertLess(hostilities.index("ADISCORD_south_offer_side_choices = yes"), hostilities.index("id = ADISCORD_south.75 days = 1"))
        self.assertEqual([(e.key, e.value) for e in block(self.event(75), "immediate")],
                         [("ADISCORD_south_close_unchosen_contests", "yes")])
        self.contest_country("KDR", 30)
        self.contest_country("WEF", -30)
        self.variable("ADISCORD_south_side", 2, "WEF")
        self.flag("ADISCORD_south_influence_seeded")
        self.flag("ADISCORD_south_spheres_agreed")
        self.execute("ADISCORD_south_close_unchosen_contests")
        self.assertIsNone(self.ledger("KDR"))
        self.assertEqual(self.ledger("WEF"), -30, "A country that chose keeps its record until its join effect")
        for flag in ("ADISCORD_south_influence_seeded", "ADISCORD_south_spheres_agreed"):
            self.assertFalse(self.facts[("GLB", "has_global_flag", flag)], flag)

    def test_a_demand_on_a_country_leaning_away_becomes_a_push(self):
        for demand in ("ADISCORD_south_demand_submission", "ADISCORD_south_demand_annexation"):
            branch = block(self.effects[demand], "if")
            self.assertIn(("ADISCORD_south_leans_away_from_root", "yes"), [(e.key, e.value) for e in block(branch, "limit")], demand)
            self.assertEqual([(e.key, e.value) for e in branch if e.key != "limit"],
                             [("ADISCORD_south_court_instead_of_demand", "yes")], demand)
        leaning = body(TRIGGERS, "ADISCORD_south_leans_away_from_root")
        self.assertIn("ADISCORD_south_lean_north_40 = yes", leaning)
        self.assertIn("ADISCORD_south_lean_shl_40 = yes", leaning)
        court = body(EFFECTS, "ADISCORD_south_court_instead_of_demand")
        self.assertIn("value = 10", court)

    def test_keizan_and_veyr_appeal_blocks_the_war_and_rearms_it(self):
        shl = (ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt").read_text(encoding="utf-8")
        for starter, target in (("SHL_start_kyz_war", 1), ("SHL_start_glp_war", 2)):
            source = body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", starter)
            first = source.index("ADISCORD_south_shl_strike_open = no")
            self.assertLess(first, source.index("ADISCORD_south_shl_strike_or_appeal = yes"), starter)
            self.assertIn(f"var = ADISCORD_south_strike_target value = {target} }}", source, starter)
        self.assertEqual(shl.count("ADISCORD_south_shl_strike_or_appeal = yes"), 2)
        self.contest_country("KYZ")
        self.execute("ADISCORD_south_begin_preparation")
        self.variable("ADISCORD_south_coalition_influence", 21, "KYZ")
        self.assertFalse(self.trigger_matches("ADISCORD_south_shl_strike_open", "KYZ"))
        self.variable("ADISCORD_south_coalition_influence", 20, "KYZ")
        self.assertTrue(self.trigger_matches("ADISCORD_south_shl_strike_open", "KYZ"))
        self.variable("ADISCORD_south_coalition_influence", 21, "KYZ")
        self.scheduled.clear()
        # The fixture expands event targets before execution; the effect saves the same one.
        self.targets["ADISCORD_south_strike_country"] = "KYZ"
        self.facts.temps["ADISCORD_south_strike_target"] = 1
        self.execute("ADISCORD_south_shl_strike_or_appeal")
        self.facts.temps.clear()
        self.assertTrue(self.facts[("KYZ", "has_country_flag", "ADISCORD_south_appeal_open")])
        self.assertEqual([entry[:2] for entry in self.scheduled], [("NAM", "ADISCORD_south.70")])
        self.scheduled.clear()
        self.facts.temps["ADISCORD_south_strike_target"] = 1
        self.execute("ADISCORD_south_shl_strike_or_appeal")
        self.facts.temps.clear()
        self.assertEqual(self.scheduled, [], "A pending appeal owns its callback")
        self.assertTrue(self.trigger_matches("ADISCORD_south_shl_strike_deferred", "KYZ"))
        # A sphere block schedules one re-check; a repeated ultimatum adds none.
        self.facts[("KYZ", "has_country_flag", "ADISCORD_south_appeal_open")] = False
        self.assertFalse(self.trigger_matches("ADISCORD_south_shl_strike_deferred", "KYZ"))
        self.flag("ADISCORD_south_spheres_agreed")
        self.variable("ADISCORD_south_sphere", 2, "KYZ")
        for _ in range(2):
            self.facts.temps["ADISCORD_south_strike_target"] = 1
            self.execute("ADISCORD_south_shl_strike_or_appeal")
            self.facts.temps.clear()
        self.assertEqual([entry[:2] for entry in self.scheduled], [("SHL", "ADISCORD_south.76")])
        self.assertTrue(self.facts[("KYZ", "has_country_flag", "ADISCORD_south_strike_recheck_pending")])
        self.assertTrue(self.trigger_matches("ADISCORD_south_shl_strike_deferred", "KYZ"))
        self.assertIn("clr_country_flag = ADISCORD_south_strike_recheck_pending",
                      EVENTS.read_text(encoding="utf-8").split("id = ADISCORD_south.76\n", 1)[1].split("country_event", 1)[0])
        self.facts[("KYZ", "has_country_flag", "ADISCORD_south_strike_recheck_pending")] = False
        self.facts[("GLB", "has_global_flag", "ADISCORD_south_spheres_agreed")] = False
        self.variable("ADISCORD_south_sphere", 0, "KYZ")
        self.scheduled.clear()
        veyr = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        veyr = veyr.split("\tSHL_ultimatum_veyr = {", 1)[1].split("\n\t}\n", 1)[0]
        self.assertIn("GLP = { ADISCORD_south_shl_strike_deferred = no }", veyr.split("cost = 50", 1)[0])
        self.assertNotIn("hidden_effect = {\n", veyr, "The returned price stays visible")
        # A declined appeal lets the war go on; an answered one defers it.
        self.facts[("KYZ", "has_country_flag", "ADISCORD_south_appeal_declined")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_shl_strike_open", "KYZ"))
        self.facts[("KYZ", "has_country_flag", "ADISCORD_south_appeal_answered")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_shl_strike_open", "KYZ"))
        rearm = self.event(76)
        self.assertEqual((scalar(rearm, "hidden"), scalar(rearm, "is_triggered_only")), ("yes", "yes"))
        events = EVENTS.read_text(encoding="utf-8")
        for days in (180, 90):
            self.assertIn(f"id = ADISCORD_south.76 days = {days}", events)

    def test_staging_reserves_use_home_supply_nodes_and_release_existing_assignments(self):
        policies = definitions(ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt")
        hubs = {line.split()[1] for line in (ROOT / "map/supply_nodes.txt").read_text().splitlines() if line.strip()}
        for tag, site in (("SHL", "707"), ("NAM", "689"), ("EFL", "68"), ("AZH", "692")):
            policy = policies[f"ADISCORD_south_{tag.lower()}_staging_reserve"]
            self.assertEqual(scalar(block(policy, "allowed"), "tag"), tag)
            self.assertEqual(scalar(policy, "abort_when_not_enabled"), "yes")
            enable = block(policy, "enable")
            self.assertEqual(scalar(enable, "ADISCORD_south_ai_border_preparation"), "yes")
            self.assertEqual([e.value for e in enable if not e.key], ["difficulty", ">", "2"])
            guard = block(enable, "NOT")
            if tag == "SHL":
                self.assertEqual(scalar(block(guard, "any_neighbor_country"), "ADISCORD_south_declarer_valid"), "yes")
            else:
                self.assertEqual(scalar(guard, "is_neighbor_of"), "SHL")
            conditions = block(enable, site)
            facts = {(site, "numeric", "supply_node"): 1, (site, "is_owned_by", tag): True,
                     (site, "is_controlled_by", tag): True}
            self.assertTrue(matches_conditions(conditions, facts, site))
            for key in facts:
                self.assertFalse(matches_conditions(conditions, {**facts, key: 0}, site))
            path, = (ROOT / "history/states").glob(f"{site}-*.txt")
            state = definitions(path)["state"]
            self.assertEqual(scalar(block(state, "history"), "owner"), tag)
            self.assertTrue(hubs.intersection(e.value for e in block(state, "provinces")))
            reserve = block(policy, "ai_strategy")
            self.assertEqual(scalar(reserve, "type"), "put_unit_buffers")
            self.assertEqual([e.value for e in block(reserve, "states")], [site])
            self.assertEqual(float(scalar(reserve, "ratio")), 0.15)
            self.assertEqual(scalar(reserve, "subtract_fronts_from_need"), "yes")
            self.assertEqual(scalar(reserve, "subtract_invasions_from_need"), "yes")

DECISIONS = ROOT / "common/decisions/ADISCORD_south_final_war_decisions.txt"
SCRIPTED_LOC = ROOT / "common/scripted_localisation/ADISCORD_south_final_war_scripted_loc.txt"
STRAIN_MODIFIER = ROOT / "common/dynamic_modifiers/ADISCORD_south_final_war_dynamic_modifiers.txt"
STRAIN_FIELDS = ("ADISCORD_south_strain_stability", "ADISCORD_south_strain_war_support", "ADISCORD_south_strain_factory")


def south_decisions():
    category = next(e.value for e in parse_clausewitz(DECISIONS.read_text(encoding="utf-8")) if e.key == "ADISCORD_south_final_war_category")
    return {e.key: e.value for e in category}


def loc_keys(language):
    raw = (ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml").read_bytes()
    return set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))


def loc_value(language, key):
    raw = (ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml").read_text(encoding="utf-8-sig")
    line = next(line for line in raw.splitlines() if re.match(rf" {re.escape(key)}:\d* \"", line))
    return line.split('"', 1)[1].rsplit('"', 1)[0]


class SouthWarOperationsTests(unittest.TestCase):
    """Home front strain, district orders and the hold mission shared by both champions."""

    def test_strain_rises_only_in_the_furnace_cycle_after_the_war_starts(self):
        cycle = body(EFFECTS, "ADISCORD_south_crisis_cycle")
        guard = cycle[cycle.index("ADISCORD_south_final_active = yes", cycle.rindex("if = {")):]
        self.assertIn("flag = ADISCORD_south_final_started", guard)
        self.assertIn("ADISCORD_south_strain_cycle = yes", guard)
        self.assertEqual(scope_calls(body(EFFECTS, "ADISCORD_south_strain_cycle"), "ADISCORD_south_strain_cycle_member"), {"SHL", "NAM", "EFL", "AZH"})
        member = body(EFFECTS, "ADISCORD_south_strain_cycle_member")
        self.assertIn("ADISCORD_south_war_champion = yes", member)
        self.assertIn("multiply_temp_variable = { var = ADISCORD_south_strain_delta value = 2 }", member)
        self.assertIn("add_to_temp_variable = { var = ADISCORD_south_strain_delta value = 3 }", member)
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            self.assertNotIn("ADISCORD_south_strain", path.read_text(encoding="utf-8-sig"), path.name)

    def test_strain_modifier_reads_the_derived_variables_and_refreshes_the_economy(self):
        modifier = next(e.value for e in parse_clausewitz(STRAIN_MODIFIER.read_text(encoding="utf-8")) if e.key == "ADISCORD_south_war_strain_dynamic")
        fields = {e.value for e in modifier if e.key not in ("icon", "enable")}
        self.assertEqual(fields, set(STRAIN_FIELDS))
        refresh = body(EFFECTS, "ADISCORD_south_refresh_strain")
        for field in STRAIN_FIELDS:
            self.assertIn(f"set_variable = {{ var = {field} value = ADISCORD_south_war_strain }}", refresh)
        self.assertIn("add_dynamic_modifier = { modifier = ADISCORD_south_war_strain_dynamic }", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", refresh)
        add = body(EFFECTS, "ADISCORD_south_add_strain")
        self.assertIn("min = 0", add)
        self.assertIn("max = 100", add)
        self.assertIn("NOT = { has_country_flag = ADISCORD_south_home_front_crisis }", add)
        self.assertNotIn("hidden_effect", add)

    def test_relief_tooltips_read_live_strain_and_clamp_each_preview(self):
        prefix = "ADISCORDSouthStrainAfter"
        definitions = parse_clausewitz(SCRIPTED_LOC.read_text(encoding="utf-8"))
        previews = {scalar(e.value, "name"): e.value for e in definitions if e.key == "defined_text"
                    and scalar(e.value, "name").startswith(prefix)}
        for language, label in (("russian", "Усталость тыла"), ("english", "Home front strain")):
            linked = set()
            for family in ("nam_resource_war", "SHL", "south_final_war"):
                path = ROOT / f"localisation/{language}/ADISCORD_{family}_l_{language}.yml"
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    key = line.split(":", 1)[0].strip()
                    match = re.search(re.escape(label) + r":? §G-(\d+)§!", line, re.I)
                    if key == "ADISCORD_south_district_order_result_tt":
                        match = re.search(r"§G(\d+)§! £NAM_war_cost_texticon", line)
                        self.assertIsNotNone(match, key)
                    elif key.startswith("ADISCORD_south_crisis_") or not match:
                        continue
                    name = prefix + match[1]
                    self.assertIn(f"[{name}]", line, key)
                    linked.add(name)
            self.assertEqual(linked, set(previews))
            self.assertEqual(loc_value(language, "ADISCORD_south_strain_none"), "")
            caption = loc_value(language, "ADISCORD_south_strain_preview")
            for var in ("ADISCORD_south_war_strain", "ADISCORD_south_preview_strain"):
                self.assertIn(f"[?{var}|0]", caption)

        for name, definition in previews.items():
            active, inactive = [entry.value for entry in definition if entry.key == "text"]
            self.assertEqual(scalar(active, "localization_key"), "ADISCORD_south_strain_preview")
            self.assertEqual(scalar(inactive, "localization_key"), "ADISCORD_south_strain_none")
            guard, copy, subtract, clamp = block(active, "trigger")
            self.assertEqual((guard.key, guard.value), ("has_variable", "ADISCORD_south_war_strain"))
            self.assertEqual((copy.key, scalar(copy.value, "value")), ("set_temp_variable", guard.value))
            self.assertEqual(subtract.key, "subtract_from_temp_variable")
            self.assertEqual(clamp.key, "clamp_temp_variable")
            for operation in (copy, subtract, clamp):
                self.assertEqual(scalar(operation.value, "var"), "ADISCORD_south_preview_strain")
            reduction = int(name.removeprefix(prefix))
            amount = int(scalar(subtract.value, "value"))
            floor, ceiling = (int(scalar(clamp.value, key)) for key in ("min", "max"))
            for current in (0, reduction - 1, reduction, reduction + 1, 73, 100):
                self.assertEqual(max(floor, min(ceiling, current - amount)), max(0, current - reduction))

    def test_every_terminal_path_closes_the_front(self):
        self.assertIn("ADISCORD_south_open_champion_front = yes", body(EFFECTS, "ADISCORD_south_prepare_champion"))
        self.assertIn("ADISCORD_south_close_champion_front = yes", body(EFFECTS, "ADISCORD_south_close_member_state"))
        close = body(EFFECTS, "ADISCORD_south_close_champion_front")
        guard = close.index("has_dynamic_modifier = { modifier = ADISCORD_south_war_strain_dynamic }")
        self.assertLess(guard, close.index("remove_dynamic_modifier = { modifier = ADISCORD_south_war_strain_dynamic }"))
        for variable in ("ADISCORD_south_war_strain", "ADISCORD_south_order_state", *STRAIN_FIELDS):
            self.assertIn(f"clear_variable = {variable}\n", close)
        for mission in ("ADISCORD_south_hold_districts", "ADISCORD_south_district_order_mission"):
            self.assertIn(f"remove_mission = {mission}", close)
        self.assertIn("clr_country_flag = ADISCORD_south_home_front_crisis", close)
        self.assertIn("remove_ideas = ADISCORD_south_order_failed", close)

    def test_home_front_crisis_answers_clear_the_marker_and_lower_strain(self):
        event = next(e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8")) if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_south.50")
        options = [e.value for e in event if e.key == "option"]
        self.assertEqual(len(options), 2)
        for option in options:
            hidden = block(option, "hidden_effect")
            self.assertIn(("clr_country_flag", "ADISCORD_south_home_front_crisis"), [(e.key, e.value) for e in hidden])
            delta = next(e for e in hidden if e.key == "set_temp_variable")
            self.assertLess(float(scalar(delta.value, "value")), 0)
            self.assertIn("custom_effect_tooltip", [e.key for e in option])

    def test_district_order_charges_one_exact_price_for_one_slot(self):
        order = south_decisions()["ADISCORD_south_district_order"]
        self.assertEqual(scalar(order, "cost"), "0")
        self.assertEqual(scalar(order, "custom_cost_text"), "ADISCORD_south_cost_district_order")
        text = body(DECISIONS, "ADISCORD_south_final_war_category")
        order_text = text[text.index("ADISCORD_south_district_order = {"):text.index("ADISCORD_south_district_order_mission = {")]
        self.assertEqual(order_text.count("add_political_power = -50"), 1)
        self.assertEqual(order_text.count("add_command_power = -25"), 1)
        for price in ("NOT = { has_political_power < 50 }", "NOT = { command_power < 25 }"):
            self.assertEqual(order_text.count(price), 2, price)
        self.assertEqual(order_text.count("NOT = { has_variable = ADISCORD_south_order_state }"), 2)
        self.assertIn("activate_mission = ADISCORD_south_district_order_mission", order_text)
        for language in ("russian", "english"):
            keys = loc_keys(language)
            for suffix in ("", "_blocked", "_tooltip"):
                self.assertIn("ADISCORD_south_cost_district_order" + suffix, keys, language)

    def test_order_mission_succeeds_on_capture_and_releases_the_slot(self):
        mission = south_decisions()["ADISCORD_south_district_order_mission"]
        self.assertEqual(scalar(mission, "days_mission_timeout"), "70")
        goal = [(e.key, e.value) for e in flatten(block(mission, "available"))]
        self.assertIn(("ADISCORD_south_state_held_by_root_side", "yes"), goal)
        for name in ("complete_effect", "timeout_effect", "cancel_effect"):
            self.assertIn("clear_variable", repr(block(mission, name)), name)
        self.assertIn("ADISCORD_south_final_active", repr(block(mission, "cancel_trigger")))

    def test_hold_mission_is_judged_only_at_timeout(self):
        mission = south_decisions()["ADISCORD_south_hold_districts"]
        available = block(mission, "available")
        self.assertEqual([(e.key, [(part.key, part.value) for part in e.value]) for e in available], [("hidden_trigger", [("always", "no")])])
        self.assertEqual(scalar(mission, "days_mission_timeout"), "84")
        self.assertIn("ADISCORD_south_count_own_key_states", repr(block(mission, "timeout_effect")))
        self.assertIn("activate_mission = ADISCORD_south_hold_districts", body(EFFECTS, "ADISCORD_south_strain_cycle_member"))

    def test_shahrabad_war_tree_feeds_the_shared_operations(self):
        member = body(EFFECTS, "ADISCORD_south_strain_cycle_member")
        self.assertIn("has_completed_focus = SHL_sw_ration_cards", member)
        self.assertIn("subtract_from_temp_variable = { var = ADISCORD_south_strain_delta value = 1 }", member)
        event = EVENTS.read_text(encoding="utf-8")
        answer = event[event.index("name = ADISCORD_south.50.a"):event.index("name = ADISCORD_south.50.b")]
        self.assertIn("has_completed_focus = SHL_sw_furnace_martial_law", answer)
        self.assertIn("SHL_sw_close_war = yes", body(EFFECTS, "ADISCORD_south_close_campaign_state"))
        shl = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
        close = body(shl, "SHL_sw_close_war")
        settled = close[close.index("has_global_flag = ADISCORD_south_final_resolved"):]
        self.assertIn("remove_dynamic_modifier = { modifier = SHL_south_war_dynamic }", settled)
        debt = close[:close.index("has_global_flag = ADISCORD_south_final_resolved")]
        self.assertIn("clr_country_flag = SHL_sw_war_bonds_debt", debt)
        modifier = (ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt").read_text(encoding="utf-8")
        enable = modifier[modifier.index("SHL_south_war_dynamic = {"):]
        self.assertIn("ADISCORD_south_final_active = yes", enable[:enable.index("}")])
        fields = re.findall(r"= (SHL_sw_\w+)", enable[:enable.index("\n}")])
        for variable in fields:
            self.assertIn(f"clear_variable = {variable}\n", settled)

    def test_svetlogorye_war_tree_feeds_the_shared_operations(self):
        member = body(EFFECTS, "ADISCORD_south_strain_cycle_member")
        self.assertIn("has_completed_focus = NAM_sw_district_compact_at_war", member)
        event = EVENTS.read_text(encoding="utf-8")
        answer = event[event.index("name = ADISCORD_south.50.a"):event.index("name = ADISCORD_south.50.b")]
        self.assertIn("has_completed_focus = NAM_sw_emergency_powers", answer)
        self.assertIn("NAM_sw_close_war = yes", body(EFFECTS, "ADISCORD_south_close_campaign_state"))
        nam = ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"
        close = body(nam, "NAM_sw_close_war")
        settled = close[close.index("has_global_flag = ADISCORD_south_final_resolved"):]
        self.assertIn("remove_dynamic_modifier = { modifier = NAM_south_war_dynamic }", settled)
        campaign = close[:close.index("has_global_flag = ADISCORD_south_final_resolved")]
        self.assertIn("clr_country_flag = NAM_sw_war_loans_debt", campaign)
        decisions = (ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt").read_text(encoding="utf-8")
        start = decisions.index("NAM_sw_inspect_captured_furnace = {")
        targets = re.search(r"targets = \{ ([\d ]+) \}", decisions[start:]).group(1).split()
        for state in targets:
            self.assertIn(f"{state} = {{ clr_state_flag = NAM_sw_furnace_inspected }}", campaign)
        modifier = (ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt").read_text(encoding="utf-8")
        enable = modifier[modifier.index("NAM_south_war_dynamic = {"):]
        self.assertIn("ADISCORD_south_final_active = yes", enable[:enable.index("}")])
        for variable in re.findall(r"= (NAM_sw_\w+)", enable[:enable.index("\n}")]):
            self.assertIn(f"clear_variable = {variable}\n", settled)
        triggers = (ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt").read_text(encoding="utf-8")
        gate = triggers[triggers.index("NAM_war_programmes_operable = {"):]
        self.assertIn("NAM_war_campaign_active = yes", gate[:gate.index("\n}")])
        self.assertIn("has_completed_focus = NAM_sw_conscription_of_the_south", triggers[triggers.index("NAM_war_campaign_active = {"):])

    def test_swapped_trees_carry_each_others_roots_hidden(self):
        # Native load_focus_tree keeps only completed focuses present in the new
        # tree, so every root crosses the swap as a hidden shared focus.
        from tools.builders import build_adiscord_focus_trees as builder

        outputs = {path.name: data.decode("utf-8") for path, data in builder.expected_outputs().items()}
        expanded = {source: builder.render_source(source) for source in builder.SOURCES}
        definitions = "\n".join(outputs.values())

        def definition(root):
            start = re.search(rf"(?m)^\t?(?:shared_)?focus = \{{\n\s*id = {root}\n", definitions)
            self.assertIsNotNone(start, root)
            end = definitions.find("\nshared_focus = {", start.end())
            return definitions[start.end():end if end > 0 else len(definitions)]

        for war, (tree_id, priors) in builder.TREE_SWAPS.items():
            war_output = outputs[builder.SOURCES[war]]
            for prior in priors:
                prior_output = outputs[builder.SOURCES[prior]]
                for root in builder.shown_roots(expanded[prior]):
                    self.assertRegex(war_output, rf"(?m)^\tshared_focus = {root}$", (war, root))
                    self.assertIn(f"allow_branch = {{ NOT = {{ has_focus_tree = {tree_id} }}", definition(root), root)
                for root in builder.shown_roots(expanded[war]):
                    self.assertRegex(prior_output, rf"(?m)^\tshared_focus = {root}$", (prior, root))
                    self.assertIn(f"allow_branch = {{ has_focus_tree = {tree_id}", definition(root), root)
        # Ungated descendants inherit campaign visibility from their parents.
        per_source = builder.source_clauses(expanded, builder.swap_plan(expanded)[1])
        for source, clause in per_source.items():
            authored = parse_clausewitz(expanded[source])
            rows = next((e.value for e in authored if e.key == "focus_tree"), authored)
            gated = {scalar(row.value, "id") for row in rows if row.key in ("focus", "shared_focus")
                     and isinstance(row.value, list) and (not any(e.key == "prerequisite" for e in row.value)
                     or any(e.key == "allow_branch" for e in row.value))}
            native = parse_clausewitz(outputs[builder.SOURCES[source]])
            gates = {scalar(row.value, "id"): e.value for row in native if row.key == "shared_focus"
                     for e in row.value if e.key == "allow_branch"}
            self.assertEqual(set(gates), gated, source)
            for name, gate in gates.items():
                self.assertEqual(gate[0].key, "NOT" if clause.startswith("NOT") else "has_focus_tree", name)
                self.assertIn("has_focus_tree", repr(gate[0]), name)
        for name in ("ADISCORD_south_load_war_tree", "ADISCORD_south_restore_prior_tree"):
            self.assertIn("mark_focus_tree_layout_dirty = yes", body(EFFECTS, name))

    def test_expedition_delivery_matches_the_donors_payment(self):
        audit = json.loads((ROOT / "tools/data/division_template_audit.json").read_text(encoding="utf-8"))
        templates = {row["key"]: row["computed"] for row in audit["templates"]}
        full = templates["script_south_desert_expedition"]
        effects = definitions(EFFECTS)
        spawn = block(effects["ADISCORD_south_create_expedition_division"], "create_unit")
        division = parse_clausewitz(scalar(spawn, "division"))
        self.assertEqual(scalar(division, "division_template"), "Desert Expedition")
        men = full["manpower"] * float(scalar(division, "start_manpower_factor"))
        rifles = full["equipment"]["infantry_equipment"] * float(scalar(division, "start_equipment_factor"))

        base = block(effects["ADISCORD_south_settle_expedition"], "if")
        extra = block(base, "if")
        self.assertEqual(scalar(block(block(extra, "limit"), "FROM"), "ADISCORD_south_large_expedition"), "yes")
        for payment, count in ((base, 2), (extra, 1)):
            stock = block(payment, "add_equipment_to_stockpile")
            self.assertEqual(scalar(stock, "type"), "infantry_equipment")
            capitals = [
                child.value
                for entry in payment if entry.key == "FROM"
                for child in entry.value if child.key == "capital_scope"
            ]
            self.assertEqual(len(capitals), 1)
            calls = [
                entry.value for entry in capitals[0]
                if entry.key == "ADISCORD_south_create_expedition_division"
            ]
            self.assertEqual(calls, ["yes"] * count)
            self.assertEqual(men * count, -int(scalar(payment, "add_manpower")))
            self.assertAlmostEqual(rifles * count, -int(scalar(stock, "amount")), delta=1)

    def test_expedition_and_defector_escrow_settles_exactly_once(self):
        decisions = south_decisions()
        for name, flag, event, refund in (
            ("ADISCORD_south_request_expedition", "ADISCORD_south_expedition_pending", "ADISCORD_south.60", "ADISCORD_south_refund_expedition"),
            ("ADISCORD_south_court_defector", "ADISCORD_south_defector_pending", "ADISCORD_south.63", "ADISCORD_south_refund_defector"),
        ):
            decision = decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0", name)
            effect = repr(block(decision, "complete_effect"))
            for part in (flag, event, "ADISCORD_south.66"):
                self.assertIn(part, effect, (name, part))
            self.assertIn(flag, repr(block(decision, "available")), name)
            refunds = body(EFFECTS, refund)
            self.assertIn(f"has_country_flag = {flag}", refunds)
            self.assertIn(f"clr_country_flag = {flag}", refunds)
            self.assertIn(f"{refund} = yes", body(EFFECTS, "ADISCORD_south_close_champion_front"))
            for language in ("russian", "english"):
                keys = loc_keys(language)
                cost = scalar(decision, "custom_cost_text")
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertIn(cost + suffix, keys, (language, cost))
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8")) if e.key == "country_event"}
        for request, refund, settle in (
            ("ADISCORD_south.60", "ADISCORD_south_refund_expedition", "ADISCORD_south_settle_expedition"),
            ("ADISCORD_south.63", "ADISCORD_south_refund_defector", "ADISCORD_south_settle_defection"),
        ):
            options = [e.value for e in events[request] if e.key == "option"]
            self.assertIn(refund, repr(options[0]), request)
            self.assertIn(settle, repr(options[1]), request)
            self.assertTrue(block(options[1], "trigger"), request)
        fallback = repr(events["ADISCORD_south.66"])
        self.assertIn("ADISCORD_south_refund_expedition", fallback)
        self.assertIn("ADISCORD_south_refund_defector", fallback)
        for settle, gate, flag in (
            ("ADISCORD_south_settle_expedition", "ADISCORD_south_expedition_possible", "ADISCORD_south_expedition_pending"),
            ("ADISCORD_south_settle_defection", "ADISCORD_south_defection_possible", "ADISCORD_south_defector_pending"),
        ):
            source = body(EFFECTS, settle)
            self.assertLess(source.index(f"{gate} = yes"), source.index(f"clr_country_flag = {flag}"), settle)
            self.assertIn(f"has_country_flag = {flag}", body(TRIGGERS, gate))
        template = body(EFFECTS, "ADISCORD_south_ensure_expedition_template")
        self.assertIn("is_locked = yes", template)
        self.assertIn('NOT = { has_template = "Desert Expedition" }', template)

    def test_operations_are_localised_in_both_languages(self):
        source = DECISIONS.read_text(encoding="utf-8")
        keys = set(south_decisions())
        keys |= {name + "_desc" for name in south_decisions()}
        keys |= set(re.findall(r"(?:tooltip|custom_effect_tooltip|custom_cost_text) = (\w+)", source))
        keys |= {"ADISCORD_south_war_strain_dynamic", "ADISCORD_south_order_failed", "ADISCORD_south_order_failed_desc"}
        loc = (ROOT / "common/scripted_localisation/ADISCORD_south_final_war_scripted_loc.txt").read_text(encoding="utf-8")
        start = loc.index("name = ADISCORDSouthStrain")
        keys |= set(re.findall(r"localization_key = (\w+)", loc[start:]))
        for language in ("russian", "english"):
            self.assertEqual(sorted(keys - loc_keys(language)), [], language)


class FocusAggregateTests(unittest.TestCase):
    """TFR-style display pairs must show exactly the variable change a focus applies."""

    DYNAMICS = (
        ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt",
        ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt",
    )
    IDEAS = (
        ROOT / "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt",
    )
    TREES = (
        ROOT / "focus_trees/NAM/main/focuses.txt",
        ROOT / "focus_trees/NAM/wartime/focuses.txt",
        ROOT / "focus_trees/NAM/postwar/focuses.txt",
        ROOT / "focus_trees/NAM/defeated/focuses.txt",
        ROOT / "focus_trees/SHL/south_war/focuses.txt",
        ROOT / "focus_trees/NAM/south_war/focuses.txt",
        *SHL_TREES,
    )
    REFRESH = {
        "NAM_administration_dynamic": "NAM_refresh_administration",
        "NAM_garrison_dynamic": "NAM_refresh_garrison",
        "NAM_navy_dynamic": "NAM_refresh_navy",
        "NAM_air_dynamic": "NAM_refresh_air",
        "SHL_conclave_power_dynamic": "SHL_refresh_conclave_power",
        "SHL_south_war_dynamic": "SHL_refresh_south_war",
        "NAM_south_war_dynamic": "NAM_refresh_south_war",
    }

    def setUp(self):
        self.fields = {}
        for path in self.DYNAMICS:
            for entry in parse_clausewitz(path.read_text(encoding="utf-8")):
                if entry.key in self.REFRESH:
                    self.fields[entry.key] = {e.value: e.key for e in entry.value if e.key not in ("icon", "enable")}
        self.display = {}
        for path in self.IDEAS:
            root = next(e.value for e in parse_clausewitz(path.read_text(encoding="utf-8")) if e.key == "ideas")
            for group in root:
                for idea in group.value:
                    name = next((e.value for e in idea.value if e.key == "name"), None)
                    if name in self.REFRESH:
                        modifier = next(e.value for e in idea.value if e.key == "modifier")
                        allowed = next(e.value for e in idea.value if e.key == "allowed")
                        self.assertEqual([(e.key, e.value) for e in allowed], [("always", "no")], idea.key)
                        self.display[idea.key] = (name, {e.key: float(e.value) for e in modifier})

    def test_every_display_delta_matches_the_applied_change(self):
        checked = set()
        owners = {var: (name, field) for name, fields in self.fields.items() for var, field in fields.items()}
        for tree in self.TREES:
            for identifier, focus in focus_blocks(tree).items():
                reward = next(e.value for e in focus if e.key == "completion_reward")
                previewed = {}
                applied = {}
                for tip in (entry.value for entry in reward if entry.key == "effect_tooltip"):
                    for entry in (part for part in flatten(tip) if part.key == "swap_ideas"):
                        swap = {part.key: part.value for part in entry.value}
                        if swap["remove_idea"] in self.display:
                            base_name, base = self.display[swap["remove_idea"]]
                            name, delta = self.display[swap["add_idea"]]
                            self.assertEqual((base_name, base), (name, {}), identifier)
                            self.assertNotIn(name, previewed, identifier)
                            previewed[name] = delta
                hidden = [part for entry in reward if entry.key == "hidden_effect" for part in entry.value]
                # A lane-end variant shows the aggregate its shared lane core applies.
                for core in (entry.key for entry in reward if entry.key.endswith("_core") and entry.value == "yes"):
                    effect = parse_clausewitz(body(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt", core))
                    hidden += [part for entry in effect if entry.key == "hidden_effect" for part in entry.value]
                for entry in (part for part in hidden if part.key == "add_to_variable"):
                    change = {part.key: part.value for part in entry.value}
                    if change.get("var") in owners:
                        name, field = owners[change["var"]]
                        fields = applied.setdefault(name, {})
                        fields[field] = fields.get(field, 0) + float(change["value"])
                self.assertEqual(previewed, applied, identifier)
                for name in previewed:
                    self.assertIn((self.REFRESH[name], "yes"), [(e.key, e.value) for e in hidden], identifier)
                checked.update(previewed)
        self.assertEqual(checked, set(self.REFRESH))

    def test_display_ideas_are_never_installed(self):
        names = set(self.display)
        for tree in self.TREES:
            text = read_focus_source(tree)
            for name in names:
                self.assertNotIn(f"add_ideas = {name}", text)
                self.assertNotIn(f"add_timed_idea = {{ idea = {name}", text)

    def test_refresh_attaches_and_updates_without_reset(self):
        for name, refresh in self.REFRESH.items():
            path = ROOT / ("common/scripted_effects/ADISCORD_nam_resource_war_effects.txt" if name.startswith("NAM") else "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt")
            source = body(path, refresh)
            self.assertIn(f"add_dynamic_modifier = {{ modifier = {name} }}", source)
            self.assertIn("force_update_dynamic_modifier = yes", source)
            if name not in ("NAM_navy_dynamic", "NAM_air_dynamic"):
                self.assertIn("ADISCORD_economy_mark_dirty = yes", source)
            self.assertNotIn("set_variable", source)


if __name__ == "__main__":
    unittest.main()
