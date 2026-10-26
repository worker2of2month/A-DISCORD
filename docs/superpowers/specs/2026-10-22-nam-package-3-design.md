# NAM Package 3: Svetlogorye at STP/VAL/RUS depth

## Goal

Raise NAM (Svetlogorye, leader Egor Rom) to the content and mechanics level of
STP, VAL and RUS. The player must have a decision to make every one to three
weeks from day 1 to the end of the South war, the resource war must be prepared,
negotiated and fought rather than waited for, and NAM's 62% share of the world's
oil must matter to other countries.

## Diagnosis this design answers

- A dead window of roughly 460-640 days between the end of the pre-war tree
  (about day 570) and the hidden 850+0..90-day war event.
- The war is imposed and binary: a free 6-division OOB with 60000 rifles,
  victory by holding state 67 at day 420, total annexation otherwise.
  `ADISCORD_nam_resource_war_resolve_peaceful_withdrawal` is never called.
- 34 of 70 focuses feed one aggregate; 30 of 37 decisions are instant currency
  converters; there are no targeted decisions.
- The five pillars move PP by about 1% and monthly drift erases every shift.
- No characters beyond Egor Rom; Yaroslav Weber is never named in war text;
  endings change neither leader, ideology nor name.
- Oil is sold into the void; the islands 225-231 have one focus.

## Decisions taken for this package

1. **NAM can survive a lost war.** A lost timeout becomes a graduated
   settlement: a compromise peace keeps a rump NAM and loads a defeat tree.
   The coalition's full victory takes the whole mainland, but a NAM that
   still owns an overseas district survives there in exile; only a NAM
   without islands is annexed.
2. **The free war army is replaced by paid mobilisation** with a small
   baseline. The AI receives orders through its own decision weights.
3. **Other countries' files may be changed** where a contract with a
   playable country needs its in-game consent (VAL, STP, SHL, RUS).
4. Existing script IDs, flags and the scripted peace dispatcher order are
   preserved unless this document replaces them explicitly.

## Campaign timeline

| Phase | Days (approx.) | Content |
| --- | --- | --- |
| Colony | 0 - 350..380 | Metropolitan oil quotas, concealed reserve, first pillar demands, memoir 1 |
| Independence | collapse event | Declaration event sets the starting ladder balance and opens the tension clock |
| Restitution pressure | collapse - war | Tension clock, notes, ultimatum, oil contracts, mobilisation orders, defence lines, underground, rivals |
| Resource war | up to 420 | Front missions, scorched wells, seal discipline, oil-score settlement |
| Victory | after war | Border belts and punishment, then `NAM_postwar_focus`: recognition, course, endings, South, EFL/AZH aftermath, RUS crisis |
| Standoff | after war | Pre-war border, no treaty or punishment, then the same `NAM_postwar_focus` |
| Compromise | after war | `NAM_defeated_focus`: revenge or accommodation |
| Island exile | after war | Mainland lost, capital on the islands; event .100 loads `NAM_exile_radical_focus` or `NAM_exile_humanist_focus`, the takeover `NAM_exile_corporate_focus` |
| Total partition | after war | Only when NAM owns no island: NAM is annexed |

## Map split for the war

The war uses five split states. State 719 (East Sukhorechye) is a NAM oil
field cut from Sukhorechye (690); the Klyuchevsk protocol cedes 719, not 690.
States 720 (Moren District), 721 (Loren Borderland) and 722 (Azhar Seaboard)
are the border belts of EFL and AZH; together with Middle Loren City (701),
which touches NAM only through 720, they are the victory award.
Field capacity units: 67 = 8, 688 = 2, 689 = 4, 690 = 3, 719 = 1.

## M1. Restitution pressure (tension clock)

Owner: core phase 1.

- Country variable `NAM_rw_tension` on NAM, 0..100. Set to 10 by
  `ADISCORD_nam_resource_war_schedule`. Recomputed only in `on_monthly_NAM`
  while `ADISCORD_nam_resource_war_scheduled` is set.
- Monthly change: base +6; -4 while the tribute (`NAM_rw_tribute`) runs;
  -2 for each active fuel contract with
  EFL or AZH; +1 for each active embargo on EFL or AZH; +1 while two or more
  mobilisation orders are paid. Clamp 0..100.
- One-shot changes: diplomatic note decision -8 (cooldown 60 days);
  each mobilisation order +2; ultimatum answers as below.
- Thresholds (each fires once): 40 -> event `ADISCORD_nam_resource_war.20`
  "Notes of restitution" (open talks: -5 and unlock note decisions;
  reject: +5 and +5% war support). 70 -> event `ADISCORD_nam_resource_war.21`
  ultimatum with four answers:
  - **Klyuchevsk protocol**: cede state 719 to AZH and sign a 365-day tribute
    contract to EFL and AZH (M3). Tension -40. Sets
    `NAM_rw_protocol_signed` and pushes the earliest war date by 365 days.
    Once per campaign.
  - **Buy time from Azhar**: 12000 fuel goes to AZH (`NAM_rw_buy_time`,
    once per campaign, permanent flag `NAM_rw_time_bought` dating the
    payment). For 75 days `NAM_rw_time_bought_active` closes the war window,
    and event `.1` moves the first backstop after the payment (or any copy
    firing inside the window) 75 days later
    (`ADISCORD_nam_resource_war_time_deferred`). AZH stays in the alliance and
    always joins the war. The former AZH-neutrality treaty and its events
    `.22`/`.23` are retired; their IDs are reserved.
  - **Reject**: +10 tension, +10% war support.
  - **Strike first**: hostilities start within 7 days, NAM is the declarer,
    `ADISCORD_nam_extraction_defence_corps` is replaced by its half-strength
    variant `ADISCORD_nam_first_strike_corps` and the coalition gets +10% war support.
- War start: when tension reaches 100 and more than 299 days have passed since
  the collapse (more than 664 after the protocol; the age of the
  `ADISCORD_nam_resource_war_scheduled` flag set at the collapse edge), dispatch
  `ADISCORD_nam_resource_war.1` in 7-21 days. The backstop is event `.1`
  scheduled at the collapse for 420+0..60 days; with `NAM_rw_protocol_signed`
  it reschedules itself once by 365 days instead of starting the war.
- A failed readiness check retries once after 120+0..90 days; when no other
  dispatch is queued, the entry stops: the scheduled flag is cleared without
  starting or resolving the war and the paid orders are refunded. Main-tree
  focuses that wait for the restitution clock bypass once the collapse has
  happened and the scheduled flag is gone, so a stopped entry never locks them.
- The clock and the next threshold are shown in scripted localisation and in
  the basin window (M6).

## M2. Mobilisation, defence lines and the war

Owner: core phase 1.

- `history/units/NAM_resource_war.txt` is reduced to a baseline: one guard
  division and two infantry divisions; the hostilities grant becomes 20000
  infantry equipment, 300 support equipment, 250 artillery and 8000 manpower.
- Category `NAM_mobilisation` with formation orders (decisions with
  `custom_cost_text`, `cost = 0`, explicit debit once in `complete_effect`):
  `NAM_order_resource_guard`, `NAM_order_field_infantry`,
  `NAM_order_motor_column`, `NAM_order_coastal_battalion`.
  Each order reserves its price in escrow variables, can be cancelled with a
  refund before the war, and is delivered by `NAM_deliver_mobilisation_orders`
  at hostilities: prepared formations claim manpower and equipment first.
  Maximum six paid orders. `Capital Guard` and `Line Infantry Brigade` in
  `NAM.txt` remain editable. `NAM_order_ensure_templates` creates separate
  locked `Mobilisation Guard` and `Mobilisation Infantry Brigade` templates
  for orders and wartime baseline reinforcements, with recruiting allowed.
  Coastal and motorised templates are created when their orders have been paid. Settlement unlocks all
  four roles. The motorised division (`Motor Column`: four
  `ADISCORD_mechanized_infantry`, engineers, artillery; 25 PP, 250 treasury,
  4600 manpower, 3000 fuel) needs `ADISCORD_tech_armored_carrier_program`,
  which its order grants. `NAM_order_spawn_one` places every paid formation
  in its own field when fully held, else in a fully held mainland state, else
  in any held state, and logs the route. Per-type delivery counters
  (`NAM_orders_delivered_*`) feed event `.11` and the category text
  (`NAMGetOrdersSummary`). Template names stay English without technical
  country prefixes; each role has a distinct template counter icon.
- Defence lines: state-targeted decision `NAM_prepare_line` on NAM-owned
  states 67, 688, 689, 690, 700 (three parallel slots, 30 PP and 100 treasury,
  35 days, bunkers and the state flag `NAM_line_prepared`). It replaces the two
  one-off fortification decisions; their category is retired.
- War missions: `NAM_hold_field_67`, `NAM_hold_field_689`,
  `NAM_hold_field_690` (120 days, success = NAM still controls the state;
  reward: +10 seal discipline, fuel and war support). Their IDs are registered
  in the synchronized mission token file.
- Scorched wells: state-targeted `NAM_scorch_wells` on a field NAM controls
  while an enemy unit is adjacent; sets the field condition (M3) to 10 and
  gives the captor nothing for 180 days. Repair projects restore it later.
- Seal discipline: country variable `NAM_seal_discipline` 0..100, 70 at
  hostilities; monthly -casualties_k/5, -10 for each field state lost, +3 per
  month at peace. Events `ADISCORD_nam_resource_war.30` (below 50) and
  `.31` (below 25) offer costly answers. At 0: `.32` "Night of seals" -
  stability -15%, ladder balance shifts 0.20 toward the vertical, the
  weakest-support rival demands the leadership (M4 coup path).
- Underground hook: at hostilities the SLF uprising is decided by
  `NAM_underground` (M4) instead of the 50/50 roll: >= 60 always, 30-59 50%,
  < 30 never; an effective compact or the Weber amnesty sets it to 0.
- Settlement by oil score at timeout (event `.50`, 420 days after
  hostilities): sum of the oil of the fields NAM controls among 67 (80),
  688 (12), 689 (36), 690 (24), 719 (12).
  - `>= 100` and NAM controls at least one border belt state (720, 721, 722
    or 701, trigger `NAM_rw_holds_border_belt`): NAM victory.
  - `>= 100` without a belt state: standoff.
  - `36..99`: compromise peace. `< 36`: coalition victory.
  Capitulation of the coalition principals is a NAM victory at any time; NAM
  capitulation is the coalition victory. A passive defence of the own fields
  therefore never earns the border award. The victory record reads the
  persistent defeat receipts `ADISCORD_nam_resource_war_EFL_defeated` /
  `_AZH_defeated` (AZH also counts once it has left the war); the
  `nam:on_uncapitulation` section clears the receipt of a liberated
  principal. A native peace that ends the war between independent
  principals settles by the oil score instead of closing silently.
- Front settlement (symmetric, no polling): the NAM `on_state_control_changed`
  hook calls `NAM_rw_queue_front_check` for 67, 688, 689, 690, 719, 720, 721,
  722 and 701. When NAM controls 720, 721, 701 (and 722 while AZH fights) and
  every field it owns (`NAM_rw_territorial_victory`), or the coalition holds
  67 and one more NAM-owned field (`NAM_rw_coalition_territorial_victory`),
  one hidden event `.51` is queued for 7 days (flag
  `NAM_rw_front_check_pending`); it rechecks the ground and imposes the NAM
  victory or the coalition victory.
- Coalition victory (`ADISCORD_nam_resource_war_resolve_coalition_victory`,
  reached by NAM capitulation, the front settlement, an oil score below 36 or
  a lost war of return): EFL annexes SLF; `NAM_rw_cede_mainland_state` gives
  689, 690, 700 and 719 to AZH and 67, 688 and every other mainland state NAM
  owns to EFL, with NAM claims kept. If NAM still owns an island
  (`NAM_rw_can_go_into_exile`), `NAM_rw_settle_island_exile` sets
  `ADISCORD_nam_resource_war_island_exile`, moves the capital to the first
  owned of 228, 225, 227, 231, 226, 229, 230, restores control of the
  islands and ends oil contracts (the 231 steel concession continues); it
  loads no tree: the island council of event .100 right after the flight
  loads the course's exile tree (M10). Islands are never transferred. Without an island NAM is annexed by
  EFL as before. News `.2` has exile and partition texts. The war of return
  is open after the compromise or the exile and also targets 700; winning it
  back returns an exiled capital to 700.
- NAM victory (`ADISCORD_nam_resource_war_resolve_nam_victory`): SLF is
  annexed and 688 restored; EFL cedes 720, 721 and 701 and AZH cedes 722
  (`NAM_rw_award_border_state`, only a belt still owned by that
  principal); NAM claims 69; each defeated principal receives the timed
  spirits `NAM_ruined_economy` and `NAM_army_of_shame` for 730 days
  (`NAM_rw_punish_defeated_coalition`); NAM gets
  `ADISCORD_nam_treaty_independence` and `NAM_treaty_independence_recognised`;
  VAL's concession is delivered; `NAM_postwar_focus` loads with
  `keep_completed = yes`; news `.3`.
- Standoff (`ADISCORD_nam_resource_war_resolve_standoff`): the wars end on the
  pre-war border, SLF is annexed and 688 returns to NAM, no belt transfer, no
  punishment and no recognition treaty. It sets
  `ADISCORD_nam_resource_war_nam_victory` (the "NAM held" marker read by VAL's
  concession and aid settlement, VAL's military contract and the post-war tree
  selection) together with `ADISCORD_nam_resource_war_standoff`, which selects
  the standoff texts of news `.3` and event `.12` and keeps the national
  programmes category open. VAL's concession is delivered as after a victory;
  `NAM_postwar_focus` loads with `keep_completed = yes`.
- Compromise peace: `ADISCORD_nam_resource_war_resolve_compromise` replaces
  the dead peaceful-withdrawal effect and news `.7` (reworded for the
  compromise). Each of 67, 688, 689, 690, 719 goes to the coalition member that
  controls it (688 to EFL, the others to their controller); SLF is annexed by
  the owner of 688; islands remain with NAM; NAM signs a 365-day tribute fuel
  contract to EFL and AZH; sets `ADISCORD_nam_resource_war_compromise`;
  loads `NAM_defeated_focus` with `keep_completed = no`. VAL's concession is
  cancelled as in the coalition-victory path.

## M3. Oil monopoly and the islands

Owner: core phase 2.

- Field condition: state variable `NAM_field_condition` (0..100, start 80) on
  states 67, 688, 689, 690, 719. Base capacity units: 67 = 8, 688 = 2, 689 = 4,
  690 = 3, 719 = 1. `NAM_oil_refresh` sets `NAM_oil_throughput` (sum over NAM-controlled
  fields of capacity x condition / 100, rounded down, plus project bonuses) and
  `NAM_oil_committed` (contract units). Event-driven: called after every
  contract, project, control change and condition change; never polled.
- Contracts: targeted decision `NAM_oil_contract_offer` on a buyer from
  EFL, AZH, VAL, STP, STS, RHM, MZR, SHL, RUS, WEF, KDR, SDR, GLP, KYZ that exists,
  is not at war with NAM and has no contract. Needs one free unit. Human buyers
  answer `ADISCORD_nam_oil.1`; AI buyers answer the same event with
  `ai_chance` by fuel stock and relation. Accepted contracts set the buyer flag
  `NAM_oil_client` and add one committed unit. Monthly in `on_monthly_NAM`:
  NAM +40 treasury per contract through the economy API and
  `ADISCORD_economy_mark_dirty`; the buyer +1500 fuel. War between NAM and a
  client ends the contract and gives the client `NAM_fuel_shortage` for 90
  days (guard removals with `has_dynamic_modifier`). `NAM_oil_contract_end`
  cancels a contract from NAM's side.
- Consequences: oil and export pillars +5 on signature; a contract with RHM or
  MZR at hostilities withholds `ADISCORD_nam_profitable_volunteer_contracts`
  from that country; contracts with EFL or AZH lower tension (M1). Fulfils the
  "future fuel contracts" promised in news `.1`.
- Embargo: targeted `NAM_fuel_embargo` on EFL, AZH or SHL gives the target
  `NAM_fuel_embargo_modifier` until lifted; +1 tension per month for EFL/AZH;
  export pillar -10.
- Field projects (state-targeted, escrow, ownership rechecked at delivery,
  refund on loss): `NAM_project_repair_wells` (+30 condition, 45 days),
  `NAM_project_refinery` (+1 unit and fuel output in the state, 90 days),
  `NAM_project_pipeline` (690 -> 700, +1 unit, needs both states, 120 days),
  `NAM_project_sea_terminal` (state 700, +1 unit usable only by overseas
  buyers VAL, STP, STS, RUS, 90 days). One project per state at a time; two in parallel.
- Islands category `NAM_overseas_districts`: steel levy (monthly treasury,
  compliance cost on 228, 230, 231), convoy service (convoys and island
  supply), the 231 steel concession offered to VAL or GLP with consent, and
  renegotiation of VAL's 230 concession (VAL consents or loses it with a
  relation penalty). The islands also carry the exiled government after a
  lost war (M2); there is no separate island independence movement.
- Field fires and SHL raids reduce condition through the existing crisis draw
  and the South-war raid effects.

## M4. The ladder of seals (politics)

Owner: core phase 3.

- Native BOP `NAM_ladder_bop` in `common/bop/NAM.txt`: left side
  `NAM_bop_vertical` (namestniks), right side `NAM_bop_districts`. Initialised
  once with `set_power_balance` at the declaration event, from 0 shifted 0.15
  by its choice. `NAM_vertical` / `NAM_districts` push 0.25; pillar measures
  push 0.10. Ranges give modifiers and mark the economy dirty.
- Pillar favours: each pillar with support >= 70 may spend 15 support on a
  120-day favour decision (`NAM_favour_<group>`, groups nam, oil, dist, garr,
  trade). Monthly drift is reduced to 0.5 toward 50.
- Rivals: four named characters in `common/characters/NAM.txt` with advisor
  roles - `NAM_Arseny_Klyuch` (Arseny Tarkhanov, namestnik of Klyuchevsk,
  oil), `NAM_Lev_Gavanov` (Lev Kornilov, harbour and islands),
  `NAM_Taras_Shtyk` (Taras Drozdov, garrison commandant), `NAM_Vera_Pechat`
  (Vera Saburova, senior registrar of seals). Character IDs predate the
  display names and are kept. Every 120 days
  the rival tied to the weakest pillar issues a demand (`ADISCORD_nam_groups.20`)
  with a 60-day mission `NAM_rival_demand`; refusal lowers that pillar 15;
  a pillar below 25 at refusal triggers the coup event `.21`. A successful coup
  replaces Egor Rom with the rival as leader for the rest of the route.
- Underground: `NAM_underground` 0..100, 25 from the fresh-campaign startup
  (M9); monthly base +3, +2 while district support < 40, +1 more below 25,
  +2 while the balance is vertical-dominant, -1 at district support >= 60,
  -3 with an active compact. Districts route: talks chain `NAM_weber_talks_1..3` ending in
  amnesty (underground 0, `NAM_Yaroslav_Weber` joins NAM as a general; SLF is
  never created). Talks broken off by an uprising return the treasury deposit
  of rounds 2 and 3 (100 and 200, escrow `NAM_weber_talks_deposit`); political
  power stays spent, as with released mobilisation orders. Vertical route: `NAM_hunt_caches` (state-targeted, -10
  underground, -5 district support). Weber is named in events `.2`, news `.5`
  and `.6`.
- Endings: the four ending focuses each set leader, ideology, cosmetic tag and
  a unique spirit: iron ladder (Rom or the coup leader, etatism, `NAM_iron_ladder`),
  service republic (Rom, service_etatism, `NAM_service_republic`), federation of
  districts (district council chair `NAM_Nadezhda_Okrug`, Nadezhda Ladygina,
  `NAM_federation`), oil union (`NAM_Kirill_Vykup`, Kirill Mezentsev, as
  leader, `NAM_oil_union`). Each sets its
  settlement terms in the South war through the existing service-state /
  federal-charter course check.
- Memoir chain: five chapters "Notes of Egor Rom" (`ADISCORD_nam_memoir.1..5`),
  every 90 days from day 4, human only, optional continuation page, full exit
  on every page; plus up to six archive events from focuses.

## M5. Focus trees

Owner: focus phase.

- `NAM_focus` (`focus_trees/NAM/main/focuses.txt`): colony and independence,
  administration and ladder, oil and islands, pillars and rivals, underground,
  mobilisation and lines, harbour, an expanded war branch (about ten focuses)
  with `bypass` once the war has passed. The post-war branch moves out.
  Target about 110 focuses, one route fitting the ~1000-day window; every major
  branch has a mutually exclusive pair with different play.
- `NAM_postwar_focus` (`focus_trees/NAM/postwar/focuses.txt` ->
  `common/national_focus/ADISCORD_NAM_postwar.txt`): loaded by the victory
  and standoff settlements with `keep_completed = yes`. Contains the moved post-war focuses
  with their IDs preserved plus EFL/AZH aftermath (normalisation or border
  revenge pair), oil expansion, the South-war branch, RUS-crisis participation
  and the endings. About 60 focuses.
- `NAM_defeated_focus` (`focus_trees/NAM/defeated/focuses.txt` ->
  `common/national_focus/ADISCORD_NAM_defeated.txt`): revenge (rebuild,
  underground return, a scripted war of return after preparation, symmetric)
  or accommodation (tribute ends early, oil union with the coalition, path to
  the South). About 25 focuses.
- AI plan `common/ai_strategy_plans/ADISCORD_NAM_plans.txt` choosing one
  alternative of every pair.
- Builder `SOURCES`, `tools/data/generated_output_owners.json` and the tree
  selection test are updated for the two new trees.

## M6. Basin window

Owner: GUI phase.

Scripted GUI opened from the `NAM_national_programmes` category, compact
template (one card definition reused per state through state scopes rather
than copied per button): tension or seal discipline, underground, ladder
balance, five node cards (67, 688, 689, 690, 700) with condition, capacity,
committed units and the project in progress, the islands card and the
contract list. Buttons call the same effects and triggers as the decisions
and show an "After:" preview. Files: `interface/ADISCORD_NAM_basin.gui`,
`interface/ADISCORD_NAM_basin.gfx`, `common/scripted_guis/ADISCORD_NAM_scripted_gui.txt`.

## M7. Cross-country links

Owner: foreign phase (VAL, South, RUS files) and core phases (NAM-side events).

- VAL: `VAL_Support_The_Viceroy` no longer fixes the 230 concession without
  NAM; NAM receives a consent event; NAM can request VAL aid itself.
- South: `ADISCORD_south_offer_alliance` handles AZH inside the EFL faction;
  NAM decisions fill `ADISCORD_south_final_war_category` (allied fuel supply,
  convoy interdiction, negotiations). The post-war tree opens one of
  `NAM_south_allied_fuel` and `NAM_south_convoy_interdiction` through an
  exclusive pair; the defeat tree's `NAM_defeat_southern_charter`, which
  starts the South war itself, opens both.
- RUS crisis: a NAM event to supply the coalition with oil or demand a share.
- EFL/AZH after a NAM victory: normalisation or border incidents (post-war tree).

## M8. Fixes

- Event `.10` gets an option affordable at the starting treasury.
- `NAM_national_spirit_desc` loses the internal "Namestnikland" name and the RUS banner.
- `NAM_treaty_independence_recognised` gains a consumer or is removed.
- Egor Rom gets traits and a description; NAM gets field marshal
  `NAM_Grigory_Levashov`, two generals (Gleb Burov, Anton Zimin) and an admiral
  (Matvei Severtsev). NAM ministers carry ordinary surnames (Mezentsev,
  Vetlugin, Nartov, Sedov, Ermolin, Tairov); their idea IDs are unchanged.
- The focus `NAM_rom_address` fires event `ADISCORD_nam_resource_war.70`,
  Rom's address in three tones: order (stability, governors and garrisons),
  oil for the people (stability, oil workers and districts) and defiance (war
  support, garrisons); the first option is the unattended answer.

## M9. Colony, active underground and the island exile

Owner: core phase 4 (third playtest batch).

- Colony phase (`NAM_colony_phase`: no `NAM_center_vanished`, no
  `ADISCORD_vorkerland_collapse_wars_started`). Category `NAM_colony`:
  `NAM_wrk_fuel_shipment` (4000 fuel, 45-day cooldown; treasury
  120 + 30 x `NAM_wrk_trade_level`, WRK opinion, namestniks +4, oil -3),
  `NAM_wrk_trade_concession` (50 PP + 200 treasury in escrow, 45 days; then
  25 + 15 x level treasury a month in `on_monthly_NAM` until the collapse),
  `NAM_counterinsurgency_sweep` (state-targeted 67/688/689/690/719/700,
  20 PP + 75 treasury in a state escrow, 21 days, one at a time, 120-day
  state cooldown; underground -8, -12 in 688, districts -4, 30% excesses).
  `NAM_wrk_trade_level` 0..3, focuses add and call `NAM_wrk_trade_refresh`.
- Collapse: `NAM_ladder_declare_independence` fires `ADISCORD_nam_resource_war.80`
  "The Centre Is Gone"; its immediate runs `NAM_colony_close` (flag
  `NAM_center_vanished`, concession ended, `mark_focus_tree_layout_dirty`) and
  its answer opens `ADISCORD_nam_groups.12`. Running colony decisions refund
  through their cancel triggers.
- Underground: runs from day 1 in `on_monthly_NAM` while
  `NAM_underground_active` (no amnesty, owns 688, resource war not started).
  The clamp opens threshold events .82/.83/.84 at 40/60/80, re-armed 15 points
  below. `NAM_underground_sabotage_roll`: from 30, 20% a month (x1.5 from 50,
  x1.5 again from 70), 60-day cooldown: .85 field fire (15 condition through
  `NAM_field_apply_damage`), .86 depot raid (up to 1500 NAM rifles), .87
  attack on a namestnik. Every event has three costed answers. The war-start
  uprising thresholds (60 always, 30-59 50%) are unchanged.
- Island exile: `NAM_rw_exile_evacuate` runs inside the coalition treaty
  before `ADISCORD_nam_resource_war_end_all_wars`: the transports carry at most
  floor(35%) of `num_divisions`; `delete_unit` removes whole state garrisons,
  front first (719, 690, 688, 67, 689), then the principals' states (720, 721,
  722, 701, 68, 70, 691, 69, 692), the harbour 700 last, while more divisions
  remain than the carried share; 65% of NAM-made rifles, support, artillery and
  squad weapons are dumped. `NAM_rw_settle_island_exile` burns the ceded
  fields and the harbour (`NAM_rw_exile_scorch_state`: condition -70,
  `NAM_scorched_wells_modifier` 180 days, building damage), forms
  under-strength remnants on the island capital up to the carried share, seeds
  the piracy variables and fires .81 "Flight to the Islands" (7-day timeout);
  each of its answers convenes the island council .100 six hours later.
- Piracy (category `NAM_piracy`, `NAM_piracy_open`): one decision per foreign
  shipping lane past the islands, `NAM_pirate_raid_lane_<id>`: oil run AZH-EFL
  (coalition, rich prize x1.5), northern coast RIV-EFL (coalition while EFL
  sails it), Luren strait ULV-LUR, Charden crossing CHD-RIV. Every lane stays
  within half the mainland's width by sea from the island harbours and passes
  an island coast (map builder check). 10 PP + 1000 fuel, 15 days, receipt
  `NAM_pirate_at_sea_<id>`, slot from `NAM_pirate_raid_slots`, max 3; haul 50 /
  prize 15 / failure 35 weighted by `num_ships`, owner alert, blockade and
  notoriety; the owners split the fuel loss and become alert; report .90 names
  the lane and owners, human owners get .91), `NAM_pirate_buy_arms`, `NAM_pirate_buy_heavy_arms`,
  `NAM_pirate_buy_convoys`, `NAM_pirate_fence_loot` (50 loot -> 100 treasury),
  `NAM_exile_drill` (20 PP + 30 loot in escrow, 30 days, readiness +10, army
  XP 15). Notoriety falls 3 a month; from 50 a 40% monthly retaliation chance
  (120-day cooldown): blockade .92 (`NAM_pirate_blockade`, 90 days) or, from
  75, punitive raid .93.
- Marines: `NAM_order_marines` (50 loot + 4300 manpower, escrow
  `NAM_marine_orders_paid`, cap `NAM_marine_order_cap` base 1 max 3,
  `NAM_order_marines_release` refunds before the war of return). Template
  `Island Marines` (4 `ADISCORD_marine_infantry`, engineer) through the
  script-only tech `ADISCORD_tech_svetlogorsk_marine_corps`.
- Revenge landing: `NAM_war_of_return_start` from exile calls
  `NAM_wor_revenge_landing` after the declaration: 2 marine divisions plus a
  third for a paid order or `NAM_revenge_readiness` >= 70 spawn in state 700
  (`prioritize_location = 16716`, enemy provinces allowed); further paid
  orders form on the island capital; report .94.

## M10. Exile revolution: radicals or humanists

Both routes overthrow the namestnik (the current NAM leader, Egor Rom or a coup
leader) in exile and keep the revenge goal; they differ in how they pay for it
and in what they do with the conquered south. The exile's road has three
stages: the war of return against Eflor and Azhar, the consolidation of the
returned south and the great war against the rest of the south.

- Trigger: no decision. Every answer of the flight event .81 fires the island
  council `ADISCORD_nam_resource_war.100` six hours later, for the human and
  the AI alike (trigger `NAM_exile_revolution_open`: NAM, exile flag, no course
  yet; 7-day timeout, the first answer is the unattended one). Its two answers
  set the NAM country flag `NAM_exile_radical` (the pillars of Svetlogorye
  overthrow him) or `NAM_exile_humanist` (the humanists of Yaroslav Veter
  overthrow him) and then load `NAM_exile_radical_focus` or
  `NAM_exile_humanist_focus` with `keep_completed = yes`. Until then NAM keeps
  the tree it lost the war with. The choice is final.
  `NAM_exile_choose_radical`: leader `NAM_Rostislav_Karamyshev` (Rostislav
  Karamyshev, etatism, traits `NAM_trait_pillar_junta_chief` and
  `NAM_trait_corsair_patron`), ruling etatism 75 / humanism 25, spirit
  `NAM_exile_pillar_junta`, readiness +5. `NAM_exile_choose_humanist`:
  `NAM_Yaroslav_Veter` recruited if needed and promoted (humanism, trait
  `NAM_trait_voice_of_the_districts`), ruling humanism 60 / etatism 40, spirit
  `NAM_exile_free_islands`, `NAM_corp_initialize` (the exile's loot becomes
  capital). Both call `NAM_rom_step_down`.
- Shared return programme (`NAM_exile_return_programme_open`: exile, course
  chosen, the exile war not yet started): `NAM_exile_drill` (category
  `NAM_exile_politics`, after `NAM_exile_general_staff`, 20 PP plus 30 loot under
  the junta or 30 capital under the humanists, refunded in the paid currency)
  and marine orders: `NAM_order_marines` (junta, 50 loot, focus
  `NAM_exile_marine_orders`) or `NAM_order_marines_corp` (humanists, 60
  capital, focus `NAM_hum_marine_contracts`); both use `NAM_marine_orders_paid`
  under `NAM_marine_order_cap`, released by `NAM_order_marines_release` /
  `NAM_order_marines_corp_release` with the paid currency.
- Radicals: piracy (`NAM_piracy_open` requires `NAM_exile_radical`). Policy on
  every conquest: annexation; non-homeland states get the state flag
  `NAM_conquered_state`, NAM's array `NAM_conquered_states` and the modifier
  `NAM_conquered_state_modifier` (no development). Category
  `NAM_southern_lands`: `NAM_radical_labour_camp` (focus `NAM_rad_labour_camps`,
  25 PP, 30 days, `NAM_labour_camp_state`: resources +50%, recruits -50%, no
  building, compliance and resistance penalties) and `NAM_radical_strip_state`
  (focus `NAM_rad_spoils_of_return`, 10 PP, once per state: one civilian and
  one military factory dismantled into treasury and arms, 1000 fuel,
  `NAM_stripped_state` for 365 days).
- Humanists: corporate economy modelled on The Fire Rises' corporate
  influence bands. Currency `NAM_corp_capital` (`NAM_corp_capital_add` with temp
  `NAM_corp_capital_change`), influence `NAM_corp_influence` 0..100
  (`NAM_corp_influence_clamp` recalculates the single aggregate
  `NAM_corp_dynamic` and opens the threshold events), free-zone slots
  `NAM_free_zone_slots` (1..3). Category `NAM_free_zones`:
  `NAM_corp_charter_free_zone` (focus `NAM_hum_free_zones`, islands 225-231, 30
  PP, 30 days; state modifier `NAM_free_zone_state`, -3% tax collection per
  zone, +20 capital, +5 influence), `NAM_corp_sell_steel`
  (`NAM_hum_steel_exchange`), `NAM_corp_labour_contract`
  (`NAM_hum_labour_bureau`, 3000 recruits leased for 90 days),
  `NAM_corp_innovation_park` (`NAM_hum_innovation_parks`, two industry
  breakthroughs), `NAM_corp_buy_arms` (`NAM_hum_credit_arms`),
  `NAM_corp_curb_influence` (`NAM_hum_regulated_partnership` or
  `NAM_hum_charter_commission`), `NAM_corp_court_investors`
  (`NAM_hum_open_doors`). Monthly in `on_monthly_NAM`: income per zone 20 +
  0.3 x influence; drift +1 per zone, +1 while workers are leased, -1. Bands:
  below 30 nothing, 30-69 research/efficiency/trade, 70-89 plus stability and
  PP penalties and event `.101`, from 90 event `.102`; three months at 90 or
  100 at once queue the takeover `.103`.
- Corporate takeover (`NAM_corp_takeover`, country flag `NAM_corp_takeover`):
  chairman `NAM_Mark_Olshansky` (commercial hedonism, trait
  `NAM_trait_chairman_of_the_boards`), cosmetic tag `NAM_corporate_state`,
  island boards `NAM_corporate_board_state`, influence fixed at 100, and
  `load_focus_tree = { tree = NAM_exile_corporate_focus keep_completed = yes }`
  after the flag. The humanist course continues: every federal
  district belongs to one of six corporations - 1 Yuzhneft oil concern, 2
  Island Steel trust, 3 Sea Line shipping company, 4 Coastal Arsenal arms
  company, 5 Artel labour agency, 6 Island Credit bank - recorded in the
  district's variable `NAM_corp_district_owner`. The owner gives the district
  the profile modifier `NAM_corp_owner_<n>_district`, the cosmetic tag
  `<TAG>_NAM_corp_<n>` ("Corporation: District") and pays the board a monthly
  dividend (capital, fuel or rifles). Rival corporations dispute districts
  (event `.108`, country flag `NAM_corp_dispute_open`, district flag
  `NAM_corp_disputed`); decisions `NAM_corp_auction_district`,
  `NAM_corp_board_arbitration` and `NAM_corp_charter_renewal`.
- Humanist policy on every conquest: the defeated country becomes a puppet with
  autonomy `autonomy_NAM_federal_district` (all manpower and trade, 90% of
  resources, 75% of civilian and 90% of military factories to NAM), country
  flag `NAM_federal_district`, NAM's array `NAM_federal_districts` and the
  cosmetic tag `<TAG>_NAM_federal_district` (or its corporation's tag after the
  takeover). Category `NAM_southern_lands`: `NAM_federal_council_session`
  (focus `NAM_hum_union_council`).
- New capital: `NAM_exile_found_new_capital` (COUNTRY NAM, called visibly by
  the exile focuses, once per campaign through the country flag
  `NAM_new_capital_founded`) renames the Great Island 228 to "Neo-Svetlogorye"
  (`NAM_neo_svetlogorye`) and its city 6893 to "Neo-Svetlogorsk"
  (`NAM_neo_svetlogorsk`), adds 2 victory points to the city and one
  infrastructure level and one shared building slot to the island; tooltip
  `NAM_exile_found_new_capital_tt`. Without 228 the island capital that
  replaced it takes the same names on its principal victory point
  (225: 11393, 227: 2478, 231: 13018, 226: 4396, 229: 3731, 230: 2742);
  without either nothing happens and the founding stays open. The names stay
  when a won war of return moves the capital back to 700.
- War of return from exile (`NAM_war_of_return_start` behind
  `NAM_war_of_return_can_start`; global flag `NAM_wor_exile_war`): against
  Eflor and Azhar only, in one temporary coalition from the shared faction
  template (dismantled on every terminal path), with the marine landing on
  South Harbour. Both capitulated: the homeland returns and the course's policy
  applies to both; global flag `NAM_war_of_return_won`; the consolidation
  begins. NAM capitulation: Svetlogorye with its islands is annexed by the
  participant holding its capital or the coalition's first independent member
  (news `.8`). The war has no deadline: it ends only when every participant
  or Svetlogorye has capitulated (the compromise war of return likewise ends
  only with the capitulation of every owner or the coalition treaty). A
  native peace, annexation or subjugation outside the treaty
  (`NAM_war_of_return_close_external`) closes it without awards; that is the
  only ending that can leave an independent exile without a win, so it is the
  only retry path: the return programme reopens and the decision
  `NAM_exile_renew_war_of_return` (category `NAM_exile_politics`, 50 PP,
  behind `NAM_war_of_return_can_start`) declares the next exile war while
  Eflor or Azhar still stands. `NAM_wor_exile_war_ready` blocks only a won or
  running war. The war of return after the compromise keeps its original
  field-owner form.
- Consolidation (`NAM_consolidation` 0..100 with `NAM_consolidation_clamp`;
  `NAM_consolidation_begin` at the exile war's victory sets 10 and the country
  flag `NAM_consolidation_started`): +2 a month, -2 below 40% stability, the
  aggregate `NAM_consolidation_dynamic` (stability, compliance). The junta pays
  3 treasury a month per conquered state until 100 and uses
  `NAM_rad_garrison_order` (+3 a month for 90 days, 20 treasury a month) and
  `NAM_rad_terror_campaign` (+8); the humanists use `NAM_hum_federal_treaty`
  (+6, per district) and `NAM_hum_reconstruction_fund` (+10 after 60 days, 60
  capital in escrow). Below 70 a 30% monthly roll (60-day cooldown) opens
  incident `.104` in a conquered state or a federal district with three costed
  answers per course. Category `NAM_consolidation`.
- Great war (`NAM_great_war_start` behind `NAM_great_war_can_start`: exile war
  won, consolidation >= 70, no War for the South, a target left): one war
  against Rahma, Sardan and Kadir plus Eflor or Azhar while still
  independent. Suppressed minors are woken first; the targets fight in one
  temporary coalition; every participant holds mandatory major status only for
  this war. Global flags `NAM_great_war_started`, `NAM_great_war_resolved`,
  `NAM_great_war_won`; events `.105` (declaration) and `.107` (victory). The
  war has no deadline. The dispatcher sections of
  `09_ADISCORD_scripted_peace_on_actions.txt` route NAM capitulation to
  `NAM_great_war_resolve_defeat` (annexation), the fall of every participant to
  `NAM_great_war_resolve_victory` (the course's policy for all) and native
  peace, annexation or subjugation to `NAM_great_war_close_external` (no
  award). After that external closure alone, the decision `NAM_renew_great_war`
  (category `NAM_consolidation`, 50 PP) restarts the war;
  `NAM_great_war_can_start` blocks only a running or won great war.
- Drill and marines per tree: `NAM_exile_drill` and its category open with
  `NAM_exile_drill_unlocked` (`NAM_exile_general_staff`,
  `NAM_hum_citizen_army` or `NAM_hum_company_guard`); `NAM_order_marines_corp`
  with `NAM_hum_marine_contracts` or `NAM_board_landing_contracts`.
- Symmetry: in both wars each side wins only by forcing the full
  capitulation of the other; there is no deadline, front settlement or capital
  rule, and no neutral state counts for either side. Events `.61` and `.106`
  (the former deadlines) are retired and kept reserved in the event registry.

## Shared contract for focus rewards

Focus rewards may only use native effects and the identifiers below. A focus
changes a value with `add_to_variable` and then calls the named clamp or
refresh effect inside `hidden_effect`, with a visible tooltip of the delta.

| Value or hook | Owner phase | Meaning |
| --- | --- | --- |
| `NAM_rw_tension` + `NAM_rw_tension_clamp = yes` | core 1 | Restitution pressure 0..100 |
| `NAM_seal_discipline` + `NAM_seal_discipline_clamp = yes` | core 1 | War discipline 0..100 |
| `NAM_line_slots` (base 2) | core 1 | Parallel defence-line preparations |
| `NAM_order_cap` (base 4, max 6) | core 1 | Mobilisation orders allowed |
| `NAM_rw_tribute` country flag with days | core 1 | Tribute deliveries to EFL and AZH; core 2 counts it as two committed units |
| `NAM_oil_bonus_units` + `NAM_oil_refresh = yes` | core 2 | Extra throughput units |
| `NAM_project_slots` (base 1, max 2) | core 2 | Parallel field projects |
| `NAM_underground` + `NAM_underground_clamp = yes` | core 3 | Weber underground 0..100 |
| `add_power_balance_value = { id = NAM_ladder_bop value = <x> }` | core 3 | Ladder balance, negative toward vertical |
| `NAM_apply_ending_iron`, `NAM_apply_ending_service`, `NAM_apply_ending_federation`, `NAM_apply_ending_oil_union` | core 3 | Ending effects called by the ending focuses |
| `NAM_wrk_trade_level` + `NAM_wrk_trade_refresh = yes` | core 4 | Trade houses in the metropole 0..3 |
| `NAM_center_vanished` country flag | core 4 | Set by event .80 at the collapse; `allow_branch` of post-collapse branches |
| `NAM_pirate_loot` via temp `NAM_pirate_loot_change` + `NAM_pirate_loot_add = yes` | core 4 | Exile loot |
| `NAM_pirate_notoriety` + `NAM_pirate_notoriety_clamp = yes` | core 4 | Coalition attention 0..100 |
| `NAM_pirate_raid_slots` (base 1, max 3) | core 4 | Parallel raids |
| `NAM_revenge_readiness` + `NAM_revenge_readiness_clamp = yes` | core 4 | Preparation for the return 0..100; 70 adds a landing division |
| `NAM_marine_order_cap` (base 1, max 3) | core 4 | Marine orders allowed |
| `NAM_exile_radical` / `NAM_exile_humanist` country flags | M10 | Course chosen by event .100 |
| `NAM_corp_capital` via temp `NAM_corp_capital_change` + `NAM_corp_capital_add = yes` | M10 | Foreign capital of the humanists |
| `NAM_corp_influence` + `NAM_corp_influence_clamp = yes` | M10 | Corporate influence 0..100 |
| `NAM_free_zone_slots` (base 1, max 3) | M10 | Free zones chartered at once |
| `NAM_consolidation` via temp `NAM_cons_change` + `NAM_consolidation_add = yes` | M10 | Hold on the returned south 0..100; 70 opens the great war |
| `NAM_great_war_start = yes` behind `NAM_great_war_can_start = yes` | M10 | The great war against the rest of the south |
| `NAM_exile_found_new_capital = yes`, country flag `NAM_new_capital_founded` | M10 | Founds Neo-Svetlogorsk on the island capital once; call visibly, not inside `hidden_effect` |
| Global flags `NAM_wor_exile_war`, `NAM_war_of_return_won`, `NAM_great_war_started`, `NAM_great_war_won`; country flags `NAM_consolidation_started`, `NAM_corp_takeover`, `NAM_federal_district`; state flag `NAM_conquered_state`; district variable `NAM_corp_district_owner` (1-6) | M10 | Read-only markers for focus conditions |
| `ADISCORD_nam_memoir.1..5`, `ADISCORD_nam_archive.1..6` | core 3 | Memoir and archive events |

Decision IDs available to `unlock_decision_tooltip`:
core 1 - `NAM_restitution_note`, `NAM_order_resource_guard`, `NAM_order_field_infantry`,
`NAM_order_motor_column`, `NAM_order_coastal_battalion`, `NAM_prepare_line`, `NAM_scorch_wells`;
core 2 - `NAM_oil_contract_offer`, `NAM_fuel_embargo`, `NAM_project_repair_wells`,
`NAM_project_refinery`, `NAM_project_pipeline`, `NAM_project_sea_terminal`,
`NAM_island_steel_levy`, `NAM_island_convoy_service`, `NAM_island_concession_231`,
`NAM_renegotiate_val_concession`, `NAM_south_allied_fuel`, `NAM_south_convoy_interdiction`;
core 3 - `NAM_favour_nam`, `NAM_favour_oil`, `NAM_favour_dist`, `NAM_favour_garr`,
`NAM_favour_trade`, `NAM_weber_talks_1`, `NAM_hunt_caches`.
A focus that needs anything else lists the request in its author's report; the
lead assigns it to the next core phase instead of inventing a call.

## File ownership

All new NAM content extends the existing `*_nam_resource_war_*` files.
New engine types each get one file: `common/bop/NAM.txt`,
`common/ai_strategy_plans/ADISCORD_NAM_plans.txt`, the basin GUI files.
Russian text goes to `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml`
(UTF-8 with BOM) and its English pair.

## Verification

Static only unless the user asks: builder `--check` then `--apply` and a second
idempotent `--check`, the NAM validator, `git diff --check`. The game is not
restarted by agents; runtime behaviour remains unproven until the user plays it.
