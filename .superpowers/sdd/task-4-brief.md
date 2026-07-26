# Task 4: Dirty-State Bootstrap and Permanent Modifier

Plan: `docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`

Read Shared Manifest and complete Task 4 before editing.

## Scope

Create:

- `common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt`
- `common/scripted_effects/ADISCORD_vorkerland_collapse_dirty_effects.txt`

Modify:

- `tools/test_validate_adiscord_vorkerland_collapse.py`
- `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`
- `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- exactly these 32 state files:
  - `49-PLACEHOLDER.txt`, `51-PLACEHOLDER.txt`, `125-Reactor.txt`
  - `152-152.txt`, `153-153.txt`, `154-154.txt`, `155-155.txt`,
    `160-160.txt`
  - `165-165.txt`, `166-166.txt`, `167-167.txt`, `168-168.txt`,
    `169-169.txt`, `171-171.txt`, `172-172.txt`, `173-173.txt`,
    `176-176.txt`, `177-177.txt`, `178-178.txt`, `180-180.txt`,
    `181-181.txt`, `182-182.txt`, `183-183.txt`, `184-184.txt`,
    `185-185.txt`, `187-187.txt`, `188-188.txt`, `189-189.txt`,
    `190-190.txt`, `191-191.txt`, `192-192.txt`, `193-193.txt`.

Do not add owners or cores. Do not edit states 23/24/57/59/60; they receive
the modifier through the effect but retain their existing owners. Preserve
state 125 `impassable = yes`.

Work on main by explicit permission. Commit only scoped files:

`feat: bootstrap contaminated territories`

## TDD workflow

1. Add `DirtyStateTests`.
2. Assert:
   - all 37 states occur exactly once in the apply effect;
   - dynamic modifier exists and has no `remove_trigger`;
   - no repo code removes this modifier;
   - all 32 spawn states have positive manpower, category and local supplies;
   - six capital provinces have their exact VP/buildings;
   - no spawn state gains owner/core.
3. Run RED.
4. Implement state bootstrap, modifier, effect and localisation.
5. Run GREEN, `--section dirty`, then `validate_tc --limit 80`.
6. Verify exact definition.csv contaminated-state match and BOM.
7. Commit scoped files and report.

## Modifier

Use exactly:

```hoi4
ADISCORD_vorkerland_dirty_state = {
    enable = { always = yes }
    icon = GFX_modifiers_sabotaged_resource
    local_manpower = -0.75
    state_resources_factor = -0.60
    local_building_slots_factor = -0.40
    state_production_speed_buildings_factor = -0.50
    local_supply_impact_factor = 0.35
}
```

No duration, `remove_trigger`, or removal effect.

The application effect enumerates exactly `CONTAMINATED_STATES`. Prefer a
small state-scoped helper with a `has_dynamic_modifier` guard, invoked once
for every state ID. It must be safe to run more than once.

## State bootstrap

- Preserve every existing province list and any non-zero manpower.
- Preserve existing categories except the six capitals may become `town`.
- Give every spawn state a positive `local_supplies`.
- Default new values for states without content:
  `state_category = rural`, `local_supplies = 0.25`,
  manpower `1500 * province_count`.
- Explicit default manpowers:
  - 165 13500; 166 12000; 167 15000; 168 10500; 169 18000;
  - 171 19500; 172 9000; 173 22500; 176 15000; 177 18000;
  - 178 9000; 180 9000; 181 21000; 182 12000; 183 9000;
  - 184 13500; 185 6000; 187 13500; 188 19500; 189 22500;
  - 190 18000; 191 22500; 192 18000; 193 22500.
- State 51: manpower 136500, keep category, local supplies 0.25.
- State 125: manpower 33000, keep category and impassable, local supplies
  0.25.
- States 152/153/154/155/160 retain respectively
  140000/45000/35000/50000/45000 and get local supplies 0.25.

Capital exceptions:

| Tag | State/Province | VP | State/buildings |
|---|---|---:|---|
| SLA | 49/16639 | 3 | manpower 20000, town, supplies .5, infrastructure 1, civilian 1 |
| RZA | 177/2952 | 3 | town, supplies .5, infrastructure 1, arms 1 |
| MLR | 152/9806 | 3 | town, supplies .5, infrastructure 1, civilian 1 |
| ERT | 169/10693 | 3 | town, supplies .5, infrastructure 1, arms 1 |
| IRT | 181/2226 | 3 | town, supplies .5, infrastructure 1, civilian 1 |
| SCA | 173/6015 | 3 | town, supplies .5, infrastructure 1, arms 1 |

Use ownerless `history = { buildings = {...} victory_points = {...} }`
blocks. Add no owner/core/controller.

## Localisation

Keep administrative/geographic wording. Add the six VP names:

- 16639 `Старолесье`
- 2952 `Реакторная станция`
- 9806 `Малая Низина`
- 10693 `Восточный узел`
- 2226 `Внутренний узел`
- 6015 `Южный узел`

Localise the dirty modifier and description in the main feature file.
All Russian YAML files must remain UTF-8 BOM.

Write report to `.superpowers/sdd/task-4-implementer-report.md`.
