# Country close-air-support models

`../build_country_cas.py` owns the nine CAS meshes, their idle animations and
the separate `NOD_cas_*`, `STP_cas_*`, `VAL_cas_*` material atlases. It uses
Blender and the installed IO PDX Mesh exporter. All `.blend` files contain
packed textures and editable geometry, skeletons, locators and animations.

The existing country-vehicle registry uses these historical filenames:

| Countries | Mesh prefix | Tier I | Tier II | Tier III |
| --- | --- | --- | --- | --- |
| STP, NOD | NOD | NOD_early_cas | NOD_cas | NOD_future_cas |
| STS, SRP | STP | STP_early_cas | STP_cas | STP_future_cas |
| VAL | VAL | VAL_early_cas | VAL_cas | VAL_future_cas |

Visual levels 0, 1 and 2 select these tiers. Tier I is piston-powered;
tier II has external jet engines; tier III adds revised engines, canards,
sensor fairings and updated weapons. STP/NOD retain a heavy straight-wing
shape, STS has swept wings and twin fins, and VAL uses twin tail booms.
The existing technology/equipment progression and statistics are unchanged.

The `aircraft_cas_{family}_{tier}.png` files are the 176x72 RGBA technology
and production cards. Their families are `VAL`, `party` (STP/NOD), and `STS`
(STS/SRP). `build_adiscord_technology_system.py` converts them losslessly to
DDS and owns their GFX routes; tier 3 repeats for later models. Use
`python -B -m tools.builders.build_adiscord_technology_system --aircraft-icons-only --aircraft-role cas --check`
before `--apply`, then repeat `--check`. The PNGs are authored artwork, separate
from the rendered mesh previews.

Run from the repository root:

```powershell
python -B -m tools.assets.source.build_country_cas --prepare
& 'D:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --python tools/assets/source/build_country_cas.py -- --build
python -B -m tools.assets.source.build_country_cas --check
python -B -m tools.assets.source.build_country_cas --apply
python -B -m tools.assets.source.build_country_cas --check
python -B -m unittest tools.tests.test_adiscord_country_vehicles.CasProgressionTests
```

Before installation, `--check` reports expected differences and exits with 1.
After installation it must report an empty list. Packaging only writes the
files listed in this package's verification manifest; shared fighter/tank
textures and entity registries are outside its ownership.

`--build --names NAME ...` rebuilds selected models and reimports the native
exports. `--render --names NAME ...` only rerenders native exports. Preview
PNGs show the reimported `.mesh`, not the original Blender geometry.

Verification checks geometry, finite attributes, texture references, rigid
skinning slots, weapon locators, animation loops and propeller movement. The
manifest records mesh/animation/texture and editable-source SHA-256 hashes.
This does not verify HOI4 rendering: a full game restart and fresh campaign
are required for that check.
