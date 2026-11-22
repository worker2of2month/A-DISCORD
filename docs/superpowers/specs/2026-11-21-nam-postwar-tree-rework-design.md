# NAM post-war tree and South heritage tree

Status: implemented in the focus sources and the NAM and South hubs. The
post-war tree `NAM_postwar_focus` holds 153 focuses (62 shared, 31 etatist, 30
pragmatic, 30 district); the South heritage tree `NAM_south_heritage_focus`
holds 33 and is unchanged by this design. The war for the South is timed from
Svetlogorye's victory, a nine-country influence contest runs until the war
starts, and the private fuel depots are a board game played through the depot
lane. Nothing in this record was checked in the running game; the native
loader, tooltips, event windows, the basin and south maps, the AI plans and the
calendar need a manual check with a full restart.

This record is the contract for maintainers. Where the focus sources and this
record disagree, the sources win and this record is corrected.

## 1. The author's orders and answers

Standing orders, in the author's words where they were given:

- "ветку почистить, сделать симметричнее, часть фокусов объединить, усилить".
- "пути федерации \ союза я бы сделал как изначальный выбор на пути гуманистов".
- "И пусть национализация не пропадает после начала войны за юг."
- "всем одинаковое количество" (research slots after the war).
- "можно убрать": `NAM_pw_southern_army` has no army-size condition; it needs
  only `NAM_pw_operable`. No test or document may ask for the old 180000-men row.
- Each path opens with its own choice; every path ends with the same number of
  post-war research slots; a development trade may lower any track; the layout
  is mirrored about the centre column; rewards follow The Fire Rises (several
  felt rewards of different kinds per focus, story events on important
  focuses, locked laws, development trades); descriptions carry no mechanics.

The size orders of the second design (about 540 days, about 95 focuses) no
longer bind: the approved third design gives the war for the South more time
instead of cutting the tree. The tree is a branching tree of about 92 cards per
view, with real pairs on six or seven rows, and the deadline is counted from the
victory (section 4).

Answers to the open questions of the third design (2026-11-22):

1. Routes without a Svetlogorye victory use a 540-day window - agreed.
2. Mandate variants of the two inner lane ends - "давай, но осторожно, чтобы не
   перегружать". Each view draws its own card at 11,8 and 31,8 (section 3.3);
   each variant adds exactly one result of a different kind.
3. New Shahrabad focuses for the longer wait - later, a separate task.
4. The spheres deal keeps Shahrabad's consent (`ADISCORD_south.72` is SHL's
   choice).
5. The depot press move costs 50 political power.
6. Readiness and an offensive for the corporate exile route - later, a separate
   task.

Kept as designed without a separate answer: the normal route of 920-950 days
inside the three-year window (heavy Shahrabad pulls cost the player optional
cards); the etatist hub takes one faction lane end while the council needs one
card of each faction; the district cards at 26,5 and 18,8 are
`NAM_schools_hospitals_fuel` and `NAM_well_partnerships` (the debt buy-out stays
pragmatic); the Azhar accord stays folded into `NAM_eflor_accord`
("Пограничный договор").

## 2. Loading and lifecycle

- `NAM_postwar_focus` loads at the resource-war victory and at the standoff
  settlement (`ADISCORD_nam_resource_war_resolve_nam_victory` and the standoff
  branch of the same file). Both call `NAM_open_postwar_future` (which seeds the
  depot board) and set the South deadline anchor with a 1095-day window before
  `ADISCORD_south_begin_preparation`. The pre-war tree is shared history, so its
  completions stay readable through `has_completed_focus`.
- The offensive focus calls `ADISCORD_south_prepare_offensive`. At the start of
  the war `ADISCORD_south_begin_hostilities` calls `NAM_pw_south_war_handover`
  (the operations plan chosen in `ADISCORD_nam_story.312` becomes a 120-day
  spirit, the war conversion a 180-day spirit) before
  `ADISCORD_south_load_war_tree` records the tree in `ADISCORD_south_prior_tree`
  (value 2) and loads `NAM_south_war_focus` with `keep_completed = yes`.
  `ADISCORD_south_close_member_state` removes the four hand-over spirits, each
  behind `has_idea`. `NAM_pw_operations_plan` is not cleared: a war restarted
  after a repelled one installs the plan again.
- A southern victory of NAM (`NAM_won_final_southern_war`) loads
  `NAM_south_heritage_focus`. Any other outcome restores the recorded tree
  through `ADISCORD_south_restore_prior_tree`.
- Locked laws stay through the war tree, the heritage tree and a restored
  post-war tree. Nothing repeals them; a later change must be an explicit
  scripted `swap_ideas`.
- The influence contest is seeded when the preparation opens and cleared when
  the war starts (section 5.6). The depot board pauses during any war of NAM and
  resolves by its total when the war for the South is resolved (section 6.2).

## 3. Shape of the post-war tree

Grid x 0..42, y 0..11, axis x = 21, mirror (x, y) <-> (42 - x, y). Every card
off the axis has a twin cell inside its own part and view.

| Zone | Part | Columns | Rows | Fixed cells |
|---|---|---|---|---|
| Trunk | shared | 21 | 0-1 | `NAM_recognition` 21,0, `NAM_law_after_war` 21,1 |
| Army | shared, `armed_forces.txt` | 0-6 | 1-8 | head `NAM_veterans_return` 3,1, lane end `NAM_pw_southern_operations` 3,8 |
| Influence | shared, `influence.txt` | 8-14 | 2-8 | head `NAM_foreign_office` 11,2, lane end 11,8 (path variant) |
| Path block | etatist / pragmatic / district | 16-26 | 2-11 | opener 21,2, opening pair 18,3 / 24,3, ports 16,5 / 16,8 / 26,5 / 26,8, hub 21,10, offensive 21,11 |
| Depots | shared, `depots.txt` | 28-34 | 2-8 | head `NAM_depot_inquiry` 31,2, lane end 31,8 (path variant) |
| Economy | shared, `economy.txt` | 36-42 | 1-8 | head `NAM_civil_repair` 39,1, lane end `NAM_pw_industrial_sites` 39,8 |

- Columns 7, 15, 27 and 35 hold no card. Columns 15 and 27 carry only the four
  port wires.
- Each path card carries `allow_branch` with its frozen mandate
  (`NAM_prewar_service_mandate`, `NAM_prewar_pragmatic_mandate`,
  `NAM_prewar_district_mandate`; `NAM_prewar_balance` below -0.30, between, or
  above +0.30) and the same mandate in `available`, with `cancel_if_invalid =
  yes` and `continue_if_invalid = no`. No shared card has `allow_branch`, and no
  shared card requires a path card.
- Drawn lines between zones: `NAM_recognition` to the three heads 3,1 / 21,1 /
  39,1; `NAM_law_after_war` to 11,2 / 21,2 / 31,2; the four ports, where the path
  card lists a shared card as an OR alternative to its in-path parent:

| Port | Shared parent | Etatist | Pragmatic | District |
|---|---|---|---|---|
| 16,5 | `NAM_south_coast_envoys` 14,4 | `NAM_pw_export_guarantees` | `NAM_insured_caravans` | `NAM_common_citizenship` |
| 16,8 | `NAM_south_press_shahrabad` 13,7 | `NAM_pw_veyr_convoys` | `NAM_commercial_commonwealth` | `NAM_oasis_voices` |
| 26,5 | `NAM_depot_audit` 28,4 | `NAM_pw_concession_prosecutor` | `NAM_warehouse_receipts` | `NAM_schools_hospitals_fuel` |
| 26,8 | `NAM_depot_reserve_charter` 29,7 | `NAM_pw_treasury_fuel_stores` | `NAM_bonded_terminal` | `NAM_town_fuel_cooperatives` |

  Every other dependency between parts is an `available` condition inside a
  `custom_trigger_tooltip`.
- Placement: every card is placed by `relative_position_id` (same-column direct
  parent, else the nearest axis ancestor for axis cards, else the nearest
  parent). Path cards never anchor on shared cards, except the opener and the six
  lane-end variants, which anchor on their lane.
- Layout rules: unique cells per view; a free column between horizontal
  neighbours; a child below its parents (97 % of edges step one row); exclusive
  partners on one row, 2-6 columns apart, with nothing on the connector; no wire
  through a card and no crossing; no single-parent straight chain longer than two
  (the trunk to the opener is the stated exception); every lane head forks.

### 3.1 The three views

| | Etatist | Pragmatic | District |
|---|---|---|---|
| Cards (shared + path) | 93 (62 + 31) | 92 (62 + 30) | 92 (62 + 30) |
| Exclusive pairs (rows) | 19 (2, 3, 4, 6, 7, 9) | 20 (2, 3, 4, 6, 7, 9) | 19 (2, 3, 4, 6, 7, 8, 9) |
| Merges / AND merges | 29 / 6 | 31 / 6 | 30 / 7 |
| Leaf rows | 5, 6, 7, 8, 11 | 5, 6, 7, 8, 11 | 5, 6, 7, 8, 9, 11 |
| Costs c1 / c2 / c3 / c4 / c6 / c9 | 19 / 51 / 16 / 5 / 1 / 1 | 19 / 50 / 16 / 5 / 1 / 1 | 20 / 50 / 14 / 6 / 1 / 1 |

62 of 92-93 cards (67 %) are the same in all three views. The paths steer the
shared lanes through the four ports, the depot hooks (section 6.6), the contest
tools (section 5.4) and the two lane-end variants.

### 3.2 Shared lanes

| Lane | Head | Pairs | Readiness and ends |
|---|---|---|---|
| Army | `NAM_veterans_return` | doctrine `NAM_pw_breakthrough_army` / `NAM_pw_mobile_army`; haulage `NAM_pw_road_priority` / `NAM_pw_rail_priority`; `NAM_svetlogorsk_shipyards` / `NAM_pw_air_review` | readiness `NAM_pw_transport_commission`, `NAM_pw_freight_schedule`, `NAM_pw_southern_army` (AND of the freight schedule and `NAM_pw_staff_exercises`); end `NAM_pw_southern_operations` (story 312, the war plan) from the shipyards or the air command; `NAM_pw_landing_supply` is a leaf on row 7 |
| Economy | `NAM_civil_repair` | `NAM_civil_dividend` / `NAM_armed_peace`; `NAM_export_consortium` / `NAM_state_refineries`; `NAM_pw_energy_commission` / `NAM_pw_oil_laboratories` | readiness `NAM_oil_exchange`, `NAM_svetlogorye` (AND of the exchange and `NAM_national_university`); end `NAM_pw_industrial_sites` from the laboratories or the grid; `NAM_pw_refinery_engineering` is a leaf on row 7 |
| Influence | `NAM_foreign_office` (story 380) | `NAM_normalisation` / `NAM_border_revenge`; `NAM_south_desert_envoys` / `NAM_south_coast_envoys`; kill stub `NAM_south_spheres_deal` / `NAM_south_coalition_council`; `NAM_south_league_of_guarantees` / `NAM_south_press_shahrabad` (story 383) | `NAM_eflor_accord`, `NAM_border_citizenship`, `NAM_border_administration`, `NAM_south_legations`, `NAM_south_congress` (story 381); end at 11,8 |
| Depots | `NAM_depot_inquiry` (story 390, opens the board) | `NAM_depot_boiler_houses` / `NAM_depot_dispatchers_strike`; `NAM_depot_audit` / `NAM_depot_export_ban`; kill stub `NAM_depot_owners_settlement` (story 393) / `NAM_depot_trial` (story 391); ending pair `NAM_depot_revoke` / `NAM_depot_reserve_charter` | `NAM_depot_double_invoices`, `NAM_depot_town_receipts`, `NAM_depot_rail_crews`, `NAM_depot_open_hearing`, `NAM_depot_station_committees`; end at 31,8 |

- `NAM_pw_district_hospitals` absorbs the former regional reconstruction and
  municipal repair cards; `NAM_national_university` absorbs the school network
  (story 310) and grants the shared research slot.
- `NAM_border_citizenship` is the only post-war unlock of
  `NAM_nationalise_region` and also opens `NAM_border_incorporation_eflor` /
  `_azhar`. Both border sides open `NAM_border_reconstruction_eflor` / `_azhar`
  and fire `ADISCORD_nam_archive.6`.
- `NAM_export_consortium` pushes 8 on every contest country holding
  `NAM_oil_client`.

### 3.3 Lane-end variants by mandate

The cells 11,8 and 31,8 carry three cards each in the source, one per mandate,
so every view draws exactly one. The three share cost (c3), prerequisites,
`available`, bypass and cell. Influence variants anchor on
`NAM_south_league_of_guarantees` (x 2, y 1); depot variants on `NAM_depot_revoke`
(x -2, y 1). Each calls the lane's shared core once and adds one path result.

| Cell | Core (NAM effects) | Etatist | Pragmatic | District |
|---|---|---|---|---|
| 11,8, after `NAM_south_league_of_guarantees` or `NAM_south_press_shahrabad`, operable and at peace | `NAM_south_coalition_compact_core`: Svetlogorye's campaign alliance when not in a faction, +8 % war support, +100 political power, and while the contest is open power +3 and push 5 on every country leaning 20 or more toward Svetlogorye | `NAM_south_namestnik_pact`: writ holders shift their home lean +10 and gain `ADISCORD_south_guaranteed_by_north`; without a writ holder +25 command power | `NAM_south_trade_coalition`: +100 treasury per contract holder now (at least 100); each held contract pays +40 per contest cycle instead of +20 | `NAM_south_communities_compact`: +2500 manpower per charter holder (at least 2500) |
| 31,8, after `NAM_depot_revoke` or `NAM_depot_reserve_charter`, at peace; bypassed when the board was conceded | `NAM_depot_fuel_service_core`: +100 political power, +35000 fuel, one fuel silo in 67 and one in 690 with their own slots (owner and controller rechecked, 450 treasury fallback each), groups oil +12 / trade -6, aggregate fuel gain +8 %, stability +3 %, administrative expense +3 % | `NAM_depot_state_fuel_service`: court fines, 100 treasury + 25 per piece of evidence, at most 400 | `NAM_depot_fuel_service_shares`: trade income +5 % in the aggregate (one preview shows the whole delta) | `NAM_depot_cooperative_fuel_service`: timed spirit `NAM_town_boiler_cooperatives` (stability +5 %, political power +5 %) for 365 days after the cooperative revocation, else 180 |

- Each variant queues the lane's story event itself: `ADISCORD_nam_story.382`
  (`days = 2`) at 11,8, `ADISCORD_nam_story.392` (`days = 2`) at 31,8.
- Readers use the OR triggers `NAM_south_compact_signed` and
  `NAM_depot_fuel_service_founded`, never one variant id.
- `NAM_depot_board_close` keeps `NAM_depot_evidence`; only
  `NAM_depot_state_fuel_service` reads and clears it.

### 3.4 Path blocks

Every block is opener -> opening pair -> three sub-lanes (left: the South;
axis: the course's own institutions; right: industry, depots and towns) -> hub
-> offensive, with a research-slot keeper off the readiness route.

| | Etatist (`etatist.txt`) | Pragmatic (`pragmatic.txt`) | District (`districts.txt`) |
|---|---|---|---|
| Opener 21,2 | `NAM_service_state` (320) | `NAM_pragmatic_compact` (340) | `NAM_federal_charter` (360) |
| Opening pair 18,3 / 24,3 | `NAM_ladder_ending_iron` (321) / `NAM_ladder_ending_service` (322) | `NAM_prag_ending_republic` (341) / `NAM_prag_ending_directorate` (342) | `NAM_charter_ending_federation` (361) / `NAM_charter_ending_oil_union` (362) |
| Left sub-lane | hawks: `NAM_namestnik_garrisons`, `NAM_pw_mobilisation_register`, `NAM_pw_military_governors` (331) / `NAM_pw_officer_appointments` (332), `NAM_pw_forward_bases` | `NAM_municipal_bonds`, `NAM_prag_settlement_agreements` (354) / `NAM_prag_south_bills` (355), `NAM_prag_partner_supply`, `NAM_prag_contract_union` (356) / `NAM_prag_credit_supplies` (357) | `NAM_community_charter` (363), `NAM_south_aid_caravans`, `NAM_mutual_aid_funds`, `NAM_oasis_voices` (376) / `NAM_well_partnerships` (377), `NAM_kadir_oil_charter`, `NAM_south_oil_for_water` |
| Axis | `NAM_south_black_basin`, `NAM_pw_armament_inspectorate` (328), `NAM_state_plan` (323) / `NAM_regional_trusts` (324), `NAM_south_desert_offices`, `NAM_pw_council_of_seals` (330), `NAM_pw_labour_code` (325) / `NAM_pw_insurance_fund` (326) | `NAM_commercial_courts`, `NAM_contract_register`, `NAM_commercial_reserve`, `NAM_prag_treasury_guarantee` (347) / `NAM_prag_private_underwriting` (348), `NAM_customs_clearinghouse` | `NAM_public_utilities`, `NAM_south_fenn_guarantee`, `NAM_district_council`, `NAM_district_militia` (364) / `NAM_relief_register` (365) |
| Right sub-lane | conservatives: `NAM_pw_cadastre` (329), `NAM_pw_constitutional_committee` (`ADISCORD_nam_resource_war.413`), `NAM_pw_administrative_courts`, `NAM_pw_cabinet_statute` (334) / `NAM_pw_state_chamber` (333), `NAM_reconstruction_statute` | `NAM_export_clearing`, `NAM_machine_tool_contracts`, `NAM_domestic_designs` (344) / `NAM_foreign_patents` (343), `NAM_tractor_leasing` / `NAM_chartered_tonnage` | `NAM_municipal_services`, `NAM_district_workshops`, `NAM_municipal_land` (366) / `NAM_tenant_councils` (367), `NAM_district_fair` (369), `NAM_rural_grid` / `NAM_public_credit` |
| Hub 21,10 | `NAM_ladder_of_seals` (327) | `NAM_balanced_accounts` (349) | `NAM_common_fuel_market` (372) |
| Offensive 21,11 | `NAM_south_seal_over_furnaces` | `NAM_prag_south_guarantees` | `NAM_south_oil_charter` |
| Keeper (c9) | `NAM_state_project_bureaus` 21,5 | `NAM_port_polytechnic` 24,7 | `NAM_regional_university` 21,8 (370) |

- Etatist balance: `NAM_postwar_future_bop` (`common/bop/NAM.txt`, hawks
  against conservatives) exists only on this course and is initialised behind
  `has_power_balance`. Every left-lane card pushes it negative and every
  right-lane card positive, all guarded; the opening sides push -0.30 / +0.30,
  the border pair -0.20 / +0.20. `NAM_pw_council_of_seals` collects
  `NAM_south_desert_offices`, `NAM_pw_officer_appointments` or
  `NAM_pw_cabinet_statute` and needs `NAM_pw_mobilisation_register` and
  `NAM_pw_administrative_courts` in `available`; it pays by the balance. The hub
  takes `NAM_pw_forward_bases` or `NAM_reconstruction_statute` and the labour or
  insurance card.
- Pragmatic: `NAM_prag_credit_supplies` takes `NAM_customs_clearinghouse` or
  `NAM_prag_partner_supply`; `NAM_prag_south_bills` buys Shahrabad's credit out
  through `ADISCORD_south_redeem_shl_debt`; the contract union lowers the
  protectorate threshold to 70 for contract holders.
- District: the hub and the keeper need the militia or the relief register
  through `available`. `NAM_common_citizenship` (368) houses the returnees;
  `NAM_town_fuel_cooperatives` sets `NAM_depot_cooperative_route`, and only the
  depot ending pair writes the settlement variant.

### 3.5 Heritage tree

Grid x 0..16, y 0..7, axis x = 8: every view is 17 columns by 8 rows; every card
off the axis has a twin cell at (16 - x, y) inside its own part and view. Root
`NAM_south_heritage` (8,0). The Khan crisis lane is shared by all paths:
`NAM_rus_crisis_watch` (8,1), the pair `NAM_rus_fuel_for_coalition` /
`NAM_rus_demand_share` (6,2) / (10,2), `NAM_rus_expedition_staff` (8,3). Each
path has two mirrored wings with their root children on rows 1-2 inside x 0-4
and 12-16. The etatist path uses two drawn pairs inside its wings
(`NAM_pw_strategic_reserve` / `NAM_pw_development_fund` and
`NAM_veyran_union_charter` / `NAM_svetlogorsk_settlement`); the pragmatic and
district paths exclude their two roots through `available` with a named
tooltip. Views: etatist 17, pragmatic 13, district 13. Heritage routes:
etatist reserve or fund -> `NAM_pw_postwar_commission` (337) -> military rule or
local offices -> `NAM_pw_southern_schools`, and Veyran union charter or
Svetlogorsk state (336) -> `NAM_veyran_invasion`; pragmatic Safir line (351) or
Bayrat lease (352) -> `NAM_south_trade_hearing` (353) ->
`NAM_south_contract_court`; district builders (373) or elected watch (374) ->
`NAM_south_delegates` (375) -> `NAM_south_free_communities`.

## 4. Calendar and budget

### 4.1 The deadline

- Anchor `global.ADISCORD_south_deadline_day` (D) in `global.num_days` units,
  set once per story campaign by `ADISCORD_south_set_deadline` (temp
  `ADISCORD_south_deadline_window`): D = today + window - 15 x
  `global.ADISCORD_south_crisis_pull`, never closer than today + 180.
- Window 1095 days from Svetlogorye's victory and from the standoff, set before
  their `ADISCORD_south_begin_preparation`. Every other route (defeat,
  compromise, retry, return war, great war) gets 540 days inside
  `begin_preparation` at the first opening without an anchor.
- Derived days, written only when D is set or pulled: near D - 31, AI window
  D - 120, pull guard D - 135, early window D - 180. The displayed date
  (`global.ADISCORD_south_deadline_d` / `_m` / `_y`) is computed from
  `global.ADISCORD_south_day0`, the day number of 1 January 2160 written once in
  `on_startup`, on the 365-day calendar.
- Pulls: Shahrabad's consolidation victory counts 3 units, a limited war 2, at
  most 6 (90 days). Before the anchor a unit is only counted; with an anchor it
  moves D by 15 days while more than 135 days remain. No pull while
  `ADISCORD_south_spheres_agreed`.
- Early floor: `ADISCORD_south_preparation_can_finish` and the
  `difficulty > 2` branch of `ADISCORD_south_ai_border_preparation` need
  `ADISCORD_south_early_window_open`, the same rule for both champions. The
  180-day minimum of preparation stays.
- `ADISCORD_south_clear_deadline` runs only where a new story campaign starts
  (island-exile settlement, return-war start, great-war start). A suspended
  preparation or a repelled war keeps the anchor.
- Days after the victory: D 1095 (1005 at full pull); earliest warning 915
  (825); earliest war on a NAM order 971 (881); Shahrabad's automatic attack
  999-1026 (909-936). On a 540-day route the warning opens from start + 360.

### 4.2 Costs and routes

| Cost | Days | Use |
|---|---|---|
| 1 | 7 | quick moves: a minor pair side, a kill stub, a depot or influence move, a port card; never a readiness card, an opening side, a hub or a capstone |
| 2 | 14 | ordinary focus |
| 3 | 21 | lane heads, trunk, path opener, lane-end variants, path turning points |
| 4 | 28 | opening-pair sides, path hub, `NAM_pw_southern_army`, `NAM_svetlogorye`, `NAM_kadir_oil_charter` |
| 6 | 42 | offensive |
| 9 | 63 | path research-slot keeper |

| | Etatist | Pragmatic | District |
|---|---|---|---|
| Cheapest readiness (trunk + shared readiness + path pair) | 588 | 525 | 539 |
| Readiness on the AI plan | 728 | 721 | 728 |
| Normal route (AI plan, offensive excluded) | 931 | 924 | 931 |
| Full route (one side of every pair, offensive excluded) | 1050 | 1022 | 1050 |

- Normal-route shares: trunk 42, army 147, economy 147, influence 133, depots
  133, path 322-329 (window 920-950). Full-route shares: trunk 42, army 161,
  economy 161, influence 147, depots 140, path 399 / 371 / 399. Limits: cheapest
  readiness at most 780, full route at most 1060, the offensive inside the
  56-day warning.
- A normal route reaches readiness long before the early window opens (day
  915) and finishes its last cards before the earliest war (day 971); a full
  pull leaves the player to skip one to four optional cards.
- Readiness = `ADISCORD_south_nam_focus_ready`: `NAM_svetlogorye`,
  `NAM_oil_exchange`, `NAM_pw_transport_commission`, `NAM_pw_southern_army`,
  `NAM_pw_freight_schedule` and one path pair (`NAM_ladder_of_seals` +
  `NAM_south_desert_offices`, `NAM_balanced_accounts` +
  `NAM_prag_partner_supply`, or `NAM_common_fuel_market` +
  `NAM_south_oil_for_water`).

## 5. The influence contest

Owner files: the "Influence contest" sections of
`common/scripted_effects/ADISCORD_south_final_war_effects.txt` and
`_triggers.txt`, `common/decisions/ADISCORD_south_final_war_decisions.txt`,
`events/ADISCORD_south_final_war_events.txt`, the south scripted localisation
and localisation, and the south map builder
`tools/builders/build_adiscord_south_influence_map.py`. In-world text names the
champions, never "north / south camp".

### 5.1 Ledger and seeds

- Nine contested countries (EFL, AZH, WEF, KDR, RHM, SDR, KYZ, MZR, GLP) carry
  `ADISCORD_south_coalition_influence` from -100 (Shahrabad) to +100
  (Svetlogorye) and a home lean `ADISCORD_south_home_lean`.
- `ADISCORD_south_seed_influence` runs from `ADISCORD_south_begin_preparation`
  when `ADISCORD_south_influence_seeded` is unset, so a preparation reopened
  after a repelled war seeds again. Home lean = base (EFL -15, AZH -15, WEF +10,
  KDR -10, RHM 0, SDR 0, KYZ +10, MZR +10, GLP -5) + ties of the day
  (`NAM_oil_client` +10; `ADISCORD_south_indebted_to_SHL` -15 with
  `ADISCORD_south_seed_debt`; `SHL_embassy` -10; faction with SHL -30; at war
  with Shahrabad +20 for KYZ / GLP). The result is added to any existing ledger
  value and clamped.
- Influence power (`ADISCORD_south_influence_power`): champions start at 10;
  NAM caps at 40, others at 30, floor 10. Delegation push 5 + power / 2, adviser
  push power / 2. Svetlogorye reaches about 26-30 by the war through the
  influence lane and path cards; Shahrabad 10 -> 30 by itself (+1 every 56 days,
  +2 per consolidation campaign won, +3 from its coalition focuses, +2 per depot
  share bought by a Shahrabad house; -3 from `NAM_south_press_shahrabad`, -1 from
  `NAM_prag_south_bills` and from `NAM_customs_clearinghouse`).

### 5.2 Cycle and helpers

- `ADISCORD_south_contest_cycle`, one call from the 28-day
  `ADISCORD_south_crisis_cycle` while `ADISCORD_south_contest_open`: drift 3
  toward home, then standing ties (Svetlogorye's tie 1-3, `NAM_oil_client` +2,
  Shahrabad credit -2, `SHL_embassy` -2, faction with NAM +3 / with SHL -3),
  trade returns (+20 treasury per held economic contract, +40 with
  `NAM_south_trade_coalition`; +15 per Shahrabad-leaning country with
  `NAM_customs_clearinghouse`). Fixed nine-tag pass, no world scan, no new
  on_action.
- Push helpers `ADISCORD_south_push_influence_north` / `_shl` (temp
  `ADISCORD_south_push_delta`) act only on a country in the contest and outside
  the pushing champion's closed sphere, and notify a human champion
  (`ADISCORD_south.74`) when 40 or 60 is crossed. `ADISCORD_south_shift_home_lean`,
  `ADISCORD_south_add_influence_power`, `ADISCORD_south_set_north_tie` (largest
  kept) and `ADISCORD_south_redeem_shl_debt` take temp inputs and are boolean
  calls.
- Triggers: `ADISCORD_south_contest_open`, `ADISCORD_south_in_contest`,
  `ADISCORD_south_contest_target_open`, `ADISCORD_south_lean_north_20/40/60/80`,
  `ADISCORD_south_lean_shl_20/40/60/80`, `ADISCORD_south_is_contest_champion`,
  `ADISCORD_south_champion_contest_ready` / `_advisers_ready` (NAM needs
  `NAM_foreign_office` / `NAM_south_legations`).

### 5.3 Thresholds and decisions

| Lean | Consumer |
|---|---|
| 20 | better acceptance of offers; side-choice weight at the war start (+20 at 20-29, +40 at 30-39) |
| 40 | the rival's demands become a push of 10 toward the rival; path tools usable; the country joins that side at the war start (30 with `ADISCORD_south_guaranteed_by_north`) |
| 60 | invitation (`ADISCORD_south.67`) |
| 80 | protectorate offer (70 for contract holders with `NAM_prag_contract_union`) |

Decisions in `ADISCORD_south_final_war_category`, champions only (faction
members and subjects act through their champion), prices through
`custom_cost_text` with `cost = 0`: `ADISCORD_south_build_coalition_influence`
(delegation, 25 political power, camp cooldown 56 days),
`ADISCORD_south_send_advisers` (20 political power, 40 days, host +5 army
experience), `ADISCORD_south_invite_to_coalition`,
`ADISCORD_south_offer_protectorate` (50 political power; the subject type
follows NAM's mandate: namestnik office, economic contract, oil charter; refusal
pushes 10 away and never means war), `ADISCORD_south_council_session` (NAM after
`NAM_south_coalition_council`: 50 political power, push 6 on every country at 20
or more). The invitation gate `ADISCORD_south_north_invitation_unlocked` opens
each country from its own focuses: EFL / AZH from `NAM_eflor_accord` or
`NAM_border_citizenship`, the desert countries from the desert envoys or the
congress plus path cards, the coast countries from the coast envoys or the
congress plus path cards.

### 5.4 Path tools

| Decision | Mandate and unlock | Price | On acceptance (`ADISCORD_south.68` a) | Tie |
|---|---|---|---|---|
| `ADISCORD_south_nam_writ` | etatist, `NAM_south_desert_offices` | 50 political power + 3000 `infantry_equipment` | rifles to the target, push +8, NAM BOP -0.05 | 2; 3 with `NAM_pw_military_governors` |
| `ADISCORD_south_nam_contract` | pragmatic, `NAM_prag_partner_supply` | 30 political power + 300 treasury | target credit and +5 % stability; +20 treasury per cycle while held | 2; 3 at 60+ with the contract union |
| `ADISCORD_south_nam_charter` | district, `NAM_community_charter` | 50 political power + 10000 fuel | fuel to the target; NAM districts group +4 | 2 |

Common rules: lean 40 toward Svetlogorye, no tool held, no escrow, no recent
refusal, no war with NAM or SHL. The decision debits once into
`ADISCORD_south_tool_escrow`; `.68` settles it exactly once (deliver and record
`ADISCORD_south_tool_kind`, or refund everything except political power, push 5
toward Shahrabad and a 56-day refusal cooldown). Cancellation and the contest
close refund the escrow.

### 5.5 Spheres deal and Shahrabad's limited wars

- `NAM_south_spheres_deal` (kill stub, c1) sends Shahrabad `ADISCORD_south.72`.
  Acceptance sets `ADISCORD_south_spheres_agreed` and a sphere per country
  (lean >= 0 to Svetlogorye, else Shahrabad), freezes pushes across the agreed
  spheres and stops the deadline pulls; refusal pushes 5 on all nine and gives
  NAM +5 % war support. Either answer closes the rest of the lane. Every contest
  tooltip shows `ADISCORD_south_spheres_note_tt` while the deal is in force.
- `ADISCORD_south_shl_strike_or_appeal` runs at the start of
  `SHL_start_kyz_war` and `SHL_start_glp_war`. A target leaning more than 20
  toward Svetlogorye while the contest is open appeals instead (`.70` to NAM):
  refuse (push 10 toward Shahrabad, the war goes on at once), send rifles
  (3000 rifles and 25 political power, push 15, war deferred 180 days) or send
  advisers (50 command power, push 8, deferred 90 days). The hidden
  `ADISCORD_south.76` re-arms the war after the deferral; `SHL_ultimatum_veyr`
  refunds its 50 political power when its war is blocked. NAM never enters a
  war before the war for the South.

### 5.6 War start

The ledger of a country is cleared in `ADISCORD_south_join_shl_side` /
`_join_north_side` after its side is set. Countries without a side are cleared
by the hidden SHL event `ADISCORD_south.75`, queued with `days = 1` from
`ADISCORD_south_begin_hostilities` after the side choice `.10`; it also clears
`ADISCORD_south_influence_seeded` and `ADISCORD_south_spheres_agreed`.

Events: `.68` tool consent, `.69` tool answer, `.70` appeal, `.71` appeal
outcome, `.72` spheres offer (SHL), `.73` spheres answer, `.74` threshold
notice, `.75` start cleanup, `.76` strike re-arm. The south map shows the
ledger as "Перевес", both powers and a per-country tooltip; no new GUI file,
no polling.

## 6. The depot game

Owner files: `depots.txt`, the depot sections of
`common/scripted_effects/ADISCORD_nam_resource_war_effects.txt` and
`_triggers.txt`, the category `NAM_depot_concessions`,
`common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt`, `on_daily_NAM`,
the basin map builder `tools/builders/build_adiscord_nam_basin_map.py`, events
`ADISCORD_nam_story.390-401`.

### 6.1 Board

| Site | State | Start share | Yield at share <= 20, per round |
|---|---|---|---|
| Южная гавань | 700 | 80 | +4000 fuel |
| Северные месторождения | 67 | 60 | field condition +5 |
| Южнобережный | 689 | 60 | field condition +5 |
| Сухоречье | 690 | 50 | field condition +5 |
| Ворваньи острова | 225 | 70 | +3000 fuel |

Total 320 of 500; sites not owned and controlled by NAM are dormant. Owners'
funds 0-100 (start 60); fronts court / street / buy-back 0-3; evidence 0-12;
buy-back price 40 treasury per level (20 with the pragmatic hook). The private
share costs 5 x total fuel a day (1600 at the start, paid in `on_daily_NAM`)
and lowers fuel storage by total / 2000 through `NAM_depot_board_dynamic`.

### 6.2 States and rounds

- Seed: `NAM_depot_board_seed` from `NAM_open_postwar_future`, skipped when
  `NAM_depot_concessions_settled`; it replaces `NAM_private_tank_farms`. The
  civilian-economy `on_add` of `common/ideas/_economic.txt` does not re-add the
  spirit once `NAM_depot_board_seeded` is set.
- States: `NAM_depot_board_pending` (seeded, not open), `NAM_depot_board_open`
  (the head card's `NAM_depot_board_open_case`), `NAM_depot_board_ended`
  (`NAM_depot_settlement_variant` set). Fronts, evidence and the discount
  stored while pending act from the first round. Lane cards after the head
  bypass on ended; the head bypasses only on `NAM_depot_concessions_settled`;
  the lane end bypasses on `NAM_depot_board_conceded`.
- Rounds: hidden `ADISCORD_nam_story.395` every 56 days from the head card,
  one self-rescheduling chain. A war pauses it (re-queued in 28 days); the end
  of the war for the South, or 900 days after the seed for the AI, resolves the
  board by its total. Every effect that sets `ADISCORD_south_final_resolved`
  calls `ADISCORD_south_close_nam_depot_board`, which also resolves a pending
  board, so an unopened dispute cannot keep its drain after the war. Round
  order: fronts on the target (doubled with their costs after a press; the
  street front pays 1500 fuel per strength step and skips the round when the
  stock is short), owners' funds and group drift, local yields, the
  owners' move by weights (lockout, lawsuit, sale of a share to a Shahrabad
  house, sabotage, press bribe; events 396-400), the loss check, recompute.

### 6.3 The press move

The selected target marker on the basin map shows "Нажим на площадку" (scripted
GUI of the basin builder, not a decision), visible while the board is open, a
front is active and no press is pending. The click costs 50 political power,
checked with `NOT = { has_political_power < 50 }`, and sets
`NAM_depot_press_next_round`; the next round doubles every active front and its
costs, then consumes the flag. One press per round. The AI presses inside the
round at 150 political power or more.

### 6.4 Endings

| Ending | Condition | Variant |
|---|---|---|
| Revocation | `NAM_depot_revoke` taken with the board won (total <= 100 or every counted site <= 30) | 1, or 3 with `NAM_depot_cooperative_route` |
| Reserve buy-out | `NAM_depot_reserve_charter` taken, won and paid (price 2 x min(total, 100), at most 200) | 2 |
| Settlement | `NAM_depot_owners_settlement` taken | 4: shares and storage frozen, drain halved, +300 treasury |
| Owners win | total >= 450 or three sites sold | 5: event 394 |
| Resolution by total | war for the South resolved with the board pending or open, or the AI at seed + 900 | 6 (event 401): <= 200 as revocation, else as owners win |

`NAM_depot_board_close` clears the open flag and the round rules; variants 1-3
remove the modifier behind `has_dynamic_modifier`, 4-5 keep it frozen.
`NAM_end_depot_concessions` closes an open board on the island-exile route. A
won board stays open until the player takes one side of the ending pair.

### 6.5 Model (not game measurements)

Median day after the victory over the four path variants, 400 runs per row; the
press is paid from a purse of R political power a day set aside for the board.

| Route | No press | 50, R 0.6 | 50, R 0.4 |
|---|---|---|---|
| Lane right after the trunk | 287-343 | 231 | 231-287 |
| Lane worked early | 399-511 | 343-399 | 343-399 |
| Spread, court first | 520-623 | 455-623 | 455-623 |
| Spread, audit | 700-828 | 660-716 | 700-772 |
| AI late lane | 780-878 | 710-766 | 710-780 |
| Head only / head and court head | not won; lost in up to 58 % | not won | not won |

### 6.6 Path hooks

- Etatist `NAM_pw_concession_prosecutor` (26,5): court +1, evidence +3, target
  -12; `NAM_pw_treasury_fuel_stores` (26,8) pushes the sites, or gives fuel gain
  +8 % and +10000 fuel after the reserve ending.
- Pragmatic `NAM_warehouse_receipts` (26,5): buy-back discount and buy-back +1;
  `NAM_bonded_terminal` (26,8): target -8, +10000 fuel more after the reserve
  ending.
- District `NAM_schools_hospitals_fuel` (26,5): street +1, target -8;
  `NAM_town_fuel_cooperatives` (26,8): `NAM_depot_cooperative_route` and target
  -12, or the lease after an ended revocation or reserve.
- Each hook reads `NOT = { NAM_depot_board_ended = yes }`; its treasury fallback
  is paid only when the board has ended.

The category `NAM_depot_concessions` holds no decisions on this tree; its
description `[NAMDepotBoardReport]` reports the pending, open, won or ended
board. The eight old ladder decisions and `NAM_depot_public_hearing` stay for
routes without this tree and hide once `NAM_depot_board_seeded` is set.

## 7. Standards

### 7.1 Reward magnitudes

Main row by cost; the secondary row is another kind at about a third.

| Kind | c1 | c2 | c3 | c4 |
|---|---|---|---|---|
| Manpower | 3500 | 7000 | 10000 | 14000 |
| `infantry_equipment` | 3000 | 6000 | 9000 | 12000 |
| Support / trucks | 100 / 120 | 200 / 250 | 300 / 400 | 400 / 550 |
| Fuel | 10000 | 20000 | 35000 | 50000 |
| Political power | 30-40 | 60-75 | 100-120 | 150 |
| Treasury (`ADISCORD_economy_treasury`) | 150 | 300 | 500 | 700 |
| Experience / command power | 15 | 25 | 40 | 55 |
| Stability / war support | 3 % | 5 % | 8 % | 10 % |
| Group support `NAM_grp_<group>_support` | +5 / -3 | +8 / -5 | +12 / -6 | +15 / -8 |
| Ledger push (one country) / influence power | 8 / +1 | 12 / +2 | 15 / +3 | 20 / +4 |
| Depot move (one site) / front | -8 / - | -12 / +1 level | -15 / +1 level | -20 / +1 level |
| Buildings | - | 1 factory or refinery with its own slot, or 2 infrastructure | 2 factories with slots | 3 factories with slots |
| Aggregate (exact dummy preview) | one line <= 5 % | two lines 6-8 % | three lines <= 10 %, one a price | three lines <= 12 %, one a price |

- Every focus pays at least one material row; a decision unlock never replaces
  it. A factory reward brings its own shared slot, rechecks owner, controller and
  site at delivery and pays the treasury fallback when no site qualifies.
- Kinds per focus: c1 at least three, c2 four, c3 five, c4 five and a story
  event; the offensive is exempt; a keeper at least four besides its slot. A
  ledger push, a power gain, a depot move and a front level each count as a
  kind. Two rows of one kind count once; costs and events do not count; a
  tooltip counts only with a real consumer.
- Contest vocabulary: a lean line reads "<Страна>: §G+N§! к перевесу в пользу
  Светлогорья"; power lines are `ADISCORD_south_power_gain_<n>_tt` ("Сила
  влияния Светлогорья на Юге: §G+N§!"). Contest rows appear only inside
  `hidden_trigger = { ADISCORD_south_contest_open = yes }`.
- Depot vocabulary: board lines start with "§YСпор за нефтебазы:§!"; fallback
  lines read "если спор уже решён"; a front raised before the head card adds
  "если спор ещё не начат: уровень вступит в силу с первым ходом владельцев".
- Southern contract ideas (`ADISCORD_south_nam_*`) of the offensives are not
  rewards.

### 7.2 Locked laws

31 laws `NAM_pw_law_<x>` in the section "Post-war republic: laws" of
`common/ideas/ADISCORD_nam_resource_war_ideas.txt`: `cost = 0`,
`removal_cost = -1`, visible only while held, `available` always false,
`allowed_to_remove` false behind `NAM_pw_law_locked_tt`, `ai_will_do` 0,
`ADISCORD_economy_queue_law_refresh` in `on_add` / `on_remove`. Enactment
`NAM_pw_enact_<x> = yes` swaps visibly over every law of the slot, is the first
native row of the reward and has exactly one focus caller. The two sides of a
pair share a slot; no route takes one slot twice.

| Owner | Focus | Law | Slot |
|---|---|---|---|
| Shared | `NAM_pw_breakthrough_army` / `NAM_pw_mobile_army` | `shock_corps` / `mobile_groups` | military organisation |
| Shared | `NAM_pw_rail_priority` / `NAM_pw_road_priority` | `rail_echelons` / `motor_columns` | logistics |
| Shared | `NAM_svetlogorsk_shipyards` / `NAM_pw_air_review` | `sea_training` / `flight_training` | training |
| Shared | `NAM_civil_dividend` / `NAM_armed_peace` | `civil_contracts` / `defence_depots` | infrastructure |
| Etatist | `NAM_ladder_ending_iron` / `NAM_ladder_ending_service` | `namestnik_rule` / `civil_service` | internal security |
| Etatist | `NAM_state_plan` / `NAM_regional_trusts` | `central_plan` / `regional_trusts` | industrial policy |
| Etatist | `NAM_pw_military_governors` / `NAM_pw_officer_appointments` | `commandant_corps` / `attested_officers` | officer corps |
| Etatist | `NAM_pw_cabinet_statute` / `NAM_pw_state_chamber` | `cabinet_decrees` / `public_accounts` | information |
| Etatist | `NAM_pw_labour_code` / `NAM_pw_insurance_fund` | `labour_service` / `state_insurance` | labour / welfare |
| Pragmatic | `NAM_prag_ending_republic` / `NAM_prag_ending_directorate` | `public_estimate` / `board_exchange` | taxation / trade |
| Pragmatic | `NAM_prag_treasury_guarantee` / `NAM_prag_private_underwriting` | `treasury_guarantee` / `private_underwriting` | economic system |
| Pragmatic | `NAM_foreign_patents` / `NAM_domestic_designs` | `licence_industry` / `design_bureaus` | industrial policy |
| District | `NAM_charter_ending_federation` / `NAM_charter_ending_oil_union` | `district_welfare` / `artel_contracts` | welfare / labour |
| District | `NAM_district_militia` / `NAM_relief_register` | `district_oath` / `district_medicine` | military justice / healthcare |
| District | `NAM_municipal_land` / `NAM_tenant_councils` | `municipal_land` / `open_minutes` | industrial policy / information |
| District heritage | `NAM_south_free_communities` | `community_rights` | cultural policy |

### 7.3 Development trades

Eleven trades `NAM_pw_trade_<lowered>_for_<raised>` in the section "Post-war
republic: development trades" of the effects file: a visible
`custom_effect_tooltip`, the level change in `hidden_effect` ending with
`ADISCORD_economy_mark_dirty = yes`; the raised track gains a level, or pays 250
treasury through the `_capped_tt` branch when it is already at 5; the lowered
track drops one level with its progress kept.

| Trade | Focus |
|---|---|
| `social_system_for_army` | `NAM_armed_peace` |
| `society_for_army` | `NAM_border_revenge` |
| `social_system_for_economic` | `NAM_pw_labour_code` |
| `economic_for_social_system` | `NAM_pw_insurance_fund`, `NAM_relief_register` |
| `society_for_state` | `NAM_ladder_of_seals` |
| `economic_for_state` | `NAM_prag_treasury_guarantee` |
| `state_for_economic` | `NAM_prag_private_underwriting` |
| `science_for_economic` | `NAM_foreign_patents` |
| `state_for_social_system` | `NAM_charter_ending_federation` |
| `society_for_economic` | `NAM_charter_ending_oil_union` |
| `state_for_army` | `NAM_district_militia` |

`economic_for_social_system` has one caller on each of two paths; no trade
appears twice on any route.

### 7.4 Story events

- Namespace `ADISCORD_nam_story`, ranges: shared 300-319, etatist 320-339,
  pragmatic 340-359, district 360-379, influence 380-389, depots 390-401;
  every id is registered in `tools/data/adiscord_event_ids.json`. Numbers 345
  and 346 are retired and not reused.
- Shape: `is_triggered_only`, `fire_only_once`, three answers; the first is the
  timeout answer and costs political power, treasury or group support; effects
  sit on the answers; prose only, within 3000 characters and 5500 UTF-8 bytes
  per page. The depot round `.395` is hidden; the owners' moves 396-400 and the
  outcomes 394 and 401 belong to the board.
- A focus fires at most one window; the call is the last row of its single
  `hidden_effect`. The lane ends `.382` and `.392` have three focus callers, one
  per mandate. At least 28 days between windows on a path spine, at least 21
  between event focuses of an AI plan. `ADISCORD_nam_story.40` is queued only
  by the hub events 327 and 349.
- Older post-war events keep their ids: `ADISCORD_nam_resource_war.12`
  (`NAM_recognition`), `.13` (`NAM_svetlogorye`), `.413`
  (`NAM_pw_constitutional_committee`), `.414` (`NAM_pw_district_hospitals`),
  `ADISCORD_nam_archive.6` (both border sides).

### 7.5 Tooltip layout

Inside `completion_reward`: unlock pairs (`unlock_decision_tooltip` then
`<decision>_unlock_tt`); native rows with the law enactment first; the dummy
preview through `effect_tooltip` (equal to the applied delta); at most one
`custom_effect_tooltip = NAM_<focus>_reward_tt` for what native lines cannot
show; one `hidden_effect` with the script and the event call last. Custom
values: one fact per line, number before its texticon, `§G` gains, `§R` losses
and prices, `§Y` neutral amounts.

### 7.6 Folded ids

A folded focus hands its absorber every reward row, unlock, flag, variable,
group or BOP push, law, trade and story event; every reader is repointed in the
same change; the folded id and its localisation go, its `spriteType` stays.
Caps on merged rewards: a same-kind stock rises at most one tier, a stock of
another kind enters at the secondary magnitude, one law, one trade and one slot
per card. 118 ids stay folded: those of the earlier builds that this design did
not restore, plus `NAM_pw_school_network` (into `NAM_national_university`),
`NAM_azhar_accord` (into `NAM_eflor_accord`), `NAM_pw_regional_reconstruction`
and `NAM_pw_municipal_repair` (into `NAM_pw_district_hospitals`). 39 earlier ids
came back as their own cards, among them `NAM_foreign_office`,
`NAM_depot_inquiry`, `NAM_depot_revoke`, `NAM_depot_reserve_charter`,
`NAM_pw_military_governors`, `NAM_customs_clearinghouse`,
`NAM_district_council` and `NAM_common_citizenship`. Folded ids stay out of
`common/`, `events/`, `focus_trees/`, `tools/tests/` and `docs/development/`.

## 8. Hand-over, AI plans, research slots

### 8.1 Offensives and gates

- The offensives (cost 6) need `NAM_svetlogorye`, no war and
  `ADISCORD_south_final_focus_available` (offensive policy, finished
  preparation, the crisis warning); with `NAM_svetlogorye` completed they are
  bypassed once the war has started or been resolved. Their reward is the
  southern contract idea and the call of `ADISCORD_south_prepare_offensive`.
- Southern gates on the spines: `NAM_south_black_basin` and
  `NAM_south_desert_offices` (etatist), `NAM_south_fenn_guarantee` and
  `NAM_south_oil_for_water` (district). Cards that are bypassed once the war has
  started or been resolved: the Kadir embassy, `NAM_community_charter`,
  `NAM_oasis_voices`, `NAM_well_partnerships`, `NAM_south_oil_for_water`.

### 8.2 AI plans

`common/ai_strategy_plans/ADISCORD_NAM_plans.txt`: `NAM_postwar_vertical_plan`
(etatist, 61 rows), `NAM_postwar_pragmatic_plan` (58), `NAM_postwar_plan`
(district, 59). Each takes one side of every pair, never a kill stub, the
offensive last; the influence row ends with the path's variant at 11,8 and the
depot row with its variant at 31,8. Shared rows: the sea / oilfields side skips
its follow card, the air / grid side skips the lane end. All three take
normalisation, the desert envoys and the league in the influence lane.

| Plan | Shared sides | Depot sides | Path sides |
|---|---|---|---|
| Etatist | breakthrough, rail, air, defence order, state refineries, energy | strike, export ban, revocation | executive, plan, officer appointments, cabinet statute, labour code |
| Pragmatic | manoeuvre, road, sea, civil dividend, consortium, oilfields | strike, audit, reserve charter | republic, treasury guarantee, domestic designs, settlement agreements, credit supplies, tractor leasing |
| District | manoeuvre, rail, sea, civil dividend, state refineries, energy | boiler houses, export ban, revocation (cooperative) | federation, militia, municipal land, oasis voices, rural grid |

The AI presses the depot target at 150 political power. The
heritage plans `NAM_south_heritage_plan`, `NAM_south_heritage_vertical_plan`
and `NAM_south_heritage_pragmatic_plan` run while the heritage tree is loaded.

### 8.3 Research slots

Every path reaches exactly two post-war slots on one route:
`NAM_national_university` (shared, economy lane) and its own keeper,
`NAM_state_project_bureaus`, `NAM_port_polytechnic` or
`NAM_regional_university`. A keeper costs 9, carries `FOCUS_FILTER_RESEARCH`,
has `add_research_slot = 1` as the first row of `completion_reward`, has no
exclusive partner and stands off the readiness route. No heritage focus grants
a slot.

## 9. Nationalisation during the war for the South

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
programmes and cancels running ones with the refund. Pinned by
`tools/tests/test_adiscord_postwar_nationalisation.py`.

## 10. Source files and their readers

| Source | Content |
|---|---|
| `focus_trees/NAM/postwar/focuses.txt` | header, `country` weight, `# @include` order (shared lanes first, then the path sections, then the three lane-end sections) |
| `government.txt` | `government`: the trunk |
| `armed_forces.txt`, `economy.txt` | outer lanes |
| `influence.txt` | `influence`: the influence lane |
| `depots.txt` | `depots`: the depot lane |
| `etatist.txt` | `etatist_ladder`, `etatist_plan`, `etatist_works`, `etatist_constitution`, `etatist_lane_ends` |
| `pragmatic.txt` | `pragmatic_compact`, `pragmatic_south`, `pragmatic_industry`, `pragmatic_lane_ends` |
| `districts.txt` | `districts_charter`, `districts_services`, `districts_municipal`, `districts_cooperatives`, `districts_lane_ends` |
| `southern_settlement.txt` | the whole heritage tree |

- `python -B -m tools.builders.build_adiscord_focus_trees --check` / `--apply`
  writes `common/national_focus/ADISCORD_NAM_postwar.txt` (owner recorded in
  `tools/data/generated_output_owners.json`); never edit the output.
- Tests: `tools/tests/test_adiscord_nam_focus.py` (class
  `NamPostwarDesignTests` and the older post-war tests),
  `test_adiscord_south_final_war.py` (calendar, contest, war start),
  `test_adiscord_postwar_nationalisation.py`,
  `test_adiscord_party_representation.py`, the SHL story and furnace tests.
- NAM hubs: `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`
  (laws, trades, hand-over, depot board, lane cores),
  `common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt`,
  `common/ideas/ADISCORD_nam_resource_war_ideas.txt` (laws, previews, spirits),
  `common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt`,
  `common/scripted_guis/ADISCORD_NAM_scripted_gui.txt` (basin map),
  `common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt`
  (`on_daily_NAM`), `events/ADISCORD_nam_resource_war_events.txt`,
  `localisation/{russian,english}/ADISCORD_nam_resource_war_l_*.yml`,
  `common/ai_strategy_plans/ADISCORD_NAM_plans.txt`.
- South hubs: `ADISCORD_south_final_war_effects.txt`, `_triggers.txt`,
  `_decisions.txt`, `_events.txt`, `_scripted_loc.txt` and their localisation;
  SHL decisions and effects for the strike-or-appeal rule;
  `common/on_actions/00_ADISCORD_on_actions.txt` for
  `global.ADISCORD_south_day0`.
- The corporate exile and return-war routes (`NAM_board_`, `NAM_rtw_`,
  `NAM_isl_`, `NAM_sub_`) share these hubs and are not part of this tree.

## 11. Left for later

1. New Shahrabad focuses for the longer wait before the war (author's answer 3).
2. Readiness and an offensive for the corporate exile route; it enters the war
   for the South only by the deadline (author's answer 6).
3. Research-slot campaign cap: with the pre-war `NAM_technical_college` a
   victory campaign can hold three extra slots against the mod's usual cap of
   two.
4. Runtime, with a full restart and fresh logs: a victory save (anchor day,
   displayed date, contest seeds), one owners' round and the press move, a
   blocked Keizan war and its re-arm, the war start (side choices read the
   ledger), the three views of the tree on screen, the event windows and their
   timeouts, the AI plans and the nationalisation decision across the war start.
