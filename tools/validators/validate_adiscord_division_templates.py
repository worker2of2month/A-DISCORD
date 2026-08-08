"""Validate the machine-readable A-Discord division-template audit.

The validator parses Clausewitz structure instead of treating the repository as
plain text.  In particular, comments, quoted inline ``create_unit`` payloads,
and unrelated nested ``name`` keys cannot become template definitions.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "tools" / "data" / "division_template_audit.json"

SCRIPT_GLOBS = (
    "common/on_actions/*.txt",
    "common/scripted_effects/*.txt",
    "common/decisions/**/*.txt",
    "common/operations/*.txt",
    "events/*.txt",
)

PROTECTED_OPTIONAL_SOURCES = {
    "history/units/ARS.txt",
    "history/units/KDL.txt",
    "history/units/SRV.txt",
    "history/units/SVL.txt",
    "history/units/VLD.txt",
    "history/units/VRA.txt",
}


@dataclass(frozen=True)
class Token:
    value: str
    line: int
    quoted: bool = False


@dataclass
class Entry:
    key: str
    value: str | list["Entry"]
    line: int
    quoted: bool = False


@dataclass(frozen=True)
class Slot:
    kind: str
    unit: str
    x: int
    y: int


@dataclass
class ActualTemplate:
    source_kind: str
    path: str
    owner: str
    namespace: str
    name: str
    line: int
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class ActualReference:
    path: str
    kind: str
    name: str
    line: int
    start_experience_factor: float | None
    start_equipment_factor: float | None


@dataclass
class Subunit:
    name: str
    categories: set[str]
    organization: float
    manpower: float
    equipment: dict[str, float]
    supply: float


@dataclass
class ComputedTemplate:
    organization: float
    manpower: float
    equipment: dict[str, float]
    supply: float
    availability: dict[str, bool]


def _tokens(text: str) -> list[Token]:
    result: list[Token] = []
    index = 0
    line = 1
    while index < len(text):
        char = text[index]
        if char in " \t\r":
            index += 1
            continue
        if char == "\n":
            line += 1
            index += 1
            continue
        if char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if char in "{}=":
            result.append(Token(char, line))
            index += 1
            continue
        if char == '"':
            start_line = line
            index += 1
            value: list[str] = []
            while index < len(text):
                char = text[index]
                if char == "\\" and index + 1 < len(text):
                    value.append(text[index + 1])
                    index += 2
                    continue
                if char == '"':
                    index += 1
                    break
                if char == "\n":
                    line += 1
                value.append(char)
                index += 1
            result.append(Token("".join(value), start_line, True))
            continue
        start = index
        start_line = line
        while index < len(text) and text[index] not in " \t\r\n#{}=":
            index += 1
        result.append(Token(text[start:index], start_line))
    return result


def parse_clausewitz(text: str) -> list[Entry]:
    """Parse the structural subset used by OOBs and scripted effects."""

    tokens = _tokens(text)
    position = 0

    def parse_block(expect_close: bool = False) -> list[Entry]:
        nonlocal position
        entries: list[Entry] = []
        while position < len(tokens):
            if tokens[position].value == "}":
                if not expect_close:
                    raise ValueError(f"unexpected closing brace at line {tokens[position].line}")
                position += 1
                return entries
            if tokens[position].value == "{":
                opening = tokens[position]
                position += 1
                entries.append(Entry("", parse_block(True), opening.line))
                continue
            key = tokens[position]
            position += 1
            if position < len(tokens) and tokens[position].value == "=":
                position += 1
                if position >= len(tokens):
                    raise ValueError(f"missing value for {key.value} at line {key.line}")
                if tokens[position].value == "{":
                    position += 1
                    entries.append(Entry(key.value, parse_block(True), key.line))
                    continue
                value = tokens[position]
                position += 1
                # Clausewitz permits prefixed blocks such as ``color = rgb {}``.
                if position < len(tokens) and tokens[position].value == "{":
                    position += 1
                    entries.append(Entry(key.value, parse_block(True), key.line))
                else:
                    entries.append(Entry(key.value, value.value, key.line, value.quoted))
            else:
                entries.append(Entry("", key.value, key.line, key.quoted))
        if expect_close:
            raise ValueError("unterminated Clausewitz block")
        return entries

    return parse_block()


def _walk(entries: list[Entry], ancestors: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Entry]]:
    for entry in entries:
        yield ancestors, entry
        if isinstance(entry.value, list):
            yield from _walk(entry.value, ancestors + (entry.key,))


def _entries(entries: list[Entry], key: str) -> list[Entry]:
    return [entry for entry in entries if entry.key == key]


def _scalar(entries: list[Entry], key: str) -> str | None:
    for entry in entries:
        if entry.key == key and isinstance(entry.value, str):
            return entry.value
    return None


def _number(entries: list[Entry], key: str, default: float | None = None) -> float | None:
    value = _scalar(entries, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _factor(
    entries: list[Entry],
    key: str,
    default: float,
    context: str,
    issues: list[str],
) -> float | None:
    entry = next((candidate for candidate in entries if candidate.key == key), None)
    if entry is None:
        return default
    if isinstance(entry.value, str):
        try:
            return float(entry.value)
        except ValueError:
            pass
    issues.append(f"{context}: invalid numeric {key} {entry.value!r}")
    return None


def _read_ast(path: Path) -> list[Entry]:
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _script_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in SCRIPT_GLOBS:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths)


def _slots(block: list[Entry]) -> tuple[Slot, ...]:
    result: list[Slot] = []
    for kind in ("regiments", "support"):
        for container in _entries(block, kind):
            if not isinstance(container.value, list):
                continue
            for entry in container.value:
                if not entry.key or not isinstance(entry.value, list):
                    continue
                x = _number(entry.value, "x")
                y = _number(entry.value, "y")
                if x is None or y is None:
                    continue
                result.append(Slot(kind, entry.key, int(x), int(y)))
    return tuple(result)


def collect_templates_and_references(root: Path) -> tuple[list[ActualTemplate], list[ActualReference], list[str]]:
    issues: list[str] = []
    active_oobs: set[str] = set()
    discovery_paths = sorted((root / "history" / "countries").glob("*.txt")) + _script_paths(root)
    parsed_scripts: dict[Path, list[Entry]] = {}
    for path in discovery_paths:
        try:
            ast = _read_ast(path)
        except (OSError, ValueError) as error:
            issues.append(f"{_relative(root, path)}: Clausewitz parse error: {error}")
            continue
        if path in _script_paths(root):
            parsed_scripts[path] = ast
        for _, entry in _walk(ast):
            if entry.key in {"oob", "load_oob"} and isinstance(entry.value, str):
                active_oobs.add(entry.value)

    templates: list[ActualTemplate] = []
    references: list[ActualReference] = []
    units_dir = root / "history" / "units"
    for oob in sorted(active_oobs):
        path = units_dir / f"{oob}.txt"
        if not path.is_file():
            issues.append(f"active OOB {oob} has no history/units/{oob}.txt")
            continue
        try:
            ast = _read_ast(path)
        except (OSError, ValueError) as error:
            issues.append(f"{_relative(root, path)}: Clausewitz parse error: {error}")
            continue
        owner = oob.split("_", 1)[0]
        relative = _relative(root, path)
        for entry in ast:
            if entry.key != "division_template" or not isinstance(entry.value, list):
                continue
            name = _scalar(entry.value, "name")
            if name is None:
                issues.append(f"{relative}:{entry.line}: division template has no direct name")
                continue
            templates.append(
                ActualTemplate("oob", relative, owner, f"oob:{oob}", name, entry.line, _slots(entry.value))
            )
        for _, entry in _walk(ast):
            if entry.key != "division" or not isinstance(entry.value, list):
                continue
            name = _scalar(entry.value, "division_template")
            if name is None:
                continue
            references.append(
                ActualReference(
                    relative,
                    "oob",
                    name,
                    entry.line,
                    _factor(
                        entry.value,
                        "start_experience_factor",
                        1.0,
                        f"{relative}:{entry.line}",
                        issues,
                    ),
                    _factor(
                        entry.value,
                        "start_equipment_factor",
                        1.0,
                        f"{relative}:{entry.line}",
                        issues,
                    ),
                )
            )

    for path in _script_paths(root):
        ast = parsed_scripts.get(path)
        if ast is None:
            try:
                ast = _read_ast(path)
            except (OSError, ValueError):
                continue
        relative = _relative(root, path)
        for ancestors, entry in _walk(ast):
            if entry.key == "division_template" and isinstance(entry.value, list):
                name = _scalar(entry.value, "name")
                if name is not None:
                    templates.append(
                        ActualTemplate("script", relative, "script", f"script:{relative}", name, entry.line, _slots(entry.value))
                    )
            elif entry.key == "division_template" and isinstance(entry.value, str):
                references.append(
                    ActualReference(relative, "technical_reference", entry.value, entry.line, None, None)
                )
            if entry.key != "create_unit" or not isinstance(entry.value, list):
                continue
            for division in _entries(entry.value, "division"):
                if not isinstance(division.value, str):
                    continue
                try:
                    inline = parse_clausewitz(division.value)
                except ValueError as error:
                    issues.append(
                        f"{relative}:{division.line}: create_unit division parse error: {error}"
                    )
                    continue
                name = _scalar(inline, "division_template")
                if name is None:
                    issues.append(f"{relative}:{division.line}: create_unit has no literal division_template")
                    continue
                references.append(
                    ActualReference(
                        relative,
                        "create_unit",
                        name,
                        division.line,
                        _factor(
                            inline,
                            "start_experience_factor",
                            1.0,
                            f"{relative}:{division.line}: create_unit",
                            issues,
                        ),
                        _factor(
                            inline,
                            "start_equipment_factor",
                            1.0,
                            f"{relative}:{division.line}: create_unit",
                            issues,
                        ),
                    )
                )
    return templates, references, issues


def _accepted_name(expected: dict[str, object], actual: str) -> bool:
    names = [expected.get("technical_name"), *expected.get("legacy_names", [])]
    return actual in names


def _same_factor(actual: float | None, expected: object) -> bool:
    if actual is None:
        return expected is None
    return isinstance(expected, (int, float)) and abs(actual - float(expected)) < 1e-9


def _collect_subunits(root: Path) -> tuple[dict[str, Subunit], list[str]]:
    result: dict[str, Subunit] = {}
    issues: list[str] = []
    for path in sorted((root / "common" / "units").glob("*.txt")):
        try:
            ast = _read_ast(path)
        except (OSError, ValueError) as error:
            issues.append(f"{_relative(root, path)}: Clausewitz parse error: {error}")
            continue
        for container in _entries(ast, "sub_units"):
            if not isinstance(container.value, list):
                continue
            for entry in container.value:
                if not entry.key or not isinstance(entry.value, list):
                    continue
                categories: set[str] = set()
                for category_block in _entries(entry.value, "categories"):
                    if not isinstance(category_block.value, list):
                        continue
                    categories.update(
                        item.value
                        for item in category_block.value
                        if item.key == "" and isinstance(item.value, str)
                    )
                equipment: dict[str, float] = {}
                for need in _entries(entry.value, "need"):
                    if not isinstance(need.value, list):
                        continue
                    for item in need.value:
                        if item.key and isinstance(item.value, str):
                            try:
                                equipment[item.key] = equipment.get(item.key, 0.0) + float(item.value)
                            except ValueError:
                                issues.append(
                                    f"{_relative(root, path)}:{item.line}: non-numeric need for {item.key}"
                                )
                result[entry.key] = Subunit(
                    entry.key,
                    categories,
                    _number(entry.value, "max_organisation", 0.0) or 0.0,
                    _number(entry.value, "manpower", 0.0) or 0.0,
                    equipment,
                    _number(entry.value, "supply_consumption", 0.0) or 0.0,
                )
    return result, issues


def _collect_equipment_archetypes(root: Path) -> tuple[set[str], list[str]]:
    definitions: dict[str, list[Entry]] = {}
    issues: list[str] = []
    for path in sorted((root / "common" / "units" / "equipment").glob("*.txt")):
        try:
            ast = _read_ast(path)
        except (OSError, ValueError) as error:
            issues.append(f"{_relative(root, path)}: Clausewitz parse error: {error}")
            continue
        for container in _entries(ast, "equipments"):
            if not isinstance(container.value, list):
                continue
            for entry in container.value:
                if entry.key and isinstance(entry.value, list):
                    definitions[entry.key] = entry.value
    archetypes = {
        name
        for name, block in definitions.items()
        if _scalar(block, "is_archetype") == "yes"
    }
    archetypes.update(
        archetype
        for block in definitions.values()
        if (archetype := _scalar(block, "archetype")) is not None
    )
    return archetypes, issues


def _starting_organization_modifiers(root: Path) -> tuple[dict[str, float], list[str]]:
    issues: list[str] = []
    effects_path = root / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt"
    try:
        effects = _read_ast(effects_path)
    except (OSError, ValueError) as error:
        return {}, [f"{_relative(root, effects_path)}: cannot derive starting technology: {error}"]

    profile_blocks = {
        entry.key: entry.value
        for entry in effects
        if entry.key.startswith("ADISCORD_grant_technology_profile_")
        and isinstance(entry.value, list)
    }
    profile = profile_blocks.get("ADISCORD_grant_technology_profile_common")
    baseline = next(
        (
            entry.value
            for entry in effects
            if entry.key == "ADISCORD_grant_2150_technology_baseline"
            and isinstance(entry.value, list)
        ),
        None,
    )
    starting = next(
        (
            entry.value
            for entry in effects
            if entry.key == "ADISCORD_grant_starting_technology_profile"
            and isinstance(entry.value, list)
        ),
        None,
    )
    if profile is None:
        return {}, [f"{_relative(root, effects_path)}: missing common starting technology profile"]
    if baseline is None or _scalar(baseline, "ADISCORD_grant_technology_profile_common") != "yes":
        issues.append(f"{_relative(root, effects_path)}: baseline does not grant common technology profile")
    if starting is None or _scalar(starting, "ADISCORD_grant_2150_technology_baseline") != "yes":
        issues.append(f"{_relative(root, effects_path)}: starting profile does not grant baseline")

    on_actions_path = root / "common/on_actions/00_ADISCORD_on_actions.txt"
    try:
        on_actions = _read_ast(on_actions_path)
    except (OSError, ValueError) as error:
        issues.append(f"{_relative(root, on_actions_path)}: cannot trace starting technology route: {error}")
    else:
        routed = any(
            entry.key == "ADISCORD_grant_starting_technology_profile"
            and entry.value == "yes"
            and "on_startup" in ancestors
            and "every_country" in ancestors
            for ancestors, entry in _walk(on_actions)
        )
        if not routed:
            issues.append(
                f"{_relative(root, on_actions_path)}: starting technology profile is not routed through on_startup every_country"
            )

    def profile_technologies(block: list[Entry]) -> set[str]:
        technology_ids: set[str] = set()
        for set_technology in _entries(block, "set_technology"):
            if not isinstance(set_technology.value, list):
                continue
            technology_ids.update(
                entry.key
                for entry in set_technology.value
                if entry.key and entry.key != "popup" and entry.value == "1"
            )
        return technology_ids

    technology_ids = profile_technologies(profile)
    called_profiles = {
        entry.key
        for _, entry in _walk(starting or [])
        if entry.key.startswith("ADISCORD_grant_technology_profile_")
        and entry.value == "yes"
    }
    starting_profile_technologies: set[str] = set(technology_ids)
    for profile_name in sorted(called_profiles):
        called_profile = profile_blocks.get(profile_name)
        if called_profile is None:
            issues.append(f"starting profile calls missing effect {profile_name}")
            continue
        starting_profile_technologies.update(profile_technologies(called_profile))

    technology_blocks: dict[str, list[Entry]] = {}
    for path in sorted((root / "common" / "technologies").glob("*.txt")):
        try:
            ast = _read_ast(path)
        except (OSError, ValueError) as error:
            issues.append(f"{_relative(root, path)}: Clausewitz parse error: {error}")
            continue
        for container in _entries(ast, "technologies"):
            if not isinstance(container.value, list):
                continue
            for entry in container.value:
                if entry.key and isinstance(entry.value, list):
                    technology_blocks[entry.key] = entry.value

    modifiers: dict[str, float] = defaultdict(float)
    for technology_id in sorted(starting_profile_technologies):
        block = technology_blocks.get(technology_id)
        if block is None:
            issues.append(f"starting technology {technology_id} has no definition")
            continue
        organization_effects = [
            (entry.key, value)
            for entry in block
            if entry.key
            and isinstance(entry.value, list)
            and (value := _number(entry.value, "max_organisation")) is not None
        ]
        if technology_id not in technology_ids and organization_effects:
            issues.append(
                "owner-specific starting organization modifier "
                f"{technology_id} is not represented by the common-baseline audit"
            )
            continue
        for target, value in organization_effects:
            modifiers[target] += value
    return dict(modifiers), issues


def _compute_template(
    template: ActualTemplate,
    subunits: dict[str, Subunit],
    archetypes: set[str],
    organization_modifiers: dict[str, float],
) -> tuple[ComputedTemplate | None, list[str]]:
    issues: list[str] = []
    organization_values: list[float] = []
    manpower = 0.0
    supply = 0.0
    equipment: dict[str, float] = defaultdict(float)
    for slot in template.slots:
        subunit = subunits.get(slot.unit)
        if subunit is None:
            issues.append(
                f"{template.path}:{template.line}: missing subunit {slot.unit} in template {template.name}"
            )
            continue
        organization = subunit.organization
        for target, value in organization_modifiers.items():
            if target == subunit.name or target in subunit.categories:
                organization += value
        organization_values.append(organization)
        manpower += subunit.manpower
        supply += subunit.supply
        for archetype, quantity in subunit.equipment.items():
            equipment[archetype] += quantity
    if len(organization_values) != len(template.slots) or not organization_values:
        return None, issues
    availability = {name: name in archetypes for name in equipment}
    for name, available in availability.items():
        if not available:
            issues.append(
                f"{template.path}:{template.line}: missing equipment archetype {name} required by {template.name}"
            )
    return (
        ComputedTemplate(
            sum(organization_values) / len(organization_values),
            manpower,
            dict(sorted(equipment.items())),
            supply,
            dict(sorted(availability.items())),
        ),
        issues,
    )


def _float_equal(left: object, right: float) -> bool:
    return isinstance(left, (int, float)) and abs(float(left) - right) < 1e-6


def _validate_computed_rows(
    audit: dict[str, object],
    templates: list[ActualTemplate],
    row_by_actual: dict[int, dict[str, object]],
    computed: dict[int, ComputedTemplate],
) -> list[str]:
    issues: list[str] = []
    floors = audit.get("role_floors", {})
    for index, row in row_by_actual.items():
        template = templates[index]
        actual = computed.get(index)
        if actual is None:
            continue
        expected_slots = {
            kind: [
                {"type": slot.unit, "x": slot.x, "y": slot.y}
                for slot in template.slots
                if slot.kind == kind
            ]
            for kind in ("regiments", "support")
        }
        for kind in ("regiments", "support"):
            if row.get(kind) != expected_slots[kind]:
                issues.append(f"{row.get('key')}: computed {kind} {expected_slots[kind]} does not match audit")
        expected = row.get("computed", {})
        for field, value in (
            ("organization", actual.organization),
            ("manpower", actual.manpower),
            ("supply", actual.supply),
        ):
            if not _float_equal(expected.get(field), value):
                issues.append(
                    f"{row.get('key')}: computed {field} {value:g} does not match audit {expected.get(field)}"
                )
        expected_equipment = expected.get("equipment", {})
        if expected_equipment != actual.equipment:
            issues.append(
                f"{row.get('key')}: computed equipment {actual.equipment} does not match audit {expected_equipment}"
            )
        if row.get("equipment_availability") != actual.availability:
            issues.append(
                f"{row.get('key')}: computed equipment availability {actual.availability} does not match audit"
            )
        role = row.get("ai_role")
        floor = floors.get(role)
        if not isinstance(floor, (int, float)):
            issues.append(f"{row.get('key')}: ai_role {role} has no organization floor")
        elif actual.organization + 1e-6 < float(floor):
            issues.append(
                f"{row.get('key')}: organization {actual.organization:g} is below {role} floor {float(floor):g}"
            )
    return issues


def _validate_schema(audit: dict[str, object]) -> list[str]:
    issues: list[str] = []
    if audit.get("schema_version") != 1:
        issues.append("audit schema_version must be 1")
    for collection in ("templates", "references"):
        seen: set[str] = set()
        for row in audit.get(collection, []):
            key = row.get("key")
            if not isinstance(key, str) or not key.isascii():
                issues.append(f"{collection} row key must be ASCII: {key}")
            elif key in seen:
                issues.append(f"duplicate {collection} row key {key}")
            seen.add(key)
            for field in ("technical_name", "display_name") if collection == "templates" else ("technical_name",):
                value = row.get(field)
                if not isinstance(value, str) or not value.isascii():
                    issues.append(f"{key}: canonical {field} must be ASCII")
        if collection == "templates":
            keys = seen
    for row in audit.get("templates", []):
        key = row.get("key")
        source = row.get("source")
        if not isinstance(source, dict):
            issues.append(f"{key}: source must be an object")
        else:
            source_kind = source.get("kind")
            if source_kind not in {"oob", "script"}:
                issues.append(f"{key}: source kind must be oob or script, got {source_kind}")
            for field in ("path", "owner"):
                value = source.get(field)
                if not isinstance(value, str) or not value or not value.isascii():
                    issues.append(f"{key}: source {field} must be a non-empty ASCII string")
        replacement = row.get("replacement_path")
        if not isinstance(replacement, dict) or replacement.get("kind") not in {"retain", "replace"}:
            issues.append(f"{key}: invalid replacement_path")
        elif replacement.get("target") not in keys:
            issues.append(f"{key}: replacement target {replacement.get('target')} is not audited")
    return issues


def _validate_optional_sources(root: Path, audit: dict[str, object]) -> list[str]:
    issues: list[str] = []
    optional = audit.get("optional_sources", [])
    registry_path = root / "tools/data/generated_output_owners.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"optional source registry cannot be read: {error}"] if optional else []
    ownership: dict[str, set[str]] = defaultdict(set)
    for family in registry.get("families", []):
        owner = family.get("owner_module")
        if not isinstance(owner, str):
            continue
        for output in family.get("output_globs", []):
            if isinstance(output, str):
                ownership[output].add(owner)
    actual_paths: set[str] = set()
    for entry in optional:
        path = entry.get("path")
        owner = entry.get("owner_module")
        if not isinstance(path, str) or not isinstance(owner, str):
            issues.append(f"optional source entry must declare ASCII path and owner_module: {entry}")
            continue
        actual_paths.add(path)
        if owner not in ownership.get(path, set()):
            issues.append(
                f"optional source {path} is not an exact output of registry owner {owner}"
            )
    # Unit fixtures may exercise arbitrary exact registry entries.  The real
    # checkout is deliberately narrower: only the six protected northern OOBs
    # observed before Task 7 writes may be absent from the committed candidate.
    if (root / ".git").exists() and actual_paths != PROTECTED_OPTIONAL_SOURCES:
        issues.append(
            "optional source allowlist must exactly equal the six protected northern OOB paths"
        )
    return issues


def _validate_structural_coverage(
    root: Path,
    audit: dict[str, object],
    templates: list[ActualTemplate],
    references: list[ActualReference],
) -> tuple[list[str], dict[int, dict[str, object]]]:
    issues: list[str] = []
    matched_templates: set[int] = set()
    row_by_actual: dict[int, dict[str, object]] = {}
    optional_paths = {entry["path"] for entry in audit.get("optional_sources", [])}
    for row in audit.get("templates", []):
        source = row.get("source", {})
        path = source.get("path")
        path_and_name_candidates = [
            index
            for index, template in enumerate(templates)
            if index not in matched_templates
            and template.path == path
            and _accepted_name(row, template.name)
        ]
        candidates = [
            index
            for index in path_and_name_candidates
            if templates[index].source_kind == source.get("kind")
            and templates[index].owner == source.get("owner")
        ]
        if not candidates:
            if path in optional_paths and not (root / path).exists():
                continue
            if path_and_name_candidates:
                actual = templates[path_and_name_candidates[0]]
                if source.get("kind") != actual.source_kind:
                    issues.append(
                        f"template coverage: audit row {row.get('key')} source kind "
                        f"{source.get('kind')} does not match actual {actual.source_kind}"
                    )
                if source.get("owner") != actual.owner:
                    issues.append(
                        f"template coverage: audit row {row.get('key')} source owner "
                        f"{source.get('owner')} does not match actual {actual.owner}"
                    )
                continue
            issues.append(f"template coverage: audit row {row.get('key')} has no actual definition at {path}")
            continue
        index = candidates[0]
        matched_templates.add(index)
        row_by_actual[index] = row
    for index, template in enumerate(templates):
        if index not in matched_templates:
            issues.append(
                f"template coverage: {template.path}:{template.line}: uncovered template {template.name}"
            )

    matched_references: set[int] = set()
    for row in audit.get("references", []):
        count = row.get("count", 1)
        candidates = [
            index
            for index, reference in enumerate(references)
            if index not in matched_references
            and reference.path == row.get("path")
            and reference.kind == row.get("kind")
            and _accepted_name(row, reference.name)
            and (
                reference.kind == "technical_reference"
                or (
                    _same_factor(reference.start_experience_factor, row.get("start_experience_factor"))
                    and _same_factor(reference.start_equipment_factor, row.get("start_equipment_factor"))
                )
            )
        ]
        if len(candidates) != count:
            issues.append(
                f"reference coverage: audit row {row.get('key')} expects {count}, found {len(candidates)}"
            )
        matched_references.update(candidates[: int(count)])
    for index, reference in enumerate(references):
        if index not in matched_references:
            issues.append(
                f"reference coverage: {reference.path}:{reference.line}: uncovered {reference.kind} reference {reference.name}"
            )
    return issues, row_by_actual


def validate(root: Path = ROOT, audit_path: Path | None = None) -> list[str]:
    """Return division-template audit issues without modifying the repository."""

    root = Path(root)
    path = Path(audit_path) if audit_path is not None else root / "tools/data/division_template_audit.json"
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{_relative(root, path)}: cannot read audit JSON: {error}"]

    issues = _validate_schema(audit)
    issues.extend(_validate_optional_sources(root, audit))
    templates, references, collection_issues = collect_templates_and_references(root)
    issues.extend(collection_issues)
    coverage_issues, row_by_actual = _validate_structural_coverage(root, audit, templates, references)
    issues.extend(coverage_issues)
    for template in templates:
        if not template.name.isascii():
            issues.append(f"{template.path}:{template.line}: non-ASCII technical template name {template.name}")
    for reference in references:
        if not reference.name.isascii():
            issues.append(f"{reference.path}:{reference.line}: non-ASCII {reference.kind} reference {reference.name}")

    compositions: dict[tuple[str, str], set[tuple[Slot, ...]]] = defaultdict(set)
    locations: dict[tuple[str, str], list[str]] = defaultdict(list)
    for template in templates:
        scope = f"owner {template.owner}" if template.source_kind == "oob" else template.namespace
        identity = (scope, template.name)
        compositions[identity].add(template.slots)
        locations[identity].append(f"{template.path}:{template.line}")
    for identity, variants in compositions.items():
        if len(variants) > 1:
            issues.append(
                f"divergent duplicate template {identity[1]} in {identity[0]} at {', '.join(locations[identity])}"
            )
    subunits, subunit_issues = _collect_subunits(root)
    archetypes, equipment_issues = _collect_equipment_archetypes(root)
    organization_modifiers, technology_issues = _starting_organization_modifiers(root)
    issues.extend(subunit_issues)
    issues.extend(equipment_issues)
    issues.extend(technology_issues)
    computed: dict[int, ComputedTemplate] = {}
    for index, template in enumerate(templates):
        result, computation_issues = _compute_template(
            template, subunits, archetypes, organization_modifiers
        )
        issues.extend(computation_issues)
        if result is not None:
            computed[index] = result
    issues.extend(_validate_computed_rows(audit, templates, row_by_actual, computed))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=300, help="maximum issues to print")
    args = parser.parse_args(argv)
    issues = validate()
    print(f"A-Discord division-template audit: {len(issues)} issue(s)")
    for issue in issues[: args.limit]:
        print(f"- {issue}")
    if len(issues) > args.limit:
        print(f"- ... {len(issues) - args.limit} more")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
