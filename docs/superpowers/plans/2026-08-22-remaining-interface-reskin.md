# Remaining Interface Reskin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the complete technology, logistics, division deployment, and intelligence-agency interfaces without changing vanilla interaction geometry or game behavior.

**Architecture:** A shared deterministic Pillow helper produces the common dark-metal surfaces and four restrained accent palettes. One builder and one contract-test module own each interface family; the technology builder is integrated with the existing generated technology system, while the other builders reproduce the installed vanilla 1.19.2 GUI structure with an exact, counted sprite-substitution manifest.

**Tech Stack:** Python 3, Pillow, `unittest`, Clausewitz `.gui`/`.gfx`, PNG source art, DDS runtime textures.

**Spec:** `docs/superpowers/specs/2026-08-22-remaining-interface-reskin-design.md`

## Global Constraints

- Structural reference: Hearts of Iron IV Operation Postern 1.19.2.0.a729 from `Z:/SteamLibrary/steamapps/common/Hearts of Iron IV`.
- Runtime visual target: 1920x1080 with UI scale 1.0.
- Preserve element names, callbacks, data bindings, positions, sizes, scrolling, clipping, orientation, and interaction flow.
- Only exact sprite substitutions and explicitly enumerated text-fit exceptions are allowed outside the generated technology-tree graph.
- Technology definitions, graph layout, `interface/countrytechtreeview.gui`, and `interface/ADISCORD_technologies.gfx` remain owned by `tools/builders/build_adiscord_technology_system.py`.
- Builders default to check mode, write only with `--apply`, and must be clean on the second check.
- Preserve unrelated dirty work; stage and commit only the paths listed by the active task.
- Russian localisation is outside scope. If touched unexpectedly, stop and restore the task boundary; never rewrite it without preserving UTF-8 BOM.

---

### Task 1: Shared deterministic UI-surface library

**Files:**
- Create: `tools/lib/adiscord_ui_surfaces.py`
- Create: `tools/tests/test_adiscord_ui_surfaces.py`

**Interfaces:**
- Consumes: Pillow `Image`, `ImageDraw`, `ImageEnhance`, `ImageOps`; `tools.lib.paths.repository_root`.
- Produces: `UiPalette`, `PALETTES`, `load_surface_source(path, minimum_size)`, `metal_surface(source, size, palette, brightness, centering)`, `framed_panel(source, size, palette, brightness)`, `button_strip(source, frame_size, palette)`, `dds_bytes(image)`, `replace_counted(text, old, new, expected)`, `apply_or_check(outputs, apply, label)`.

- [ ] **Step 1: Write the failing helper tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from PIL import Image

from tools.lib.adiscord_ui_surfaces import (
    PALETTES, apply_or_check, button_strip, dds_bytes, framed_panel,
)


class UiSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.source = Image.new("RGBA", (1024, 1024), (39, 43, 44, 255))

    def test_four_section_palettes_are_distinct(self):
        self.assertEqual(set(PALETTES), {"technology", "logistics", "deployment", "intelligence"})
        self.assertEqual(len({palette.accent for palette in PALETTES.values()}), 4)

    def test_panel_and_three_state_button_dimensions(self):
        panel = framed_panel(self.source, (192, 192), PALETTES["technology"], 0.82)
        strip = button_strip(self.source, (81, 41), PALETTES["technology"])
        self.assertEqual(panel.size, (192, 192))
        self.assertEqual(strip.size, (243, 41))
        self.assertEqual(panel.getchannel("A").getextrema(), (255, 255))

    def test_apply_or_check_writes_only_in_apply_mode(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "panel.dds"
            outputs = {path: dds_bytes(self.source)}
            self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 1)
            self.assertFalse(path.exists())
            self.assertEqual(apply_or_check(outputs, apply=True, label="test"), 0)
            self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 0)
```

- [ ] **Step 2: Run the helper tests and confirm the import failure**

Run: `python -B -m unittest tools.tests.test_adiscord_ui_surfaces -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.lib.adiscord_ui_surfaces'`.

- [ ] **Step 3: Implement the shared API**

Use an immutable palette and keep warning colors independent of accents:

```python
@dataclass(frozen=True)
class UiPalette:
    deep: tuple[int, int, int, int]
    panel: tuple[int, int, int, int]
    edge: tuple[int, int, int, int]
    edge_light: tuple[int, int, int, int]
    accent: tuple[int, int, int, int]
    accent_light: tuple[int, int, int, int]


PALETTES = {
    "technology": UiPalette((7, 11, 12, 255), (17, 24, 25, 255), (55, 69, 70, 255), (104, 124, 123, 255), (48, 126, 126, 255), (74, 166, 162, 255)),
    "logistics": UiPalette((10, 10, 8, 255), (25, 22, 17, 255), (75, 64, 47, 255), (132, 112, 75, 255), (153, 101, 43, 255), (197, 142, 67, 255)),
    "deployment": UiPalette((8, 10, 7, 255), (21, 25, 17, 255), (64, 70, 49, 255), (112, 121, 79, 255), (91, 111, 57, 255), (132, 151, 78, 255)),
    "intelligence": UiPalette((7, 9, 12, 255), (17, 21, 27, 255), (54, 65, 78, 255), (98, 116, 135, 255), (58, 91, 121, 255), (84, 128, 164, 255)),
}
```

Implement `button_strip` with normal, hover, and disabled frames. Implement `apply_or_check` by byte-comparing all declared outputs, printing `STALE:` in check mode and `WROTE:` in apply mode, and creating only each output's parent directory.

- [ ] **Step 4: Run the helper tests**

Run: `python -B -m unittest tools.tests.test_adiscord_ui_surfaces -v`

Expected: 3 tests, all PASS.

- [ ] **Step 5: Commit the shared helper**

```powershell
git add -- tools/lib/adiscord_ui_surfaces.py tools/tests/test_adiscord_ui_surfaces.py
git commit -m "feat: add shared interface surface builder"
```

---

### Task 2: Technology research shell and generated tree skin

**Files:**
- Create: `tools/builders/build_adiscord_technology_ui_assets.py`
- Create: `tools/tests/test_adiscord_technology_ui.py`
- Create: `gfx/interface/technology/source/technology_surface_source.png`
- Create: generated files under `gfx/interface/technology/ui/`
- Create: `interface/countrytechnologyview.gui`
- Create: `interface/countrytechnologyview.gfx`
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: generated `interface/countrytechtreeview.gui`
- Modify: generated `interface/ADISCORD_technologies.gfx`

**Interfaces:**
- Consumes: Task 1 surface API, vanilla `countrytechnologyview.gui/.gfx`, the existing `BASE_GAME`, `find_block_end`, `write_gui`, and `write_gfx` technology-generator paths.
- Produces: `technology_ui_expected_outputs() -> dict[Path, bytes]`; `render_technology_view() -> str`; `technology_sprite_entries() -> str`; teal technology surface sprites prefixed `GFX_ADISCORD_technology_`.

- [ ] **Step 1: Write failing technology UI contract tests**

The test must assert the main window, slot rows, facility tab, folder surfaces, cards, progress bars, and three-state tabs use `GFX_ADISCORD_technology_*`. It must also assert that `countrytechtreeview.gui` still contains every generated `ADISCORD_*_folder` container and that running the technology builder in check mode produces no drift after apply.

```python
def test_research_shell_preserves_engine_bound_elements(self):
    gui = read("interface/countrytechnologyview.gui")
    for name in ("countrytechnologyview", "research_slots", "facilities", "research_slots_grid", "research_groups_grid", "close_button"):
        self.assertEqual(gui.count(f'name = "{name}"'), 1, name)

def test_research_shell_uses_adiscord_surfaces(self):
    gui = read("interface/countrytechnologyview.gui")
    for sprite in ("GFX_ADISCORD_technology_window_bg", "GFX_ADISCORD_technology_top_panel", "GFX_ADISCORD_technology_slot_bg", "GFX_ADISCORD_technology_tab"):
        self.assertIn(f'"{sprite}"', gui)

def test_generated_tree_keeps_all_custom_folders(self):
    gui = read("interface/countrytechtreeview.gui")
    for folder in FOLDER_BACKGROUNDS:
        self.assertEqual(gui.count(f'name = "{folder}"'), 1, folder)
```

- [ ] **Step 2: Run the technology UI tests and confirm missing-file failures**

Run: `python -B -m unittest tools.tests.test_adiscord_technology_ui -v`

Expected: FAIL because `interface/countrytechnologyview.gui` and the new builder do not exist.

- [ ] **Step 3: Implement the technology asset builder and research-shell renderer**

Copy the checked-in original metal source into the dedicated technology source path without altering the source file, then generate exact-sized DDS surfaces. Build `countrytechnologyview.gui` from the installed 1.19.2 vanilla file by counted token replacement:

```python
SPRITE_REPLACEMENTS = {
    "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_technology_window_bg", 1),
    "GFX_research_bg": ("GFX_ADISCORD_technology_slots_bg", 1),
    "GFX_research_slot": ("GFX_ADISCORD_technology_slot_bg", 1),
}

def replace_counted(text: str, old: str, new: str, expected: int) -> str:
    actual = text.count(f'"{old}"')
    if actual != expected:
        raise ValueError(f"{old}: expected {expected}, found {actual}")
    return text.replace(f'"{old}"', f'"{new}"')
```

Extend the mapping only with exact surface sprites discovered in the installed source; do not replace semantic icons such as technology, equipment, designer, carrier fighter, or research bonus glyphs. Emit all new sprite declarations into `countrytechnologyview.gfx`.

- [ ] **Step 4: Integrate tree skin declarations through the owning technology builder**

Import `technology_ui_expected_outputs` and `technology_sprite_entries` into `build_adiscord_technology_system.py`. Append the UI entries inside `write_gfx()` and apply only surface-name substitutions inside the existing `write_gui()` output after folder rendering. Do not move folder nodes or change `FOLDER_BACKGROUNDS`, grid positions, years, or branch sizes.

- [ ] **Step 5: Apply, check idempotence, and run focused technology tests**

Run:

```powershell
python -B -m tools.builders.build_adiscord_technology_ui_assets --apply
python -B -m tools.builders.build_adiscord_technology_system --apply
python -B -m tools.builders.build_adiscord_technology_ui_assets --check
python -B -m tools.builders.build_adiscord_technology_system --check
python -B -m unittest tools.tests.test_adiscord_technology_ui tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts -v
```

Expected: both checks exit 0 and all focused tests PASS.

- [ ] **Step 6: Commit only the technology UI path set**

```powershell
git add -- tools/builders/build_adiscord_technology_ui_assets.py tools/tests/test_adiscord_technology_ui.py tools/builders/build_adiscord_technology_system.py gfx/interface/technology interface/countrytechnologyview.gui interface/countrytechnologyview.gfx interface/countrytechtreeview.gui interface/ADISCORD_technologies.gfx
git diff --cached --check
git commit -m "feat: reskin technology interface"
```

---

### Task 3: Logistics interface and nested graphs

**Files:**
- Create: `tools/builders/build_adiscord_logistics_ui_assets.py`
- Create: `tools/tests/test_adiscord_logistics_ui.py`
- Create: `gfx/interface/logistics/source/logistics_surface_source.png`
- Create: generated files under `gfx/interface/logistics/ui/`
- Create: `interface/countrylogisticsview.gui`
- Create: `interface/countrylogisticsview.gfx`

**Interfaces:**
- Consumes: Task 1 surface API and vanilla `countrylogisticsview.gui/.gfx`.
- Produces: `expected_outputs() -> dict[Path, bytes]`, `render_gui() -> str`, amber/copper sprites prefixed `GFX_ADISCORD_logistics_`.

- [ ] **Step 1: Write failing logistics contracts**

```python
def test_all_logistics_windows_remain_present(self):
    gui = read("interface/countrylogisticsview.gui")
    for name in ("countrylogisticsview", "materiel", "fuel_info", "logistics_info_window", "logistics_fuel_window", "variants"):
        self.assertEqual(gui.count(f'name = "{name}"'), 1, name)

def test_semantic_icons_are_not_replaced(self):
    gui = read("interface/countrylogisticsview.gui")
    for sprite in ("GFX_logistics_need", "GFX_logistics_stockpile", "GFX_fuel_icon"):
        self.assertIn(sprite, gui)
```

Add exact DDS assertions for the main window tile, header, materiel list tile, equipment row, fuel panel, graph background/frame, variant row, priority control, and three-state time buttons.

- [ ] **Step 2: Run the logistics tests and confirm missing-file failures**

Run: `python -B -m unittest tools.tests.test_adiscord_logistics_ui -v`

Expected: FAIL because the logistics outputs are absent.

- [ ] **Step 3: Implement counted GUI substitutions and copper assets**

Use the installed vanilla GUI as input. Replace only backgrounds, headers, list rows, graph chrome, tabs, and priority button surfaces. Preserve resource, factory, fuel, shortage, efficiency, balance, and equipment icons. Fail the builder if any expected vanilla sprite count differs.

```python
VANILLA_GUI = BASE_GAME / "interface/countrylogisticsview.gui"
GUI_OUTPUT = ROOT / "interface/countrylogisticsview.gui"

def render_gui() -> str:
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    return text

def expected_outputs() -> dict[Path, bytes]:
    outputs = {GUI_OUTPUT: render_gui().encode("utf-8")}
    outputs.update(render_logistics_dds_outputs())
    outputs[GFX_OUTPUT] = render_gfx().encode("utf-8")
    return outputs
```

- [ ] **Step 4: Apply, check idempotence, and run logistics tests**

```powershell
python -B -m tools.builders.build_adiscord_logistics_ui_assets --apply
python -B -m tools.builders.build_adiscord_logistics_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_logistics_ui -v
```

Expected: check exits 0 and tests PASS.

- [ ] **Step 5: Commit only logistics paths**

```powershell
git add -- tools/builders/build_adiscord_logistics_ui_assets.py tools/tests/test_adiscord_logistics_ui.py gfx/interface/logistics interface/countrylogisticsview.gui interface/countrylogisticsview.gfx
git diff --cached --check
git commit -m "feat: reskin logistics interface"
```

---

### Task 4: Division deployment and template selection

**Files:**
- Create: `tools/builders/build_adiscord_deployment_ui_assets.py`
- Create: `tools/tests/test_adiscord_deployment_ui.py`
- Create: `gfx/interface/deployment/source/deployment_surface_source.png`
- Create: generated files under `gfx/interface/deployment/ui/`
- Create: `interface/countrydeploymentview.gui`
- Create: `interface/countrydeploymentview.gfx`

**Interfaces:**
- Consumes: Task 1 surface API and vanilla `countrydeploymentview.gui/.gfx`.
- Produces: `expected_outputs() -> dict[Path, bytes]`, `render_gui() -> str`, olive sprites prefixed `GFX_ADISCORD_deployment_`.

- [ ] **Step 1: Write failing deployment contracts**

```python
def test_engine_bound_deployment_widgets_remain_unique(self):
    gui = read("interface/countrydeploymentview.gui")
    for name in ("countrydeploymentview", "templatedeploymentwindow", "templates_grid", "deployments_list_gridbox", "foreign_templates_grid", "symbols_grid"):
        self.assertEqual(gui.count(f'name = "{name}"'), 1, name)

def test_training_and_equipment_bars_keep_semantics(self):
    gui = read("interface/countrydeploymentview.gui")
    for name in ("equipment_progressbar", "training_progressbar", "deploy_line_button", "cancel_line_button"):
        self.assertIn(f'name = "{name}"', gui)
```

Assert exact assets for the main window, template window, template rows, deployment rows, conveyor summary/end, progress frames, dropdowns, priority controls, and disabled/decommissioned states.

- [ ] **Step 2: Run the deployment tests and confirm missing-file failures**

Run: `python -B -m unittest tools.tests.test_adiscord_deployment_ui -v`

Expected: FAIL because the deployment outputs are absent.

- [ ] **Step 3: Implement counted substitutions and olive assets**

Preserve every template/HQ lock consumer, button name, progressbar name, dropdown child, flag frame, and tutorial highlight. Replace chrome only. Keep shortage red, ready green, equipment/training fill semantics, and priority-state frame ordering unchanged.

```python
VANILLA_GUI = BASE_GAME / "interface/countrydeploymentview.gui"
GUI_OUTPUT = ROOT / "interface/countrydeploymentview.gui"

def render_gui() -> str:
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    return text

def expected_outputs() -> dict[Path, bytes]:
    outputs = {GUI_OUTPUT: render_gui().encode("utf-8")}
    outputs.update(render_deployment_dds_outputs())
    outputs[GFX_OUTPUT] = render_gfx().encode("utf-8")
    return outputs
```

- [ ] **Step 4: Apply, check idempotence, and run deployment/HQ tests**

```powershell
python -B -m tools.builders.build_adiscord_deployment_ui_assets --apply
python -B -m tools.builders.build_adiscord_deployment_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_deployment_ui tools.tests.test_adiscord_army_hq_contracts -v
```

Expected: check exits 0 and all focused tests PASS.

- [ ] **Step 5: Commit only deployment paths**

```powershell
git add -- tools/builders/build_adiscord_deployment_ui_assets.py tools/tests/test_adiscord_deployment_ui.py gfx/interface/deployment interface/countrydeploymentview.gui interface/countrydeploymentview.gfx
git diff --cached --check
git commit -m "feat: reskin division deployment interface"
```

---

### Task 5: Intelligence agency and operative surfaces

**Files:**
- Create: `tools/builders/build_adiscord_intelligence_ui_assets.py`
- Create: `tools/tests/test_adiscord_intelligence_ui.py`
- Create: `gfx/interface/intelligence/source/intelligence_surface_source.png`
- Create: generated files under `gfx/interface/intelligence/ui/`
- Create: `interface/countryintelligenceagencyview.gui`
- Create: `interface/countryintelligenceagencyview.gfx`
- Create: `interface/operative.gui`
- Create: `interface/operativeleader.gui`
- Create: `interface/operativeleader.gfx`

**Interfaces:**
- Consumes: Task 1 surface API and the five installed vanilla intelligence/operative interface files.
- Produces: `expected_outputs() -> dict[Path, bytes]`, `render_gui_files() -> dict[Path, str]`, blue-grey sprites prefixed `GFX_ADISCORD_intelligence_`.

- [ ] **Step 1: Write failing agency and operative contracts**

```python
def test_agency_nested_windows_remain_present(self):
    gui = read("interface/countryintelligenceagencyview.gui")
    for name in ("countryintelligenceagencyview", "name_logo_agency_selection_window", "intelligence_agency_upgrades_window", "operations_grid", "country_list", "logo_list"):
        self.assertIn(f'name = "{name}"', gui)

def test_operative_controls_remain_engine_bound(self):
    leader = read("interface/operativeleader.gui")
    for name in ("operative_leader_window", "operative_order_bar", "operative_badge_view", "operative_status_window", "operative_view"):
        self.assertEqual(leader.count(f'name = "{name}"'), 1, name)
```

Assert exact assets for creation, naming, logo selection, branch upgrades, agent rows, operations, crypto, recruitment, portrait frames, mission/order buttons, status bars, badges, and captured/dead/disabled states.

- [ ] **Step 2: Run intelligence tests and confirm missing-file failures**

Run: `python -B -m unittest tools.tests.test_adiscord_intelligence_ui -v`

Expected: FAIL because the intelligence outputs are absent.

- [ ] **Step 3: Implement counted substitutions across all five files**

Preserve agency upgrade icons, flags, logos, mission/operation icons, traits, nationalities, portraits, crypto symbols, and semantic alerts. Replace only window chrome, list/card surfaces, tabs, frames, button plates, and progressbar frames. Require exact source SHA-256 values for all five vanilla files before `--apply`; report a source-version mismatch instead of emitting partially compatible GUI.

```python
VANILLA_FILES = {
    "countryintelligenceagencyview.gui": "00153f0968113c3f29d914bda227c729ba5d95f5888135c0dd98db89748ef3e5",
    "countryintelligenceagencyview.gfx": "5c4eb6c934654ff9d8c188c2560d51656b084d8b0de61d18fa4fb16b00c3d7da",
    "operative.gui": "bcdfa922932131db91c26dab7323e24456ae094b65c2aa2e7b77478c8dc5aa22",
    "operativeleader.gui": "cd80a14a5e2b70d11511eadf52a89b15be5188e4e03dce2e1acbc0040ecd79e0",
    "operativeleader.gfx": "f3ff58f344a1dcae6db664bcea70d3fe44ec1e64571f7165f5a135d927218f0f",
}

def verified_source(name: str, expected_sha256: str) -> bytes:
    data = (BASE_GAME / "interface" / name).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(f"vanilla interface mismatch for {name}: {actual}")
    return data

def render_gui_files() -> dict[Path, str]:
    rendered = {}
    for name, checksum in VANILLA_FILES.items():
        if not name.endswith(".gui"):
            continue
        text = verified_source(name, checksum).decode("utf-8-sig")
        for old, (new, expected) in FILE_REPLACEMENTS[name].items():
            text = replace_counted(text, old, new, expected)
        rendered[ROOT / "interface" / name] = text
    return rendered
```

- [ ] **Step 4: Apply, check idempotence, and run intelligence tests**

```powershell
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --apply
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_intelligence_ui -v
```

Expected: check exits 0 and tests PASS.

- [ ] **Step 5: Commit only intelligence paths**

```powershell
git add -- tools/builders/build_adiscord_intelligence_ui_assets.py tools/tests/test_adiscord_intelligence_ui.py gfx/interface/intelligence interface/countryintelligenceagencyview.gui interface/countryintelligenceagencyview.gfx interface/operative.gui interface/operativeleader.gui interface/operativeleader.gfx
git diff --cached --check
git commit -m "feat: reskin intelligence agency interface"
```

---

### Task 6: Cross-screen static and runtime acceptance

**Files:**
- Modify only if a real contract defect is found: the task-owned files from Tasks 1-5.
- Inspect: fresh HOI4 logs under `Documents/Paradox Interactive/Hearts of Iron IV/logs/`.

**Interfaces:**
- Consumes: all four builders and focused test modules.
- Produces: a clean static gate and recorded fresh-campaign visual/runtime acceptance at 1920x1080, UI scale 1.0.

- [ ] **Step 1: Prove all builders are current**

```powershell
python -B -m tools.builders.build_adiscord_technology_ui_assets --check
python -B -m tools.builders.build_adiscord_technology_system --check
python -B -m tools.builders.build_adiscord_logistics_ui_assets --check
python -B -m tools.builders.build_adiscord_deployment_ui_assets --check
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --check
```

Expected: every command exits 0 without `STALE:` output.

- [ ] **Step 2: Run the complete focused UI suite**

```powershell
python -B -m unittest tools.tests.test_adiscord_ui_surfaces tools.tests.test_adiscord_technology_ui tools.tests.test_adiscord_logistics_ui tools.tests.test_adiscord_deployment_ui tools.tests.test_adiscord_intelligence_ui tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts tools.tests.test_adiscord_army_hq_contracts -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run repository gates**

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: validator exits 0 or reports only identified pre-existing warnings; both diff checks produce no task-owned errors.

- [ ] **Step 4: Perform fresh-game visual acceptance**

Fully exit HOI4, start it through the launcher with only the intended mod set, begin a fresh 2160 campaign at 1920x1080 and UI scale 1.0, and open:

1. Research overview, facilities, every technology folder, a selectable technology, and an active research slot.
2. Logistics main list, equipment detail graph, fuel graph, every time-range tab, and a variant list.
3. Deployment main list, template selection, foreign/decommissioned templates, custom symbol list, active training line, and all priority states.
4. Agency creation/naming/logo selection, upgrades, operations, cryptology, recruitment, an idle operative, an assigned operative, and any available captured/dead/disabled state.

For every surface, verify textures, frame order, clipping, scrolling, clickability, tooltips, disabled state, and Russian text fit. Then inspect fresh `error.log` for task-owned `.gui`, `.gfx`, missing texture, missing sprite, and parse errors.

- [ ] **Step 5: Commit only acceptance-driven corrections**

If runtime acceptance found a defect, add only its owning builder, test, generated GUI/GFX, and DDS outputs; rerun Steps 1-3 before committing. If no correction was required, do not create an empty commit.

```powershell
git diff --cached --name-only
git diff --cached --check
git commit -m "fix: finalize remaining interface reskin"
```
