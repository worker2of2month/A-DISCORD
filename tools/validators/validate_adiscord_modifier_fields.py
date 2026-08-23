"""Screen every modifier field this feature writes against the engine's own vocabulary.

Three defects in one day came from script naming fields the engine does not
have. The parser's response to an unknown token is not an error the author can
see: in ``common/ideas/`` it aborts the file and silently discards every
definition after the offending line, which is how a live campaign lost most of
its civil-war national spirits. Nothing in the game log says so.

A name being real is not enough either. ``enemy_army_speed_factor`` is a
genuine field, but only in state scope; written into a country modifier it
parses, loads, displays, and does nothing at all. A silent no-op is worse than
a hard error because it never gets found.

So this validator screens on both axes - does the field exist, and is it valid
in the scope the definition is actually applied in - plus the two structural
shapes that caused the campaign loss, and the icon references that kill a
definition just as dead as a bad field name.

The vocabulary is harvested from the game's own files rather than from
``modifiers_l_english.yml``. The localisation file is not a trustworthy source:
it carries entries for fields the engine does not accept and omits fields it
does, because it is a display table and not a schema. What the engine
demonstrably accepts is what vanilla itself writes, so the harvest reads the
``modifier = { ... }`` blocks and dynamic modifier bodies of the base game.

The harvest is committed to ``tools/data/adiscord_modifier_fields.json`` so the
validator runs without the game installed. Regenerate it with ``--refresh``
when the game updates; the run is idempotent and reports whether anything moved.

Usage:
    python -B tools/validate_adiscord_modifier_fields.py
    python -B tools/validate_adiscord_modifier_fields.py --refresh
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPOSITORY_ROOT / "tools" / "data" / "adiscord_modifier_fields.json"
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")

# Icon prefixes that a modifier or idea definition can legally point at. The
# snapshot only carries base-game sprites under these prefixes; sprites this
# mod defines live in ``interface/`` and are read live, so a sprite added here
# never needs a refresh to be recognised.
ICON_PREFIXES = ("GFX_idea_", "GFX_modifiers_", "GFX_goal_", "GFX_decision_")


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------
# Everything this feature owns that can name a modifier field. Both dynamic
# modifier files matter: the collapse file carries the state-scope district
# modifiers and the new war-economy trade-offs, and the legitimacy file carries
# the claim-strength modifier the phase layer applies every month.
COVERED_GLOBS = (
    "common/dynamic_modifiers/ADISCORD_vorkerland_*.txt",
    "common/ideas/ADISCORD_vorkerland_collapse_ideas.txt",
    "common/ideas/ADISCORD_vorkerland_focus_expansion_ideas.txt",
)

# Scripted effects that may write the variables our dynamic modifiers read. A
# modifier pointing at a variable nobody writes is the same silent zero as a
# misspelt field, so the variable names are screened too.
VARIABLE_WRITER_GLOBS = (
    "common/scripted_effects/ADISCORD_*.txt",
    "common/on_actions/*.txt",
    "events/ADISCORD_*.txt",
)


# ---------------------------------------------------------------------------
# Scope declarations
# ---------------------------------------------------------------------------
# A dynamic modifier's legal vocabulary depends on what it is attached to, and
# nothing inside the definition records that. Each one is declared here with
# the reason it is that scope, and the validator asserts the declarations cover
# exactly the definitions present - so a new modifier cannot be added without
# stating where it is applied.
COUNTRY = "country"
STATE = "state"

DYNAMIC_MODIFIER_SCOPES: dict[str, tuple[str, str]] = {
    "ADISCORD_vorkerland_dirty_state": (
        STATE,
        "applied per state by the collapse dirty-state effects to mark districts "
        "wrecked in the fighting",
    ),
    "ADISCORD_vorkerland_regional_autonomy": (
        STATE,
        "applied per state to districts administered locally rather than from the "
        "centre",
    ),
    "ADISCORD_vorkerland_macri_volunteer_corps": (
        COUNTRY,
        "applied to PIV as a country by the collapse effects when Afrela commits "
        "the volunteer corps",
    ),
    "ADISCORD_vorkerland_civil_war_attrition": (
        STATE,
        "applied to the seventeen named central-front states by the phase effects, "
        "not to the claimants, so its combat fields resolve on the ground fought over",
    ),
    "ADISCORD_vorkerland_civil_war_exhaustion": (
        COUNTRY,
        "applied to a claimant country as the war runs long",
    ),
    "ADISCORD_vorkerland_legitimacy_dynamic": (
        COUNTRY,
        "applied to each claimant country by the phase layer to express the "
        "strength of its claim",
    ),
    "ADISCORD_vorkerland_wkr_war_economy": (
        COUNTRY,
        "applied to WKR by the war-economy branch head focus",
    ),
    "ADISCORD_vorkerland_vad_war_economy": (
        COUNTRY,
        "applied to VAD by the war-economy branch head focus",
    ),
    "ADISCORD_vorkerland_tva_war_economy": (
        COUNTRY,
        "applied to TVA by the war-economy branch head focus",
    ),
    "ADISCORD_vorkerland_wkr_doctrine": (
        COUNTRY,
        "applied to WKR when it publishes a variant programme, then rewritten "
        "monthly from legitimacy",
    ),
    "ADISCORD_vorkerland_vad_doctrine": (
        COUNTRY,
        "applied to VAD when it publishes a variant programme, then rewritten "
        "monthly from legitimacy",
    ),
    "ADISCORD_vorkerland_tva_doctrine": (
        COUNTRY,
        "applied to TVA when it publishes a variant programme, then rewritten "
        "monthly from legitimacy",
    ),
}


# ---------------------------------------------------------------------------
# Engine patterns
# ---------------------------------------------------------------------------
# Fields the engine synthesises rather than declares, so they cannot appear in
# a harvest of vanilla's files. Each carries the reason it is legitimate; this
# is deliberately not a bare allowlist, because an undocumented exemption is
# indistinguishable from the defect it hides.
def _ideology_pattern_fields(ideologies: set[str]) -> dict[str, str]:
    """Per-ideology fields the engine generates from ``common/ideologies/``."""
    generated: dict[str, str] = {}
    for ideology in sorted(ideologies):
        generated[f"{ideology}_drift"] = (
            f"engine generates <ideology>_drift for every ideology; this mod replaces "
            f"vanilla's four ideologies with its own, so '{ideology}' cannot appear in "
            f"a harvest of base-game files"
        )
        generated[f"{ideology}_acceptance"] = (
            f"engine generates <ideology>_acceptance for every ideology; '{ideology}' is "
            f"declared in this mod's common/ideologies/ and not in the base game"
        )
    return generated


# Structural tokens that sit inside a modifier-bearing block without being
# modifier fields. Harvesting would otherwise treat them as engine vocabulary
# and then fail to flag them when they appear somewhere they do not belong.
STRUCTURAL_TOKENS = frozenset(
    {
        "enable", "remove_trigger", "icon", "attacker_modifier", "defender_modifier",
        "targeted_modifier", "tag", "factor", "add", "value", "var", "modifier",
        "picture", "allowed", "allowed_civil_war", "removal_cost", "ai_will_do",
        "cancel_if_invalid", "available", "visible", "trigger", "name", "always",
        "research_bonus", "equipment_bonus", "targeted_modifiers", "rule",
        "traits", "cost", "level", "days", "id", "on_add", "on_remove",
        "scaled_value", "is_good", "use_for_ai", "cancel_if_not_visible",
        "law", "default", "allowed_to_remove", "on_add_effect",
    }
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
FIELD_ASSIGNMENT = re.compile(r"(?m)^[ \t]*([a-z][a-z0-9_]*)[ \t]*=[ \t]*(-?[\d.]+|[A-Za-z_][\w.]*)[ \t]*(?:#.*)?$")


def _strip_comments(text: str) -> str:
    return re.sub(r"(?m)#.*$", "", text)


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced braces")


def keyword_blocks(text: str, keyword: str) -> list[str]:
    """Bodies of every ``<keyword> = { ... }`` block, at any nesting depth."""
    bodies = []
    for match in re.finditer(rf"(?m)^[ \t]*{keyword}[ \t]*=[ \t]*\{{", text):
        start = text.index("{", match.start())
        bodies.append(text[start + 1 : _matching_brace(text, start)])
    return bodies


def top_level_definitions(text: str) -> dict[str, str]:
    """Bodies of every ``Name = { ... }`` declared at column zero."""
    definitions = {}
    for match in re.finditer(r"(?m)^([A-Za-z_]\w*)[ \t]*=[ \t]*\{", text):
        start = text.index("{", match.start())
        definitions[match.group(1)] = text[start + 1 : _matching_brace(text, start)]
    return definitions


def flatten(body: str) -> str:
    """Drop every nested block so only the body's own assignments remain."""
    previous = None
    while previous != body:
        previous = body
        body = re.sub(r"\{[^{}]*\}", "", body)
    return body


def scalar_fields(body: str) -> set[str]:
    return {
        match.group(1)
        for match in FIELD_ASSIGNMENT.finditer(body)
        if match.group(1) not in STRUCTURAL_TOKENS
    }


# ---------------------------------------------------------------------------
# Harvest
# ---------------------------------------------------------------------------
def harvest_from_game(game_root: Path) -> dict[str, list[str]]:
    """Read the engine's accepted vocabulary out of the base game's own files.

    Two sets come back. ``existence`` is every field vanilla writes anywhere,
    which answers "is this a real name". ``country`` is every field vanilla
    writes inside ``common/ideas/``, which answers "is it valid on a country" -
    an idea is always applied to a country, so anything vanilla puts in one is
    country-legal by demonstration. A field in ``existence`` but not in
    ``country`` is real but unproven outside state scope, which is precisely
    the ``enemy_army_speed_factor`` shape.
    """
    common = game_root / "common"
    if not common.is_dir():
        raise SystemExit(f"base game not found for refresh: {common}")

    existence: set[str] = set()
    country: set[str] = set()

    for path in sorted(common.rglob("*.txt")):
        try:
            text = _strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue

        for body in keyword_blocks(text, "modifier"):
            fields = scalar_fields(flatten(body))
            existence |= fields
            if path.parent.name == "ideas" or "ideas" in path.parts:
                country |= fields

        if path.parent.name == "dynamic_modifiers":
            for body in top_level_definitions(text).values():
                existence |= scalar_fields(flatten(body))

    sprites: set[str] = set()
    for path in sorted((game_root / "interface").rglob("*.gfx")):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        sprites |= {
            name
            for name in re.findall(r'name\s*=\s*"?(GFX_[\w]+)"?', text)
            if name.startswith(ICON_PREFIXES)
        }

    return {
        "existence": sorted(existence),
        "country": sorted(country),
        "sprites": sorted(sprites),
    }


def load_snapshot() -> dict[str, set[str]]:
    if not SNAPSHOT_PATH.is_file():
        raise SystemExit(
            f"missing harvest snapshot {SNAPSHOT_PATH.relative_to(REPOSITORY_ROOT)}; "
            "regenerate it with --refresh"
        )
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {key: set(raw[key]) for key in ("existence", "country", "sprites")}


def refresh_snapshot() -> int:
    harvested = harvest_from_game(BASE_GAME)
    payload = {
        "_comment": (
            "Engine modifier vocabulary harvested from the base game by "
            "tools/validators/validate_adiscord_modifier_fields.py --refresh. "
            "Do not hand-edit; regenerate instead."
        ),
        "_source": str(BASE_GAME),
        **harvested,
    }
    serialised = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    previous = SNAPSHOT_PATH.read_text(encoding="utf-8") if SNAPSHOT_PATH.is_file() else ""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(serialised, encoding="utf-8", newline="\n")

    changed = serialised != previous
    print(
        f"harvest: {len(harvested['existence'])} fields, "
        f"{len(harvested['country'])} country-attested, "
        f"{len(harvested['sprites'])} icon sprites"
    )
    print("snapshot changed" if changed else "snapshot unchanged (idempotent)")
    return 0


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def mod_ideologies(root: Path) -> set[str]:
    ideologies: set[str] = set()
    for path in sorted((root / "common" / "ideologies").glob("*.txt")):
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for body in keyword_blocks(text, "ideologies"):
            ideologies |= set(re.findall(r"(?m)^[ \t]*(\w+)[ \t]*=[ \t]*\{", body))
    return ideologies


def mod_sprites(root: Path) -> set[str]:
    sprites: set[str] = set()
    for path in sorted((root / "interface").rglob("*.gfx")):
        sprites |= set(re.findall(r'name\s*=\s*"?(GFX_[\w]+)"?', path.read_text(encoding="utf-8", errors="replace")))
    return sprites


def written_variables(root: Path) -> set[str]:
    """Variable names any owned script writes, in any of the writing effects."""
    names: set[str] = set()
    writers = re.compile(
        r"(?:set_variable|add_to_variable|subtract_from_variable|multiply_variable"
        r"|divide_variable|clamp_variable|set_temp_variable|round_variable)"
        r"\s*=\s*\{\s*(?:var\s*=\s*)?([\w.@]+)"
    )
    for pattern in VARIABLE_WRITER_GLOBS:
        for path in sorted(root.glob(pattern)):
            text = _strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))
            names |= {match.group(1) for match in writers.finditer(text)}
    return names


def localisation_keys(root: Path) -> set[str]:
    """Every English localisation key, for fields that name one rather than a value."""
    keys: set[str] = set()
    for path in sorted((root / "localisation" / "english").rglob("*.yml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        keys |= set(re.findall(r"(?m)^\s*([\w.\-]+):\d*\s+\"", text))
    return keys


def covered_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in COVERED_GLOBS:
        paths.extend(sorted(root.glob(pattern)))
    if not paths:
        raise SystemExit("no covered files matched; the coverage globs are stale")
    return paths


def _check_structural_shapes(path: Path, name: str, body: str, failures: list[str]) -> None:
    """The two shapes that cost a live campaign, both cheap to detect.

    A dynamic modifier declared ``attacker_modifier = yes`` is a combat modifier
    the engine resolves per battle. It takes neither ``enable`` nor
    ``remove_trigger``; vanilla's ``unplanned_offensive`` is the only correct
    example of the shape. An ``enable`` inside a ``targeted_modifier`` block is
    the defect that aborted the ideas file and discarded the civil-war spirits.
    """
    where = f"{path.name}: {name}"
    flat = flatten(body)

    for combat_kind in ("attacker_modifier", "defender_modifier"):
        if not re.search(rf"(?m)^[ \t]*{combat_kind}[ \t]*=[ \t]*yes", flat):
            continue
        for forbidden in ("enable", "remove_trigger"):
            if re.search(rf"\b{forbidden}\s*=", flat):
                failures.append(
                    f"{where}: '{combat_kind} = yes' takes no '{forbidden}' block. "
                    "The engine resolves combat modifiers per battle and ignores "
                    "the gate, so the modifier applies unconditionally. See vanilla "
                    "unplanned_offensive for the only correct shape."
                )

    # Written inline as often as not, so this cannot anchor to line starts.
    for targeted in re.finditer(r"targeted_modifier\s*=\s*\{", body):
        start = body.index("{", targeted.start())
        if re.search(r"\benable\s*=", body[start + 1 : _matching_brace(body, start)]):
            failures.append(
                f"{where}: 'enable' is not accepted inside a 'targeted_modifier' "
                "block. This is the shape that aborted common/ideas/ parsing and "
                "silently discarded every definition after it."
            )


def validate(root: Path = REPOSITORY_ROOT) -> list[str]:
    snapshot = load_snapshot()
    existence = snapshot["existence"]
    country = snapshot["country"]
    sprites = snapshot["sprites"] | mod_sprites(root)

    patterns = _ideology_pattern_fields(mod_ideologies(root))
    variables = written_variables(root)
    loc_keys = localisation_keys(root)
    failures: list[str] = []

    declared = set(DYNAMIC_MODIFIER_SCOPES)
    seen_dynamic: set[str] = set()

    for path in covered_files(root):
        relative = path.relative_to(root).as_posix()
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        is_dynamic = path.parent.name == "dynamic_modifiers"

        # (name, body, scope) for every definition that can carry fields.
        units: list[tuple[str, str, str]] = []
        if is_dynamic:
            for name, body in top_level_definitions(text).items():
                seen_dynamic.add(name)
                scope = DYNAMIC_MODIFIER_SCOPES.get(name, (None, ""))[0]
                if scope is None:
                    failures.append(
                        f"{relative}: dynamic modifier '{name}' has no scope "
                        "declaration in DYNAMIC_MODIFIER_SCOPES. A field's validity "
                        "depends on what the modifier is attached to, so the scope "
                        "has to be stated before the fields can be screened."
                    )
                    scope = COUNTRY
                units.append((name, body, scope))
                _check_structural_shapes(path, name, body, failures)
        else:
            # Ideas are always applied to a country.
            for match in re.finditer(r"(?m)^\t\t([A-Za-z_]\w*)[ \t]*=[ \t]*\{", text):
                start = text.index("{", match.start())
                body = text[start + 1 : _matching_brace(text, start)]
                units.append((match.group(1), body, COUNTRY))
                _check_structural_shapes(path, match.group(1), body, failures)

        for name, body, scope in units:
            if is_dynamic:
                assignments = list(FIELD_ASSIGNMENT.finditer(flatten(body)))
            else:
                assignments = [
                    assignment
                    for modifier_body in keyword_blocks(body, "modifier")
                    for assignment in FIELD_ASSIGNMENT.finditer(flatten(modifier_body))
                ]

            for assignment in assignments:
                field, value = assignment.group(1), assignment.group(2)
                if field in STRUCTURAL_TOKENS:
                    continue
                where = f"{relative}: {name}: '{field}'"

                if field not in existence and field not in patterns:
                    failures.append(
                        f"{where} is not a modifier field the engine accepts. It "
                        "appears nowhere in the base game's own modifier blocks. An "
                        "unknown token aborts the file and discards everything after it."
                    )
                    continue

                if scope == COUNTRY and field not in country and field not in patterns:
                    failures.append(
                        f"{where} is a real field but is not attested in country "
                        f"scope, and '{name}' is applied to a country "
                        f"({DYNAMIC_MODIFIER_SCOPES.get(name, ('', 'an idea'))[1]}). "
                        "A state-scope field on a country parses and then does "
                        "nothing, which is worse than a hard error."
                    )

                # custom_modifier_tooltip names a localisation key rather than a
                # value, so it is screened against the loc corpus instead.
                if field == "custom_modifier_tooltip":
                    if value not in loc_keys:
                        failures.append(
                            f"{where} names localisation key '{value}', which is not "
                            "defined in any English localisation file. The tooltip line "
                            "renders as the raw key."
                        )
                    continue

                # A variable-valued field that nothing writes reads as zero.
                if not re.fullmatch(r"-?[\d.]+", value) and value not in {"yes", "no"}:
                    if value not in variables:
                        failures.append(
                            f"{where} reads variable '{value}', which no owned script "
                            "writes. An unwritten variable evaluates to zero, so the "
                            "modifier loads and silently does nothing."
                        )

            for icon in re.findall(r"(?m)^[ \t]*(?:icon|picture)[ \t]*=[ \t]*(GFX_\w+)", body):
                if icon not in sprites:
                    failures.append(
                        f"{relative}: {name}: icon '{icon}' resolves to no sprite in "
                        "the base game or this mod. A bad icon reference kills the "
                        "definition as surely as a bad field name."
                    )

    stale = declared - seen_dynamic
    if stale:
        failures.append(
            "DYNAMIC_MODIFIER_SCOPES declares modifiers that no longer exist: "
            + ", ".join(sorted(stale))
        )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-harvest the engine vocabulary from the base game install",
    )
    arguments = parser.parse_args(argv)

    if arguments.refresh:
        return refresh_snapshot()

    failures = validate()
    if failures:
        print(f"validation failed with {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    snapshot = load_snapshot()
    print(
        f"modifier fields: screened against {len(snapshot['existence'])} engine field "
        f"names ({len(snapshot['country'])} attested in country scope)"
    )
    print(f"covered files: {len(covered_files(REPOSITORY_ROOT))}")
    print(f"dynamic modifiers with declared scope: {len(DYNAMIC_MODIFIER_SCOPES)}")
    print("validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
