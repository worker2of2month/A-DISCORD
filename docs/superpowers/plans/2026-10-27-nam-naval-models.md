# NAM naval models

Use the actual NAM general portraits as the visual reference: olive-grey uniform, dark green facings, brown leather and restrained brass. Preserve native skeletons, weapon attachments and animations. The marine retains the NAM line infantry body and kit, with a flotation collar and sealed landing bag.

1. Extend `build_headquarters.py` with a NAM profile: textured olive uniform with a closed collar and peaked cap, dark green facings, leather cross belt and map case. Keep existing RUS output unchanged. Register NAM and its cosmetic tags in the existing HQ registries.
2. Add the NAM variant to the specialist model family through `tools/assets/source/build_specialists.py`. Retain the NAM body, trousers and field kit, replace the helmet and chinstrap with a low black beret, and add a dark marine jacket, flotation collar and sealed landing bag. Preserve the native body normals, rig and attachments. Add a marine-only model pool so ordinary infantry retains its field model.
3. Extend `build_country_aircraft.py` with selective verified packaging. Refine NAM's six aircraft with naval paint, service markings and deck equipment; preserve other families byte-for-byte.
4. Register generated ownership. Build outside the runtime directories, inspect native reimports and rendered poses, run dry checks, apply verified packages, then confirm idempotence.
5. Run personnel and aircraft tests, `python -B tools/validate_tc.py --limit 300` and `git diff --check`. Record final hashes and native animation checks. In-game verification is performed by the user; keep it separate from Blender verification.

Editable model sources belong in `tools/assets/source/`; native reports belong in `docs/development/model-verification/`. Temporary review renders are removed after inspection. Existing unrelated changes remain untouched.
