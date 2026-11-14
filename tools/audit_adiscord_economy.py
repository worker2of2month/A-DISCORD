"""Reproducible source arithmetic and economic-content inventory.

Run with ``python -B -m tools.audit_adiscord_economy --output PATH``.
The matrix varies every budget independently. It is a controlled source model,
not an emulator of combat, trade, building queues or the native event scheduler.
Reports go to an explicitly supplied path, never to a runtime directory.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
import hashlib
import itertools
import json
from pathlib import Path
import re

from tools.tests.test_adiscord_economy_rebalance import income_fixture
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[1]
P = "ADISCORD_economy_"
MODELS = (
    "fragmented", "decentralized_market", "mixed", "state_coordinated",
    "planned_bureaucratic", "industrializing", "technocratic", "oligarchic_clan", "syndicalist",
)
PROFILES = {
    "small": (8, 4, 3, 0, 0, 0, 30, 1500, 2, 1),
    "medium": (25, 12, 10, 2, 1, 1, 100, 5000, 3, 3),
    "large": (60, 30, 20, 12, 4, 2, 250, 15000, 5, 3),
}
SKIP = {
    "effect_tooltip", "custom_effect_tooltip", "available", "visible", "allowed",
    "limit", "ai_will_do", "ai_strategy", "cancel_trigger", "target_trigger",
    "prerequisite", "mutually_exclusive", "completion_reward_tooltip",
}
TRACKED = {
    "add_equipment_to_stockpile", "add_building_construction", "add_ideas",
    "remove_ideas", "swap_ideas", "add_timed_idea", "add_dynamic_modifier",
    "add_to_variable", "subtract_from_variable", "set_variable",
    "set_temp_variable", "add_to_temp_variable", "subtract_from_temp_variable",
    "multiply_variable", "multiply_temp_variable", "divide_variable", "divide_temp_variable",
    "clamp_variable", "clamp_temp_variable",
    "army_attack_factor", "army_defence_factor", "army_org_factor",
    "research_speed_factor", "industrial_capacity_factory",
    "production_speed_buildings_factor",
}


def scalar(nodes, key, default=None):
    return next((n.value for n in nodes if n.key == key), default)


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def walk(nodes, trail=()):
    for node in nodes:
        if node.key in SKIP:
            continue
        yield node, trail
        if isinstance(node.value, list):
            yield from walk(node.value, (*trail, node.key))


@cache
def model_modifiers(model):
    suffix = {"fragmented": "agrarian", "decentralized_market": "free_market"}.get(model, model)
    name = "ADISCORD_economic_system_" + suffix
    for node, _ in walk(parse_file(ROOT / "common/ideas/_economic.txt")):
        if node.key == name:
            return {n.key: number(n.value) for n in scalar(node.value, "modifier", [])
                    if n.key.startswith(P) and number(n.value) is not None}
    raise ValueError(f"Missing economic model idea: {name}")


def controlled_fixture(profile, model, war=False):
    civ, mil, resources, business, clusters, science, battalions, population, slots, level = PROFILES[profile]
    fixture = income_fixture(civ, mil, resources, business)
    for name in fixture.facts:
        if name.startswith(P + "model_is_"):
            fixture.facts[name] = name == P + "model_is_" + model
        match = re.search(r"_development_(at_least|exact)_(\d)$", name)
        if match:
            fixture.facts[name] = (
                int(match[2]) <= level if match[1] == "at_least" else int(match[2]) == level
            )
    values = fixture.scopes["A"]
    values.update({
        "has_war": war,
        "num_battalions": battalions,
        "ADISCORD_state_development_level": level,
        "ADISCORD_economic_development_level": level,
        "ADISCORD_social_system_development_level": level,
        "ADISCORD_industrial_cluster_count": clusters,
        "ADISCORD_science_center_count": science,
        P + "cached_core_population_k": population,
        P + "cached_research_slots": slots,
        P + "cached_army_organization_factor": 1,
        P + "army_spending_mode": 3,
        P + "research_spending_mode": 3,
        P + "social_spending_mode": 3,
    })
    for key, value in model_modifiers(model).items():
        values["modifier@" + key] = value
    fixture.run(P + "calculate_final_modifier_factors")
    return fixture


def budget(fixture):
    for suffix in ("calculate_income", "calculate_expenses", "calculate_monthly_balance", "calculate_weekly_budget"):
        fixture.run(P + suffix)
    values = fixture.scopes["A"]
    return {
        key: round(values.get(P + key, 0), 6)
        for key in ("weekly_income", "weekly_expenses", "weekly_balance", "army_expenses",
                    "social_expenses", "research_expenses")
    }


def matrix():
    rows = []
    for profile, model, war in itertools.product(PROFILES, MODELS, (False, True)):
        fixture = controlled_fixture(profile, model, war)
        seed = fixture.scopes["A"].copy()
        for tax, army, science, social in itertools.product(range(1, 6), repeat=4):
            fixture.scopes["A"] = seed.copy()
            fixture.calls.clear()
            fixture.scopes["A"].update({
                P + "tax_burden_mode": tax,
                P + "army_spending_mode": army,
                P + "research_spending_mode": science,
                P + "social_spending_mode": social,
            })
            rows.append({
                "profile": profile, "model": model, "war": war,
                "tax": tax, "army": army, "science": science, "social": social,
                **budget(fixture),
            })
        print(f"Calculated {profile}/{model}/{'war' if war else 'peace'}", flush=True)
    return rows


def inventory():
    records = []
    sources = {}
    counts = Counter()
    for folder in ("common/national_focus", "common/decisions", "common/scripted_effects",
                   "common/ideas", "common/dynamic_modifiers", "common/technologies",
                   "common/buildings", "common/on_actions", "common/scripted_guis",
                   "common/scripted_triggers", "common/units", "common/special_projects",
                   "history", "events"):
        for path in sorted((ROOT / folder).rglob("*.txt")):
            data = path.read_bytes()
            relative = path.relative_to(ROOT).as_posix()
            sources[relative] = hashlib.sha256(data).hexdigest()
            nodes = parse_clausewitz(data.decode("utf-8-sig"))
            counts[folder] += 1
            for node, trail in walk(nodes):
                economic_modifier = node.key.startswith(P) and number(node.value) is not None
                if node.key not in TRACKED and "treasury" not in node.key and not economic_modifier:
                    continue
                value = node.value
                if isinstance(value, list):
                    value = {n.key: n.value for n in value if not isinstance(n.value, list)}
                if node.key.endswith("variable"):
                    target = value.get("var", next(iter(value), ""))
                    if not any(term in target for term in (
                        "treasury", "_bonus", "income", "development_progress", "loot", "deposit",
                        "_factor", "_attack", "_defence", "_org", "research", "production",
                        "capacity", "cost", "weekly", "monthly", "spending", "_cash", "_price",
                    )):
                        continue
                records.append({
                    "source": relative, "line": node.line, "owner": "/".join(trail),
                    "operation": node.key, "value": value,
                })
    return {"files": dict(counts), "source_sha256": sources, "records": records}


def parse_file(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def country_inputs():
    """Read dated-start physical inputs, without inventing future conquests."""
    profiles = {}
    for path in sorted((ROOT / "history/countries").glob("*.txt")):
        tag = path.name[:3]
        nodes = parse_file(path)
        ideas = []
        for node in nodes:
            if node.key == "add_ideas":
                ideas.extend([n.value for n in node.value] if isinstance(node.value, list) else [node.value])
        profiles[tag] = {
            "ideas": ideas, "states": [], "source": path.relative_to(ROOT).as_posix(),
            "slots": float(scalar(nodes, "set_research_slots", 2)),
            "civ": 0, "mil": 0, "dockyards": 0, "battalions": 0,
            "divisions": 0, "planes": 0, "ships": 0,
        }
        oob = scalar(nodes, "oob")
        unit_path = ROOT / "history/units" / f"{oob}.txt"
        if oob:
            if not unit_path.is_file():
                raise ValueError(f"Unresolved starting OOB: {tag}/{oob}")
            units = parse_file(unit_path)
            templates = {}
            for node in units:
                if node.key == "division_template":
                    templates[scalar(node.value, "name")] = len(scalar(node.value, "regiments", []))
            for node, _ in walk(units):
                if node.key == "division":
                    profiles[tag]["divisions"] += 1
                    template = scalar(node.value, "division_template")
                    if template not in templates:
                        raise ValueError(f"Unresolved starting template: {tag}/{template}")
                    profiles[tag]["battalions"] += templates[template]
                elif node.key == "ship":
                    profiles[tag]["ships"] += 1
                elif node.key == "air_wings":
                    for wing in node.value:
                        if isinstance(wing.value, list):
                            profiles[tag]["planes"] += float(scalar(wing.value, "amount", 0))
    states = {}
    for path in sorted((ROOT / "history/states").glob("*.txt")):
        state = scalar(parse_file(path), "state", [])
        history = scalar(state, "history", [])
        owner = scalar(history, "owner")
        if owner not in profiles:
            continue
        sid = scalar(state, "id")
        buildings = scalar(history, "buildings", [])
        values = {"controller": scalar(history, "controller", owner), "cores": [n.value for n in history if n.key == "add_core_of"]}
        values["state_population_k"] = float(scalar(state, "manpower", 0)) / 1000
        for node in scalar(state, "resources", []):
            values["resource@" + node.key] = float(node.value)
        for node in buildings:
            if not isinstance(node.value, list) and number(node.value) is not None:
                values["building_level@" + node.key] = float(node.value)
                values["non_damaged@" + node.key] = float(node.value)
        for native, key in (("industrial_complex", "civ"), ("arms_factory", "mil"), ("dockyard", "dockyards")):
            if values["controller"] == owner:
                profiles[owner][key] += values.get("building_level@" + native, 0)
        states[sid] = values
        profiles[owner]["states"].append(sid)
    return profiles, states


def starting_snapshots():
    profiles, states = country_inputs()
    base = income_fixture()
    base.facts.clear()
    for folder in ("common/scripted_effects", "common/scripted_triggers"):
        for path in (ROOT / folder).glob("*.txt"):
            base.definitions.update({n.key: n.value for n in parse_file(path) if isinstance(n.value, list)})
    idea_modifiers = {}
    for path in (ROOT / "common/ideas").glob("*.txt"):
        for node, _ in walk(parse_file(path)):
            if isinstance(node.value, list) and isinstance(scalar(node.value, "modifier"), list):
                idea_modifiers[node.key] = {
                    n.key: number(n.value) for n in scalar(node.value, "modifier")
                    if number(n.value) is not None
                }
    technology_modifiers = {}
    for path in (ROOT / "common/technologies").glob("*.txt"):
        for node in scalar(parse_file(path), "technologies", []):
            if isinstance(node.value, list):
                technology_modifiers[node.key] = {
                    n.key: number(n.value) for n in node.value
                    if n.key.startswith("ADISCORD_economy_") and number(n.value) is not None
                }
    technologies = json.loads(
        (ROOT / "tools/data/adiscord_starting_technology_profiles.json").read_text(encoding="utf-8")
    )["countries"]
    startup = parse_file(ROOT / "common/on_actions/00_ADISCORD_on_actions.txt")
    development_overrides = {}
    for node, _ in walk(startup):
        if node.key not in ("STP", "VAL", "NOD", "event_target:ADISCORD_vorkerland_nation"):
            continue
        if not isinstance(node.value, list):
            continue
        calls = [n.key for n in node.value if n.key.startswith("ADISCORD_set_") and "development_" in n.key]
        if calls:
            development_overrides["WRK" if node.key.startswith("event_target:") else node.key] = calls
    results = []
    for tag, profile in profiles.items():
        if not profile["states"]:
            continue
        f = copy.copy(base)
        f.facts = {"has_dynamic_modifier": False}
        f.calls = []
        f.stubs = {"add_dynamic_modifier", "remove_dynamic_modifier", "force_update_dynamic_modifier"}
        f.scopes = {"A": {"tag": tag}}
        for sid in profile["states"]:
            state = states[sid].copy()
            state["controller"] = "A" if state["controller"] == tag else state["controller"]
            state["cores"] = ["A" if core == tag else core for core in state["cores"]]
            f.scopes[sid] = state
        f.run(P + "set_default_values")
        values = f.scopes["A"]
        values.update({
            "tag": tag, "states": profile["states"],
            "num_battalions": profile["battalions"], "num_divisions": profile["divisions"],
            "num_deployed_planes": profile["planes"], "num_ships": profile["ships"],
            "amount_research_slots": profile["slots"],
            P + "cached_civilian_factories": profile["civ"],
            P + "cached_military_factories": profile["mil"],
            P + "cached_naval_factories": profile["dockyards"],
        })
        for idea in profile["ideas"]:
            values["idea@" + idea] = True
        f.run("ADISCORD_initialize_default_country_development")
        for call in development_overrides.get(tag, []):
            f.run(call)
        for idea_key, active in list(values.items()):
            if active and idea_key.startswith("idea@"):
                for key, value in idea_modifiers.get(idea_key[5:], {}).items():
                    values["modifier@" + key] = values.get("modifier@" + key, 0) + value
        for tech in technologies.get(tag, {}).get("technologies_2160", []):
            for key, value in technology_modifiers.get(tech, {}).items():
                values["modifier@" + key] = values.get("modifier@" + key, 0) + value
        f.run(P + "apply_country_starting_profile")
        f.run(P + "update_model_and_cycle")
        f.run(P + "recalculate_policy_modifiers")
        f.run(P + "recount_economic_buildings")
        f.run(P + "calculate_income")
        f.run(P + "calculate_macro_indicators")
        result = budget(f)
        results.append({"tag": tag, **profile, **result,
                        "treasury": values[P + "treasury"], "debt": values[P + "debt"],
                        "model": values[P + "model"],
                        "economic_development": values["ADISCORD_economic_development_level"],
                        "army_capacity": values.get(P + "nod_division_capacity"),
                        "note": "History, technology and development baseline; full factory utilisation; story transfers and national weekly dispatchers excluded."})
    return results


def focus_route_bounds():
    """Upper bounds, not a simulation: preserve focus prerequisites/exclusions.

    Positive dynamic deltas inside conditional rewards are deliberately included
    together. External prerequisites are assumed complete. Events, bypasses,
    completed prior trees and decision programmes require separate review.
    """
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix
    from tools.builders.build_adiscord_focus_trees import SOURCES, render_source

    metrics = {
        "army_attack_factor", "army_defence_factor", "army_org_factor",
        "research_speed_factor", "industrial_capacity_factory",
        "production_speed_buildings_factor", "ADISCORD_economy_overall_income_factor",
    }
    bindings = {}
    for path in (ROOT / "common/dynamic_modifiers").glob("*.txt"):
        for definition in parse_file(path):
            if isinstance(definition.value, list):
                for node in definition.value:
                    if node.key in metrics and isinstance(node.value, str) and number(node.value) is None:
                        bindings[node.value] = node.key
    effects = {}
    for path in (ROOT / "common/scripted_effects").glob("*.txt"):
        effects.update({n.key: n.value for n in parse_file(path) if isinstance(n.value, list)})
    recalculations = {
        key for key, nodes in effects.items()
        if any(node.key == "set_variable" and scalar(node.value, "var") in bindings
               for node, _ in walk(nodes))
    }

    def deltas(nodes, stack=()):
        result = Counter()
        for node in nodes:
            if node.key in SKIP or re.fullmatch(r"[A-Z]{3}|FROM|PREV|event_target:.*", node.key):
                continue
            if node.key == "add_to_variable":
                variable = scalar(node.value, "var")
                amount = number(scalar(node.value, "value"))
                if variable in bindings and amount is not None and amount > 0:
                    result[bindings[variable]] += amount
            elif (node.key in effects and node.value == "yes" and node.key not in stack
                  and node.key not in recalculations):
                result.update(deltas(effects[node.key], (*stack, node.key)))
            elif isinstance(node.value, list):
                result.update(deltas(node.value, stack))
        return result

    result = []
    for source in sorted(SOURCES):
        path = ROOT / "focus_trees" / source
        for tree in parse_clausewitz(render_source(source)):
            if tree.key != "focus_tree":
                continue
            focuses = [n.value for n in tree.value if n.key == "focus"]
            if not focuses:
                continue
            ids = {scalar(f, "id"): i for i, f in enumerate(focuses)}
            rewards = [deltas(scalar(f, "completion_reward", [])) for f in focuses]
            rows = []
            for i, focus in enumerate(focuses):
                for node in focus:
                    if node.key not in ("prerequisite", "mutually_exclusive"):
                        continue
                    others = [n.value for n in node.value if n.key == "focus"]
                    if node.key == "prerequisite" and all(key in ids for key in others):
                        rows.append(({i: 1, **{ids[key]: -1 for key in others}}, 0))
                    elif node.key == "mutually_exclusive":
                        rows.extend(({i: 1, ids[key]: 1}, 1) for key in others if key in ids)
            days = [7 * float(scalar(f, "cost", 10)) for f in focuses]
            for horizon in (365, 730, None):
                constraints = rows + ([(dict(enumerate(days)), horizon)] if horizon else [])
                matrix = lil_matrix((len(constraints), len(focuses)))
                for r, (coefficients, _) in enumerate(constraints):
                    for c, value in coefficients.items():
                        matrix[r, c] = value
                constraint = LinearConstraint(matrix.tocsr(), -np.inf, [r[1] for r in constraints])
                for metric in sorted(metrics):
                    objective = np.array([r[metric] for r in rewards])
                    if not objective.any():
                        continue
                    solution = milp(-objective + np.array(days) * 1e-8, integrality=np.ones(len(focuses)),
                                    bounds=Bounds(0, 1), constraints=constraint,
                                    options={"time_limit": 15})
                    if not solution.success:
                        raise RuntimeError(f"Unsolved route bound: {path}/{metric}/{horizon}: {solution.message}")
                    selected = [scalar(f, "id") for f, x in zip(focuses, solution.x) if x > .5]
                    result.append({"source": path.relative_to(ROOT).as_posix(), "metric": metric,
                                   "horizon_days": horizon,
                                   "positive_delta_bound": round(float(objective @ np.rint(solution.x)), 6),
                                   "focus_days": sum(d for d, x in zip(days, solution.x) if x > .5),
                                   "selected_focuses": selected})
        print(f"Audited route bounds: {path.parent.relative_to(ROOT)}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--starting-only", action="store_true")
    parser.add_argument("--routes-only", action="store_true", help="Requires scipy; report conservative focus-route bounds")
    args = parser.parse_args()
    report = inventory()
    if args.routes_only:
        report["focus_route_bounds"] = focus_route_bounds()
    elif args.starting_only:
        report["starting_snapshots"] = starting_snapshots()
    elif not args.inventory_only:
        report["budget_matrix"] = matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Economic operations: {len(report['records'])}; matrix rows: {len(report.get('budget_matrix', []))}")


if __name__ == "__main__":
    main()
