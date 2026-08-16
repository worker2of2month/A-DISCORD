# A-Discord Economic-System Icon Pilot Design

**Date:** 2026-08-16

**Status:** Approved visual direction; awaiting written-spec review

**Scope:** Three preview icons only

## Goal

Create an original, coherent pilot set of three 64x64 icons for the existing
A-Discord economic-system laws. The pilot tests whether a compact embossed
metal-medallion language remains distinct and readable in the Hearts of Iron IV
interface before the remaining six economic-system icons are commissioned.

The three laws are:

- `ADISCORD_economic_system_mixed`
- `ADISCORD_economic_system_planned_bureaucratic`
- `ADISCORD_economic_system_oligarchic_clan`

## Visual Language

Each icon is an original circular medallion on a genuinely transparent canvas.
The shared construction uses a dark gunmetal outer rim, a recessed charcoal
field, a large silver-grey embossed symbol, restrained edge highlights, and one
muted accent colour. The rendering should feel like a compact strategy-game UI
emblem without reproducing any supplied reference asset or identifiable logo.

The silhouette must survive reduction to 64x64. Use one central metaphor, broad
forms, strong value separation, and no tiny lettering or decorative clutter.
Exclude words, numbers, flags, national emblems, real-world corporate marks,
watermarks, and elements touching the canvas edge.

## Icon Concepts

### Mixed economy

A balanced scale is the primary silhouette. One pan carries a compact industrial
gear and the other a simple coin disc, representing regulated coexistence of
public coordination and private exchange. A restrained oxidised-teal accent
appears behind or around the balance pivot; the metal symbols remain dominant.

### Planned-bureaucratic economy

A rigid administrative clipboard or ledger grid stands in front of two broad
factory chimneys. Straight ruled divisions and an aligned composition convey
central planning, while a muted dark-red accent marks the plan itself. Avoid
fine writing: the ledger is represented only by large geometric rows.

### Clan-oligarchic economy

Three dark formal sleeves converge from different directions and grip a central
gold coin shaped or edged like an industrial gear. The shared grasp communicates
concentrated ownership and cartel bargaining. Hands and sleeves must read as one
bold radial symbol rather than a detailed human scene.

## Deliverables

For each concept, generate one high-resolution transparent source image through
the built-in image-generation tool. Preserve those sources under
`tools/assets/source/economic_system_laws/` with stable ASCII filenames.

Create preview derivatives at exactly 64x64 pixels and a labelled comparison
sheet showing both the large sources and the final-size icons. Keep all pilot
art outside active GFX declarations: this phase does not replace the current
fallback textures or modify gameplay, localisation, or law definitions.

## Acceptance Criteria

- All three requested concepts are present and visually distinct.
- The set shares one rim, lighting direction, material language, and rendering
  density.
- Every final preview is exactly 64x64 with preserved transparency.
- The main metaphor remains recognisable at 100% display size.
- There is no text, flag, logo, watermark, clipped subject, or opaque square
  background.
- No existing mod asset or unrelated dirty file is overwritten.
- The three source prompts and saved output paths are reported for review.

## Follow-up Boundary

Connecting approved icons to `interface/ADISCORD_ideas.gfx`, producing DDS game
assets, adding generator ownership, and creating the remaining six economic
system icons are separate follow-up work. They begin only after the pilot is
visually accepted.
