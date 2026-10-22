# Agent teams and subagents

Claude Code agent teams are enabled per developer, not for the whole repository:
put the flag in the ignored `.claude/settings.local.json`.

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Every teammate is a full session: it loads `CLAUDE.md`, which imports
`AGENTS.md`. Repository rules therefore never need to be repeated in agent
definitions; an agent file describes only its role, area and checks.

## Agent definitions

Shared roles live in `.claude/agents/<name>.md`, one file per role. Name roles
by responsibility (`stp-content`, `localisation-ru`, `focus-builder`), not by a
single task. Personal experiments belong in `~/.claude/agents/`.

```markdown
---
name: <kebab-case-role>
description: <when the lead should use this role; one or two sentences>
tools: Read, Grep, Glob, Edit, Write, PowerShell
model: inherit
---

Role: <what this agent is responsible for>.

Owned files:
- <explicit paths or globs this role may edit>

Read-only context:
- <files and docs to read before working, e.g. docs/lore/..., focus-effects.md>

Checks before reporting:
- <focused test or validator for this area>

Report: changed paths, checks run with their result, open questions.
```

`tools` is optional; omit it to inherit every tool. Restrict a reviewer or
lore auditor to `Read, Grep, Glob` so it cannot edit files. MCP tools are
listed by their full names, as `blender-modeler` does with `mcp__blender__*`;
the MCP server itself is configured per developer and must be running.

## Splitting work

- One owner per file. In this mod the conflict hubs are a country's
  `events/ADISCORD_<TAG>_events.txt`, its decisions and decision categories,
  its scripted effects/triggers, `localisation/russian/ADISCORD_<TAG>_l_russian.yml`
  and the generated `common/national_focus/` output. For models, the hub is
  the live Blender scene: one modeller at a time.
- Prefer splitting by country or by engine data type within one country, not
  by individual focus.
- Focus sources may be edited by several roles only in different
  `focus_trees/` files; the lead runs the focus builder once afterwards.
- The lead integrates: `--apply` builders, the full test suite,
  `python -B tools/validate_tc.py --limit 300`, `git diff --check`, review of
  the combined diff, and any commit on the user's request.
- Teammates do not commit, push, reset, checkout or delete files.

Start with two or three teammates; each one uses tokens like a separate session.
