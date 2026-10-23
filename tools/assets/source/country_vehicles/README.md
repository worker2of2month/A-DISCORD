# Country vehicles

`package_vehicles.py` owns the shared mesh, entity and animation registries.
`build_motorized.py` owns the four wheeled APC meshes, textures, animation
clips and packed Blender scenes in this family. It uses the native geometry
helpers in `build_country_cas.py` and `build_taran.py`.
`build_idle.py` owns the shared idle motion for these four APCs, the VAL/NOD/STP
tanks and STS Taran. The APC and Taran geometry builders call its exporter.

- VAL: long, low eight-wheel wedge hull with overlapping side skirts and a wide,
  flat faceted turret; blue-grey panels.
- STP: short four-wheel chassis with a raised cabin, rear drum turret and commander's
  cupola; burgundy panels and brass trim.
- STS: six-wheel chassis with a separate engine hood, driver's cab and troop box;
  open shielded weapon mount, olive paint and external kit.
- NAM: wide eight-wheel amphibious hull with a boat bow, side floats and stern jets;
  rear asymmetric turret with an offset optic housing, teal paint and ochre strips.

The existing `ADISCORD_mechanized_infantry` battalion uses `sprite = mechanized`.
National and cosmetic identities route its visual levels and carrier equipment
to their APC. Motorized aliases also resolve to the same model; these aliases
do not create a battalion or change equipment stats. Other countries retain
their existing fallback.

`gfx/interface/equipmentdesigner/graphic_db/ADISCORD_country_vehicles.txt` registers
the national model pools for the division designer. Each pool is restricted to
`ADISCORD_mechanized_infantry`; both its rifle and carrier archetype select the
same national vehicle with escort. Ordinary rifle infantry and headquarters do
not match these pools. Root keys are registered country tags, so cosmetic state
names do not need separate equipment-database entries. `package_vehicles.py`
generates this database together with the entity aliases.

The root entity uses the native `motorized_frame_mesh`. The vehicle and existing
national rifle infantry are separate attachments, with idle, move, retreat,
attack, defend, support attack, training and death states. The frame already
scales its vehicle attachment to 0.7 in idle; the APC mesh scale is 0.95 and the
escort inherits the national infantry entity's scale without an additional
override. The native unit presentation still needs an in-game check.

Idle cycles last 8-11.5 seconds. Turrets scan six degrees to either side, guns
adjust elevation and the hull has a small engine vibration. Taran uses only
elevation within its fixed mount. The root, wheels and track links stay still.
Native reimport checks position and velocity continuity at the loop seam.

To update only idle motion while preserving installed meshes, paint, movement
and attack clips:

```powershell
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --threads 4 --python tools/assets/source/country_vehicles/build_idle.py -- --build
python -B -m tools.assets.source.country_vehicles.build_idle --check
python -B -m tools.assets.source.country_vehicles.build_idle --apply
python -B -m tools.assets.source.country_vehicles.build_idle --check
python -B -m unittest tools.tests.test_adiscord_country_vehicles.GroundVehicleIdleTests
```

This stages exports in the system temporary directory `adiscord-vehicle-idle`,
updates the idle action in existing APC Blender scenes, and records the native
input hashes and motion measurements in
`docs/development/model-verification/vehicle_idle.json`. Rebuild idle after
changing any of its input meshes; the installer rejects changed input hashes.

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
