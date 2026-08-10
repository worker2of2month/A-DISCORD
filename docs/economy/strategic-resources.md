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

Late support equipment, drone carriers and advanced anti-air consume rare
components. Late artillery, combat platforms and hardened trains consume rare
alloys. Neither factory is placed in state history; both are player-built,
slot-consuming industrial choices. They share the
`ADISCORD_advanced_material_plants` state group, so one state cannot host both.

## Planned technology integration

The current technology generator is intentionally unchanged. A later dedicated
technology pass should introduce the stable planned IDs below and then bind the
existing building IDs without renaming them:

| Planned technology ID | Future responsibility |
| --- | --- |
| `ADISCORD_tech_rare_components_industry` | unlock the Components Plant and later improve component yield |
| `ADISCORD_tech_rare_alloy_metallurgy` | unlock the Rare Alloy Foundry and later improve alloy yield |

Until that pass, the buildings are directly constructible and no generated
technology or starting-state file is touched.

Air-equipment consumers are intentionally deferred: that authoritative source is
owned by concurrent aircraft work and must not be merged into this change without
a separate balance audit.

The economy window remains independent from Trade. Its top-bar button occupies
the new slot immediately to the right of Trade, while the six treasury actions
are integrated into the main economy dashboard and require no overlay state.
