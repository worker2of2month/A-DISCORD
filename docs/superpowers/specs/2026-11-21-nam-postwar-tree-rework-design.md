# NAM post-war tree and South heritage tree

Status: implemented in the focus sources and the NAM hubs. The post-war tree
`NAM_postwar_focus` holds 77 focuses, the South heritage tree
`NAM_south_heritage_focus` 33. Static tests pin the layout, the days, the AI
plans, the research slots, the story events and the folded ids. Nothing in this
record was checked in the running game; the native loader, tooltips, event
windows and the AI plans need a manual check with a full restart.

This record is the contract for maintainers. Where the focus sources and this
record disagree, the sources win and this record is corrected.

## 1. The author's orders

Binding, in the author's words:

- "ветку почистить, сделать симметричнее, часть фокусов объединить, усилить".
- "пути федерации \ союза я бы сделал как изначальный выбор на пути гуманистов".
- After the first rebuild: "До войны юга нужно больше времени или сократить
  кол-во фокусов послевоенных. Я бы второй вариант сделал." He set the size: a
  normal playthrough of one path with its share of the shared branches and the
  offensive takes about a year and a half of focus time (about 540 days, about
  30 focuses); everything one playthrough can reach takes at most about 700
  days (about 40 focuses); the whole post-war tree about 95 focuses. The number
  of focuses falls, not their length.
- "И пусть национализация не пропадает после начала войны за юг."
- "всем одинаковое количество" (research slots after the war).
- "можно убрать": `NAM_pw_southern_army` has no army-size condition; it needs
  only `NAM_pw_operable`. No test or document may ask for the old 180000-men row.

Standing decisions: each path opens with its own choice on its early days; every
path ends with the same number of post-war research slots; a development trade
in this tree may lower any track; the layout is mirrored about the centre column
with a free cell between neighbours and no straight chain longer than two;
rewards follow The Fire Rises (several felt rewards of different kinds per
focus, story events on important focuses, locked laws, development trades);
descriptions carry no mechanics.

Counts against time. The two figures of the order disagree at the fixed card
costs: a full route of 700 days holds about 34 focuses, not 40, because every
route carries heavy cards (trunk 42 days, opening side 28, two wing capstones of
28, path hub 28, offensive 42, path keeper 63). The tree keeps the 700-day
limit, so it has 77 focuses, not about 95. Taking back about four cards per path
would need a full route of about 780 days (section 12).

## 2. Loading and lifecycle

- `NAM_postwar_focus` loads at the resource-war victory
  (`ADISCORD_nam_resource_war_nam_victory`). The pre-war tree is shared history,
  so its completions stay readable through `has_completed_focus`.
- The offensive focus calls `ADISCORD_south_prepare_offensive`; at the start of
  the war for the South `ADISCORD_south_load_war_tree` records the tree in
  `ADISCORD_south_prior_tree` (value 2 for the post-war tree) and loads
  `NAM_south_war_focus` with `keep_completed = yes`.
- A southern victory of NAM (`NAM_won_final_southern_war`:
  `ADISCORD_south_final_resolved` and `ADISCORD_south_hegemon_NAM`) loads
  `NAM_south_heritage_focus`. Any other outcome restores the recorded tree
  through `ADISCORD_south_restore_prior_tree`.
- Locked laws stay through the war tree, the heritage tree and a restored
  post-war tree. Nothing repeals them; a later change must be an explicit
  scripted `swap_ideas`.

## 3. Shape of the post-war tree

Grid x 0..72, y 0..14, axis x = 36. Every card at (x, y) off the axis has a twin
at (72 - x, y) inside its own part and view.

| Zone | Columns | Rows | Fixed cells |
|---|---|---|---|
| Trunk | 36 | 0-1 | `NAM_recognition` (36,0), `NAM_law_after_war` (36,1) |
| Armed forces (outer left) | 2-14 | 1-13 | head `NAM_veterans_return` (8,1) |
| Neighbours and border (inner left) | 18-26 | 2-4 | pair (20,2) / (24,2) |
| Path funnel | 29-43 | 2-5 | opener (36,2), opening pair (33,3) / (39,3) |
| Civil services (inner right) | 46-54 | 2-4 | pair (48,2) / (52,2) |
| Economy (outer right) | 58-70 | 1-13 | head `NAM_civil_repair` (64,1) |
| Path body | 18-54 | 6-12 | - |
| Path hub and offensive | 36 | 13-14 | hub (36,13), offensive (36,14) |

- The three paths occupy the same cells. Each path card carries `allow_branch`
  with its frozen mandate (`NAM_prewar_service_mandate`,
  `NAM_prewar_pragmatic_mandate`, `NAM_prewar_district_mandate`; the mandate is
  `NAM_prewar_balance` below -0.30, between, or above +0.30), so one view shows
  the shared cards and one path. No shared card has `allow_branch`.
- Drawn lines cross a zone border only from `NAM_recognition` to the three
  heads (8,1), (36,1), (64,1) and from `NAM_law_after_war` to (20,2), (24,2),
  (36,2), (48,2), (52,2) on the half-row bus. Every other dependency between
  parts is an `available` condition inside a `custom_trigger_tooltip`.
- Layout rules, all pinned per view: unique cells; at least one free column
  between horizontal neighbours; a child strictly below its parents; exclusive
  partners on one row, 3-6 columns apart, with nothing on the connector; no
  wire through a card and no crossing; no single-parent straight chain longer
  than two (the trunk `NAM_recognition` -> `NAM_law_after_war` -> opener is the
  stated exception); children of an exclusive pair stay on their own side.
- View sizes: shared 32 cards; etatist view 48, pragmatic 47, district 46.

### 3.1 Heritage tree

Grid x 0..30, y 0..7, axis x = 15. Root `NAM_south_heritage` (15,0). The Khan
crisis lane is shared by all paths: `NAM_rus_crisis_watch` (15,1), the pair
`NAM_rus_fuel_for_coalition` / `NAM_rus_demand_share` (13,2) / (17,2),
`NAM_rus_expedition_staff` (15,3). Each path has two mirrored wings with their
root children on row 1 inside x 1-11 and 19-29. A drawn root pair never
straddles the Khan lane: the etatist path uses two drawn pairs inside its wings
(`NAM_pw_strategic_reserve` / `NAM_pw_development_fund` and
`NAM_veyran_union_charter` / `NAM_svetlogorsk_settlement`); the pragmatic and
district paths exclude their two roots through `available` with a named
tooltip, without `mutually_exclusive`. Views: etatist 17, pragmatic 13,
district 13.

## 4. Budget in days

Costs (one point = 7 days):

| Role | Cost | Days |
|---|---|---|
| Ordinary focus | 2 | 14 |
| Turning point: opener, fork side, wing head, `NAM_recognition`, `NAM_law_after_war` | 3 | 21 |
| Capstone: opening-pair side, path hub, `NAM_pw_southern_army`, `NAM_svetlogorye` | 4 | 28 |
| Offensive (`NAM_south_seal_over_furnaces`, `NAM_prag_south_guarantees`, `NAM_south_oil_charter`) | 6 | 42 |
| Path research-slot keeper | 9 | 63 |

`NAM_kadir_oil_charter` keeps its own cost of 4. The heritage tree uses the same
scale. No post-war focus costs 1.

Routes (focus time from the tree's start; the war's own months not counted):

| Path | Readiness, cheapest | Offensive done | Normal route | Full route |
|---|---|---|---|---|
| Etatist | 385 | 427 | 553 (25 focuses) | 700 (34 focuses) |
| Pragmatic | 378 | 420 | 539 (24 focuses) | 693 (33 focuses) |
| District | 378 | 420 | 546 (24 focuses) | 700 (33 focuses) |

- Readiness = the closure of `ADISCORD_south_nam_focus_ready` (section 9).
- Normal route = trunk 42 + the two outer-wing spines (98 + 98) + one inner
  side with one child (35) + the path spine with the offensive and the keeper +
  the path's diplomacy gates. Full route = every card one playthrough can reach
  with one side of every pair; the shared share is 406 days (22 focuses), the
  path share 294 / 287 / 294.
- Limits pinned by `test_postwar_days_and_ai_plans_fit_the_window`: readiness at
  most 385 / 378 / 378, offensive at most 427 / 420 / 420, full route at most
  700, normal route 525-560.
- The southern deadline opens between 2165.12.1 (strongest crisis pull) and
  2166.3.1; in a campaign won on 2163.3.22 that is day 984-1074 of the tree,
  leaving 431-535 days of margin on a normal route and 284-381 on a full one.

## 5. Standards

### 5.1 Reward magnitudes

Main row by role; the secondary row is a second material row of another kind.

| Kind | c2 | c3 | c4 | Secondary |
|---|---|---|---|---|
| Manpower | 7000 | 10000 | 14000 | 3000-4000 |
| `infantry_equipment` | 6000 | 9000 | 12000 | 2000-3000 |
| Support equipment | 200 | 300 | 400 | 100 |
| Trucks | 250 | 400 | 550 | 120 |
| Artillery / anti-air / armoured carriers | 72 / 72 / 80 | 120 | 160 | 36 / 36 / 40 |
| Convoys | 10 | 15 | 20 | 5 |
| Fuel | 20000 | 35000 | 50000 | 8000 |
| Political power | 60-75 | 100-120 | 150 | 40 |
| Treasury (`ADISCORD_economy_treasury`) | 300 | 500 | 700 | 150 |
| Army, navy or air experience; command power | 25 | 40 | 55 | 15 |
| Stability or war support | 5% | 8% | 10% | 3% |
| Group support `NAM_grp_<group>_support` | +8 / -5 | +12 / -6 | +15 / -8 | - |
| Buildings | 1 factory with its own slot, or 2 infrastructure or naval levels | 2 factories with slots, or 1 factory + 2 infrastructure | 3 factories, or 2 factories + 2 infrastructure | - |
| Aggregate lines | two, 6-8% | three, up to 10%, one a price | three, up to 12%, one a price | - |

- Every focus pays at least one material row; a decision unlock never replaces
  it. A factory reward brings its own shared slot, rechecks owner, controller
  and site at delivery and pays the treasury fallback (300 / 450 / 600 by tier,
  150 for a road level that cannot be built) when no site qualifies.
- Kinds per focus: c2 at least four, c3 at least five, c4 at least five and a
  story event; the offensive carries the war and is exempt; a keeper at least
  four besides its slot. Two rows of one kind count once; costs and events do
  not count; a tooltip counts only when it names a real consumer.
- Southern contract ideas (`ADISCORD_south_nam_*`) of the offensives are not
  rewards.

### 5.2 Folding

A folded focus hands its absorber every reward row, every
`unlock_decision_tooltip` with its `_unlock_tt`, every flag, variable, group or
BOP push, law, trade and story event. Every reader of the folded id is
repointed in the same change; where the folded card was one side of a pair, the
reader is rewritten for the surviving meaning. The folded id and its
localisation go; its `spriteType` stays (other NAM trees reuse those sprites).
No stub and no alias.

Caps on merged rewards (merging is not adding): a same-kind stock rises at most
one tier (c2 to the c3 value, c3 to c4, c4 by 20%); a stock of another kind
enters at the secondary magnitude; aggregates keep the absorber's tier; one
law, one trade and one slot per card. Value the caps cannot carry is dropped,
not moved. A dummy preview that moves to an absorber is renamed
`NAM_adm_<absorber>_idea`, so the preview test pairs it by name.

`test_folded_postwar_focus_ids_are_gone` keeps the 153 folded ids out of
`common/`, `events/`, `focus_trees/`, `tools/tests/` and `docs/development/`
(written as `NAM_<id>`).

### 5.3 Locked laws

25 laws `NAM_pw_law_<x>` in the section "Post-war republic: laws" of
`common/ideas/ADISCORD_nam_resource_war_ideas.txt`: `cost = 0`,
`removal_cost = -1`, visible only while held, `available` always false behind
`NAM_pw_law_<x>_source_tt`, `allowed_to_remove` false behind
`NAM_pw_law_locked_tt`, `ai_will_do` 0, `ADISCORD_economy_queue_law_refresh` in
`on_add` / `on_remove`. Enactment `NAM_pw_enact_<x> = yes` (section "Post-war
republic: laws" of `ADISCORD_nam_resource_war_effects.txt`) swaps visibly over
every law of the slot, adds only into an empty slot and shows
`NAM_pw_law_lock_tt`; it is the first native row of the reward. The two sides of
an exclusive pair share a slot; no route takes one slot twice.

| Owner | Focus | Law | Slot |
|---|---|---|---|
| Shared | `NAM_pw_breakthrough_army` / `NAM_pw_mobile_army` | `rail_echelons` / `motor_columns` | logistics |
| Shared | `NAM_svetlogorsk_shipyards` / `NAM_pw_air_review` | `sea_training` / `flight_training` | training |
| Shared | `NAM_civil_dividend` / `NAM_armed_peace` | `civil_contracts` / `defence_depots` | infrastructure |
| Etatist | `NAM_ladder_ending_iron` / `NAM_ladder_ending_service` | `namestnik_rule` / `civil_service` | internal security |
| Etatist | `NAM_state_plan` / `NAM_regional_trusts` | `central_plan` / `regional_trusts` | industrial policy |
| Etatist | `NAM_pw_labour_code` / `NAM_pw_insurance_fund` | `labour_service` / `state_insurance` | labour / welfare |
| Pragmatic | `NAM_prag_ending_republic` / `NAM_prag_ending_directorate` | `public_estimate` / `board_exchange` | taxation / trade |
| Pragmatic | `NAM_prag_treasury_guarantee` / `NAM_prag_private_underwriting` | `treasury_guarantee` / `private_underwriting` | economic system |
| Pragmatic | `NAM_foreign_patents` / `NAM_domestic_designs` | `licence_industry` / `design_bureaus` | industrial policy |
| District | `NAM_charter_ending_federation` / `NAM_charter_ending_oil_union` | `district_welfare` / `artel_contracts` | welfare / labour |
| District | `NAM_district_militia` / `NAM_relief_register` | `district_oath` / `district_medicine` | military justice / healthcare |
| District | `NAM_municipal_land` / `NAM_tenant_councils` | `municipal_land` / `open_minutes` | industrial policy / information |
| District heritage | `NAM_south_free_communities` | `community_rights` | cultural policy |

### 5.4 Development trades

Ten trades `NAM_pw_trade_<lowered>_for_<raised>` in the section "Post-war
republic: development trades" of the effects file. Shape: a visible
`custom_effect_tooltip`, the level change in `hidden_effect` ending with
`ADISCORD_economy_mark_dirty = yes`; the raised track gains a level through
`NAM_board_dev_raise_<track>` or `NAM_pw_dev_raise_social_system`, or pays 250
treasury through the `_capped_tt` branch when it is already at 5; the lowered
track drops one level with its progress kept through
`NAM_board_dev_lower_society`, `NAM_board_dev_lower_social_system`,
`NAM_pw_dev_lower_state`, `NAM_pw_dev_lower_economic` or
`NAM_pw_dev_lower_science`.

| Trade | Focus |
|---|---|
| `social_system_for_army` | `NAM_armed_peace` |
| `society_for_army` | `NAM_border_revenge` |
| `social_system_for_economic` | `NAM_pw_labour_code` |
| `society_for_state` | `NAM_ladder_of_seals` |
| `economic_for_state` | `NAM_prag_treasury_guarantee` |
| `state_for_economic` | `NAM_prag_private_underwriting` |
| `science_for_economic` | `NAM_foreign_patents` |
| `state_for_social_system` | `NAM_charter_ending_federation` |
| `society_for_economic` | `NAM_charter_ending_oil_union` |
| `state_for_army` | `NAM_district_militia` |

No trade appears twice on any route.

### 5.5 Story events

- Namespace `ADISCORD_nam_story`, ranges: shared 300-319, etatist 320-339,
  pragmatic 340-359, district 360-379; every id is registered in
  `tools/data/adiscord_event_ids.json`. Numbers 345 and 346 are retired and not
  reused; 363 and 371 were never created.
- Shape: `is_triggered_only`, `fire_only_once`, three answers; the first is the
  timeout answer and costs political power, treasury or group support; effects
  sit on the answers; prose only, within 3000 characters and 5500 UTF-8 bytes
  per page.
- A focus fires at most one window; the call is the last row of its single
  `hidden_effect`. At least 28 days between windows on a path spine, at least 21
  between event focuses of an AI plan. `ADISCORD_nam_story.40` is queued only by
  the hub events 327 and 349. `ADISCORD_nam_groups.11` no longer exists.
- Older post-war events keep their ids: `ADISCORD_nam_resource_war.12`
  (`NAM_recognition`), `.13` (`NAM_svetlogorye`), `.413`
  (`NAM_pw_constitutional_committee`), `.414` (`NAM_pw_district_hospitals`),
  `ADISCORD_nam_archive.6` (both border sides).

### 5.6 Tooltip layout

Inside `completion_reward`: unlock pairs (`unlock_decision_tooltip` then
`<decision>_unlock_tt`, starting "После применения решения: "); native rows with
the law enactment first; the dummy preview through `effect_tooltip` (equal to
the applied delta); at most one `custom_effect_tooltip = NAM_<focus>_reward_tt`
for what native lines cannot show; one `hidden_effect` with the script and the
event call last. Custom values: one fact per line, number before its texticon,
`§G` gains, `§R` losses and prices, `§Y` neutral amounts.

## 6. Shared branches

| Branch | File, section | Cards | Real choice |
|---|---|---|---|
| Trunk | `government.txt`, `government` | `NAM_recognition`, `NAM_law_after_war` | - |
| Neighbours and border | `government.txt`, `government_border` and `government_neighbours` | `NAM_normalisation` -> `NAM_eflor_accord`, `NAM_azhar_accord`; `NAM_border_revenge` -> `NAM_border_citizenship` | normalisation or armed border |
| Civil services | `government.txt`, `government_civil_services` | `NAM_pw_school_network` -> `NAM_national_university`; `NAM_pw_district_hospitals` -> `NAM_pw_regional_reconstruction`, `NAM_pw_municipal_repair` | schools or hospitals |
| Armed forces | `armed_forces.txt` | `NAM_veterans_return` -> `NAM_pw_transport_commission` -> doctrine pair -> `NAM_pw_freight_schedule` -> `NAM_pw_southern_army` -> fleet or air -> `NAM_pw_landing_supply` or `NAM_pw_southern_air_command` | breakthrough (`NAM_pw_breakthrough_army`) or manoeuvre (`NAM_pw_mobile_army`); fleet (`NAM_svetlogorsk_shipyards`) or air (`NAM_pw_air_review`) |
| Economy | `economy.txt` | `NAM_civil_repair` -> `NAM_oil_ministry` -> dividend pair -> `NAM_oil_exchange` -> `NAM_svetlogorye` -> grid or oilfields -> `NAM_pw_power_grid` or `NAM_pw_refinery_engineering` | `NAM_civil_dividend` or `NAM_armed_peace`; `NAM_pw_energy_commission` or `NAM_pw_oil_laboratories` |

- The two outer wings are the readiness spines; the inner wings are optional.
- `NAM_border_citizenship` is the only post-war unlock of
  `NAM_nationalise_region` and also opens `NAM_border_incorporation_eflor` /
  `_azhar`. Both border sides open `NAM_border_reconstruction_eflor` / `_azhar`.
- `NAM_postwar_future_bop` (`common/bop/NAM.txt`, hawks against
  conservatives) is pushed by the border pair (-0.20 / +0.20) and by the path
  cards that the author tied to it (`NAM_ladder_of_seals` among them); its
  initialisation lives in `ADISCORD_nam_resource_war_effects.txt` behind
  `has_power_balance`.

## 7. The three paths

Each path has an opener at (36,2), an opening pair at (33,3) / (39,3) that
installs a leader course, a permanent spirit and a locked law, one wing card
under each side, a spine to the hub (36,13) and the offensive (36,14), one
research-slot keeper off the readiness spine, and two further real forks.

### 7.1 Etatist course (`etatist.txt`)

- Opener `NAM_service_state` (story 320) -> `NAM_ladder_ending_iron` "Исполнительная
  власть" (321) or `NAM_ladder_ending_service` "Служебная республика" (322).
- Wing cards: `NAM_namestnik_garrisons` (garrison order, fuel quota, state
  warehouses; story 328) under the executive; `NAM_pw_cadastre` (titles,
  cadastre, land allotments, district appeals; story 329) under the service
  republic.
- Spine: `NAM_south_black_basin` (southern gate) -> fork `NAM_state_plan` (323)
  or `NAM_regional_trusts` (324) -> `NAM_south_desert_offices` (Kadir embassy,
  southern gate) -> fork `NAM_pw_labour_code` (325) or `NAM_pw_insurance_fund`
  (326) -> hub `NAM_ladder_of_seals` (327) -> `NAM_south_seal_over_furnaces`.
- Off the spine: keeper `NAM_state_project_bureaus` under the basin card;
  `NAM_pw_export_guarantees` (northern invitations, steel project) and
  `NAM_pw_constitutional_committee` (`ADISCORD_nam_resource_war.413`) under the
  embassy.
- Heritage: reserve or fund -> `NAM_pw_postwar_commission` (337) -> military
  rule or local offices -> `NAM_pw_southern_schools`; Veyran union charter or
  Svetlogorsk state (336) -> embarkation staff -> arsenal or convoy ->
  `NAM_veyran_invasion`.

### 7.2 Pragmatic course (`pragmatic.txt`)

- Opener `NAM_pragmatic_compact` (340) -> `NAM_prag_ending_republic` "Республика
  договоров" (341) or `NAM_prag_ending_directorate` "Деловой совет государства"
  (342).
- Wing cards: `NAM_municipal_bonds` under the republic, `NAM_export_clearing`
  under the directorate; both rejoin at `NAM_contract_register` (barter charter,
  emergency service).
- Spine: `NAM_contract_register` -> `NAM_prag_partner_supply` -> fork
  `NAM_prag_treasury_guarantee` (347) or `NAM_prag_private_underwriting` (348)
  -> hub `NAM_balanced_accounts` (349) -> `NAM_prag_south_guarantees`.
- Off the spine: `NAM_insured_caravans` (350; merchant order, export office,
  northern invitations) on the axis; keeper `NAM_port_polytechnic` with the fork
  `NAM_foreign_patents` (343) or `NAM_domestic_designs` (344).
- Heritage: Safir line (351) or Bayrat lease (352) as root alternatives ->
  customs or rail -> `NAM_south_trade_hearing` (353) -> `NAM_south_contract_court`.

### 7.3 District (humanist) course (`districts.txt`)

- Opener `NAM_federal_charter` (360) -> `NAM_charter_ending_federation` "Учредить
  федерацию" (361) or `NAM_charter_ending_oil_union` "Учредить Союз" (362).
  This is the author's opening choice of the humanists. The union side also
  brings deep drilling and the combine projects.
- `NAM_public_utilities` follows either side. Its federation row houses the
  returnees and fires story 368 fifty days later; its union row opens the
  charter fuel aid.
- Forks under the utilities: `NAM_district_militia` (364) or
  `NAM_relief_register` (365); `NAM_municipal_land` (366) or
  `NAM_tenant_councils` (367).
- Spine: `NAM_public_utilities` -> `NAM_south_fenn_guarantee` (district schools,
  emergency well repair) -> `NAM_south_oil_for_water` (southern gate) -> hub
  `NAM_common_fuel_market` (372; on the union route story 369 follows 30 days
  later) -> `NAM_south_oil_charter`. The hub and the keeper need the militia or
  the relief service through `available`.
- Off the spine: keeper `NAM_regional_university` (370); `NAM_kadir_oil_charter`
  under the signal corps.
- Heritage: builders (373) or elected watch (374) -> water councils or ward
  magistrates -> `NAM_south_delegates` (375) -> `NAM_south_free_communities`.

## 8. Absorbers and absorbed focuses

Ids without the `NAM_` prefix. "First rebuild" = 220 to 119 focuses, "second
cut" = 119 to 77. A first-rebuild fold whose absorber was folded again is shown
with its intermediate card; a fold split between two absorbers is listed under
both.

| Absorber | First rebuild | Second cut |
|---|---|---|
| normalisation | border_administration (via foreign_office), border_compacts | foreign_office |
| border_revenge | border_administration (via foreign_office), border_security | foreign_office |
| pw_school_network | - | pw_returnee_registration |
| pw_district_hospitals | - | pw_returnee_registration |
| national_university | - | pw_civil_communications |
| border_citizenship | neighbour_national_charters (via neighbour_local_commands) | neighbour_local_commands |
| service_state | seal_registry | - |
| ladder_ending_iron | appointed_prefects, pw_military_governors | - |
| ladder_ending_service | civil_service_exam, pw_civil_police | - |
| namestnik_garrisons | pw_mobilisation_register, pw_strategic_guard, pw_officer_appointments and pw_defence_accounts (via pw_armament_inspectorate), pw_state_warehouses (via oil_quotas) | oil_quotas, pw_armament_inspectorate |
| south_black_basin | pw_public_supply | state_logistics_grid |
| pw_cadastre | pw_administrative_courts, pw_civil_payroll and pw_public_procurement (via pw_central_treasury) | pw_central_treasury, district_inspectorate |
| state_project_bureaus | engineering_collegium, building_code and pw_labour_inspection (via works_commission) | works_commission |
| state_plan | pw_cabinet_statute, unified_standards, distribution_board and pw_tool_reserve (via pw_industrial_commission) | pw_industrial_commission |
| regional_trusts | pw_state_chamber, pw_industrial_credit, pw_standard_projects (via development_bank) | development_bank |
| pw_export_guarantees | pw_survey_corps and pw_local_design_offices (via basin_reservoirs) | basin_reservoirs |
| pw_constitutional_committee | reconstruction_statute | - |
| pw_labour_code | pw_technical_training, pw_arbitration_commissions and pw_social_budget (via pw_employment_offices) | pw_employment_offices |
| pw_insurance_fund | pw_company_housing (via pw_family_pensions) | pw_family_pensions |
| pragmatic_compact | commercial_courts | - |
| municipal_bonds | customs_clearinghouse | prag_city_works, commercial_commonwealth |
| export_clearing | - | licensed_assembly, machine_tool_contracts |
| contract_register | - | repair_depots, warehouse_receipts (relief port) |
| prag_partner_supply | prag_settlement_agreements, prag_border_protocol, through_waybill (via tractor_leasing) | tractor_leasing |
| balanced_accounts | commercial_reserve, freight_exchange (via freight_brokerage), bonded_terminal (via chartered_tonnage) | freight_brokerage (freight rule), chartered_tonnage (silo), warehouse_receipts (silo, warrant) |
| insured_caravans | merchant_charter (via port_agreement), freight_exchange (via freight_brokerage), bonded_terminal (via chartered_tonnage) | port_agreement, freight_brokerage (unlock), chartered_tonnage (convoys) |
| port_polytechnic | - | testing_office |
| foreign_patents | precision_gauges and relay_trials (via licensed_workshop) | licensed_workshop (licence side) |
| domestic_designs | precision_gauges and relay_trials (via licensed_workshop) | licensed_workshop (design side) |
| federal_charter | district_council | - |
| charter_ending_oil_union | haulage_cooperatives and tool_cooperatives (via cooperative_congress) | cooperative_congress (drilling), district_workshops (project slots) |
| public_utilities | municipal_services, workers_inspection | returnee_offices, civic_audit, common_citizenship, oil_fund, rural_grid |
| south_fenn_guarantee | - | rescue_college, water_boards |
| district_militia | - | relief_reserves |
| relief_register | relief_trains, mobile_clinics | relief_reserves |
| regional_university | open_libraries, district_scholarships | - |
| municipal_land | - | district_workshops |
| tenant_councils | - | district_workshops |
| common_fuel_market | public_credit (via district_fair), haulage_cooperatives and tool_cooperatives (via cooperative_congress) | cooperative_congress (delivery), district_fair, relief_reserves (fuel) |
| veterans_return | pw_army_review, pw_reserve_centres | - |
| pw_transport_commission | pw_freight_depots, pw_logistics_depots | - |
| pw_breakthrough_army | pw_engineer_units, pw_artillery_observers, pw_rail_priority, pw_river_crossings | - |
| pw_mobile_army | pw_field_workshops, pw_road_priority, pw_southern_corridor | - |
| pw_freight_schedule | pw_rail_workshops, pw_transport_maintenance | - |
| pw_southern_army | pw_staff_exercises, pw_combined_arms | - |
| svetlogorsk_shipyards | pw_naval_workshops, pw_escort_fleet, pw_strike_fleet and pw_crew_schools (via pw_naval_review) | pw_naval_review (fork role, story 303) |
| pw_landing_supply | pw_naval_fuel_depots, pw_naval_service | - |
| pw_air_review | pw_airfield_network, pw_flight_schools | - |
| pw_southern_air_command | pw_radar_posts, pw_air_supply, pw_ground_control, pw_power_reserve, pw_frontline_air and pw_engine_workshops (via pw_air_defence) | pw_air_defence |
| civil_repair | reclaim_230, pw_industrial_recovery | - |
| civil_dividend | export_consortium, pw_civil_engineering, pw_industrial_sites | - |
| armed_peace | state_refineries, pw_arms_engineering, pw_chemical_works | - |
| oil_exchange | depot_inquiry, depot_revoke, depot_reserve_charter | - |
| svetlogorye | pw_toolmaking | - |
| pw_energy_commission | svetlogorsk_dam, pw_regional_power | - |
| pw_oil_laboratories | pw_oil_equipment | - |
| pw_power_grid | pw_grid_dispatch, pw_irrigation_works and pw_reservoir_survey (via pw_water_intakes) | pw_water_intakes |
| pw_refinery_engineering | pw_fuel_reservoirs | middle_loren_wells |
| pw_strategic_reserve (heritage) | pw_war_accounts | - |
| pw_development_fund (heritage) | pw_unified_budget, pw_southern_industrial_repair | - |
| pw_postwar_commission (heritage) | pw_demobilisation_board, pw_civil_administration, pw_permanent_institutions | - |
| veyran_invasion (heritage) | veyran_counterplan | - |

Moved story events: 303 to `NAM_svetlogorsk_shipyards`, 328 to
`NAM_namestnik_garrisons`, 329 to `NAM_pw_cadastre` (each `days = 2`), 368 to
`NAM_public_utilities` on the federation route (`days = 50`), 369 to
`NAM_common_fuel_market` on the union route (`days = 30`, after 372). The
pragmatic sea-or-land fork and its events 345 / 346 were retired; its delivery
bonuses on `NAM_pw_merchant_order` were dropped by the caps.

## 9. Hand-over to the war for the South

- `ADISCORD_south_nam_focus_ready` (south final war triggers) needs the shared
  five `NAM_svetlogorye`, `NAM_oil_exchange`, `NAM_pw_transport_commission`,
  `NAM_pw_southern_army`, `NAM_pw_freight_schedule` and one path pair:
  `NAM_ladder_of_seals` + `NAM_south_desert_offices`, `NAM_balanced_accounts` +
  `NAM_prag_partner_supply`, or `NAM_common_fuel_market` +
  `NAM_south_oil_for_water`. No optional focus is a prerequisite of these.
- The offensives (cost 6) need `NAM_svetlogorye`, no war and
  `ADISCORD_south_final_focus_available` (offensive policy, finished
  preparation, the crisis warning); with `NAM_svetlogorye` completed they are
  bypassed once the war has started or been resolved. Their reward is the southern contract idea and the call of
  `ADISCORD_south_prepare_offensive`; nothing after the offensive is played in
  this tree.
- Southern gates on the spines: `NAM_south_black_basin` and
  `NAM_south_desert_offices` (etatist), `NAM_south_fenn_guarantee` and
  `NAM_south_oil_for_water` (district); `NAM_kadir_oil_charter` sits one card
  off the district spine. Northern invitations: `NAM_pw_export_guarantees`,
  `NAM_insured_caravans`, `NAM_eflor_accord` / `NAM_azhar_accord`.
- Spine story windows (path days, trunk excluded): etatist 23 / 51 / 86 / 121 /
  149; pragmatic 23 / 51 / 114 / 142; district federation 22 / 50 / 85 / 113 /
  141, union 22 / 50 / 85 / 141 / 170.

### 9.1 AI plans

`common/ai_strategy_plans/ADISCORD_NAM_plans.txt`: `NAM_postwar_vertical_plan`
(etatist), `NAM_postwar_pragmatic_plan`, `NAM_postwar_plan` (district). Each is
the normal route plus at most three optional focuses, one side of every pair,
the offensive as the last row, event focuses at least 21 days apart. The
offensives complete on plan days 567 / 574 / 581; the keepers on days 203 /
294 / 315. The vertical plan takes the executive, the plan and the labour duty;
the pragmatic plan the republic, the treasury guarantee and the domestic
designs; the district plan the federation, the militia and the tenants'
councils. No plan takes the schools side, so an AI path holds one post-war slot.
The heritage plans `NAM_south_heritage_plan`, `NAM_south_heritage_vertical_plan`
and `NAM_south_heritage_pragmatic_plan` run while the heritage tree is loaded.

## 10. Research slots

Every path reaches exactly two post-war slots on one route:
`NAM_national_university` (shared, schools side, 14 days) and its own keeper,
`NAM_state_project_bureaus`, `NAM_port_polytechnic` or
`NAM_regional_university`. A keeper costs 9, carries `FOCUS_FILTER_RESEARCH`,
has `add_research_slot = 1` as the first row of `completion_reward`, has no
exclusive partner and stands off the readiness spine. No heritage focus grants
a slot. Pinned by `test_every_path_ends_with_the_same_postwar_research_slots`.

## 11. Nationalisation during the war for the South

`NAM_nationalise_region` (category `NAM_administration`, visible while
`NAM_mainland_programmes_active`) is visible once `NAM_nationalisation_unlocked`
holds (`NAM_border_citizenship` in this tree). Its `available`,
`cancel_trigger` and `remove_effect` read `NAM_nationalisation_country_ready`:

- `NAM_independent_programmes_operable` and either `has_war = no` or
  `NAM_nationalisation_south_war_only`;
- `NAM_nationalisation_south_war_only`: `ADISCORD_south_final_active`, NAM on
  the northern side (`ADISCORD_south_on_north_side`), and every enemy is SHL, an
  SHL subject, an SHL faction member or a country with
  `ADISCORD_south_on_shl_side`. Subjects and faction members are matched by
  relation because the side variable is written only for SHL, the side-choice
  joiners and SLF.

So the decision stays visible and can be started during the war for the South,
and a programme paid before the war keeps running and settles on its own
receipt (`NAM_nationalisation_pending`). Any other enemy still blocks new
programmes and cancels running ones with the refund. The trigger file sections
"Nationalisation of held regions" and the tooltip `NAM_nationalisation_ready_tt`
carry the text. `NAM_border_incorporation_*`, `NAM_border_reconstruction_*`
and the state projects had no war gate and need none. The defeat and exile
unlocks read the same trigger. Pinned by
`tools/tests/test_adiscord_postwar_nationalisation.py`
(`test_svetlogorye_nationalises_during_the_war_for_the_south`,
`test_svetlogorye_war_for_the_south_keeps_the_other_war_rules`).

## 12. Source files and their readers

| Source | Content | Readers |
|---|---|---|
| `focus_trees/NAM/postwar/focuses.txt` | header, `country` weight, `# @include` order | builder |
| `focus_trees/NAM/postwar/government.txt` | trunk, border, civil services, neighbours | builder |
| `focus_trees/NAM/postwar/etatist.txt` | etatist sections `etatist_ladder`, `etatist_plan`, `etatist_works`, `etatist_constitution` | builder |
| `focus_trees/NAM/postwar/pragmatic.txt` | `pragmatic_compact`, `pragmatic_industry`, `pragmatic_freight` | builder |
| `focus_trees/NAM/postwar/districts.txt` | `districts_charter`, `districts_services`, `districts_municipal`, `districts_cooperatives` | builder |
| `focus_trees/NAM/postwar/armed_forces.txt`, `economy.txt` | outer wings | builder |
| `focus_trees/NAM/postwar/southern_settlement.txt` | the whole heritage tree | builder (second source of the same output) |

- `python -B -m tools.builders.build_adiscord_focus_trees --check` / `--apply`
  writes `common/national_focus/ADISCORD_NAM_postwar.txt` (owner recorded in
  `tools/data/generated_output_owners.json`); never edit the output.
- The tests read the generated output: `tools/tests/test_adiscord_nam_focus.py`
  (class `NamPostwarDesignTests` and the older post-war tests),
  `test_adiscord_postwar_nationalisation.py`,
  `test_adiscord_party_representation.py`, `test_adiscord_south_final_war.py`.
- Hubs: `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt` (laws,
  trades, settle effects), `common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt`,
  `common/decisions/ADISCORD_nam_resource_war_decisions.txt`,
  `common/ideas/ADISCORD_nam_resource_war_ideas.txt` (laws, aggregate previews,
  story spirits), `common/scripted_localisation/ADISCORD_nam_resource_war_scripted_loc.txt`,
  `events/ADISCORD_nam_resource_war_events.txt` (story events, namespace
  `ADISCORD_nam_story`), `localisation/{russian,english}/ADISCORD_nam_resource_war_l_*.yml`,
  `common/ai_strategy_plans/ADISCORD_NAM_plans.txt`.
- The corporate exile and return-war routes (`NAM_board_`, `NAM_rtw_`,
  `NAM_isl_`, `NAM_sub_`) share these hubs and are not part of this tree.

## 13. Left for later

1. Counts against time (section 1). If the author prefers the counts, the full
   route rises to about 780 days and each path takes back about four cards,
   first the opening sides' wing cards; the naval special project
   (`common/special_projects/projects/naval_projects.txt`) reading a merged
   focus would free 28 shared days.
2. Research-slot campaign cap: with the pre-war `NAM_technical_college` a
   victory campaign can hold three extra slots against the mod's usual cap of
   two. If the cap must hold, the keepers lose the slot and every full route
   shortens by 49 days.
3. Taste choices the author may reverse without touching the budget: the naval
   fork card keeps the name "Верфи Светлогорска"; `NAM_border_revenge` takes the
   group push Гарнизоны +12, Экспортные конторы -6; drought and blackout
   prevention add +15 days to the incident interval once; the pragmatic path
   keeps the licences-or-designs fork and retired the sea-or-land fork; the
   etatist project slots come with the keeper; the district keeper hangs from
   the utilities with the militia or relief choice in `available`.
4. Values dropped by the merge caps, for review: the etatist namestnik's
   maximum entrenchment and the merged inspections' aggregate lines, the export
   guarantees' fuel silo in 700 and +5 steel in 690; the pragmatic extra fuel,
   navy experience, merchant-order bonuses, the commonwealth aggregate and the
   120 artillery / 120 anti-air rows; the district relief silo in 690, the
   union market's 700 treasury and the utilities' stability row; the shared
   navy experience, the foreign office's political power and the school
   network's own political power.
5. Runtime: a full restart with fresh logs, the event windows and their
   timeouts, the AI plans in a running campaign and the nationalisation
   decision across the war start remain to be checked by hand.
