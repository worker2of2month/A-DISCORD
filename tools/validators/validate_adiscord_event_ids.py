"""Validate the central inventory of A-Discord event IDs.

The parser distinguishes top-level event definitions from nested event calls,
ignores comments and quoted strings, and keeps external vanilla namespaces on
an explicit allow-list.  The validator never modifies repository files.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from tools.lib.paths import repository_root


ROOT = repository_root()
REGISTRY_PATH = ROOT / "tools" / "data" / "adiscord_event_ids.json"

EVENT_TYPES = (
    "country_event",
    "news_event",
    "state_event",
    "unit_leader_event",
    "operative_leader_event",
    "character_event",
)
EVENT_BLOCK_RE = re.compile(
    rf"\b({'|'.join(EVENT_TYPES)})\s*=\s*\{{"
)
EVENT_INLINE_RE = re.compile(
    rf"\b({'|'.join(EVENT_TYPES)})\s*=\s*"
    r"([A-Za-z_][A-Za-z0-9_]*\.[0-9]+)\b"
)
ID_ASSIGNMENT_RE = re.compile(
    r"\bid\s*=\s*([A-Za-z_][A-Za-z0-9_]*\.([0-9]+))\b"
)
FULL_ID_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([0-9]+)$")
NAMESPACE_RE = re.compile(
    r"(?m)^\s*add_namespace\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$"
)

SCAN_ROOTS = ("common", "events", "history", "interface")
VALID_STATUSES = {"active", "compatibility", "reserved"}
REQUIRED_FIELDS = {"id", "namespace", "number", "owner", "subsystem", "status"}

COLLAPSE_OWNER = "events/ADISCORD_vorkerland_collapse_events.txt"
REQUIRED_ACTIVE_COLLAPSE_IDS = {
    *(f"ADISCORD_vorkerland_collapse.{number}" for number in range(10, 20)),
    "ADISCORD_vorkerland_collapse.63",
    "ADISCORD_vorkerland_collapse.64",
    "ADISCORD_vorkerland_collapse.83",
    "ADISCORD_vorkerland_collapse.84",
}
PLANNED_RECOVERY_IDS = {
    **{
        f"ADISCORD_vorkerland_phase.{number}":
        "events/ADISCORD_vorkerland_phase_events.txt"
        for number in range(1, 8)
    },
    **{
        f"ADISCORD_vorkerland_dirty_zone.{number}":
        "events/ADISCORD_vorkerland_dirty_zone_events.txt"
        for number in range(1, 4)
    },
    **{
        f"ADISCORD_vorkerland_postwar.{number}":
        "events/ADISCORD_vorkerland_postwar_events.txt"
        for number in range(1, 4)
    },
}


@dataclass(frozen=True)
class EventDefinition:
    event_id: str
    path: str
    line: int
    namespace: str


@dataclass(frozen=True)
class EventReference:
    event_id: str
    path: str
    line: int


@dataclass(frozen=True)
class RegistryEntry:
    event_id: str
    namespace: str
    number: int
    owner: str
    subsystem: str
    status: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _mask_comments_and_strings(source: str) -> str:
    """Replace comments and quoted content while preserving offsets/newlines."""
    masked = list(source)
    index = 0
    in_quote = False
    while index < len(source):
        char = source[index]
        if in_quote:
            if char == "\\" and index + 1 < len(source):
                masked[index] = " "
                masked[index + 1] = " "
                index += 2
                continue
            if char == '"':
                in_quote = False
            if char != "\n":
                masked[index] = " "
            index += 1
            continue
        if char == '"':
            in_quote = True
            masked[index] = " "
            index += 1
            continue
        if char == "#":
            while index < len(source) and source[index] != "\n":
                masked[index] = " "
                index += 1
            continue
        index += 1
    return "".join(masked)


def _brace_depths(masked: str) -> list[int]:
    depth = 0
    depths = [0] * (len(masked) + 1)
    for index, char in enumerate(masked):
        depths[index] = depth
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
    depths[len(masked)] = depth
    return depths


def _closing_brace(masked: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _direct_event_id(
    masked: str,
    depths: list[int],
    opening: int,
    closing: int,
) -> tuple[str, int] | None:
    direct_depth = depths[opening] + 1
    for match in ID_ASSIGNMENT_RE.finditer(masked, opening + 1, closing):
        if depths[match.start()] == direct_depth:
            return match.group(1), match.start(1)
    return None


def _event_files(root: Path) -> list[Path]:
    events = root / "events"
    return sorted(events.glob("*.txt")) if events.exists() else []


def _scan_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for relative_root in SCAN_ROOTS:
        base = root / relative_root
        if not base.exists():
            continue
        files.update(path for path in base.rglob("*.txt") if path.is_file())
        if relative_root == "interface":
            files.update(path for path in base.rglob("*.gui") if path.is_file())
    return sorted(files)


def _inventory_game_files(
    root: Path,
) -> tuple[list[EventDefinition], list[EventReference], dict[str, set[str]], list[str]]:
    definitions: list[EventDefinition] = []
    references: list[EventReference] = []
    namespaces_by_path: dict[str, set[str]] = {}
    issues: list[str] = []
    event_paths = set(_event_files(root))

    for path in _scan_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            source = _read_text(path)
        except UnicodeDecodeError as exc:
            issues.append(f"{relative}: cannot decode as UTF-8: {exc}")
            continue
        masked = _mask_comments_and_strings(source)
        depths = _brace_depths(masked)
        namespaces = set(NAMESPACE_RE.findall(masked))
        if path in event_paths:
            namespaces_by_path[relative] = namespaces

        for match in EVENT_BLOCK_RE.finditer(masked):
            opening = masked.find("{", match.start(), match.end())
            closing = _closing_brace(masked, opening)
            if closing is None:
                continue
            direct_id = _direct_event_id(masked, depths, opening, closing)
            if direct_id is None:
                continue
            event_id, offset = direct_id
            line = source.count("\n", 0, offset) + 1
            namespace = event_id.rsplit(".", 1)[0]
            if path in event_paths and depths[match.start()] == 0:
                definitions.append(
                    EventDefinition(event_id, relative, line, namespace)
                )
            else:
                references.append(EventReference(event_id, relative, line))

        for match in EVENT_INLINE_RE.finditer(masked):
            event_id = match.group(2)
            line = source.count("\n", 0, match.start(2)) + 1
            references.append(EventReference(event_id, relative, line))

    return definitions, references, namespaces_by_path, issues


def _load_registry(
    registry_path: Path,
) -> tuple[dict[str, RegistryEntry], set[str], list[str]]:
    issues: list[str] = []
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, set(), [f"missing event-ID registry: {registry_path.as_posix()}"]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, set(), [f"invalid event-ID registry {registry_path.as_posix()}: {exc}"]

    if not isinstance(raw, dict):
        return {}, set(), ["event-ID registry root must be a JSON object"]
    if raw.get("schema_version") != 1:
        issues.append("event-ID registry schema_version must be 1")

    external_raw = raw.get("external_namespaces", [])
    if not isinstance(external_raw, list) or not all(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
        for value in external_raw
    ):
        issues.append("external_namespaces must contain only namespace strings")
        external_namespaces: set[str] = set()
    else:
        external_namespaces = set(external_raw)
        if len(external_namespaces) != len(external_raw):
            issues.append("external_namespaces contains duplicates")

    events_raw = raw.get("events")
    if not isinstance(events_raw, list):
        issues.append("event-ID registry events must be a list")
        return {}, external_namespaces, issues

    entries: dict[str, RegistryEntry] = {}
    for index, item in enumerate(events_raw, start=1):
        label = f"event-ID registry entry #{index}"
        if not isinstance(item, dict):
            issues.append(f"{label} must be an object")
            continue
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            issues.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
            continue
        event_id = item["id"]
        match = FULL_ID_RE.fullmatch(event_id) if isinstance(event_id, str) else None
        if match is None:
            issues.append(f"{label} has invalid full id: {event_id!r}")
            continue
        namespace = item["namespace"]
        number = item["number"]
        owner = item["owner"]
        subsystem = item["subsystem"]
        status = item["status"]
        valid = True
        if namespace != match.group(1):
            issues.append(
                f"namespace drift for {event_id}: id uses {match.group(1)}, registry uses {namespace!r}"
            )
            valid = False
        if isinstance(number, bool) or not isinstance(number, int) or number != int(match.group(2)):
            issues.append(
                f"number drift for {event_id}: id uses {match.group(2)}, registry uses {number!r}"
            )
            valid = False
        if not isinstance(owner, str) or not owner.startswith("events/") or not owner.endswith(".txt"):
            issues.append(f"{label} has invalid owner path: {owner!r}")
            valid = False
        if not isinstance(subsystem, str) or not subsystem.strip():
            issues.append(f"{label} has an empty subsystem")
            valid = False
        if status not in VALID_STATUSES:
            issues.append(f"{label} has invalid status: {status!r}")
            valid = False
        if event_id in entries:
            issues.append(f"duplicate registry ID: {event_id}")
            continue
        if valid:
            entries[event_id] = RegistryEntry(
                event_id, namespace, number, owner, subsystem, status
            )

    registered_namespaces = {entry.namespace for entry in entries.values()}
    overlap = registered_namespaces & external_namespaces
    if overlap:
        issues.append(
            "namespaces cannot be both owned and external: " + ", ".join(sorted(overlap))
        )
    return entries, external_namespaces, issues


def validate(
    root: Path = ROOT,
    registry_path: Path | None = None,
    *,
    enforce_recovery_contract: bool = True,
) -> list[str]:
    root = Path(root)
    selected_registry = registry_path or root / "tools" / "data" / "adiscord_event_ids.json"
    entries, external_namespaces, issues = _load_registry(selected_registry)
    definitions, references, namespaces_by_path, scan_issues = _inventory_game_files(root)
    issues.extend(scan_issues)

    definitions_by_id: dict[str, list[EventDefinition]] = defaultdict(list)
    for definition in definitions:
        definitions_by_id[definition.event_id].append(definition)

    for event_id, matches in sorted(definitions_by_id.items()):
        if len(matches) > 1:
            locations = ", ".join(f"{item.path}:{item.line}" for item in matches)
            issues.append(f"duplicate definition {event_id}: {locations}")
        entry = entries.get(event_id)
        for definition in matches:
            if entry is None:
                issues.append(
                    f"unregistered event definition {event_id} at {definition.path}:{definition.line}"
                )
                continue
            if entry.owner != definition.path:
                issues.append(
                    f"owner drift for {event_id}: registry={entry.owner}, actual={definition.path}:{definition.line}"
                )
            declared = namespaces_by_path.get(definition.path, set())
            if definition.namespace not in declared:
                issues.append(
                    f"namespace drift for {event_id}: {definition.path} does not declare {definition.namespace}"
                )

    for event_id, entry in sorted(entries.items()):
        matches = definitions_by_id.get(event_id, [])
        if entry.status in {"active", "compatibility"} and not matches:
            issues.append(
                f"status drift for {event_id}: {entry.status} entry has no live definition"
            )
        if entry.status == "reserved" and matches:
            issues.append(
                f"status drift for {event_id}: reserved entry has a live definition"
            )
        owner_path = root / entry.owner
        if entry.status in {"active", "compatibility"} and not owner_path.is_file():
            issues.append(f"missing {entry.status} owner for {event_id}: {entry.owner}")
        if owner_path.is_file():
            declared = namespaces_by_path.get(entry.owner, set())
            if entry.namespace not in declared:
                issues.append(
                    f"namespace drift for {event_id}: owner {entry.owner} does not declare {entry.namespace}"
                )

    seen_reference_locations: set[tuple[str, str, int]] = set()
    for reference in references:
        key = (reference.event_id, reference.path, reference.line)
        if key in seen_reference_locations:
            continue
        seen_reference_locations.add(key)
        namespace = reference.event_id.rsplit(".", 1)[0]
        if namespace in external_namespaces:
            continue
        entry = entries.get(reference.event_id)
        if entry is None:
            issues.append(
                f"unregistered event reference {reference.event_id} at {reference.path}:{reference.line}"
            )

    if enforce_recovery_contract:
        for event_id in sorted(REQUIRED_ACTIVE_COLLAPSE_IDS):
            entry = entries.get(event_id)
            if entry is None:
                issues.append(f"missing required active collapse ID: {event_id}")
            else:
                if entry.status != "active":
                    issues.append(
                        f"status drift for live collapse ID {event_id}: expected active, got {entry.status}"
                    )
                if entry.owner != COLLAPSE_OWNER:
                    issues.append(
                        f"owner drift for live collapse ID {event_id}: expected {COLLAPSE_OWNER}, got {entry.owner}"
                    )
        for event_id, planned_owner in sorted(PLANNED_RECOVERY_IDS.items()):
            entry = entries.get(event_id)
            if entry is None:
                issues.append(f"missing planned recovery ID: {event_id}")
                continue
            if entry.owner != planned_owner:
                issues.append(
                    f"owner drift for planned recovery ID {event_id}: expected {planned_owner}, got {entry.owner}"
                )
            expected_status = "active" if definitions_by_id.get(event_id) else "reserved"
            if entry.status != expected_status:
                issues.append(
                    f"status drift for planned recovery ID {event_id}: expected {expected_status}, got {entry.status}"
                )

    return issues


def main() -> int:
    issues = validate()
    if issues:
        print("A-DISCORD event-ID validation: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("A-DISCORD event-ID validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
