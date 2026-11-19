"""Static contracts of the southern final war between Svetlogorye and Shahrabad.

The checks cover script wiring only: side lists, terminal cleanup, flag order
and path focuses. Engine war, faction and peace behaviour needs a game run.
"""

from pathlib import Path
from dataclasses import replace
import json
import re
import unittest

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


class SouthFinalWarContractTests(unittest.TestCase):
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
        checked = 0
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
                checked += 1
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
        self.assertGreaterEqual(checked, 16)

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
        self.assertEqual(delayed, [])
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
        self.facts = {}
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
            self.facts[(tag, "numeric", "date")] = 21650101
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
        """Open the preparation and age it past the minimum before an early start."""
        self.execute("ADISCORD_south_begin_preparation")
        self.assertTrue(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_preparation_started")))
        self.flag("ADISCORD_south_preparation_started", age=age)

    def set_date(self, date):
        for tag in CANDIDATES:
            self.facts[(tag, "numeric", "date")] = numeric_date(date)

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
            elif entry.key in ("set_variable", "check_variable") and scalar(entry.value, "value") in ("ROOT", "FROM"):
                # HOI4 stores country scope references in variables as numeric tag IDs.
                country = self.event_root if scalar(entry.value, "value") == "ROOT" else self.event_sender
                tag_id = str((*CHAMPIONS, *REGIONAL).index(country) + 1)
                fields = [replace(field, value=tag_id) if field.key == "value" else field for field in entry.value]
                result.append(replace(entry, value=fields))
            elif entry.key == "check_variable" and scalar(entry.value, "var").startswith("global."):
                fields = [replace(e, value=e.value.removeprefix("global.")) if isinstance(e.value, str) else e
                          for e in entry.value]
                result.append(replace(entry, key="GLB", value=[replace(entry, value=fields)]))
            elif entry.key == "check_variable" and scalar(entry.value, "value").startswith("global."):
                fields = [
                    replace(field, value=str(self.facts.get(("GLB", "variable", field.value.removeprefix("global.")), 0)))
                    if field.key == "value" else field
                    for field in entry.value
                ]
                result.append(replace(entry, value=fields))
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

    def test_expedition_offer_checks_the_price_of_the_requested_force(self):
        self.event_root = "EFL"
        self.flag("ADISCORD_south_final_started")
        for champion, side, focus in (
            ("SHL", 1, "SHL_sw_buy_the_sands"),
            ("NAM", 2, "NAM_sw_protectorate_offers"),
        ):
            self.event_sender = champion
            self.variable("ADISCORD_south_side", side, champion)
            self.variable("ADISCORD_south_side", side, "EFL")
            self.facts[(champion, "has_country_flag", "ADISCORD_south_expedition_pending")] = True
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
                        self.assertEqual(self.trigger_matches("ADISCORD_south_expedition_possible", "EFL"), ready)

    def test_normalisation_protects_both_neighbours_in_southern_negotiations(self):
        for normalised in (False, True):
            self.facts[("NAM", "has_completed_focus", "NAM_normalisation")] = normalised
            for tag in ("EFL", "AZH", "KDR"):
                self.facts[(tag, "tag", tag)] = True
                self.assertEqual(self.trigger_matches("NAM_neighbour_sovereignty_recognised", tag),
                                 normalised and tag in ("EFL", "AZH"))

    def test_both_leaders_and_their_allies_can_invite_a_regional_country(self):
        decisions = definitions(ROOT / "common/decisions/ADISCORD_south_final_war_decisions.txt")
        invitation = block(decisions["ADISCORD_south_final_war_category"], "ADISCORD_south_invite_to_coalition")
        self.assertEqual({e.value for e in block(invitation, "targets")}, set(REGIONAL))
        self.event_sender = "KYZ"
        for tag in ("KDR", "WEF", "KYZ"):
            for key, value in (("exists", "yes"), ("has_capitulated", "no"), ("is_subject", "no"),
                               ("is_in_faction", "no"), ("has_war", "no")):
                self.facts[(tag, key, value)] = True
        for ally, leader in (("KDR", "NAM"), ("WEF", "SHL")):
            self.facts[(ally, "faction_leader")] = leader
            self.facts[(ally, "is_in_faction_with", leader)] = True
            self.facts[(ally, "is_in_faction", "no")] = False
            self.facts[(leader, "is_faction_leader", "yes")] = True
            self.facts[(leader, "is_in_faction", "no")] = False
        for sender in ("NAM", "SHL", "KDR", "WEF"):
            with self.subTest(sender=sender):
                self.event_root = sender
                self.assertTrue(self.matches(block(invitation, "allowed"), sender))
                self.assertTrue(self.matches(block(invitation, "visible"), sender))
                self.assertTrue(self.matches(block(invitation, "target_trigger"), sender))
        self.event_root = "WEF"
        self.event_sender = "KDR"
        self.assertTrue(self.matches(block(invitation, "visible"), "WEF"))
        self.event_root = "NAM"
        self.assertFalse(self.matches(block(invitation, "visible"), "NAM"))
        self.event_sender = "KYZ"
        for key in ("has_capitulated", "is_subject"):
            self.facts[("KYZ", key, "no")] = False
            self.assertFalse(self.trigger_matches("ADISCORD_south_coalition_invitee", "KYZ"), key)
            self.facts[("KYZ", key, "no")] = True

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

    def test_envoy_reserves_one_recipient_and_consent_names_the_actual_leader(self):
        invitation = south_decisions()["ADISCORD_south_invite_to_coalition"]
        self.event_root, self.event_sender = "WEF", "KDR"
        for tag in ("WEF", "KDR"):
            for key, value in (("exists", "yes"), ("is_subject", "no"), ("has_capitulated", "no")):
                self.facts[(tag, key, value)] = True
        self.facts[("WEF", "is_in_faction_with", "SHL")] = True
        self.facts[("KDR", "is_in_faction_with", "NAM")] = True
        self.facts[("KDR", "faction_leader")] = "NAM"
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
        self.facts[("WEF", "is_in_faction_with", "SHL")] = False
        self.facts[("WEF", "is_in_faction_with", "NAM")] = True
        self.assertFalse(self.matches(guard, "KDR"))
        self.assertEqual(join_orders(), [])
        self.variable("ADISCORD_south_offer_kind", 2, "KDR")
        self.execute_entries(block(reject, "hidden_effect"), "KDR")
        self.assertFalse(self.facts[("KDR", "has_variable", "ADISCORD_south_coalition_envoy")])
        self.assertEqual(self.facts[("KDR", "variable", "ADISCORD_south_offer_kind")], 2)
        self.assertTrue(self.facts[("KDR", "is_in_faction_with", "NAM")])

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
                self.facts[(current, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key in ("set_variable", "add_to_variable", "clamp_variable"):
                name = scalar(entry.value, "var")
                holder = "GLB" if name.startswith("global.") else current
                name = name.removeprefix("global.")
                old = self.facts.get((holder, "variable", name), 0)
                if entry.key == "clamp_variable":
                    value = min(float(scalar(entry.value, "max")), max(float(scalar(entry.value, "min")), old))
                else:
                    value = float(scalar(entry.value, "value"))
                    if entry.key == "add_to_variable":
                        value += old
                self.variable(name, value, holder)
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
        for path in (ROOT / "focus_trees/NAM/postwar/focuses.txt", ROOT / "focus_trees/NAM/defeated/focuses.txt", *SHL_TREES):
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
        for focus in ("NAM_rad_great_war_plan", "NAM_hum_union_call", "NAM_board_stock_mobilisation"):
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
            self.calls.clear()
            for tag in ("NAM", "SHL"):
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), phase == "complete", phase)
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, phase == "complete", phase)
        self.flag("NAM_great_war_won", False)
        self.facts[("RHM", "exists", "yes")] = False
        self.facts[("EFL", "exists", "yes")] = False
        self.facts[("AZH", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_crisis_open"), "No remaining great-war opponents")

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

    def test_economic_offer_requires_pragmatic_sender_and_refusal_stays_peaceful(self):
        self.event_root = "EFL"
        self.event_sender = "NAM"
        self.facts[("NAM", "tag", "NAM")] = True
        self.variable("ADISCORD_south_offer_kind", 4, "EFL")
        self.assertFalse(self.trigger_matches("ADISCORD_south_offer_answer_valid", "EFL"))
        self.facts[("NAM", "has_completed_focus", "NAM_pragmatic_compact")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_offer_answer_valid", "EFL"))
        self.execute("ADISCORD_south_refuse_offer", "EFL")
        self.assertEqual(self.calls, [])
        for champion in ("SHL", "NAM"):
            self.assertFalse(self.facts.get(("EFL", "has_country_flag", "ADISCORD_south_refused_" + champion), False))
        self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
        self.variable("ADISCORD_south_offer_kind", 4, "EFL")
        self.execute("ADISCORD_south_accept_offer", "EFL")
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_NAM")])
        self.assertEqual([call[:3] for call in self.calls], [("EFL", "country_event", "ADISCORD_south.41")])
        chosen = list(selected_effects(self.expand(self.effects["ADISCORD_south_finalize_submission"]), self.facts, "EFL"))
        autonomy = [scalar(e.value, "autonomy_state") for scope, e in chosen if e.key == "set_autonomy"]
        self.assertEqual(autonomy, ["autonomy_NAM_economic_contract"])
        keys = [e.key for _, e in chosen]
        self.assertLess(keys.index("set_autonomy"), keys.index("country_event"))
        self.assertEqual([(scope, scalar(e.value, "id")) for scope, e in chosen if e.key == "country_event"],
                         [("NAM", "ADISCORD_south.42")])

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
        finalizer = self.expand(self.effects["ADISCORD_south_finalize_submission"])
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
                                 [("EFL", "ADISCORD_south_submits_to_SHL"), ("EFL", "ADISCORD_south_submits_to_NAM")])
                self.facts[("EFL", "has_war_with", sender)] = True
                self.assertFalse(any(e.key in ("puppet", "set_autonomy", "NAM_apply_border_protocol")
                                     for _, e in self.submission_effects("EFL")))

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

    def test_deadline_dates_and_offsets_follow_the_pull_levels(self):
        triggers = definitions(TRIGGERS)
        offsets = {"ADISCORD_south_deadline_reached": 0, "ADISCORD_south_deadline_date_near": 31,
                   "ADISCORD_south_deadline_date_in_ai_window": 120, "ADISCORD_south_deadline_can_pull": 135}
        for name, offset in offsets.items():
            branches = [e.value for e in block(triggers[name], "OR")]
            # A sixth unit can never be added, so the pull guard has no level 6.
            self.assertEqual(len(branches), 6 if name == "ADISCORD_south_deadline_can_pull" else 7, name)
            for level, branch in enumerate(branches):
                guard = block(branch, "check_variable")
                compare = "less_than" if level == 0 else "greater_than_or_equals" if level == 6 else "equals"
                self.assertEqual((scalar(guard, "var"), scalar(guard, "value"), scalar(guard, "compare")),
                                 ("global.ADISCORD_south_crisis_pull", str(max(level, 1)), compare), (name, level))
                literal = [e.value for e in flatten(branch) if not e.key][-1]
                self.assertEqual(literal, script_date(day_number(DEADLINES[level]) - offset), (name, level))
        for level in range(1, 7):
            self.assertEqual(day_number(DEADLINES[level - 1]) - day_number(DEADLINES[level]), 15, level)
        # The latest observed opening (2164.1.15) plus the postwar route's 651
        # readiness days still fits before the earliest possible deadline.
        self.assertGreater(day_number(DEADLINES[-1]), day_number("2164.1.15") + 651)

    def test_deadline_is_reached_on_its_date_and_shown_for_its_level(self):
        self.assertFalse(self.trigger_matches("ADISCORD_south_deadline_reached"), "2165.1.1 is before every level")
        self.set_date("2166.2.28")
        self.assertFalse(self.trigger_matches("ADISCORD_south_deadline_reached"), "An unset counter is level 0")
        self.set_date("2166.3.1")
        self.assertTrue(self.trigger_matches("ADISCORD_south_deadline_reached"))
        shown = next(e.value for e in parse_clausewitz(SCRIPTED_LOC.read_text(encoding="utf-8"))
                     if e.key == "defined_text" and scalar(e.value, "name") == "ADISCORDSouthDeadlineDate")
        texts = [e.value for e in shown if e.key == "text"]
        for level, deadline in enumerate(DEADLINES):
            with self.subTest(level=level):
                self.variable("ADISCORD_south_crisis_pull", level)
                self.set_date(script_date(day_number(deadline) - 1))
                self.assertFalse(self.trigger_matches("ADISCORD_south_deadline_reached"))
                self.set_date(deadline)
                self.assertTrue(self.trigger_matches("ADISCORD_south_deadline_reached"))
                chosen = next(text for text in texts
                              if not any(e.key == "trigger" for e in text) or self.matches(block(text, "trigger")))
                self.assertEqual(scalar(chosen, "localization_key"), f"ADISCORD_south_deadline_date_{level}")
                for language, expected in (("russian", DEADLINE_TEXT_RU[level]), ("english", DEADLINE_TEXT_EN[level])):
                    self.assertEqual(loc_value(language, f"ADISCORD_south_deadline_date_{level}"), expected, language)

    def test_pull_counts_from_game_start_with_cap_and_guard(self):
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
        # A unit applies only while the current deadline is more than 135 days away.
        for level, deadline in enumerate(DEADLINES[:-1]):
            with self.subTest(level=level):
                self.variable("ADISCORD_south_crisis_pull", level)
                self.set_date(script_date(day_number(deadline) - 135))
                self.execute("ADISCORD_south_pull_clock_unit")
                self.assertEqual(self.pull(), level)
                self.set_date(script_date(day_number(deadline) - 136))
                self.execute("ADISCORD_south_pull_clock_unit")
                self.assertEqual(self.pull(), level + 1)
                self.assertGreater(day_number(DEADLINES[level + 1]) - day_number(self.today()), 120)
        # A campaign meeting the guard partway keeps only the units that fit.
        self.variable("ADISCORD_south_crisis_pull", 0)
        self.set_date("2165.10.1")
        self.execute("ADISCORD_south_pull_clock_campaign")
        self.assertEqual(self.pull(), 2)

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

    def test_suspension_clears_the_deadline_and_reopening_restarts_the_minimum(self):
        self.pass_deadline()
        self.execute("ADISCORD_south_suspend_preparation")
        self.assertFalse(self.deadline_passed())
        self.calls.clear()
        self.execute("ADISCORD_south_check_deadline")
        self.assertEqual(self.calls, [], "No deadline without a running preparation")
        self.execute("ADISCORD_south_begin_preparation")
        self.execute("ADISCORD_south_check_deadline")
        self.assertFalse(self.deadline_passed(), "A reopened preparation receives its own 180 days")
        self.flag("ADISCORD_south_preparation_started", age=180)
        self.execute("ADISCORD_south_check_deadline")
        self.assertTrue(self.deadline_passed())

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
        for opened, fired in (("2163.6.13", DEADLINES[0]), ("2166.1.1", script_date(day_number("2166.1.1") + 180))):
            with self.subTest(opened=opened):
                self.setUp()
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
        self.execute("ADISCORD_south_begin_preparation")
        self.facts[("NAM", "is_ai", "yes")] = True
        for level in (0, 6):
            self.variable("ADISCORD_south_crisis_pull", level)
            for age, before, expected in ((60, 121, False), (60, 120, True), (59, 120, False), (60, -30, True)):
                with self.subTest(level=level, age=age, before=before):
                    self.flag("ADISCORD_south_preparation_started", age=age)
                    self.set_date(script_date(day_number(DEADLINES[level]) - before))
                    self.assertEqual(self.trigger_matches("ADISCORD_south_ai_border_preparation", "NAM"), expected)
        self.flag("ADISCORD_south_final_started")
        self.assertFalse(self.trigger_matches("ADISCORD_south_ai_border_preparation", "NAM"))

    def test_focus_route_stages_both_current_champions_before_the_calendar_window(self):
        gate = "ADISCORD_south_ai_border_preparation"
        self.open_preparation(age=60)
        self.set_date("2165.1.1")
        for tag in CANDIDATES:
            self.facts[(tag, "is_ai", "yes")] = True
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
DEADLINE_TEXT_RU = ("1 марта 2166 г.", "14 февраля 2166 г.", "30 января 2166 г.", "15 января 2166 г.",
                    "31 декабря 2165 г.", "16 декабря 2165 г.", "1 декабря 2165 г.")
DEADLINE_TEXT_EN = ("1 March 2166", "14 February 2166", "30 January 2166", "15 January 2166",
                    "31 December 2165", "16 December 2165", "1 December 2165")
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
    """Cost of the war, district orders and the hold mission shared by both champions."""

    def test_cost_rises_only_in_the_furnace_cycle_after_the_war_starts(self):
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

    def test_cost_modifier_reads_the_derived_variables_and_refreshes_the_economy(self):
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

    def test_home_front_crisis_answers_clear_the_marker_and_lower_the_cost(self):
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
