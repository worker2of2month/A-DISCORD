# Remaining Interface Reskin Design

## Goal

Finish the A-Discord visual conversion of the Hearts of Iron IV interface for
technology, logistics, division deployment, and the intelligence agency. The
work includes every nested window belonging to those sections while preserving
vanilla behavior and nearly all vanilla geometry.

The change is a visual reskin. It does not alter mechanics, scripted content,
localisation, technology effects, division rules, intelligence behavior, or DLC
availability.

## Design Principles

- Preserve vanilla element names, callbacks, data bindings, dimensions,
  scrolling, clipping, orientation, and interaction flow.
- Permit only explicitly documented spacing adjustments needed to prevent text
  or replacement textures from clipping.
- Use the established A-Discord dark metal visual language already present in
  production, construction, trade, and decisions.
- Give each section a restrained accent color. Accent color is used for active
  tabs, selected states, progress highlights, and small separators, not for
  large background fields.
- Cover normal, hover, pressed, selected, and disabled button states.
- Treat generated technology outputs as generator-owned.

## Visual Language

All four sections share charcoal metal backgrounds, slightly lighter raised
panels, worn steel borders, pale neutral text, and restrained texture noise.
The surfaces must remain readable behind icons and localized text.

Section accents are:

- Technology: muted cyan/teal.
- Logistics: muted amber/copper.
- Deployment: muted olive.
- Intelligence agency: cold blue-grey.

Hover states brighten the relevant accent slightly. Pressed states darken it.
Disabled states are desaturated and lower contrast. Warning, shortage, and
failure colors retain their existing semantic meaning and are not recolored to
match a section accent.

## Scope

### Technology

Reskin the research overview, research slots, facilities tab, technology tree,
technology cards, folders, tabs, progress presentation, and associated nested
selection/detail surfaces.

The existing technology generator remains the owner of generated technology
definitions, graph layouts, `interface/countrytechtreeview.gui`, and
`interface/ADISCORD_technologies.gfx`. Visual changes to those outputs must be
implemented in `tools/builders/build_adiscord_technology_system.py` and then
regenerated. The research overview is introduced through the vanilla-compatible
`countrytechnologyview.gui/.gfx` pair.

### Logistics

Reskin `countrylogisticsview.gui/.gfx`, including the main materiel list,
resource strip, equipment rows, priorities, factory summaries, fuel section,
stockpile and consumption graphs, time-range controls, and equipment-variant
detail lists.

### Division Deployment

Reskin `countrydeploymentview.gui/.gfx`, including the deployment list, template
selection, foreign and decommissioned templates, custom symbols, equipment and
training progress, priority controls, conveyor summaries, and division-name
selection.

### Intelligence Agency

Reskin `countryintelligenceagencyview.gui/.gfx`, `operative.gui`, and
`operativeleader.gui/.gfx`. This includes agency creation and naming, logo
selection, branch upgrades, agents, operations, cryptology, operative
recruitment, operative portraits, mission states, status bars, badges, and
order controls.

The agency screens remain compatible with the installed vanilla/DLC contract.
The reskin does not make intelligence features available when their normal game
requirements are not met.

## Asset Architecture

Each section has a dedicated asset builder and source-image directory. A small
shared helper owns the common palette, metal-surface treatment, borders, and
button-state transformations. Section builders own exact dimensions, slicing,
frame counts, semantic accents, output filenames, and their GFX declarations.

Builders support explicit `--check` and `--apply` modes. `--check` reports drift
without writing. `--apply` writes only declared owned assets and declarations.
After an apply that changes output, a second check must be clean.

Source PNG material is retained in the repository beside the relevant project
assets. Runtime DDS files use RGBA data, exact engine-facing dimensions, and the
frame layout required by the original sprite contract.

## Vanilla Compatibility Guard

The installed Hearts of Iron IV Operation Postern 1.19.2.0.a729 interface files
are the structural reference for newly introduced screens. Tests record a normalized structural
fingerprint for each reskinned GUI. The fingerprint includes interactive
element names, types, positions, sizes, orientations, scroll configuration,
clipping, bindings, and callbacks while excluding approved sprite-name
substitutions.

Any intentional geometry exception is listed explicitly in the test rather
than silently changing the reference fingerprint. Technology-tree graph
geometry is exempt because it is generated for A-Discord, but the surrounding
research-window interaction contract remains protected.

## Validation

Focused tests verify:

- every expected A-Discord sprite is used by its live GUI surface;
- retired vanilla surface sprites are absent from the converted elements;
- GFX declarations point to existing mod-owned files;
- DDS dimensions, color mode, alpha behavior, and button frame counts;
- normalized vanilla structural fingerprints and documented exceptions;
- generator ownership, check/apply behavior, and idempotence;
- UTF-8 BOM preservation for any Russian localisation file, although
  localisation changes are outside the planned scope.

Repository gates are the focused UI tests and validators followed by:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Static checks do not prove Clausewitz runtime behavior. Final acceptance
requires a full Hearts of Iron IV restart, a fresh campaign, and fresh logs.
Each main screen and nested window must be opened at 1920x1080 with UI scale
1.0. Review covers missing textures, incorrect frames, clipping,
scrolling, clickability, tooltips, localization fit, disabled states, and the
absence of new mod-owned GUI/GFX errors.

## Delivery Order

Implement and validate the sections independently in this order:

1. Technology, while preserving current generator-owned changes.
2. Logistics.
3. Division deployment.
4. Intelligence agency and operative surfaces.
5. Cross-screen consistency and final repository/runtime acceptance.

Each section is kept reviewable as an isolated path set. The dirty shared
checkout is preserved, unrelated files are not reformatted or reverted, and
only explicitly verified paths may be staged.
