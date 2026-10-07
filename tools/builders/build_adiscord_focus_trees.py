"""Assemble authored focus sources into flat native national_focus files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from tools.lib.paths import repository_root
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = repository_root()
SOURCE_ROOT = ROOT / "focus_trees"
OUTPUT_ROOT = ROOT / "common/national_focus"
SOURCES = {
    "NAM/main/focuses.txt": "ADISCORD_NAM_focus.txt",
    "SHL/main/focuses.txt": "ADISCORD_SHL_focus.txt",
    "IVN/main/focuses.txt": "ADISCORD_IVN_focus.txt",
    "RUS/main/focuses.txt": "ADISCORD_national_focus_RUS.txt",
    "VAL/main/focuses.txt": "ADISCORD_national_focus_VAL.txt",
    "VAL/new_world/focuses.txt": "ADISCORD_VAL_new_world.txt",
    "shared/bookmark/focuses.txt": "ADISCORD_national_focus_bookmark.txt",
    "shared/generic/focuses.txt": "generic.txt",
    "STP/preparation/focuses.txt": "ADISCORD_STP_preparation.txt",
    "STP/civil_war/focuses.txt": "ADISCORD_STP_civil_war.txt",
    "STP/postwar/focuses.txt": "ADISCORD_STP_exile_return.txt",
    "VAL/defeated/focuses.txt": "ADISCORD_VAL_defeated.txt",
    "VAL/administration/focuses.txt": "ADISCORD_VAL_administration.txt",
    "Vorkerland/civil_war/focuses.txt": "ADISCORD_Vorkerland_civil_war.txt",
    "Vorkerland/iba_norvane/focuses.txt": "ADISCORD_Vorkerland_iba_norvane.txt",
    "Vorkerland/zao/focuses.txt": "ADISCORD_Vorkerland_zao.txt",
}
INCLUDE = re.compile(r"(?m)^# @include ([\w/.-]+)#(\w+)\n")
SECTION = re.compile(r"(?m)^# @section (\w+)\n")
SHARED_HISTORY_SOURCES = frozenset({"VAL/main/focuses.txt"})


def block_end(source: str, opening: int) -> int:
    """Locate a native block without treating quoted payloads or comments as braces."""
    depth = 0
    quoted = False
    escaped = False
    comment = False
    for index in range(opening, len(source)):
        character = source[index]
        if comment:
            comment = character != "\n"
            continue
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == "#":
            comment = True
        elif character == '"':
            quoted = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError("Unterminated focus block")


def render_shared_history_tree(source: str) -> str:
    """Keep one definition per old focus so native tree changes retain its completion."""
    trees = [row for row in parse_clausewitz(source) if row.key == "focus_tree"]
    if len(trees) != 1:
        raise ValueError("A shared-history source must contain exactly one focus tree")
    focuses = [row for row in trees[0].value if row.key == "focus"]
    definitions = {}
    prerequisites = {}
    for focus in focuses:
        ids = [row.value for row in focus.value if row.key == "id"]
        if len(ids) != 1 or not isinstance(ids[0], str) or ids[0] in definitions:
            raise ValueError("Shared-history focuses need unique scalar IDs")
        focus_id = ids[0]
        definitions[focus_id] = focus
        prerequisites[focus_id] = {
            child.value
            for row in focus.value if row.key == "prerequisite"
            for child in row.value if child.key == "focus"
        }
    unknown = set().union(*prerequisites.values()) - definitions.keys()
    if unknown:
        raise ValueError(f"Shared-history prerequisites leave the source tree: {sorted(unknown)}")
    roots = {name for name, parents in prerequisites.items() if not parents}
    covered = set(roots)
    while True:
        descendants = {
            name for name, parents in prerequisites.items() if parents & covered
        }
        expanded = covered | descendants
        if expanded == covered:
            break
        covered = expanded
    if covered != definitions.keys():
        raise ValueError(f"Shared-history roots cannot reach: {sorted(definitions.keys() - covered)}")

    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    chunks = []
    shared = []
    cursor = 0
    for focus_id, focus in definitions.items():
        start = offsets[focus.line - 1]
        match = re.match(r"[ \t]*focus\s*=\s*\{", source[start:])
        if match is None:
            raise ValueError(f"Cannot locate authored focus {focus_id}")
        opening = start + match.end() - 1
        end = block_end(source, opening)
        chunks.append(source[cursor:start])
        if focus_id in roots:
            chunks.append(f"\tshared_focus = {focus_id}")
        # The original body is retained byte for byte, including quoted unit payloads.
        shared.append("shared_focus = " + source[opening:end])
        cursor = end
    chunks.append(source[cursor:])
    tree = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", "".join(chunks)).rstrip()
    return tree + "\n\n" + "\n\n".join(shared) + "\n"


def render_native_source(relative: str, source: str) -> str:
    """Compose engine definitions separately from the authored tooling view."""
    if relative in SHARED_HISTORY_SOURCES:
        return render_shared_history_tree(source)
    return source


def render_source(
    relative: str, used_sections: set[tuple[Path, str]] | None = None
) -> str:
    """Expand named fragments without changing their native scope or order."""
    source = (SOURCE_ROOT / relative).read_text(encoding="utf-8")

    def expand(match: re.Match[str]) -> str:
        path = (SOURCE_ROOT / match[1]).resolve()
        if not path.is_relative_to(SOURCE_ROOT.resolve()):
            raise ValueError(f"Include escapes focus sources: {match[1]}")
        text = path.read_text(encoding="utf-8")
        sections = list(SECTION.finditer(text))
        selected = [i for i, item in enumerate(sections) if item[1] == match[2]]
        if len(selected) != 1:
            raise ValueError(f"Expected one section {match[0].strip()}")
        if used_sections is not None:
            key = (path, match[2])
            if key in used_sections:
                raise ValueError(f"Focus section included more than once: {key}")
            used_sections.add(key)
        index = selected[0]
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        fragment = text[sections[index].end() : end]
        if "# @include" in fragment:
            raise ValueError("Focus fragments cannot include other fragments")
        return fragment

    rendered = INCLUDE.sub(expand, source)
    if "# @include" in rendered:
        raise ValueError(f"Malformed include in {relative}")
    if rendered.startswith("\ufeff"):
        raise ValueError(f"Gameplay source has a BOM: {relative}")
    return rendered


def expected_outputs() -> dict[Path, bytes]:
    outputs = {}
    used_sections: set[tuple[Path, str]] = set()
    for source, filename in SOURCES.items():
        header = (
            "# Generated by tools/builders/build_adiscord_focus_trees.py; do not edit.\n"
            f"# Source: focus_trees/{source}\n"
        )
        if source in SHARED_HISTORY_SOURCES:
            header += "# Native layout: shared focus history; tools read the authored focus tree.\n"
        header += "\n"
        outputs[OUTPUT_ROOT / filename] = (
            header + render_native_source(source, render_source(source, used_sections))
        ).encode("utf-8")
    for path in SOURCE_ROOT.rglob("*.txt"):
        text = path.read_text(encoding="utf-8")
        if text.startswith("\ufeff"):
            raise ValueError(f"Gameplay source has a BOM: {path}")
        sections = list(SECTION.finditer(text))
        if not sections and path.relative_to(SOURCE_ROOT).as_posix() not in SOURCES:
            raise ValueError(f"Unregistered focus source: {path}")
        for section in sections:
            if (path.resolve(), section[1]) not in used_sections:
                raise ValueError(f"Unused focus section: {path}#{section[1]}")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    parser.add_argument("--source", choices=tuple(SOURCES), help="Check or write only this authored tree")
    args = parser.parse_args()
    stale = []
    for path, data in expected_outputs().items():
        if args.source and path.name != SOURCES[args.source]:
            continue
        if path.is_file() and path.read_bytes() == data:
            continue
        stale.append(path)
        if args.apply:
            path.write_bytes(data)
        print(f"{'WROTE' if args.apply else 'STALE'}: {path.relative_to(ROOT)}")
    if not stale:
        print("Focus tree outputs are current.")
    return int(bool(stale) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
