"""Targeted structural validation for the Kefreyt rework."""

from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


from tools.lib.paths import source_section
from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
VAL_ON_ACTIONS_FILE = "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"
FRESH_CAMPAIGN_FLAG = "ADISCORD_fresh_campaign_contract_v1"
VAL_FRESH_FEATURE_FLAG = "ADISCORD_val_rework_fresh_campaign_v1"
TIER_MIGRATION_EFFECT = "VAL_migrate_contract_tier_levels"


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def named_blocks(text: str, key: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{", text):
        depth = 0
        start = match.start()
        in_string = False
        escaped = False
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : index + 1])
                    break
    return blocks


def mask_comments(text: str) -> str:
    """Mask Clausewitz comments while preserving source offsets and line breaks."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
            continue
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            in_comment = True
            result.append(" ")
        else:
            result.append(character)
            if character == '"':
                in_string = True
    return "".join(result)


def mask_non_code(text: str) -> str:
    """Mask comments and strings while preserving source offsets and line breaks."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
            continue
        if in_string:
            result.append(" " if character not in "\r\n" else character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            in_comment = True
            result.append(" ")
        elif character == '"':
            in_string = True
            result.append(" ")
        else:
            result.append(character)
    return "".join(result)


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unclosed brace at index {opening}")


@dataclass(frozen=True)
class Block:
    name: str
    start: int
    end: int
    text: str


def named_block_spans(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*\{{")
    blocks: list[Block] = []
    for match in pattern.finditer(masked):
        opening = masked.index("{", match.start(), match.end())
        closing = closing_brace(masked, opening) + 1
        blocks.append(
            Block(
                name=name,
                start=offset + match.start(),
                end=offset + closing,
                text=text[match.start() : closing],
            )
        )
    return blocks


def brace_depth_before(text: str, position: int) -> int:
    return text[:position].count("{") - text[:position].count("}")


def direct_named_blocks(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    return [
        block
        for block in named_block_spans(text, name, offset)
        if brace_depth_before(masked, block.start - offset) == 1
    ]


def scalar_values(text: str, key: str) -> list[str]:
    return re.findall(
        rf"(?m)^\s*{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\s*(?:#.*)?$",
        mask_comments(text),
    )


def assignment_values(text: str, key: str) -> list[str]:
    return re.findall(
        rf"\b{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\b",
        mask_non_code(text),
    )


def assignment_names_at_depth(text: str, depth: int) -> list[str]:
    masked = mask_non_code(text)
    return [
        match.group(1)
        for match in re.finditer(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*=", masked)
        if brace_depth_before(masked, match.start()) == depth
    ]


def assignment_values_at_depth(text: str, key: str, depth: int) -> list[str]:
    masked = mask_non_code(text)
    return [
        match.group(1)
        for match in re.finditer(
            rf"(?<![A-Za-z0-9_]){re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\b",
            masked,
        )
        if brace_depth_before(masked, match.start()) == depth
    ]


def script_children(items: list[Entry], key: str) -> list[Entry]:
    return next((item.value for item in items if item.key == key and isinstance(item.value, list)), [])


def script_fields(items: list[Entry]) -> dict[str, str]:
    return {item.key: item.value for item in items if isinstance(item.value, str)}


def walk_script(items: list[Entry], *, executable: bool = False):
    for item in items:
        if executable and item.key in {"effect_tooltip", "custom_effect_tooltip", "unlock_decision_tooltip", "limit", "trigger"}:
            continue
        yield item
        if isinstance(item.value, list):
            yield from walk_script(item.value, executable=executable)


def validate_supplemental_rewards(focus_text: str, effects_text: str, dynamic_text: str = "",
                                  decisions_text: str = "") -> list[str]:
    """Points may accompany a real effect; display text and marker writes are not one.

    This checks presence, not balance or every conditional outcome. The targeted
    route, payment and modifier tests below retain those separate contracts.
    """
    supplemental = {"army_experience", "add_command_power", "add_political_power"}
    material = {
        "add_stability", "add_war_support", "add_manpower", "add_equipment_to_stockpile",
        "add_offsite_building", "add_building_construction", "build_railway", "add_tech_bonus",
        "add_ideas", "add_timed_idea", "swap_ideas", "add_dynamic_modifier", "add_intel",
        "add_research_slot", "activate_decision", "activate_mission", "give_resource_rights", "recruit_character",
    }
    effects = {e.key: e.value for e in parse_clausewitz(effects_text) if isinstance(e.value, list)}
    refresh = effects.get("VAL_refresh_contract_modifier", [])
    consumed_variables = {value for dynamic in parse_clausewitz(dynamic_text) if isinstance(dynamic.value, list)
                          for value in script_fields(dynamic.value).values()}
    # Include inputs which select a modifier band, following the actual refresh
    # assignments/conditions instead of treating arbitrary country variables as rewards.
    while True:
        previous = consumed_variables.copy()
        for branch in (e for e in walk_script(refresh) if e.key in {"if", "else_if"}):
            writes = [script_fields(e.value) for e in walk_script(branch.value, executable=True)
                      if e.key in {"set_variable", "set_temp_variable", "add_to_variable"}]
            if any(fields.get("var") in consumed_variables for fields in writes):
                for fields in writes:
                    source = fields.get("value", "")
                    if fields.get("var") in consumed_variables and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source):
                        consumed_variables.add(source)
                for check in walk_script(script_children(branch.value, "limit")):
                    if check.key == "check_variable":
                        consumed_variables.add(script_fields(check.value).get("var", ""))
        if previous == consumed_variables:
            break

    refreshed_variables = {script_fields(entry.value).get("var")
                           for entry in walk_script(refresh, executable=True) if entry.key == "set_variable"}

    def nonzero(value, values):
        try:
            return float(value) != 0
        except (ValueError, TypeError):
            return values[value] != 0 if value in values else bool(value)

    def consequential(items, flags, values, changes, seen=frozenset()):
        for entry in walk_script(items, executable=True):
            if entry.key == "set_country_flag":
                flags.add(entry.value)
            elif entry.key == "clr_country_flag":
                flags.discard(entry.value)
            if entry.key in {"set_temp_variable", "set_variable"}:
                fields = script_fields(entry.value)
                changes.pop(fields.get("var"), None)
                try:
                    values[fields.get("var")] = float(fields.get("value", 0))
                except ValueError:
                    values[fields.get("var")] = values.get(fields.get("value"), 0)
            if entry.key == "add_to_variable":
                fields = script_fields(entry.value)
                value = fields.get("value", "0")
                try:
                    amount = float(value)
                except ValueError:
                    amount = values.get(value, 0)
                if fields.get("var") in consumed_variables and amount:
                    variable = fields["var"]
                    changes[variable] = changes.get(variable, 0) + amount
            if entry.key == "VAL_refresh_contract_modifier":
                # A refresh replaces derived outputs. Only input changes and
                # specialisations still present after that replacement count.
                for variable in refreshed_variables:
                    changes.pop(variable, None)
                for branch in (e for e in refresh if e.key == "if"):
                    required_flags = {e.value for e in walk_script(script_children(branch.value, "limit")) if e.key == "has_country_flag"}
                    if required_flags and required_flags <= flags:
                        additions = [script_fields(e.value) for e in walk_script(branch.value, executable=True) if e.key == "add_to_variable"]
                        for addition in additions:
                            variable = addition.get("var")
                            if variable in consumed_variables:
                                changes[variable] = changes.get(variable, 0) + float(addition.get("value", 0))
                continue
            if entry.key in material:
                if isinstance(entry.value, str) and nonzero(entry.value, values):
                    return True
                if isinstance(entry.value, list):
                    fields = script_fields(entry.value)
                    quantities = [fields[key] for key in ("amount", "level", "bonus") if key in fields]
                    if not quantities or any(nonzero(value, values) for value in quantities):
                        return True
            if entry.key in effects and entry.key not in seen and entry.value == "yes":
                if consequential(effects[entry.key], flags, values, changes, seen | {entry.key}):
                    return True
        return False

    decisions: dict[str, list[list[Entry]]] = {}
    for category in parse_clausewitz(decisions_text):
        if isinstance(category.value, list):
            for decision in category.value:
                if isinstance(decision.value, list):
                    decisions.setdefault(decision.key, []).append(decision.value)

    def requires_focus(items, focus_id):
        def required(entry):
            if entry.key == "has_completed_focus":
                return entry.value == focus_id
            if entry.key in {"AND", "hidden_trigger", "custom_trigger_tooltip"}:
                return requires_focus(entry.value, focus_id)
            if entry.key == "OR":
                return bool(entry.value) and all(required(e) for e in entry.value)
            return False
        return any(required(e) for e in items)

    def paid_unlock(reward, focus_id):
        for unlock in (e for e in walk_script(reward) if e.key == "unlock_decision_tooltip"):
            definitions = decisions.get(unlock.value, []) if isinstance(unlock.value, str) else []
            if len(definitions) != 1:
                continue
            decision = definitions[0]
            fields = script_fields(decision)
            try:
                paid = math.isfinite(float(fields.get("cost", 0))) and float(fields.get("cost", 0)) > 0
            except ValueError:
                paid = False
            # custom_cost_text replaces native payment; that separate contract
            # cannot be inferred from a positive cost field alone.
            if not paid or "custom_cost_text" in fields:
                continue
            gate = script_children(decision, "visible") + script_children(decision, "available")
            if not requires_focus(gate, focus_id):
                continue
            changes = {}
            outcome = script_children(decision, "complete_effect") + script_children(decision, "remove_effect")
            if consequential(outcome, set(), {}, changes) or any(changes.values()):
                return True
        return False

    issues = []
    for focus in (e for e in walk_script(parse_clausewitz(focus_text)) if e.key == "focus" and isinstance(e.value, list)):
        reward = script_children(focus.value, "completion_reward")
        changes = {}
        if (any(e.key in supplemental for e in walk_script(reward, executable=True))
                and not consequential(reward, set(), {}, changes) and not any(changes.values())
                and not paid_unlock(reward, script_fields(focus.value).get("id"))):
            issues.append(f"{script_fields(focus.value).get('id', 'unknown focus')} gives only supplemental points or unconsumed markers")
    return issues


def validate_val_preview_ideas(ideas_text: str, sources: dict[str, str], dynamic_text: str,
                             effects_text: str) -> tuple[set[str], list[str]]:
    """Prove display-only ideas from their real consumers, not an ID suffix.

    Aggregate previews follow focus flags or numeric input additions through
    refresh into the native dynamic-modifier variable mapping.
    Industry previews instead compare the installed tier vectors at every tier.
    Read-only has_idea probes are permitted; executable references are not.
    """
    issues: list[str] = []
    ideas_root = script_children(parse_clausewitz(ideas_text), "ideas")
    declarations = [e for group in ideas_root if isinstance(group.value, list)
                    for e in group.value if isinstance(e.value, list)]
    ideas = {e.key: e.value for e in declarations}
    candidates = {key for key, body in ideas.items() if "name" in script_fields(body)}
    names = {key: script_fields(ideas[key])["name"] for key in candidates}
    native_maps = {e.key: {v: k for k, v in script_fields(e.value).items()}
                   for e in parse_clausewitz(dynamic_text) if isinstance(e.value, list)}

    def modifiers(idea):
        try:
            return {e.key: float(e.value) for e in script_children(ideas[idea], "modifier")}
        except (KeyError, ValueError, TypeError):
            issues.append(f"preview {idea} must use a declared numeric modifier vector")
            return {}

    vectors = {key: modifiers(key) for key in ideas}
    for idea in sorted(candidates):
        if sum(e.key == idea for e in declarations) != 1:
            issues.append(f"preview {idea} must be declared exactly once")
        allowed = script_children(ideas[idea], "allowed")
        if len(allowed) != 1 or script_fields(allowed) != {"always": "no"}:
            issues.append(f"preview {idea} must have allowed = {{ always = no }}")
        if names[idea] not in native_maps and names[idea] not in ideas:
            issues.append(f"preview {idea} has unknown native name {names[idea]}")

    refresh = script_children(parse_clausewitz(effects_text), "VAL_refresh_contract_modifier")
    flag_deltas: dict[str, dict[str, float]] = {}
    for branch in (e for e in refresh if e.key == "if"):
        flags = [e.value for e in walk_script(script_children(branch.value, "limit")) if e.key == "has_country_flag"]
        if len(flags) == 1:
            delta = {}
            for effect in walk_script(branch.value, executable=True):
                if effect.key == "add_to_variable":
                    fields = script_fields(effect.value)
                    try:
                        delta[fields["var"]] = delta.get(fields["var"], 0) + float(fields["value"])
                    except (KeyError, ValueError):
                        continue
            if delta:
                flag_deltas[flags[0]] = delta

    def resets_output(items, variable, already=False):
        """A recomputed output needs a numeric baseline on every branch."""
        index = 0
        while index < len(items):
            entry = items[index]
            if entry.key == "set_variable":
                fields = script_fields(entry.value)
                if fields.get("var") == variable:
                    try:
                        already = math.isfinite(float(fields["value"]))
                    except (KeyError, ValueError):
                        already = False
            elif entry.key == "if":
                chain = [entry]
                while index + 1 < len(items) and items[index + 1].key in {"else_if", "else"}:
                    index += 1
                    chain.append(items[index])
                outcomes = [resets_output(e.value, variable, already) for e in chain]
                if chain[-1].key != "else":
                    outcomes.append(already)
                already = all(outcomes)
            index += 1
        return already

    # Recognise only same-country, untransformed persistent input copies. A
    # conditional scope or unsupported arithmetic cannot prove a preview delta.
    numeric_copies: dict[str, list[str]] = {}
    for index, branch in enumerate(refresh):
        if branch.key != "if":
            continue
        guard = script_children(branch.value, "limit")
        if len(guard) != 1 or guard[0].key != "has_variable" or not isinstance(guard[0].value, str):
            continue
        source = guard[0].value
        payload = [e for e in branch.value if e.key != "limit"]
        if not payload or any(e.key != "add_to_variable" or script_fields(e.value).get("value") != source for e in payload):
            continue
        input_writes = [e for e in walk_script(refresh, executable=True)
                        if e.key in {"set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable",
                                     "multiply_variable", "divide_variable", "clamp_variable", "clear_variable"}
                        and (e.value == source if isinstance(e.value, str) else script_fields(e.value).get("var") == source)]
        if input_writes:
            continue
        for effect in payload:
            fields = script_fields(effect.value)
            target = fields.get("var")
            if fields.get("value") != source or not target or not resets_output(refresh[:index], target):
                continue
            overwritten = any(e.key in {"set_variable", "set_temp_variable", "subtract_from_variable", "multiply_variable",
                                        "divide_variable", "clamp_variable", "clear_variable"}
                              and (e.value == target if isinstance(e.value, str) else script_fields(e.value).get("var") == target)
                              for e in walk_script(refresh[index + 1:], executable=True))
            if not overwritten:
                numeric_copies.setdefault(source, []).append(target)

    def updates_native(native):
        for index, branch in enumerate(refresh[:-1]):
            if branch.key != "if" or refresh[index + 1].key != "else":
                continue
            guard = script_children(branch.value, "limit")
            if len(guard) != 1 or guard[0].key != "has_dynamic_modifier":
                continue
            modifier = guard[0].value if isinstance(guard[0].value, str) else script_fields(guard[0].value).get("modifier")
            if (modifier == native and script_fields(branch.value).get("force_update_dynamic_modifier") == "yes"
                    and script_fields(script_children(refresh[index + 1].value, "add_dynamic_modifier")).get("modifier") == native):
                return True
        return False

    def numeric_reward_delta(items, native):
        def country_sequence(children):
            for entry in children:
                if entry.key == "hidden_effect":
                    yield from country_sequence(entry.value)
                elif entry.key not in {"effect_tooltip", "custom_effect_tooltip", "unlock_decision_tooltip"}:
                    yield entry

        pending, applied, invalid = {}, {}, set()
        for entry in country_sequence(items):
            if entry.key == "add_to_variable":
                fields = script_fields(entry.value)
                variable = fields.get("var")
                if variable in numeric_copies:
                    try:
                        amount = float(fields["value"])
                        if not math.isfinite(amount):
                            raise ValueError("non-finite delta")
                        pending[variable] = pending.get(variable, 0) + amount
                    except (KeyError, ValueError):
                        invalid.add(variable)
            elif entry.key in {"set_variable", "set_temp_variable", "subtract_from_variable", "multiply_variable",
                               "divide_variable", "clamp_variable", "clear_variable"}:
                invalid.add(entry.value if isinstance(entry.value, str) else script_fields(entry.value).get("var"))
            elif entry.key == "VAL_refresh_contract_modifier" and entry.value == "yes":
                applied = pending.copy()
        expected = {}
        if updates_native(native):
            for source, amount in applied.items():
                if source in invalid or pending.get(source) != amount:
                    continue
                for target in numeric_copies[source]:
                    modifier = native_maps[native].get(target)
                    if modifier:
                        expected[modifier] = expected.get(modifier, 0) + amount
        return expected

    referenced, checked = set(), set()

    # Native swap previews need country ideas on both sides. These mirrors carry
    # full tier vectors; the engine computes the difference between them.
    mirrors = {
        key for key in candidates
        if re.fullmatch(r"VAL_(administration|army)_[123]_preview", key)
    }
    country_ids = {e.key for e in script_children(ideas_root, "country")}
    for idea in mirrors:
        native = "VAL_contract_" + idea.removeprefix("VAL_").removesuffix("_preview")
        if idea not in country_ids or names[idea] != native or vectors[idea] != vectors.get(native):
            issues.append(f"preview {idea} must mirror the full native country tier {native}")
        checked.add(idea)

    def compare(idea, expected, context):
        keys = vectors[idea].keys() | expected.keys()
        if any(abs(vectors[idea].get(k, 0) - expected.get(k, 0)) > 1e-8 for k in keys):
            issues.append(f"preview {idea} does not match actual {context} delta")
        checked.add(idea)

    def tier_previews(items, level, inside=False):
        def condition(entry):
            if entry.key == "NOT": return not any(condition(e) for e in entry.value)
            if entry.key == "OR": return any(condition(e) for e in entry.value)
            if entry.key == "AND": return all(condition(e) for e in entry.value)
            if entry.key == "has_variable":
                if entry.value != "VAL_contract_industry_level":
                    raise ValueError(f"industry preview checks the wrong variable {entry.value}")
                return level is not None
            if entry.key == "check_variable":
                fields = script_fields(entry.value)
                if fields.get("var") != "VAL_contract_industry_level":
                    raise ValueError(f"industry preview checks the wrong variable {fields.get('var')}")
                actual, expected = level or 0, float(fields["value"])
                return {"less_than": actual < expected, "greater_than_or_equals": actual >= expected,
                        "equals": actual == expected}[fields.get("compare", "greater_than_or_equals")]
            raise ValueError(f"unsupported industry preview condition {entry.key}")
        found, matched = [], False
        for entry in items:
            if entry.key in {"if", "else_if", "else"}:
                take = all(condition(e) for e in script_children(entry.value, "limit"))
                if entry.key == "if": matched = False
                if take and not matched:
                    found += tier_previews([e for e in entry.value if e.key != "limit"], level, inside)
                    matched = True
            elif entry.key == "swap_ideas" and inside:
                pair = script_fields(entry.value)
                after = pair.get("add_idea")
                native = names.get(after, "")
                # Aggregate deltas are already checked independently of tier changes.
                aggregate = (after in checked and native in native_maps
                             and not native.startswith("VAL_contract_industry_"))
                if not aggregate:
                    found.append(pair)
            elif isinstance(entry.value, list) and entry.key not in {"hidden_effect", "limit"}:
                found += tier_previews(entry.value, level, inside or entry.key == "effect_tooltip")
        return found

    def inspect(items, path, inside=False, reward=None, hidden=False):
        for entry in items:
            if entry.key == "focus" and isinstance(entry.value, list):
                inspect(entry.value, path, inside, script_children(entry.value, "completion_reward"), hidden)
                continue
            if isinstance(entry.value, str) and entry.value in candidates:
                referenced.add(entry.value)
                if entry.key != "has_idea" and not inside:
                    issues.append(f"preview {entry.value} has executable/non-tooltip reference in {path}:{entry.line}")
                elif entry.key != "has_idea" and hidden:
                    issues.append(f"preview {entry.value} is hidden from the player in {path}:{entry.line}")
            if entry.key == "swap_ideas" and inside:
                pair = script_fields(entry.value)
                before, after = pair.get("remove_idea"), pair.get("add_idea")
                if after in candidates:
                    if after in mirrors:
                        if before not in mirrors or before.rsplit("_", 2)[0] != after.rsplit("_", 2)[0]:
                            issues.append(f"preview {after} needs a mirror of the same tier family")
                    elif before not in candidates or names.get(before) != names[after] or vectors.get(before):
                        issues.append(f"preview {after} needs an empty baseline with the same native name")
                    else:
                        checked.add(before)
                    native = names[after]
                    if native in native_maps and reward is not None:
                        executable = list(walk_script(reward, executable=True))
                        flags = {e.value for e in executable if e.key == "set_country_flag"}
                        expected = {}
                        for flag in flags:
                            for variable, value in flag_deltas.get(flag, {}).items():
                                modifier = native_maps[native].get(variable)
                                if modifier:
                                    expected[modifier] = expected.get(modifier, 0) + value
                        for modifier, value in numeric_reward_delta(reward, native).items():
                            expected[modifier] = expected.get(modifier, 0) + value
                        if not expected or not any(e.key == "VAL_refresh_contract_modifier" and e.value == "yes" for e in executable):
                            issues.append(f"preview {after} has no matching executed flag/numeric-input refresh reward")
                        compare(after, expected, native)
                    elif after not in mirrors and not native.startswith("VAL_contract_industry_"):
                        issues.append(f"preview {after} has no proven native reward consumer")
            if isinstance(entry.value, list):
                inspect(entry.value, path, inside or entry.key == "effect_tooltip", reward,
                        hidden or entry.key == "hidden_effect")

    for path, text in sources.items():
        entries = parse_clausewitz(text)
        inspect(entries, path)
        for focus in (e for e in walk_script(entries) if e.key == "focus" and isinstance(e.value, list)):
            reward = script_children(focus.value, "completion_reward")
            tier_ids = {e.value for e in walk_script(reward) if e.key == "add_idea" and
                        e.value in candidates and names[e.value].startswith("VAL_contract_industry_")}
            if not tier_ids:
                continue
            target = max(int(names[idea].rsplit("_", 1)[1]) for idea in tier_ids)
            if not any(e.key == f"VAL_apply_contract_industry_{target}" for e in walk_script(reward, executable=True)):
                issues.append(f"industry preview has no actual tier-{target} grant")
            for level in (None, 0, 1, 2, 3):
                try:
                    pairs = tier_previews(reward, level)
                except (ValueError, KeyError) as error:
                    issues.append(str(error))
                    break
                expected_count = int((level or 0) < target)
                if len(pairs) != expected_count:
                    issues.append(f"industry tier-{target} preview is wrong at current tier {level}")
                for pair in pairs:
                    idea = pair.get("add_idea")
                    if idea not in tier_ids:
                        issues.append("industry preview references an unexpected delta")
                        continue
                    full = vectors.get(names[idea], {})
                    previous = vectors.get(f"VAL_contract_industry_{level}", {})
                    compare(idea, {k: full.get(k, 0) - previous.get(k, 0) for k in full.keys() | previous.keys()}, f"industry tier {level}->{target}")
    for idea in sorted(candidates - (referenced & checked)):
        issues.append(f"preview {idea} has no validated tooltip-only consumer")
    return candidates if not issues else set(), issues


def main() -> int:
    issues: list[str] = []
    focus_text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
    focuses = named_blocks(focus_text, "focus")
    if "relative_position_id" in focus_text:
        issues.append("focus layout still uses cascading relative coordinates")
    ids = {
        match.group(1)
        for block in focuses
        if (match := re.search(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)", block))
    }
    required = {
        "VAL_Operational_Directorate",
        "VAL_Ministry_Of_Contract_Memory",
        "VAL_Quarterly_Contract_Norm",
        "VAL_Arsenal_Reserve",
        "VAL_Contract_General_Staff",
        "VAL_State_Above_Captains",
        "VAL_Westerholm_Concessions",
        "VAL_Vorkerland_Contracts_Burn",
        "VAL_State_Contract",
        "VAL_Industrial_Mobilization_Plan",
        "VAL_Army_Of_The_Ledger",
        "VAL_Wireless_Contract_Bureau",
        "VAL_Two_Concurrent_Narratives",
        "VAL_Logistics_Command",
    }
    for missing in sorted(required - ids):
        issues.append(f"missing focus {missing}")
    machine_shops = next(
        (
            block
            for block in focuses
            if re.search(r"(?m)^\s*id\s*=\s*VAL_Mobilize_Machine_Shops\s*$", block)
        ),
        "",
    )
    machine_shop_reward = named_blocks(machine_shops, "completion_reward")
    if len(machine_shop_reward) != 1:
        issues.append("VAL machine-shop focus must define exactly one completion reward")
    else:
        capital_rewards = named_blocks(machine_shop_reward[0], "capital_scope")
        expected_infrastructure = (
            "add_building_construction = { type = infrastructure level = 1 instant_build = yes }"
        )
        if len(capital_rewards) != 1 or expected_infrastructure not in capital_rewards[0]:
            issues.append("VAL machine-shop infrastructure reward is not capital-state scoped")
    if len(focuses) < 70:
        issues.append(f"focus tree is still too small ({len(focuses)} focuses)")
    for block in focuses:
        focus_id = re.search(r"(?m)^\s*id\s*=\s*(\S+)", block)
        cost = re.search(r"(?m)^\s*cost\s*=\s*(\d+)", block)
        if not cost:
            issues.append(f"{focus_id.group(1) if focus_id else 'unknown focus'} has no cost")
        elif int(cost.group(1)) > 5:
            issues.append(f"{focus_id.group(1) if focus_id else 'unknown focus'} exceeds 35 days")
    issues.extend(validate_supplemental_rewards(
        focus_text, read("common/scripted_effects/ADISCORD_VAL_effects.txt"),
        read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"),
        read("common/decisions/ADISCORD_VAL_decisions.txt")))

    focus_blocks = {
        match.group(1): block
        for block in focuses
        if (match := re.search(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)", block))
    }
    exclusive_pairs: set[frozenset[str]] = set()
    for focus_id, block in focus_blocks.items():
        exclusive = named_blocks(block, "mutually_exclusive")
        if not exclusive:
            continue
        for rival in re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", exclusive[0]):
            exclusive_pairs.add(frozenset((focus_id, rival)))
    for focus_id, block in focus_blocks.items():
        prerequisites = named_blocks(block, "prerequisite")
        prerequisite_groups = [
            set(re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", prerequisite))
            for prerequisite in prerequisites
        ]
        for pair in exclusive_pairs:
            if len(pair) != 2:
                continue
            if all(any(member in group for group in prerequisite_groups) for member in pair):
                if not any(pair.issubset(group) for group in prerequisite_groups):
                    issues.append(
                        f"{focus_id} requires mutually exclusive focuses in separate prerequisite blocks"
                    )

    prerequisite_groups = {
        focus_id: [
            re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", prerequisite)
            for prerequisite in named_blocks(block, "prerequisite")
        ]
        for focus_id, block in focus_blocks.items()
    }
    viable_cache: dict[str, list[frozenset[str]]] = {}
    visiting: set[str] = set()

    def viable_paths(focus_id: str) -> list[frozenset[str]]:
        if focus_id in viable_cache:
            return viable_cache[focus_id]
        if focus_id in visiting:
            return []
        visiting.add(focus_id)
        candidates = [frozenset((focus_id,))]
        for prerequisite_group in prerequisite_groups[focus_id]:
            alternatives = [
                path
                for prerequisite_id in prerequisite_group
                if prerequisite_id in focus_blocks
                for path in viable_paths(prerequisite_id)
            ]
            candidates = [
                current | alternative
                for current in candidates
                for alternative in alternatives
                if not any(pair <= current | alternative for pair in exclusive_pairs)
            ]
            minimal: list[frozenset[str]] = []
            for candidate in sorted(set(candidates), key=len):
                if not any(existing <= candidate for existing in minimal):
                    minimal.append(candidate)
            candidates = minimal
        visiting.remove(focus_id)
        viable_cache[focus_id] = candidates
        return candidates

    for focus_id in focus_blocks:
        if not viable_paths(focus_id):
            issues.append(f"{focus_id} has no completable prerequisite path")

    final_join = focus_blocks.get("VAL_Contracts_Outlive_Kings", "")
    for terminal in (
        "VAL_State_Contract",
        "VAL_Industrial_Mobilization_Plan",
        "VAL_Army_Of_The_Ledger",
    ):
        if not re.search(
            rf"prerequisite\s*=\s*\{{\s*focus\s*=\s*{terminal}\s*\}}",
            final_join,
        ):
            issues.append(f"final branch join is missing {terminal}")
    coordinates: dict[str, tuple[int, int, str | None]] = {}
    for block in focuses:
        focus_id = re.search(r"(?m)^\s*id\s*=\s*(\S+)", block)
        x = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)", block)
        y = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)", block)
        relative = re.search(r"(?m)^\s*relative_position_id\s*=\s*(\S+)", block)
        if focus_id and x and y:
            coordinates[focus_id.group(1)] = (
                int(x.group(1)),
                int(y.group(1)),
                relative.group(1) if relative else None,
            )

    resolved: dict[str, tuple[int, int]] = {}

    def resolve(focus_id: str) -> tuple[int, int]:
        if focus_id in resolved:
            return resolved[focus_id]
        x, y, relative = coordinates[focus_id]
        if relative:
            parent_x, parent_y = resolve(relative)
            x, y = x + parent_x, y + parent_y
        resolved[focus_id] = (x, y)
        return x, y

    occupied: dict[tuple[int, int], list[str]] = {}
    for focus_id in coordinates:
        occupied.setdefault(resolve(focus_id), []).append(focus_id)
    for position, focus_ids in occupied.items():
        if len(focus_ids) > 1:
            issues.append(f"focus coordinate collision at {position}: {', '.join(focus_ids)}")
    if resolved:
        xs = [position[0] for position in resolved.values()]
        if max(xs) - min(xs) < 24:
            issues.append("focus tree is not wide enough to separate its main branches")
        final_position = resolved.get("VAL_Contracts_Outlive_Kings")
        terminal_positions = [
            resolved.get(terminal)
            for terminal in (
                "VAL_State_Contract",
                "VAL_Industrial_Mobilization_Plan",
                "VAL_Army_Of_The_Ledger",
            )
        ]
        if final_position and all(terminal_positions):
            if final_position[1] <= max(position[1] for position in terminal_positions if position):
                issues.append("final branch join is drawn above a required branch ending")
            terminal_rows = {position[1] for position in terminal_positions if position}
            if len(terminal_rows) != 1:
                issues.append("political, industrial and army branch endings are not aligned")
        strategy_positions = [
            resolved.get(strategy)
            for strategy in (
                "VAL_Offer_The_Mountain_Contract",
                "VAL_Secure_The_Resource_Corridor",
                "VAL_Negotiate_The_Deferred_Invoice",
                "VAL_Let_Nodrul_Bleed",
            )
        ]
        if all(strategy_positions):
            strategy_rows = {position[1] for position in strategy_positions if position}
            if len(strategy_rows) != 1:
                issues.append("the four final crisis alternatives are not aligned")

    for focus_id in ("VAL_Westerholm_Concessions", "VAL_Vorkerland_Contracts_Burn"):
        block = next((block for block in focuses if f"id = {focus_id}" in block), "")
        if "allow_branch" not in block:
            issues.append(f"{focus_id} is not world-reactive")

    shared_effects = read("common/scripted_effects/ADISCORD_shared_action_effects.txt")
    shared_triggers = read("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")
    if "VAL_" in shared_effects or "VAL_" in shared_triggers:
        issues.append("shared action API contains Kefreyt-specific content")
    for token in (
        "ADISCORD_economy_spend_50",
        "ADISCORD_economy_spend_100",
        "ADISCORD_economy_spend_250",
        "ADISCORD_economy_spend_500",
        "ADISCORD_economy_receive_15",
        "ADISCORD_economy_receive_50",
        "ADISCORD_campaign_slot_consume",
        "ADISCORD_campaign_slot_release",
    ):
        if token not in shared_effects:
            issues.append(f"shared action API is missing {token}")

    foreign_operations = source_section(read(
        "common/scripted_effects/ADISCORD_VAL_effects.txt"
    ), 'foreign_operation_effects')
    if re.search(
        r"\bVAL_recalculate_stp_campaign_readiness\s*=\s*yes\b",
        mask_comments(foreign_operations),
    ):
        issues.append(
            "independent foreign operations still call the removed STP campaign readiness effect"
        )
    for target in ("cin", "osf", "aph"):
        effect_id = f"VAL_resolve_{target}_operation"
        resolvers = named_blocks(foreign_operations, effect_id)
        if len(resolvers) != 1:
            issues.append(f"foreign operation resolver must be declared once: {effect_id}")
        elif "VAL_clear_foreign_operation = yes" not in resolvers[0]:
            issues.append(f"{effect_id} does not release the shared foreign-operation slot")

    decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
    for token in (
        "days_mission_timeout = 90",
        "VAL_reserve_export_rifles = yes",
        "VAL_refund_export_rifles = yes",
        "limit = { has_country_flag = VAL_export_rifles_reserved }",
        "VAL_resolve_quarterly_contract_norm = yes",
        "ADISCORD_has_campaign_slot = yes",
    ):
        if token not in decisions:
            issues.append(f"decision system is missing {token}")
    if re.search(r"ADISCORD_economy_treasury\s+value\s*=", decisions):
        issues.append("Kefreyt decisions bypass the shared treasury API")
    for debug_decision in (
        "VAL_debug_initialize_systems",
        "VAL_debug_unlock_operations_map",
        "VAL_debug_disrupt_vorkerland_contracts",
        "VAL_debug_reputation_maximum",
        "VAL_debug_reputation_minimum",
        "VAL_debug_grant_contract_reserves",
        "VAL_debug_reset_rework_state",
    ):
        if not named_blocks(decisions, debug_decision):
            issues.append(f"missing debug decision {debug_decision}")
    categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
    debug_category = named_blocks(categories, "VAL_rework_debug")
    if not debug_category or "is_debug = yes" not in debug_category[0]:
        issues.append("Kefreyt debug category is not gated by debug mode")

    legacy_decisions = read("common/decisions/ADISCORD_VAL_contract_decisions.txt")
    service_decisions = {
        "VAL_resource_corridor_control_30",
        "VAL_STP_adviser_factory_obligation",
        "VAL_STP_arms_debt_day_30",
        "VAL_STP_arms_debt_day_90",
        "VAL_STP_arms_debt_day_150",
        "VAL_northern_campaign_timeout_210",
        "STP_VAL_war_countdown_120",
        "STP_VAL_war_countdown_180",
        "STP_VAL_war_countdown_300",
        "STP_VAL_war_countdown_450",
        "STP_VAL_war_countdown_breached",
    }
    legacy_children = set(
        re.findall(r"(?m)^\t([A-Z][A-Za-z0-9_]+)\s*=\s*\{", legacy_decisions)
    )
    for obsolete in sorted(legacy_children - service_decisions):
        issues.append(f"obsolete player-facing legacy decision remains: {obsolete}")
    compatibility_mission = named_blocks(legacy_decisions, "VAL_resource_corridor_control_30")
    if compatibility_mission and "visible = { always = no }" not in " ".join(
        compatibility_mission[0].split()
    ):
        issues.append("legacy resource-corridor mission is not hidden")
    for obsolete_path in (
        "common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt",
        "interface/ADISCORD_STP_VAL_crisis.gui",
    ):
        if (ROOT / obsolete_path).exists():
            issues.append(f"obsolete legacy panel still exists: {obsolete_path}")

    operational_focus = focus_blocks.get("VAL_Operational_Directorate", "")
    if "set_country_flag = VAL_operations_map_unlocked" not in operational_focus:
        issues.append("Operational Directorate does not unlock the operations map")
    map_category = named_blocks(categories, "VAL_military_operations")
    if not map_category:
        issues.append("operations-map decision category is missing")
    else:
        for token in (
            "has_country_flag = VAL_operations_map_unlocked",
            "visible_when_empty = yes",
            "scripted_gui = ADISCORD_VAL_operations_panel",
        ):
            if token not in map_category[0]:
                issues.append(f"operations-map category is missing {token}")
    for decision_id in (
        "VAL_ops_finance_cin_contacts",
        "VAL_ops_finance_osf_contacts",
    ):
        block = named_blocks(decisions, decision_id)
        if not block or "has_country_flag = VAL_northern_operations_unlocked" not in block[0]:
            issues.append(f"{decision_id} is not gated by its world-reactive focus")

    effects = source_section(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), 'rework_effects')
    on_actions = read_country_on_actions(VAL_ON_ACTIONS_FILE, 'kefreyt')
    startup_blocks = named_blocks(on_actions, "on_startup")
    if len(startup_blocks) != 1:
        issues.append(f"VAL rework must define exactly one on_startup, found {len(startup_blocks)}")
    else:
        startup = mask_comments(startup_blocks[0])
        startup_branches = [branch for branch in named_blocks(startup, "if") if "VAL_initialize_rework = yes" in branch]
        if len(startup_branches) != 1:
            issues.append(
                "VAL rework startup must contain one fresh-campaign initialization branch"
            )
        else:
            startup_branch = startup_branches[0]
            limits = named_blocks(startup_branch, "limit")
            if len(limits) != 1:
                issues.append("VAL rework startup branch must contain exactly one limit")
            else:
                limit = limits[0]
                fresh_guard = f"has_global_flag = {FRESH_CAMPAIGN_FLAG}"
                feature_guard = (
                    f"NOT = {{ has_global_flag = {VAL_FRESH_FEATURE_FLAG} }}"
                )
                for token in (fresh_guard, feature_guard, "VAL = { exists = yes }"):
                    if limit.count(token) != 1:
                        issues.append(f"VAL rework startup limit must contain {token} exactly once")

            feature_set = f"set_global_flag = {VAL_FRESH_FEATURE_FLAG}"
            initialize_call = "VAL_initialize_rework = yes"
            for token in (feature_set, initialize_call):
                if startup_branch.count(token) != 1:
                    issues.append(f"VAL rework startup must contain {token} exactly once")
            if not re.search(
                r"VAL\s*=\s*\{\s*VAL_initialize_rework\s*=\s*yes\s*\}",
                startup_branch,
            ):
                issues.append("VAL rework initializer must execute in VAL scope")

            ordered_tokens = (
                f"has_global_flag = {FRESH_CAMPAIGN_FLAG}",
                f"NOT = {{ has_global_flag = {VAL_FRESH_FEATURE_FLAG} }}",
                feature_set,
                initialize_call,
            )
            if all(startup_branch.count(token) == 1 for token in ordered_tokens):
                positions = tuple(startup_branch.index(token) for token in ordered_tokens)
                if positions != tuple(sorted(positions)):
                    issues.append(
                        "VAL rework startup must check fresh provenance and one-shot guard "
                        "before setting its feature flag and initializing VAL"
                    )

    initialize_call = "VAL_initialize_rework = yes"
    if mask_comments(on_actions).count(initialize_call) != 1:
        issues.append("VAL rework initializer must have exactly one guarded runtime caller")
    for token in (
        "set_temp_variable = { var = STP_cw_rifle_cost value = 4000 }",
        "STP_cw_pay_rifles = yes",
        "limit = { has_country_flag = STP_cw_rifles_paid }",
        "VAL_contract_reputation_level",
        "VAL_vorkerland_contract_disruptions",
        "give_resource_rights = { receiver = VAL state = 38 }",
        "remove_resource_rights = 202",
    ):
        if token not in effects:
            issues.append(f"rework effects are missing {token}")
    initialize = named_blocks(effects, "VAL_initialize_rework")
    if not initialize or "set_country_flag = VAL_operations_map_unlocked" not in initialize[0]:
        issues.append("rework initialization does not migrate the operations-map unlock")

    tier_families = {
        "administration": tuple(f"VAL_contract_administration_{tier}" for tier in range(1, 4)),
        "industry": tuple(f"VAL_contract_industry_{tier}" for tier in range(1, 4)),
        "army": tuple(f"VAL_contract_army_{tier}" for tier in range(1, 4)),
        "reputation": tuple(f"VAL_contract_reputation_{tier}" for tier in range(4)),
    }
    level_variables = {
        "administration": "VAL_contract_administration_level",
        "industry": "VAL_contract_industry_level",
        "army": "VAL_contract_army_level",
    }
    authoritative_level_variables = {
        *level_variables.values(),
        "VAL_contract_reputation_level",
    }
    used_contract_level_variables = set(
        re.findall(
            r"\bvar\s*=\s*(VAL_contract_[A-Za-z0-9_]*level)\b",
            mask_comments(effects),
        )
    )
    if used_contract_level_variables != authoritative_level_variables:
        issues.append(
            "contract tier effects do not use exactly the authoritative level variables: "
            + ", ".join(sorted(used_contract_level_variables))
        )
    for family, expected_variable in {
        **level_variables,
        "reputation": "VAL_contract_reputation_level",
    }.items():
        family_variables = set(
            re.findall(
                rf"\bvar\s*=\s*(VAL_contract_{family}_[A-Za-z0-9_]+)\b",
                mask_comments(effects),
            )
        )
        if family_variables != {expected_variable}:
            issues.append(
                f"{family} contract state must use only {expected_variable}: "
                + ", ".join(sorted(family_variables))
            )

    def validate_hidden_renderer(
        owner: str,
        container: str,
        family: str,
        target: str,
    ) -> str | None:
        hidden_blocks = direct_named_blocks(container, "hidden_effect")
        if len(hidden_blocks) != 1:
            issues.append(f"{owner} needs exactly one direct hidden_effect renderer")
            return None
        hidden = hidden_blocks[0].text
        expected_ideas = set(tier_families[family])
        removals = assignment_values_at_depth(hidden, "remove_ideas", 1)
        additions = assignment_values_at_depth(hidden, "add_ideas", 1)
        if (
            len(removals) != len(expected_ideas)
            or set(removals) != expected_ideas
            or assignment_values_at_depth(hidden, "remove_idea", 1)
        ):
            issues.append(
                f"{owner} does not directly remove every {family} tier exactly once"
            )
        if additions != [target] or assignment_values_at_depth(hidden, "add_idea", 1):
            issues.append(f"{owner} does not directly add only target tier {target}")
        idea_commands = {"add_idea", "add_ideas", "remove_idea", "remove_ideas", "swap_ideas"}
        direct_idea_commands = [
            name for name in assignment_names_at_depth(hidden, 1) if name in idea_commands
        ]
        expected_direct_commands = ["remove_ideas"] * len(expected_ideas) + ["add_ideas"]
        if direct_idea_commands != expected_direct_commands:
            issues.append(f"{owner} has an invalid direct idea-render command sequence")
        masked_hidden = mask_non_code(hidden)
        nested_idea_commands = [
            match.group(1)
            for match in re.finditer(
                r"(?<![A-Za-z0-9_])(add_idea|add_ideas|remove_idea|remove_ideas|swap_ideas)\s*=",
                masked_hidden,
            )
            if brace_depth_before(masked_hidden, match.start()) > 1
        ]
        if nested_idea_commands:
            issues.append(f"{owner} nests idea rendering below hidden_effect direct depth")
        removal_positions = [
            match.start()
            for match in re.finditer(r"(?m)^\s*remove_ideas\s*=", mask_comments(hidden))
            if brace_depth_before(masked_hidden, match.start()) == 1
        ]
        addition_positions = [
            match.start()
            for match in re.finditer(r"(?m)^\s*add_ideas\s*=", mask_comments(hidden))
            if brace_depth_before(masked_hidden, match.start()) == 1
        ]
        if removal_positions and addition_positions and max(removal_positions) > min(addition_positions):
            issues.append(f"{owner} adds {target} before completing its remove-all render")
        return hidden

    for family in ("administration", "industry", "army"):
        variable = level_variables[family]
        for tier, target in enumerate(tier_families[family], start=1):
            effect_id = f"VAL_apply_contract_{family}_{tier}"
            effect_blocks = named_block_spans(effects, effect_id)
            if len(effect_blocks) != 1:
                issues.append(f"expected exactly one tier effect {effect_id}")
                continue
            effect_block = effect_blocks[0].text
            # Native previews are not tier mutations; validate the executable renderer separately.
            for preview in named_blocks(effect_block, "effect_tooltip"):
                effect_block = effect_block.replace(preview, "")
            engine_effect = mask_comments(effect_block)
            if re.search(r"\b(?:has_idea|swap_ideas)\s*=", engine_effect):
                issues.append(f"{effect_id} still derives transitions from idea state")
            branches = direct_named_blocks(effect_block, "if")
            if len(branches) != 1 or direct_named_blocks(effect_block, "else_if"):
                issues.append(f"{effect_id} needs one direct guarded transition branch")
                continue
            branch = branches[0]
            limits = direct_named_blocks(branch.text, "limit", branch.start)
            setters = direct_named_blocks(branch.text, "set_variable", branch.start)
            hidden_blocks = direct_named_blocks(branch.text, "hidden_effect", branch.start)
            for hidden_block in hidden_blocks:
                setters += direct_named_blocks(hidden_block.text, "set_variable", hidden_block.start)
            if len(limits) != 1 or len(setters) != 1 or len(hidden_blocks) != 1:
                issues.append(
                    f"{effect_id} must directly contain one limit, level setter, and hidden renderer"
                )
                continue
            limit = limits[0]
            hidden_limits = direct_named_blocks(limit.text, "hidden_trigger", limit.start)
            if len(hidden_limits) == 1:
                limit = hidden_limits[0]
            guards = direct_named_blocks(limit.text, "OR", limit.start)
            if len(guards) != 1:
                issues.append(f"{effect_id} needs one direct OR level guard")
            else:
                guard = guards[0]
                missing_checks = direct_named_blocks(guard.text, "NOT", guard.start)
                level_checks = direct_named_blocks(guard.text, "check_variable", guard.start)
                guard_operands = assignment_names_at_depth(guard.text, 1)
                if len(guard_operands) != 2 or set(guard_operands) != {
                    "NOT",
                    "check_variable",
                }:
                    issues.append(
                        f"{effect_id} OR guard must contain only missing-variable and less-than checks"
                    )
                if (
                    len(missing_checks) != 1
                    or assignment_values(missing_checks[0].text, "has_variable") != [variable]
                    or assignment_names_at_depth(missing_checks[0].text, 1)
                    != ["has_variable"]
                ):
                    issues.append(f"{effect_id} does not guard the missing {variable}")
                if len(level_checks) != 1 or (
                    scalar_values(level_checks[0].text, "var") != [variable]
                    or scalar_values(level_checks[0].text, "value") != [str(tier)]
                    or scalar_values(level_checks[0].text, "compare") != ["less_than"]
                    or assignment_names_at_depth(level_checks[0].text, 1)
                    != ["var", "value", "compare"]
                ):
                    issues.append(f"{effect_id} does not guard {variable} as less than {tier}")
            setter = setters[0].text
            if not re.search(
                rf"\bvar\s*=\s*{re.escape(variable)}\b.*?\bvalue\s*=\s*{tier}\b",
                mask_comments(setter),
                re.DOTALL,
            ):
                issues.append(f"{effect_id} does not set {variable} to {tier}")
            hidden = validate_hidden_renderer(effect_id, branch.text, family, target)
            all_removals = scalar_values(effect_block, "remove_ideas")
            all_additions = scalar_values(effect_block, "add_ideas")
            if hidden is not None and (
                all_removals != scalar_values(hidden, "remove_ideas")
                or all_additions != scalar_values(hidden, "add_ideas")
            ):
                issues.append(f"{effect_id} renders tier ideas outside hidden_effect")
            dirty_calls = scalar_values(hidden or "", "ADISCORD_economy_mark_dirty")
            if family in {"administration", "industry"} and dirty_calls != ["yes"]:
                issues.append(f"{effect_id} must mark the economy dirty inside its renderer")
            if family == "army" and dirty_calls:
                issues.append(f"{effect_id} must not mark the economy dirty")

    reputation_refresh = named_block_spans(effects, "VAL_refresh_contract_reputation")
    if len(reputation_refresh) != 1:
        issues.append("expected exactly one reputation refresh selector")
    else:
        refresh = reputation_refresh[0].text
        conditional_branches = sorted(
            [
                *direct_named_blocks(refresh, "if"),
                *direct_named_blocks(refresh, "else_if"),
            ],
            key=lambda branch: branch.start,
        )
        if [branch.name for branch in conditional_branches] != ["if", "else_if", "else_if"]:
            issues.append("reputation refresh must select tiers 3, 2, and 1 in descending order")
        else:
            for tier, branch in zip((3, 2, 1), conditional_branches):
                limits = direct_named_blocks(branch.text, "limit", branch.start)
                checks = (
                    direct_named_blocks(limits[0].text, "check_variable", limits[0].start)
                    if len(limits) == 1
                    else []
                )
                if len(checks) != 1 or (
                    assignment_values(checks[0].text, "var")
                    != ["VAL_contract_reputation_level"]
                    or assignment_values(checks[0].text, "value") != [str(tier)]
                    or assignment_values(checks[0].text, "compare")
                    != ["greater_than_or_equals"]
                ):
                    issues.append(f"reputation refresh has an invalid tier {tier} level check")
                effect_id = f"VAL_apply_contract_reputation_{tier}"
                renderer_calls = re.findall(
                    r"\bVAL_apply_contract_reputation_([0-3])\s*=\s*yes\b",
                    mask_comments(branch.text),
                )
                if renderer_calls != [str(tier)]:
                    issues.append(f"reputation refresh tier {tier} does not call only {effect_id}")
        fallback = direct_named_blocks(refresh, "else")
        fallback_calls = re.findall(
            r"\bVAL_apply_contract_reputation_([0-3])\s*=\s*yes\b",
            mask_comments(fallback[0].text if fallback else ""),
        )
        if len(fallback) != 1 or fallback_calls != ["0"]:
            issues.append("reputation refresh needs an unconditional tier-0 fallback")
        elif named_block_spans(fallback[0].text, "check_variable"):
            issues.append("reputation tier-0 fallback must not have a level guard")
    for level in range(4):
        effect_id = f"VAL_apply_contract_reputation_{level}"
        effect_blocks = named_block_spans(effects, effect_id)
        if len(effect_blocks) != 1:
            issues.append(f"expected exactly one reputation renderer {effect_id}")
            continue
        effect_block = effect_blocks[0].text
        if re.search(r"\b(?:has_idea|swap_ideas)\s*=", mask_comments(effect_block)):
            issues.append(f"{effect_id} still derives rendering from idea state")
        target = tier_families["reputation"][level]
        hidden = validate_hidden_renderer(effect_id, effect_block, "reputation", target)
        if hidden is not None and (
            scalar_values(effect_block, "remove_ideas")
            != scalar_values(hidden, "remove_ideas")
            or scalar_values(effect_block, "add_ideas")
            != scalar_values(hidden, "add_ideas")
        ):
            issues.append(f"{effect_id} renders reputation ideas outside hidden_effect")

    migration_focuses = {
        ("administration", 3): {"VAL_State_Contract"},
        ("administration", 2): {
            "VAL_Central_Payment_Office",
            "VAL_Provincial_Contract_Courts",
        },
        ("administration", 1): {
            "VAL_The_Weaponry_Baron",
            "VAL_Provincial_Brokers",
            "VAL_Ministry_Auditors",
        },
        ("industry", 3): {"VAL_Industrial_Mobilization_Plan"},
        ("industry", 2): {
            "VAL_Standardize_Rifle_Lots",
            "VAL_Standard_Cartridges",
            "VAL_Three_Shift_Arsenals",
        },
        ("industry", 1): {
            "VAL_Contract_Accounting_Office",
            "VAL_Munitions_Board",
        },
        ("army", 3): {"VAL_Contract_General_Staff", "VAL_Army_Of_The_Ledger"},
        ("army", 2): {
            "VAL_Contractor_Officers",
            "VAL_Motorized_Columns",
            "VAL_Field_Repair_Corps",
            "VAL_Contract_NCO_Schools",
            "VAL_Logistics_Command",
        },
        ("army", 1): {
            "VAL_Count_The_Captains",
            "VAL_The_Mercenary_State",
            "VAL_Company_Rosters",
            "VAL_Border_Survey_Corps",
            "VAL_Company_Service_Code",
        },
    }
    migration_blocks = named_block_spans(effects, TIER_MIGRATION_EFFECT)
    if len(migration_blocks) != 1:
        issues.append("expected exactly one VAL_migrate_contract_tier_levels effect")
    else:
        migration = migration_blocks[0].text
        migration_branches = sorted(
            [
                *direct_named_blocks(migration, "if"),
                *direct_named_blocks(migration, "else_if"),
            ],
            key=lambda branch: branch.start,
        )
        expected_branches = [
            (family, tier, "if" if tier == 3 else "else_if")
            for family in ("administration", "industry", "army")
            for tier in (3, 2, 1)
        ]
        if len(migration_branches) != len(expected_branches):
            issues.append("tier migration must have one descending three-branch chain per family")
        else:
            for branch, (family, tier, branch_name) in zip(
                migration_branches, expected_branches
            ):
                effect_id = f"VAL_apply_contract_{family}_{tier}"
                if branch.name != branch_name:
                    issues.append(f"{effect_id} migration branch is out of descending order")
                apply_calls = re.findall(
                    r"(?m)^\s*(VAL_apply_contract_(?:administration|industry|army)_[1-3])\s*=\s*yes\s*$",
                    mask_comments(branch.text),
                )
                if apply_calls != [effect_id]:
                    issues.append(f"migration branch must call only {effect_id}")
                limits = direct_named_blocks(branch.text, "limit", branch.start)
                if len(limits) != 1:
                    issues.append(f"{effect_id} migration branch needs one direct limit")
                    continue
                limit = limits[0]
                missing = direct_named_blocks(limit.text, "NOT", limit.start)
                variable = level_variables[family]
                if (
                    len(missing) != 1
                    or assignment_values(missing[0].text, "has_variable") != [variable]
                    or assignment_names_at_depth(missing[0].text, 1)
                    != ["has_variable"]
                ):
                    issues.append(f"{effect_id} migration must require missing {variable}")
                expected_focuses = migration_focuses[(family, tier)]
                limit_operands = assignment_names_at_depth(limit.text, 1)
                if len(expected_focuses) == 1:
                    direct_focuses = assignment_values_at_depth(
                        limit.text, "has_completed_focus", 1
                    )
                    if (
                        len(limit_operands) != 2
                        or set(limit_operands) != {"NOT", "has_completed_focus"}
                        or direct_focuses != list(expected_focuses)
                    ):
                        issues.append(
                            f"{effect_id} migration must directly check its single caller focus"
                        )
                else:
                    alternatives = direct_named_blocks(limit.text, "OR", limit.start)
                    if (
                        len(limit_operands) != 2
                        or set(limit_operands) != {"NOT", "OR"}
                        or len(alternatives) != 1
                    ):
                        issues.append(
                            f"{effect_id} migration must combine caller focuses in one direct OR"
                        )
                    else:
                        alternative_operands = assignment_names_at_depth(
                            alternatives[0].text, 1
                        )
                        alternative_focuses = assignment_values_at_depth(
                            alternatives[0].text, "has_completed_focus", 1
                        )
                        if (
                            alternative_operands
                            != ["has_completed_focus"] * len(expected_focuses)
                            or len(alternative_focuses) != len(expected_focuses)
                            or set(alternative_focuses) != expected_focuses
                        ):
                            issues.append(
                                f"{effect_id} migration OR alternatives do not exactly cover callers"
                            )

    migration_call_pattern = re.compile(
        rf"(?m)^\s*{re.escape(TIER_MIGRATION_EFFECT)}\s*=\s*yes\b"
    )
    migration_callers: list[str] = []
    for runtime_root in ("common", "events", "history"):
        for path in sorted((ROOT / runtime_root).rglob("*.txt")):
            source = path.read_text(encoding="utf-8-sig", errors="replace")
            if migration_call_pattern.search(mask_comments(source)):
                migration_callers.append(path.relative_to(ROOT).as_posix())
    if migration_callers:
        issues.append(
            f"{TIER_MIGRATION_EFFECT} must have zero runtime callers, found "
            f"{migration_callers}"
        )

    ideas_text = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
    hidden_ideas = named_blocks(ideas_text, "hidden_ideas")
    if not hidden_ideas:
        issues.append("Kefreyt has no hidden-idea layer for technical bonuses")
    else:
        for idea_id in (
            "VAL_contract_reputation_0",
            "VAL_contract_reputation_1",
            "VAL_contract_reputation_2",
            "VAL_contract_reputation_3",
            "VAL_contract_administration_1",
            "VAL_contract_administration_2",
            "VAL_contract_administration_3",
            "VAL_contract_industry_1",
            "VAL_contract_industry_2",
            "VAL_contract_industry_3",
            "VAL_contract_army_1",
            "VAL_contract_army_2",
            "VAL_contract_army_3",
            "VAL_hot_production_lines",
        ):
            declarations = named_blocks(hidden_ideas[0], idea_id)
            if len(declarations) != 1:
                issues.append(f"technical idea must be declared once under hidden_ideas: {idea_id}")

    candidate_ids = {
        entry.key for entry in walk_script(parse_clausewitz(ideas_text))
        if isinstance(entry.value, list) and "name" in script_fields(entry.value)
        and entry.key.startswith("VAL_")
    }
    preview_sources = {}
    for runtime_root in ("common", "events", "history"):
        for path in sorted((ROOT / runtime_root).rglob("*.txt")):
            source = path.read_text(encoding="utf-8-sig", errors="replace")
            if any(idea in source for idea in candidate_ids):
                preview_sources[path.relative_to(ROOT).as_posix()] = source
    display_only, preview_issues = validate_val_preview_ideas(
        ideas_text, preview_sources,
        read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"),
        read("common/scripted_effects/ADISCORD_VAL_effects.txt"))
    issues.extend(preview_issues)

    for ideas_path in (
        "common/ideas/ADISCORD_VAL_rework_ideas.txt",
        "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt",
    ):
        ideas_text = read(ideas_path)
        for idea_id in sorted(set(re.findall(r"(?m)^\s*(VAL_[A-Za-z0-9_]+)\s*=\s*\{", ideas_text))):
            idea_blocks = named_blocks(ideas_text, idea_id)
            if idea_blocks and idea_id not in display_only and not re.search(r"\bpicture\s*=", mask_comments(idea_blocks[0])):
                issues.append(f"idea {idea_id} has no picture")

    # Kefreyt starts without domestic steel. Its initial steel supply comes from
    # Vorkerland resource rights to state 33; later conquests/projects may add more.
    for state_id, path in (
        (24, "history/states/24-Irem.txt"),
        (42, "history/states/42-Prigranichie.txt"),
        (48, "history/states/48-Depoitodron.txt"),
        (54, "history/states/54-Spastlant.txt"),
        (55, "history/states/55-Erstantpeo.txt"),
        (56, "history/states/56-Zeigen.txt"),
        (57, "history/states/57-Zoilong.txt"),
        (168, "history/states/168-168.txt"),
    ):
        homeland = read(path)
        resources = named_blocks(homeland, "resources")
        if resources and re.search(r"(?m)^\s*steel\s*=", resources[0]):
            issues.append(f"Kefreyt homeland state {state_id} must not contain starting steel")
    vorkerland_start = read("history/states/33-33.txt")
    if not re.search(r"resources\s*=\s*\{[^}]*steel\s*=\s*16", vorkerland_start, re.S):
        issues.append("state 33 must retain Kefreyt's starting Vorkerland steel source")
    arsenal_init = named_blocks(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_initialize_arsenal_recovery")
    if not arsenal_init or "give_resource_rights = { receiver = VAL state = 33 }" not in arsenal_init[0]:
        issues.append("Kefreyt startup must grant Vorkerland steel rights in state 33")

    state_202 = read("history/states/38-38.txt")
    if not re.search(r"resources\s*=\s*\{[^}]*steel\s*=\s*10", state_202, re.S):
        issues.append("state 38 does not contain the baseline Vorkerland steel deposit")
    collapse_events = source_section(read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events')
    if "VAL_handle_vorkerland_war_outbreak = yes" not in collapse_events:
        issues.append("Vorkerland war start does not disrupt Kefreyt contracts")

    gfx = read("interface/ADISCORD_VAL_operations.gfx")
    gui = read("interface/ADISCORD_VAL_operations.gui")
    scripted_gui = read("common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt")
    panel = named_blocks(scripted_gui, "ADISCORD_VAL_operations_panel")
    if not panel:
        issues.append("operations scripted-GUI panel is missing")
    else:
        for token in (
            "context_type = decision_category",
            'window_name = "ADISCORD_VAL_operations_panel_window"',
            "visible = { always = yes }",
        ):
            if token not in " ".join(panel[0].split()):
                issues.append(f"operations scripted-GUI panel is missing {token}")
    from tools.builders.build_adiscord_val_operations_map import STATE_IDS, FRAME_COUNT
    if "instantTextBoxType" in gui:
        issues.append("operations map must not contain visible text labels")
    for state in STATE_IDS:
        path = ROOT / f"gfx/interface/VAL_operations/VAL_ops_state_{state}.png"
        if not path.exists():
            issues.append(f"missing operations overlay for state {state}")
            continue
        with Image.open(path) as image:
            if image.width % FRAME_COUNT or not 0 < image.width // FRAME_COUNT <= 420 or not 0 < image.height <= 340:
                issues.append(f"state {state} overlay has size {image.size}, expected {FRAME_COUNT} cropped frames")
        for text, label in ((gfx, "GFX"), (gui, "GUI"), (scripted_gui, "scripted GUI")):
            if f"{state}" not in text:
                issues.append(f"state {state} is missing from operations {label}")
    background = ROOT / "gfx/interface/VAL_operations/VAL_ops_map_background.png"
    if not background.exists():
        issues.append("missing operations-map background")
    else:
        with Image.open(background) as image:
            if image.size != (420, 340):
                issues.append(f"operations background has size {image.size}, expected 420x340")

    localization_path = ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"
    if not localization_path.read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian rework localisation is missing its UTF-8 BOM")
    localization = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
    for key in (*required, "VAL_quarterly_contract_deadline", "VAL_operations_map_tt"):
        if not re.search(rf"(?m)^\s*{re.escape(key)}:", localization):
            issues.append(f"missing Russian localisation {key}")

    all_russian_localization = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="replace")
        for path in (ROOT / "localisation/russian").glob("*.yml")
    )
    for focus_id in sorted(ids):
        for key in (focus_id, f"{focus_id}_desc"):
            if not re.search(rf"(?m)^\s*{re.escape(key)}:", all_russian_localization):
                issues.append(f"missing Russian localisation {key}")
    for key in (
        "VAL_rework_debug",
        "VAL_debug_initialize_systems",
        "VAL_debug_unlock_operations_map",
        "VAL_debug_disrupt_vorkerland_contracts",
        "VAL_debug_lose_westerholm_metal",
        "VAL_debug_reputation_maximum",
        "VAL_debug_reputation_minimum",
        "VAL_debug_grant_contract_reserves",
        "VAL_debug_reset_rework_state",
        "ADISCORD_cost_t50",
        "ADISCORD_cost_t100",
        "ADISCORD_cost_t200",
        "ADISCORD_cost_t500",
        "ADISCORD_cost_r2500",
        "ADISCORD_cost_r4000",
    ):
        if not re.search(rf"(?m)^\s*{re.escape(key)}:", all_russian_localization):
            issues.append(f"missing Russian localisation {key}")

    if issues:
        print("Kefreyt rework validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"Kefreyt rework validation passed ({len(focuses)} focuses, {len(STATE_IDS)} active map regions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
