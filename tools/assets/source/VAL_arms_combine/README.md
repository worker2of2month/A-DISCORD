# Kefreyt arms combine

`build_combine.py` owns the native mesh, three shared DDS maps and the marked
Kefreyt sections in `mapitems_custom.gfx`, `mapitems_custom.asset` and
`map/ambient_object.txt`. Edit the builder rather than its packaged output.
The editable Blender scene and preview use geometry reimported from the native
mesh. The model uses one material, no skeleton and no recurring particle emitters.

```powershell
python tools/assets/source/VAL_arms_combine/build_combine.py --prepare
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tools/assets/source/VAL_arms_combine/build_combine.py -- --build
python tools/assets/source/VAL_arms_combine/build_combine.py --check
python tools/assets/source/VAL_arms_combine/build_combine.py --apply
python tools/assets/source/VAL_arms_combine/build_combine.py --check
python -B -m unittest tools.tests.test_adiscord_landmarks
```

Blender uses the existing IO PDX Mesh exporter and the material compatibility
helper in `STP_regulars/export_verify.py`; texture preparation requires Pillow.
An initial `--check` reports pending changes and exits with code 1.

The 32 x 22 foundation is placed at scale 0.20 inside state 48. Ambient Y is
absolute terrain height, while the mesh extends below its origin to avoid a
gap on uneven terrain. Keep the footprint test synchronized with authored
dimensions if the model changes.

Gameplay belongs to `common/buildings/01_landmark_buildings.txt` and the starting
building in `history/states/48-Depoitodron.txt`. Its two 5% modifiers affect only
that state through the native building system; no country reward or periodic
script is installed. Localisation stays in the existing building files.

For game verification, hash the installed mesh, textures, entity registrations,
ambient placement, building definition, state and localisation before a cold
launch. Start a new campaign as VAL and inspect the factory from several map
angles, ground contact, state building tooltip and both regional modifiers.
The native-mesh preview and static tests do not prove engine rendering or UI.
Existing saves do not acquire a newly authored state-history building.
