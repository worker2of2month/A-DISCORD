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
    "NOD/main/focuses.txt": "ADISCORD_NOD_focus.txt",
    "NAM/main/focuses.txt": "ADISCORD_NAM_focus.txt",
    "NAM/wartime/focuses.txt": "ADISCORD_NAM_wartime.txt",
    "NAM/postwar/focuses.txt": "ADISCORD_NAM_postwar.txt",
    "NAM/defeated/focuses.txt": "ADISCORD_NAM_defeated.txt",
    "NAM/exile_radical/focuses.txt": "ADISCORD_NAM_exile_radical.txt",
    "NAM/exile_humanist/focuses.txt": "ADISCORD_NAM_exile_humanist.txt",
    "NAM/exile_corporate/focuses.txt": "ADISCORD_NAM_exile_corporate.txt",
    "NAM/south_war/focuses.txt": "ADISCORD_NAM_south_war.txt",
    "SHL/main/focuses.txt": "ADISCORD_SHL_focus.txt",
    "SHL/shared/focuses.txt": "ADISCORD_SHL_shared.txt",
    "SHL/south_war/focuses.txt": "ADISCORD_SHL_south_war.txt",
    "IVN/main/focuses.txt": "ADISCORD_IVN_focus.txt",
    "IVN/legion/focuses.txt": "ADISCORD_IVC_focus.txt",
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
    "Vorkerland/prewar/focuses.txt": "ADISCORD_Vorkerland_prewar.txt",
    "Vorkerland/wkr/focuses.txt": "ADISCORD_Vorkerland_wkr.txt",
    "Vorkerland/vad/focuses.txt": "ADISCORD_Vorkerland_vad.txt",
    "Vorkerland/tva/focuses.txt": "ADISCORD_Vorkerland_tva.txt",
    "Vorkerland/settlement/focuses.txt": "ADISCORD_Vorkerland_settlement.txt",
    "Vorkerland/joint_postwar/focuses.txt": "ADISCORD_Vorkerland_joint_postwar.txt",
    "Vorkerland/world_empire/focuses.txt": "ADISCORD_Vorkerland_world_empire.txt",
    "Vorkerland/worker_confederation/focuses.txt": "ADISCORD_Vorkerland_worker_confederation.txt",
    "Vorkerland/technical_directorate/focuses.txt": "ADISCORD_Vorkerland_technical_directorate.txt",
    "Vorkerland/iba_norvane/focuses.txt": "ADISCORD_Vorkerland_iba_norvane.txt",
    "Vorkerland/zao/focuses.txt": "ADISCORD_Vorkerland_zao.txt",
}
NAM_POSTWAR_SOURCE = "NAM/postwar/focuses.txt"
NAM_POSTWAR_BRANCHES = {
    f"NAM/postwar/{chapter}.txt": f"ADISCORD_NAM_postwar_{chapter}.txt"
    for chapter in ("government", "economy", "armed_forces", "southern_settlement")
}
INCLUDE = re.compile(r"(?m)^# @include ([\w/.-]+)#(\w+)\n")
SECTION = re.compile(r"(?m)^# @section (\w+)\n")
# The humanist exile tree is replaced by the corporate tree at the takeover;
# its completed focuses still open the free-zone and federation decisions.
# WKR copies WRK completion through the prewar tree before loading its own tree.
# Shared history retains preparation rewards without displaying the old branches.
# Restoration programmes keep their unlocks through a later cabinet transition.
# The war for the South swaps each champion into its war tree and back: the
# course trees, every Svetlogorye tree a champion can hold and both war trees
# keep their completions across both swaps.
SHARED_HISTORY_SOURCES = frozenset({
    "VAL/main/focuses.txt",
    "NAM/main/focuses.txt",
    "NAM/wartime/focuses.txt",
    "NAM/postwar/focuses.txt",
    "NAM/defeated/focuses.txt",
    "NAM/exile_humanist/focuses.txt",
    "NAM/exile_radical/focuses.txt",
    "NAM/exile_corporate/focuses.txt",
    "NAM/south_war/focuses.txt",
    "SHL/main/focuses.txt",
    "SHL/south_war/focuses.txt",
    "Vorkerland/prewar/focuses.txt",
    "Vorkerland/joint_postwar/focuses.txt",
})


# Shahrabad also references shared roots from its course sources during the swap.
TREE_SWAPS = {
    "SHL/south_war/focuses.txt": ("SHL_south_war_focus", ("SHL/main/focuses.txt",)),
}


def shown_roots(source: str) -> list[str]:
    """Roots a tree displays: its own unconditioned focuses and its shared references."""
    trees = [row for row in parse_clausewitz(source) if row.key == "focus_tree"]
    if len(trees) != 1:
        raise ValueError("A swapped tree source must contain exactly one focus tree")
    roots = []
    for row in trees[0].value:
        if row.key == "shared_focus" and isinstance(row.value, str):
            roots.append(row.value)
        elif row.key == "focus" and not any(child.key == "prerequisite" for child in row.value):
            roots.append(next(child.value for child in row.value if child.key == "id"))
    return roots


def swap_plan(sources: dict[str, str]) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Carried shared references per source and the allow_branch clause per carried root."""
    carried: dict[str, list[str]] = {}
    clauses: dict[str, str] = {}
    for war, (tree_id, priors) in TREE_SWAPS.items():
        war_roots = shown_roots(sources[war])
        for root in war_roots:
            clauses[root] = f"has_focus_tree = {tree_id}"
        for prior in priors:
            prior_roots = shown_roots(sources[prior])
            for root in prior_roots:
                if clauses.get(root, f"NOT = {{ has_focus_tree = {tree_id} }}") != f"NOT = {{ has_focus_tree = {tree_id} }}":
                    raise ValueError(f"Root {root} is carried in both directions")
                clauses[root] = f"NOT = {{ has_focus_tree = {tree_id} }}"
                if root not in carried.setdefault(war, []):
                    carried[war].append(root)
            prior_carried = carried.setdefault(prior, [])
            for root in war_roots:
                if root not in prior_carried:
                    prior_carried.append(root)
    return carried, clauses


FOCUS_DEFINITION = re.compile(r"(?m)^([ \t]*)(?:shared_)?focus\s*=\s*\{\s*\n\s*id\s*=\s*(\w+)[ \t]*\n")


def source_clauses(sources: dict[str, str], clauses: dict[str, str]) -> dict[str, str]:
    """The swap clause of each source that defines a carried root.

    A focus with its own allow_branch is evaluated separately from its parent,
    so each authored gate in that source must also carry the swap clause.
    """
    owners: dict[str, str] = {}
    for source, text in sources.items():
        for match in FOCUS_DEFINITION.finditer(text):
            if match[2] in clauses:
                if match[2] in owners:
                    raise ValueError(f"Carried root {match[2]} is defined twice")
                owners[match[2]] = source
    missing = sorted(set(clauses) - set(owners))
    if missing:
        raise ValueError(f"Carried roots need an authored definition: {missing}")
    result: dict[str, str] = {}
    for root, source in owners.items():
        if result.setdefault(source, clauses[root]) != clauses[root]:
            raise ValueError(f"{source} defines roots carried in both directions")
    return result


def hide_carried_roots(source: str, clause: str | None) -> str:
    """Guard roots and explicit branch gates while preserving native inheritance."""
    if clause is None:
        return source
    for match in reversed(list(FOCUS_DEFINITION.finditer(source))):
        opening = source.index("{", match.start())
        end = block_end(source, opening)
        body = source[match.end():end]
        indent = match[1] + "\t"
        existing = re.search(r"(?m)^[ \t]*allow_branch\s*=\s*\{", body)
        if existing:
            insert = match.end() + existing.end()
            source = source[:insert] + f" {clause}" + source[insert:]
        elif not re.search(r"(?m)^[ \t]*prerequisite\s*=", body):
            source = source[:match.end()] + f"{indent}allow_branch = {{ {clause} }}\n" + source[match.end():]
    return source


def carry_shared_roots(rendered: str, roots: list[str]) -> str:
    """List carried roots at the end of the tree block of a shared-history output."""
    if not roots:
        return rendered
    tree = re.search(r"(?m)^focus_tree\s*=\s*\{", rendered)
    end = block_end(rendered, rendered.index("{", tree.start()))
    lines = "".join(f"\tshared_focus = {root}\n" for root in roots)
    head = rendered[: end - 1].rstrip() + "\n\n\t# Carried across the war-tree swap; hidden by allow_branch.\n"
    return head + lines + rendered[end - 1:]


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


def render_shared_history_tree(source: str, *, separate_definitions: bool = False) -> str:
    """Keep one definition per old focus so native tree changes retain its completion."""
    trees = [row for row in parse_clausewitz(source) if row.key == "focus_tree"]
    if len(trees) != 1:
        raise ValueError("A shared-history source must contain exactly one focus tree")
    focuses = [row for row in trees[0].value if row.key == "focus"]
    # A tree that already displays another source's shared root also displays
    # that root's shared descendants, so a prerequisite on such a root is local.
    referenced = {row.value for row in trees[0].value if row.key == "shared_focus"}
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
    unknown = set().union(*prerequisites.values()) - definitions.keys() - referenced
    if unknown:
        raise ValueError(f"Shared-history prerequisites leave the source tree: {sorted(unknown)}")
    roots = {name for name, parents in prerequisites.items() if not parents}
    covered = roots | referenced
    while True:
        descendants = {
            name for name, parents in prerequisites.items() if parents & covered
        }
        expanded = covered | descendants
        if expanded == covered:
            break
        covered = expanded
    if covered - referenced != definitions.keys():
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
        if not separate_definitions:
            shared.append("shared_focus = " + source[opening:end])
        cursor = end
    chunks.append(source[cursor:])
    tree = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", "".join(chunks)).rstrip()
    return "\n\n".join([tree, *shared]) + "\n"


def render_native_source(relative: str, source: str) -> str:
    """Compose engine definitions separately from the authored tooling view."""
    if relative in SHARED_HISTORY_SOURCES:
        return render_shared_history_tree(source, separate_definitions=relative == NAM_POSTWAR_SOURCE)
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
    expanded = {source: render_source(source, used_sections) for source in SOURCES}
    carried, clauses = swap_plan(expanded)
    per_source = source_clauses(expanded, clauses)
    hidden = {source: hide_carried_roots(text, per_source.get(source)) for source, text in expanded.items()}
    for source, filename in SOURCES.items():
        header = (
            "# Generated by tools/builders/build_adiscord_focus_trees.py; do not edit.\n"
            f"# Source: focus_trees/{source}\n"
        )
        if source in SHARED_HISTORY_SOURCES:
            header += "# Native layout: shared focus history; tools read the authored focus tree.\n"
        header += "\n"
        native = render_native_source(source, hidden[source])
        native = carry_shared_roots(native, carried.get(source, []))
        outputs[OUTPUT_ROOT / filename] = (header + native).encode("utf-8")
    postwar_includes = INCLUDE.findall((SOURCE_ROOT / NAM_POSTWAR_SOURCE).read_text(encoding="utf-8"))
    for source, filename in NAM_POSTWAR_BRANCHES.items():
        chapter = (SOURCE_ROOT / source).read_text(encoding="utf-8")
        sections = list(SECTION.finditer(chapter))
        if len(sections) != 1 or postwar_includes.count((source, sections[0][1])) != 1:
            raise ValueError(f"Postwar branch must be included once by its tree: {source}")
        body = re.sub(r"(?m)^\tfocus = \{", "shared_focus = {", chapter[sections[0].end():])
        header = f"# Generated by tools/builders/build_adiscord_focus_trees.py; do not edit.\n# Source: focus_trees/{source}\n\n"
        outputs[OUTPUT_ROOT / filename] = (header + body).encode("utf-8")
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
    selected = {SOURCES[args.source]} if args.source else set()
    if args.source == NAM_POSTWAR_SOURCE:
        selected.update(NAM_POSTWAR_BRANCHES.values())
    for path, data in expected_outputs().items():
        if selected and path.name not in selected:
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
