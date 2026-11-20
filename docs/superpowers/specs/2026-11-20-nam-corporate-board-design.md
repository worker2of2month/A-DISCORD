# NAM corporate exile: the council of boards

Status: design draft for implementation by subagents. Nothing in this document
is implemented yet. Line numbers are hints from a snapshot taken on 2026-11-20;
the NAM files are edited in parallel by the user and by Codex, so re-read every
target before inserting and splice by section, never by line.

## Goal

Give the corporate exile route of NAM (flag `NAM_corp_takeover`, tree
`NAM_exile_corporate_focus`) its own mechanics, at the level of the three parts
of the mod the user finds most fun to play: the NAM governor before the resource
war, the Stelander civil war and the Khan's bunker.

The player is the council itself, not its chairman. The six company boards are
the player's material: their votes, their trust, their ministers and their
demands. Two outside rivals, "the Two Judases", press on the council until they
are dealt with. Changing the chairman is a tool and a risk, never a game over.

## What exists today (verified in code)

- Six companies with one-based ids: 1 Loren (oil), 2 Ferrant (steel),
  3 Navis (shipping), 4 Arktur (arsenal), 5 Smenkom (labour exchange),
  6 Reidbank (bank).
- `NAM_board_recount` counts votes: 3 per industry, 2 per undisputed federal
  district, 1 for a minister; ties go to the lower id; `NAM_board_rank_1..6`
  orders the pyramid seats.
- Industries: oil (1), coastal shipping (3) and the labour exchange (5) are
  fixed. Three lots are tendered 7 days after the takeover, one after another:
  rail workshops (2 or 5), shipyards (3 or 4), fuel depots (1 or 6). The winner
  is a 50/50 `random_list`; the tender events have one option and no effect.
- A company holding assets without a minister is neutral for 30 days
  (`NAM_board_objection_days`), then boycotts: its two profile modifiers flip
  sign at half strength. The pyramid card already prints "В кабинете",
  "Нейтральна", "До бойкота: N", "Бойкот".
- The pyramid window `ADISCORD_NAM_board_window` (460x594) is embedded in the
  decision category `NAM_free_zones` through the scripted GUI
  `ADISCORD_NAM_board_panel`. It has no buttons and no effects.
- Cabinet: seven `political_advisor_*` slots, 75 political power each. Company
  seats today: economy (Loren or Reidbank), education (Ferrant or Smenkom),
  defence (Arktur or the non-company Selivanov), foreign affairs (Navis).
  Premier Kornev cannot be removed.
- There are no federal districts during exile (the array `NAM_federal_districts`
  is filled only after a won return), so in exile votes come only from
  industries and ministers. Starting votes are 3, 0, 4, 0, 4, 1.
- `NAM_corp_influence` is pinned at 100 by `NAM_corp_influence_clamp`. Foreign
  capital `NAM_corp_capital` is the working currency: 50 a month per free zone,
  one zone slot, prices of 30-60.
- The Two Judases have no state: the kill focuses only call
  `retire_character`. The category `NAM_two_judases` shows status text and
  three decisions.
- The tree has 70 focuses (157 cost points, 1099 days; one playthrough is about
  850-875 days). Five focuses have rewards. Nothing in the tree starts the
  return war; `NAM_war_of_return_start` exists and targets EFL and AZH.
- The country leader is Mark Olshansky, promoted once in `NAM_corp_takeover`.
  No company head is named anywhere. No effect replaces one board chairman with
  another.

## Decisions taken by the user

1. The player plays the council. A change of chairman is an instrument.
2. The leader changes only through a vote of no confidence or the annual
   shareholders' meeting, not on every recount.
3. The country leader is the head of the company that takes the chair. Every
   minister carries a visible trait naming his company. Companies demand seats
   and the dismissal of rival ministers; the player chooses between companies.
4. Tenders are decided by the player. No random winner.
5. Both kill focuses are always available. Consequences depend on how much
   support the rival still has.
6. "99 to 1" means 99 percent poor and 1 percent rich.
7. Company events get their own look.
8. After `NAM_board_partition_night` a large sub-branch opens lower in the same
   tree: seizing the Ulven League (ULV, states 644-648), the Luren Archipelago
   (LUR, 649-652) and the Sharden Confederation (CHD, 672-680) by landings,
   marines, rearming the army and industry, the 99 to 1 society, and at the end
   the return to the mainland. After the return a separate unique tree loads,
   depending on who won; only the corporate winner is in scope now.
9. The focuses `NAM_board_treaty_two_judases` and `NAM_board_escheated_throne`
   stay closed as work in progress. Only the route where both rivals die is
   built now.
10. Ferrant's demands must be weightier than a truck order.
11. At the annual meeting the chair goes strictly to the head of the company
    at the top of the pyramid. The council does not nominate. The player
    steers the outcome only by who holds the most votes on that day.
12. Every chairman brings his own buffs and debuffs. A company's tooltip names
    its head and lists his traits, so the player sees in advance what a change
    of chairman would bring.
13. The state is renamed from "Корпоративное Светлогорье" to "Светлогорская
    директория". Only the localisation values of `NAM_corporate_state` change.

## Design principles taken from the three references

Each rule below was observed in the reference code and binds this design.

- One shared pool of action slots for attack and defence (STP political action
  slots). Here: chancery slots.
- A rival that acts on a visible clock and aims at what the player did last
  (STP inspections). Here: the Judas meetings.
- Two competing proposals; the rejected side answers with its own price (NAM
  council agreements). Here: board sessions.
- Missions with material goals, a success result and a failure result (NAM
  agreements). Here: resolutions.
- The chain promise - failure - recovery mission - loss of the leader (NAM
  pillar crisis and coup). Here: boycott - vote of no confidence - new chair.
- A capacity budget every option draws on (bunker power). Here: seven cabinet
  seats for six companies.
- Focus gates that read the real state of the mechanic (bunker commission).
  Here: the final needs a majority.
- One advisor line naming the next risk, and "now / after" previews (bunker
  panel). Here: the council line on the pyramid.
- Forecasts in tooltips: what will happen and why (STP district forecast).

Not to copy, because the references are weakest there: `random_list` outcomes,
passive waiting timers, rows of identical flat bonuses, and fixed-price answers
that only cancel a threat.

## M0. Interregnum: the islands without a government

Decided by the user on 2026-11-20. A story stage between the evacuation and
the council of boards. Only the corporate exit is built now.

1. After the evacuation the sitting ruler (Egor Rom, or the pre-war coup
   leader where one rules) keeps the seals on the islands for 7 days.
2. Then an event the player does not control: the crowd executes him on the
   quay. He is retired for good.
3. The same effect, `NAM_interregnum_begin`, sets the ruling party to
   anarchism without elections and promotes the character
   `NAM_Absent_Government` ("Отсутствующее правительство"), whose portrait
   reuses the texture `gfx/leaders/TFF/portrait_TFF_absent_government.png`
   under a NAM sprite name. The character is recruited in the country history
   with an `anarchism_ideology` leader role, as the board heads are.
4. The spirit "Безвластие" lowers stability a little every week and cuts
   political power gain. It is removed when a government takes the seals.
5. The focus tree changes to a short interregnum tree,
   `NAM_exile_interregnum_focus` (source
   `focus_trees/NAM/exile_interregnum/focuses.txt`): a root, three lanes of
   two focuses in which each camp makes its case - the boards of Olshansky,
   the port committees of Weber, the coast guard officers of Karamyshev - and
   three mutually exclusive finals that hand the seals to one camp. Every
   focus costs 1 (7 days), so root, lanes and a final fit in 56 days. The
   final for the boards calls `NAM_corp_takeover`, which loads the corporate
   tree as today. The finals for the committees and for the officers are
   closed with the existing `NAM_island_wip_tt` gate.
6. A visible 60-day timeout-only mission, "Острова без власти", runs from the
   execution. If it runs out before a final is taken, the boards take the
   seals by themselves through the same takeover.
7. The stage is story: events and small concrete results, no new subsystem.
   Each lane focus still gives a full, concrete reward that reaches the
   country after the takeover (the lint rejects tooltip-only rewards), and
   the lanes differ in kind: men from the committees, readiness or army
   experience from the officers, capital from the boards.
8. The council's clocks (tenders, sessions, the Judas meetings, the annual
   meeting) count from the takeover, not from the evacuation.
9. The debug corporate start skips the interregnum.
10. The AI takes the boards' lane and the boards' final.

## M1. Trust, stance and the majority

### State

Country NAM, all arrays of size 7 with index 0 unused, index = company id.

| Name | Kind | Meaning |
| --- | --- | --- |
| `NAM_board_support` | array | Trust of a company in the council, 0-100 |
| `NAM_board_stance` | array | Derived in recount: 1 for, 0 waiting, -1 boycott |
| `NAM_board_objection_days` | array, exists | Absolute day when a company below the boycott line starts its boycott |
| `NAM_board_votes_for` | variable | Votes of companies that are for |
| `NAM_board_votes_against` | variable | Votes of boycotting companies |
| `NAM_board_votes_total` | variable | All votes |
| `NAM_board_chair` | variable | 0 Olshansky, 1-6 the company whose head chairs |
| `NAM_board_selected` | variable | Company selected on the pyramid, 0 for none |

Trust is the only new number per company. Stance is derived, never written by
hand. Do not add flags that mirror it.

### Bands

- 60 and above: for. Votes count for the council; the company profile applies
  at full level.
- 35-59: waiting. Votes count for nobody; the profile applies at zero.
- below 35: a 30-day countdown starts (the existing `NAM_board_objection_days`
  slot and its "До бойкота: N" text). If trust is still below 35 when it ends,
  the company boycotts: votes count against, the profile applies at -0.5 of the
  level, and its product is blocked (see "Blocked products"). Rising to 35 or
  above clears the countdown or the boycott.

Stance depends on trust alone. The existing loop in
`NAM_board_update_industrial_policy` clears the countdown whenever a minister
is seated or the company has no assets; that rule is removed. A company with
no industry still boycotts with its votes; only its profile stays at zero. The
four status texts in scripted localisation are driven by `NAM_board_stance`
and the countdown, not by `has_idea` or by the sign of a rate.

### Resting level and drift

Once a month trust moves 1 point toward its resting level:

    resting = 30 + 10 per seat held + 5 per industry held
              + 10 if its head chairs
              - 5 for each OTHER company that holds two or more industries
    clamped to 20-70; the premier's seat counts as two seats

| Example | Resting level |
| --- | --- |
| No seat, no industry (Ferrant and Arktur at the start) | 30: drifts into a countdown |
| One industry, no seat (Loren at the start) | 35: on the brink |
| One seat, one industry (Navis, Smenkom) | 45 |
| Two seats and two industries | 60 |
| The same company with its head in the chair | 70 |

Nobody rests in the "for" band without two seats and two industries or the
chair. Support is earned by fulfilled resolutions, tenders and lobbying, and a
gain of 15 lasts about fifteen months. The envy term is what makes hoarding
every lot in three companies expensive: the other three sink toward a boycott.

Opening trust: Navis, Smenkom and Reidbank 66; Loren, Ferrant and Arktur 45.
The opening majority therefore lasts about half a year without any action and
the player sees it running out.

The card tooltip shows the forecast: trust now, trust after the next monthly
step, the resting level and its components.

### Events that move trust

| Cause | Change |
| --- | --- |
| Its candidate is appointed | +10 |
| Its minister is dismissed or replaced | -15 (-5 after a prepared dismissal) |
| Wins a tender | +15 |
| Loses a tender | -15 |
| Its motion is adopted at a session | +5 |
| Its motion is rejected | -10 and its sanction; -5 and no sanction while Olshansky chairs |
| Its resolution is fulfilled | +15 |
| Its resolution fails | -20 and its sanction |
| Chancery lobbying | +10, and -5 for its tender rival |
| Dividend paid | +8 for every company that holds an industry |
| Dividend withheld | -8 for every company that holds an industry |
| Its head takes the chair at the annual meeting | +15 |
| Its head loses the chair | -20 |

A seat resolution that succeeds gives the +15 only; the +10 of the
appointment is suppressed for that appointment. Tender rivals are the pairs
1-6, 2-5 and 3-4.

Every write goes through one effect, `NAM_board_support_change`, with the
temporary inputs `NAM_board_company_input` and `NAM_board_delta_input`, or
`NAM_board_set_input` for an absolute value. It clamps to 0-100. Callers never
write the array directly, except the one-time opening values.

Contract for effects with temporary inputs: an effect copies its inputs into
its own private temporary variables on its first lines, because idea callbacks
and nested calls reuse the shared input names. Nothing may rely on an input
after calling another board effect.

### Votes and the majority

| Source | Votes |
| --- | --- |
| Every company, as a shareholder | 2 |
| Each industry | 2 |
| Each seat | 1, the premier's seat 2 |
| Each undisputed district or island concession | 2 |

Opening votes: Loren 4, Ferrant 2, Navis 5, Arktur 2, Smenkom 5, Reidbank 3,
21 in total. No company is ever without a vote, so every stance matters.

`NAM_board_recount` additionally derives the stance array, the rank-indexed
stance frames and the three vote sums. The council has a majority when
`votes_for x 2 > votes_total`. The recount records the day the majority began
in `NAM_board_majority_since` and clears it when the majority is lost.

Recount discipline: the queue through hidden event `.111` gets a transient
flag `NAM_board_recount_queued`, set by the queue effect and cleared by the
event, so one session queues one recount. Any effect that reads votes after
changing trust calls `NAM_board_recount = yes` directly: the annual meeting,
the no-confidence timeout, "adopt both" and `NAM_board_install_chairman`. The
monthly order inside `NAM_corp_monthly` is drift, recount, no-confidence
check, written with `for_loop_effect` over 1-6 (the validator rejects
`every_country` and `every_owned_state` there).

Consumers of the majority:

- `NAM_board_politics`: a majority gives political power +0.20 a day and
  stability +5%; each boycotting company gives stability -3%. The recount
  stores `NAM_board_majority_pp` and `NAM_board_majority_stab`; only
  `NAM_corp_refresh` composes the final `NAM_corp_mod_pp` and
  `NAM_corp_mod_stability`, because it overwrites them on every call.
- Adopting both motions at a session needs a majority (M3).
- `NAM_board_partition_night` and the war focuses of the lower branch need a
  majority that has held for 60 days in a row. One localised custom trigger
  tooltip shows "держится N из 60 дней".

### Blocked products

One scripted trigger per product, `NAM_board_product_blocked_<n>`, is true
while company n boycotts or while its sanction spirit runs. It closes the
decisions that use that product and withholds its consignment: fuel (1), steel
and armour (2), convoys (3), arms (4), manpower contracts (5), loans and the
payments it still owes (6).

### Vote of no confidence

When the monthly check finds `votes_against > votes_for` and at least one
boycott, the timeout-only mission `NAM_board_no_confidence` opens for 45 days.
The player can still appoint, lobby, concede a resolution or let a countdown
company recover. The council line forecasts the result: the votes for and
against if the vote were counted today and the head who would take the chair.

At timeout, after a direct recount:

- if `votes_against > votes_for` still holds, the motion passes. In this
  order: every boycotting company is set to 55; every company that was for
  loses 10; the chair goes to the head of the boycotting company with the most
  votes that does not already hold the chair (lower id on a tie); if there is
  no such company the motion fails instead. The new chair's company gets no
  further bonus. The timed spirit "Вотум недоверия" lasts 120 days: stability
  -10%, political power -0.20 a day;
- otherwise the motion fails: stability +5%, and each company that
  boycotted loses 5 more.

Either way a 180-day immunity starts. The mission cannot open during the
immunity, while the flag `NAM_board_meeting_open` is set (the annual meeting
event sets it in `immediate` and clears it in every option), or while
`NAM_board_operable` is false.

### Lifecycle rules for every clock and operation

- Missions are not re-armed from inside themselves: `activate_mission` fails
  on an active mission. The `timeout_effect` queues a hidden event one day
  later that activates the mission again and stores the next speakers or
  target. The interval is adjusted with `add_days_mission_timeout`.
- Each mission stores its absolute end day in a variable when it is armed
  (`NAM_board_session_day`, `NAM_board_meeting_day`,
  `NAM_board_no_confidence_day`, `NAM_judas_weber_day`,
  `NAM_judas_karamyshev_day`). The window and the texts read those, as the
  existing boycott countdown does.
- While `NAM_board_operable` is false (subject, capitulated, not NAM), every
  timeout re-arms silently without its event, and every operation is cancelled
  through its `cancel_trigger` with a refund and the release of its slot.
- Clocks, slots and trust keep running across the swap to
  `NAM_south_war_focus` and back and through the return war. The council
  mechanic ends when the stage-3 tree is loaded.
- `remove_mission` runs no effect: whoever removes a mission by script also
  releases its slot and settles its deposit.
- New arrays and variables are created inside the existing one-time guard of
  `NAM_board_initialize`. No separate `has_variable` guard: that would be
  recovery for saves this mod does not support.
- Every `_desc` of a new mission, decision or spirit is narrative only.
  Criteria go into `available`, results into the effect blocks with native
  output or `custom_effect_tooltip`.
- Every timed country-wide result is a spirit added with `add_timed_idea`. If
  it changes scripted income, the income effect reads it with `has_idea` and
  the spirit's `on_add` and `on_remove` call `ADISCORD_economy_mark_dirty`.

## M2. Cabinet

Seven seats, six companies, three candidates per company, plus four career
officials without a company. Every seat is contested.

| Seat | Career official | Company candidates |
| --- | --- | --- |
| Premier (`head_of_state`) | Семён Корнев | Loren: Всеволод Рахманов; Reidbank: Вениамин Крамской |
| Defence | Виктор Селиванов | Arktur: Марк Ветлугин; Ferrant: Матвей Бронников; Navis: Ефрем Баталов |
| Economy | - | Loren: Борис Нартов; Reidbank: Леонид Белов; Ferrant: Варвара Ставрова |
| Health | Лев Вересов | Smenkom: Фаина Одинцова; Reidbank: Юлия Савицкая |
| Education | - | Ferrant: Федот Ермолин; Smenkom: Пётр Литвинов; Arktur: Иннокентий Бахметьев |
| Intelligence | Андрей Булатов | Arktur: Тихон Зарубин; Navis: Раиса Чайкина |
| Foreign affairs | - | Navis: Павел Ордынцев; Loren: Юлиан Дашков; Smenkom: Рашид Ильдаров |

Rules:

- A career official gives no vote and moves no trust. He is the safe choice
  that pleases nobody: every company that has a candidate for his seat may
  table a motion to replace him.
- Kornev becomes removable. The premier's seat counts as two votes and as two
  seats for the resting level.
- Company ministers are board-era ideas in
  `common/ideas/ADISCORD_nam_resource_war_ideas.txt`, named
  `NAM_board_min_<company>_<seat>`. The existing ids
  `NAM_board_bank_nominee` and `NAM_board_labor_nominee` stay. Нартов, Ермолин,
  Ветлугин and Ордынцев get board-era twins; their pre-war
  `minister_NAM_*` ideas are hidden under the takeover, because those ideas are
  visible before the exile and must not show a company there.
- Each company minister has exactly one trait, a label-only company trait
  (`NAM_trait_company_loren` and so on, `random = no`, defined beside
  `minister_trait_foreign_commissioner`), and his own working modifier in the
  idea's `modifier` block. No idea in the mod or in vanilla lists two traits;
  do not rely on that.
- Each minister's working modifier is different in kind from the others in his
  seat, so the choice of seat holder is also a choice of policy. No two
  candidates for one seat give the same modifier with different numbers.
- `on_add` and `on_remove` set `NAM_board_company_input` and call
  `NAM_board_minister_seated` or `NAM_board_minister_unseated`, which apply the
  trust change and queue the recount. The recount counts seats by `has_idea`
  per company; it does not keep a counter that script removal could desync.
- `NAM_board_appoint_cabinet` keeps the opening cabinet: Kornev, Selivanov,
  Veresov, Bulatov, Belov, Litvinov and the board-era twin of Ordyntsev.
- Order inside `NAM_corp_takeover`, so that no penalty fires at the start:
  1. create the arrays inside the one-time guard of `NAM_board_initialize`;
  2. appoint the cabinet while the seat callbacks are silent;
  3. write the opening trust with `set_variable`;
  4. set the flag `NAM_board_opened`, then run the first recount.
  The seat callbacks do nothing until `NAM_board_opened` is set, and a
  transient flag silences them around `ADISCORD_debug_clear_country_ideas` in
  the debug start. A test checks that the debug start and the ordinary start
  end with the same trust and stance.
- The pre-war ideas `minister_NAM_Boris_Nar`, `_Fedot_Mir`, `_Mara_Kluch` and
  `_Pavel_Ordyntsev` lose their board callbacks and their
  `NAM_board_appointment_N_tt` tooltips; the twins carry them now.
- `NAM_board_minister_1..6` are replaced by a seat count per company inside
  the recount (the premier's seat counts 2).
- Every board minister has `ai_will_do` factor 0 unless the scripted AI policy
  has flagged that seat (M9); otherwise native advisor churn would swing trust
  at random.
- Working modifiers of all 22 are in appendix A.5.

The portrait list for these people is appendix E.

## M3. Board sessions and resolutions

### The clock

The visible timeout-only mission `NAM_board_session` runs for 60 days and is
re-armed by its own timeout. When it starts, the two speakers of the coming
session are fixed and shown in the category text, so the player knows 60 days
ahead who will speak:

- candidates are companies with at least one vote or one seat that have no
  running resolution and did not speak at the previous session;
- the two with the lowest trust speak; ties go to more votes, then lower id.

Each company has an ordered agenda of five motions. It tables the first one
whose conditions hold and which has not been fulfilled. Its card tooltip shows
that motion. The agenda is appendix A.

### The session event

There is no conditional event picture, so there are six thin session events,
one per first speaker, each with that company's plate. A hidden dispatcher
picks the id; all six call the same option effects. The country event window
has four option slots. An unattended event takes its first option, so the
first option is the default:

1. Close the session without a decision: both speakers lose 10 and both apply
   their sanctions.
2. Adopt the first speaker's motion.
3. Adopt the second speaker's motion.
4. Adopt both: needs a majority, both resolution slots free, 50 political
   power, and not within 180 days of the previous time.

The company whose motion is rejected loses 10 and applies its sanction, a
company-specific 60-day spirit (appendix A.2).

During the 14 days before a session the category offers "Снять вопрос с
повестки": 40 political power, both speakers lose 5, the session moves 30
days. It cannot be used for two sessions in a row. A session that finds both
resolution slots full moves 30 days by itself.

Speakers: a company that lost a tender in the last 180 days is always a
candidate. If fewer than two companies are eligible, the exclusion "spoke at
the previous session" is dropped first, then the exclusion "has a running
resolution".

### Resolutions

An adopted motion becomes a mission with a material goal and a deadline of
90-150 days. At most two run at once. Kinds, so that no two are the same
purchase with a different label:

- seat: appoint our candidate to a named seat;
- dismissal: remove a named rival minister;
- industry: award us the named lot;
- order: place a state order for our product and take delivery;
- privilege: grant a timed privilege that costs the country something;
- a stand on a Judas: act against him, or leave him alone, for a period.

Success: +15 trust and the motion's concrete result. Failure or cancellation:
-20 and the company's sanction. Paid deposits follow the existing escrow
pattern (`cost = 0`, `custom_cost_text` with `_blocked` and `_tooltip`
variants, a deposit variable and a refund effect), as in
`NAM_corp_innovation_park`.

## M4. Tenders

The three lots keep their order and their pairs. They open on days 14, 60 and
120 after the takeover. Each is a visible 14-day mission with award decisions
named `NAM_board_award_<lot>_<company>` and `NAM_board_keep_<lot>_public`.
Do not name anything `NAM_board_tender_<lot>`: two tests forbid those ids.

- Terms are in appendix A.3: the company that already holds an industry pays
  80 capital; the newcomer pays 40 and adds a consignment of its product.
- Award: the winner gains the industry and +15 trust; the loser gets -15 and
  becomes a guaranteed speaker for 180 days, with its dismissal or seat motion
  against the winner first on its agenda.
- Keep public: the existing public-lot bonus in
  `NAM_board_update_industrial_policy` stays, both bidders lose 5, and the lot
  returns as a motion.
- Unattended timeout: the lot stays public, both lose 10, and the tender
  reopens 30 days later.

`NAM_board_close_tender` loses its three `random_list` blocks.

## M5. The chancery

`NAM_board_action_slots` starts at 1; two focuses of the centre branch raise
it to 3, the third no earlier than the second year. `NAM_board_action_used`
counts running operations. Slots are shared between different operations: one
decision cannot run twice, so there is one lobbying at a time.

- Lobby the selected company: 30 political power and 25 capital, 21 days, +10
  trust and -5 for its tender rival, not above 65, and not on the same company
  within 120 days (`NAM_board_lobby_day`, an array of absolute days).
- Prepare a dismissal: 20 political power, 21 days; the next dismissal of the
  named company's minister costs that company 5 instead of 15
  (`NAM_board_dismissal_prepared`, cleared at the dismissal, at the minister's
  removal and after 120 days).
- Every operation against a Judas (M7).

The pyramid seats become buttons that set `NAM_board_selected`. Operations on
a company are single decisions that act on the selected company through the
arrays; do not write six copies. A running operation stores its own target in
`complete_effect` and reads only that later; its `visible` also holds
`has_decision` of itself so it stays listed when the selection changes. The
selection is written by the buttons for the player and by script only for
`is_ai = yes`.

Seat prices: a company candidate costs 50 political power, a career official
25. The safe choice is also the cheap one.

## M6. Annual meeting and the chair

### Annual meeting

The visible timeout-only mission `NAM_board_annual_meeting` runs 360 days from
the takeover and re-arms. Its event asks two things.

The chair is settled first, then the dividend.

Dividend: pay 40 capital for each industry held by a company (120-240), and
every company that holds an industry gains 8; or withhold it, each of them
loses 8 and the capital stays.

Chair: the head of the company at the top of the pyramid
(`NAM_board_rank_1` on that day) takes or keeps the chair. There is no
nomination and no exception for a majority. Olshansky, who has no company,
therefore holds the chair only until the first annual meeting or the first
successful vote of no confidence. The top company is read once, when the
mission times out; the category text and the pyramid show who would take the
chair if the meeting were held today, and the days left.

This makes the pyramid a race toward a known date: tenders, seats and later
the seized islands decide whose head rules for the next year.

### Installing a chairman

One effect, `NAM_board_install_chairman`, with the input
`NAM_board_company_input` (0 restores Olshansky):

1. `promote_character = { character = <head> ideology = <sub-ideology> }`;
2. set `NAM_board_chair`, apply the trust changes, run the recount directly;
3. keep the ruling party, the cosmetic tag and the cabinet;
4. `ADISCORD_economy_mark_dirty`.

The engine has no demotion. `recruit_character` works only in country
history, so the six heads are recruited there without a role, as Olshansky is.
They get their hedonism leader role once, in `NAM_corp_takeover`, without
`promote_leader`; Olshansky is promoted as
today and is restored the same way. Never call `remove_country_leader_role`
or `retire_character` on a head or on Olshansky, and never add a role twice:
`NAM_party_representative_hedonism` also holds a hedonism leader role and the
engine would fall back to him. `NAM_island_partition_succession` and every
check of `has_country_leader = { character = NAM_Mark_Olshansky ... }` move to
a trigger `NAM_board_chairman_rules`.

Both consumers of the chair follow `NAM_board_chair`, not `NAM_board_rank_1`:
the extra level in `NAM_board_update_industrial_policy` and the consignment
test in `NAM_corp_charter_renewal`. Under Olshansky no company gets them. The
caption over seat 1 becomes "Первое место"; the rules text
`NAM_board_election_rules` is rewritten.

A signature decision is only visible under its chairman. What it started
outlives him: a repayment spirit, a build in progress and a debt variable
never test the chair in `cancel_trigger`.

### The six chairmen

Changed by the user on 2026-11-20: the directorate is ruled by the technocracy
party, and Olshansky and all six heads carry the one leader ideology
`techno_corporatism` ("Технокорпоратократия"). The "Sub-ideology" column of
the table below and every mention of a hedonism leader role are void:
`promote_character` makes a character leader only inside the ruling party.
The chairmen differ by their traits and signature decisions.

Each head has leader traits that carry both buffs and debuffs, and one
signature decision that exists only while he chairs. The decisions differ in
kind, and so do the traits: no two chairmen are the same bonus with different
numbers, and every one of them costs the country something.

The company card tooltip on the pyramid reads "Компанию возглавляет <имя>" and
lists his traits with their modifiers, whether or not he chairs. The traits
are native leader traits; the tooltip repeats their localised text through
`$key$` references, so the two can never disagree.

| Company | Head | Sub-ideology | Signature decision |
| --- | --- | --- | --- |
| Loren | Аристарх Вяземцев | `patronal_hedonism` | Advance against future oil: capital now, repaid from the fields after the return |
| Ferrant | Таисия Вальц | `industrial_aristocratism` | Trust plan: a fixed-price factory on a chosen island |
| Navis | Савелий Крузе | `commercial_hedonism` | Letters of marque: opens the existing piracy lanes against ULV, LUR and CHD to the council |
| Arktur | Родион Калёнов | `radical_hedonism` | Order out of turn: capital into arms now, and a company guard formation |
| Smenkom | Назар Гурьев | `hedonism_ideology` | Contract recruitment: manpower from overseas labour contracts |
| Reidbank | Лидия Вельяминова | `aristocratic_hedonism` | Consolidated loan: a large sum now against a monthly repayment |

Leader traits. Each has a price; these replace the buff-only list of appendix
A.6. The signature decisions are detailed in appendix A.4.

| Head | Trait | Buffs | Debuffs |
| --- | --- | --- | --- |
| Вяземцев | "Нефтяной патриарх" | fuel gain +20%, maximum fuel +25% | research speed -5% |
| Вальц | "Хозяйка стального треста" | military factory output +5%, maximum factory efficiency +5% | army experience gain -10% |
| Крузе | "Король фрахта" | dockyard output +10%, convoy retreat speed +20% | `ADISCORD_economy_tax_collection_factor` -5% |
| Калёнов | "Порядок прежде прибыли" | war support +10%, core defence +5% | stability -5%, consumer goods +3% |
| Гурьев | "Распорядитель биржи" | monthly population +10%, construction speed +5% | stability -3%; Weber's support grows 1 faster a month while he lives |
| Вельяминова | "Держательница векселей" | political power +0.10 a day, `ADISCORD_economy_admin_expense_factor` -5% | war support -10% |

Olshansky keeps `NAM_trait_chairman_of_the_boards` and has no signature
decision. His value is neutrality: no company rests higher because of him, and
a company whose motion is rejected under him loses 5 instead of 10 and applies
no sanction.

## M7. The Two Judases

### State

`NAM_judas_weber` and `NAM_judas_karamyshev`, 0-100: the support of the port
committees and of the coast guard officers. Weber starts at 70, Karamyshev at
60. Each grows by 2 a month while its man lives. The variables are cleared when
he dies.

### Their clocks

Each camp meets on a visible timeout-only mission and then acts. The category
text names the next target and the reason in advance.

- Port committees: every 50 days, 40 at support of 60 or more, paused below
  20. Target: the industry of the company the council favoured last (the last
  tender winner or resolution beneficiary).
- Officers' assembly: every 60 days, 45 at support of 60 or more, paused below
  20. Target: the army's preparation.

Each meeting fires one event with three answers that cost different things: a
concession paid in capital that raises the camp's support, force that lowers it
at a price in stability or readiness and needs a willing company, or standing
aside and losing the targeted asset for a period. None of them is a plain fee
that cancels the threat. Appendix B lists them.

### Operations

Chancery operations in `NAM_two_judases`, unlocked by
`NAM_board_founders_of_unrest` (Weber) and `NAM_board_dead_mans_veto`
(Karamyshev) and by later focuses of their branches. Each takes a slot, has a
price and a duration, lowers the camp's support and moves the trust of the
companies with an interest in that camp. Appendix B lists them.

### The killings

`NAM_board_last_debtor` and `NAM_board_posthumous_signature` stay without
conditions. Their reward shows, through scripted localisation, the outcome at
the current support, and applies the same branch:

| Support | Weber | Karamyshev |
| --- | --- | --- |
| 60 or more | General strike: 90 days of zero zone income, lower dockyard output and stability | Coast guard mutiny: a share of the convoys and one division leave, readiness falls sharply |
| 30-59 | Strike: 45 days at half strength | Unrest: readiness falls, 60 days of weaker recovery |
| below 30 | The committees dissolve quietly and their men enter the labour exchange | The officers swear to the council and the staff joins it |

Timed country-wide results are national spirits added with `add_timed_idea`.
Each killing also moves company trust; the table is in appendix B.

The WIP focuses keep their gates. `NAMIslandWeberStatus` and
`NAMIslandKaramyshevStatus` gain a support line while the man lives.

## M8. The pyramid window

- Seats become buttons that select a company. The category then lists the
  operations for it.
- Beside each mark: one multi-frame stance sprite (for, waiting, countdown,
  boycott), frame read from a rank-indexed variable written by the recount.
  Seat N shows the company at rank N, so every per-seat value is rank-indexed.
- A marker on a seat whose company has a running resolution.
- Top left free rectangle (x 4-100, y 20-148): votes for, against, total.
- Top right free rectangle (x 350-455, y 20-148): the chairman's name, the
  days to the next session and to the annual meeting, read from the native
  missions, and the head who would take the chair if the meeting were today.
- Each company card tooltip names the company's head and his traits (M6).
- Under the caption: one council line naming the first risk in this order: a
  vote of no confidence is running; a company is counting down to a boycott; a
  resolution has less than 30 days; a session comes within 14 days; a Judas
  meeting comes within 14 days; nothing urgent.
- The category `NAM_free_zones` keeps its id; its title changes to "Совет
  правлений".

The window and its sprites at the top of `ADISCORD_NAM_basin.gfx` are
hand-authored, but the files are registered to the basin map builder. Check
`tools/data/generated_output_owners.json` and the builder's markers before
editing, and keep new board sprites outside the generated blocks.

## M9. AI

- The plan `NAM_exile_corporate_plan` keeps one alternative of each exclusive
  pair and both killings.
- Sessions: `ai_chance` favours the speaker with more votes.
- Tenders: the AI awards to the bidder with higher trust.
- Monthly policy inside `NAM_corp_monthly`: select the company with the lowest
  trust among those holding votes and lobby it when a slot is free; run the
  cheapest Judas operation otherwise.
- The AI pays the dividend when it can.
- A lost vote of no confidence is a normal outcome for the AI.

## M10. The tree

### Upper tree (70 focuses)

Every focus gets a full reward tied to the mechanics above: a seat, a slot, an
operation, a programme with a price and a duration, a concrete delivery. No
focus rewards a tooltip alone, and no branch is a chain of the same bonus. The
per-focus table is appendix C. Fixed points:

- left branch: capital income, zones, tender terms, the re-gating of
  `NAM_corp_sell_steel` and `NAM_corp_labour_contract`, whose humanist gates
  are unreachable today;
- centre: the chancery slots, the majority tools, the final;
- centre-left and centre-right: the operations against each Judas and the
  consequences of his death;
- right branch: readiness, the drill, arms and the fleet.

`NAM_board_partition_night` needs a majority. Its reward divides the mainland
in advance: in order of votes each company is assigned the districts it will
hold after the return, replacing the round-robin of `NAM_corp_assign_district`
for those districts.

### Lower branch (stage 2)

Opens after `NAM_board_partition_night` in the same tree and in the same
source file, as its own commented section: AGENTS.md forbids splitting a
coherent tree into files. Its entry focuses have no prerequisite and are gated
by `allow_branch` on a flag that the final sets; a hidden event one hour later
calls `mark_focus_tree_layout_dirty`. The layout inspector must learn
`allow_branch`. The layout mirrors the upper tree's symmetry and the spacing
rules (a free cell between neighbours, no straight chain longer than two).
Outline in appendix D:

- letters of marque turn into landings: LUR, ULV and CHD, each a separate
  scripted war with its own participants, major-status cleanup and settlement;
- marines, army rearmament, industrial rearmament;
- the 99 to 1 society;
- the return to the mainland through `NAM_war_of_return_start`.

Seized island states become company concessions: a state variable names the
owning company, and the recount counts 2 votes per concession beside the
districts. They are not subject countries.

Temporary exception to the focus-tree rules: the Judas branches have no live
exclusive pair while the two WIP focuses are closed. A test pins the exception
so it is removed with them.

### After the return (stage 3)

A separate tree for the corporate winner, loaded in the victory path of the
return war. Out of scope here; it needs its own document.

## Tests and tools this design breaks

- `tools/tests/test_adiscord_nam_focus.py`: the cabinet list and slot mapping
  and the single monthly recount (around 9031-9078, 9456-9475); the opening
  votes and rank; the board layout pins (around 16063-16250); the category
  that holds exactly three decisions (around 15193-15227); the tree pins of 70
  focuses, one leaf and the plan ending on the final (around 8763-8874).
- `tools/tests/test_adiscord_party_representation.py`: the succession outcomes
  (around 437-493).
- `tools/validators/validate_adiscord_nam_resource_war.py`: the takeover order.
- `tools/validators/inspect_nam_corporate_focus_layout.py`: rejects
  `allow_branch` and reads one source file.
- `common/scripted_effects/ADISCORD_debug_idea_catalogue.txt` is generated by
  `tools/builders/build_adiscord_idea_reset.py`: regenerate after adding ideas.
- `tools/data/adiscord_event_ids.json`: register new events; take ids with a
  gap above the current maximum.
- `docs/development/focus-effects.md`, section "Корпоративное изгнание NAM":
  rewrite to the new contract.

Update each pin to the new contract; do not delete a test to make it pass.

## Work packages

The NAM effects, triggers, decisions, events, ideas, scripted localisation and
localisation files are single hubs: one owner at a time. Packages therefore
run strictly in order, one agent at a time. Each package includes its Russian
and English text and updates the test pins and validator contracts that it
changes, so the suite is green between packages. The lead runs the `--apply`
builders, the full suite and `validate_tc.py` between them and reviews the
diff.

| # | Package | Main files |
| --- | --- | --- |
| 1 | Cabinet and people: 18 company minister ideas and 4 officials, six label traits, six heads with leader roles, `NAM_board_install_chairman`, `NAM_board_chairman_rules`, takeover order and the silencing of seat callbacks, rename of the state | ideas, characters, minister traits, effects, triggers, portraits gfx, localisation |
| 2 | Trust, stance, votes, recount, majority, blocked products, no confidence, status texts | effects, triggers, dynamic modifiers, on_actions, decisions, events, scripted localisation |
| 3 | Tenders, sessions, resolutions, sanctions, chancery | decisions, events, effects, triggers, ideas |
| 4 | The Two Judases | decisions, events, effects, ideas, scripted localisation |
| 5 | Annual meeting, signature decisions, AI policy, debug decisions for a session, a vote and a meeting | decisions, events, effects, AI plans, debug decisions |
| 6 | Pyramid window | basin gui and gfx, scripted GUI, scripted localisation |
| 7 | Rewards of the upper tree | focus source |
| 8 | Focus-effects guide section and a final pass over stale texts | docs, localisation |

Package 1 comes first because package 2 counts seats and installs chairmen.

Status: package 1 was implemented on 2026-11-20. It added
`NAM_board_support_change` (absolute mode through the country variable
`NAM_board_set_input`, which the effect clears), `NAM_board_minister_seated`,
`NAM_board_minister_unseated`, `NAM_board_install_chairman`,
`NAM_board_chairman_rules`, the arrays `NAM_board_support` and
`NAM_board_seat_count`, the variable `NAM_board_chair` and the flags
`NAM_board_opened` and `NAM_board_silence_seats`. Later packages build on
these names.

Status: package 2 was implemented on 2026-11-20. It added the stance, rest,
forecast and vote variables of M1, `NAM_board_has_majority`,
`NAM_board_majority_held`, `NAM_board_product_blocked_1..6`, the mission
`NAM_board_no_confidence` with `NAM_board_arm_no_confidence`,
`NAM_board_check_no_confidence` and `NAM_board_settle_no_confidence`, the
spirit `NAM_board_no_confidence_spirit`, events
`ADISCORD_nam_resource_war.420-.422`, the flags `NAM_board_recount_queued`
and `NAM_board_no_confidence_immunity`, and the optional input
`NAM_board_no_bonus_input` of `NAM_board_install_chairman`.

Status: package 3 was implemented on 2026-11-20. It added the tender
missions `NAM_board_bid_<lot>` with `NAM_board_award_<lot>_<company>` and
`NAM_board_keep_<lot>_public`, the session clock `NAM_board_session` with
events `ADISCORD_nam_resource_war.430-.437`, one resolution mission
`NAM_board_resolution_<company>` per company, the sanction spirits
`NAM_board_sanction_<company>`, the chancery (`NAM_board_action_slots`,
`NAM_board_action_used`, the company selection (now the six seat buttons), `NAM_board_lobby_company`,
`NAM_board_prepare_dismissal`) and `NAM_board_end_operations`, which the
future stage-3 tree loader must call. The Judas motions read
`NAM_judas_weber`, `NAM_judas_karamyshev` and `NAM_judas_last_op_weber` /
`NAM_judas_last_op_karamyshev` and cannot be tabled until those exist. The
operation dates are day numbers: two writes on one day cannot be told apart,
so a resolution adopted on day D counts an operation as a breach only when
its date is greater than D.

Status: the interregnum (M0) and package 4 were implemented on 2026-11-20.
M0 added `NAM_interregnum_begin`, `NAM_interregnum_close`,
`NAM_corp_seed_capital`, the tree `NAM_exile_interregnum_focus`, the mission
`NAM_interregnum_islands`, the spirit `NAM_interregnum_power_vacuum` and
event `ADISCORD_nam_resource_war.460`. Package 4 added the support variables,
`NAM_judas_support_change`, the meeting missions
`NAM_judas_<camp>_meeting` with events `.450-.454`, ten operations
`NAM_judas_<operation>`, fifteen spirits, the banded killings and the report
panel `ADISCORD_NAM_judas_panel`. It leaves `NAM_judas_dividend_surcharge`
for the annual dividend to consume and clear. Under the tree's exclusive
pairs nine of the ten operations are reachable in one campaign; that is
intended.

Notes for every package:

- The user and Codex edit the corporate tree, the ideas and the localisation
  at the same time. Re-read a block right before changing it and insert by
  section. Never reformat or reorder what you did not write.
- Teammates never commit, never run `--apply` builders and never run the full
  suite. Each reports the files it changed and the focused checks it ran.
- Generated or registered outputs: the debug idea catalogue (regenerate
  through `tools/builders/build_adiscord_idea_reset.py` after adding ideas or
  characters; lead only); the traits localisation has an Ainholm-generated
  block, write outside it; event plates go into the hand-authored
  `interface/ADISCORD_eventpictures.gfx` at 507x184, opaque.
- Register every mission id read through `days_mission_timeout@ID` in
  `common/synchronized_dynamic_tokens/ADISCORD_tokens.txt`, every new event in
  `tools/data/adiscord_event_ids.json` (ids with a gap above the current
  maximum), and every paid decision in `CUSTOM_COST_DECISIONS` of the NAM
  validator.
- No new decision category: a test allows exactly two under the takeover.

## Review findings to fix (packages 1-3)

Confirmed by an independent review on 2026-11-20. Fix them in the next script
package; none is covered by a test yet, so add one for each.

1. A speaker whose agenda is empty is still seated and then "rejected": it
   loses trust and gets a sanction for a motion it never made. In
   `NAM_board_close_session`, `NAM_board_adopt_first` and
   `NAM_board_adopt_second`, call `NAM_board_reject_motion` for a slot only
   when its `NAM_board_offer_motion_N` is above 0. In `NAM_board_pick_speaker`
   a company with an empty agenda speaks only when nobody else can; read the
   agendas at the start of `NAM_board_arm_session`.
2. `NAM_board_end_operations` does not end the vote of no confidence or the
   majority bonus. After setting `NAM_board_ended`, it must remove the mission
   `NAM_board_no_confidence`, set `NAM_board_no_confidence_day` to -1, clear
   `NAM_board_no_confidence_immunity` and `NAM_board_recount_queued`, call
   `NAM_board_recount` (with the council inoperable it zeroes the majority
   values) and `NAM_corp_refresh`. The annexation handler then drops the
   lines it duplicates. Each `NAM_board_product_blocked_<n>` is false once
   `NAM_board_ended` is 1. Event `.422` also requires `NAM_board_ended = 0`.
   Do not reset the stance array or clear `NAM_board_opened`.
3. A company that lost a tender must beat both speaker exclusions for 180
   days (M3, M4). Today a loser that spoke at the previous session is passed
   over.
4. Lobbying whose gain is clamped to zero at completion (the target passed
   65 meanwhile) refunds the price and applies neither the rival's -5 nor the
   120-day lockout.
5. `NAM_board_adopt_both` calls `NAM_board_recount` directly, as M1 requires.
6. `NAM_board_withdraw_question` shows the raw variable `NAM_board_deferred`
   in its condition: wrap it in a localised custom trigger tooltip.

## Verification

Static: the focused tests of each package, then
`python -B -m tools.builders.build_adiscord_focus_trees --check`,
`python -B tools/validate_tc.py --limit 300` and `git diff --check`.

Runtime, by the user after a full restart, none of it provable statically:

- the company trait shows on a minister and the seat changes trust once;
- a session offers the two announced speakers and the rejected one answers;
- a tender ends by the player's decision and by timeout;
- a boycott countdown, a vote of no confidence that passes and one that fails;
- the leader portrait and trait change at the annual meeting, and the
  hedonism party representative never becomes leader;
- both killings at each of the three support bands;
- the pyramid buttons, stance frames and the council line.

## Appendices

Appendices A, B, D and E were drafted against an earlier version of the core.
Where they differ, sections M1-M10 win. Known differences:

- A.6 (leader traits) is replaced by the table in M6, which adds the debuffs.
- A.7 point 1: a public lot already has a bonus in
  `NAM_board_update_industrial_policy`; do not add capital income for it.
- A.0: one resolution mission per company (six ids) is accepted; at most two
  run at once.
- Any mention of nominating a chairman is void: the chair goes strictly to the
  head of the top company (user decision 11).
- B.6 offsets are accepted: the port committees first meet on day 30, the
  officers on day 75, the first session is on day 60, the first annual meeting
  on day 330 and then every 360 days; no meeting starts within 7 days of a
  session or of the annual meeting; sessions come every 45 days once both
  rivals are dead.
- B.7 fixes are accepted: `NAM_board_elected_in_absentia` is re-parented to
  `NAM_board_founders_of_unrest` and `NAM_board_inheritance_without_empire` to
  `NAM_board_dead_mans_veto`, so operations open while the man lives; the
  drill unlocks with `NAM_board_dead_mans_veto`; the killing tooltip states
  the band "at completion".
- The ten event plates exist and are registered in
  `interface/ADISCORD_event_art.gfx` under these names, which replace the
  names proposed in appendix E: `GFX_event_adiscord_nam_loren_oil`,
  `_nam_ferrant_steel`, `_nam_navis_shipping`, `_nam_arktur_arsenal`,
  `_nam_smenkom_exchange`, `_nam_reidbank_credit`, `_nam_board_session`,
  `_nam_chair_handover`, `_nam_weber_committees`, `_nam_karamyshev_officers`.
- Art that exists and may be referenced by any package:
  - text icons, written as `£<name>` after the number:
    `NAM_board_trust_texticon`, `NAM_board_slot_texticon`,
    `NAM_judas_committees_texticon`, `NAM_judas_officers_texticon`,
    `NAM_board_stance_texticon|N` (1 for, 2 waiting, 3 countdown, 4 boycott),
    beside the older `NAM_board_votes_texticon`, `NAM_board_mark_texticon|N`,
    `NAM_foreign_capital_texticon` and `NAM_return_readiness_texticon`;
  - pyramid sprites `GFX_NAM_board_stance_marks` (4 frames, 28x28),
    `GFX_NAM_board_resolution_marker` (20x20) and `GFX_NAM_board_seat_select`
    (3 frames, cornered tile, border 6);
  - spirit pictures `GFX_idea_NAM_board_no_confidence`,
    `GFX_idea_NAM_board_sanction_<company>` for the six companies,
    `GFX_idea_NAM_judas_weber_committees`, `_karamyshev_watch`, `_strike`,
    `_mutiny`, `_port_peace`, `_staff_oath` and
    `GFX_idea_NAM_board_loan_service`. An idea's `picture` takes the name
    without the `GFX_idea_` prefix only if that is how the neighbouring NAM
    ideas reference theirs; check before use.
- Appendix A writes `NAM_corp_zone_slots`; the real variable is
  `NAM_free_zone_slots`.
- Appendix C assumes the premier's seat stays fixed until
  `NAM_board_privatise_governorate`. It does not: Kornev is removable from the
  start (M2). Ignore C.10 point 3 and any reward that "frees" that seat; give
  that focus another reward of the same weight.
- Appendix C is the starting table for package 7. It is re-checked against the
  focus source and the implemented ids of packages 1-6 before use, because the
  tree is being edited while this document is written.

## Appendix A. Company agendas, sanctions, tender terms, signature decisions, minister modifiers

Sources were read on 2026-11-20 with static reading only. Nothing was run. Ids not named in this appendix are new.

### A.0 Rules shared by every motion

- Each company has one resolution mission, `NAM_board_resolution_<company>` (loren, ferrant, navis, arktur, smenkom, reidbank). That makes six ids in `common/synchronized_dynamic_tokens/ADISCORD_tokens.txt`. The adopted motion number goes in the array `NAM_board_motion^<id>`.
- The motion's cost spirit or deposit is applied when it is adopted. On success the company gains +15 and the result is applied. On failure or cancellation the company loses 20, its sanction (A.2) is applied, and any deposit comes back only if the company is not boycotting.
- **Seat** (120 days). The goal is `has_idea` of the named minister. The player pays the native 75 political power, and the displaced company loses 15 (M1).
- **Dismissal** (90 days). It can be tabled only while the named minister sits. The goal is that he is no longer in the cabinet. The player pays 75 political power for a successor, and the minister's company loses 15. A prepared dismissal (M5) cuts that loss to 5.
- **Industry** (90 days). It can be tabled while the lot is public and no tender is running. The goal is to use the award decision. The company pays its tender terms (A.3), and the other bidder loses 15.
- **Order** (120 days). A deposit uses the `NAM_corp_innovation_park` escrow. The goods arrive 60 days after payment, and the mission succeeds on delivery.
- **Privilege** (150 days). A cost spirit is added with `add_timed_idea` for 150 days. The goal is to keep it for 120 days. The revoke decision ends the motion as a failure.
- **Stand against a Judas** (150 days). The camp's support is stored at adoption. The goal is to push it 15 below that value.
- **Stand: leave him alone** (120 days). The mission is timeout-only, and its timeout is the success branch. The `cancel_trigger` fails the motion if the council runs a chancery operation against him or picks the "force" answer at his meeting. The operation records its date in `NAM_judas_last_op_<name>`, so no flag is needed.
- If a building's state has lost its free slot by delivery, the result pays 60 capital instead.

### A.1 Agendas (tabled in this order: the first motion that can be tabled and is not yet fulfilled)

**Loren (oil).** It stands against Weber, because the port committees strike the oil quay.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Склады - под крышу Лорэн" | industry | depots lot public | - | Loren's terms | Reidbank |
| 2 | "Причалы без комитетов" | against Weber | Weber alive, support 40 or more | chancery operations | +1 `fuel_silo` in the capital state | Smenkom |
| 3 | "Топливо для флота возвращения" | order | fuel stock below half of the maximum | 50 capital deposit | 20000 fuel | Navis |
| 4 | "Рахманов - в премьеры" | seat | Корнев or Крамской is premier | as A.0 | +1 `synthetic_refinery` on the capital island | Reidbank |
| 5 | "Убрать Белова" | dismissal | Белов sits | as A.0 | spirit `NAM_board_loren_order_fee`, 120 days, stability +3% | Reidbank |

**Ferrant (steel).** It leaves Karamyshev alone, because the officers' rearmament buys its plate.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Вагонные мастерские без торгов" | industry | rail lot public, or Smenkom holds it while not for the council | 50 political power by decree; if Smenkom holds the lot it loses it, -15 | Ferrant's terms | Smenkom |
| 2 | "Сталь для верфей - только через Ферран" | privilege | yards lot sold; Ferrant holds a seat or an industry | spirit `NAM_board_ferrant_steel_monopoly`: dockyard output -10% | +1 `dockyard` on an island chosen from 225-231 | yards owner |
| 3 | "Бронелист для береговой охраны" | leave Karamyshev alone | Karamyshev alive; Ferrant not boycotting | 60 capital deposit | at timeout: 24 `ADISCORD_armored_carrier_2163` and 4 `armored_train_equipment_1` | Navis |
| 4 | "Бронников - в оборону" | seat | Селиванов, Ветлугин or Баталов holds defence | as A.0 | +1 `coastal_bunker` in 3 coastal provinces of the capital state | Arktur |
| 5 | "Убрать Литвинова" | dismissal | Литвинов sits | as A.0 | spirit `NAM_board_ferrant_shift`, 120 days, factory efficiency growth +10% | Smenkom |

The armour-plate order travels inside motion 3. Ferrant's stand on Karamyshev is that order: the council leaves the officers alone and arms them through Ferrant.

**Navis (shipping).** It stands against Karamyshev, because the coast guard searches its hulls.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Верфи - Навису" | industry | yards lot public | - | Navis's terms | Arktur |
| 2 | "Фарватер без досмотров" | against Karamyshev | Karamyshev alive, support 40 or more | chancery operations | spirit `NAM_board_navis_free_fairway`, 180 days: convoy escort efficiency +20%, naval speed +5% | Ferrant |
| 3 | "Конвойный заказ" | order | fewer than 40 convoys in stock | 45 capital deposit | 10 `convoy_1` and one `ADISCORD_coastal_patrol_ship` (`create_ship`) | Ferrant |
| 4 | "Чайкина - в разведку" | seat | Булатов or Зарубин holds intelligence | as A.0 | +1 `naval_base` in the capital island's port | Arktur |
| 5 | "Убрать Ветлугина" | dismissal | Ветлугин sits | as A.0 | 30 capital and 4 `convoy_1` | Arktur |

**Arktur (arsenal).** It stands against Weber, because the committees control the foundry floor.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Верфи - Арктуру" | industry | yards lot public | - | Arktur's terms | Navis |
| 2 | "Ветлугин - в оборону" | seat | Селиванов, Бронников or Баталов holds defence | as A.0 | 3000 `infantry_equipment` | Ferrant |
| 3 | "Литейный двор без комитетов" | against Weber | Weber alive, support 40 or more | chancery operations | +1 `arms_factory` on the capital island | Smenkom |
| 4 | "Казённое оружие - только у Арктура" | privilege | Arktur holds a seat or the yards | `NAM_corp_buy_arms` closed, plus spirit `NAM_board_arktur_arms_monopoly`: consumer goods +3% | spirit `NAM_board_arktur_line`, 180 days: maximum factory efficiency +10%, equipment conversion speed +25% | Reidbank |
| 5 | "Убрать Ордынцева" | dismissal | Ордынцев sits | as A.0 | 36 `artillery_equipment` | Navis |

**Smenkom (labour exchange).** It leaves Weber alone and wants the committee men on its rolls.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Мастерские - бирже" | industry | rail lot public | - | Smenkom's terms | Ferrant |
| 2 | "Комитеты - на биржу, не на виселицу" | leave Weber alone | Weber alive | none | at timeout: 3000 manpower, Weber's support -10 | Loren, Arktur |
| 3 | "Одинцова - в здравоохранение" | seat | Вересов or Савицкая holds health | as A.0 | +1 `infrastructure` on two islands chosen from 225-231 | Reidbank |
| 4 | "Закрытый цех" | privilege | Smenkom holds a seat | spirit `NAM_board_smenkom_closed_shop`: recruitable population -5% | spirit `NAM_board_smenkom_brigades`, 180 days: construction speed +15% | Ferrant |
| 5 | "Убрать Ермолина" | dismissal | Ермолин sits | as A.0 | `NAM_revenge_readiness` +10 | Ferrant |

**Reidbank (bank).** It stands against Karamyshev and buys up the officers' debts.

| # | Motion | Kind | Tabled when | Price | Result | Hurts |
|---|---|---|---|---|---|---|
| 1 | "Склады - в залог Рейдбанку" | industry | depots lot public | - | Reidbank's terms | Loren |
| 2 | "Расчётная палата Рейдбанка" | privilege | not boycotting; zone slots below 3 | spirit `NAM_board_reidbank_clearing`: zone income -10 capital a month (read by the income effect) | `NAM_corp_zone_slots` +1, maximum 3 | Navis |
| 3 | "Крамской - в премьеры" | seat | Корнев or Рахманов is premier | as A.0 | 60 capital | Loren |
| 4 | "Убрать Рахманова" | dismissal | Рахманов sits | as A.0 | 50 capital | Loren |
| 5 | "Выкупить офицерские векселя" | against Karamyshev | Karamyshev alive, support 40 or more | chancery operations | spirit `NAM_board_reidbank_bills`, 180 days: stability +5% | Ferrant |

Each company's dismissal target is a minister of its tender rival: Loren and Reidbank, Ferrant and Smenkom, Navis and Arktur. The M4 rule "the loser's next motion turns against the winner" therefore takes the dismissal motion, or the seat motion while the target is not seated.

### A.2 Sanctions: 60-day spirits added with `add_timed_idea`

| Company | Spirit | Effect | Blocks |
|---|---|---|---|
| Loren | "Лорэн перекрывает вентиль" | fuel gain -50%, maximum fuel -30% | - |
| Ferrant | "Ферран вывозит сталь" | the existing state dynamic modifier `NAM_corp_steel_export_state` (-8 steel) for 60 days on every `NAM_corp_steel_site`; dockyard output -10% | `NAM_corp_sell_steel` |
| Navis | "Каботаж на приколе" | 8 `convoy_1` withdrawn, held in `NAM_board_navis_withheld` and returned in `on_remove` | `NAM_island_requisition_transports` |
| Arktur | "Арсенал на замке" | military factory output -10% | `NAM_corp_buy_arms` |
| Smenkom | "Биржа отзывает бригады" | construction speed -25%, monthly population -20% | `NAM_corp_labour_contract` |
| Reidbank | "Рейдбанк закрывает кредит" | monthly capital income halved | - |

Reidbank's income cut is read by `has_idea` in the income formula, the same way as `NAM_board_reidbank_clearing`. Every sanction is a visible spirit with its own end date, so the player can stock fuel, delay building or pay ahead.

### A.3 Tender terms

Income is 50 capital a month per zone, and the exile has one zone, so 80 capital is about 1.6 months of income. In every lot the company that already holds an industry is the incumbent.

| Lot | Incumbent offers | Newcomer offers |
|---|---|---|
| Rail workshops | Smenkom: 80 capital | Ferrant: 40 capital, 2 `armored_train_equipment_1` |
| Shipyards | Navis: 80 capital | Arktur: 40 capital, 2000 `infantry_equipment`, 24 `artillery_equipment` |
| Fuel depots | Loren: 80 capital | Reidbank: 40 capital and 3 monthly payments of 15 capital |

Payments still owed are withheld while the company boycotts (M1).

### A.4 Signature decisions (visible while that head chairs)

| Head | id | Title | Price | Duration | Result | Repeat |
|---|---|---|---|---|---|---|
| Вяземцев | `NAM_board_sig_oil_advance` | "Аванс под будущую нефть" | 25 political power | instant | +120 capital and 10000 fuel now. After `NAM_war_of_return_won`, spirit `NAM_board_loren_lien` lasts 180 days per advance: fuel gain -40%. No repayment if the return never comes. | 2 per campaign |
| Вальц | `NAM_board_sig_trust_plan` | "Трестовый план" | 90 capital + 20 political power (escrow) | 120 days | Targets an island of 225-231 with a free slot: +1 `arms_factory`, slot checked again at delivery or the price refunded | every 180 days, 2 per chairmanship |
| Крузе | `NAM_board_sig_letters_of_marque` | "Каперские свидетельства" | 40 political power + 30 capital | 180 days (timed flag `NAM_board_letters_of_marque`) | Opens the strait (ULV, LUR) and crossing (CHD) lanes; `NAM_pirate_raid_slots` at least 1; loot goes to capital | renewable after it expires |
| Калёнов | `NAM_board_sig_out_of_turn` | "Заказ вне очереди" | 70 capital + 25 political power | 45 days | 3000 `infantry_equipment`, 36 `artillery_equipment`, and the locked division "Arktur Guard" (6 infantry, artillery support) at the capital | once per chairmanship |
| Гурьев | `NAM_board_sig_contract_recruitment` | "Контрактный набор" | 30 political power + 30 capital | 60 days | +5000 manpower; Weber's support +5 while he lives | every 120 days, 3 per chairmanship |
| Вельяминова | `NAM_board_sig_consolidated_loan` | "Консолидированный заём" | 20 political power | instant | +200 capital. Spirit `NAM_board_loan_service`, 360 days: -20 capital a month through the income effect, 240 in total | not while the spirit runs |

Why each differs in kind:

- Loren's advance is debt against land the council does not yet hold, repaid in oil after the war.
- Reidbank's loan is cash now, paid out of current income with interest.
- Ferrant's plan leaves a permanent building.
- Navis's letters open a system of repeated raids with notoriety and the victims' protests.
- Arktur's order gives a standing formation.
- Smenkom's contracts give manpower and pay for it in Weber's strength.

Repayment spirits and builds already in progress outlive the chair. Do not put `has_country_leader` in their `cancel_trigger`.

**Gates for the letters of marque.** Leave `NAM_piracy_open` (triggers:2458) unchanged. It also opens `NAM_order_marines` and the black-market decisions (`NAM_pirate_buy_arms`, `_buy_heavy_arms`, `_buy_convoys`, `_fence_loot`, decisions:20206-20472), which spend loot and stay with the radical route.

1. `NAM_pirate_commissioned` (triggers:2465): add the branch "takeover flag, `NAM_board_letters_of_marque` and NOT `NAM_war_of_return_won`".
2. Category `NAM_piracy` (categories:14-24): its `visible` is `NOT takeover AND NAM_piracy_open`. OR it with `NAM_pirate_commissioned = yes`.
3. `NAM_pirate_raid_lane_oil` (decisions:19760) and `_coast` (decisions:19872): add `NOT = { has_country_flag = NAM_corp_takeover }` to `visible`. They hit EFL, AZH and RIV, the targets of the return war.
4. The crossing lane also lists RIV (triggers:2514-2519, effects:10043-10060). Under the takeover, skip RIV in `NAM_pirate_lane_crossing_open` and `NAM_pirate_save_lane_victims`.
5. `NAM_pirate_raid_slots` is written only by radical focuses (`focus_trees/NAM/exile_radical/focuses.txt`:1894, 1942, 1981), so it is unset, that is 0, under the boards. The decision sets it to at least 1, clamped to 3.
6. `NAM_pirate_loot_add` (effects:9944): loot is turned into capital only once, at the takeover (effects:8357-8362). Under the takeover, send `NAM_pirate_loot_change` to `NAM_corp_capital_add`.
7. `NAM_pirate_monthly` (effects:10283) needs `NAM_piracy_open`, so notoriety would never fade. Gate it with `NAM_pirate_commissioned`. Retaliation events .92/.93 still need EFL or AZH to exist. Keep that as policing of the seas or gate it, but decide explicitly.
8. `ADISCORD_NAM_piracy_panel` (scripted_guis:256-645): switch the lane and fleet elements to `NAM_pirate_commissioned`. The revenge, marine and coalition rows (654-723) stay radical.
9. When the letters expire, the lanes' existing `cancel_trigger` (`NAM_pirate_commissioned = no`) refunds the fuel of raids at sea through `NAM_pirate_raid_release`. No new handler is needed.

### A.5 Minister working modifiers (22)

Existing modifiers are kept. The board twins of Нартов, Ермолин and Ветлугин copy their old trait values into `modifier`.

| Seat | Minister | Modifier |
|---|---|---|
| Premier | Корнев | political power +0.05 a day (existing) |
| | Рахманов (Loren) | stability +4%, fuel gain +15% |
| | Крамской (Reidbank) | consumer goods -3% |
| Defence | Селиванов | planning speed +5% (existing) |
| | Ветлугин (Arktur) | reinforce rate +2%, organisation +3%, stability -3% (existing) |
| | Бронников (Ferrant) | armour attack +5%, armour defence +5% |
| | Баталов (Navis) | `amphibious_invasion` +15%, `naval_invasion_prep_speed` +15% |
| Economy | Нартов (Loren) | civilian factory construction +4%, compliance growth +3%, military factory output -2% (existing) |
| | Белов (Reidbank) | resource shortage penalty -15% |
| | Ставрова (Ferrant) | factory efficiency growth +5%, line change efficiency +10% |
| Health | Вересов | casualty trickleback +4% (existing) |
| | Одинцова (Smenkom) | monthly population +5% |
| | Савицкая (Reidbank) | stability +3%, war support -2% |
| Education | Ермолин (Ferrant) | research +2%, compliance growth +2%, stability -2% (existing) |
| | Литвинов (Smenkom) | training time -10% |
| | Бахметьев (Arktur) | army experience gain +10% |
| Intelligence | Булатов | army intel +4% (existing) |
| | Зарубин (Arktur) | resistance suppression +15%, `enemy_operative_detection_chance_factor` +15% |
| | Чайкина (Navis) | navy intel +10%, naval detection +10% |
| Foreign | Ордынцев (Navis) | political power +0.05 a day, admin expense +2.5% (existing) |
| | Дашков (Loren) | trade opinion +25% |
| | Ильдаров (Smenkom) | recruitable population +3%, ideology drift defence +15% |

### A.6 Leader traits of the six heads

| Head | Trait | Modifiers |
|---|---|---|
| Вяземцев | "Нефтяной патриарх" | fuel gain +20%, maximum fuel +25% |
| Вальц | "Хозяйка стального треста" | military factory output +5%, maximum factory efficiency +5% |
| Крузе | "Король фрахта" | dockyard output +10%, convoy retreat speed +20% |
| Калёнов | "Порядок прежде прибыли" | war support +10%, core defence +5% |
| Гурьев | "Распорядитель биржи" | monthly population +10%, construction speed +5% |
| Вельяминова | "Держательница векселей" | political power +0.10 a day, `ADISCORD_economy_admin_expense_factor` -5% |

Олшанский's existing trait gives efficiency growth, so Вальц was given output instead.

### A.7 Contradictions found in M2-M6, with fixes

1. **M4 "the lot's state bonus stays".** No public-lot bonus exists: index 0 of the weights is always 0 (effects:9139). Fix: each public lot gives +10 capital a month, read in the income effect, so keeping a lot public is a real option.
2. **M3 speakers versus M4 losers.** A company needs a vote or a seat to speak. Ferrant, Arktur or Reidbank after a lost tender has neither, so the M4 rule "its next motion turns against the winner" can never be tabled. Fix: a company that lost a tender in the last 180 days is also a candidate.
3. **M1 resting level.** A company with no industry and no seat rests at 45, above a seat-less company with an industry (35). But it can never speak (point 2), so the higher level only makes it harmless. Fix: keep 45, and state that it applies only outside the 180-day window of a lost tender.
4. **M3 "leave him alone" stands.** These invert the mission contract: the timeout is the success and the violation is a `cancel_trigger`. The spec should say so, and the success results go in `timeout_effect`.
5. **Sanctions and boycott block the same decisions.** Define them once: the boycott check and the sanction spirit both feed one trigger per product, `NAM_board_product_blocked_<n>`.
6. **M6 "exists only while he chairs".** Repayments and builds in progress must outlive the chair (A.4). Only `visible` reads the chair.
7. **M10 versus A.1.** The left branch re-gates `NAM_corp_labour_contract` and zones, and Reidbank motion 2 also raises zone slots. That is compatible through the 1-3 clamp (effects:8344-8356). Smenkom's privilege deliberately does not unlock the labour contract, so the focus keeps that decision.
8. **M2.** No idea may hold two traits, so the twins of Нартов, Ермолин and Ветлугин carry only the company label trait. Their old values move into `modifier` (A.5).
9. **M6 letters of marque.** "Against ULV, LUR and CHD" only holds after gates 3-4 of A.4. Without them the existing lanes also hit RIV, EFL and AZH.

None of this was checked in the running game. Exact modifier keys were checked against the vanilla `documentation/modifiers_documentation.md` except the mod-defined `ADISCORD_economy_admin_expense_factor`, which is already used on Ордынцев. Plain-language rows map to the existing ids already in use (`fuel_gain_factor`, `industrial_capacity_factory`, `production_speed_buildings_factor` and so on). The building types are in `common/buildings/00_buildings.txt`.

## Appendix B

### B0. Common rules

- Support values: `NAM_judas_weber` (port committees) and `NAM_judas_karamyshev` (coast guard officers). Every change goes through one effect, `NAM_judas_support_change`, with the inputs `NAM_judas_camp_input` (1 Weber, 2 Karamyshev) and `NAM_judas_delta_input`. It clamps the value to 0-100 and refreshes the category text. Company trust moves only through `NAM_board_support_change` (M1).
- The bands below are read when the killing focus completes, not when it is selected. The focus tooltip shows the band at the current support and warns that a running operation, or the monthly +2 growth, can move the value across a band during the 21 days of the focus.
- A "willing company" for a force answer is a company with trust 50 or more that is not counting down to a boycott and is not boycotting. If none qualifies, the answer shows greyed out with that reason.
- New events, timed ideas and the mission ids go into the existing NAM hubs: events, decisions, ideas, `ADISCORD_tokens.txt` and `adiscord_event_ids.json`.

### B1. Meetings

**Port committees: "Собрание портовых комитетов"**

The meeting runs as the visible mission `NAM_judas_weber_meeting`.
- Interval: 50 days, or 40 at support of 60 or more. The clock pauses below 20.
- Target: the company the council favoured last, meaning the last tender winner or the beneficiary of the last resolution. The target is stored in `NAM_judas_weber_target`.
- If that company holds no industry, the target falls back to the non-boycotting company with the most industry votes, lower id on a tie.
- The target follows the player's actions until 14 days before the meeting, then locks. Until then the player can redirect it by favouring another company.
- How the player sees it: the category text names the target and the reason ("Комитеты идут на причалы Навис: Навис выиграла торги"). The target's pyramid card carries a marker, and the council line warns at 14 days.

| Answer | Price | Camp | Trust | Economy / army |
| --- | --- | --- | --- | --- |
| "Уступить комитетам" | 40 capital | Weber +10 | target -5, Smenkom -5 (the committees keep their hiring hall) | none beyond the capital |
| "Разогнать комитеты" (needs a willing company: the target or Arktur) | timed idea `NAM_judas_port_arrests` "Аресты в порту", 60 days: stability -5%, political power gain -0.10 | Weber -8 | the company that lends men +5, Smenkom +5 | none beyond the idea |
| "Не вмешиваться" | timed idea `NAM_judas_dock_walkout` "Стачка на причалах", 60 days. While it lasts, `NAM_board_update_industrial_policy` reads the idea and the target variable and sets the target company's profile level to 0 | Weber +5 | target -10 | that company's profile is lost for 60 days |

If nobody answers, the event takes "Не вмешиваться".

**Officers' assembly: "Офицерское собрание"**

The meeting runs as the visible mission `NAM_judas_karamyshev_meeting`.
- Interval: 60 days, or 45 at support of 60 or more. The clock pauses below 20.
- Target: the preparation the player raised last, stored in `NAM_judas_karamyshev_target`. The default is readiness.
  - 1 readiness: set by the drill.
  - 2 convoys: set by requisitioning transports or a Navis consignment.
  - 3 army equipment: set by buying arms, an Arktur consignment, or recruiting guards.
- Visibility is the same as for Weber: category text with the reason, and a warning at 14 days.

| Answer | Price | Camp | Trust | Economy / army |
| --- | --- | --- | --- | --- |
| "Удовлетворить требования" | 35 capital | Karamyshev +10 | Arktur -5 (money taken from arms orders), Reidbank -3 | none beyond the capital |
| "Арестовать зачинщиков" (needs a willing company: Navis crews or the Arktur guard) | readiness -8 | Karamyshev -8 | the company that lends men +5 | readiness -8 |
| "Не вмешиваться" | loses the target: (1) readiness -10 and `NAM_exile_drill` blocked for 60 days; (2) 4 convoys withdrawn and returned by a delayed event 90 days later; (3) timed idea `NAM_judas_drill_boycott` "Офицеры саботируют учения", 60 days: army organisation -10%, training time +20% | Karamyshev +5 | Navis -8 (convoys) or Arktur -8 (equipment); no change for readiness | as listed |

If nobody answers, the event takes "Не вмешиваться".

### B2. Operations

All operations are chancery operations in `NAM_two_judases`. Each takes one slot (M5) and stores its camp. The slot is released on completion, cancellation and removal. A cancelled operation refunds its capital and gives no support change. Each operation can be run once. While a "leave him alone" resolution against that camp is running (M3), the camp's operations are unavailable and show a localised reason.

Several unlocking focuses currently sit below the killing focus. B7.1 explains this and gives the re-parenting that makes them reachable while the man lives.

**Against Weber (centre-right)**

| # | Operation | Kind | Unlocked by | Price, duration | Support | Trust | Side cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| W1 | "Скупить векселя комитетов" | buying debts | `NAM_board_founders_of_unrest` | 40 capital + 15 political power, 30 days | -12 | Reidbank +8 (the paper sits on its books), Loren -4 (it held committee notes at a discount) | the next committee meeting comes 10 days earlier |
| W2 | "Отменить заочные мандаты" | law | `NAM_board_elected_in_absentia` | 25 political power, 21 days | -10 | Loren +5, Navis -5 (its captains hold committee proxies) | timed idea `NAM_judas_unseated_proxies` "Лишённые мандатов", 90 days: political power gain -0.10 |
| W3 | "Наём через биржу" | changing who hires | `NAM_board_widows_share` | 20 political power + 1500 manpower lent as dock crews (returned at completion or cancellation), 45 days | -12 | Smenkom +12, Navis -6 (committee foremen leave its quays) | the manpower is locked for 45 days |
| W4 | "Умеренные на жалованье" | bribing moderates | `NAM_board_subsidised_opposition` | 50 capital, 60 days | -10 | Reidbank -6 (its credit line pays the stipends), Navis +6 (moderate crews return) | humanism popularity +5 |
| W5 | "Разогнать траурный митинг" (needs a willing Arktur) | force | `NAM_board_mourning_licence` | 20 political power, 14 days | -15 | Arktur +8, Smenkom -8 (exchange workers were in the crowd) | timed idea `NAM_judas_embankment_blood` "Кровь на набережной", 60 days: stability -8% |

**Against Karamyshev (centre-left)**

| # | Operation | Kind | Unlocked by | Price, duration | Support | Trust | Side cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| K1 | "Перерегистрация патентов" | law | `NAM_board_dead_mans_veto` | 30 political power, 30 days | -10 | Arktur +5, Navis -5 (its masters sail on old-seal patents) | readiness -5 (officers struck off the rolls) |
| K2 | "Командиры по патенту правлений" | changing who hires | `NAM_board_inheritance_without_empire` | 25 political power + 30 capital, 45 days | -12 | Navis +10 (its people command the cutters), Arktur -6 | 2 convoys pass into Navis service for good |
| K3 | "Выкупить офицерские закладные" | buying debts | `NAM_board_uncrested_buyers` | 45 capital, 30 days | -12 | Reidbank +8, Arktur -4 (the officers' arms credit is cancelled) | the next annual dividend costs 20 more |
| K4 | "Отступные капитанам" | bribing moderates | `NAM_board_district_buyout` | 25 political power + 30 command power, 45 days | -10 | Arktur +6 (the bought captains join its guard), Navis -4 | timed idea `NAM_judas_bought_captains` "Купленные капитаны", 90 days: army experience gain -15% |
| K5 | "Разоружить катера" (needs a willing Navis or Arktur) | force | `NAM_board_privatise_governorate` | 20 political power, 21 days | -15 | the company that lends men +6, Loren -5 (fuel barges held during the boarding) | readiness -8 and 800 manpower |

Arithmetic:
- Each camp loses 59 support to its five operations.
- Weber starting at 70 with +2 a month reaches about 90 by day 300. All five operations plus two force answers bring him to about 15.
- Karamyshev starting at 60 reaches about 80. All five operations plus one force answer bring him to about 13.
- A single concession (+10) costs roughly one operation's worth of progress.
- Every unlocking focus is in the AI plan. `NAM_board_price_of_silence` was not used for this reason.

### B3. What each man gives while alive

Each bonus is a plain national spirit added in `NAM_corp_takeover` and removed in his elimination effect, with a `has_idea` guard.

- Weber, idea `NAM_judas_weber_committees` "Портовые комитеты Вебера":
  - dockyard construction speed +5%;
  - +10 capital a month while his support is 30 or more. The consumer is `NAM_corp_monthly`, which reads the idea and the support, and the income line shows it.
  - If an earlier amnesty gave him a corps commander role, `retire_character` also takes that commander away.
- Karamyshev, idea `NAM_judas_karamyshev_watch` "Береговая стража Карамышева":
  - naval invasion preparation speed +10%;
  - +1 `NAM_revenge_readiness` a month while his support is 30 or more, with no gain from this source above 60. The consumer is `NAM_corp_monthly`.

Killing either man early therefore costs this income and readiness, as well as the worse band.

### B4. Killing outcomes

The existing rewards stay:
- `NAM_board_last_debtor` keeps its unlocks of `NAM_corp_buy_arms` and `NAM_island_recruit_warehouse_guards`.
- `NAM_board_posthumous_signature` keeps its unlock of `NAM_island_requisition_transports`.
- In the band of 60 or more, these decisions are blocked in `available` while the band's timed idea runs, so the unlock arrives once the idea ends.

**Weber**

- 60 or more: `NAM_judas_general_strike` "Всеобщая портовая забастовка", 90 days.
  - Zone income 0. The consumer is `NAM_corp_monthly`; with one zone this is about -150 capital.
  - Dockyard output -20%, stability -10%.
  - Humanism popularity +5.
- 30-59: `NAM_judas_dock_strike` "Портовая забастовка", 45 days.
  - Zone income halved, dockyard output -10%, stability -5%.
- Below 30: no penalty.
  - +2000 manpower at once (committee men join the labour exchange).
  - Humanism popularity -10 in favour of hedonism.
  - `NAM_judas_port_peace` "Портовый мир", 120 days: dockyard construction speed +10%, stability +5%.

**Karamyshev**

- 60 or more: `NAM_judas_coast_guard_mutiny` "Мятеж береговой охраны", 90 days.
  - -6 convoys and readiness -25.
  - One division is removed if NAM fields 3 or more; otherwise 1500 infantry equipment and 1000 manpower are lost.
  - While the idea lasts: army organisation -15%, naval invasion preparation speed -25%.
- 30-59: readiness -10.
  - `NAM_judas_officers_unrest` "Брожение в офицерском корпусе", 60 days: organisation recovery -15%, training time +15%.
- Below 30: readiness +15 and +25 army experience.
  - `NAM_judas_staff_oath` "Штаб присягнул совету", 120 days: naval invasion preparation speed +15%, army experience gain +10%.

Both killings also clear the camp's variable, its meeting mission and its target, and they cancel the camp's running operations with refunds.

### B5. Company trust at the killings

| Company | Weber 60+ | Weber 30-59 | Weber <30 | Karamyshev 60+ | Karamyshev 30-59 | Karamyshev <30 |
| --- | --- | --- | --- | --- | --- | --- |
| Loren | -5 | -3 | +3 | -5 | 0 | 0 |
| Ferrant | 0 | 0 | +3 | 0 | 0 | +5 |
| Navis | -15 | -8 | +5 | -10 | -5 | +5 |
| Arktur | +5 | +3 | 0 | -15 | -8 | +12 |
| Smenkom | -10 | -5 | +15 | 0 | 0 | 0 |
| Reidbank | -10 | -5 | +5 | -5 | -3 | +5 |

Reasons:
- **Loren**: its tankers load at the striking quays, and fuel barges sail under the coast guard's escort. Calm on the water serves it either way.
- **Ferrant**: the rail workshops sit inland, so a strike does not reach them. A new staff that swears to the council orders armour.
- **Navis**: coastal shipping is the first thing a dock strike stops and the first thing mutinous cutters seize. Peace on both fronts puts its crews back to work.
- **Arktur**: its guard is paid to break a strike. A mutiny loots its stores and shames that guard. A loyal staff buys arms through the arsenal.
- **Smenkom**: the labour exchange is blamed for the strike, and its halls are burned. Dissolved committees bring their men into the exchange. The officers do not hire through it.
- **Reidbank**: zone income services its loans, and war risk raises the premium. Calm lowers both.

### B6. The clocks over the upper tree

Proposed changes:
- **Offsets.** Weber's first meeting at day 30, Karamyshev's at day 75, the first session at day 60.
- **Annual meeting.** First at day 330, then every 360 days. With the spec's figures, Weber's 40, Karamyshev's 45 and the session's 60 all divide 360, so all four fall on day 360 together.
- **Spacing.** No meeting starts within 7 days of a session or the annual meeting; it shifts and the visible clock extends.
- **Session interval.** 45 days once both men are dead.

Sample calendar. Weber dies at about day 260 and Karamyshev at about day 420.

| Day | Event |
| --- | --- |
| 7-49 | three tenders of 14 days each |
| 30 | Weber 1 (40-day clock) |
| 60 | session 1 |
| 70 | Weber 2 |
| 75 | Karamyshev 1 (45-day clock) |
| 110 | Weber 3 |
| 120 | session 2 |
| 127 | Karamyshev 2 (shifted from 120) |
| 150 | Weber 4 (support below 60, so the clock becomes 50) |
| 172 | Karamyshev 3 (support below 60, so the clock becomes 60) |
| 180 | session 3 |
| 200, 250 | Weber 5, Weber 6 |
| 232 | Karamyshev 4 |
| 240 | session 4 |
| ~260 | Weber killed |
| 292 | Karamyshev 5 |
| 300 | session 5 |
| 330 | annual meeting |
| 352 | Karamyshev 6 |
| 360 | session 6 |
| ~420 | Karamyshev killed; session 7 |
| 465, 510, 555, 600, 645 | sessions on the 45-day clock |
| 690 | annual meeting (the session due at 690 shifts to 697) |
| 742, 787, 832 | sessions |

Density:
- Up to day 420 there is a scheduled decision every 15-25 days. Operation completions (14-60 days with 1-3 slots) and resolution deadlines fill the gaps, so the player decides something every one to three weeks.
- After both deaths, without the 45-day session clock, the gaps would grow to 4-6 weeks.

### B7. Problems in M7 and proposed fixes

1. **The tree blocks the operations.** Every focus below row 3 of both camp branches requires the killing focus (for example `elected_in_absentia` and `purged_majority` need `last_debtor`; `inheritance_without_empire` and `facsimile_blood` need `posthumous_signature`). Operations unlocked by "later focuses of their branches" would therefore open only after the man is dead.
   - Fix: re-parent `NAM_board_elected_in_absentia` to `NAM_board_founders_of_unrest`, and `NAM_board_inheritance_without_empire` to `NAM_board_dead_mans_veto`.
   - `purged_majority` and `facsimile_blood` keep the killing as their prerequisite, because their texts are set after the deaths.
   - `both_squares_bought` still requires both killings, so the final still needs both deaths.
   - Re-read the `_desc` of `elected_in_absentia`, `widows_share`, `inheritance_without_empire` and `uncrested_buyers` for mentions of a death.
   - Then run the layout inspector and the parent-above-child pin.
2. **Readiness is frozen before the killings.** `NAM_exile_drill_unlocked` needs both killing focuses, and the WIP alternatives are locked. Before the deaths, readiness has no player source, so the readiness target and the readiness prices act on a number the player cannot move. Fix: unlock the drill with `NAM_board_dead_mans_veto`.
3. **Clock collision.** All four clocks meet at day 360. Fix: the offsets and the 7-day spacing from B6.
4. **The Weber target can be empty.** "The industry of the company favoured last" may name a company with no industry; Ferrant, Arktur and Reidbank can hold none. Fix: the fallback and the 14-day lock from B1.
5. **Zero zone income has no native modifier.** The strike ideas and the alive bonuses must be read by `NAM_corp_monthly` through `has_idea`; that is the real consumer. Invalidate the economy cache in the ideas' `on_add` and `on_remove`.
6. **"Leave him alone" is undefined.** The M3 resolution "a stand on a Judas: leave him alone" does not say what it blocks. Fix: while it runs, it blocks that camp's operations and its force answer; choosing force fails the resolution.
7. **The band can change during the focus.** The spec says the killing focus shows the outcome "at the current support", but the band is applied 21 days later. Fix: state "at completion" in the tooltip, as in B0.

These are static design proposals. Nothing in this appendix was implemented or tested in the game, and no repository file was changed.

## Appendix C. Reward table of the 70 focuses

This appendix was written from a static reading of `focus_trees/NAM/exile_corporate/focuses.txt` on 2026-11-20. Nothing was run or changed.

**Conventions**
- Ids are written without the `NAM_board_` prefix. PP means political power, cap means `NAM_corp_capital`, d means days. W1-W5 and K1-K5 are the operations of B2.
- **Trust.** "+N Loren" means a call to `NAM_board_support_change`. Trust is never the main reward of a focus; it rides beside a material result.
- **Permanent modifiers** go into an existing aggregate through a focus component variable, and each is shown through a dummy idea, `NAM_board_preview_<focus>`, with `effect_tooltip`.
  - `NAM_corp_refresh` adds `NAM_board_focus_pp` and `NAM_board_focus_stab` to `NAM_corp_mod_pp` and `NAM_corp_mod_stability`.
  - `NAM_board_update_industrial_policy` adds `NAM_board_focus_output`, `_construction` and `_goods`, the same way it already adds the 0.08 growth base (effects:9260).
  - `NAM_board_army` gets one new key: `army_org_factor = NAM_board_focus_org`.
- **Dead target.** An operation unlocked after its man is already dead is useless. Each such row names the fallback paid instead ("if dead"), chosen with native `if` in `completion_reward`.
- **Re-gating** means adding `OR = { has_completed_focus = <focus> }` to the decision's existing `visible`. Nothing is copied.

### C.1 Centre (chancery, majority, final)

| Focus | Title | Kind | Reward | Feeds | Gate |
|---|---|---|---|---|---|
| beacon_out | Когда в гавани погас маяк | operation | Unlocks `op_lobby` (M5: 20 PP + 25 cap, 21 d, trust +12 up to 70, the same company not again within 90 d). +30 cap. Loren, Ferrant and Arktur +5 each (they open at 45). | M5, M1 | - |
| bought_century | Скупленное столетие | slot | `NAM_board_action_slots` 1 to 2. Unlocks `op_prepare_dismissal` (15 PP, 21 d). | M5 | - |
| property_qualification | Имущественный ценз | slot | Slots 2 to 3. Reidbank +5, Smenkom -5. | M5 | - |
| both_squares_bought | Обе площади куплены | modifier | `NAM_board_politics`: PP +0.10 a day, stability +5% (preview). The session clock drops from 60 to 45 d (B6). | M1, M3 | Existing: both killings |
| original_stays_home | Подлинник остаётся дома | rule | No-confidence immunity rises from 180 to 270 d. A no-confidence mission already running gets +30 d once. +40 cap. | M1 | - |
| sole_vote_holder | Единый держатель голосов | operation | Unlocks `op_buy_proxies` "Скупить доверенности миноритариев": 40 cap + 15 PP, 30 d. The selected company gets +1 vote until the next annual meeting, at most 2 per company (array `NAM_board_proxy_votes`, read by the recount, cleared at the meeting). | M1, M6 | - |
| copy_across_strait | Копия за проливом | building | `NAM_board_expand_company_airport` in the capital state (+2 air base). 2 `convoy_1`. Navis +8. | - | Capital state owned and controlled at completion, otherwise 40 cap |
| mainland_inventory | Материк по описи | capital | +120 cap (the mortgage roll is sold abroad). Reidbank +10, Loren -5. | capital | Existing: `harbour_exchange` |
| table_six | Стол на шесть приборов | trust | Every company below 50 gets +10 (up to 60). Every boycott countdown that is running restarts at 30 d. | M1 | Existing: `residency_for_hire` |
| partition_night | Одна ночь на раздел мира | partition | See below. | M1, M10 | `NAM_board_has_majority` |

**How `partition_night` works**
- `available` needs `NAM_board_has_majority`, one localised custom trigger.
- The reward runs `NAM_board_partition_assign`. It writes `NAM_board_partition_order^1..6`: companies sorted by votes plus `NAM_board_partition_weight`, ties to the lower id.
- `NAM_corp_assign_district` takes owners from that order before it falls back to the round-robin.
- From exile the return creates 2 districts, EFL and AZH (effects:6811). The companies in the first 2 places get +10 trust; the others get -5.
- The call to `NAM_island_partition_succession` goes. The chair changes only through M6.
- It sets the flag that the lower branch reads.

### C.2 Left branch (economy)

| Focus | Title | Kind | Reward | Feeds | Gate |
|---|---|---|---|---|---|
| quay_chain | Хозяева причальной цепи | tender | Every tender bid pays +20 cap on top of the A.3 terms. A lot kept public pays +10 cap a month more, on top of the A.7.1 +10. Smenkom, Navis and Loren +3. | M4 | - |
| private_gospel | Евангелие частной собственности | programme | Re-gates `NAM_corp_sell_steel` (+60 cap, -8 steel for 60 d, 60 d cooldown). Ferrant +8. | A.2 | Blocked by a Ferrant boycott or sanction |
| salt_monopoly | Солевая монополия | zone | `NAM_free_zone_slots` +1, to 2. +30 cap. | zone slot | - |
| future_output_pledge | Залог будущей добычи | income | +15 cap a month until `NAM_war_of_return_won`; `NAM_corp_monthly` reads the focus. Loren +8. | capital income | - |
| double_lock_warehouse | Склад под двумя замками | rule | The base annual dividend drops from 60 to 40 cap; +20 per sold lot still applies. Reidbank +5. | M6 | - |
| loren_receipt | Долг переживёт должника | building | +1 `synthetic_refinery` on the island of 225-231 with the most free slots, excluding the capital (motion L4 builds there). Loren +5. | building | Free slot checked at completion, otherwise 60 cap |
| bearer_warrant | Варрант на предъявителя | modifier | `NAM_board_industrial_policy`: consumer goods -2% (`NAM_board_focus_goods`, preview). Reidbank +8. | aggregate | - |
| loren_priority | Первой взыщет Лорэн | delivery | Loren's consignment now: 12000 fuel, through the same fuel-reserve path as `NAM_board_ship_district_order` for company 1. Loren +10, Reidbank -5. | delivery | 6000 fuel if Loren is boycotting |
| eflor_debt_purchase | Мы купили ваш долг | programme | Unlocks `buy_eflor_mortgages` "Скупка эфлорских закладных": 50 cap, 60 d, at most 3. Each adds 1 to `NAM_board_eflor_mortgages`. At the return victory each mortgage pays 100 cap and Reidbank +5. | capital, return settlement | EFL exists |
| land_foreclosure | Взыскание землёй | programme | Re-gates `NAM_corp_labour_contract` (3000 manpower lent for 90 d, +45 cap). +1500 manpower now. Smenkom +8. | A.2 | Blocked by a Smenkom boycott or sanction |
| concession_courts | Концессионные суды | programme | Re-gates `NAM_island_concession_231` (VAL or GLP buys the Middle Island steel rights for 300 treasury). Reidbank +5, Ferrant -5. | foreign income | 231 owned and controlled |
| harbour_exchange | Биржа у последнего причала | zone | Zone slots +1, to 3. Zone income rises from 50 to 60 cap per zone. | capital income | - |

### C.3 Centre-left (Karamyshev)

| Focus | Title | Kind | Reward | Feeds | Gate |
|---|---|---|---|---|---|
| dead_mans_veto | Вето мертвеца | readiness | `NAM_exile_drill_unlocked` gains this focus in an OR (B7.2): drill 20 PP + 30 cap, 30 d, +10 readiness, +15 army XP. Readiness +5 now. Unlocks K1. | readiness, M7 | - |
| escheated_throne | Выморочный престол | WIP, unchanged | - | - | `always = no` |
| posthumous_signature | Посмертная подпись | kill | Keeps `NAM_island_requisition_transports`. Applies the B4 band read at completion and the B5 trust table. | M7 | None |
| silence_after_settlement | Тишина после расчёта | WIP, unchanged | - | - | Closed |
| inheritance_without_empire | Наследство без империи | operation | Unlocks K2. Navis +5. If dead: 2 `convoy_1` + 30 cap. | M7 | Re-parent to `dead_mans_veto` (B7.1) |
| facsimile_blood | Кровь под факсимиле | modifier | `NAM_board_army`: organisation +5% (`NAM_board_focus_org`, preview). Readiness +5. | aggregate, readiness | Existing: after the killing |
| escheated_land_auction | Аукцион выморочных земель | WIP, unchanged | - | - | Closed |
| uncrested_buyers | Покупатели без гербов | capital | +60 cap. Reidbank +8. Unlocks K3; if dead, +30 cap more. | capital, M7 | - |
| privatise_governorate | Приватизация наместничества | seat | The premier's seat opens: Корнев becomes removable, and Рахманов and Крамской become eligible (their `allowed`/`available` read this focus). Unlocks K5. Loren and Reidbank +5. | M2, M7 | - |
| hereditary_roll | Наследственный список | rule | At the officers' meeting the concession costs 20 cap instead of 35 and gives Karamyshev +6 instead of +10. Reidbank +8, Loren +5, Smenkom -8. | M7 | Exclusive |
| old_settlers_oath | Присяга старожилов | programme | Unlocks `settlers_militia` "Дружина старожилов": 25 PP + 2000 manpower + 1200 `infantry_equipment`, 45 d, once. Result: one locked 6-battalion infantry division at the capital. The officers' "arrest" answer no longer needs a willing company and costs readiness -4 instead of -8. Smenkom +8, Reidbank -5. | M7, army | Exclusive |
| admitted_owners_register | Реестр допущенных собственников | building | `NAM_board_build_company_offices` (business centre) in the capital state. Arktur and Reidbank +4. | building | Capital state owned at completion |
| boundary_notches | Зарубки на меже | programme | Re-gates `NAM_island_public_works` (+1 infrastructure, 42 d, 30 PP + 250 treasury). +1000 manpower. | building | - |
| eflor_petition | Прошение из Эфлора | partition | An event with one answer per company that holds a vote. The chosen company gets +10 trust and +3 `NAM_board_partition_weight`; the others get -3. | M10 | - |
| district_buyout | Отступные за округ | operation | Unlocks K4. Arktur +4. If dead: 30 command power + 40 cap. | M7 | - |
| price_of_silence | Выкуп за молчание | Judas pressure | Karamyshev -6 directly, using no slot, and his next meeting comes 20 d later, once. Reidbank -5. If dead: +60 cap. | M7 | - |
| close_the_lawsuit | Черта под тяжбой | trust | All companies +5. After the return, the dispute roll (effects:9713) is off for 360 d. | M1, districts | - |
| land_under_seal | Земля под печатью | readiness | Readiness +10 and 2000 manpower. | readiness | - |

### C.4 Centre-right (Weber)

| Focus | Title | Kind | Reward | Feeds | Gate |
|---|---|---|---|---|---|
| founders_of_unrest | Учредители будущей смуты | operation | Unlocks W1 and makes the Weber meeting clock visible. +30 cap. | M7 | - |
| last_debtor | Голос последнего должника | kill | Keeps `NAM_corp_buy_arms` and `NAM_island_recruit_warehouse_guards`. Applies the B4 band read at completion and the B5 trust table. | M7 | None |
| treaty_two_judases | Договор с обоими Иудами | WIP, unchanged | - | - | `always = no` |
| purged_majority | Большинство после чистки | modifier | `NAM_board_politics`: PP +0.10 a day (preview). Smenkom +5. | aggregate | Existing: after the killing |
| elected_in_absentia | Избран заочно повешенным | operation | Unlocks W2. Loren +5. If dead: +40 cap. | M7 | Re-parent to `founders_of_unrest` |
| proxy_parliament | Парламент доверенностей | WIP, unchanged | - | - | Closed |
| widows_share | Вдовья доля | delivery | 4 `convoy_1`. Navis +5. Unlocks W3; if dead, +1500 manpower instead. | delivery, M7 | - |
| ministries_in_concession | Министерства в концессию | WIP, unchanged | - | - | Closed |
| society_99_1 | Общество 99\1 | income | +20 cap a month in club dues. `NAM_board_politics`: stability -3% (`NAM_board_focus_stab`, preview). | capital income | - |
| subsidised_opposition | Оппозиция на содержании | operation | Unlocks W4. At the committees' meeting the concession costs 25 cap instead of 40 and gives Weber +6 instead of +10. Humanism +5. | M7 | Exclusive |
| incumbents_credit | Кредит действующей власти | programme | Unlocks `mainland_officials` "Жалованье чиновникам материка": 30 cap + 20 PP, 90 d, can run again 90 d later. EFL and AZH get `NAM_mainland_bought_officials` for 90 d: war support -5%, stability -5%. Loren +5. | return war | Exclusive; EFL or AZH exists |
| political_debt_register | Реестр политических долгов | rule | A rejected company's sanction lasts 30 d instead of 60. "Return for revision" costs 20 PP instead of 40. | M3 | - |
| family_relief_fund | Касса семейного призрения | timed spirit | Unlocks `relief_fund`: 60 cap, every 180 d. Adds `NAM_board_relief_fund_spirit` for 180 d: stability +5%, monthly population +10%. Smenkom +8. | spirit | - |
| lawyers_of_both_shores | Стряпчие обоих берегов | tender | Unlocks `retender_lot` "Повторные торги": 25 PP. It reopens one public lot's tender now instead of 90 d later, and both bids pay +20 cap. | M4 | A lot is public |
| mourning_licence | Лицензия на траур | operation | Unlocks W5. Arktur +4. If dead: +40 cap. | M7 | - |
| representation_for_loss | Представительство по утрате | seat | The next health appointment costs 0 PP. Smenkom and Reidbank +5. | M2 | - |
| chairmans_copy | Председательский экземпляр | votes | The chair's company gets +1 vote; the recount reads `NAM_board_chair` and the focus. +50 cap. | M1, M6 | - |
| port_rights_monopoly | Монополия портовых прав | income | +25 cap a month. Navis +10, Arktur -5. | capital income | - |

### C.5 Right branch (army and fleet)

| Focus | Title | Kind | Reward | Feeds | Gate |
|---|---|---|---|---|---|
| order_arsenal | Арсенал порядка | delivery | 1500 `infantry_equipment` and 12 `artillery_equipment`. Arktur +10. | delivery | - |
| arsenal_monopoly | Арсенальная монополия | modifier | `NAM_board_industrial_policy`: factory output +5% (`NAM_board_focus_output`, preview). Arktur +5, Ferrant -5. | aggregate | - |
| foundry_mark | Клеймо литейного двора | building | +1 `arms_factory` on an island of 225-231 with a free slot. Ferrant +5. | building | Slot checked at completion, otherwise 60 cap |
| island_fleet_shares | Паи островного флота | programme | Re-gates `NAM_island_convoy_service` (+15% resources on the islands for 180 d, 25 PP + 150 treasury). Navis +5. | programme | - |
| factory_guard | Частная заводская стража | readiness | Readiness +10 and 1500 manpower. Arktur +5. | readiness | - |
| captains_share_qualification | Паевой ценз капитанов | delivery | 6 `convoy_1`. Navis +8. | delivery | - |
| last_voyage_rifles | Винтовки последнего рейса | programme | Re-gates `NAM_order_marines` under the takeover: 50 cap + 4300 manpower, at most 3; the loot price stays for the radical route. +1000 `infantry_equipment`. | readiness, landing | - |
| return_voyage | Обратный рейс | readiness | The drill gives +15 readiness instead of +10. +2000 manpower. | readiness | - |
| azhar_land_fund | Земельный фонд Ажара | partition | Navis +3 `NAM_board_partition_weight`. +60 cap. Navis +5, Loren -3. | M10 | - |
| private_strait | Частный пролив | building | `NAM_board_build_company_docks` in the capital state (+1 dockyard). Navis +5. | building | Existing dockyard cap of 20 |
| corporate_mass_housing | Корпоративная массовая застройка | programme | Unlocks `company_housing`: 50 cap + 20 PP, 60 d, on at most 2 islands. At completion it calls `NAM_board_build_company_housing` on the target; ownership is checked again, otherwise the price is refunded. Smenkom +5. | building | - |
| residency_for_hire | Прописка по найму | modifier | `NAM_board_industrial_policy`: construction +10% (`NAM_board_focus_construction`) and `NAM_board_politics`: stability -2% (preview). Smenkom +10. | aggregate | Existing gate of `table_six` |

### C.6 The exclusive pairs

**`hereditary_roll` / `old_settlers_oath`: buy the officers or out-arm them.**
- **Hereditary roll.** Karamyshev's meetings become cheap to concede, and the line opens K4, a bribe operation. The money flows through Reidbank and Loren, which gain, while Smenkom loses. Karamyshev ends lower through capital spent and slots used.
- **Old settlers' oath.**
  - The line has no K4. Karamyshev loses 47 support through operations instead of 59; `price_of_silence` adds -6.
  - The player instead gets a standing division and an arrest answer that needs no company and costs only -4 readiness, so the officers can be faced down at every meeting.
  - It pays in manpower and equipment, not capital. Smenkom gains and Reidbank loses.
  - The line ends with readiness +10 (`land_under_seal`), not with the trust reset of `close_the_lawsuit`.

**`subsidised_opposition` / `incumbents_credit`: buy the committees or weaken the enemy abroad.**
- **Subsidised opposition.** The council pays the moderates: W4, cheaper concessions, humanism up. The line gives tools for running the council (shorter sanctions, cheaper revision, retenders, +1 vote for the chair). It reaches `table_six` through `chairmans_copy`.
- **Incumbents credit.**
  - Weber is broken by force (W5, `mourning_licence`).
  - Capital goes abroad: the paid officials weaken EFL and AZH before the return war.
  - The line pays back in social spirits and +25 cap a month from port rights.
  - It reaches `table_six` through `port_rights_monopoly`, which needs `residency_for_hire` from the right branch.
- The AI plan keeps hereditary and incumbents, as today.

### C.7 Timeline

- **How long it takes.** A focus point is 7 days. One playthrough is 121-125 points, 847-875 days:
  - centre 23 points;
  - left 26;
  - right 26;
  - the shared Weber and Karamyshev focuses 14 each;
  - one Weber line and one Karamyshev line, 9-11 points each.
- **What must come early.** These six focuses make the mechanics usable before the clocks of B6 start: `beacon_out`, `quay_chain`, `bought_century`, `founders_of_unrest`, `dead_mans_veto` and `property_qualification`. Together they are 13 points, about day 91.
  - Tenders run on days 7-49.
  - Weber's first meeting is on day 30, the first session on day 60, Karamyshev's first meeting on day 75.
  - The drill is the only source of readiness before the killings.
- **Proposed cost change.** Lower `quay_chain` from 2 to 1. Taken right after the root, its terms then apply to every lot from the shipyard tender on. The total becomes 156; costs stay within the test's (0,3].
- **Re-parents** (B7.1): `elected_in_absentia` under `founders_of_unrest`, and `inheritance_without_empire` under `dead_mans_veto`.
  - Then every operation is reachable while its man lives. W5 lies 105 days of branch focuses deep, and so does K4.
  - That fits the B6 estimates: Weber killed around day 260, Karamyshev around day 420.
- **The bottom of the centre.** `both_squares_bought` needs both killings, so the lower centre (126 days) starts at about day 420 and ends at about day 546, well inside the playthrough.
- **Why three slots by day 63 is right.**
  - Up to day 420 the slots carry 10 operations, the lobby and the prepared dismissal.
  - After the killings three separate operations are left (lobby, prepared dismissal, buying proxies), so the third slot never sits idle: one decision cannot run twice (w3_X).
- **No other focus needs to move.** The partition race does need the annual meeting at day 690 to fall before `partition_night` (about day 850). That holds.

### C.8 Count of rewards by kind

| Kind | Count |
|---|---|
| Programme (price and duration) | 10 |
| Operation unlock | 8 |
| WIP, unchanged | 6 |
| Permanent modifier (aggregate) | 6 |
| Rule or terms | 5 |
| Building | 5 |
| Readiness | 4 |
| Delivery | 4 |
| Capital income | 3 |
| Partition | 3 |
| Slot | 2 |
| Kill | 2 |
| Capital | 2 |
| Zone slot | 2 |
| Tender | 2 |
| Trust | 2 |
| Seat | 2 |
| Judas pressure | 1 |
| Votes | 1 |
| Timed spirit | 1 |
| **Total** | **70** |

No chain has three focuses of the same kind in a row.

### C.9 New ids required beyond appendices A and B

**Decisions**
- `NAM_board_op_lobby` and `NAM_board_op_prepare_dismissal`: named here, specified in M5.
- `NAM_board_op_buy_proxies`
- `NAM_board_buy_eflor_mortgages`
- `NAM_board_settlers_militia`
- `NAM_board_mainland_officials`
- `NAM_board_relief_fund`
- `NAM_board_retender_lot`
- `NAM_board_company_housing`

**Ideas**
- Previews: `NAM_board_preview_both_squares`, `_purged_majority`, `_society_99_1`, `_bearer_warrant`, `_arsenal_monopoly`, `_facsimile_blood`, `_residency_for_hire`.
- Timed: `NAM_board_relief_fund_spirit`; `NAM_mainland_bought_officials`, which goes on EFL and AZH.

**Variables**
- Focus components: `NAM_board_focus_pp`, `_stab`, `_output`, `_construction`, `_goods`, `_org`.
- Arrays: `NAM_board_proxy_votes`, `NAM_board_partition_order`, `NAM_board_partition_weight`.
- `NAM_board_eflor_mortgages`.

**Other**
- Scripted trigger `NAM_board_has_majority`.
- Effect `NAM_board_partition_assign`.
- The `eflor_petition` event, registered in `adiscord_event_ids.json`.
- The division template "Дружина старожилов".

### C.10 Problems found

1. **Wrong variable name in appendix A.** Appendix A writes `NAM_corp_zone_slots`. The real variable is `NAM_free_zone_slots`, clamped to 1-3 (effects:8344-8356). Once `harbour_exchange` is done, Reidbank's motion 2 can no longer be tabled; its "below 3" condition already handles that.
2. **The hidden island decisions need more than a re-gate.**
   - `NAM_island_public_works`, `_convoy_service` and `_concession_231` need `NAM_independent_programmes_operable`, which needs `NAM_center_vanished` (triggers:670-677). They are priced in treasury.
   - They sit in `NAM_national_programmes`, which is hidden under the takeover, and the pin at test:8950-8981 allows only two categories there.
   - Fix: move the three blocks into `NAM_free_zones` and add a takeover branch to their operable triggers. `NAM_island_steel_levy` stays unused.
3. **The premier motions can be tabled before the seat exists.** Appendix A's Loren motion 4 and Reidbank motion 3 can come up from day 60, but Корнев stays fixed until `privatise_governorate`. Gate both motions on that focus.
4. **`partition_night` has little to divide.** From exile the return creates only 2 districts (EFL, AZH), so only the top two companies get land. That is a sharp, readable race, but the spec should say so. If the lower branch's island wars do not create districts (w3_X, M10 finding), the weights from `eflor_petition` and `azhar_land_fund` matter only for those two places.
5. **The Karamyshev arithmetic in B2 assumes the hereditary route.** On the oath route K4 is missing. B2 should state 47 + 6, not 59.
6. **Tests and tools must change together with the rewards.**
   - The reward lint exemption for this tree (test:8079-8085) must be removed.
   - `validate_focus_rewards` will then judge these rows.
   - The `quay_chain` cost change and the two re-parents need the layout inspector run and the parent-above-child pin checked.
   - The user and Codex are editing the focus source live, so package 7 must start from a frozen file.

None of this was checked in the running game.

## Appendix D. Outline of the lower branch

Sources were read on 2026-11-20. Line numbers are hints. Nothing in this appendix is implemented, and nothing here has been checked in the game.

### D1. The three targets

| | Ulven League ULV | Luren Archipelago LUR | Sharden Confederation CHD |
| --- | --- | --- | --- |
| States (capital) | 644-648 (648) | 649-652 (651) | 672-680 (680) |
| Civilian / military factories / dockyards | 3 / 1 / 1 | 2 / 1 / 1 | 4 / 2 / 1 |
| Manpower in state history | 850 000 (557 000 in 648) | 540 000 (434 000 in 651) | 1 900 000 (1 718 000 in 680) |
| Starting army | 2 "Territorial Brigade" (3 infantry each), at 6452 and 5667 | 2, at 1894 and 11300 | 3, at 1610, 1858 and 12852 |
| Fleet, convoys | 6 DD, 40 convoys | 6 DD, 40 convoys | 1 CL, 6 DD, 1 SS, 50 convoys |
| Naval bases | level 1 in every state | level 1 in every state | level 1 in every state except 679 |
| Strategic regions | 190, 192-195 | 196, 198, 199, 201 | 220, 222, 223 |
| Map distance from the 228 port (6893), unitstacks px | 227 | 506 | 591 |
| Suppression | not listed in `ADISCORD_is_non_participating_minor` | same | same |

For comparison, the South Harbour (16716) is 201 px from the 228 port. The NAM islands sit in strategic region 25, so none of the targets shares a region with them.

Sources: `history/states/644..680-*.txt`, `history/countries/<TAG> - <TAG>.txt`, `history/units/<TAG>.txt`, `map/unitstacks.txt`.

What follows for landings:
- Ulven lies about as far away as the mainland landing.
- Luren is 2.5 times as far and Sharden 3 times. Sharden therefore needs a seized strait island as a staging port.
- The base invasion cap is 4 divisions (`BASE_NAVAL_INVASION_DIVISION_CAP`).
- NAM holds `ADISCORD_tech_restored_dockyards` (invasion capacity 100) through its naval profile. It does not hold `ADISCORD_tech_amphibious_formation_organization` (+2 divisions per invasion); no NAM route grants it today.
- NAM's starting fleet is 22 patrol vessels, 4 CA, 6 CL and 8 SS. The exile entry effect removes no ships, but survival in a real campaign is unverified; check a text save.
- The targets appear in NAM script only as piracy victims: lane 3 "strait" is ULV+LUR, lane 4 "crossing" is CHD+RIV (`NAM_pirate_save_lane_victims`). Once a target becomes a subject, `NAM_pirate_victim_valid` closes its lane.
- No waking is required. Registration still calls `ADISCORD_release_non_participating_minor_optimization`, as `NAM_wor_register_target` does.
- `NAM_order_marines` is radical-gated (`NAM_piracy_open`), and its orders are delivered only at the return landing. Island wars need marines that exist earlier.
- "Island Marines" is locked with `force_allow_recruiting = yes`, so it can be recruited normally once it exists.

### D2. Branch plan (60 focuses, 10 exclusive pairs)

Source: `focus_trees/NAM/exile_corporate/lower.txt`, `# @section lower` and `# @include` from the main file. Five entry focuses take `prerequisite = NAM_board_partition_night` plus `allow_branch = { has_completed_focus = NAM_board_partition_night }`. The reward of partition night adds `mark_focus_tree_layout_dirty = yes`.

| Sub-branch | Purpose | Count | Exclusive pairs | Council use |
| --- | --- | --- | --- | --- |
| Society "99 к 1" | the 1 percent and the payroll islands | 10 | debt bondage / bread and lottery; closed register / people's shares | Smenkom, Reidbank and the register trust; the final writes the handoff model |
| Industrial rearmament | factories, fuel, war economy | 10 | steel for guns / company docks; cartel / open tenders | Ferrant, Navis, Loren and Arktur trust; factories in concession districts |
| Strait | Ulven and Luren | 7 | night landing / strait blockade | operation focuses need a majority; Navis and Loren must not boycott |
| Trunk | marque, concessions, the return | 6 | mainland by shares / union of boards | the final needs a majority; the pair decides the chairman's weight after the return |
| Sharden | the large prize | 7 | promise to the south / hunger in Sharden | Reidbank finance; the concession goes to Arktur or Reidbank |
| Army rearmament | contract army, readiness | 10 | mercenaries / conscription; armour / light columns | an Arktur boycott blocks the contract programme |
| Marines and fleet | corporate marines, convoys, raids | 10 | escort flotilla / raider cruisers | Navis convoys; the raids feed the war design |

**Concessions.** Each settled island becomes a federal district: 2 votes, an operator company, monthly dividends of 8/10/10/6/12/15 capital, and `NAM_board_factory_site` construction. The operator comes from a concession tender between a fixed pair:

| Island | Bidders |
| --- | --- |
| ULV | Navis or Ferrant |
| LUR | Loren or Smenkom |
| CHD | Arktur or Reidbank |

The pairs deliberately cross the industry tender pairs, so the three awards move the six seats of the pyramid. Exile votes start at 12; the districts add 6.

### D3. Focus list

Ids omit `NAM_board_`. "legacy" means an id whose localisation already exists. Its `_desc` must be re-read and stripped of mechanics.

**Trunk**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| letters_of_marque | 18,13,2 | Каперские патенты | Navis prints patents under the council's flag | programme: piracy lanes 3 and 4 open to the corporate route; Navis +10 |
| island_concessions (legacy) | 18,14,1 | Островные концессии | company plates on harbours not yet taken | capital +40 (existing tt); opens the category "Островные операции" with the bidder forecast |
| assembly_point | 18,23,2 | Сборный пункт Семи островов | every hull anchors off 228 | readiness +15 (`NAM_revenge_readiness`); convoys +10 |
| mainland_shares | 16,24,2 | Материк по долям | the partition-night map is notarised | council: each company with a pre-assigned district +10; mainland district dividends +25% after the return |
| union_of_boards (legacy) | 20,24,2 | Союз правлений | the boards merge under one seal | council: the chair company rests a further +10; 360-day no-confidence immunity; companies with no district or industry -15 |
| war_of_return (legacy) | 18,25,3 | Операция "Контрольный пакет" | the fleet sails for the South Harbour | war: `NAM_war_of_return_start` |

**Strait**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| strait_pilot_charts | 15,15,1 | Лоцманские карты пролива | old pilots sell their soundings | intel: army and navy intel 25 on ULV and LUR; strait operations start at readiness 5 |
| night_landing | 14,17,2 | Ночной десант | land before the league wakes | doctrine: strait threshold 30; launch idea +10% |
| strait_blockade | 16,17,2 | Блокада пролива | starve both harbours first | programme: blockade decision; threshold 50; the strait pact applies |
| strait_beachhead | 15,18,1 | Плацдарм на скалах | rehearsal on a bare rock | tech: `ADISCORD_tech_amphibious_formation_organization` |
| ulven_operation | 14,20,2 | Операция "Ульвен" | the league refuses to sell its harbour | war operation ULV |
| luren_operation | 16,20,2 | Операция "Лурен" | the archipelago closes its roads | war operation LUR |
| strait_masters | 15,22,2 | Хозяева пролива | both shores answer to the council | building: +1 dockyard in each strait concession capital (`NAM_board_build_company_docks`) |

**Sharden**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| sharden_ledgers | 21,15,1 | Счета Шардена | Reidbank reads the confederation's debts | programme: "Скупка шарденских долгов" (40 capital, 60 days; CHD timed idea, 180 days: factory output -10%, stability -5%); Reidbank +10 |
| southern_promise | 20,17,2 | Обещание южным островам | autonomy promised to 672-675 | war terms: CHD brigades 2 and 3 disband at the declaration; the CHD district pays half dividends |
| sharden_hunger | 22,17,2 | Голод в Шардене | grain ships turned away from 680 | programme: "Хлебная блокада" (40 capital + 2000 fuel, 60 days; CHD timed idea, 180 days: stability -25%, war support -30%); NAM timed idea, 180 days: stability -5% |
| sharden_note | 21,18,2 | Нота конфедерации | the council's demands are delivered | diplomatic: NAM claims 672-680; available only with one strait concession |
| sharden_operation | 20,20,3 | Операция "Шарден" | the largest fleet the islands have seen | war operation CHD |
| sharden_bonds | 22,20,1 | Шарденские облигации | bonds secured on a harbour not yet taken | capital +80; the first 180 days of CHD dividends go to the bondholders; Reidbank +10 |
| sharden_concession | 21,22,2 | Концессия Шардена | Sharden's regiments swear to the company | units: 2 infantry divisions in 680; chair company +10 |

**Society**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| one_percent | 4,13,2 | Один процент | the club of 99 closes its doors | political: hedonism +10; `NAM_corp_mod_pp` +0.10 (dummy preview) |
| debt_bondage | 2,14,2 | Долговая кабала | debts repaid in labour | programme: "Отработка долгов" (15 PP, 60 days, +3000 manpower, stability -3%; 90-day cooldown, at most 4); Smenkom +10 |
| bread_and_lottery | 6,14,2 | Хлеб и лотерея | a bread ration and a weekly draw | spirit, 360 days: stability +8%, war support +5%, consumer goods +5%; Reidbank +10 |
| company_towns | 4,15,2 | Города при конторах | quarters by payroll list | building: `NAM_board_build_company_housing` on 228 and 225 |
| private_police | 2,16,1 | Частная полиция | constables replaced by company guards | modifier: `NAM_corp_mod_stability` +3%; Weber strike spirits end early |
| wage_in_scrip | 6,16,1 | Жалованье талонами | wages redeemable only at company stores | income: capital +15 a month in `NAM_corp_monthly` |
| closed_registry | 2,18,2 | Закрытый реестр | no new names in the register | council: all companies +5 trust and resting level +5; stability -5% |
| people_shares | 6,18,2 | Народные паи | tiny shares for the 99 percent | capital +100; stability +5%, war support +5%; all companies -5 |
| strikebreakers | 4,19,1 | Штрейкбрехеры | overseas dockers break the last strike | spirit, 180 days: dockyard output +15%, stability -3%; Smenkom +15 |
| society_99_to_1 | 4,20,2 | Общество 99 к 1 | ninety-nine percent own nothing | aggregate: factory output +5%, consumer goods -5%, stability -5%, plus a term per earlier choice; writes the handoff variables |

**Industry**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| war_contracts | 10,13,2 | Военные подряды | the first war orders are placed | programme: "Заводской подряд" (25 PP + 60 capital escrow, 90 days, +1 military factory on a chosen island 225-231, rechecked at delivery; the selected company +8; at most 4) |
| steel_for_guns | 8,14,2 | Сталь в стволы | rolling mills switch to barrels | building: +2 military factories on 228 and 227; Ferrant +10 |
| company_docks (legacy) | 12,14,2 | Доки пароходства "Навис" | slipways for transport hulls | building: `NAM_board_build_company_docks` on 227 and 231; Navis +10 |
| fuel_reserve | 10,15,1 | Неприкосновенный запас | Loren fills the war tanks | stockpile: +5000 fuel; Loren +5 |
| double_shifts | 8,16,1 | Две смены у станка | the night shift becomes permanent | spirit, 270 days: factory and dockyard output +10%, stability -5% |
| foreign_licences | 12,16,2 | Лицензии из-за моря | foreign patents bought for capital | research: two 100% industry bonuses |
| concession_factories | 10,17,2 | Заводы на концессиях | plants rise on the seized islands | building: +1 military factory in every operating island district passing `NAM_board_factory_site`; needs one concession |
| cartel_prices | 8,18,2 | Картельные цены | the arms companies fix one price | aggregate: production efficiency cap +10%; Arktur, Ferrant and Loren +10; Reidbank and Smenkom -10 |
| open_war_tenders | 12,18,2 | Открытые военные торги | every order goes to auction | programme: plant contract 35 capital, cap 6; Arktur and Ferrant -10 |
| war_economy_charter | 10,20,2 | Военный устав компаний | the companies sign the war charter | law: one economy step toward war; `ADISCORD_economy_mark_dirty` |

**Army**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| army_price_list | 26,13,2 | Армия по прейскуранту | regiments priced like freight | programme: "Контрактный батальон" (40 capital + 3000 manpower, 45 days, 1 equipped infantry division; at most 4; blocked by an Arktur boycott) |
| mercenary_battalions (legacy) | 24,14,2 | Наёмные батальоны | Smenkom hires foreign veterans | units: 3 infantry divisions at 50% experience; -20 capital a month for 12 months; Smenkom +10 |
| island_conscription | 28,14,2 | Островной призыв | islanders called up by register | law: conscription +1 step, +5000 manpower, stability -5%; Smenkom -10 |
| officer_shares | 26,15,1 | Офицерские паи | officers paid in shares | army XP +30, command power +20 |
| artillery_park | 24,16,1 | Артиллерийский парк | guns from the arsenal sheds | equipment: 72 artillery, 48 anti-tank, 1000 rifles |
| live_fire_drills | 28,16,2 | Учения с боевой стрельбой | the beaches hear live rounds | programme: `NAM_exile_drill` gives +15 readiness and re-enables after 10 days |
| staff_of_return | 26,17,2 | Штаб возвращения | a staff for the crossing | aggregate `NAM_board_army`: planning speed +10%, max planning +5% |
| arktur_armour | 24,18,2 | Бронерота "Арктура" | Arktur assembles a tank company | equipment and tech: light-armour tech, 40 tanks; Arktur +10 |
| light_columns | 28,18,2 | Лёгкие колонны | trucks instead of tanks | equipment and tech: motorised tech, 250 trucks; Loren +10 |
| army_of_shareholders | 26,20,2 | Армия акционеров | every soldier holds a coupon | readiness +15; war support +10% |

**Marines and fleet**

| id | x,y,c | Title | Gist | Reward |
| --- | --- | --- | --- | --- |
| private_navy (legacy) | 32,13,2 | Флот компаний | Navis charters coastal steamers | convoys +8, naval XP +25; Navis +10 |
| landing_contracts (legacy) | 30,14,2 | Подряд на высадку | marines on investors' capital | programme: `NAM_order_marines_corp` (60 capital + 4300 manpower, 60 days, 1 "Island Marines" division at the capital; at most 4); never writes `NAM_marines_orders_delivered` |
| landing_craft | 34,14,2 | Десантные баржи | flat-bottomed barges | tech: `ADISCORD_tech_amphibious_landing_craft` |
| marine_school | 32,15,2 | Школа морской пехоты | Arktur's sergeants drill the companies | unit: 1 "Island Marines" division now; army XP +15 |
| escort_flotilla | 30,16,2 | Конвойная флотилия | escorts for every transport | spirit, 365 days: convoy escort +20%; convoys +6 |
| raider_cruisers | 34,16,2 | Рейдерские крейсера | cruisers hunt enemy tankers | programme: `NAM_pirate_raid_slots` +1 |
| shore_parties | 32,17,1 | Береговые партии | beach-masters with flags | tech: `ADISCORD_tech_amphibious_shore_parties` |
| harbour_pilots | 30,18,1 | Лоцманы чужих гаваней | foreign pilots on the payroll | operation: +10 readiness to the running or next island operation; CHD navy intel 40 |
| company_airport (legacy) | 34,18,1 | Аэропорт правления | the boards' airfield | building: `NAM_board_expand_company_airport` at the capital; 24 close-air-support planes |
| marine_corps_of_boards | 32,20,2 | Морская пехота правлений | the companies' own corps | return: the 700 landing always takes 3 divisions (extend `NAM_landing_third_division`) |

### D4. Layout

The branch is mirrored on x 18:

| Columns | Sub-branch |
| --- | --- |
| 2-6 | society |
| 8-12 | industry |
| 14-16 | strait |
| 18 | trunk |
| 20-22 | Sharden |
| 24-28 | army |
| 30-34 | marines |

Rows run from 13 to 25:
- Row 13: the five entries at x 4, 10, 18, 26 and 32. Their wire bus at y 12.5 hits no card.
- Every row was checked by hand against the inspector's rules: same-row gaps of at least 2, no wire through a card, and no crossing between unrelated wires.
- An "either side of a pair" child always has a single position. Two children under a pair would cross.
- The longest vertical chains have two links: 18,13 to 18,14; S9 to S10; I1/I4-type merges are staggered.
- Side finals sit at row 20 (4, 10, 26, 32), settlements at row 22, and the trunk at rows 23-25.

The inspector must learn to read includes and to accept `allow_branch` on the five entries.

### D5. War design

**Order.** One island operation at a time, held in the variable `NAM_isl_op_target` (1 ULV, 2 LUR, 3 CHD).
- ULV and LUR can be taken in either order.
- The Sharden note needs one strait concession as a staging port.

**Core.** One shared set of effects and variables in the NAM effects file:
- effects `NAM_isl_op_open`, `NAM_isl_op_add_readiness` (temporary input `NAM_isl_op_gain`), `NAM_isl_op_launch` and `NAM_isl_op_close`;
- the variable `NAM_isl_op_readiness`, 0-100.

This follows the VAL south pattern: `VAL_operation_expand_southern_bridgehead` declares the war, then `VAL_south_reinforce_defender` and `VAL_ert_op_apply_launch` run.

**Preparation.** Decisions in "Островные операции". Each takes a chancery slot.

| Decision | Price | Days | Readiness | Condition and extra effect |
| --- | --- | --- | --- | --- |
| "Промер глубин" | 20 PP | 21 | +15 | - |
| "Склады плацдарма" | 40 capital + 1000 fuel | 28 | +20 | Loren must not boycott |
| "Подкуп гарнизона" | 50 capital | 30 | +15 | Reidbank trust at least 35; the target loses one brigade at the declaration |

**Entry.** The decision "Высадка: <target>" declares `annex_everything`. It needs:
- readiness of at least 50, or 30 on the night-landing route;
- a majority;
- no boycott by Navis or Loren;
- 20 or more convoys;
- at least 2 marine divisions delivered by the corporate order.

The launch adds a timed idea for 60 days: amphibious invasion +10, +20 or +30% at readiness 50, 75 or 100, as three ideas. It also adds NAM claims on the target's states.

**Defender reinforcement.** Applied once, at the declaration (flag `NAM_isl_defence_mobilised`):

| Target | Manpower | Rifles | Other |
| --- | --- | --- | --- |
| ULV, LUR | +6000 | +4000 | 2 brigades |
| CHD | +15000 | +10000 | 120 support, 4 brigades, coastal fort 2 at 1610 and 1858 |

- Difficulty above 2 adds 1 brigade to ULV or LUR and 2 to CHD.
- An alerted target (`NAM_pirate_alert`, or the blockade route) gets coastal fort 1 at its capital.
- Raids drain the target's fuel but alert it. That trade is the reason for the escort/raider pair.

**Participants.**
- Normally the war has one defender.
- Strait pact: if the other strait island is independent and alerted, it joins through `create_faction_from_template` (`faction_template_ADISCORD_standard`), in the shape of `NAM_wor_form_coalition`.
- Both members must then fall. Both sides get major status for the campaign through the existing `ADISCORD_nam_resource_war_reserve_major`, which is safe because the resource war and the return never overlap with these wars.
- Every terminal path releases the status and dismantles the coalition.

**Ending, without a default winner.** The defenders have no transports, and NAM cannot win without landing. Two visible timeout-only missions, each id registered in the synchronized tokens, decide the war:
1. "Плацдарм" (45 days, 60 for CHD). Success when NAM or its subject controls a target state. Timeout means the landing failed.
2. "Кампания" (150 days, 210 for CHD). Ends on the target's capitulation. Timeout:
   - with the target capital controlled, the settlement runs;
   - otherwise the landing has failed.

**A failed landing costs:**
- `white_peace` through script;
- the timed idea `NAM_isl_landing_failed`, 180 days: stability -10%, PP -0.15 a day;
- readiness and deposits are lost;
- Navis and both of the island's bidders lose 15 trust;
- the target cannot be reopened for 120 days, keeps its reinforcements and stays alerted;
- divisions lost at sea stay lost.

**Settlement.** New sections `nam_islands:on_capitulation_immediate` and `nam_islands:on_capitulation` follow `nam:` in `09_ADISCORD_scripted_peace_on_actions.txt`, plus `on_peace` for an external close. They use a one-day receipt and `skip_default_capitulation`.

The effect `NAM_isl_settle_defeated`:
1. calls a core extracted from `NAM_wor_federal_district_join` (puppet, `autonomy_NAM_federal_district`, flag, array), without `NAM_southern_lands_open`;
2. restores the subject's control of its states, because a same-tick `set_autonomy` leaves the overlord in occupation;
3. queues the recount;
4. opens the concession tender, a 30-day mission.

The tender has three outcomes:
- award to one of the two bidders: sets `NAM_corp_district_owner` before `NAM_corp_district_apply`; the winner +15, the loser -15;
- "Под управление совета": NAM annexes the subject, gains the factories directly and no votes; both bidders -10;
- timeout: no owner and therefore no votes; both bidders -5; the tender reopens 90 days later.

### D6. The return

`war_of_return` is available when all of these hold:
- a majority (one localised custom trigger);
- `NAM_revenge_readiness` at least 70;
- `marine_corps_of_boards` completed, or `NAM_marine_orders_paid` at least 1;
- no island operation open;
- `NAM_war_of_return_can_start = yes`, which already requires `has_war = no`.

Its prerequisites run through `assembly_point`, which needs `strait_masters` and `sharden_concession`.

The reward is `hidden_effect = { NAM_war_of_return_start = yes }` with a custom tooltip. The district subjects join automatically (`can_decline_call_to_war = no`, `units_deployed_to_overlord = yes`).

`load_focus_tree` keeps only shared completions, so the following must be saved before the victory-path load:

| Record | Holds |
| --- | --- |
| `NAM_board_return_chair` | snapshot of `NAM_board_chair` |
| `NAM_corp_district_owner` on EFL and AZH | from partition night |
| `NAM_corp_district_owner` on ULV, LUR, CHD | from the tenders |
| `NAM_board_return_course` | 1 shares, 2 union |
| `NAM_board_society_labour` | 1 bondage, 2 lottery |
| `NAM_board_society_registry` | 1 closed, 2 people's |
| global flag `NAM_wor_winner_corporate` | set in `NAM_war_of_return_resolve_victory` |

That function then loads the stage-3 tree. The swap at SF:1324-1346 and 1365-1397 must learn the new tree.

### D7. Timeline

Focus points cost 7 days each.

| Measure | Points | Days |
| --- | --- | --- |
| Upper tree, one playthrough | 125 | 875 |
| Lower branch, one playthrough | 87 | 609 |
| Lower branch, all 60 focuses | 108 | 756 |

Lower branch by sub-branch: society 13, industry 14, army 14, marines 15, trunk 3, strait 10, Sharden 11, final 7.

Day marks counted from partition night (P):

| Day | Event |
| --- | --- |
| P+63 | Ulven operation opens |
| about P+110 | Ulven landing declared |
| about P+200 | Ulven concession awarded |
| P+170 to 270 | Luren operation |
| P+270 to 480 | Sharden operation and tender |
| about P+609 | return; day 1484 from the takeover |

During this time the council keeps working:
- about 10 sessions;
- the annual meetings at P+205 and P+565;
- three concession tenders, which shift 6 votes;
- the chancery slots shared between landing preparation, lobbying and the chairman's nomination;
- no-confidence votes as the concessions move votes.

The Judas clocks are over on the built route.

AI plan:
- one side of each pair: debt bondage, closed register, steel for guns, cartel, mercenaries, armour, escort flotilla, night landing, promise to the south, union of boards;
- the plan ends on `war_of_return`;
- in tenders the AI awards to the bidder with higher trust.

### D8. Risks and questions for the user

1. Sharden is mandatory for the return. Should `assembly_point` be bypassed if CHD no longer exists, or after two failed landings?
2. "Под управление совета" gives factories and no votes. Is annexing the island acceptable, and should NAM gain cores there?
3. District names exist only for five southern tags. Should ULV, LUR and CHD get 18 cosmetic tags (3 x 6 companies), or keep their own names?
4. The existing random dispute roll (15% a month, E:9713-9722) starts once two districts operate. Should island districts be exempt, or should the roll become a player decision?
5. The return arrives about 1484 days after the takeover. Should the side branches be trimmed to cost 1 (about 480 days)? The southern final war and the survival of EFL and AZH were not checked against that date.
6. The focus `letters_of_marque` overlaps Navis's signature decision in M6. Proposal: the signature becomes +1 raid slot and no notoriety while Navis chairs.

## Appendix E. Portrait and event plate briefs

All images follow `tools/assets/source/characters/NAM/art_prompts.json`. `<style>` means its top-level `"style"` string. `<advisor_style>` means the opening of the "NAM military leadership small portraits" prompts, with "military staff advisor" replaced by "civilian cabinet minister". The world dresses like the 1930s-40s, as the existing plates show (`ledger_handover.png`). Where a subject asks for an old cut (frock coat, morning coat, pince-nez), the subject says so outright. That overrides "Modern clothing" in `<style>` for that person, without turning the clothes into costume.

### E.1 Company heads (leader portraits, 156x210)

Runtime path: `gfx/leaders/NAM/<filename>`. Sprites go in `interface/ADISCORD_leader_portraits.gfx` as `GFX_portrait_NAM_<Name>` and `GFX_portrait_NAM_<Name>_small` on the same texture, following the Olshansky entries.

```json
[
  {
    "character": "NAM_Aristarkh_Vyazemtsev",
    "filename": "portrait_NAM_Aristarkh_Vyazemtsev.png",
    "subject": "Aristarkh Vyazemtsev, male patriarch of an old oil concern. About 67, heavy massive build, broad fleshy face, full long grey beard, heavy drooping eyelids over pale brown eyes, thick grey hair brushed back. Slow, weighty, faintly contemptuous expression. Deliberately old-fashioned dark frock coat, dark oxblood waistcoat with a gold watch chain across it, white shirt. Worn as real clothing, not costume. No glasses, no hat.",
    "prompt": "<style> + subject"
  },
  {
    "character": "NAM_Taisiya_Valts",
    "filename": "portrait_NAM_Taisiya_Valts.png",
    "subject": "Taisiya Valts, female director of a steel trust. About 52, lean angular face, hollow cheeks, short practical greying hair, thin steel-rimmed round glasses, cool grey eyes. Brisk impatient expression, lips pressed together, no smile. Plain steel-grey work jacket buttoned to the throat over a dark shirt, with a small plain round steel lapel pin that has no design on it. No jewellery.",
    "prompt": "<style> + subject"
  },
  {
    "character": "NAM_Saveliy_Kruze",
    "filename": "portrait_NAM_Saveliy_Kruze.png",
    "subject": "Saveliy Kruze, male owner of a shipping line and former skipper. About 59, sturdy build, deeply weathered ruddy face, grey skipper's fringe beard along the jaw with a shaven upper lip, a permanent squint from sea glare, light blue eyes, short grey hair. Shrewd patient expression. Plain dark navy closed tunic with no insignia, no buttons of rank, no cap.",
    "prompt": "<style> + subject"
  },
  {
    "character": "NAM_Rodion_Kalyonov",
    "filename": "portrait_NAM_Rodion_Kalyonov.png",
    "subject": "Rodion Kalyonov, male head of an arms company and former officer. About 55, square heavy jaw, sandy-grey crew cut, dark brown eyes, short straight nose, a pale healed scar across the left cheekbone, clean shaven. Cold controlled expression. Half-military sand-khaki tunic with a closed stand collar and no insignia, shoulder straps or decorations. Must not resemble the existing pale-eyed commandant Drozdov.",
    "prompt": "<style> + subject"
  },
  {
    "character": "NAM_Nazar_Guryev",
    "filename": "portrait_NAM_Nazar_Guryev.png",
    "subject": "Nazar Guryev, male boss of a labour exchange who rose from the docks. About 48, broad plain face, thick dark moustache, short dark hair, warm brown eyes, a wide one-of-the-lads grin that does not reach the eyes. Expensive brown suit that fits badly, tight at the shoulders, with an amber tie loosened at the collar. No glasses, no jewellery.",
    "prompt": "<style> + subject"
  },
  {
    "character": "NAM_Lidiya_Velyaminova",
    "filename": "portrait_NAM_Lidiya_Velyaminova.png",
    "subject": "Lidiya Velyaminova, female chair of a private bank. About 44, fine narrow features, smooth dark hair parted in the middle and drawn back, dark composed eyes, faint courteous smile. Black dress with a starched white collar, small pearl earrings, no other jewellery, no glasses. Poised, unreadable.",
    "prompt": "<style> + subject"
  }
]
```

### E.2 Cabinet (advisor icons, 62x67)

Each idea's `picture = NAM_<Name>` resolves to the sprite `GFX_idea_NAM_<Name>`. That sprite is registered in `interface/ADISCORD_leader_portraits.gfx` on `gfx/interface/ideas/NAM/portrait_NAM_<Name>_small.png`, following the `NAM_Kirill_Vykup` precedent. The four pre-war ideas (`minister_NAM_Boris_Nar`, `_Fedot_Mir`, `_Mara_Kluch`, `_Pavel_Ordyntsev`) are the same people and may point to the same sprites. A face shows no company.

```json
{
  "tool": "built-in image_gen",
  "variant": "NAM council of boards cabinet small portraits",
  "frame_source": "tools/assets/source/portar idea.psd",
  "frame_layer": 4,
  "background": "Soft grey-violet gradient matched to minister_generic examples",
  "export": "62x67; perspective at 8x size then Lanczos reduction; original frame",
  "portraits": [
    {"id": "NAM_board_premier_kornev", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Semyon_Kornev_small.png", "sprite": "GFX_idea_NAM_Semyon_Kornev", "prompt": "<advisor_style> + subject",
     "subject": "Semyon Kornev, career premier and former port traffic manager, man about 55. Long tired face, bags under grey eyes, thinning brown-grey hair, clean shaven. Patient, worn-out expression. Modest faded grey suit, plain dark tie. Almost frontal."},
    {"id": "NAM_board_defense_selivanov", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Viktor_Selivanov_small.png", "sprite": "GFX_idea_NAM_Viktor_Selivanov", "prompt": "<advisor_style> + subject",
     "subject": "Viktor Selivanov, career officer in charge of depots and garrisons, man about 52. Oblong face, short dark moustache, thinning dark hair, brown eyes, upright bearing. Dutiful weary expression. Faded grey-olive army greatcoat with turned-up collar, no insignia. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_health_veresov", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Lev_Veresov_small.png", "sprite": "GFX_idea_NAM_Lev_Veresov", "prompt": "<advisor_style> + subject",
     "subject": "Lev Veresov, ship's surgeon, man about 60. Lean grey face, short grey hair and close grey beard, steady pale blue eyes. Calm stern expression. White doctor's coat open over a dark navy naval tunic, no badges. Almost frontal."},
    {"id": "NAM_board_intelligence_bulatov", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Andrei_Bulatov_small.png", "sprite": "GFX_idea_NAM_Andrei_Bulatov", "prompt": "<advisor_style> + subject",
     "subject": "Andrei Bulatov, former port radio operator, man about 37. Thin narrow face, untidy light brown hair, sharp hazel eyes, clean shaven. Alert listening expression. Dark roll-neck sweater under a worn grey jacket. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_loren_premier", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Vsevolod_Rakhmanov_small.png", "sprite": "GFX_idea_NAM_Vsevolod_Rakhmanov", "prompt": "<advisor_style> + subject",
     "subject": "Vsevolod Rakhmanov, man about 61. Heavy round fleshy face, balding crown, big grey moustache with rounded ends, pince-nez on a black cord. Smug, comfortable expression. Deliberately old-fashioned dark three-piece suit, oxblood tie. Must not resemble the lean walrus-moustached Karamyshev. Almost frontal."},
    {"id": "NAM_board_min_reidbank_premier", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Veniamin_Kramskoy_small.png", "sprite": "GFX_idea_NAM_Veniamin_Kramskoy", "prompt": "<advisor_style> + subject",
     "subject": "Veniamin Kramskoy, man about 58. Dry narrow face, grey side whiskers, clean chin, cold grey eyes. Precise disapproving expression. Deliberately old-fashioned black morning coat, starched white stand-up collar, dark green tie. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_min_arktur_defense", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Mark_Vetlugin_small.png", "sprite": "GFX_idea_NAM_Mark_Vetlugin", "prompt": "<advisor_style> + subject",
     "subject": "Mark Vetlugin, retired officer and inspector of quota battalions, man about 51. Straight-backed, long jaw, short dark-grey hair, trimmed grey moustache, grey eyes. Correct, reserved expression. Sand-khaki tunic with closed stand collar, no insignia. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_ferrant_defense", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Matvei_Bronnikov_small.png", "sprite": "GFX_idea_NAM_Matvei_Bronnikov", "prompt": "<advisor_style> + subject",
     "subject": "Matvei Bronnikov, man about 50. Stocky, wide face, very thick dark eyebrows, short dark hair greying at the sides, clean shaven. Blunt hard expression. Black leather jacket over a steel-grey shirt and dark tie, plain round steel lapel pin. Almost frontal."},
    {"id": "NAM_board_min_navis_defense", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Efrem_Batalov_small.png", "sprite": "GFX_idea_NAM_Efrem_Batalov", "prompt": "<advisor_style> + subject",
     "subject": "Efrem Batalov, merchant navy captain, man about 56. Weathered face, grey wedge-shaped beard, dark eyes under heavy brows. Gruff confident expression. Plain merchant navy peaked cap without badge, black pea coat with collar up, teal-grey scarf. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_min_loren_economy", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Boris_Nartov_small.png", "sprite": "GFX_idea_NAM_Boris_Nartov", "prompt": "<advisor_style> + subject",
     "subject": "Boris Nartov, inspector of production quotas from an oilfield accounts office, man about 54. Stout, round face, round wire glasses, thin combed-over hair, small moustache. Fussy careful expression. Oxblood waistcoat, white shirt with black sleeve protectors, no jacket. Almost frontal."},
    {"id": "NAM_board_bank_nominee", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Leonid_Belov_small.png", "sprite": "GFX_idea_NAM_Leonid_Belov", "prompt": "<advisor_style> + subject",
     "subject": "Leonid Belov, bank accounts officer for ship-repair workshops, man about 41. Narrow pale face, mousy brown hair slicked flat, thin pencil moustache, watchful brown eyes. Polite calculating expression. Dark suit, starched white collar, bottle-green tie. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_ferrant_economy", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Varvara_Stavrova_small.png", "sprite": "GFX_idea_NAM_Varvara_Stavrova", "prompt": "<advisor_style> + subject",
     "subject": "Varvara Stavrova, woman about 47. Severe oval face, dark hair in a tight bun, heavy horn-rimmed glasses, dark eyes. Unsmiling exacting expression. Steel-grey tailored suit, dark blouse, plain round steel lapel pin. Almost frontal."},
    {"id": "NAM_board_min_smenkom_health", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Faina_Odintsova_small.png", "sprite": "GFX_idea_NAM_Faina_Odintsova", "prompt": "<advisor_style> + subject",
     "subject": "Faina Odintsova, works clinic doctor, woman about 42. Short dark-blonde hair, tired grey eyes with shadows, plain face without makeup. Kind but exhausted expression. White coat over a dark brown dress. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_min_reidbank_health", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Yulia_Savitskaya_small.png", "sprite": "GFX_idea_NAM_Yulia_Savitskaya", "prompt": "<advisor_style> + subject",
     "subject": "Yulia Savitskaya, hospital trustee, woman about 36. Fair hair in a strict bun, thin rimless glasses, light blue eyes, fine features. Cool attentive expression. Dark bottle-green jacket, white starched collar. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_ferrant_education", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Fedot_Ermolin_small.png", "sprite": "GFX_idea_NAM_Fedot_Ermolin", "prompt": "<advisor_style> + subject",
     "subject": "Fedot Ermolin, works instructor and curator of registry schools, man about 58. Square weathered face, grey crew cut, grey moustache, deep lines. Strict fatherly expression. Steel-grey work jacket over a collarless shirt, plain round steel lapel pin. Almost frontal."},
    {"id": "NAM_board_labor_nominee", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Petr_Litvinov_small.png", "sprite": "GFX_idea_NAM_Petr_Litvinov", "prompt": "<advisor_style> + subject",
     "subject": "Petr Litvinov, training foreman from the island labour exchange, man about 46. Weathered broad face, short brown hair, brown eyes, clean shaven. Earnest stubborn expression. Brown corduroy jacket over a shirt and amber tie. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_min_arktur_education", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Innokenty_Bakhmetyev_small.png", "sprite": "GFX_idea_NAM_Innokenty_Bakhmetyev", "prompt": "<advisor_style> + subject",
     "subject": "Innokenty Bakhmetyev, former military academy lecturer, man about 63. Thin face, grey goatee, receding grey hair, pince-nez. Pedantic sceptical expression. Old sand-khaki uniform tunic without shoulder boards, closed stand collar. Almost frontal."},
    {"id": "NAM_board_min_arktur_intelligence", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Tikhon_Zarubin_small.png", "sprite": "GFX_idea_NAM_Tikhon_Zarubin", "prompt": "<advisor_style> + subject",
     "subject": "Tikhon Zarubin, man about 49. Shaven head, heavy brow, small dark eyes with a heavy unblinking stare, clean shaven. Menacing stillness. Black tunic with closed stand collar and a plain leather cross-belt, no insignia. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_navis_intelligence", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Raisa_Chaykina_small.png", "sprite": "GFX_idea_NAM_Raisa_Chaykina", "prompt": "<advisor_style> + subject",
     "subject": "Raisa Chaykina, woman about 39. Reddish hair under a dark navy beret, freckles, green eyes, attentive sidelong look. Guarded alert expression. Dark navy raincoat with collar up over a teal-grey scarf. Three-quarter view toward viewer's left."},
    {"id": "NAM_board_min_navis_foreign", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Pavel_Ordyntsev_small.png", "sprite": "GFX_idea_NAM_Pavel_Ordyntsev", "prompt": "<advisor_style> + subject",
     "subject": "Pavel Ordyntsev, envoy for external relations, man about 49. Even oval face, dark hair with grey temples, clean shaven, calm grey eyes. Diplomatic neutral expression. Dark navy double-breasted suit, white shirt, teal-grey tie. Almost frontal."},
    {"id": "NAM_board_min_loren_foreign", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Yulian_Dashkov_small.png", "sprite": "GFX_idea_NAM_Yulian_Dashkov", "prompt": "<advisor_style> + subject",
     "subject": "Yulian Dashkov, man about 45. Narrow fox-like face, thin nose, dark hair combed back, clean shaven, light hazel eyes. Polite practised smile. Light grey summer suit, oxblood bow tie. Must not resemble the broad-faced Olshansky. Three-quarter view toward viewer's right."},
    {"id": "NAM_board_min_smenkom_foreign", "runtime": "gfx/interface/ideas/NAM/portrait_NAM_Rashid_Ildarov_small.png", "sprite": "GFX_idea_NAM_Rashid_Ildarov", "prompt": "<advisor_style> + subject",
     "subject": "Rashid Ildarov, man about 38. Swarthy lean face, neat short black beard, black hair, sharp dark eyes. Quick appraising look. Dark brown three-piece suit, amber tie, heavy gold signet ring on a hand raised to the lapel. Three-quarter view toward viewer's left."}
  ]
}
```

**Check against the in-game text.**
- I found no contradictions with `NAM_board_*_desc` (lines 5556-5558 and 6529-6535 of the Russian file) or with `minister_NAM_Pavel_Ordyntsev_desc` (nsb:465).
- Two looks are refined to fit the text:
  - Белов keeps the accounts of ship-repair workshops (LOC:5558), so he is drawn as an accounts officer rather than a teller.
  - Нартов carries the trait "Инспектор производственных квот" (traits:144), so he is drawn as a quota inspector from an oilfield accounts office. The sleeve protectors stay.
- Селиванов has no rank in the text, and `<style>` forbids insignia, so he reads as a colonel only through his bearing and the greatcoat.
- I added explicit "must not resemble" notes for four existing faces that the roster nearly duplicates: Olshansky/Dashkov, Karamyshev/Rakhmanov, Drozdov/Kalyonov and Severtsev/Kruze.

### E.3 Company visual key

The colours come from the existing marks in `gfx/interface/NAM_basin/board_company_marks.png`. The cue has to read at the 36x48 face area of an icon, so it sits at the collar and tie.

- **Loren** (Лорэн): burnt orange and oxblood. An oxblood waistcoat, tie or bow tie, and an old-money cut: watch chain, pince-nez on a cord, sleeve protectors.
- **Ferrant** (Феррант): steel blue-grey. Steel-grey workwear or a severe suit buttoned high, with a plain round steel lapel pin that has no design.
- **Navis** (Навис): teal and dark navy. Navy wool cut for weather (pea coat, raincoat, tunic) and a teal-grey scarf or tie. Sea-weathered skin.
- **Arktur** (Арктур): sand-khaki and black. A closed stand collar of half-military cut, with no insignia or shoulder boards.
- **Smenkom** (Сменком): amber and brown. Brown cloth (corduroy, a badly fitting brown suit) and an amber tie. Faces of men and women who rose from the floor.
- **Reidbank** (Рейдбанк): sage and bottle green on black and white. A starched white collar on dark clothes, with a bottle-green tie or jacket.
- **Career officials:** no company colour. Faded grey and olive, worn cloth.

Arktur and Smenkom marks are both ochre. Keep Arktur's clothing black and khaki, and Smenkom's brown and amber.

### E.4 Event plates

- **Format:** 507x184 px, RGB PNG, fully opaque. This size is required by `tools/tests/test_adiscord_event_ui.py:432-488`.
- **Style:** match the existing plates, for example `ledger_handover.png`. That means 1930s-40s photoreal stills in muted colour with fine horizontal scanlines. No readable text or real emblems.
- **Location and registration:**
  - Files go in `gfx/event_pictures/standard/country/<scene>.png`.
  - Each `<scene>` is added to `FINISHED_COUNTRY` in `tools/builders/build_adiscord_event_pictures.py`.
  - The builder writes the sprite `GFX_event_adiscord_<scene>` into `interface/ADISCORD_event_art.gfx`. The lead runs `--check`, then `--apply`, then a second `--check`.
  - Do not register these sprites in a NAM `.gfx` file: that fails the art test.
- **Company plates:**
  - Keep the left third as a flat field in the company colour. After generation, paste the company's frame from `board_company_marks.png` (one 50x36 frame) onto that field. Do not let the image tool draw the logo.
  - The head of the company stands in the right third. Generate each plate after the head's portrait, using the portrait as the identity reference.

| Scene | Composition |
| --- | --- |
| `nam_board_loren` | Vyazemtsev at a tall window of a panelled office; behind the glass, island tank farms and a derrick against an orange dusk. |
| `nam_board_ferrant` | Valts on a gantry walkway above a rolling mill, with a glowing billet and men in steel-grey jackets below. |
| `nam_board_navis` | Kruze on a wet quay at night, a line of moored coasters and cargo nets behind him, teal harbour lights. |
| `nam_board_arktur` | Kalyonov between stacked rifle crates in an arsenal shed, sand-khaki guards checking serial numbers. |
| `nam_board_smenkom` | Guryev leaning on the counter of a crowded hiring hall, a queue of workers with caps in hand, amber lamplight. |
| `nam_board_reidbank` | Velyaminova at a green-baize desk before an open vault door, with clerks carrying ledgers past marble columns. |
| `nam_board_session` | A long council table seen from its foot: six delegations along the sides, each in its house colours, and the chairman's high-backed seat at the far end. Faces stay small, so the plate fits any chairman. |
| `nam_board_chair_falls` | In the same hall, the chairman's high-backed chair is pulled out and empty. One man walks out in the back light while another hand rests on the chair's back. No identifiable face, because the plate is reused for all seven chairmen. |
| `nam_judas_weber` | Dockers voting by raised hands in a warehouse among cranes and bales. Weber, whose look follows `portrait_NAM_Yaroslav_Weber.png`, speaks from a crate at mid-distance. |
| `nam_judas_karamyshev` | Coast guard officers in dark greatcoats round a wardroom table at a patrol-boat base, a grey cutter visible through the porthole. Karamyshev, after `portrait_NAM_Rostislav_Karamyshev.png`, sits at the head. |

### E.5 Заметка для пользователя

Всего 38 изображений: 6 портретов глав компаний 156x210 (в `gfx/leaders/NAM/`), 22 иконки министров 62x67 с рамкой из `portar idea.psd` (в `gfx/interface/ideas/NAM/`) и 10 картинок событий 507x184 без прозрачности (в `gfx/event_pictures/standard/country/`).
Оригиналы, исходники и промпты сохраняете вы сами (AGENTS.md); в мод кладутся только эти игровые копии, а превью удаляются после работы.

