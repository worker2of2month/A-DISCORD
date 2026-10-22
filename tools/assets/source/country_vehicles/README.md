# Country vehicles

`package_vehicles.py` owns the shared mesh, entity and animation registries.
`build_motorized.py` owns the four wheeled APC meshes, textures, animation
clips and packed Blender scenes in this family. It uses the native geometry
helpers in `build_country_cas.py` and `build_taran.py`.

- VAL: low eight-wheel hull, angular remote weapon station, blue-grey panels.
- STP: taller six-wheel hull, enclosed cupola, burgundy panels and brass trim.
- STS: eight-wheel hull, shielded weapon station, olive paint and external kit.
- NAM: eight-wheel hull, enclosed weapon station with raised optics, teal paint,
  ochre identification strips and rear ventilation housings.

The existing `ADISCORD_mechanized_infantry` battalion uses `sprite = mechanized`.
National and cosmetic identities route its visual levels and carrier equipment
to their APC. Motorized aliases also resolve to the same model; these aliases
do not create a battalion or change equipment stats. Other countries retain
their existing fallback.

The root entity uses the native `motorized_frame_mesh`. The vehicle and existing
national rifle infantry are separate attachments, with idle, move, retreat,
attack, defend, support attack, training and death states. The frame already
scales its vehicle attachment to 0.7 in idle; the APC mesh scale is 0.95 and the
escort scale is 0.25. The native unit presentation still needs an in-game check.

## Rebuild

Run from the repository root, using Blender 5.2 with the installed IO PDX Mesh
extension. The exporter compatibility shim is process-local.

```powershell
python -B -m tools.assets.source.country_vehicles.build_motorized --prepare
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 4 --python tools/assets/source/country_vehicles/build_motorized.py -- --build
python -B -m tools.assets.source.country_vehicles.build_motorized --check
python -B -m tools.assets.source.country_vehicles.build_motorized --apply
python -B -m tools.assets.source.country_vehicles.build_motorized --check
python -B tools/assets/source/country_vehicles/package_vehicles.py --check
python -B tools/assets/source/country_vehicles/package_vehicles.py --apply
python -B tools/assets/source/country_vehicles/package_vehicles.py --check
python -B -m unittest tools.tests.test_adiscord_country_vehicles.ArmoredPersonnelCarrierTests
```

The first check reports pending changes without writing them. The final check
must be empty. Staging uses the system temporary directory `adiscord-country-apc`.
Runtime exports go to `gfx/models/units/ADISCORD_country_vehicles`; the SHA-256
and native reimport report goes to `docs/development/model-verification/country_apc.json`.
Packed editable scenes stay alongside this README. Temporary renders go only to
`docs/development/previews/country-apc` and are removed after visual review.

Native verification checks indices, finite geometry, UVs, material paths, all
four rigid skin slots, every wheel's movement, gun recoil and animation seams.
It does not confirm engine loading or the appearance of the combined entity.
Fully restart HOI4 with the final hashes and inspect a new campaign and fresh
logs before treating the runtime result as verified.
