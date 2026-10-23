# Country vehicles

`package_vehicles.py` owns the shared mesh, entity and animation registries.
`build_motorized.py` owns the five wheeled APC meshes, textures, animation
clips and packed Blender scenes in this family. It uses the native geometry
helpers in `build_country_cas.py` and `build_taran.py`.
`build_idle.py` owns the shared idle motion for these five APCs, the VAL/NOD/STP
tanks and STS Taran. The APC and Taran geometry builders call its exporter.

- VAL: long, low eight-wheel wedge hull with overlapping side skirts and a wide,
  flat faceted turret; blue-grey panels.
- STP: short four-wheel chassis with a raised cabin, rear drum turret and commander's
  cupola; burgundy panels and brass trim.
- STS: six-wheel chassis with a separate engine hood, driver's cab and troop box;
  open shielded weapon mount, olive paint and external kit.
- NAM: wide eight-wheel amphibious hull with a boat bow, side floats and stern jets;
  rear asymmetric turret with an offset optic housing, teal paint and ochre strips.
- NOD: six large wheels with separate angled mudguards, a continuous sloped hull,
  rear troop ramp and compact enclosed turret; slate-blue armour and pale bands.

The existing `ADISCORD_mechanized_infantry` battalion uses `sprite = mechanized`.
National and cosmetic identities route its visual levels and carrier equipment
to their APC. Motorized aliases also resolve to the same model; these aliases
do not create a battalion or change equipment stats. Other countries retain
their existing fallback.

`gfx/interface/equipmentdesigner/graphic_db/ADISCORD_country_vehicles.txt` registers
national model candidates for the division designer. Each pool matches only
`infantry_equipment` used by `ADISCORD_mechanized_infantry`. Ordinary rifle
infantry and headquarters do not match these pools. Root keys are registered
country tags, so cosmetic state names do not need separate database entries.
`package_vehicles.py` generates this database together with the entity aliases.

The native designer collects models from available domestic and foreign
equipment. A mechanized carrier can select its origin country's models; rifle
equipment retains the division owner's country. Candidate entity names are
deduplicated before priority insertion, so a later equipment query cannot
promote an already collected model. The pool therefore uses the root APC entity
only through rifles, separately from the legacy carrier aliases. Do not also
register that root entity for carriers: it would consume the rifle candidate
at the carrier's visual technology level. Pool weight orders models within an
equipment query; it does not replace the designer's equipment priority.

For the carrier-2163 and rifle-2156/2163 combination, the separate national
candidate has visual technology level 2/3 against the carrier's level 1.
This is an offline selection contract, not a rendered-game verification or a
rule overriding every possible imported equipment tier or manually selected
division model. NOD uses its own APC and national infantry escort through the
same country routes, independently of human or AI control.
Native addresses, source hashes and the replay's limits are recorded in
`docs/development/model-verification/country_apc_selection.json`.

The root entity uses the native `motorized_frame_mesh`. The vehicle and existing
national rifle infantry are separate attachments, with idle, move, retreat,
attack, defend, support attack, training and death states. The frame already
scales its vehicle attachment to 0.7 in idle; the APC mesh scale is 0.95 and the
escort inherits the national infantry entity's scale without an additional
override. The native unit presentation still needs an in-game check.

Idle cycles last 8-12 seconds. Turrets scan six degrees to either side, guns
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
For a single APC, pass `--tag NOD` (or another listed tag) to both `--prepare`
and `--build`. Unselected installed exports are checked against their report
and preserved byte-for-byte. Run the shared idle builder after installing a
changed mesh to refresh its independent motion verification.
Runtime exports go to `gfx/models/units/ADISCORD_country_vehicles`; the SHA-256
and native reimport report goes to `docs/development/model-verification/country_apc.json`.
Packed editable scenes stay alongside this README. Temporary renders go only to
`docs/development/previews/country-apc` and are removed after visual review.

Native verification checks indices, finite geometry, UVs, material paths, all
four rigid skin slots, every wheel's movement, gun recoil and animation seams.
It does not confirm engine loading or the appearance of the combined entity.
Fully restart HOI4 with the final hashes and inspect a new campaign and fresh
logs before treating the runtime result as verified.
