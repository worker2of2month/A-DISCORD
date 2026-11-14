# Great Shift industrial landmark

The Oilworkers Union ending unlocks construction in province 11219, state 723
(Loren Coast). NAM must own and control the site. The landmark does not transfer
territory or change the political ending.

## Construction contract

- Each of two phases costs 75 political power and 750 treasury, occupies one
  existing NAM regional project slot, and reserves five civilian factories for
  a 360-day mission. Foundations appear when the first phase is paid; assembly
  replaces them at its completion. The second phase installs the completed model.
- Additional crews take 30 days and shorten the active mission by 30 days for
  25 political power and 150 treasury. Engineering preparation takes 45 days and
  saves 60 days for 50 political power and 350 treasury. Only one support order
  can be outstanding. Orders require more than 120 days remaining and cannot
  carry their result into a later phase.
- Losing ownership, control or independence cancels the current phase and refunds
  its state escrow and any outstanding support order. Completed structural stages
  remain. Restarting a cancelled phase pays its full price again.
- Commissioning adds three shared slots, two civilian factories, one refinery
  and 15 victory points in province 11219, named "Great Shift". Delivery rechecks
  ownership and building caps. The consumed receipt and final stage prevent
  duplicate buildings or victory points.
- The completed complex installs a permanent state modifier: +100% construction
  speed, +100% shared building slots, -50% factory energy consumption and +5 local
  supplies. It belongs to state 723 and remains active after a change of owner.

State variable `NAM_combine_stage` is authoritative. Actor 610723 is created from
state 723, replaced at stage boundaries, and reconstructed by the shared startup
hook for ordinary save/load. No daily visual reconciliation is used.

## Native assets

Builder: `python -B -m tools.builders.build_adiscord_nam_combine`.
Run `--check` before `--apply`, then `--check` again. `--preview` is opt-in.
The builder owns only its marked registry sections and the files named in
`NAM_combine.json`. Three construction meshes share one material and three
1024-pixel DDS textures with mipmaps. Each mesh is exported and reimported through
the native mesh exporter; reports explicitly distinguish this from game testing.

The footprint is 126 by 82 authoring units, placed at x=3657, map-y=653,
height=11.61, scale=0.09 and rotation=0. Its centre is in province 11219;
the foundation remains within state 723 and covers the sampled terrain.
Its buried retaining foundation extends below the visible ground plane.

Only the completed entity emits smoke. Six entity locators meet the exported
chimney rims at heights 44 and 36; native reimport verification checks their
alignment. A local particle alias uses the base game's continuous
`factory_smoke_file` at scale 12 to compensate for the actor's 0.09 scale.
Each emitter starts once with the idle state and belongs to its actor, so actor
replacement removes it. The entity bounds include the rising smoke. Construction
stages and the unplaced reserve have no emitters. Actual plume appearance still
requires inspection in the running game.

The smaller factory is retained as `ADISCORD_NAM_combine_reserve.mesh`, with
editable source `tools/assets/source/buildings/NAM/combine/reserve.blend`.
It has a registered entity but no placement or gameplay caller.

## Verification boundary

Focused tests cover native output hashes, terrain and province placement,
construction payments, cancellation and restart, support-order isolation,
mission timeout semantics, synchronized mission tokens, building caps and
single-shot VP delivery. The source and asset checks do not verify the native
mission modifier, screen appearance or actor persistence in a running campaign.
Those checks require the user's manual game session.
