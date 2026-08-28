# Semantic Interface Reskin Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failed generic technology, intelligence-agency, and division-deployment surfaces with exact-size semantic A-Discord assets inspired by TFR's clarity without copying TFR content.

**Architecture:** Keep every live GUI widget and position, but replace the four-generic-surface model with per-role `SpriteContract` manifests. Shared code owns deterministic drawing and contract/preview utilities; each screen builder owns exact sizes, frame counts, semantic zones, font substitutions, GFX declarations, and generated outputs.

**Tech Stack:** Python 3, Pillow, Clausewitz `.gui`/`.gfx`, DDS RGBA assets, `unittest`, repository builders and validators.

**Spec:** `docs/superpowers/specs/2026-08-28-semantic-interface-reskin-correction-design.md`

## Global Constraints

- Scope is technology, intelligence agency/operatives, and division deployment only; do not modify logistics.
- Preserve all vanilla/current widget names, bindings, callbacks, scrolling, clipping, positions, and sizes unless an exception is explicitly tested.
- Do not copy TFR textures, fonts, GUI blocks, or source art; TFR is a visual-principle reference only.
- Fixed sprites retain their native total dimensions, sprite kind, frame count, effect metadata, and horizontal frame layout.
- Custom declarations remain in additive A-Discord GFX files; do not create `countrytechnologyview.gfx`, `countrydeploymentview.gfx`, `countryintelligenceagencyview.gfx`, or `operativeleader.gfx`.
- Generated GUI and DDS outputs are edited only through their owning builders.
- Russian localization is outside scope; if unexpectedly touched, preserve UTF-8 BOM.
- Preserve unrelated dirty STP/BOP/decision work and stage only explicit verified paths.
- Apply TDD to every code or contract change: write the test, observe the expected failure, implement the minimum correction, then rerun focused tests.
- Runtime acceptance still requires a full HOI4 restart, fresh campaign, screenshots, and fresh logs.

## File Structure

- `tools/lib/adiscord_ui_surfaces.py`: low-level surface, frame, recess, rail, status-band, state-strip, and preview drawing primitives.
- `tools/lib/adiscord_ui_contracts.py`: immutable sprite contracts, dimension/frame validation, GFX entry rendering, and deterministic preview assembly.
- `tools/tests/test_adiscord_ui_surfaces.py`: pixel-level behavior of drawing primitives.
- `tools/tests/test_adiscord_ui_contracts.py`: literal engine-facing contract and preview behavior.
- `tools/builders/build_adiscord_deployment_ui_assets.py`: deployment manifest, semantic drawing functions, GUI substitutions, GFX, DDS, and preview outputs.
- `tools/tests/test_adiscord_deployment_ui.py`: deployment dimensions, one-to-one roles, GUI/HQ invariants, and current outputs.
- `tools/builders/build_adiscord_intelligence_ui_assets.py`: agency/operative manifests, dark-surface font substitutions, semantic drawings, source-art crop, GFX, DDS, and preview outputs.
- `tools/tests/test_adiscord_intelligence_ui.py`: agency dimensions, frame counts, fonts, nested-window invariants, and current outputs.
- `gfx/interface/intelligence/source/ADISCORD_intelligence_header_source.png`: original generated monochrome espionage header source.
- `tools/builders/build_adiscord_technology_ui_assets.py`: research overview, detail surfaces, state-node drawings, GFX, and preview outputs.
- `tools/builders/build_adiscord_technology_system.py`: generated tree skin integration and late state-sprite override output.
- `tools/tests/test_adiscord_technology_ui.py`: overview/tree dimensions, state semantics, additive load order, and current outputs.
- `tools/tests/test_build_adiscord_technology_system.py`: technology generator idempotence and state-override ownership.
- `interface/ADISCORD_deployment_ui.gfx`, `interface/ADISCORD_intelligence_ui.gfx`, `interface/ADISCORD_technology_ui.gfx`: generated additive declarations.
- `interface/zz_ADISCORD_technology_states.gfx`: generated late-loaded declarations for engine-recognized technology state sprite names.
- `gfx/interface/{deployment,intelligence,technology}/ui/*.dds`: generated runtime assets.
- `gfx/interface/{deployment,intelligence,technology}/preview/*.png`: deterministic review sheets not referenced by runtime GFX.

---

### Task 1: Shared Semantic Drawing and Contract Primitives

**Files:**
- Create: `tools/lib/adiscord_ui_contracts.py`
- Create: `tools/tests/test_adiscord_ui_contracts.py`
- Modify: `tools/lib/adiscord_ui_surfaces.py`
- Modify: `tools/tests/test_adiscord_ui_surfaces.py`

**Interfaces:**
- Produces: `SpriteContract`, `render_gfx_entry()`, `validate_contract_image()`, `contact_sheet()`, `surface()`, `outer_frame()`, `recessed_well()`, `raised_field()`, `status_band()`, `partial_rails()`, and `horizontal_state_strip()`.
- Consumes: existing `UiPalette`, `PALETTES`, `load_surface_source()`, `dds_bytes()`, `replace_counted()`, and `apply_or_check()`.

- [ ] **Step 1: Add failing pixel-level tests for semantic primitives**

Add tests using a literal 96×64 source and hand-checked coordinates:

```python
from tools.lib.adiscord_ui_surfaces import (
    outer_frame,
    partial_rails,
    recessed_well,
    status_band,
)

def test_recess_and_status_band_change_only_their_declared_zones(self) -> None:
    image = Image.new("RGBA", (96, 64), (40, 42, 44, 255))
    recessed_well(image, (8, 10, 55, 48), PALETTES["deployment"])
    status_band(image, (60, 10, 90, 15), (132, 151, 78, 255))

    self.assertEqual(image.getpixel((2, 2)), (40, 42, 44, 255))
    self.assertNotEqual(image.getpixel((8, 10)), (40, 42, 44, 255))
    self.assertEqual(image.getpixel((70, 12)), (132, 151, 78, 255))

def test_partial_rails_do_not_draw_a_repeated_full_outer_frame(self) -> None:
    image = Image.new("RGBA", (96, 64), (40, 42, 44, 255))
    partial_rails(image, (5, 6, 90, 58), PALETTES["intelligence"])
    self.assertEqual(image.getpixel((5, 6)), (40, 42, 44, 255))
    self.assertNotEqual(image.getpixel((48, 6)), (40, 42, 44, 255))
```

- [ ] **Step 2: Run the surface tests and verify RED**

Run: `python -B -m unittest tools.tests.test_adiscord_ui_surfaces -v`

Expected: import failure for `outer_frame`/`partial_rails`/`recessed_well`/`status_band`, proving the current helper cannot express semantic layouts.

- [ ] **Step 3: Add failing literal contract tests**

Create `tools/tests/test_adiscord_ui_contracts.py` with expectations independent from the implementation:

```python
import unittest
from PIL import Image

from tools.lib.adiscord_ui_contracts import (
    SpriteContract,
    contact_sheet,
    render_gfx_entry,
    validate_contract_image,
)

class UiContractTests(unittest.TestCase):
    def test_fixed_sprite_requires_total_native_dimensions(self) -> None:
        contract = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(516, 42),
            frames=2,
            effect_file="gfx/FX/buttonstate_nodowneffect.lua",
        )
        with self.assertRaisesRegex(ValueError, "expected 516x42"):
            validate_contract_image(contract, Image.new("RGBA", (258, 42)))

    def test_gfx_entry_preserves_kind_frames_and_effect(self) -> None:
        contract = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(516, 42),
            frames=2,
            effect_file="gfx/FX/buttonstate_nodowneffect.lua",
        )
        rendered = render_gfx_entry(contract, "gfx/interface/example.dds")
        self.assertIn('name = "GFX_ADISCORD_example"', rendered)
        self.assertIn("noOfFrames = 2", rendered)
        self.assertIn('effectFile = "gfx/FX/buttonstate_nodowneffect.lua"', rendered)

    def test_contact_sheet_is_deterministic_and_rgba(self) -> None:
        entries = [
            ("a", Image.new("RGBA", (40, 20), (10, 20, 30, 255))),
            ("b", Image.new("RGBA", (20, 40), (40, 50, 60, 255))),
        ]
        first = contact_sheet(entries, width=160)
        second = contact_sheet(entries, width=160)
        self.assertEqual(first.mode, "RGBA")
        self.assertEqual(first.tobytes(), second.tobytes())
```

- [ ] **Step 4: Run the contract tests and verify RED**

Run: `python -B -m unittest tools.tests.test_adiscord_ui_contracts -v`

Expected: `ModuleNotFoundError: tools.lib.adiscord_ui_contracts`.

- [ ] **Step 5: Implement the minimum shared APIs**

Create the contract type with explicit validation:

```python
@dataclass(frozen=True)
class SpriteContract:
    source_name: str
    target_name: str
    filename: str
    kind: Literal["spriteType", "corneredTileSpriteType", "frameAnimatedSpriteType"]
    total_size: tuple[int, int]
    frames: int = 1
    border_size: tuple[int, int] | None = None
    effect_file: str | None = None
    always_transparent: bool = False
    tiling_center: bool = False
    extra_lines: tuple[str, ...] = ()

def validate_contract_image(contract: SpriteContract, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"{contract.target_name}: expected RGBA, found {image.mode}")
    if image.size != contract.total_size:
        expected = f"{contract.total_size[0]}x{contract.total_size[1]}"
        actual = f"{image.width}x{image.height}"
        raise ValueError(f"{contract.target_name}: expected {expected}, found {actual}")
    if contract.total_size[0] % contract.frames:
        raise ValueError(f"{contract.target_name}: width is not divisible by frames")
```

Implement `render_gfx_entry()` from contract fields, including
`tilingCenter = yes` when requested and verbatim animation/load metadata from
`extra_lines`. Make `contact_sheet()` place labeled, unscaled RGBA assets on a
neutral background in input order. Add the six drawing primitives to
`adiscord_ui_surfaces.py`; each mutates only the supplied image and box.

- [ ] **Step 6: Run shared tests and verify GREEN**

Run: `python -B -m unittest tools.tests.test_adiscord_ui_surfaces tools.tests.test_adiscord_ui_contracts -v`

Expected: all shared tests pass.

- [ ] **Step 7: Commit the shared foundation**

```powershell
git add -- tools/lib/adiscord_ui_surfaces.py tools/lib/adiscord_ui_contracts.py tools/tests/test_adiscord_ui_surfaces.py tools/tests/test_adiscord_ui_contracts.py
git diff --cached --check
git commit -m "refactor: add semantic interface asset contracts"
```

---

### Task 2: Correct Division Deployment Composition

**Files:**
- Modify: `tools/builders/build_adiscord_deployment_ui_assets.py`
- Modify: `tools/tests/test_adiscord_deployment_ui.py`
- Regenerate: `interface/countrydeploymentview.gui`
- Regenerate: `interface/ADISCORD_deployment_ui.gfx`
- Create/replace: `gfx/interface/deployment/ui/*.dds`
- Create: `gfx/interface/deployment/preview/ADISCORD_deployment_preview.png`

**Interfaces:**
- Consumes: `SpriteContract`, `render_gfx_entry()`, `validate_contract_image()`, `contact_sheet()`, and shared drawing primitives from Task 1.
- Produces: `DEPLOYMENT_CONTRACTS`, `render_asset(contract)`, `render_gui()`, `render_gfx()`, and deterministic `expected_outputs()`.

- [ ] **Step 1: Replace the generic-presence test with failing semantic contracts**

Add literal expectations that catch the current wrong kind/size reuse:

```python
EXPECTED_FIXED = {
    "GFX_ADISCORD_deployment_reinforcement_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_upgrade_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_garrison_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_operations_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_template": ((346, 78), 1),
    "GFX_ADISCORD_deployment_template_obsolete": ((348, 79), 1),
    "GFX_ADISCORD_deployment_conveyor": ((490, 84), 1),
    "GFX_ADISCORD_deployment_line": ((514, 40), 1),
    "GFX_ADISCORD_deployment_end_line": ((518, 40), 1),
    "GFX_ADISCORD_deployment_priority_title": ((159, 26), 1),
    "GFX_ADISCORD_deployment_priority_meter": ((108, 33), 1),
}

def test_fixed_deployment_assets_keep_native_semantic_dimensions(self) -> None:
    contracts = {item.target_name: item for item in DEPLOYMENT_CONTRACTS}
    for name, (size, frames) in EXPECTED_FIXED.items():
        self.assertEqual(contracts[name].kind, "spriteType", name)
        self.assertEqual(contracts[name].total_size, size, name)
        self.assertEqual(contracts[name].frames, frames, name)

def test_deployment_gui_does_not_reuse_one_line_for_incompatible_roles(self) -> None:
    gui = GUI.read_text(encoding="utf-8-sig")
    for name in EXPECTED_FIXED:
        self.assertIn(f'"{name}"', gui)
    self.assertNotIn('"GFX_ADISCORD_deployment_panel"', gui)
```

- [ ] **Step 2: Run the deployment test and verify RED**

Run: `python -B -m unittest tools.tests.test_adiscord_deployment_ui -v`

Expected: import failure for `DEPLOYMENT_CONTRACTS` or missing semantic sprite names; the current four-surface builder must not satisfy the test.

- [ ] **Step 3: Define one-to-one deployment contracts and substitutions**

Replace the broad mapping with explicit source-to-target entries. Include the eleven fixed contracts above plus true tiled shell contracts for `GFX_tiled_window2_1b_border`, `GFX_tiled_window`, `GFX_tiled_window_1b_thin_border`, `GFX_tiled_plain_bg_small`, `GFX_tiled_window_transparent`, and the large overlay. Preserve source kinds, 64/16/1-pixel borders, effects, and total sizes.

Use exact counted replacements, for example:

```python
SPRITE_REPLACEMENTS = {
    "GFX_deploy_reinforcements_entry": ("GFX_ADISCORD_deployment_reinforcement_row", 2),
    "GFX_deploy_upgrades_entry": ("GFX_ADISCORD_deployment_upgrade_row", 1),
    "GFX_deploy_garrisons_entry": ("GFX_ADISCORD_deployment_garrison_row", 1),
    "GFX_deploy_operations_entry": ("GFX_ADISCORD_deployment_operations_row", 1),
    "GFX_deployment_named_division_bg": ("GFX_ADISCORD_deployment_template", 1),
    "GFX_deployment_named_division_obsolete_bg": ("GFX_ADISCORD_deployment_template_obsolete", 1),
    "GFX_military_deployment_conveyor_view_bg": ("GFX_ADISCORD_deployment_conveyor", 1),
    "GFX_military_deployment_line_view_bg": ("GFX_ADISCORD_deployment_line", 1),
    "GFX_military_deployment_end_line_view_bg": ("GFX_ADISCORD_deployment_end_line", 1),
    "GFX_deploy_priority_title_bg": ("GFX_ADISCORD_deployment_priority_title", 2),
    "GFX_deploy_priority_equipment_meter_bg": ("GFX_ADISCORD_deployment_priority_meter", 2),
}
```

If a counted source occurrence differs, inspect the exact current vanilla GUI and correct the literal count; do not weaken `replace_counted()`.

- [ ] **Step 4: Draw native semantic deployment assets**

Implement separate functions:

```python
def _priority_row(source: Image.Image, accent: Color) -> Image.Image
def _template_row(source: Image.Image, size: tuple[int, int], obsolete: bool) -> Image.Image
def _conveyor_row(source: Image.Image) -> Image.Image
def _line_row(source: Image.Image, size: tuple[int, int], end_line: bool) -> Image.Image
def _priority_title(source: Image.Image) -> Image.Image
def _priority_meter(source: Image.Image) -> Image.Image
```

`_priority_row()` draws an icon recess at x=5..102, a label field at x=106..309, and a progress/control field at x=313..487. Use olive, rust, neutral supply steel, and violet only in a 4-pixel status band. `_template_row()` draws separate icon, title, and action wells matching the live 346×78/348×79 geometry. `_conveyor_row()` preserves the icon bay and two progress/control wells visible in the original 490×84 composition. Avoid complete nested frames inside these fixed sprites.

- [ ] **Step 5: Generate deployment outputs and verify GREEN**

Run:

```powershell
python -B -m tools.builders.build_adiscord_deployment_ui_assets --apply
python -B -m tools.builders.build_adiscord_deployment_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_deployment_ui tools.tests.test_adiscord_army_hq_contracts -v
```

Expected: second builder run reports current outputs; semantic dimensions and Army HQ contracts pass.

- [ ] **Step 6: Inspect the generated deployment preview**

Open `gfx/interface/deployment/preview/ADISCORD_deployment_preview.png`. Reject the task if icon, label, progress, or action zones are not visually distinct, if any row has a full nested outer frame, or if text/control wells do not align across rows.

- [ ] **Step 7: Commit deployment correction**

Stage only the deployment builder, test, GUI, additive GFX, runtime DDS, and preview paths; run cached diff check; commit:

```powershell
git commit -m "fix: rebuild division deployment interface"
```

---

### Task 3: Correct Intelligence Agency and Operative Composition

**Files:**
- Modify: `tools/builders/build_adiscord_intelligence_ui_assets.py`
- Modify: `tools/tests/test_adiscord_intelligence_ui.py`
- Create: `gfx/interface/intelligence/source/ADISCORD_intelligence_header_source.png`
- Regenerate: `interface/countryintelligenceagencyview.gui`
- Regenerate: `interface/operative.gui`
- Regenerate: `interface/operativeleader.gui`
- Regenerate: `interface/ADISCORD_intelligence_ui.gfx`
- Create/replace: `gfx/interface/intelligence/ui/*.dds`
- Create: `gfx/interface/intelligence/preview/ADISCORD_intelligence_preview.png`

**Interfaces:**
- Consumes: Task 1 contracts/primitives and the original generated header source.
- Produces: `INTELLIGENCE_CONTRACTS`, `FONT_REPLACEMENTS`, `_header()`, `_operations_tabs()`, semantic agency/operative asset functions, and deterministic outputs.

- [ ] **Step 1: Add failing intelligence dimension, frame, and contrast tests**

Use literal engine contracts:

```python
EXPECTED_FIXED = {
    "GFX_ADISCORD_intelligence_header": ((519, 109), 1),
    "GFX_ADISCORD_intelligence_create": ((508, 99), 1),
    "GFX_ADISCORD_intelligence_branches_popup": ((1092, 91), 1),
    "GFX_ADISCORD_intelligence_branch_row": ((1040, 136), 1),
    "GFX_ADISCORD_intelligence_operatives": ((522, 76), 1),
    "GFX_ADISCORD_intelligence_tabs": ((524, 53), 2),
    "GFX_ADISCORD_intelligence_operation_row": ((1038, 89), 2),
    "GFX_ADISCORD_intelligence_crypto_row": ((516, 87), 1),
    "GFX_ADISCORD_intelligence_crypto_selected": ((516, 87), 1),
    "GFX_ADISCORD_intelligence_required": ((33, 29), 1),
    "GFX_ADISCORD_intelligence_add_operative": ((61, 83), 1),
    "GFX_ADISCORD_intelligence_mission_bar": ((402, 79), 1),
}

def test_dark_agency_tabs_use_a_pale_font(self) -> None:
    gui = AGENCY_GUI.read_text(encoding="utf-8-sig")
    for block_name in ("operations_tab_button", "crypto_tab_button"):
        marker = f'name = "{block_name}"'
        marker_at = gui.index(marker)
        start = gui.rfind("buttonType = {", 0, marker_at)
        end = gui.index("\n\t\t}", marker_at) + len("\n\t\t}")
        block = gui[start:end]
        self.assertIn('font = "hoi_18mbs"', block)
        self.assertNotIn('hoi4_typewriter16', block)

def test_operation_strip_keeps_two_equal_frames(self) -> None:
    contract = next(c for c in INTELLIGENCE_CONTRACTS if c.target_name.endswith("operation_row"))
    self.assertEqual(contract.total_size, (1038, 89))
    self.assertEqual(contract.frames, 2)
    self.assertEqual(contract.total_size[0] // contract.frames, 519)
```

Add a source-art test requiring an RGBA/RGB image at least 1024×512 and generated header output exactly 519×109.

- [ ] **Step 2: Run intelligence tests and verify RED**

Run: `python -B -m unittest tools.tests.test_adiscord_intelligence_ui -v`

Expected: missing `INTELLIGENCE_CONTRACTS`, missing source art, missing semantic names, and dark-tab font assertion failures.

- [ ] **Step 3: Generate original intelligence header source with imagegen**

Use the built-in image generation tool with this prompt:

```text
Use case: stylized-concept
Asset type: wide strategy-game intelligence-agency header source art
Primary request: an original anonymous futuristic intelligence analyst in partial silhouette, wearing a restrained high-collared field coat, standing before layered translucent map grids and radio-spectrum traces
Style/medium: monochrome cinematic digital illustration, grounded military intelligence dossier aesthetic, original composition, no resemblance to existing game or mod art
Composition/framing: very wide horizontal composition, subject left of center, quiet negative space on the right for UI controls, readable when cropped to 519x109
Lighting/mood: cold low-key side lighting, secretive and analytical rather than action-oriented
Color palette: charcoal, cold steel blue, faint desaturated violet highlights
Constraints: no text, no letters, no logos, no flags, no insignia, no watermark, no weapons, no bright background
Avoid: TFR imagery, Hearts of Iron artwork, recognizable real people, pulp-noir fedora cliché
```

Inspect the generated output. Copy the selected project-bound image to `gfx/interface/intelligence/source/ADISCORD_intelligence_header_source.png`; do not leave the consuming builder pointed at the default generated-images directory.

- [ ] **Step 4: Define one-to-one intelligence contracts and safe font substitutions**

Create the twelve fixed contracts above plus separate true tiled contracts for the agency window shell, content tile, paper replacement tile, transparent tile, and small cost tile. Preserve the progress-bar nature of `GFX_decrypt_active_bg`; do not replace it with a static card.

Replace `GFX_intel_header_bg`, `GFX_operations_tab_large`, and each current fixed role with its exact semantic target. For the two dark tabs, replace the counted `font = "hoi4_typewriter16"` occurrences inside the named button blocks with `hoi_18mbs`; do not globally replace every typewriter font.

- [ ] **Step 5: Draw agency, tab, branch, operation, crypto, and operative assets**

Implement dedicated functions:

```python
def _header(source_art: Image.Image, metal: Image.Image) -> Image.Image
def _operations_tabs(metal: Image.Image) -> Image.Image
def _create_agency(metal: Image.Image) -> Image.Image
def _operatives_summary(metal: Image.Image) -> Image.Image
def _branch_popup(metal: Image.Image) -> Image.Image
def _branch_row(metal: Image.Image) -> Image.Image
def _operation_strip(metal: Image.Image) -> Image.Image
def _crypto_row(metal: Image.Image, selected: bool) -> Image.Image
def _add_operative(metal: Image.Image) -> Image.Image
def _mission_bar(metal: Image.Image) -> Image.Image
```

The two 262×53 tab frames use the same silhouette; only the selected edge/value differs. The two 519×89 operation frames preserve identical zones and vary selected/available emphasis. `_header()` crops with `ImageOps.fit(..., centering=(0.42, 0.48))`, converts to low-saturation cold steel, darkens it under controls, and adds only an outer lower rail.

- [ ] **Step 6: Generate intelligence outputs and verify GREEN**

Run:

```powershell
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --apply
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_intelligence_ui tools.tests.test_validate_adiscord_gui_contracts -v
```

Expected: source fingerprints, nested windows, semantic dimensions, frame counts, pale tab fonts, and checked-in outputs pass.

- [ ] **Step 7: Inspect the generated intelligence preview**

Open the preview and reject the task if dark text remains on dark panels, the two tab states are ambiguous, branch rows lack separate title/card zones, or the generated header competes with controls.

- [ ] **Step 8: Commit intelligence correction**

Stage only the intelligence source art, builder, test, three GUI files, additive GFX, runtime DDS, and preview; run cached diff check; commit:

```powershell
git commit -m "fix: rebuild intelligence agency interface"
```

---

### Task 4: Correct Technology Overview and Detail Surfaces

**Files:**
- Modify: `tools/builders/build_adiscord_technology_ui_assets.py`
- Modify: `tools/tests/test_adiscord_technology_ui.py`
- Regenerate: `interface/countrytechnologyview.gui`
- Regenerate: `interface/ADISCORD_technology_ui.gfx`
- Create/replace: `gfx/interface/technology/ui/*.dds`
- Create: `gfx/interface/technology/preview/ADISCORD_technology_overview_preview.png`

**Interfaces:**
- Consumes: Task 1 contracts/primitives.
- Produces: `TECHNOLOGY_OVERVIEW_CONTRACTS`, overview/detail semantic drawing functions, `apply_tree_skin()`, and deterministic overview outputs.

- [ ] **Step 1: Add failing overview and detail contract tests**

Use literal native totals:

```python
EXPECTED_OVERVIEW = {
    "GFX_ADISCORD_technology_slot": ((508, 99), 1),
    "GFX_ADISCORD_technology_idea": ((63, 63), 1),
    "GFX_ADISCORD_technology_tabs": ((516, 42), 2),
    "GFX_ADISCORD_technology_top": ((548, 138), 1),
    "GFX_ADISCORD_technology_bottom": ((546, 66), 1),
    "GFX_ADISCORD_technology_info_top": ((548, 220), 1),
    "GFX_ADISCORD_technology_info": ((508, 517), 1),
}

def test_research_slot_has_distinct_icon_title_and_progress_zones(self) -> None:
    outputs = expected_outputs()
    image = Image.open(io.BytesIO(outputs[SLOT])).convert("RGBA")
    self.assertNotEqual(image.getpixel((34, 46)), image.getpixel((250, 46)))
    self.assertNotEqual(image.getpixel((250, 46)), image.getpixel((430, 73)))
```

Also assert that true outer/content tiles have separate target names and that no fixed sprite points to a cornered tile declaration.

- [ ] **Step 2: Run technology UI tests and verify RED**

Run: `python -B -m unittest tools.tests.test_adiscord_technology_ui -v`

Expected: missing `TECHNOLOGY_OVERVIEW_CONTRACTS`, generic panel reuse, and semantic-zone failures.

- [ ] **Step 3: Define exact overview/detail contracts and substitutions**

Keep distinct tiled contracts for the 190×190 outer shell, 190×190 content shell, 549×600 overlay, 122×244 tree stripes, and other genuine tiles. Define fixed contracts for every item in `EXPECTED_OVERVIEW`. Rename the two-frame tab asset to `GFX_ADISCORD_technology_tabs` so its state-strip role is explicit.

Replace the current twelve `GFX_tiled_window_2b_border` tree occurrences only with a true tree-window tile. Replace paper detail surfaces with dedicated 548×220 and 508×517 fixed sprites, not the generic tree tile.

- [ ] **Step 4: Draw overview and detail assets**

Implement:

```python
def _research_slot(source: Image.Image) -> Image.Image
def _idea_button(source: Image.Image) -> Image.Image
def _overview_tabs(source: Image.Image) -> Image.Image
def _overview_top(source: Image.Image) -> Image.Image
def _overview_bottom(source: Image.Image) -> Image.Image
def _technology_info_top(source: Image.Image) -> Image.Image
def _technology_info(source: Image.Image) -> Image.Image
```

The slot uses an icon bay, title field, long progress rail, and remaining-time well aligned to the unchanged GUI. Detail surfaces are lighter cold steel than the tree background. Tabs differ by edge glow/value rather than a full bright fill.

- [ ] **Step 5: Apply and verify the overview correction**

Run:

```powershell
python -B -m tools.builders.build_adiscord_technology_ui_assets --apply
python -B -m tools.builders.build_adiscord_technology_ui_assets --check
python -B -m unittest tools.tests.test_adiscord_technology_ui -v
```

Expected: native dimensions, one-to-one declarations, semantic pixel zones, and checked-in outputs pass.

- [ ] **Step 6: Inspect and commit the overview**

Open the overview preview and reject it if slot controls float without zones or if detail text would sit on a near-black field. Stage explicit technology overview paths and commit:

```powershell
git commit -m "fix: rebuild technology overview interface"
```

---

### Task 5: Add Technology Node State Assets and Generator Integration

**Files:**
- Modify: `tools/builders/build_adiscord_technology_ui_assets.py`
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `tools/tests/test_adiscord_technology_ui.py`
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Regenerate: `interface/countrytechtreeview.gui`
- Regenerate: `interface/ADISCORD_technologies.gfx`
- Create: `interface/zz_ADISCORD_technology_states.gfx`
- Create/replace: `gfx/interface/technology/ui/ADISCORD_technology_node_*.dds`
- Create: `gfx/interface/technology/preview/ADISCORD_technology_tree_preview.png`

**Interfaces:**
- Consumes: Task 4 technology drawing/build outputs and the existing technology-system generator.
- Produces: `TECHNOLOGY_STATE_CONTRACTS`, `_technology_node()`, `_researching_strip()`, and late-loaded engine-recognized state declarations.

- [ ] **Step 1: Add failing literal state tests**

```python
EXPECTED_STATES = {
    "GFX_technology_unavailable_item_bg": ((183, 84), 1),
    "GFX_technology_available_item_bg": ((183, 84), 1),
    "GFX_technology_researched_item_bg": ((183, 84), 1),
    "GFX_technology_branch_item_bg": ((183, 84), 1),
    "GFX_technology_currently_researching_item_bg": ((1647, 84), 9),
}

def test_state_overrides_are_additive_and_late_loaded(self) -> None:
    path = ROOT / "interface/zz_ADISCORD_technology_states.gfx"
    self.assertTrue(path.is_file())
    self.assertFalse((ROOT / "interface/countrytechtreeview.gfx").exists())
    self.assertGreater(path.name.lower(), "countrytechtreeview.gfx")

def test_technology_states_preserve_engine_names_dimensions_and_frames(self) -> None:
    contracts = {item.target_name: item for item in TECHNOLOGY_STATE_CONTRACTS}
    for name, (size, frames) in EXPECTED_STATES.items():
        self.assertEqual(contracts[name].total_size, size)
        self.assertEqual(contracts[name].frames, frames)
```

Add a pixel-state assertion proving unavailable is neutral grey, available has a muted gold edge, researched has a muted green edge, and researching includes a teal moving edge across all nine frames.

- [ ] **Step 2: Run technology state tests and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_technology_ui tools.tests.test_build_adiscord_technology_system -v
```

Expected: missing late-loaded state file/contracts and missing state assets.

- [ ] **Step 3: Implement native node and animation-strip drawings**

Implement one 183×84 composition with an icon region, title region, and 17-pixel status band. Vary only the edge/status treatment by state. Assemble the researching output from nine independently drawn 183×84 frames into a 1647×84 strip; preserve the original animation rate/effect metadata from the installed vanilla declaration.

- [ ] **Step 4: Generate the late additive state declarations**

`zz_ADISCORD_technology_states.gfx` intentionally declares the five engine-recognized `GFX_technology_*` names because the technology renderer selects them by that naming contract. The additive filename loads after vanilla while avoiding a fragile full `countrytechtreeview.gfx` shadow. Include only these five state declarations.

Keep the state file in the technology UI builder's `expected_outputs()`. Add the same expected bytes to the technology-system idempotence snapshot so the system builder cannot silently remove or drift it.

- [ ] **Step 5: Regenerate technology outputs and verify GREEN**

Run:

```powershell
python -B -m tools.builders.build_adiscord_technology_ui_assets --apply
python -B -m tools.builders.build_adiscord_technology_system --apply
python -B -m tools.builders.build_adiscord_technology_ui_assets --check
python -B -m tools.builders.build_adiscord_technology_system --check
python -B -m unittest tools.tests.test_adiscord_technology_ui tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts -v
```

Expected: both generators are current and all technology tests pass.

- [ ] **Step 6: Inspect and commit technology tree states**

Open the tree preview. Reject it if state identity depends on large solid fills, if text/icon zones disappear, or if nine researching frames differ in geometry. Stage explicit technology state/generator paths and commit:

```powershell
git commit -m "fix: add semantic technology state surfaces"
```

---

### Task 6: Remove Obsolete Generic Outputs and Run Static Acceptance

**Files:**
- Modify: the three screen builders/tests only if ownership lists need cleanup.
- Delete after reference proof: obsolete generic DDS files under `gfx/interface/deployment/ui`, `gfx/interface/intelligence/ui`, and `gfx/interface/technology/ui`.
- Do not modify: logistics paths or unrelated dirty files.

**Interfaces:**
- Consumes: final `expected_outputs()` dictionaries from Tasks 2–5.
- Produces: no unowned runtime UI files, clean builders, clean focused/static gates, and a runtime review checklist.

- [ ] **Step 1: Add a failing ownership test for obsolete generic assets**

For each screen, compare the checked-in `ui/*.dds` set to the builder-owned DDS set and reject extras:

```python
def test_runtime_dds_directory_contains_only_builder_owned_outputs(self) -> None:
    owned = {path for path in expected_outputs() if path.suffix == ".dds"}
    checked_in = set(ASSET_DIR.glob("*.dds"))
    self.assertEqual(checked_in, owned)
```

- [ ] **Step 2: Run the three UI test modules and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_deployment_ui tools.tests.test_adiscord_intelligence_ui tools.tests.test_adiscord_technology_ui -v
```

Expected: obsolete generic assets are reported as extras.

- [ ] **Step 3: Prove no live references and delete exact obsolete files**

Use `rg` for each candidate filename and GFX name across `interface`, `tools`, and `gfx` manifests. Delete only files with zero live/generated references and an explicit semantic replacement. Do not delete a shared source PNG or any logistics asset.

- [ ] **Step 4: Run complete focused verification**

```powershell
python -B -m tools.builders.build_adiscord_deployment_ui_assets --check
python -B -m tools.builders.build_adiscord_intelligence_ui_assets --check
python -B -m tools.builders.build_adiscord_technology_ui_assets --check
python -B -m tools.builders.build_adiscord_technology_system --check
python -B -m unittest tools.tests.test_adiscord_ui_surfaces tools.tests.test_adiscord_ui_contracts tools.tests.test_adiscord_deployment_ui tools.tests.test_adiscord_intelligence_ui tools.tests.test_adiscord_technology_ui tools.tests.test_adiscord_production_ui tools.tests.test_adiscord_construction_ui tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts tools.tests.test_adiscord_army_hq_contracts tools.tests.test_validate_adiscord_gui_contracts
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Read every exit code. Separate known unrelated map/STP findings from any finding on task-owned paths; do not weaken validators.

- [ ] **Step 5: Inspect final previews and exact Git scope**

Open all four generated preview sheets (deployment, intelligence, technology overview, technology tree). Run `git status --short`, `git diff --stat`, and scoped diffs for every task-owned path. Confirm no logistics or unrelated STP/BOP/decision path is staged.

- [ ] **Step 6: Commit cleanup and static acceptance**

Stage only exact obsolete deletions and any ownership-test updates, run cached diff check, and commit:

```powershell
git commit -m "test: finalize semantic interface reskin"
```

- [ ] **Step 7: Hand off runtime acceptance**

Provide the user the three screen groups to open after a full restart and request screenshots of:

1. technology overview plus one unavailable, available, researching, and researched node with the detail window open;
2. deployment priority rows plus template list and one active training conveyor;
3. agency creation, created-agency overview, branch-upgrade popup, operations/cryptology tabs, recruitment, and operative mission bar.

Do not claim visual completion until those screenshots and fresh logs are reviewed.
