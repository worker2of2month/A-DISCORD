# Vorkerland Urban VP Density Design

## Goal

Add victory points to genuine Vorkerland urban settlements that currently have
no VP, without deleting, moving, or changing any existing victory point.

## Selection rule

- Treat directly touching `urban` provinces as one city cluster.
- If a cluster already contains any VP, add nothing to that cluster. Large
  cities therefore retain the usual single central VP rather than receiving a
  marker on every urban province.
- If a disconnected urban cluster contains no VP, add exactly one VP to it.
- The current map audit finds two such clusters: province 16588 in state 310
  and province 16624 in state 318.

## Values and names

- Add province 16588 at value 1 and keep its existing Russian localisation.
- Add province 16624 at value 1 and keep its existing Russian localisation.
- Preserve all existing VP values, order, and localisation keys.

## Ownership and generation

The exact Vorkerland theatre manifest remains authoritative. Add both points
to `tools/lib/adiscord_vorkerland_theatre_manifest.py`, update package totals,
and regenerate state history through `build_adiscord_new_states.py
--apply-vorkerland-vps`. Do not hand-edit state history or Russian
localisation.

## Verification

Add a focused contract test that proves the two new VPs exist and the relevant
pre-existing centres remain unchanged. Then run the focused new-state tests,
the Vorkerland and new-state validators, the builder check, `validate_tc`, and
`git diff --check`. Verify the Russian localisation retains its UTF-8 BOM and
prove a second targeted generator run is idempotent.
