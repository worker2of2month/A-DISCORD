# A-Discord Six-Tier Economic Mobilization Design

**Date:** 2026-08-16

**Status:** Approved direction; awaiting written-spec review

**Scope:** Active `economy` law progression, one new civilian law, and six user-authored icons

## Goal

Turn the active economic-mobilization progression into a clear six-tier scale.
Add a new civilian-oriented first law as the default, retain the existing five
active laws as tiers 2 through 6, and connect the user's six finished 64x64 PNG
icons to the matching laws.

This is separate from the `ADISCORD_economic_system_laws` category. The earlier
removal of `ADISCORD_economic_system_mobilization` does not remove or rename the
ordinary civilian-to-total-mobilization progression defined in the `economy`
category.

## Final Active Progression

| Player tier | Law ID | Russian name | Engine `level` |
|---|---|---|---|
| 1 | `ADISCORD_civilian_oriented_economy` | Гражданско-ориентированная экономика | 6 |
| 2 | `civilian_economy` | Гражданская экономика | 5 |
| 3 | `low_economic_mobilisation` | Подготовительная мобилизация | 4 |
| 4 | `partial_economic_mobilisation` | Частичная мобилизация | 3 |
| 5 | `war_economy` | Военная экономика | 2 |
| 6 | `tot_economic_mobilisation` | Тотальная мобилизация | 1 |

The new law receives `default = yes`; `civilian_economy` no longer receives the
default marker. Countries that explicitly start with an economy law keep that
law. Countries relying on the category default begin at the new tier 1.

The disabled legacy entries remain unavailable. To keep engine levels unique,
`isolation` moves from level 6 to 7 and `undisturbed_isolation` from 7 to 8.
Their modifiers, localisation, and `allowed = { always = no }` boundaries remain
unchanged.

## New Tier 1 Law

### Definition

- ID: `ADISCORD_civilian_oriented_economy`;
- cost: 150 political power;
- removal cost: -1;
- engine level: 6;
- available only while the country is at peace;
- `cancel_if_invalid = no`, so a country already using it is not silently
  stripped of its law when war begins;
- the only default law in the category.

### Initial balance

```text
consumer_goods_expected_value = 0.38
stability_factor = 0.12
production_speed_industrial_complex_factor = 0.18
production_speed_arms_factory_factor = -0.40
production_speed_dockyard_factor = -0.35
conversion_cost_civ_to_mil_factor = 0.40
conversion_cost_mil_to_civ_factor = -0.15
production_factory_max_efficiency_factor = -0.08
industrial_capacity_factory = -0.10
max_fuel_factor = -0.35
fuel_gain_factor = -0.45
factory_energy_consumption = -0.30
ADISCORD_economy_civilian_factory_income_factor = 0.15
ADISCORD_economy_military_industry_income_factor = -0.15
ADISCORD_economy_army_expense_factor = -0.15
ADISCORD_economy_inflation_pressure_factor = -0.08
ADISCORD_economy_price_stability_factor = 0.08
ADISCORD_economy_creditworthiness_factor = 0.05
ADISCORD_economy_state_overload_gain_factor = -0.08
ADISCORD_country_development_economic_growth_factor = 0.05
```

The law is deliberately more peaceful than `civilian_economy`: it improves
civilian construction, stability, civilian income, price stability, and
long-term development while imposing a larger consumer-goods burden and much
stronger military-industry and conversion penalties.

The economy cache gives this law a
`ADISCORD_economy_cached_consumer_goods_law_adjustment` value of `1.0`. The
existing tier values remain unchanged: civilian `0.7`, preparatory `0.4`,
partial `-0.2`, war `-0.5`, total `-0.9`.

## Progression Behavior

The stable trigger wrapper
`ADISCORD_economy_has_idea_civilian_oriented_economy` is added for the new law.
The existing `upgrade_economy_law` effect gains a first branch that advances
the new law to `civilian_economy`; its existing civilian → preparatory → partial
→ war → total branches remain in the same order.

Postwar demobilization remains unchanged: it still reduces war or total economy
to partial mobilization. No monthly polling, old-save migration, or automatic
step-down to tiers 1 or 2 is added.

## Icon Assets

Create:

`gfx/interface/ideas/laws/economic_mobilization/`

Move only these six current source files into that directory:

| Current filename | Final filename | Law sprite |
|---|---|---|
| `Гражданско-ориентированная экономика ур1.png` | `ADISCORD_economic_mobilization_1_civilian_oriented.png` | `GFX_idea_ADISCORD_civilian_oriented_economy` |
| `Гражданско-ориентированная экономика ур2 (чуть меннее, нужно поменять название).png` | `ADISCORD_economic_mobilization_2_civilian.png` | `GFX_idea_civilian_economy` |
| `ранняя мобилизация ур3.png` | `ADISCORD_economic_mobilization_3_early_mobilization.png` | `GFX_idea_low_economic_mobilisation` |
| `частичная мобилизация ур4.png` | `ADISCORD_economic_mobilization_4_partial_mobilization.png` | `GFX_idea_partial_economic_mobilisation` |
| `военная экономика ур5.png` | `ADISCORD_economic_mobilization_5_war_economy.png` | `GFX_idea_war_economy` |
| `тотальная мобилизация ур 6.png` | `ADISCORD_economic_mobilization_6_total_mobilization.png` | `GFX_idea_tot_economic_mobilisation` |

The provisional prose embedded in the tier-2 source filename is not used as a
law name. Its player-facing law remains the existing `Гражданская экономика`.
All six PNGs remain byte-identical during the move and must remain exactly
64x64, PNG, with alpha.

`interface/ADISCORD_ideas.gfx` declares all six sprites explicitly. This task
does not edit or stage `tools/assets/source/laws.psd`.

## Localisation

Add the new keys in Russian and English:

- `ADISCORD_civilian_oriented_economy`;
- `ADISCORD_civilian_oriented_economy_desc`.

Approved names:

- Russian: `Гражданско-ориентированная экономика`;
- English: `Civilian-Oriented Economy`.

The description explains that civilian consumption, construction, and stable
development take priority, at the cost of military production and rapid
conversion. Existing tier 2-6 names and descriptions remain unchanged. Russian
localisation retains UTF-8 BOM.

## Implementation Boundaries

- Do not change the modifiers, availability, costs, or AI weights of tiers 2-6.
- Do not edit explicit starting economy laws in country history.
- Do not change postwar demobilization or the war-support gates for tiers 3-6.
- Do not change the separate `ADISCORD_economic_system_laws` category.
- Do not create startup or old-save migration logic.
- Do not edit the six PNGs or `tools/assets/source/laws.psd`.
- Preserve unrelated dirty technology, equipment, entity, leader-art, and
  documentation work.
- Do not launch Hearts of Iron IV automatically.

## Verification

Implementation begins with failing focused tests and is complete statically
only when all of the following hold:

- the active progression contains the exact six IDs in the approved order;
- the new law is the only default and has the approved level, availability,
  cost, and modifiers;
- disabled isolation levels are unique and remain unavailable;
- all six sprite names resolve to the intended byte-preserved 64x64 alpha PNGs;
- the new stable wrapper exists and the cache branch publishes `1.0`;
- `upgrade_economy_law` advances tier 1 to tier 2 before existing branches;
- tiers 2-6 definitions remain otherwise unchanged;
- bilingual localisation exists and Russian BOM is intact;
- focused economic-mobilization tests pass;
- the full weekly economy contracts and economy/AI validator pass;
- `python -B tools/validate_tc.py --limit 300` passes;
- both unstaged and cached `git diff --check` pass.

Static validation does not prove sprite override order or Clausewitz runtime
behavior. A full Hearts of Iron IV restart and fresh-campaign law-screen check
must confirm all six icons, the new default, tier order, localisation wrapping,
AI selection, and the upgrade effect in game.
