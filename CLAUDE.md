# A-Discord - Claude Code context

Hearts of Iron IV 1.19 total conversion "Abyss of Discord", GitHub repository
`worker2of2month/A-DISCORD`, branch `main`. Other people work in this checkout:
keep the code style, performance contracts and file grouping intact.

The binding repository rules are in AGENTS.md; they apply to every session,
subagent and teammate:

@AGENTS.md

## Repository map

- `common/`, `events/`, `history/`, `map/`, `interface/`, `gfx/`, `localisation/` -
  files loaded by the game. `localisation/russian` is primary, `english` and
  `replace` follow it.
- `focus_trees/<TAG>/<branch>/focuses.txt` - focus sources. The game files in
  `common/national_focus/` are generated from them; never edit those directly.
- `tools/builders/` - generators (`--check` by default, `--apply` to write).
- `tools/validators/` - static validators; `tools/validate_tc.py` is the full gate.
- `tools/tests/` - unittest suite; `tools/lib/` - shared helpers and manifests.
- `tools/data/generated_output_owners.json` - which generator owns which output.
- `docs/lore/` - world and country dossiers (may lag behind the code; the code
  and localisation win when they disagree).
- `docs/development/` - focus-effects, performance, scripted-peace testing and
  language guides. `docs/superpowers/` - specs, plans and reports.

## Commands

Run from the repository root; Python always with `-B`.

```powershell
python -B -m tools.builders.build_adiscord_focus_trees --check
python -B -m tools.builders.build_adiscord_focus_trees --apply
python -B -m unittest tools.tests.<test_module> -v
python -B -m unittest discover -s tools/tests -p "test_*.py"
python -B tools/validate_tc.py --limit 300
git diff --check
```

Static checks do not prove runtime behaviour; say so when the game was not restarted.

## Agent teams and subagents

Project agent definitions live in `.claude/agents/`; the authoring template
and team conventions are in `docs/development/agent-teams.md`.

- Give every teammate a disjoint set of files. Shared hubs - one country's
  events, decisions, scripted effects/triggers, localisation file, and the
  generated focus output - have exactly one owner per team.
- Only the lead runs `--apply` builders, the full test suite and
  `validate_tc.py`; teammates run the focused test for their own area.
- Teammates never commit, push, reset, checkout or delete files. The lead
  reviews the combined diff and stages explicit paths only on the user's request.
- Report results with file paths and the checks actually run, including failures.
