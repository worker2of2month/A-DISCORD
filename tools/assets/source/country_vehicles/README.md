# Country tanks and aircraft

Nine native models cover VAL, NOD and STP: one main battle tank, fighter and
ground-attack aircraft per country. STS and SRP retain the STP set during player
handoffs. These are country appearances, not separate equipment statistics or
a complete visual progression for every future chassis.

`build_vehicles.py` owns geometry, rigid skinning, locators and native animations.
`package_vehicles.py` owns DDS compilation and the two country vehicle registries.
Edit these sources rather than the generated `.mesh`, `.anim`, `.dds`, `.gfx`
and `.asset` outputs. All countries share these two builders and this folder.

## Materials and geometry

`weathering_source.png` contains four flat material sources: armor paint,
aircraft skin, muddy tracks and soot-covered metal. The compiler maps these
into separate tank and aircraft atlases, applies each country's muted palette
and adds markings from the existing flags. Tanks receive the rougher armor and
track treatment; aircraft use the panelled skin. All DDS maps have mip chains.
The advanced shader uses the HOI4 GA normal encoding. Glass remains opaque to
avoid transparent sorting artifacts at map scale.

Each model uses one material. Tanks have 46 bones: opposite track shoes and
road wheels share straight-line movement, while hull, turret and gun remain
separate. The four-second movement clip closes its track loop; the attack clip
recoils the gun and settles the hull. Flight trajectories and battle maneuvers
remain native engine scenes, so the six jets need only a rigid idle clip.
Do not treat a stationary aircraft idle as a missing flight-path animation.

Rigid skins declare one influence per vertex but retain the native four-slot
storage layout. All four indices address the same valid bone, with weights
`1, 0, 0, 0`: the game shader fetches matrices even for zero-weight slots.
The verifier checks padding indices as well as the weighted influence.

The tank points forward along Blender -Y / Clausewitz -Z. Its `barrel` locator
follows the gun; exhaust and track emitters follow their own assembly. Aircraft
provide `root`, `gun1`, `gun2` and `bomb` locators for the native plane states.

## Build and verify

Pillow is required for DDS preparation. Background Blender uses the existing
IO PDX Mesh exporter and the compatibility helper in `STP_regulars/export_verify.py`.

```powershell
python tools/assets/source/country_vehicles/package_vehicles.py --prepare
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tools/assets/source/country_vehicles/build_vehicles.py
# Optional subset: append -- --names VAL_tank NOD_tank STP_tank
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tools/assets/source/country_vehicles/build_vehicles.py -- --preview tank
# Repeat with --preview fighter and --preview cas for the other lineups.
python tools/assets/source/country_vehicles/package_vehicles.py --check
python tools/assets/source/country_vehicles/package_vehicles.py --apply
python tools/assets/source/country_vehicles/package_vehicles.py --check
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tools/assets/source/country_vehicles/build_vehicles.py -- --verify-installed
python -B -m unittest tools.tests.test_adiscord_country_vehicles
python -B -m unittest tools.tests.test_validate_adiscord_force_designs -k air
```

An initial `--check` exits 1 if packaging changes are pending. The native verifier
reimports the mesh and each animation, checks geometry, weights and referenced
textures, samples deformed vertices, and records both motion and loop closure.
`verification.json` binds these results to the installed asset hashes. Editable
`.blend` files and lineup renders contain reimported native geometry.

## Selection and engine verification

The existing air subunits and their archetypes use distinct `ADISCORD_fighter`
and `ADISCORD_cas` sprites. Their generic aliases preserve native light-plane
fallbacks for other countries. Country aliases and concrete equipment aliases
select the authored models. Tank aliases cover the medium-armor sprite and the
three existing main battle tank equipment tiers; light and heavy tank classes
retain their own appearances.

Static validation cannot prove Clausewitz selection, shaders or particles.
Before a cold launch, record the source hashes of both registries, both air
scripts and the packaged assets. In a fresh campaign verify VAL/NOD/STP tank
movement and firing, fighter/CAS selection in the same air region, texture
appearance in daylight and snow, unit zoom scales, and STS/SRP handoff. Inspect
fresh logs for missing entities, meshes, animations, textures and locators.
Do not use hot reload in an existing campaign as final visual evidence.
