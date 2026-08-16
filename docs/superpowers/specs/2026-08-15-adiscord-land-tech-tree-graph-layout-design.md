# A-Discord Land Technology Tree Graph Layout Design

## Status

Approved for inline implementation by the user on 2026-08-15. The Fire Rises
and Darkest Hour are layout references only; no technology IDs, localisation,
icons, or code are copied from either mod.

## Problem

The generated infantry and armour folders currently present most programmes as
long single lines. A previous horizontal-layout pass also transposed technology
coordinates while leaving the grid direction as `UP`. The visible year labels
and engine-rendered technology items therefore use different layout contracts,
which produces the large icon/year displacement shown in the user's screenshot.

## Reference contract

- TFR horizontal trees use `format = "LEFT"`, keep the programme lane in
  technology `position.x`, and put the time slot in `position.y`.
- Darkest Hour vertical trees use `format = "UP"`, with the conventional
  horizontal lane in `position.x` and chronological row in `position.y`.
- Both keep technology grid boxes as direct children of the folder container;
  decorative backgrounds and year text may be nested separately.

## Chosen design

Generated folders have an explicit orientation contract instead of transposing
coordinates ad hoc:

- horizontal folders: `format = "LEFT"`, `position.x = programme lane`,
  `position.y = chronological slot`;
- vertical folders: `format = "UP"`, `position.x = programme lane`,
  `position.y = chronological slot`.

The chronological slot remains the generator's stable compact year index. The
year label for a horizontal slot is derived from the same slot and grid origin,
so labels and technology centres cannot drift independently.

The four major infantry programmes and three major armour programmes become
real three-lane DAGs:

- small arms: receivers, ammunition, and optics converge on the 2180 service
  rifle;
- squad weapons: firepower and command/sensor lines synthesize autonomous and
  swarm fire support;
- protection: body protection, combat medicine, and environmental systems
  converge on the late assault kit;
- special forces: urban assault, reconnaissance, and airborne insertion
  converge on augmented special forces;
- reconnaissance armour: mobility, sensors, and autonomy converge on the
  autonomous reconnaissance screen;
- combat armour: protection, fire control, and autonomy converge before the
  existing permanent late specialization choice;
- heavy armour: survivability, power, and engineering converge on autonomous
  breakthrough, then siege firepower and coordination rejoin at the capstone.

Short three-node APC/IFV, combat-medicine, and unmanned-ground programmes remain
compact side lines. Cross-grid dependencies remain dependency-only because HOI4
does not reliably draw paths between separate grid boxes.

## Geometry rules

- Each main programme has exactly one root and all nodes are reachable.
- Every edge moves to a strictly later start year.
- Main programmes use at least three visible lanes and contain a real fork plus
  either an AND synthesis or the existing explicit XOR specialization.
- Grid height is derived from its maximum lane; titles remain above their own
  grid and grids are separated by a fixed gap.
- Horizontal year text and technology positions share one chronological-slot
  function and one slot width.
- `armour_folder` and `nsb_armour_folder` receive identical technology
  coordinates and grid orientation.

## Verification

Automated tests must fail if horizontal folders revert to `UP`, if horizontal
technology output places time in `x`, if a named main branch becomes linear, if
a synthesis loses an incoming dependency, or if the two armour folders diverge.
The builder is run in check mode before apply, then applied twice with identical
hashes, followed by focused tests, the technology validator, full TC validation,
`git diff --check`, and Russian localisation BOM verification. A fully restarted
HOI4 process and fresh campaign screenshot remain required for runtime/UI proof.
