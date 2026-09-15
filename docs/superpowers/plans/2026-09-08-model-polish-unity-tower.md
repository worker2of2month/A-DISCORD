# Model polish and Unity Tower animation

**Goal:** Finish the authored infantry surfaces and animate the existing Unity Tower collapse in HOI4.

**Design:** Preserve original user mesh/texture bytes. Apply export finishing only to the four authored infantry variants and eight shared weapons. Derive a separate segmented tower mesh from the existing pyramid, with partial upper-crown collapse and settled-damage clips. Keep the lower tiers and the opposite upper side intact; 17 irregular moving sections produce an expanded asymmetric roof breach. Bake localized soot and broken glazing into a 4096 diffuse atlas with 512 normal/specular maps, used only by the destruction actor. Replace its single ambient placement with one scripted actor, using the existing destruction flag and event guard.

**Constraints:** Keep HOI4 PDX mesh/animation contracts, original uniform palettes, shared weapon progression, protected province 16428, current collapse consequences and current event IDs. No unrelated staging or commits. Keep source generators and native output separate.

- [x] Inspect installed Darkest Hour Hindenburg entities, clips and scripted spawn/cleanup.
- [x] Finish gear bevel normals, open cloth/strap shells and militia scarf weighting; retain UVs and weapon transforms.
- [x] Export the segmented tower and both clips; check every sampled frame, weights, material references and final settlement.
- [x] Register tower states and timed native particles in mapitems; connect the existing guarded collapse and startup restore.
- [x] Validate package parity, JoroDox reads, focused lifecycle tests and full validator.
- [ ] Inspect fresh native HOI4 rendering when Windows input is available; distinguish offline evidence from runtime proof.

Source owners: `tools/assets/source/infantry_polish.py`, existing infantry exporters, and `tools/assets/source/WRK_unity_tower/`. Gameplay owners: existing Vorkerland events/effects/on_actions. Preserve the original pyramid entity and seven smoke locators for the intact actor.

Native reference: installed Darkest Hour `gfx/entities/DH_landmarks.asset`, `DH_landmarks.gfx`, `common/scripted_effects/_Landmarks_scripted_effects.txt`; base game `gfx/entities/landmarks.asset` and engine effect documentation. Reference model/animation geometry is not included in the output.

Verified: 12 polished native meshes with zero degenerate triangles; 17,768 infantry
frames; 1,264 weapon frames; 392 tower frames after re-import; 122 focused tests;
full `validate_tc.py --limit 300` exit 0 and `git diff --check` exit 0. JoroDox
parses the current tower and infantry packages; its Phong fallback cannot verify
the native PdxMeshAdvanced shader. Tower endpoint and separate ruins clip match.

The native game review remains blocked by the elevated On-Screen Keyboard window
(still present at final QA). Current HOI4 was launched before the package. No
campaign/save/mod-list changes were made. Recheck tower ground height, FX scale,
zoom and reload in a fresh process after the window is closed. In extreme militia
aim frame 140, part of the scarf tail is still occluded by the jacket/collar.
