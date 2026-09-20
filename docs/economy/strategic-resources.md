# Strategic resources and trade UI

The total conversion owns nine strategic resources. Electricity remains frame 7;
the two late-industrial resources are appended so existing resource identities do
not move:

| Frame | Resource | Main role | Bounded sources |
| --- | --- | --- | --- |
| 8 | Rare Components | precision electronics, sensors and control assemblies | `ADISCORD_rare_components_plant` (4 per level) |
| 9 | Rare Alloys | heat-resistant structural and weapons material | `ADISCORD_rare_alloy_foundry` (3 per level) |

Both resources are tradable. Their civilian-factory price is deliberately twice
the standard material price (`cic = 0.25`) because they are refined industrial
inputs rather than raw ore. The nine-column trade override retains all native
trade behavior and only widens the resource, filter and country-entry geometry.

Late support equipment, drone carriers, advanced anti-air, interceptors and
guided strike aircraft consume rare components. Late artillery, combat platforms,
hardened trains and advanced aircraft consume rare alloys. The final combat
platforms retain both material requirements rather than dropping the previous
generation's rare input. Basic fighters, attack aircraft and early armour retain
their conventional resource requirements. Existing plants in WRK and RIV state
history form the initial supply; further plants are player-built,
slot-consuming industrial choices. They share the
`ADISCORD_advanced_material_plants` state group, so one state cannot host both.

## Technology integration

The technology generator owns a six-node Advanced Materials branch. Components
and alloys are independent research paths, so researching either plant does not
require the other plant. Their final recycling technology requires both paths.

| Technology ID | Responsibility |
| --- | --- |
| `ADISCORD_tech_rare_components_industry` | 2158: unlock the Components Plant, base output 4 |
| `ADISCORD_tech_rare_alloy_metallurgy` | 2158: unlock the Rare Alloy Foundry, base output 3 |
| `ADISCORD_tech_precision_component_fabrication` | 2166: +2 components per plant |
| `ADISCORD_tech_vacuum_alloy_refining` | 2166: +1 alloy per foundry |
| `ADISCORD_tech_advanced_material_recycling` | 2173: +1 output for each plant type |

Both plants require their technology. The industrial starting profile includes
the two unlocks. RIV receives only the narrow material profile alongside its
existing fragment profile, preserving its inherited factories without granting
the full industrial package. Base output reaches 7 components or 5 alloys before
regional modifiers. The 2166 upgrades each add 2% factory energy demand; recycling
removes 2%. All equipment consumers have later research dates than the 2158
plant unlocks. Research dates indicate availability, not guaranteed construction
or a sufficient national supply; countries may also trade these resources.

## Budget research

The eight-node Economy and Administration line uses existing country economy
modifiers consumed by `ADISCORD_economy_modifier_effects.txt`. Its cumulative
effects, including the common accounting baseline, are +7% tax collection,
+8% civilian industrial income, +4% trade income, +3% resource rent, +4% military
industrial income, -9% administration costs, -6% construction costs, -5% military
factory upkeep and -3% research costs. These affect their respective budget
categories, not total income or expenses uniformly.

Assembly and factory automation add a further +5% civilian industrial income.
Predictive maintenance and three power-grid milestones reduce military factory
upkeep by a further 7%. Existing native energy-consumption effects remain in
force. Budget research invalidates the existing economy cache through its single
research-completion callback, shared with any research reward. Scripted technology
profile grants also invalidate that cache; no recurring technology scan or
increment-only country variable is needed.

The economy window remains independent from Trade. Its top-bar button occupies
the new slot immediately to the right of Trade, while the six treasury actions
are integrated into the main economy dashboard and require no overlay state.

## Paid industrial programmes

Kefreite and postwar Shabrat receive nine-focus investment branches after their
existing economic-recovery finales. Focuses authorize investment; they do not
charge treasury or produce unresearched equipment. The final focus requires one
completed capital programme, not merely all preceding focuses.

| Programme | Treasury | Components / alloys | Days | Delivered result |
| --- | ---: | ---: | ---: | --- |
| Precision tooling | 800 | 6 / 3 | 90 | +8% efficiency cap, +10% efficiency growth |
| Industrial automation | 1200 | 8 / 6 | 120 | +8% factory output, +10% total income |
| National computing | 1500 | 12 / 4 | 120 | +7% research, -10% administrative costs |
| Supply service | 600 | 4 / 6 | 60 | 300 researched trucks, 20 researched armoured trains |
| Reconnaissance order | 1000 | 8 / 4 | 90 | 60 researched drone-carrier vehicles |
| Combat-platform order | 1800 | 8 / 12 | 120 | 80 researched combat platforms |

One programme occupies the national investment slot. Payment is recorded once
in the existing treasury action ledger. The `project_id` identifies the active
operation; `project_deposit` is its receipt. An active country-scoped dynamic
modifier reserves three civilian factories and the specified continuous resource
flow with native `country_resource_cost_rare_components` and
`country_resource_cost_rare_alloys`. Availability reads the current country
`resource@` surplus, including trade and ordinary production. The resources are
not an invented stockpile, nor permanently subtracted from a state's deposits.

Resource deficits, insufficient surviving civilian industry, capitulation or
loss of independence cancel work. The country recovers 75% of its receipt;
25% is sunk cost. Cancellation and delivery both release the native allocation,
clear the receipt and invalidate the economy cache. Callbacks check their own
project ID, so a stale operation cannot settle another country's or another
project's payment. An explicit cancellation decision uses the same refund path.
There are no new recurring country/state scans or delayed event dispatchers.

The three capital programmes cannot be bought twice. Equipment contracts have
a 90-day re-enable delay and require technologies that actually enable their
specific delivered models. The source-executing transaction tests cover exact
fractional input boundaries, duplicate/stale callbacks, interruptions and the
native allocation edges. They do not replace a cold game load and a complete
in-game decision lifecycle check.
