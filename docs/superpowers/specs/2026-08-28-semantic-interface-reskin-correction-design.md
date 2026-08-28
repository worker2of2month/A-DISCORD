# Semantic Interface Reskin Correction Design

## Goal

Replace the failed generic-surface treatment on the technology, intelligence
agency, and division-deployment interfaces with a semantic A-Discord skin.
Every visible card, row, tab, header, and nested window must retain its original
functional composition while adopting the established A-Discord industrial
visual language.

Logistics is explicitly outside this correction pass. Its current files and
assets remain unchanged.

## Runtime Failure Being Corrected

The first implementation replaced many unrelated vanilla sprites with four
generic framed rectangles per screen. That preserved GUI coordinates, but it
discarded the visual structure encoded in the original fixed-size sprites:
icon wells, text fields, progress channels, button areas, state frames, and
multi-frame selection behavior.

The runtime result is unacceptable:

- repeated borders make nested elements look as if they overlap;
- controls float on undifferentiated dark fields;
- paper tabs and generic metal panels clash within the same window;
- dark textures combined with dark vanilla fonts make labels illegible;
- large empty areas read as unfinished black sheets rather than deliberate
  interface space;
- fixed-size sprites were replaced by differently sized cornered tiles, losing
  their original composition and sometimes their frame semantics.

The correction removes the one-surface-per-category architecture. Shared code
may provide drawing primitives, but each semantic sprite receives an
individually composed asset with the native engine-facing dimensions, type,
and frame count of the sprite it replaces.

## TFR Reference Study

The locally installed The Fire Rises interface is a visual reference only. No
TFR texture, source image, font file, GUI block, or other content is copied into
A-Discord.

The useful principles observed in its technology, deployment, and intelligence
assets are:

- dark interfaces remain readable because raised steel and recessed fields
  have materially different values;
- fixed-size rows preserve dedicated icon, label, progress, and control zones;
- borders are thin and mostly reserved for outer edges and semantic wells;
- available, researched, selected, and disabled states use colored outlines or
  narrow bands instead of tinting the whole screen;
- large headers and agency panels use one strong thematic focal element rather
  than repeating small ornaments everywhere;
- tabs use a clear active/inactive silhouette and a font chosen for the actual
  background value;
- empty regions retain subtle texture and structural rails, but not a dense
  grid of identical frames.

A-Discord will adapt these principles to its own gunmetal, oxidized steel,
brass, muted teal, cold blue, olive, and warning colors.

## Global Visual System

### Surfaces

True resizable window shells use a dark gunmetal tile compatible with the
production and construction screens. Raised working panels are visibly lighter
than the shell. Recessed fields are darker but retain enough texture to remain
separate from the map behind the interface.

Only true outer windows receive a complete frame. Nested content backgrounds
use one-pixel separators, edge highlights, or partial rails. Decorative rivets
are limited to large structural corners and are not repeated on every row.

### Semantic Zones

Every fixed-size sprite is designed around the live widgets placed over it.
The asset builder records the intended regions for icons, labels, progress
bars, counters, and buttons. Visual dividers align with those regions rather
than being placed generically around the full texture.

### Color

- Neutral shell: charcoal and cold gunmetal.
- Technology: teal for active research, muted gold for available technology,
  restrained green for researched technology, and neutral grey for locked
  technology.
- Deployment: olive for reinforcement, rust for equipment replacement,
  desaturated violet for operations, and neutral steel for training lines.
- Intelligence: cold blue-grey with muted violet for agency creation and
  cryptology, plus restrained warm highlights for completed upgrades.
- Existing red, yellow, and green warning/status meanings remain unchanged.

Large backgrounds are never filled with an accent color. Accent is limited to
outlines, narrow title bands, selected states, progress channels, and small
identity marks.

### Typography

Geometry and localization keys remain unchanged. Where the original typewriter
font assumes a light paper background, the builder substitutes an existing
A-Discord/vanilla pale font suitable for a dark surface. Font changes are
explicitly enumerated and tested. Text positions change only when a screenshot
proves clipping; such exceptions must be recorded in the structural test.

## Asset Contract

The original vanilla or current generated declaration is the contract for each
replaced sprite:

- `spriteType` remains `spriteType`;
- `corneredTileSpriteType` remains `corneredTileSpriteType`;
- source dimensions are preserved for fixed sprites;
- `noOfFrames`, animation metadata, transparency behavior, effect files, and
  load behavior are preserved;
- multi-frame assets keep their original horizontal frame layout;
- one A-Discord replacement name maps to one semantic role unless two original
  sprites are proven to have identical dimensions, frame semantics, and widget
  composition.

Custom declarations remain in additive `interface/ADISCORD_*.gfx` files. The
mod must not introduce vanilla-named `country*.gfx` overrides.

The obsolete generic `window`, `panel`, `card`, `selected`, `template`, and
`line` assets are removed once no live GUI references them. Generated GUI files
are changed through their owning builders.

## Technology

### Research Overview

Research slots receive an exact-size technical console surface with a distinct
icon bay, title field, progress channel, and remaining-time area. Empty,
active, and completed presentations remain visually distinct without moving
their widgets.

The top and bottom overview panels retain broad uninterrupted metal surfaces.
Their internal controls are grouped through shallow recesses and narrow teal or
brass separators rather than complete nested frames.

### Technology Tree

The generated tree keeps all current graph positions and dependencies. Tree
backgrounds use a restrained technical-grid treatment with branch regions
visible at normal zoom.

Technology nodes receive separate assets for unavailable, available,
researching, researched, and branch states. Each asset preserves the live
icon/title/progress layout. State is communicated primarily by the outer edge
and lower status band, following the clarity of the TFR reference without
copying its art.

The technology detail window and its nested information surfaces use a lighter
steel writing area so effects, costs, and descriptions remain readable.

## Division Deployment

The deployment builder creates distinct fixed-size assets for reinforcement,
upgrade/replacement, supply, operations, garrison, division-template,
deployment-line, conveyor, end-line, priority, and location-control roles.

The left priority rows keep a dedicated icon recess and a separate horizontal
meter/control field. Their functional categories use narrow, muted color bands
rather than an identical olive frame around every child.

The template list keeps a large template-icon bay, a readable title field, and
separate action/control wells. Active, obsolete, and decommissioned states have
their own native-size frames.

Training and deployment conveyor backgrounds retain separate areas for the
division icon, progress and equipment state, location, and action buttons.
These separators must align with the unchanged GUI coordinates. Army HQ,
template locks, train/view buttons, progress behavior, and priority controls
remain mechanically untouched.

## Intelligence Agency

The main agency window uses a cold-steel shell with a purpose-built header,
agency branch strip, operative summary, and operations/cryptology tabs.

The header may include a new original monochrome espionage illustration or
procedural emblem owned by A-Discord. It must not reuse TFR imagery. The focal
art remains low-contrast behind controls and text.

Agency creation, operatives, branch upgrades, cryptology entries, operation
entries, selected entries, recruitment, operative cards, and mission bars each
receive role-specific assets of their native size and frame count. Paper
surfaces are eliminated only together with compatible pale text treatment; no
dark text may remain on a dark replacement.

Operations and cryptology tabs use a two-state angled or chamfered silhouette
with a clearly visible selected edge. Branch-upgrade rows retain separate title
and upgrade-card areas. Recruitment and operative windows reuse the same cold
steel hierarchy so nested windows no longer look like unrelated themes.

## Builder Architecture

`tools/lib/adiscord_ui_surfaces.py` remains a library of low-level primitives:
surface preparation, raised/recessed wells, partial rails, chamfered frames,
status bands, state-strip assembly, DDS serialization, and generated-output
checking. It no longer encourages a single framed rectangle as the final asset.

Each screen-specific builder owns:

- its semantic sprite manifest;
- the original sprite type, size, frame count, and source declaration fingerprint;
- exact drawing function and zone layout for every output;
- one-to-one GUI sprite substitutions;
- explicitly approved dark-surface font substitutions;
- its generated GFX declarations and owned DDS paths;
- a deterministic preview contact sheet used for human review but not loaded by
  the game.

## Tests

Tests are written before the corrected builder behavior. They must fail against
the current generic implementation and then pass after the correction.

Focused tests verify:

- no generic replacement sprite serves incompatible semantic roles;
- every fixed-size replacement matches the native dimensions and frame count;
- sprite declaration types and effect metadata match their source contracts;
- semantic zones contain the expected value separation and divider positions;
- small nested panels do not contain a full repeated outer frame;
- dark tabs and panels use approved pale fonts;
- every generated GUI reference resolves to an additive A-Discord GFX entry;
- the five dangerous vanilla-named GFX override paths remain absent;
- technology generator outputs are idempotent;
- deployment Army HQ and template-lock contracts still pass;
- intelligence source fingerprints still guard against upstream vanilla drift;
- each screen produces a deterministic contact sheet for visual inspection.

## Acceptance

Static acceptance requires all three builders to pass `--check`, focused UI,
technology, Army HQ, and GUI-contract tests to pass, followed by:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Static checks are insufficient for final acceptance. After a full HOI4 restart
and a fresh campaign at 1920x1080 and UI scale 1.0, review:

- technology overview and every technology-tree/detail state;
- deployment priority rows, templates, training lines, and Army HQ behavior;
- agency creation, branches, operations, cryptology, recruitment, operative
  cards, and mission windows;
- text contrast, clipping, scrolling, clickability, button states, tooltips,
  missing textures, and fresh mod-owned GUI/GFX log errors.

The implementation is not called visually complete until these runtime screens
have been inspected. If runtime screenshots expose a visual defect, the
corresponding semantic asset and regression test are corrected at the builder
source rather than patched by hand.

## Delivery Order

1. Shared semantic drawing primitives and contract tests.
2. Division deployment, because the current loss of row composition is most
   visible and mechanically sensitive.
3. Intelligence agency and nested operative windows.
4. Technology overview and generated tree states.
5. Cross-screen contact-sheet review, static gates, and runtime handoff.

Each stage is committed as an isolated verified path set. Existing unrelated
STP balance-of-power and decision work in the shared checkout remains untouched.
