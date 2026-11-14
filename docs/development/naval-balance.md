# Starting fleets and coastal control

The starting campaign uses small surface groups for local landings. The terrain
baseline is converted through the native `DOMINANCE_CONTROLLED_THRESHOLD_RATIO`
of 0.60: displayed minimum = baseline * 0.60 / (1 - 0.60).

| Terrain | Script baseline | Displayed minimum |
| --- | ---: | ---: |
| Fjords and archipelagos | 16 | 24 |
| Shallow sea | 20 | 30 |
| Ocean | 40 | 60 |
| Deep ocean | 80 | 120 |
| Strongest Current | 400 | 600 |

`common/terrain/00_terrain.txt` owns these baselines. The Current keeps its
terrain modifiers and all five strategic-region definitions. The global 60%
control ratio is not overridden. Enemy fleets can still contest a crossing.

Every combat-ship archetype in `ADISCORD_convoy_equipment.txt` declares the native
`naval_dominance_factor`: escorts 20, light cruisers 35, heavy cruisers 60,
submarines 4, battleships 150 and carriers 120. Models inherit their archetype's
value. Range, speed, mission, intelligence and other native modifiers determine
the actual contribution. Two 2155 escorts provide 40 base hull points before
those modifiers; their range and speed exceed the native neutral values.
This is a planning budget for uncontested local waters, not guaranteed control
against an enemy or with ineffective missions.

## Fleet allocation

`tools/lib/adiscord_starting_navies.py` owns the added rosters. Counts below are
heavy cruisers / light cruisers / escorts / submarines. Existing NAM (40),
AZH (25), EFL (15), STP (20), NOD (20) and VAL (16) fleets retain their authored
ships and task forces.

| Country | Added starting roster | Minimum convoy reserve |
| --- | --- | ---: |
| IVN | 2 / 4 / 10 / 4 | 80 |
| WRK | 1 / 2 / 6 / 3 | 60 |
| SHL | 0 / 2 / 6 / 2 | 60 |
| WIT | 0 / 2 / 8 / 2 | 60 |
| RVN | 0 / 2 / 6 / 2 | 60 |
| YPR, TFF | 0 / 1 / 6 / 1 | 40 |
| IIA, MRV, CHD | 0 / 1 / 6 / 1 | 50 |
| PIO | 0 / 0 / 6 / 0 | 60 |
| COF, SFR, FLR, PRR, ULV, LUR, OLR | 0 / 0 / 6 / 0 | 40 |
| DAN, BCM, EVR | 0 / 0 / 4 / 0 | 40 |

Each added fleet has two independent surface groups and, where present, a
separate submarine group. Heavy cruisers retain at least three escort ships
each. Large industrial countries have cruiser forces; island and port leagues
rely on escorts. Polar routes require concentrating ships more than shallow
coastal crossings do. Starting reserves above the listed minima are preserved.

All bases are owned, built ports with physical access to navigable sea. Antolla
uses its existing canal connection. SHL's base is at Safir province 3234 in
state 730; WRK's is at Remmel province 4443 in state 200. Each has a level-2 base
and one dockyard, owned by `build_adiscord_new_states.py`. RUS starts inland
and receives no stranded ships. Successor tags and RUS may use native naval AI
templates when they obtain a coast and ships through their campaign routes.

Naval technology grants precede the OOB load. The `naval` profile supplies
`ADISCORD_tech_restored_dockyards`, which enables invasion transport; countries
with light cruisers also receive `naval_taskforce`. Transport-capable ordinary
infantry can land without requiring the separate marine recruitment programmes.
The AI's patrol minimum is two escorts and its requested dominance margin is
20 points. Native port, range, convoy, preparation and enemy-control requirements
still apply. Diplomacy remains limited to the mod's scripted war routes.

## Rebuilding and checks

The naval builder owns only marked fleet sections and country-history naval
grants/convoy minima. It preserves land armies, production queues and political
history. The remainder-country generator calls the same renderer. No recurring
fleet grants or save migrations are used.

```text
python -B -m tools.builders.build_adiscord_starting_navies --check
python -B -m tools.builders.build_adiscord_starting_navies --apply
python -B tools/build_adiscord_new_states.py --check-state-metadata 200 --check-state-metadata 730
python -B tools/build_adiscord_technology_system.py --check-starting-profiles
python -B -m unittest tools.tests.test_adiscord_naval_programmes
```

The tests cover owned ports and canal connectivity, pre-OOB hull availability,
invasion transport, convoy reserves, formation screens, AI eligibility and
idempotent regeneration. In-game validation needs a new campaign: inspect the
fleet and hull contribution, put surface groups on the relevant missions, let
control accumulate and test a landing through every sea zone on the route.
