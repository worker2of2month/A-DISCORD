# A-Discord Land Technology Tree Graph Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align horizontal technology icons with the year axis and replace the
linear infantry/armour rails with compact, semantic fork-and-synthesis graphs.

**Architecture:** `tools/builders/build_adiscord_technology_system.py` remains
the source of truth for technology graphs, coordinates, generated GUI, and
generated technology files. Orientation is explicit per folder; graph topology
is explicit per programme and validated before rendering.

**Tech Stack:** Python 3 generator and unittest contracts; HOI4 Clausewitz
technology and GUI script.

## Global Constraints

- Preserve unrelated dirty work and do not commit without a new explicit user
  request.
- Do not hand-edit generated technology or GUI output.
- TFR and Darkest Hour are pattern references only; copy no content or assets.
- Preserve ASCII technical IDs and UTF-8 BOM in Russian localisation.
- Static checks do not replace a fresh HOI4 restart and campaign UI smoke test.

---

### Task 1: Executable orientation and graph contracts

**Files:**
- Modify: `tools/tests/test_build_adiscord_technology_system.py`

**Interfaces:**
- Consumes: `BRANCH_GRAPHS`, `render_technology()`, and `render_folder()` from
  the generator.
- Produces: regression tests for horizontal coordinate orientation, GUI grid
  direction, branch forks, lane counts, synthesis dependencies, and armour
  folder parity.

- [ ] Add a test rendering a horizontal technology and assert the hand-derived
  contract `x = lane`, `y = year_index * 3`.
- [ ] Add a test rendering `infantry_folder` and assert every generated grid is
  `LEFT`, while a vertical folder remains `UP`.
- [ ] Add literal topology expectations for the seven named main land branches:
  at least three lanes, at least one fork, and at least one multi-parent node or
  the explicit combat-armour XOR.
- [ ] Run the focused tests and confirm they fail on the current transposed,
  linear output.

### Task 2: Orientation root-cause fix

**Files:**
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Generated: `common/technologies/ADISCORD_infantry.txt`
- Generated: `common/technologies/ADISCORD_armor.txt`
- Generated: `interface/countrytechtreeview.gui`

**Interfaces:**
- Consumes: `HORIZONTAL_FOLDERS`, `YEAR_TO_Y`, `GRID_SLOT`, and per-branch lane
  data.
- Produces: `folder_grid_format(folder) -> str` and
  `technology_grid_position(branch, index) -> tuple[int, int]` used by both
  technology and GUI rendering.

- [ ] Implement explicit orientation helpers returning `LEFT` for horizontal
  folders and `UP` for vertical folders.
- [ ] Keep lanes in technology `position.x`; put the chronological slot in
  `position.y`, multiplying horizontal time by three.
- [ ] Render each grid with the matching format and derive horizontal year
  labels from the same chronological-slot calculation.
- [ ] Run the orientation tests and confirm they pass without changing graph
  topology yet.

### Task 3: Semantic land programme graphs

**Files:**
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Generated: `common/technologies/ADISCORD_infantry.txt`
- Generated: `common/technologies/ADISCORD_armor.txt`
- Generated: `interface/countrytechtreeview.gui`

**Interfaces:**
- Consumes: `make_graph()` and current compact 16-node land programmes.
- Produces: explicit 16-node graph builders selected by `graph_for_branch()`.

- [ ] Replace the unused 20-node infantry graph definitions with 16-node
  semantic graphs matching the design specification.
- [ ] Add 16-node recon-, combat-, and heavy-armour graphs; preserve the current
  combat-armour permanent XOR group at indices 12 and 13.
- [ ] Bind the seven graphs in `graph_for_branch()` and keep all short side
  programmes linear.
- [ ] Run topology tests and the existing starting-profile/XOR tests.

### Task 4: Regeneration and idempotence

**Files:**
- Generated outputs owned by
  `tools/builders/build_adiscord_technology_system.py`.

**Interfaces:**
- Consumes: the updated generator.
- Produces: synchronized technology, GUI, localisation, GFX, scripted-effect,
  AI-strategy, and manifest outputs.

- [ ] Run `python -B tools/build_adiscord_technology_system.py --check` and
  confirm it reports pending generated changes.
- [ ] Run the explicit `--apply` mode.
- [ ] Hash generated outputs, run `--apply` again, and assert identical hashes.
- [ ] Run `--check` and confirm the generated tree is current.

### Task 5: Verification and handoff

**Files:**
- Verify all changed and generated paths; do not stage or commit.

**Interfaces:**
- Consumes: generated artifacts and validators.
- Produces: static verification evidence plus a bounded runtime smoke-test list.

- [ ] Run the focused generator and technology-contract tests.
- [ ] Run the focused technology validator.
- [ ] Run `python -B tools/validate_tc.py --limit 300`.
- [ ] Run `git diff --check` and verify Russian localisation BOM.
- [ ] Inspect the final diff for unrelated changes and report that a fresh game
  restart is still required to confirm exact on-screen geometry.
