# Vlad Macri State Rebalance

## Goal

Raise the visible population and development of every state transferred to Vlad Macri's Republic of Ebern while keeping it below the industrial and demographic weight of Technograd.

## Scope and coupling

The change covers states 197 and 311-314, the complete territory transferred by `ADISCORD_vorkerland_setup_eba`. State 311 belongs to WRK before the collapse; states 197 and 312-314 belong to VLA. Updating state history therefore strengthens those starting owners before EBA is created. This is an accepted consequence of making the population visible in the states themselves.

Resources, borders, ownership, cores, VP values, collapse diplomacy, and country ideology remain unchanged.

## State profiles

| State | Population | Category | Infrastructure | Civilian factories | Military factories | Air base | Local supplies |
|---|---:|---|---:|---:|---:|---:|---:|
| 197, Ebern | 1,050,000 | `large_town` | 4 | 3 | 1 | 1 | 4.5 |
| 311, Felden | 750,000 | `town` | 3 | 1 | 0 | 0 | 2.5 |
| 312, Noyen | 650,000 | `town` | 3 | 1 | 1 | 0 | 3.0 |
| 313, Estervik | 550,000 | `town` | 3 | 1 | 0 | 0 | 3.0 |
| 314, Linden | 550,000 | `town` | 3 | 1 | 0 | 0 | 3.0 |

The combined EBA territory has 3,550,000 population, seven civilian factories, two military factories, one air base, and 16.0 local supplies. It remains well below state 105 Technograd at 9,800,000 population, seven civilian factories, five military factories, and three air bases.

## Collapse military balance

EBA keeps four three-battalion militia divisions. Their placement changes from four divisions stacked at the old south-eastern anchor to two in Ebern (bay-side urban province 16623), one in Noyen (province 16637), and one in Estervik (province 16617).

The setup reserve changes from 8,000 to 10,000 manpower and from 800 to 1,100 infantry equipment. No fifth division, support company, artillery, or additional equipment type is added.

## Data ownership

`tools/build_adiscord_new_states.py` remains authoritative for the generated profiles of states 311-314 and the legacy profile of state 197. The five history state files mirror those exact values. The EBA OOB owns only division placement; `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt` owns the country reserve and equipment grant.

Existing validators receive an explicit EBA balance contract covering state totals, exact per-state profiles, four distributed divisions, and the 10,000/1,100 setup reserve. The broad state generator will not be run over the dirty working tree; intended output files will be patched directly to match the authoritative constants.

## Verification

The implementation starts with a failing contract against the current 2,250,000 population, 6/1 factory split, capital stack, and 8,000/800 reserve. After implementation, run the focused new-state and Vorkerland unit/validator suites, `python -B tools/validate_tc.py --limit 300`, and scoped `git diff --check`.

Static checks prove state values, generator wiring, unit locations, and scripted reserves. They do not prove runtime balance or map presentation; those require a fresh collapse scenario and an in-game screenshot or save observation.
