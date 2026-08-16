# A-Discord Economic-System Laws, Icons, and Syndicalism Design

**Date:** 2026-08-16

**Status:** Approved direction; awaiting written-spec review

**Scope:** Economic-system law roster, icons, model 5, and selected starting laws

## Goal

Connect the user's nine finished 64x64 economic-system icons to the active law
category, give them stable ASCII asset names in a dedicated subfolder, replace
the total-mobilization economic system with an actual syndicalist economic
system, and correct the requested countries' starting systems.

The result must contain exactly nine economic-system laws. It is intended for a
fresh campaign; this change does not provide an old-save migration.

## Law Roster

The existing mobilization law is removed from the category and model logic:

- remove `ADISCORD_economic_system_mobilization`;
- remove `ADISCORD_economy_model_is_mobilization` and every branch whose only
  purpose is to apply the old model-5 wartime economy behavior;
- remove the mobilization law's GFX and localisation bindings;
- remove mobilization from explicit economic-system allowlists in tests and
  validators.

The replacement law is:

- ID: `ADISCORD_economic_system_syndicalist`;
- picture: `ADISCORD_economic_system_syndicalist`;
- internal economy-model value: `5`;
- Russian name: `Синдикалистская экономика`;
- English name: `Syndicalist Economy`.

Keeping numeric value 5 avoids renumbering the later oligarchic-clan and
technocratic models. It does not preserve the former model-5 mechanics.

The final roster is:

1. agrarian;
2. industrializing;
3. free market;
4. mixed;
5. state-coordinated;
6. planned-bureaucratic;
7. syndicalist;
8. oligarchic-clan;
9. technocratic.

## Syndicalist Law Design

The law represents enterprises managed by worker associations and industrial
unions, with production coordinated through agreements between collectives.
Its identity is civilian resilience and broadly shared industrial development,
not wartime command economics.

### Availability

The law is available when at least one of these conditions is true:

- the country is anarchist;
- the country is utilitarian;
- the country has `ADISCORD_labor_policy_guild_protections`.

This makes syndicalism politically accessible while also allowing a country to
reach it through established professional and worker organisations.

### Modifiers

The approved initial balance is:

```text
consumer_goods_expected_value = 0.05
min_export = -0.05
industrial_capacity_factory = 0.03
production_speed_industrial_complex_factor = 0.10
production_speed_infrastructure_factor = 0.05
line_change_production_efficiency_factor = -0.05
production_factory_max_efficiency_factor = 0.05
production_factory_efficiency_gain_factor = 0.05
political_power_gain = -0.03
stability_factor = 0.05
ADISCORD_economy_tax_collection_factor = 0.05
ADISCORD_economy_trade_income_factor = -0.05
ADISCORD_economy_civilian_factory_income_factor = 0.10
ADISCORD_economy_building_income_factor = 0.08
ADISCORD_economy_admin_expense_factor = 0.08
ADISCORD_economy_creditworthiness_factor = -0.05
ADISCORD_economy_price_stability_factor = 0.05
ADISCORD_economy_investment_confidence_factor = -0.10
ADISCORD_country_development_economic_growth_factor = 0.05
```

The strengths describe stable collective production, civilian construction,
and organised collection of public revenue. The costs describe coordination
overhead, reduced private-capital confidence, weaker access to conventional
credit, and less flexible production-line changes.

### Economy-model behavior

`ADISCORD_economy_model_is_syndicalist` replaces the model-5 predicate. Model 5
may satisfy the existing advanced-taxation and market-expansion capability
groups, but it does not satisfy state-planning, mobilization-economy, or
emergency-extraction groups merely because it is syndicalist.

All old model-5 special cases that impose mobilization income penalties,
military-expense multipliers, inflation pressure, wartime development losses,
state load, military-investment bonuses, or war-fatigue changes are deleted
instead of being renamed. The explicit law modifiers above define the initial
syndicalist balance; a deeper cooperative-economy simulation is outside this
change.

## Icon Assets

Create the dedicated directory:

`gfx/interface/ideas/laws/economic_system/`

Move the user's nine PNG files from `gfx/interface/ideas/laws/` into that
directory with these stable names:

| Current filename | Final filename |
|---|---|
| `аграрная.png` | `ADISCORD_economic_system_agrarian.png` |
| `ранняя индустриальная.png` | `ADISCORD_economic_system_industrializing.png` |
| `свободный рынок.png` | `ADISCORD_economic_system_free_market.png` |
| `смешанная.png` | `ADISCORD_economic_system_mixed.png` |
| `государственно-координируемая.png` | `ADISCORD_economic_system_state_coordinated.png` |
| `плановая.png` | `ADISCORD_economic_system_planned_bureaucratic.png` |
| `синдикалисткая экономика.png` | `ADISCORD_economic_system_syndicalist.png` |
| `олигархо-клановая.png` | `ADISCORD_economic_system_oligarchic_clan.png` |
| `технократическая.png` | `ADISCORD_economic_system_technocratic.png` |

The misspelling in the submitted syndicalist filename is corrected by the
technical rename and localisation. Each `spriteType` in
`interface/ADISCORD_ideas.gfx` points directly at the matching PNG. The PNGs
remain exactly 64x64 with alpha; this task does not recreate or convert the
user's artwork and does not modify `tools/assets/source/laws.psd`.

Only the nine filenames listed in the table belong to this move. In particular,
`gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png` and any
other new artwork for the separate economic-mobilization progression remain at
their current paths and are not renamed, moved, edited, declared, or otherwise
incorporated into this task.

## Starting Economic Systems

Country history must give exactly these requested starts:

| Tag | Starting economic-system law |
|---|---|
| `STP` | `ADISCORD_economic_system_oligarchic_clan` |
| `NOD` | `ADISCORD_economic_system_oligarchic_clan` |
| `VAL` | `ADISCORD_economic_system_state_coordinated` |
| `APH` | `ADISCORD_economic_system_agrarian` |
| `OSF` | `ADISCORD_economic_system_agrarian` |
| `CIN` | `ADISCORD_economic_system_agrarian` |

`APH`, `OSF`, and `CIN` are the northern cannibal countries in this scope.
Existing unrelated national ideas and ministers in those history files remain
unchanged. Every listed country must start with exactly one law from the
economic-system category.

## Localisation

Russian and English receive the new law name, description, and model-5 display
label. The descriptions explain collective management, civilian industrial
resilience, and the trade-off in private finance and coordination without
listing raw modifier values.

Russian localisation remains UTF-8 with a BOM. The earlier law-localisation
rewrite plan must be updated so it no longer expects the removed mobilization
ID or name; this newer approved design supersedes only that part of the older
design's non-goal boundary.

## Implementation Boundaries

- Preserve unrelated dirty technology, equipment, entity, documentation, and
  source-art changes.
- Do not modify generated outputs directly; no country-history or economic-law
  path in this scope is currently identified as generator-owned.
- Do not add compatibility aliases or startup migrations for the removed law.
- Do not change other law categories, country ideas, or economic-system costs.
- Do not change the existing `ADISCORD_economy_model_allows_mobilization_economy`
  capability or the separate civilian-to-mobilized economy progression except
  to remove the obsolete model-5 predicate from capability membership. The
  state-coordinated and planned-bureaucratic members remain intact.
- Do not touch `Гражданско-ориентированная экономика ур1.png` or later assets
  being prepared for that separate progression.
- Do not launch Hearts of Iron IV automatically.

## Verification

Implementation begins with a failing focused contract test. The completed
change must prove:

- the active category contains exactly the approved nine IDs;
- mobilization is absent from active economic-system definitions, mappings,
  GFX, localisation, tests, and validators;
- syndicalism maps to model value 5 and has the approved availability and
  modifiers;
- none of the former mobilization-only model-5 effects remain;
- all nine sprite paths resolve to 64x64 alpha-capable PNG files;
- `Гражданско-ориентированная экономика ур1.png` remains at its original path
  with unchanged content and is absent from the economic-system sprite changes;
- the six selected tags have exactly the requested starting law;
- Russian localisation retains its UTF-8 BOM;
- focused economic-system and existing weekly economy tests pass;
- the focused economy AI validator passes;
- `python -B tools/validate_tc.py --limit 300` passes;
- both unstaged and cached `git diff --check` pass for the implementation
  scope.

Because the change affects loaded ideas, GFX, localisation, and country history,
static checks are not final runtime proof. A full Hearts of Iron IV restart and
fresh-campaign law-screen inspection are required afterward to confirm icon
loading, localisation, starting assignments, and Clausewitz behavior.
