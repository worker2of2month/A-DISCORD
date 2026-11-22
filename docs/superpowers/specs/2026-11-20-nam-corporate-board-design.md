# NAM corporate exile: the council of boards

Status: M0-M8, the reward layer (appendix C), the compact corporate tree of
68 focuses with its invasion lanes, island wars, mainland cells and
"Операция \"Посейдон\"" (appendix D), the subversive operations and the
partition claims (appendix F), the wartime tree of the return (appendix G)
the tree of the Directory on the mainland that follows a won return
(appendix H), and the partition of the South with the Directory's last tree
that follow a won War for the South (appendix I) are implemented in the
script. Nothing was checked in the running game. Line numbers are
hints; the NAM files are edited in parallel, so re-read every target before
inserting and splice by section, never by line.

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
14. Focus rewards follow The Fire Rises: every focus gives several rewards of
    different kinds, important focuses fire story events, and the amounts must
    be felt ("300 людей условные - ни о чём"). Rewards are not only stock: some
    focuses enact laws of the council that cannot be changed afterwards ("пусть
    дают законы разные, которые сменить нельзя"), and some lower the level of
    social development while raising another track ("понижает уровень соц.
    развития, но повышает другое"). A focus may carry more than five reward
    kinds, up to seven, when its story asks for it ("пусть даёт не только эти
    награды"); C.1 and C.12.
15. The great war against Rahma, Sardan and Kadir stays its own stage
    between the return and the War for the South. Asked whether it must
    remain, the user answered: "Да, должна". Every playthrough passes it;
    treaties may make it smaller but never replace it (appendix H.4).

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
  `NAM_south_war_focus` and back, through the return war and on the
  mainland: loading `NAM_mainland_directory_focus` does not end the council.
  The council ends only with the route (`NAM_board_end_operations`, from
  `nam:on_annex`); appendix H.6 lists what changes scale on the mainland.
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
- Keep public: the lot pays +10 capital a month in `NAM_corp_monthly` while
  the treasury holds it (+5 with `quay_chain`), both bidders lose 5, and the
  lot returns as a motion. It gives the industrial policy nothing.
- The first award of each lot also opens the winner's next charter line
  (appendix C.2); a retender award does not.
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
mission times out. The pyramid shows who would take the
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

### The corporate tree (68 focuses)

One tree in one source file, `focus_trees/NAM/exile_corporate/focuses.txt`,
mirrored around x 18 (columns 0-36, rows 0-10). Every focus gets a full reward
tied to the mechanics above: a seat, a slot, an operation, a programme with a
price and a duration, a concrete delivery. No focus rewards a tooltip alone,
and no branch is a chain of the same bonus. Contract in appendix D, reward
rules in appendix C. Lanes:

- centre: the chancery trunk, the Judas turning points, the chancery pair,
  "Материк по описи", "Стол на шесть приборов", the partition night and
  "Операция \"Посейдон\"" directly under it;
- Karamyshev lane (x 8-14) and Weber lane (x 22-28): the operations against
  each Judas, the kill, the law focus, the pair and one capstone per side;
- left wing (x 2-7): capital income, zones, tender terms, the re-gating of
  `NAM_corp_sell_steel` and `NAM_corp_labour_contract`; its outer lane (x 0-9,
  rows 7-10) is war economy and supply;
- right wing (x 29-34): readiness, the drill, arms; its outer lane (x 27-36,
  rows 7-10) is fleet, marines and the three island operations, which open
  early from "Флот компаний" and "Подряд на высадку".

`NAM_board_partition_night` needs a majority, both turning points of the
centre and, through the chancery pair, both kills. Its reward divides the
mainland in advance between the two companies with the most votes
(`NAM_board_partition_efl` / `_azh`, frozen), replacing the round-robin of
`NAM_corp_assign_district` for those districts, opens the subversive
operations and the claims (appendix F), seeds the mainland cells and
dispatches the backers' choice (event 180). "Операция \"Посейдон\"" opens 90
days after it on its material conditions, declares the war of return and
hands the war to the wartime tree one day later (appendix G).

Seized islands are annexed, not subject countries. The concession operator,
named by `NAM_board_isl_owner^<island>`, counts 2 votes in the recount beside
the districts (Sharden 1 after the southern promise) and draws a dividend.

Temporary exception to the focus-tree rules: the two kill focuses have no
live alternative while their WIP partners are closed. The Karamyshev and Weber
lanes carry live exclusive pairs below the kills (appendix C.4). A test pins
the exception so it is removed with the WIP focuses.

### The wartime tree of the return (32 focuses)

`NAM_return_war_focus` (`focus_trees/NAM/return_war/focuses.txt`) replaces
the corporate tree for the war of return and gives it back on every terminal
path: two fronts, the strait, the districts and the council at war, five
locked war laws, two development trades, the form of rule after victory, and
the endings (victory, Eflor's surrender, three pauses, defeat). Contract in
appendix G.

### The Directory on the mainland (82 focuses)

`NAM_mainland_directory_focus` "Континент правлений"
(`focus_trees/NAM/mainland_directory/focuses.txt`) loads at the victory of
the war of return in both forms of rule and keeps the council running at
the scale of a continent: the form of the joint state, the conquered land of
Eflor and Azhar, the home districts, the council of six, the desert war
against Kadir, Sardan and Rahma as its own stage, four southern lanes and
"Час юга", which gives the order of the War for the South. Contract in
appendix H.

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
`NAM_board_prepare_dismissal`) and `NAM_board_end_operations`, which runs
only at the end of the route (`nam:on_annex`), not at the return: the
mainland tree's loader `NAM_mdr_begin` keeps the council running. It keeps
the council laws of C.12, which the mainland tree succeeds or repeals by name
(appendix H.5) and the annexation repeals (`NAM_board_repeal_laws`). The Judas motions read
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
`NAM_judas_<operation>`, fifteen spirits, the banded killings and the camp
report in the two portrait cards of the `NAM_two_judases` category. Hovering
over a card shows `NAMJudasWeberBlock` or `NAMJudasKaramyshevBlock`. It leaves `NAM_judas_dividend_surcharge`
for the annual dividend to consume and clear. Under the tree's exclusive
pairs nine of the ten operations are reachable in one campaign; that is
intended.

Status: packages 5-8 are implemented. The focus layer (package 7) follows
appendix C: rewards in one writing order with shared script shapes, charter
lines of the industrial policy opened by the tenders and nine wing focuses,
alive and dead branches with the three-band spoils, seven exclusive pairs,
story events `ADISCORD_nam_story.50-96`, the council decisions D1-D6, the
Directory campaigns in `NAM_public_campaigns`, the development reset at the
flight with six Directory programmes, and the end of the mainland leftovers at
the flight or the takeover. The focus-effects guide section "Корпоративное
изгнание NAM" describes the same contract (package 8).

Status: the corporate tree is the compact tree of appendix D: 68 focuses in
one mirrored tree with 11 exclusive pairs; 45 focuses of the former upper tree
and lower branch are folded into the focuses that stay, two moved to the
wartime tree and one moved to the mainland tree (table in D3). The invasion
programmes of `NAM_board_invasion`, the island wars of `NAM_board_islands`,
the mainland cells with the enemy's `NAM_cells_counter`, the backers' choice
(event `ADISCORD_nam_story.180`) and "Операция \"Посейдон\"" with its 90-day
window follow D5-D8.

Status: the subversive operations and the partition claims are implemented
as appendix F describes (category `NAM_board_subversion`, events 135-137).

Status: the wartime tree of the return is implemented as appendix G
describes: `NAM_return_war_focus` with 32 focuses, the category `NAM_rtw_war`
with decisions W1-W12, five locked war laws, two development trades, the
endings with their transfers, and events `ADISCORD_nam_story.138-169`.

Status: the tree after the return is implemented as appendix H describes:
`NAM_mainland_directory_focus` with 82 focuses, thirteen locked laws of the
continent, the desert stage with its treaties and lapse, the categories
`NAM_mdr_army` and `NAM_mdr_south_office` beside the existing
`NAM_consolidation` and `NAM_free_zones`, and events
`ADISCORD_nam_story.181-222`.

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
- Island categories under the takeover: `NAM_two_judases`, `NAM_free_zones`,
  `NAM_public_campaigns` and `NAM_directory_development` (appendix C.9);
  `NAM_board_invasion` (after a lane opener or the partition night),
  `NAM_board_islands` (after the first strait operation) and
  `NAM_board_subversion` (after the partition night), the enemy's
  `NAM_cells_counter` for EFL and AZH (appendices D and F), and during the war
  of return `NAM_rtw_war` (appendix G). Add no other category.

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

Appendices A, B and E were drafted against an earlier version of the core.
Where they differ, sections M1-M10 win. Appendix C is the maintained contract
of the reward rules, appendix D of the compact corporate tree, appendix F of
the subversive operations and the partition claims, appendix G of the wartime
tree of the return, appendix H of the mainland tree, appendix I of the
partition of the South and the dominion tree. Appendix C still names focuses by the ids they had before
the compaction; a folded id stands for its absorber in the D3 table, and its
rows, laws, unlocks and events are those of the absorber. Known differences:

- A.6 (leader traits) is replaced by the table in M6, which adds the debuffs.
- A.7 point 1 holds: a public lot pays +10 capital a month and gives the
  industrial policy nothing (M4, appendix C.2).
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
    `GFX_NAM_board_resolution_marker` (20x20) and `GFX_NAM_board_seat_selected`
    (single frame, cornered tile, border 6; a cornered tile ignores frames);
  - spirit pictures `GFX_idea_NAM_board_no_confidence`,
    `GFX_idea_NAM_board_sanction_<company>` for the six companies,
    `GFX_idea_NAM_judas_weber_committees`, `_karamyshev_watch`, `_strike`,
    `_mutiny`, `_port_peace`, `_staff_oath` and
    `GFX_idea_NAM_board_loan_service`. An idea's `picture` takes the name
    without the `GFX_idea_` prefix only if that is how the neighbouring NAM
    ideas reference theirs; check before use.
- Appendix A writes `NAM_corp_zone_slots`; the real variable is
  `NAM_free_zone_slots`.
- Appendix C is the maintained contract of the implemented focus layer; the
  focus source and its reward keys hold the values. Kornev is removable from
  the start (M2), so no reward "frees" the premier's seat.

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
- Weber's card names the target. Its tooltip explains why the committee chose it. The target's pyramid card carries a marker, and the council line warns at 14 days.

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
- Karamyshev's card shows the target, with the reason on hover and a warning at 14 days.

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

## Appendix C. Focus rewards of the council of boards

This appendix is the maintained contract of the focus layer: the upper corporate tree
`NAM_exile_corporate_focus` (64 playable focuses and six closed stubs:
`escheated_throne`, `treaty_two_judases`, `silence_after_settlement`,
`proxy_parliament`, `escheated_land_auction`, `ministries_in_concession`) and
the interregnum tree `NAM_exile_interregnum_focus` (eight playable focuses; the
finals `seals_committees` and `seals_officers` stay closed). The focus sources
are `focus_trees/NAM/exile_corporate/focuses.txt` and
`focus_trees/NAM/exile_interregnum/focuses.txt`; the files in
`common/national_focus/` are generated from them. The values of each reward
live in the focus source and its `NAM_board_<focus>_reward_tt` key; this
appendix fixes the rules they follow. Ids are written without the
`NAM_board_` prefix where the tree makes it unambiguous. The 46 focuses of the
lower branch follow the same writing order, script shapes and tooltip layout;
their own rules (three more reward kinds, the all-native exception, the mirror
rule) are in appendix D.

Companies: 1 Loren, 2 Ferrant, 3 Navis, 4 Arktur, 5 Smenkom, 6 Reidbank.
"Capital" is `NAM_corp_capital`, "readiness" `NAM_revenge_readiness`,
"committees" `NAM_judas_weber`, "officers" `NAM_judas_karamyshev`.

### C.1 Writing order of a reward

Inside `completion_reward`, in this order:

1. `unlock_decision_tooltip = <decision>` directly followed by
   `custom_effect_tooltip = <decision>_unlock_tt`, one pair per unlocked
   decision, campaign or development programme. The `_unlock_tt` value starts
   with "После применения решения: " (pinned by
   `test_visible_decision_summaries_share_one_lead_in_across_trees`).
2. Native effects (`add_political_power`, `add_manpower`,
   `add_equipment_to_stockpile`, `army_experience`, `navy_experience`,
   `add_command_power`, `add_stability`, `add_popularity`, `add_timed_idea`)
   and the development call of C.8. All of them print their own line and stay
   outside every `hidden_effect`.
3. `effect_tooltip = { add_ideas = NAM_board_preview_<x> }` for a fixed
   aggregate. The preview ideas (`allowed = { always = no }`) are in
   `common/ideas/ADISCORD_nam_resource_war_ideas.txt`; the applied delta equals
   the preview (`test_upper_reward_previews_equal_the_applied_deltas`).
4. One `custom_effect_tooltip = NAM_board_<focus>_reward_tt`, or the
   `_alive_tt` / `_dead_tt` pair of C.3. An all-native reward has no
   `_reward_tt`, because it would only restate native lines.
5. One `hidden_effect` with the script. The story event call is its last line.

The two kill focuses (`posthumous_signature`, `last_debtor`) keep their single
`hidden_effect` with the kill effect and fire their story event from a second
`hidden_effect` after it (`tools/tests/test_adiscord_party_representation.py`
unpacks exactly one entry from the first).

Script shapes, all in `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`:

| Result | Shape |
| --- | --- |
| Trust | temp `NAM_board_trust_input_1` .. `_6` (signed, unset reads 0), then `NAM_board_trust_package = yes`; one package per reward or answer; it resets the inputs and recounts once |
| Capital | temp `NAM_corp_capital_change` (negative spends), then `NAM_corp_capital_add = yes` |
| Readiness | `add_to_variable = { var = NAM_revenge_readiness value = <n> }`, then `NAM_revenge_readiness_clamp = yes` |
| Camp support | temp `NAM_judas_camp_input` (1 committees, 2 officers) and `NAM_judas_delta_input`, then `NAM_judas_support_change = yes`; no effect once that man is dead |
| Charter line | temp `NAM_board_company_input` (1-6), then `NAM_board_grant_charter = yes` (C.2) |
| Fixed aggregate | `add_to_variable` on `NAM_board_focus_pp`, `_stab`, `_output`, `_construction`, `_goods`, `_org` or `_research`, then `NAM_board_recount = yes` |
| Fuel | `add_to_variable` on `NAM_open_fuel_reserve`, then `NAM_open_fuel_release = yes` |
| Directory campaign place | `add_to_variable = { var = NAM_dir_campaign_slots value = 1 }`, then `clamp_variable = { var = NAM_dir_campaign_slots max = 3 }` (C.7) |
| Vote until the next annual meeting | `add_to_variable = { var = NAM_board_proxy_votes^<company> value = 1 }`, then `NAM_board_recount = yes` |
| Dead-branch spoils | temp `NAM_judas_camp_input` and `NAM_corp_capital_change` (the full replacement), then `NAM_judas_pay_spoils = yes` |
| Story event | `country_event = { id = ADISCORD_nam_story.<N> days = <d> }` as the last line of the `hidden_effect` |

Every "all six companies" result is written with the trust package and six
inputs, not with a loop. A loop of the council follows the loop contract
stated above `NAM_board_recount`: its own temp counter is set to the loop
start minus one directly before `for_loop_effect`, the first body statement
advances it by 1, arrays are indexed only through that counter, and the loop
`value = NAM_board_loop_step` is never read. Counters per site:
`NAM_board_petitioner` (focus rewards), `NAM_board_partition_index`
(`partition_night`), `NAM_board_expiry_company` (event `.437`),
`NAM_board_story_company` (story events). The counts are pinned by
`test_board_loops_never_read_the_native_loop_value` as `[9, 2, 4]` (effects,
events, corporate focus source).

**Kinds.** Every playable focus gives two to seven rewards of different kinds
(the author lifted the ceiling from five when council laws and development
trades joined the rewards); the typical focus gives three or four. Kinds:
political power, manpower, equipment (convoys, fuel), experience or command
power, stability or technocracy popularity, capital, readiness, trust given,
rival camp support lowered, decision or programme unlock, lasting rule (slot,
vote, charter line), aggregate or timed spirit or monthly income, building,
development, council law (L, C.12) and development trade (W, C.12).
Costs (trust taken, camp support raised, capital spent, humanism popularity)
and the story event do not count. Two rows of one kind count once. Pinned by
`test_every_playable_focus_gives_two_to_seven_kinds_of_reward`, whose table
mirrors the source. The six one-week interregnum focuses are the only two-kind
focuses; each kill adds one native row that holds in every band
(`posthumous_signature` manpower, `last_debtor` rifles).

**Tooltip layout.** Every custom tooltip of this route follows the layout
rules pinned by `test_council_tooltips_follow_the_layout_standard`: one fact
per line (`Label: value icon`, the value coloured, the number before its
icon); a group gets one yellow heading and two-space indented rows with
`$NAM_board_short_<n>$` names; `§G` for what the council gains (including
lower rival support), `§R` for losses and prices, `§Y` for neutral amounts;
fallbacks and conditions on their own indented line under the fact; delayed
results under their own heading ("После возвращения:", "При передаче
печатей:", "В любом исходе:"); at most 55 visible characters per line
(`_unlock_tt` up to 100); no value starts or ends with `\n` and no `\n\n\n`;
native lines are never restated. Texticons follow rule T17: the renderer drops
the character directly after a `£name` token, so one space precedes a line
break, punctuation, a closing bracket, an escaped quote or `§!`, and two spaces
precede anything that needs a visible gap. Pinned also by
`NamDirectoryCampaignTests.test_council_texticons_keep_the_next_character`.

### C.2 Charter lines of the industrial policy

The spirit `NAM_board_industrial_policy` starts with penalties only. Each
company has a charter level 0-2 in `NAM_board_charter` (size 7): level 1 opens
its rate A, level 2 rates A and B. A closed line applies minus its factor,
whatever the company's stance or industries; an open line applies the live
potential (weight x factor while the company is "for", 0 while it waits or
holds no industry, -0.5 x the potential while it boycotts).

| Company | Rate A (factor) | Rate B (factor) |
| --- | --- | --- |
| 1 Loren | factory output 1 | construction 2 |
| 2 Ferrant | factory output 2 | efficiency growth 3 |
| 3 Navis | dockyard output 3 | dockyard construction 3 |
| 4 Arktur | factory output 3 | max efficiency 1 |
| 5 Smenkom | construction 2 | efficiency growth 2 |
| 6 Reidbank | construction 3 | consumer goods -1 |

Day one, no line open: factory output -6%, construction -7%, efficiency growth
-5%, dockyard output -3%, dockyard construction -3%, max efficiency -1%,
consumer goods +1%, research -10%. There is no flat efficiency base and public
lots give the spirit nothing; each lot still held by the treasury pays +10
capital a month in `NAM_corp_monthly` (+5 with `quay_chain`).

Levels rise only through `NAM_board_grant_charter`. A grant to a company whose
two lines are open pays +40 capital instead. Callers:

- the tender award: `NAM_board_close_tender` grants the winner's next line on
  the first award of each lot (`NAM_board_lot_awarded`); a retender award and
  "Оставить в казне" open nothing;
- nine focuses of the two industrial wings, none behind an exclusive choice:

| Company | Focus grants |
| --- | --- |
| 1 Loren | `future_output_pledge`, `loren_priority` |
| 2 Ferrant | `concession_courts` |
| 3 Navis | `island_fleet_shares`, `private_strait` |
| 4 Arktur | `last_voyage_rifles` |
| 5 Smenkom | `corporate_mass_housing`, `residency_for_hire` |
| 6 Reidbank | `bearer_warrant` |

Research comes from `NAM_board_focus_research` (read by `NAM_corp_refresh`
into `NAM_corp_mod_research`): -0.10 at the takeover, +0.10 each from
`foundry_mark` (right wing) and `harbour_exchange` (left wing), shown by the
preview `NAM_board_preview_research`. No focus of the centre or of the
Karamyshev and Weber lanes opens a line or a research step. The charter grant
has no dummy preview, because its delta depends on the stance on the
completion day; the nested key `NAM_board_charter_grant_<n>_tt` shows the line
that opens and its live potential. Pinned by
`test_charter_lines_open_in_order_and_close_with_penalties`,
`test_first_tender_award_opens_the_winners_line_once` and
`test_eleven_wing_focuses_grant_charters_and_two_raise_research`; the two
lower-branch capstones `arsenal_of_the_boards` (Ferrant, input 2) and
`first_wave` (Arktur, input 4) are the tenth and eleventh grants.

### C.3 Alive and dead branches

A focus whose camp operation or rule needs the man alive splits its reward:

```
if = {
	limit = { has_idea = NAM_judas_karamyshev_watch }
	custom_effect_tooltip = NAM_board_<focus>_alive_tt
	hidden_effect = { ... }
}
else = {
	if = {
		limit = { check_variable = { NAM_judas_karamyshev_end < 2 } }
		<native replacement, full>
	}
	else_if = {
		limit = { check_variable = { NAM_judas_karamyshev_end < 3 } }
		<native replacement, half>
	}
	custom_effect_tooltip = NAM_board_<focus>_dead_tt
	hidden_effect = { ... NAM_judas_pay_spoils = yes ... }
}
```

Committees use `has_idea = NAM_judas_weber_committees` and
`NAM_judas_weber_end`. The engine shows only the branch that applies. A
development call sits before the `if`, so both branches get it. An unlock that
needs the man alive (his operation, the campaigns "Агитаторы на жалованье" and
"Мятежники в погонах") sits inside the alive branch only.

**Three-band spoils.** The kill effects `NAM_island_eliminate_weber` and
`NAM_island_eliminate_karamyshev` store the band in `NAM_judas_weber_end` /
`NAM_judas_karamyshev_end`: 3 (support 60+), 2 (30-59), 1 (below 30). A dead
branch keeps the part both branches share and pays its replacement at 100% /
50% / 0% by that band; a missing variable reads as band 1. The capital part goes
through `NAM_judas_pay_spoils`; a native part uses the band `if` above. The
tooltip names the share through `NAMJudasKaramyshevSpoils` /
`NAMJudasWeberSpoils`. Split focuses: `founders_of_unrest`,
`inheritance_without_empire`, `uncrested_buyers`, `privatise_governorate`,
`hereditary_roll`, `old_settlers_oath`, `district_buyout`, `price_of_silence`,
`elected_in_absentia`, `widows_share`, `subsidised_opposition`,
`mourning_licence`. Pinned by
`test_dead_branches_pay_their_replacement_by_the_kill_band`.

The kill tooltips `NAM_island_eliminate_karamyshev_tt` and
`NAM_island_eliminate_weber_tt` show the band that applies now in full
("Если завершить сейчас (<band>): ...", chosen by
`NAMJudas<Man>OutcomeNow`), the other two bands as one line each, and the
results that hold in every band.

### C.4 Exclusive pairs

Seven `mutually_exclusive` pairs; the AI plan in
`common/ai_strategy_plans/ADISCORD_NAM_plans.txt` names one side of each live
pair.

| Pair | Lane | One side | Other side | AI |
| --- | --- | --- | --- | --- |
| `original_stays_home` / `sole_vote_holder` | centre | the council protects itself: third chancery slot, longer no-confidence immunity, capital | the council plays for votes: third chancery slot, D1, the keeper vote of event 73 | `sole_vote_holder` |
| `double_lock_warehouse` / `loren_receipt` | left | the creditors' route: cheaper dividend rule, fuel now | Loren's route: refinery (capital fallback), a Loren vote, the expedition of events 54 and 83 | `loren_receipt` |
| `hereditary_roll` / `old_settlers_oath` | Karamyshev | buy the officers: capital, cheaper "Удовлетворить требования" | out-arm them: D2, manpower, readiness, "Арестовать зачинщиков" without a company | `hereditary_roll` |
| `subsidised_opposition` / `incumbents_credit` | Weber | buy the committees: cheaper "Уступить комитетам", the council tools of its line | weaken the enemy abroad: D5 and the social line | `incumbents_credit` |
| `factory_guard` / `captains_share_qualification` | right | the army: organisation preview, manpower, readiness, army development | the fleet: convoys, naval experience, capital, the newsreel campaign | `factory_guard` |
| `posthumous_signature` / `escheated_throne` | Karamyshev | the kill, always available | closed stub | - |
| `last_debtor` / `treaty_two_judases` | Weber | the kill, always available | closed stub | - |

Each live side fires its own story event (C.5) and rejoins its lane, so both
alternatives reach the capstones and the final. Pinned by
`test_island_focus_diagram_and_duration` (seven pairs) and
`test_partition_requires_every_compatible_branch_and_only_spared_leaders_are_wip`.

### C.5 Story events

- Namespace `ADISCORD_nam_story`, ids 50-96, in
  `events/ADISCORD_nam_resource_war_events.txt`, one commented section
  "Council of boards: story events" after story event 44. Every id is
  registered in `tools/data/adiscord_event_ids.json` (subsystem `nam_story`).
- One source per event: the focus reward that names it, as the last line of its
  `hidden_effect` (the kill focuses from their second `hidden_effect`). Event
  82 comes from the interregnum focus `open_customs`; event 83 comes only from
  event 54, ninety days later. `seals_boards` fires the existing takeover event
  `ADISCORD_nam_resource_war.100` and has no story event of its own.
- `is_triggered_only = yes`, `fire_only_once = yes`. The trigger reads
  `has_country_flag = NAM_board_opened` and `NAM_board_ended = 0`, never
  `NAM_board_operable`: an offer that arrives while the council is paralysed
  is delayed, not discarded. Event 65 also needs
  `has_idea = NAM_judas_karamyshev_watch`, event 83 `has_variable =
  NAM_story_54_choice`, event 82 `has_idea = NAM_interregnum_power_vacuum`.
- The first option is the one an unattended event takes on timeout. It is
  never a pure gain: it costs capital (at most 40) or political power, or at
  most -3 trust to a company that asked. Event 82, the lane choice of the
  interregnum, is the only exemption.
- Native effects print themselves; the option key `NAM_story_<N>_<option>_tt`
  covers capital, trust, votes, readiness and camp support only. Camp rows sit
  inside the alive `if` on the camp idea.
- Development answers, each with a price and written natively outside the
  `hidden_effect`: 86 c (cultural), 89 c (economic), 90 b (state), 93 c
  (social system), all `ADISCORD_programme_<track>_development`.
- Descriptions are prose on light paper: no colour codes, ASCII `-` and `"`,
  under 3000 characters and 5500 UTF-8 bytes. The chairman is named through
  `[NAMBoardChairLeader]`; Olshansky is named only in 50 and 82.
- Pictures are the ten registered plates `GFX_event_adiscord_nam_<plate>`;
  `chair_handover` stays reserved for the takeover and chair installation.

Important focuses and their events:

| Role | Focus (event) |
| --- | --- |
| Branch openers | `beacon_out` (50), `quay_chain` (84), `dead_mans_veto` (59), `founders_of_unrest` (66), `order_arsenal` (74) |
| Kills | `posthumous_signature` (60), `last_debtor` (67) |
| Pairs | `original_stays_home` (86), `sole_vote_holder` (73), `double_lock_warehouse` (85), `loren_receipt` (54), `hereditary_roll` (63), `old_settlers_oath` (64), `subsidised_opposition` (87), `incumbents_credit` (88), `factory_guard` (76), `captains_share_qualification` (77) |
| Turning points | `facsimile_blood` (96), `purged_majority` (68), `both_squares_bought` (72), `society_99_1` (70), `mainland_inventory` (94), `table_six` (95) |
| Capstones | `harbour_exchange` (89), `close_the_lawsuit` (90), `eflor_petition` (58), `land_under_seal` (91), `chairmans_copy` (80), `port_rights_monopoly` (92), `residency_for_hire` (93) |
| Final | `partition_night` (81) |
| Others | `property_qualification` (51), `private_gospel` (52), `salt_monopoly` (53), `loren_priority` (55), `land_foreclosure` (56), `concession_courts` (57), `uncrested_buyers` (61), `privatise_governorate` (62), `price_of_silence` (65), `widows_share` (69), `mourning_licence` (71), `arsenal_monopoly` (75), `return_voyage` (78), `corporate_mass_housing` (79); interregnum `open_customs` (82) |

Lasting state written by the events and read by the council:
`NAM_board_guarantor_vote` (event 58) and `NAM_board_keeper_vote` (event 73),
each +1 vote to one company until `partition_night` clears them;
`NAM_story_54_choice` (cleared by event 83); the flags
`NAM_judas_officer_families_listed` and `NAM_judas_receipts_published`;
`NAM_board_society_dues` (event 70). Pinned by
`test_story_events_are_registered_safe_by_default_and_fired_once` and
`test_bought_and_story_votes_expire_at_their_own_moments`.

### C.6 Council decisions D1-D6

All in the category `NAM_free_zones`. The paid ones follow the custom cost
contract (`cost = 0`, `custom_cost_text` with `_blocked` and `_tooltip`,
every currency checked in `custom_cost_trigger`, rechecked and debited once in
`complete_effect`) and are listed in `CUSTOM_COST_DECISIONS` of the NAM
validator.

| # | Decision | Unlocked by | Price | Run | Result | Hidden when |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | `NAM_board_buy_proxies` | `sole_vote_holder` | 15 PP, 40 capital | 30 days, a chancery slot | the selected company +1 vote until the next annual meeting, at most two bought votes in the council; the top company -5 if another company is the target | - |
| D2 | `NAM_board_settlers_militia` | `old_settlers_oath` (cap 1), `land_under_seal` (cap 2) | 25 PP, 4000 manpower, 3600 `infantry_equipment` | 45 days | one locked four-battalion division "Old Settlers Militia" in the capital | every allowed division stands and none is being raised |
| D3 | `NAM_board_relief_fund` | `family_relief_fund` | 60 capital | instant | timed spirit `NAM_board_family_relief` for 180 days, Smenkom +3 | - (the spirit gates a repeat) |
| D4 | `NAM_board_retender` | `lawyers_of_both_shores` | native 25 PP | reopens the selected company's lot as its bid mission | the holder keeps or loses the lot; no second charter grant | all three lots retendered |
| D5 | `NAM_board_underwrite_payroll` "Жалованье чиновникам материка" | `incumbents_credit` | 30 capital, 20 PP | 90 days, a chancery slot, again 90 days later | `NAM_mainland_bought_officials` for 90 days on EFL and AZH while they exist and are not NAM subjects; Navis -3; Loren and Reidbank +4 on the first run | - |
| D6 | `NAM_board_redeem_mortgages` "Скупка эфлорских закладных" | `eflor_debt_purchase` | 50 capital | 60 days | `NAM_board_eflor_mortgages` +1, at most 3; each pays 100 capital and Reidbank +5 at the return victory | the third package is bought |

D2, D4 and D6 leave the list once used up, so the council category does not
grow. Each cancellation (`NAM_board_operable = no`) refunds the capital or
the goods, keeps political power spent and releases the slot. Pinned by
`test_council_rows_hide_once_used_up`.

### C.7 Directory campaigns

The eight campaigns `NAM_dir_campaign_<name>` (timed spirits
`NAM_dir_campaign_<name>_spirit`, launch effects
`NAM_dir_campaign_<name>_launch`, no more running than the places counted by
`NAM_dir_campaign_room`) sit at the end of the category
`NAM_public_campaigns`. That category shows on this route from the takeover
until `NAM_board_ended`, and its title and description switch to the
Directory through `NAMPublicCampaignsTitle` / `NAMPublicCampaignsDesc`. The
nine mainland campaigns of the category carry
`NAM_mainland_programmes_active = yes` in their `visible`, so they never show
on the islands.

**Places.** The capacity is the country variable `NAM_dir_campaign_slots`,
set to 0 in the one-time guard of `NAM_board_initialize`, so the ordinary
takeover and the debug corporate start (both through `NAM_corp_takeover`)
begin with no place. Three focuses each add one in their `hidden_effect`
(`add_to_variable = { var = NAM_dir_campaign_slots value = 1 }`, then
`clamp_variable` at 3): `property_qualification`, `foundry_mark` and
`society_99_1`, in any order. The always-true scripted trigger
`NAM_dir_campaign_count_free` leaves the free count in the temp variable
`NAM_dir_campaign_free` (capacity minus one per running campaign spirit); a
running campaign stays its timed spirit, so there is no second bookkeeping
variable and no polling. `NAM_dir_campaign_room` is that count above 0; it is
read by every campaign's `available` (tooltip `NAM_dir_campaign_room_tt`, which
prints "free N of M") and by the hidden recheck of the four custom-cost
campaigns. Each slot focus prints the place as the first row of its
`NAM_board_<focus>_reward_tt`: "Места кампаний Директории: +1 <icon>, всего N"
(`£operatives_propaganda_texticon`, T17 spacing). N comes from the defined
texts `NAMDirCampaignSlotsAfterPropertyQualification` / `...FoundryMark` /
`...Society`: the current capacity once that focus is completed, otherwise one
more. The word "для" of the requested wording is dropped because the
55-character layout limit counts a defined text as 12 characters.
`society_99_1` now carries its own `custom_effect_tooltip =
NAM_board_society_99_1_reward_tt`; the club dues of its law moved to
`NAM_board_society_99_1_law_reward_tt` (the law's `custom_modifier_tooltip`).
The slot counts as the kind "lasting rule": `foundry_mark` becomes A B D R T,
the other two keep their kinds.

The Directory's category description `NAM_dir_campaigns_desc` starts with
`[NAMDirCampaignSlots]`: with no place `NAM_dir_campaigns_slots_none` ("0 of
0", the three focuses named through their keys), otherwise
`NAM_dir_campaigns_slots_line` ("Свободно мест для кампаний: F из M", F from
`NAMDirCampaignFree`, which reads the same `NAM_dir_campaign_count_free`).

"Дивиденд в каждый дом" (`dividend`) is an economic action without the
propaganda prefix and is listed from the takeover; like every campaign it
waits for the first place. The seven propaganda
campaigns open by a focus: the reward carries `unlock_decision_tooltip =
NAM_dir_campaign_<name>`, `custom_effect_tooltip =
NAM_dir_campaign_<name>_unlock_tt` and, in its `hidden_effect`,
`set_country_flag = NAM_dir_campaign_<name>_open`.

| Campaign | Flag | Focus | Placement |
| --- | --- | --- | --- |
| `pays_on_time` "Директория платит в срок" | `NAM_dir_campaign_pays_on_time_open` | `property_qualification` | top of the reward |
| `newsreel` "Акционерная кинохроника" | `NAM_dir_campaign_newsreel_open` | `captains_share_qualification` | top of the reward |
| `gazette` "Ведомости Директории" | `NAM_dir_campaign_gazette_open` | `foundry_mark` | top of the reward |
| `lottery` "Лотерея акций" | `NAM_dir_campaign_lottery_open` | `society_99_1` | top of the reward |
| `return` "Мы вернёмся" | `NAM_dir_campaign_return_open` | `return_voyage` | top of the reward |
| `agitators` "Агитаторы на жалованье" | `NAM_dir_campaign_agitators_open` | `elected_in_absentia` | alive branch (Weber) |
| `mutineers` "Мятежники в погонах" | `NAM_dir_campaign_mutineers_open` | `inheritance_without_empire` | alive branch (Karamyshev) |

`NAM_dir_campaigns_close`, the last call of `NAM_board_end_operations`,
removes the running spirits and clears the seven flags. A launch moves trust
once; campaigns are an optional paid lever and are not part of the route
totals. Pinned by `NamDirectoryCampaignTests` and
`test_directory_campaigns_sit_in_the_public_campaigns_category`.

### C.8 Development: the reset at the flight and the six programmes

**Reset.** `NAM_rw_settle_island_exile` calls
`ADISCORD_reset_country_development` (in
`common/scripted_effects/ADISCORD_society_development_effects.txt`) on NAM
while the global flag `ADISCORD_nam_resource_war_island_exile` is still unset,
so it runs once per campaign on the ordinary and the debug entry. Every track
returns to level 1 with zero progress and zero monthly growth; science then
regains points from research slots alone. The debug idea reset keeps every
law slot, so the reset survives `NAM_debug_prepare_corporate_start`. The
evacuation tooltip `NAM_exile_evacuation_tt` (event
`ADISCORD_nam_resource_war.81`) lists the level-1 penalties.

**Focus rows.** Fifteen rows rebuild development, in position 2 of the
reward. The first row of each track calls `ADISCORD_reform_<track>_development`
(+25 progress now, +2 growth a month); every later row calls
`ADISCORD_programme_<track>_development` (+40 progress, no growth, economy
marked dirty).

| Track | Reform | Progress rows |
| --- | --- | --- |
| society | `beacon_out` | `eflor_debt_purchase`, `both_squares_bought` |
| social system | `widows_share` | `corporate_mass_housing` |
| army | `order_arsenal` | `factory_guard` |
| cultural | `copy_across_strait` | `mourning_licence` |
| state | `bought_century` | `admitted_owners_register` or `boundary_notches`, `chairmans_copy` |
| economic | `property_qualification` | `bearer_warrant` |

Science has no reform; the research steps of C.2 are its focus-side help. No
other focus or event calls a development effect except the four answers of
C.5 and the four development trades of C.12.

**Programmes.** Category `NAM_directory_development` "Развитие Директории"
(visible under the takeover until `NAM_board_ended`, no
`visible_when_empty`, so it appears with the first programme). Arrays
`NAM_dev_runs` and `NAM_dev_running` (size 7) are created in the one-time guard
of `NAM_board_initialize`; index 1-6 is the row of the table.

| # | Decision | Track | Opened by | Price | Result besides +40 progress | Sponsor +4 | Rival -3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `NAM_dev_census_halls` | society | `salt_monopoly` | 20 PP, 30 capital | 1500 manpower | Smenkom | Reidbank |
| 2 | `NAM_dev_harbour_infirmaries` | social system | `widows_share` | 40 capital | stability +2% | Navis | Arktur |
| 3 | `NAM_dev_drill_cadres` | army | `arsenal_monopoly` | 30 PP, 20 capital | 15 army experience | Arktur | Ferrant |
| 4 | `NAM_dev_works_schools` | cultural | `foundry_mark` | 25 PP, 30 capital | one industry research bonus | Ferrant | Smenkom |
| 5 | `NAM_dev_notary_registers` | state | `bought_century` | native 35 PP | 25 political power | Reidbank | Loren |
| 6 | `NAM_dev_oil_credit` | economic | `quay_chain` | 50 capital | fuel reserve +6000 | Loren | Navis |

Shared rules: 60 days, a chancery slot for the whole run, 120 days before the
next run, at most two runs per programme. The first run needs the sponsor not
boycotting, the second needs it "for". The `NAM_dev_running^k` receipt gates
the result in `remove_effect` and the refund in `cancel_effect`
(`NAM_board_operable = no`: capital back, political power spent, run and slot
returned). The `visible` hides a programme after its second run unless a run
is in progress. Pinned by
`test_flight_resets_development_once_and_survives_the_debug_start`,
`test_development_programme_effects_add_progress_only`,
`test_directory_programmes_follow_their_price_run_and_sponsor` and
`test_development_rows_follow_the_table_outside_hidden_effects`.

### C.9 Mainland leftovers

Completed mainland focuses stay completed through the tree swaps, so a
`has_completed_focus` gate does not hide mainland content on the islands. The
trigger `NAM_mainland_programmes_active` (no island exile, no takeover) is the
gate.

Ending at the flight:

- the categories `NAM_mobilisation`, `NAM_administration`,
  `NAM_postwar_orders` and `NAM_basin_economy` (the last one stays for the
  south-war tree) and the nine mainland campaigns of `NAM_public_campaigns`
  hide; no new mainland work starts;
- 31 running decisions and the two combine missions
  (`NAM_combine_frame_process`, `NAM_combine_plant_process`) that act on
  mainland states are cancelled through their own `cancel_effect` by the
  condition `NAM_mainland_programmes_active = no` with the tooltip
  `NAM_mainland_programmes_lost_tt`, placed as a branch of a top-level `OR`
  of the `cancel_trigger`;
- running national work (the `NAM_ind_*` projects, the pre-war campaigns)
  finishes for the government in exile and returns its slot, because its
  payload names no state;
- the settlement's first NAM block removes the mission
  `NAM_depot_public_hearing`, calls `NAM_end_depot_concessions` (the depot
  case and the spirit `NAM_private_tank_farms`) and clears `NAM_coup_pending`;
  the rivals and pillar monthly blocks read `NAM_mainland_programmes_active`;
- country development (C.8).

Ending at the takeover:

- `NAM_board_install_spirits` removes the balance of power `NAM_ladder_bop`
  (the interregnum events may still read it until then) and the mainland
  dynamic modifiers;
- `NAM_clear_mainland_national_spirits` (ordinary entry) and the debug idea
  reset clear the mainland national spirits.

After the flight and before the takeover only `NAM_interregnum_quay` is
visible. After the takeover the island categories are `NAM_two_judases`,
`NAM_free_zones`, `NAM_public_campaigns` and, once a programme opens,
`NAM_directory_development`. Pinned by
`test_mainland_leftovers_end_at_the_flight_and_the_takeover` and
`test_corporate_takeover_exposes_only_the_island_categories`.

### C.10 Interregnum rewards

The 56-day interregnum gives men, readiness or capital now and pledges for the
takeover. `NAM_interregnum_apply_pledges`, called by `NAM_corp_takeover`
after the opening trust is written, applies them: the boards' lane gives two
companies trust, the committees' and officers' lanes raise that camp's opening
support (a worse kill band later). Capital goes through
`NAM_corp_seed_capital` and `NAM_corp_capital_add`. `open_customs` fires event
82, whose answer is the lane pledge. Pinned by
`test_interregnum_pledges_move_the_opening_camp_support` and
`test_interregnum_finals_and_board_capital`.

### C.11 Reward magnitudes

After the flight the islands are not NAM cores, so the native pool of the
whole Directory is about 1900 recruits; focus and story manpower is the army
of the return. Material rows follow the focus cost (c1 7 days, c2 14, c3 21)
and the row's role: main (the headline result), secondary (a second material
row of another kind) or fallback (paid when the main result cannot be
delivered).

| Kind | c1 main | c2 main | c3 main | Secondary | Fallback |
| --- | --- | --- | --- | --- | --- |
| Manpower | 3000 | 4000-6000 | 7000 | 2500-3000 | - |
| `infantry_equipment` | - | 6000-7500 | 12000 | - | - |
| Convoys | 4 (interregnum) | 8-10 | 10 | 3 | - |
| Fuel reserve | - | 8000-12000 | - | 6000 | - |
| Political power | 40 (interregnum) | 60-75 | 100-125 | 30-50 | - |
| Army / navy experience | - | 25-30 | - | 15-20 | - |
| Capital | 60-80 | 100-120 where money is the story | 150 | 30-60 | building or zone 150 (c2) / 200 (c3) |
| Buildings | - | 1 factory with its slot | 2 factories with their slots | 1 naval base level | the capital above |

- `foundry_mark` and `loren_receipt` build their factory or refinery on an
  owned island together with `add_extra_state_shared_building_slots = 1`, so
  the reward never takes an island slot already in use (refineries keep the
  state cap of 3); capital is paid only when no island qualifies.
  `private_strait` builds its capital dockyard the same way
  (`NAM_board_build_company_docks` adds the slot, `NAM_board_yard_site` needs
  only a held port with a naval base and fewer than 20 dockyards); the 150
  capital is paid only when the capital has no such port.
  `representation_for_loss` (one arms factory, 150 capital fallback) and
  `residency_for_hire` (two civilian factories in one island state with
  `add_extra_state_shared_building_slots = 2`, 200 capital fallback) follow
  the `foundry_mark` shape. Pinned by
  `test_island_factory_rewards_bring_their_own_slot`.
- Dead branches pay their native replacement at full value in band 1 and
  half in band 2 (C.3): `widows_share` 3000 / 1500 manpower,
  `inheritance_without_empire` 4 / 2 convoys, `hereditary_roll` 80 / 40 PP,
  `old_settlers_oath` 30 / 15 army experience, `subsidised_opposition`
  2500 / 1250 manpower (beside its 45-capital spoils). Capital spoils,
  readiness, command power, stability, trust and camp support keep their
  values.
- Second pass: a focus whose only material row was 30-60 capital, or which
  had none, now pays a main row of its cost, varied along each chain.
  The 30-60 capital row was replaced in `bought_century` (8000 fuel),
  `private_gospel` and `concession_courts` (60 PP each), `island_fleet_shares`
  (8000 fuel), `azhar_land_fund` (8 convoys; its naval base stays as a
  secondary row with a 60-capital fallback), `boundary_notches` (30 army
  experience), `district_buyout` (6000 rifles in both branches) and
  `mourning_licence` (25 army experience in both branches; the dead branch
  keeps its 40-capital spoils). Rows were added to `founders_of_unrest` and
  `inheritance_without_empire` (60 PP in both branches, before the camp
  `if`; the founders' shared capital rose to the secondary 40),
  `family_relief_fund` (4000 manpower) and the kills: `posthumous_signature`
  gives 7000 manpower and `last_debtor` 10000 rifles in every band, beside
  the band results of the kill effect. Raised rows: `copy_across_strait` 10
  convoys plus 15 naval experience, `price_of_silence` 70 PP, `widows_share`
  stability +5% (shared by both branches, before the camp `if`), and capital
  where money is the story: `bearer_warrant` 150, `uncrested_buyers` 120 in
  both branches and `lawyers_of_both_shores` 120 beside its tender rule
  (45 before the pass).
- Third pass, the six focuses left without a material row: `dead_mans_veto`
  3000 manpower and 20 army experience (D M T X Y), `facsimile_blood` 4000
  manpower (A M T Y), `representation_for_loss` an arms factory with its slot
  (B R S T), `society_99_1` 7000 manpower (A D M R S), `residency_for_hire`
  two civilian factories with their slots (A B R T) and `partition_night` 10
  convoys plus 6000 fuel (A Q R T Y). The working standard also named 100 PP
  for `partition_night`; that row would make six kinds, so the fuel row of
  the same kind as the convoys replaces it. The standard's worked examples
  for other focuses were completed in the same pass: `quay_chain` 80 capital
  (60 before) plus 3 convoys (C D Q R T), `last_voyage_rifles` 192 squad
  weapons beside its 12000 rifles, `arsenal_monopoly` 36 artillery beside its
  6000 rifles.
- Capital deliberately departs from the working standard's "same route total,
  fewer rows" rule only where money is the story; the second pass removed
  eight 30-60 rows and raised four, so the run total fell from about 1100 to
  about 1045. Capital stays the council's price currency (prices 15-90).
- Interregnum: `roll_call` and `second_shift` 3000 manpower each,
  `underwrite_freight` 4 convoys, `open_customs` 40 PP, `guarantors` 30 PP.
- Story answers (C.5) give 2500-3000 manpower, 3000-4500 rifles, 4 convoys or
  4000-6000 fuel; their prices are unchanged except 74.a, the timeout
  answer, which now costs 30 capital for its 3000 rifles so that it is not a
  near-free gain.

One playthrough on the AI plan (dead branches in band 1, every building
delivered) hands out about 70000 manpower (82000 on the oath route), 48500
rifles, 72 artillery and 192 squad weapons, 35 convoys (45 on the fleet
route), 34000 fuel (46000 on the creditors' route), 1205 political power, 75
more army and 15 more naval experience than the first pass, about 1065
capital in lump sums, and 8 building levels with 6 added shared slots
(arms factories of `foundry_mark` and `representation_for_loss`, the
refinery of `loren_receipt`, the dockyard of `private_strait`, two civilian
factories of `residency_for_hire`, the naval base of `azhar_land_fund`, the
business centre of `admitted_owners_register`); the interregnum adds 6000
manpower, 4 convoys and 70 political power. Every playable focus of the
upper tree now pays a material row of its cost. Manpower and political power
stand above the working standard's route targets (45000-50000, 900-1100),
convoys too (25-30, though inside the 30-35 the return needs), while army
experience stays under its 120-160; the lower branch should take this into
account. Readiness, command power and stability rewards are
unchanged, so the return still needs one or two drills.

### C.12 Council laws and development trades

The author's order of 2026-11-21: focus rewards must also enact laws of the
council that the player cannot change, and lower a social development track
while raising another.

**Laws.** Fourteen council laws live in the section "Council of boards: laws"
at the top of `common/ideas/ADISCORD_nam_resource_war_ideas.txt`, one slot block
each (`law = yes` stays with the slot's first declaration in the generic law
files). Each has `cost = 0`, `visible = { has_idea = <self> }`, a scripted-only
`available` naming its focus (`NAM_board_law_<x>_source_tt`), `allowed_to_remove`
false with `NAM_board_law_locked_tt`, `ai_will_do = 0` and the economy refresh in
`on_add`/`on_remove` (`ADISCORD_economy_queue_law_refresh`). Every law gives one
or two headline gains and one or two felt prices. The modifiers below are the
contract; a change to one is a change to this table.

| Focus | Law | Slot | Replaces (history) | Repealed to (default) |
| --- | --- | --- | --- | --- |
| `property_qualification` | `NAM_board_law_property_census` | taxation | balanced_register | balanced_register |
| `both_squares_bought` | `NAM_board_law_paid_publicity` | information | state_bulletins | licensed_press |
| `concession_courts` | `NAM_board_law_concession_courts` | military justice | regular_tribunals | regular_tribunals |
| `harbour_exchange` | `NAM_board_law_harbour_exchange` | trade | export_focus | export_focus |
| `hereditary_roll` | `NAM_board_law_hereditary_patents` | officer corps | political_commissars | local_seniority |
| `old_settlers_oath` | `NAM_board_law_sworn_commanders` | officer corps | political_commissars | local_seniority |
| `privatise_governorate` | `NAM_board_law_district_wardens` | internal security | internal_directorate | local_garrisons |
| `society_99_1` | `NAM_welfare_society_99_1` | welfare | basic_services | basic_services |
| `subsidised_opposition` | `NAM_board_law_permitted_dissent` | cultural policy | heritage_protection | public_entertainment |
| `mourning_licence` | `NAM_board_law_mourning_licence` | cultural policy | heritage_protection | public_entertainment |
| `arsenal_monopoly` | `NAM_board_law_arsenal_monopoly` | industrial policy | state_planning_boards | balanced_workshops |
| `factory_guard` | `NAM_board_law_factory_guard` | military organisation | cadre_army | cadre_army |
| `captains_share_qualification` | `NAM_board_law_captains_share` | logistics | centralized_depots | civilian_contracts |
| `residency_for_hire` | `NAM_board_law_residency_for_hire` | labor policy | regulated_shifts | loose_contracts |

Modifiers (gains first, then prices; `econ` stands for `ADISCORD_economy_`):

| Law | Gains | Prices |
| --- | --- | --- |
| property_census | political power +5%, econ creditworthiness +15%, investment confidence +10% | population tax income -15% |
| paid_publicity | drift defence +20%, war support +3% | research speed -5%, admin expense +8% |
| concession_courts | investment confidence +10%, resource rent +10% | political power -5%, tax collection -8% |
| harbour_exchange | trade income +35%, resource rent +20% | min export 70%, civilian intel to others +25, navy intel to others +15 |
| hereditary_patents | army organisation +5%, political power +5%, stability +3% | army experience -10%, planning speed -5% |
| sworn_commanders | army defence +5%, army experience +10%, training time -5%, war support +3% | political power -8%, army expense +8% |
| district_wardens | stability +6%, political power +5%, drift defence +10%, admin expense -10% | tax collection -8%, overload resistance -10% |
| society_99_1 | social expense -20%, political power +5% | war support -3%, demographic fatigue +10% |
| permitted_dissent | stability +4%, drift defence +15% | political power -5%, admin expense +8% |
| mourning_licence | war support +6%, political power +5% | drift defence -15%, admin expense +8% |
| arsenal_monopoly | factory efficiency gain +15%, military industry income +12% | building speed -5%, civilian factory income -8% |
| factory_guard | army defence +8%, army expense -10% | army attack -5%, training time +5% |
| captains_share | naval invasion capacity +2, invasion preparation +15% | trade income -10%, stability -3% |
| residency_for_hire | civilian factory income +8%, social expense -8% | demographic fatigue +12%, monthly population -3% |

Shared slots are reached only through exclusive pairs: `hereditary_roll` and
`old_settlers_oath` are one pair; `mourning_licence` follows
`incumbents_credit`, which excludes `subsidised_opposition`. So no enactment
ever finds another council law in its slot; an enactment that did would fall to
its `add_ideas` fallback, and a new focus that breaks this must extend the
enactment chain first.

**One law per slot.** A slot never holds two laws: the law enacted later
replaces the one in the slot. Three war laws of appendix G.5 share a slot with
a council law (`holders_contracts` with `arsenal_monopoly`, `martial_rule` with
`district_wardens`, `field_courts` with `concession_courts`; `strait_requisition`
and `veteran_reserve` have no council partner). A war law's chain names its
council law first; the council law's chain names its war law first, for the
council focus completed after an armistice has reloaded the corporate tree.
Either way the native `swap_ideas` line of the focus names the replaced law.
The replaced law is not restored when the later one is repealed:
`NAM_board_repeal_laws` returns the slot to its default. Pinned by
`test_a_law_slot_never_holds_two_laws`.

**Enactment.** The focus calls `NAM_board_enact_<x> = yes` as the first
position-2 row (after the unlock pairs, before a camp `if`, so both branches
enact it). The effect is an `if`/`else_if` chain over every law of the slot,
each a visible `swap_ideas` to the council law, so the native line names the
law that goes and what it gave; `add_ideas` is only the fallback for an empty
slot. It ends with the lock row `NAM_board_law_lock_tt`. No enactment sits in a
`hidden_effect`. The economy reads trade laws by name: the x1.15 resource factor
of `export_focus` ends with the swap, and the exchange law's visible rent line
replaces it.

**Lock.** The law screen cannot enact or leave a council law: `available` is
`always = no` behind `NAM_board_law_<x>_source_tt` (the focus is the only
source), `allowed_to_remove` is `always = no` behind `NAM_board_law_locked_tt`,
`removal_cost = -1`, `ai_will_do = 0`, `cancel_if_invalid = no`. Only an
explicit `swap_ideas` in script replaces a council law.

**Lifecycle.** A law lives from its focus to the end of the council.
`NAM_board_end_operations` does not touch the laws.
`NAM_board_repeal_laws` swaps every held council law for the slot's
`default = yes` law (column "Repealed to") and is called once, from
`nam:on_annex` right after `NAM_board_end_operations`. The return keeps the
laws: the mainland tree succeeds or repeals each one by name through its
own enactments (appendix H.5), and its thirteen laws of the continent join
the repeal list. The debug idea reset keeps law
slots. Every enactment and repeal refreshes the economy through the laws'
`on_add`/`on_remove`.

**Trades.** `NAM_board_trade_<social>_for_<raised>` moves 100 progress: the
raised track gains 100 and checks its level at once (state through its own
threshold; economic through `ADISCORD_economy_check_economic_development_upgrade`,
whose gate `ADISCORD_economy_can_upgrade_economic_development` needs treasury
25+, debt pressure below 60, inflation below 40, stretch below 3 and, from
level 4, state development 4+; banked progress waits for the monthly tick).
Guard: when the raised track is already at level 5 the council takes 100 capital
instead (`_capped_tt` variant). The social track drops one level and keeps its
progress, or at level 1 loses its progress and, once per campaign and track
(`NAM_board_dev_cut_<track>`) and only while its growth is above 0, one point of
monthly growth. The tooltip is visible and the level changes run in a
`hidden_effect` that ends with `ADISCORD_economy_mark_dirty`. The trade
tooltips state the gate and the floor rule on indented note lines.

| Focus | Lowered | Raised |
| --- | --- | --- |
| `society_99_1` | social system | economic |
| `land_foreclosure` | society | economic |
| `subsidised_opposition` | society | state |
| `port_rights_monopoly` | social system | economic |

Every route takes three trades and ends with one social track at level 1: the
S side sacrifices the society, the I side the social system. Pinned by
`test_council_laws_are_scripted_locked_and_refresh_the_economy`,
`test_council_laws_are_enacted_once_by_their_focus_with_a_visible_swap`,
`test_council_laws_are_repealed_to_slot_defaults_at_the_annexation`,
`test_development_trades_follow_the_table_outside_hidden_effects` and
`test_development_trades_move_one_hundred_points_each_way`. The stability
cost of the laws against the history laws is about -13.5% on the AI route
(war support unchanged); it is a balance point for the author.

Nothing in this appendix was checked in the running game.

## Appendix D. The compact tree: lanes, islands, partisans and "Посейдон"

This appendix is the maintained contract of `NAM_exile_corporate_focus` as it
stands after the compaction: one tree of 68 focuses in which the council
lanes, the invasion preparation, the island operations and the final
"Операция \"Посейдон\"" are woven together. The focus source
(`focus_trees/NAM/exile_corporate/focuses.txt`), the decisions and the
effects hold the values; this appendix fixes the rules they follow and names
the script that carries them. Appendix C keeps the reward rules (writing
order, script shapes, tooltip layout, T17, kinds, events, laws); appendix F
the subversive operations and the claims; appendix G the wartime tree of the
return. Nothing here was checked in the running game.

**Author's orders for this tree (binding for every design and layout of it):**

- The first stage below `NAM_board_partition_night` prepares the invasion in four lanes:
  fleet, marines, supply, war economy ("следующая ветка с подготовкой вторжения: флот,
  морпехи, снабжение, военная экономика; пусть открывается после последнего фокуса").
- The branch is as symmetric as the upper tree ("ветка должна быть такая же симметричная").
  It is mirrored around the tree's centre column (x 18, the column of
  `NAM_board_partition_night`): lanes on each side at mirrored x positions, the same
  number of rows and the same shape of forks and merges on both sides, exclusive pairs
  placed as mirror images, and the opener and the final on the centre column. A focus on
  one side has a counterpart cell on the other; an odd focus sits on the centre column.
  The upper tree's spacing rules stay: a free cell between neighbours and no straight
  chain longer than two.
- Rewards follow the magnitude pass ordered together with it ("баффни фокусы. 300 людей
  условные - ни о чём").
- Recruitment stays as it is: the Directory's own islands 225-231 do not become national
  territory, so focuses, programmes and conquests supply the men, and they must supply
  enough for an invasion ("количество
  людей не меняя, их нужно достаточно много для вторжения").
- The last focus of the branch starts the second war, the war of return, against Eflor and
  Azhar ("нужно, чтобы последний фокус ветки запускал её; против Эфлора и Ажара"). That
  last focus is named "Операция \"Посейдон\"" (the author's name for it).
- Before that last focus the Directory may invade the neighbours' islands and nationalise
  them ("а до этого можно вторгнуться на другие острова соседей и национализировать их;
  открывает \"Одна ночь на раздел мира\""). The island wars are optional: the final must
  be reachable without them. A nationalised island becomes the Directory's national
  territory.
- The branch can prepare partisans who rise on the enemy's territory ("можно подготовить
  партизан, которые будут вставать на территории врага").
- `NAM_board_partition_night` also opens subversive operations against Eflor and Azhar,
  through which the Directory can hang penalties on them, and gives claims on land ("пусть
  одна ночь на раздел мира также открывает операции подрывные против Эфлора и Ажара
  (возможность дебафов навешать), даёт претензии на земли").
- The island operations come earlier than the end of the preparation ("сами операции на
  острова я бы сделал раньше").
- The final declares the war and loads another focus tree, the wartime tree of the return
  ("последний фокус объявляет войну, загружая другую ветку фокусов - военную на
  возвращение").
- The two parts of the tree are joined ("может совместим эти две ветки?"; "вплести в
  крылья"; "по горизонтали можно расширить"; "операции сделать пораньше, но не Посейдон,
  она будет последним фокусом"; "пусть не всё обязательно выполнять будет"). The
  preparation lanes continue the wings of the council tree: war economy and supply grow
  out of the left wing, fleet and marines out of the right wing, and the tree grows wider
  instead of taller. "Операция \"Посейдон\"" stays the last focus of the tree. Neither it
  nor any other capstone requires every focus: the player chooses what to complete.
- The tree is cut to a year or a year and a half ("может быть, тогда примерно на год
  ограничить эту ветку фокусов"; "год-полтора, я бы так делал"; "после одной ночи на
  раздел мира сразу показывать там операцию Посейдон; часть фокусов просто внедрить
  непосредственно в другие фокусы, а часть фокусов перенести уже на послевоенные либо на
  военную ветку"). "Операция \"Посейдон\"" sits directly under "Одна ночь на раздел мира".
  A folded focus hands its rewards, events, laws and unlocks to the focus that absorbs it;
  a moved focus goes to the wartime tree of the return or is kept for the tree after the
  return.
- After a won return a separate tree loads: the Directory on the mainland and its
  preparation for the war for the South, sized for two to three years of focus time
  ("сделай теперь ветку после возвращения и подготовке к войне за юг (фокус на 2-3 года)").
  The great war against the southern neighbours (Rahma, Sardan, Kadir) stays a separate
  stage inside that tree, before the war for the South against Shahrabad ("да, должна").
- The war of return has two real endings ("поражение - это полный конец; победа - это
  получение полностью владычества над Эфлором и Ажаром, ну и территории своей, конечно").
  Defeat ends the Directory's campaign. Victory gives the Directory its own former
  territory and complete dominion over both Eflor and Azhar, all of their land; a choice
  inside the wartime tree decides the form of that rule (company districts or direct
  rule), never its extent. Armistices and a dictated peace are pauses on the way, not
  victories: they leave the player a way to finish both enemies later (appendix G).

### D1. Shape, budget and what the capstones require

| Measure | Value |
| --- | --- |
| Focuses | 68: 66 playable and the two closed stubs `escheated_throne` and `treaty_two_judases` (cost 1, `available` never) |
| Exclusive pairs | 11: seven in the council lanes and wings, four in the outer lanes |
| Grid | columns 0-36, rows 0-10, centre column x 18; mirror of column x is 36 - x |
| Costs | c1 (7 days) everywhere except the 2-point focuses pinned in `COMPACT_TWO_POINT_FOCUSES`: the two kills, `facsimile_blood`, `purged_majority`, `both_squares_bought`, `mainland_inventory`, `table_six`, `partition_night`, "Посейдон", `harbour_exchange`, `residency_for_hire`, `close_the_lawsuit`, `land_under_seal`, `port_rights_monopoly`, `chairmans_copy`, `supply_overseas`, `first_wave`, `arsenal_of_the_boards`, `sharden_operation` |
| AI plan `NAM_exile_corporate_plan` | 44 focuses, 57 points (about day 399 for "Посейдон"), pinned at 58 points or less |
| Whole tree, one side of each pair | 55 focuses, 72 points (504 days), pinned at 77 points (a year and a half) or less |
| Fastest route | partition night after 20 focuses (day 210); "Посейдон" by prerequisite after 21, but not before day 314 because of its window |

No focus carries `bypass`, `allow_branch` or `relative_position_id`; nothing is
hidden, so the partition night no longer marks the layout dirty.

**What the capstones require.**

- "Одна ночь на раздел мира" (`partition_night`, 18,9, c2): prerequisites
  `mainland_inventory`, `table_six` and one side of the chancery pair
  (`original_stays_home` | `sole_vote_holder`); `available = { NAM_board_majority_held = yes }`.
  Through the pair it needs `both_squares_bought`, whose `available` requires
  the property census and, for each camp, the kill or its closed stub; with
  both stubs closed that means both kills and both Judas turning points
  (`facsimile_blood`, `purged_majority`). No wing, no wing capstone and no
  outer lane is required. `sole_vote_holder` needs the chancery open for 180
  days (`NAM_board_half_year_tt`).
- "Операция \"Посейдон\"" (`operation_poseidon`, 18,10, c2): shown directly
  under the night; its only prerequisite is `partition_night`. Its
  `available` (section D8) is the 90-day window and the material conditions;
  no lane focus, island or further kill is required.

### D2. Lanes and the mirror rule

```
row 0                                         [beacon 18]
row 1   [quay 5]                              [bought 18]                              [order_arsenal 31]
row 2   [gospel 5]          [dead_veto 12]    [property 18]    [founders 24]          [arsenal_mon 31]
row 3 [dbl_lock 3]x[loren_rcpt 5] [salt 7]  [eschtd 12]x[posthum 14] [last_debtor 22]x[treaty 24] [foundry 29] [guard 31]x[captains 33]
row 4    [bearer 4]      [privatise 10]   [facsimile 16]    [purged 20]   [society 26]      [last_voyage 32]
row 5 [courts 2] [foreclosure 6] [hered 8]x[oath 12]  [both_squares 18]  [incumb 24]x[subsid 28] [housing 30] [strait 34]
row 6    [exchange 4]                    [original 16]x[sole 20]                      [residency 32]
row 7 [war_econ 2] [quarterm 6] [close 10] [land_seal 14]          [port_rights 22] [chairmans 26] [landing 30] [navy 34]
row 8 [cartel 0]x[tenders 2] [bonds 4] [synth 6]  [mainland_inv 16] [table_six 20]  [luren 30] [ulven 32] [fire 34]x[escort 36]
row 9 [isl_arsenal 1] [ars_boards 5] [tanker 7]x[depots 9] [partition 18] [shore 27]x[storm 29] [sharden 31] [docks 35]
row 10                [supply_overseas 8]       [poseidon 18]       [first_wave 28]
```

Ids without `NAM_board_`; "A\|B" is one prerequisite group (either), "A, B"
separate groups (all). Costs in points of 7 days. "Event" is the story event
the focus fires itself (a second id is the delayed event of a folded focus).

**Centre (the chancery trunk, the Judas turning points, the night and the final)**

| id | Название | x,y | c | Prerequisites | Exclusive | Event |
| --- | --- | --- | --- | --- | --- | --- |
| `beacon_out` | Когда в гавани погас маяк | 18,0 | 1 | - | | 50 |
| `bought_century` | Скупленное столетие | 18,1 | 1 | beacon_out | | |
| `property_qualification` | Имущественный ценз | 18,2 | 1 | bought_century | | 51 |
| `facsimile_blood` | Кровь под факсимиле | 16,4 | 2 | posthumous_signature | | 96 |
| `purged_majority` | Большинство после чистки | 20,4 | 2 | last_debtor | | 68 |
| `both_squares_bought` | Обе площади куплены | 18,5 | 2 | property_qualification\|facsimile_blood\|purged_majority | | 72 |
| `original_stays_home` | Подлинник остаётся дома | 16,6 | 1 | both_squares_bought | sole_vote_holder | 86 |
| `sole_vote_holder` | Единый держатель голосов | 20,6 | 1 | both_squares_bought | original_stays_home | 73 |
| `mainland_inventory` | Материк по описи | 16,8 | 2 | close_the_lawsuit\|land_under_seal | | 94, 118 |
| `table_six` | Стол на шесть приборов | 20,8 | 2 | chairmans_copy\|port_rights_monopoly | | 95 |
| `partition_night` | Одна ночь на раздел мира | 18,9 | 2 | mainland_inventory, table_six, original_stays_home\|sole_vote_holder | | 81 |
| `operation_poseidon` | Операция \"Посейдон\" | 18,10 | 2 | partition_night | | 101 or 124 |

**Karamyshev lane (x 8-14) and Weber lane (x 22-28)**

| id | Название | x,y | c | Prerequisites | Exclusive | Event |
| --- | --- | --- | --- | --- | --- | --- |
| `dead_mans_veto` | Вето мертвеца | 12,2 | 1 | bought_century | | 59 |
| `escheated_throne` | Выморочный престол | 12,3 | 1 | dead_mans_veto | posthumous_signature | (closed) |
| `posthumous_signature` | Посмертная подпись | 14,3 | 2 | dead_mans_veto | escheated_throne | 60 |
| `privatise_governorate` | Приватизация наместничества | 10,4 | 1 | dead_mans_veto | | 62, 61 |
| `hereditary_roll` | Наследственный список | 8,5 | 1 | privatise_governorate | old_settlers_oath | 63 |
| `old_settlers_oath` | Присяга старожилов | 12,5 | 1 | privatise_governorate | hereditary_roll | 64, 65 |
| `close_the_lawsuit` | Черта под тяжбой | 10,7 | 2 | hereditary_roll | | 90, 58 |
| `land_under_seal` | Земля под печатью | 14,7 | 2 | old_settlers_oath | | 91 |
| `founders_of_unrest` | Учредители будущей смуты | 24,2 | 1 | bought_century | | 66 |
| `last_debtor` | Голос последнего должника | 22,3 | 2 | founders_of_unrest | treaty_two_judases | 67 |
| `treaty_two_judases` | Договор с обоими Иудами | 24,3 | 1 | founders_of_unrest | last_debtor | (closed) |
| `society_99_1` | Общество 99\1 | 26,4 | 1 | founders_of_unrest | | 70, 69 |
| `incumbents_credit` | Кредит действующей власти | 24,5 | 1 | society_99_1 | subsidised_opposition | 88, 71 |
| `subsidised_opposition` | Оппозиция на содержании | 28,5 | 1 | society_99_1 | incumbents_credit | 87 |
| `port_rights_monopoly` | Монополия портовых прав | 22,7 | 2 | incumbents_credit | | 92 |
| `chairmans_copy` | Председательский экземпляр | 26,7 | 2 | subsidised_opposition | | 80 |

`posthumous_signature` kills Karamyshev and `last_debtor` kills Weber; the
stubs beside them are the spared-leader routes, closed as work in progress
(user decision 9). A test pins this exception so it is removed together with
the stubs.

**Left wing (x 2-7) and right wing (x 29-34)**

| id | Название | x,y | c | Prerequisites | Exclusive | Event |
| --- | --- | --- | --- | --- | --- | --- |
| `quay_chain` | Хозяева причальной цепи | 5,1 | 1 | beacon_out | | 84 |
| `private_gospel` | Евангелие частной собственности | 5,2 | 1 | quay_chain | | 52 |
| `double_lock_warehouse` | Склад под двумя замками | 3,3 | 1 | private_gospel | loren_receipt | 85 |
| `loren_receipt` | Долг переживёт должника | 5,3 | 1 | private_gospel | double_lock_warehouse | 54 |
| `salt_monopoly` | Солевая монополия | 7,3 | 1 | private_gospel | | 53 |
| `bearer_warrant` | Варрант на предъявителя | 4,4 | 1 | double_lock_warehouse\|loren_receipt | | |
| `concession_courts` | Концессионные суды | 2,5 | 1 | bearer_warrant | | 57 |
| `land_foreclosure` | Взыскание землёй | 6,5 | 1 | bearer_warrant | | 56, 55 |
| `harbour_exchange` | Биржа у последнего причала | 4,6 | 2 | land_foreclosure, concession_courts | | 89 |
| `order_arsenal` | Арсенал порядка | 31,1 | 1 | beacon_out | | 74 |
| `arsenal_monopoly` | Арсенальная монополия | 31,2 | 1 | order_arsenal | | 75 |
| `foundry_mark` | Клеймо литейного двора | 29,3 | 1 | arsenal_monopoly | | |
| `factory_guard` | Частная заводская стража | 31,3 | 1 | arsenal_monopoly | captains_share_qualification | 76 |
| `captains_share_qualification` | Паевой ценз капитанов | 33,3 | 1 | arsenal_monopoly | factory_guard | 77 |
| `last_voyage_rifles` | Винтовки последнего рейса | 32,4 | 1 | captains_share_qualification\|factory_guard | | |
| `corporate_mass_housing` | Корпоративная массовая застройка | 30,5 | 1 | last_voyage_rifles | | 79 |
| `private_strait` | Частный пролив | 34,5 | 1 | last_voyage_rifles | | 78 |
| `residency_for_hire` | Прописка по найму | 32,6 | 2 | corporate_mass_housing, private_strait | | 93 |

**Outer lanes: war economy and supply (x 0-9), fleet, marines and islands (x 27-36)**

| id | Название | x,y | c | Prerequisites | Exclusive | Event |
| --- | --- | --- | --- | --- | --- | --- |
| `war_economy_charter` | Военный устав компаний | 2,7 | 1 | concession_courts | | 102 |
| `war_quartermaster` | Интендантство совета | 6,7 | 1 | land_foreclosure | | 106 |
| `cartel_prices` | Картельные цены | 0,8 | 1 | war_economy_charter | open_war_tenders | 103 |
| `open_war_tenders` | Открытые военные торги | 2,8 | 1 | war_economy_charter | cartel_prices | 104 |
| `war_bonds` | Военные облигации | 4,8 | 1 | war_economy_charter | | |
| `synthetic_plant` | Синтетика Лорэн | 6,8 | 1 | war_quartermaster | | |
| `island_arsenal` | Островной арсенал | 1,9 | 1 | cartel_prices\|open_war_tenders | | |
| `arsenal_of_the_boards` | Военная экономика правлений | 5,9 | 2 | synthetic_plant\|war_bonds | | 105 |
| `tanker_caravan` | Танкерный караван | 7,9 | 1 | war_quartermaster | shore_depots | 107 |
| `shore_depots` | Береговые склады | 9,9 | 1 | war_quartermaster | tanker_caravan | 108 |
| `supply_overseas` | Подвоз за море | 8,10 | 2 | shore_depots\|tanker_caravan | | 109 |
| `landing_contracts` | Подряд на высадку | 30,7 | 1 | corporate_mass_housing | | 114 |
| `private_navy` | Флот компаний | 34,7 | 1 | private_strait | | 110, 100 |
| `luren_operation` | Операция \"Лурен\" | 30,8 | 1 | landing_contracts | | 120 |
| `ulven_operation` | Операция \"Ульвен\" | 32,8 | 1 | private_navy | | 119 |
| `fire_squadron` | Огневая эскадра | 34,8 | 1 | private_navy | escort_flotilla | 112 |
| `escort_flotilla` | Конвойная флотилия | 36,8 | 1 | private_navy | fire_squadron | 111 |
| `shore_battalions` | Береговые батальоны | 27,9 | 1 | landing_contracts | storm_companies | 116 |
| `storm_companies` | Ударные роты | 29,9 | 1 | landing_contracts | shore_battalions | 115 |
| `sharden_operation` | Операция \"Шарден\" | 31,9 | 2 | ulven_operation\|luren_operation | | 121 |
| `company_docks` | Доки пароходства \"Навис\" | 35,9 | 1 | escort_flotilla\|fire_squadron | | 113 |
| `first_wave` | Первая волна | 28,10 | 2 | shore_battalions\|storm_companies | | 117 |

The cells mirror, not the content: `war_bonds`, `synthetic_plant` and
`arsenal_of_the_boards` face "Ульвен", "Лурен" and "Шарден".

**The mirror rule** (the author's order):

- every focus at (x, y) has a focus at (36 - x, y) whose prerequisite groups
  are the mirror images of its own, whose exclusive partner is the mirror of
  its partner and whose cost is equal; focuses on x 18 are their own mirror;
- every exclusive pair sits on one row with no card between its two cells;
- cards in one row are at least two columns apart; the longest chain of
  single prerequisites is two links;
- under the repository wiring model (`corporate_focus_wiring` in
  `tools/validators/inspect_nam_corporate_focus_layout.py`) the tree has no
  card hit and no wire crossing.

A new focus therefore always comes with its mirror cell, or sits on x 18.

Lane patrons (trust in the lane's rewards and events): war economy Ferrant 2
and Reidbank 6 against Smenkom 5; supply Loren 1 and Smenkom 5 against
Reidbank 6; fleet Navis 3 and Ferrant 2 against Arktur 4; marines Arktur 4 and
Smenkom 5 against Navis 3. The island operations pay their tender pair. The
partition night and the launch pay the two partition holders,
`NAM_board_partition_efl` and `NAM_board_partition_azh`, frozen by the night;
they are not the current ranks.

### D3. Folds, moves and the parked focus

A folded focus is gone from the source, the AI plan and both localisation
files; its rows, unlocks, law, development row, charter grant, rule hooks and
story event live in the absorbing focus. A story event of a folded focus fires
from the absorber 10-30 days after the absorber's own event, or from the event
or effect named below. The merged trust of an absorber is the sum of the
absorbed rows, without rows of -2 to +2 and capped at 10 per company (the
partition night's holders +12 is the exception).

| Absorber | Absorbed | What moves with it |
| --- | --- | --- |
| `private_gospel` | `future_output_pledge` | the pledge income row of `NAM_corp_monthly` |
| `arsenal_monopoly` | `island_fleet_shares` | `NAM_convoy_service_authorised` and the convoy service unlock |
| `escheated_throne` | `silence_after_settlement`, `escheated_land_auction` | empty stubs |
| `treaty_two_judases` | `proxy_parliament`, `ministries_in_concession` | empty stubs |
| `privatise_governorate` | `inheritance_without_empire`, `uncrested_buyers` | appoint masters, buy mortgages, campaign mutineers; event 61 |
| `society_99_1` | `elected_in_absentia`, `widows_share`, `family_relief_fund` | unseat proxies, campaign agitators, harbour infirmaries, exchange hiring, relief fund; event 69 |
| `land_foreclosure` | `loren_priority` | event 55 |
| `concession_courts` | `eflor_debt_purchase` | redeem mortgages |
| `hereditary_roll` | `district_buyout` | pay captains |
| `old_settlers_oath` | `boundary_notches`, `price_of_silence` | public works; event 65 |
| `subsidised_opposition` | `political_debt_register` | the four revoke decisions, the six sanction rows, two scripted-loc texts |
| `incumbents_credit` | `mourning_licence` | the mourning licence law and disperse mourners; event 71 |
| `private_strait` | `return_voyage` | the return campaign, the drill's return rows; event 78 |
| `corporate_mass_housing` | `azhar_land_fund` | rows only |
| `table_six` | `copy_across_strait` | rows only |
| `close_the_lawsuit` | `eflor_petition` | event 58 (it keeps its own guard) |
| `chairmans_copy` | `lawyers_of_both_shores` | retender and the tender bonus of `NAM_board_close_tender` |
| `port_rights_monopoly` | `representation_for_loss` | rows only |
| `mainland_inventory` | `mainland_contacts` | the cell programme, the cell seed, the enemy's raid category; event 118 |
| `partition_night` | `invasion_prospectus`, `holders_underwrite`, `six_share_pool`, `northern_safehouses`, `southern_safehouses` | event 81 dispatches 97, 180 (the backers' choice), 122 and 123; the holders-or-pool pair is the three answers of event 180; the safehouse rules read `NAM_board_partition_fixed` |
| `operation_poseidon` | `invasion_fleet` | the gate's men and the fleet spirit; event 101 |
| `war_economy_charter` | `double_shifts` | `NAM_board_double_shifts_spirit` |
| `island_arsenal` | `steel_for_guns` | rows only |
| `supply_overseas` | `ration_lists`, `bunker_piers`, `expedition_rear` | `NAM_board_expedition_rear_spirit` and the expedition-rear island rules |
| `private_navy` | `assembly_roads` | `NAM_board_assembly_roads_spirit`, the +10 island readiness of `NAM_isl_open_target`; event 100 |
| `company_docks` | `landing_craft`, `loading_schedules`, `island_squadron` | the two technologies, the soundings rule, the island squadron's escort cap and naval bases |
| `landing_contracts` | `marine_school`, `marine_kit` | the drill's landing rehearsal rows, the second marine raise slot |
| `storm_companies` | `marine_officers` | rows only |
| `shore_battalions` | `mercenary_battalions` | the mercenary brigade and `NAM_board_mercenary_pay` |
| `first_wave` | `landing_flotilla` | rows only |

Moved to the wartime tree of the return (appendix G): `hospital_ships` into
`NAM_rtw_districts_rise` (the spirit `NAM_board_hospital_ships_spirit`, the
social-system programme and its men) and `beach_masters` into
`NAM_rtw_war_cabinet` (its rifles, support equipment, squad weapons, army
experience and trust). Moved to the mainland tree:
`admitted_owners_register`, now `NAM_mdr_owners_register` "Реестр
допущенных собственников" (appendix H.3).

`tools/tests/test_adiscord_nam_focus.py` lists the 48 removed ids in
`COMPACT_REMOVED` and checks that none of them is left in the source.

### D4. Rewards

The rewards follow appendix C.1: writing order, script shapes, tooltip layout
and T17; two to seven kinds per focus, with the letters of `reward_kinds`
(the invasion lanes add K technology with an experience fallback, U a
formation, Y readiness and Z war started). The focus source holds every row.
Fixed points of the compact tree:

- `mainland_inventory`: unlocks the cell programme, +100 PP, +2000 men, the
  inventory preview, cells +10 in the six districts (`NAM_board_cells_seed`),
  trust Reidbank +5 and Loren -3; event 94, then event 118, whose answer b
  pays the two current vote leaders +6 and the other four -2
  (`NAM_story_118_b_leaders_tt`), because no holder exists before the night.
- `table_six`: +125 PP, 10 convoys, naval experience 15, the cultural
  development reform; +12 trust to every company below 50, Navis +4,
  Arktur -4, a 90-day immunity from the vote of no confidence.
- `partition_night`: opens the category `NAM_board_subversion` (appendix F),
  +4000 men, 10 convoys, `NAM_board_partition_charter` for 180 days, the
  partition of the mainland between the two vote leaders (holders +12, the
  other four -5), readiness +10, fuel reserve +6000, cells +15 in each of the
  six districts, `NAM_board_partition_claims` once, then event 81. With the
  category unlock it is at the ceiling of seven kinds.
- `operation_poseidon`: +15 000 men and +60 PP; previews of
  `NAM_board_poseidon_spirit` (120 days) and `NAM_board_invasion_fleet_spirit`
  (365 days), which the launch adds only on a real start;
  `NAM_rtw_tree_next_day_tt`; then `NAM_board_poseidon_launch` (section D8).
- The outer lanes carry the former invasion rewards of their absorbed
  focuses: the programme unlocks of section D5, the technologies
  `ADISCORD_tech_amphibious_*` with their fallback, the buildings through
  `NAM_board_build_on_island` with the capital fallback, the formations, the
  timed spirits and the island rules of D6.

Island rules read the completed focus, never a mirror flag:
`private_navy` adds 10 readiness to a newly opened island target;
`company_docks` raises "Промер глубин" to readiness +20; `supply_overseas`
makes "Склады плацдарма" cost 500 fuel for readiness +25 and gives a
nationalised island's capital a naval base and a supply hub, and a failed
landing returns half of the launch rifles; `fire_squadron` stops alerted
strait islands from building a coastal fort and raises the landing spirit one
tier; `storm_companies` lands marines at 35% experience.

Spirits of the outer lanes (all `add_timed_idea`, values in
`common/ideas/ADISCORD_nam_resource_war_ideas.txt`):
`NAM_board_assembly_roads_spirit`, `NAM_board_invasion_fleet_spirit`,
`NAM_board_double_shifts_spirit` (`on_add` / `on_remove` mark the economy
dirty), `NAM_board_tanker_caravan_spirit`, `NAM_board_expedition_rear_spirit`,
`NAM_board_escort_flotilla_spirit`, `NAM_board_fire_squadron_spirit`,
`NAM_board_storm_companies_spirit`, `NAM_board_landing_rehearsal_spirit`,
`NAM_board_mercenary_pay`, `NAM_board_porous_barrels`,
`NAM_board_poseidon_spirit` and `NAM_board_poseidon_ebb`.

### D5. Invasion programmes

Category `NAM_board_invasion` "Подготовка вторжения"
(`common/decisions/categories/ADISCORD_nam_resource_war_categories.txt`,
priority 25): `allowed = { tag = NAM }`, visible with `NAM_corp_takeover`,
`NAM_board_ended` not 1 and any of `NAM_board_partition_fixed` (first row: the
flag survives the tree swap) or the completed lane openers
`war_economy_charter`, `war_quartermaster`, `private_navy`,
`landing_contracts`, `mainland_inventory`. It holds programmes 1-9, the cell
programme and the mission "Плацдарм \"Посейдона\"".

Shared rules:

- arrays `NAM_board_inv_runs`, `NAM_board_inv_running`, `NAM_board_inv_cap`
  (index = programme) and `NAM_board_inv_share_done` are created in the
  one-time guard of `NAM_board_initialize`;
- caps: the unlocking focus or answer sets the base and rules add to it, all
  through `NAM_board_inv_cap_add` (temps `NAM_board_inv_k`,
  `NAM_board_inv_cap_change`), clamped to 0-6 (arsenal 0-7, marines 0-4) and
  never below the runs already made, so the order of completion never
  overwrites a bonus;
- custom cost contract of C.6: `cost = 0`, `custom_cost_text` with `_blocked`
  and `_tooltip`, every currency checked, rechecked in a `hidden_trigger` of
  `complete_effect` and debited once; all nine are in `CUSTOM_COST_DECISIONS`
  of `tools/validators/validate_adiscord_nam_resource_war.py`;
- the receipt `NAM_board_inv_running^k = 1` gates the result in
  `remove_effect` (`NAM_board_inv_settle_<k>`) and the refund in
  `cancel_effect` (`NAM_board_inv_refund_<k>`); a cancel returns capital,
  manpower, equipment and fuel and the run, never political power or trust;
- the targeted programmes 1 and 4 share one receipt each: a second target is
  refused, in `available` and in the recheck, until the first run settles; the
  target carries the state flag `NAM_board_inv_work`;
- the sponsor gate reads `NAM_board_product_blocked_<k> = no`; none of the
  programmes takes a chancery slot.

| # | Decision | Unlock | Price | Days | Result | Cap | Sponsor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `NAM_board_inv_convert_plant` "Перевод завода на военный заказ" (state 225-231) | `war_economy_charter` | 30 capital, 20 PP | 30 | one civilian factory of the target becomes an arms factory; no site: 30 capital back | 3, +2 `open_war_tenders` | Ferrant (`NAM_board_inv_arms_sponsor_ok_2`: cartel needs "for", tenders ignore the boycott) |
| 2 | `NAM_board_inv_arsenal_order` "Заказ островного арсенала" | `island_arsenal` | 50 capital, 10 PP | 30 | 4500 rifles, 96 squad weapons | 4, +2 tenders, event 100 +1 or -1 | Arktur (`_ok_4`, same rule) |
| 3 | `NAM_board_inv_fuel_freight` "Нефтяной фрахт Рейдбанка" | `war_bonds` | 60 capital, 15 PP | 30 | fuel reserve +6000 | 3 | Reidbank |
| 4 | `NAM_board_inv_harbour_works` "Портовые работы" (state 225-231) | `shore_depots` | 30 capital, 15 PP | 30 | +1 naval base at the island's main port while below 10; else 30 capital back | 3 | Smenkom |
| 5 | `NAM_board_inv_tonnage` "Фрахт транспортного тоннажа" | `private_navy` | 80 capital, 15 PP | 30 | 5 convoys | 4, event 100 +1 or -1 | Navis |
| 6 | `NAM_board_inv_escort_contract` "Закладка эскорта" | `company_docks` | 120 capital, 25 PP | 120 | one `ADISCORD_escort_ship_2155` while an island yard is held (`NAM_board_island_yard_ready`); else 120 capital back | 3, +1 `escort_flotilla`, +1 event 113 b | Navis; from the second run Navis "for" |
| 7 | `NAM_board_inv_raise_marines` "Набор морской бригады" | `landing_contracts` | 40 capital, 4300 men, 3870 rifles, 192 squad weapons | 45 | one "Island Marines" division at the capital, 20% experience, 35% after `storm_companies` | 2, +1 `shore_battalions`, +1 `first_wave` | Arktur; visible and available only while `NAM_marine_orders_open = yes` |
| 8 | `NAM_board_inv_holders_levy` "Взнос держателей" | event 180 b (`NAM_board_inv_backing = 1`) | 25 PP; each holder -3 at launch | 30 | 4 convoys, fuel reserve +5000 | 3 | both holders not boycotting (`NAM_board_holders_backing`) |
| 9 | `NAM_board_inv_expedition_share` "Пай в экспедиции" (the company selected on the pyramid, stored in `NAM_board_inv_share_target`) | event 180 a (`NAM_board_inv_backing = 2`) | 40 capital, 25 PP; that company -3 and its product blocked while the run lasts | 30 | by company: Loren fuel +6000, Ferrant 4500 rifles, Navis 5 convoys, Arktur 36 artillery and 96 squad weapons, Smenkom 2500 men, Reidbank 80 capital; that company +6 | once per company | the selected company |

The marine raise cap reaches 3 on the storm route and 4 on the battalions
route. "Island Marines" is sold at a fixed price, and
`NAM_marine_unlock_template` unlocks the template only once
`NAM_marine_orders_open = no`; a running raise is cancelled with its full
refund when the return landing closes the marine orders, so the template
stays locked whenever a fixed-price raise is possible.

The expedition share holds the product: each `NAM_board_product_blocked_<k>`
trigger has a row that is true while `NAM_board_inv_running^9 = 1` and
`NAM_board_inv_share_target = <k>`.

**The backers' choice** (`ADISCORD_nam_story.180` "Подписной лист экспедиции",
dispatched by event 81 twelve days after the night; `is_triggered_only`,
`fire_only_once`). Each answer writes `NAM_board_inv_backing` once; that
number replaces every reader of the two folded pair focuses: the holders'
levy, the expedition share, the cell price, the rifle debit of a cell run, the
backers' condition of "Посейдон" and two scripted-loc texts.

| Answer | Effects | Backing | Follow-up |
| --- | --- | --- | --- |
| a "Складчина шести правлений" (default, AI 80) | unlocks the expedition share; capital -40; +50 PP; stability +3%; all six +3 | 2 | event 99 in 30 days |
| b "Подряд держателей" (AI 15) | unlocks the holders' levy (cap 8 +3); 6 convoys; one proxy vote to each holder until the next annual meeting; holders +8, the other four -3; cell runs cost 750 rifles | 1 | event 98 in 30 days |
| c "Совет обходится без подписки" (AI 5) | capital +40; no decision | 0 | - |

"Посейдон" then needs both holders not boycotting (backing 1) or tolerates one
boycotting company (backing 0 or 2): `NAM_board_invasion_backers_ready`.
`NAM_board_end_operations` clears the variable.

### D6. Island operations and nationalisation

**Targets.** Island index k is used by every variable and effect.

| k | Target | States (capital) | Landing province | Capital VP province | Bidders |
| --- | --- | --- | --- | --- | --- |
| 1 | Ulven League ULV | 643 "Тарвен", 644-648 (648) | 3094 | 6452 | Navis 3 / Ferrant 2 |
| 2 | Luren Archipelago LUR | 649-652 (651) | 3313 | 1894 | Loren 1 / Smenkom 5 |
| 3 | Sharden Confederation CHD | 672-680 (680) | 3224 | 1610 | Arktur 4 / Reidbank 6 |

Every island state is its own island. Tarven (643, owner and core ULV, 720 000
manpower in history, VPs worth 26 of Ulven's 36) belongs to every Ulven list;
it starts without units. The three targets have no faction, guarantee or
overlord in history, and guarantees are blocked by the default game rule. They
are not suppressed minors, but each registration still calls
`ADISCORD_release_non_participating_minor_optimization`.

**Operation focuses**, early in the outer right lane ("Ульвен" from
`private_navy`, "Лурен" from `landing_contracts`, both on row 8, "Шарден" from
either on row 9). `available`: the target exists and is not a subject (tooltip
`NAM_isl_target_free_tt`); Sharden also needs `NAM_isl_staging_port_held`, 648
or 651 owned and controlled (tooltip `NAM_isl_staging_tt`). An operation focus
does not declare war: the war starts with "Высадка" at the moment the player
chooses.

| Focus | Rewards |
| --- | --- |
| `ulven_operation` (c1) | unlocks "Высадка" and "Промер глубин"; claims on 643-648; Ulven readiness +15, +25 after `private_navy` (`NAM_isl_open_target`); naval XP +20; Navis +5, Ferrant +5 |
| `luren_operation` (c1) | the same for 649-652 and Luren; Loren +5, Smenkom +5 |
| `sharden_operation` (c2) | unlocks the promise and the blockade; claims on 672-680; Sharden readiness +10, +20 after `private_navy`; 10 convoys; Arktur +5, Reidbank +5 |

The first successful launch fires `ADISCORD_nam_story.101` "Флаг на флагмане"
the next day (`fire_only_once`): every answer writes
`NAM_board_expedition_flag`, which the island tenders 125-127 read, and the
landing settles weeks later, so the flag is always written before a tender.

**Category** `NAM_board_islands` "Островные операции": NAM only, visible with
`NAM_corp_takeover`, `NAM_board_ended` not 1 and the Ulven or Luren operation
completed; priority 24. Status array `NAM_isl_status^k`: 0 independent, 1
registered in the running island war, 2 annexed, 3 national. Readiness is the
state variable `NAM_isl_readiness` on the capital state (0-100,
`NAM_isl_add_readiness`, temp `NAM_isl_gain`). Targeted decisions use
`targets = { 648 651 680 }` and derive k through `NAM_isl_k_from_target`.

| Decision | Price | Days | Conditions beyond the council operating | Result |
| --- | --- | --- | --- | --- |
| `NAM_isl_soundings` "Промер глубин" | 20 PP | 21 | operation focus done, status 0, chancery slot (`NAM_judas_slot_tt`), no reopen cooldown | readiness +15, +20 after `company_docks` |
| `NAM_isl_depots` "Склады плацдарма" | 40 capital, 1000 fuel (500 after `supply_overseas`) | 28 | as above; Loren's product not blocked | readiness +20, +25 after `supply_overseas` |
| `NAM_isl_bribe` "Подкуп гарнизона" | 50 capital | 30 | as above, once per island; Reidbank trust 35 or more | readiness +15; flag `NAM_isl_bribed`: one defender brigade fewer at the declaration |
| `NAM_isl_launch` "Высадка" | Ulven, Luren: 25 PP, 12 900 men, 11 610 rifles; Sharden: 40 PP, 21 500 men, 19 350 rifles | instant | `has_war = no`; no island war and no war of return; majority held; Navis and Loren products not blocked; readiness 50 or more; 20 convoys; no reopen cooldown; the target (and a pact partner) independent and at peace; no preparation running on the island; Sharden: the staging port | `NAM_isl_op_launch` |
| `NAM_isl_sharden_promise` "Обещание южным островам" | 35 PP | 30 | Sharden focus done, CHD status 0, neither Sharden decision done or running | flag `NAM_isl_sharden_promise_done`: two CHD brigades fewer at the declaration; the four southern states 672, 677, 678, 679 are never cored; Arktur and Reidbank -8 at completion; the Sharden concession counts 1 vote and half its dividend |
| `NAM_isl_sharden_blockade` "Хлебная блокада Шардена" | 40 capital, 2000 fuel | 60 | as the promise, mirrored | CHD spirit `NAM_isl_sharden_hunger` 180 days; NAM spirit `NAM_isl_blockade_strain` 180 days; Sharden readiness +10 |
| `NAM_isl_pacify` "Умиротворение" | 25 PP, 50 capital | 30 | status 2, every island state owned and controlled | every island state: resistance -15, compliance +10 |
| `NAM_isl_nationalise` "Национализация" | Ulven 70 PP + 180 capital, Luren 50 + 120, Sharden 90 + 250; with an operator whose product is not blocked 120 / 80 / 170 capital | 90 | status 2, island held, capital-state resistance 25% or less | `NAM_isl_nationalise_finish` |
| `NAM_isl_insurance` "Страховой полис экспедиции" | 15 PP, 60 capital | 30 | `war_bonds` done, an island at status 0, not insured; Reidbank's product not blocked | flag `NAM_isl_insured`, consumed by the next settlement: a failed landing pays back 150 capital and costs the blamed companies 8 instead of 15; a stalled one pays back 75; a victory consumes it for nothing |

The three preparations take a chancery slot each and keep a state receipt on
the capital (`NAM_isl_prep_soundings`, `_depots`, `_bribe`); "Высадка" refuses
an island with a running preparation. All paid island decisions follow the
custom cost contract and are in `CUSTOM_COST_DECISIONS`; a cancel returns
capital and fuel, never political power or trust.

Missions (timeout-only, `available = { hidden_trigger = { always = no } }`,
`selectable_mission = no`, registered in
`common/synchronized_dynamic_tokens/ADISCORD_tokens.txt`):

| Mission | Days | Activated by | Timeout |
| --- | --- | --- | --- |
| `NAM_isl_beachhead_strait` | 45 | landing on Ulven or Luren | `NAM_isl_beachhead_check` |
| `NAM_isl_beachhead_sharden` | 60 | landing on Sharden | the same |
| `NAM_isl_campaign_strait` | 105 | a held beachhead | `NAM_isl_campaign_check` |
| `NAM_isl_campaign_sharden` | 150 | a held beachhead | the same |
| `NAM_board_poseidon_beachhead` | 90 | section D8 | event 131 |

**The landing** (`NAM_isl_op_launch`, NAM scope, FROM the capital state, temp
`NAM_isl_k`), in order:

1. `NAM_isl_op_target = k`, `NAM_isl_status^k = 1`;
2. strait pact (Ulven or Luren only): the other strait island joins when it is
   at status 0 and `NAM_isl_pact_partner_ready` (exists, not a subject, at
   peace, `NAM_isl_alerted`); it becomes `NAM_isl_pact_member`, the target
   founds the faction `NAM_isl_pact_faction` "Проливной пакт" from
   `faction_template_ADISCORD_standard`, and NAM and both islands take campaign
   major status through `ADISCORD_nam_resource_war_reserve_major`, so every
   member must fall;
3. every registered island: `NAM_isl_register_target` (woken, flag
   `NAM_isl_participant`, leaves any faction) and `NAM_isl_reinforce_defender`;
4. `declare_war_on` with `annex_everything`, then `add_to_war` for the pact
   member on the target's side; a partner that did not enter the war is
   released, and a declaration that made no war calls `NAM_isl_launch_abort`
   (statuses back, the whole price back, `NAM_isl_release`);
5. landing spirit `NAM_isl_landing_spirit_1/2/3` for 60 days at readiness 50,
   75 or 100, one tier higher after `fire_squadron`;
6. `NAM_isl_land_first_wave`: the defenders of the capital state are teleported
   to their capital province, NAM takes the landing province and 2 "Island
   Marines" (Sharden 3) land there at 30% experience (35% after
   `storm_companies`);
7. the beachhead mission; the second echelon is booked in
   `NAM_isl_echelon_k` / `NAM_isl_echelon_day` and the hidden event 132 runs
   `NAM_isl_second_echelon` 10 days later: 1 division (Sharden 2) on a held
   landing province, otherwise 4300 men and 3870 rifles back per division;
8. the bribe flag on the capital is consumed; readiness stays through the war;
9. event 101 the next day (it fires once per campaign).

**Defender reinforcement**, once per war (`NAM_isl_defence_mobilised`, cleared
at release; units given earlier stay):

| Target | Manpower | Rifles | Other | Brigades |
| --- | --- | --- | --- | --- |
| ULV, LUR | +6000 | +4000 | an alerted island gets a level-1 coastal fort at its capital province unless `fire_squadron` is completed | 2 "Territorial Brigade", +1 above difficulty 2, -1 bribed |
| CHD | +15000 | +10000 | 120 support equipment; level-2 coastal forts at 1610 and 1858 | 4, +2 above difficulty 2, -2 promised, +1 alerted, -1 bribed |

**Endings.** Neither side wins by default:

- native capitulation: `NAM_isl_record_capitulation` runs inside the existing
  `nam:on_capitulation_immediate` and `nam:on_capitulation` blocks of
  `common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt`. A registered
  island beaten by NAM or its subject keeps the two-day receipt
  `NAM_isl_capitulation_reserved` and the war settles as a victory once every
  registered island has fallen (`NAM_isl_all_defeated`). NAM capitulating to a
  participant is a failed landing. The receipt makes the `nam:` block set
  `skip_default_capitulation` in both directions, so the ZZ fallback never
  annexes the Directory or a target;
- capital hold: `NAM_isl_monthly` sets `NAM_isl_capital_hold` (40 days) when NAM
  controls every registered capital state and settles a victory at the next
  pulse that still finds them held; a lost capital clears the flag;
- beachhead timeout (45 / 60 days): a foothold (landing province or any island
  state) opens the campaign mission, none is a failed landing;
- campaign timeout (105 / 150 days): every registered capital held is a
  victory; the main capital held but not the partner's annexes the main target
  and settles the partner as stalled; a foothold alone is a stalled landing;
- external: `NAM_isl_close_external` (inside the existing `nam:on_peace`,
  `nam:on_puppet` and `nam:on_annex` blocks, after
  `NAM_great_war_close_external`) runs only while `NAM_isl_op_target > 0`; the
  war closes without awards (status 2 for an island whose capital NAM owns,
  else 0); a partner that left alone is released while the main target fights
  on.

**Commit rule.** Every terminal island effect first copies `NAM_isl_op_target`
and `NAM_isl_pact_member` into the temps `NAM_isl_settle_k` and
`NAM_isl_settle_member`, writes the terminal statuses and clears both
variables, and only then calls `white_peace` or `annex_country`.
`NAM_isl_release` runs last: it removes the island missions, releases the
campaign major status of NAM and the islands, dismantles the pact faction
(founder flag) and clears `NAM_isl_participant`, `NAM_isl_defence_mobilised`
and `NAM_isl_capital_hold`.

| Settlement | Effects |
| --- | --- |
| `NAM_isl_settle_victory` (temp `NAM_isl_member_stalled`) | status 2; `white_peace` and `annex_country` (`transfer_troops = no`) of each annexed island; island states still held by a participant are transferred and every owned one set to NAM's control; Sharden's hunger spirit removed; insurance consumed; a stalled partner gets white peace, half readiness, a 90-day reopen flag and the alert; stability +3%; the other strait island is alerted; tender event 125/126/127 the next day per annexed island; economy dirty; recount queued |
| `NAM_isl_settle_stalled` | status 0; white peace with every registered island; spirit `NAM_isl_landing_stalled` 120 days; readiness halved, reopen after 90 days, island alerted; insurance pays 75; Navis and the island's bidders -5 (skipped with temp `NAM_isl_quiet = 1`) |
| `NAM_isl_settle_failed` | status 0; white peace; spirit `NAM_isl_landing_failed` 180 days; readiness 0, reopen after 120 days, island alerted and keeps its reserves; Navis and both bidders -15 (-8 insured, insurance pays 150); with `supply_overseas` half of the launch rifles back (5805, Sharden 9675); event 128 the next day |

**Tenders and concessions.** Events 125-127 fire one day after the victory.
"Отложить тендер" costs both bidders 5 (nothing with
`NAM_board_expedition_flag = 1`) and re-fires the event after 90 days while
the island is held without an operator; an award (`NAM_isl_tender_award`)
writes `NAM_board_isl_owner^k`, sets `NAM_isl_tender_done_<k>`, gives the
winner +15 (+20 when it chairs and `NAM_board_expedition_flag = 2`) and the
loser -15, then recounts. A concession is 2 votes in `NAM_board_recount`
(Sharden 1 after the promise; the operator is copied into the temp
`NAM_board_isl_owner_input` before it indexes `NAM_board_holdings`). Islands
are annexed, not federal districts. Monthly dividends (`NAM_isl_monthly`):
Ulven 10 (Navis or Ferrant), Luren 8 (Loren) or 12 (Smenkom), Sharden 6
(Arktur) or 15 (Reidbank), halved to 3 or 8 after the promise; they are added
to `NAM_corp_last_income` as well. A concession survives the nationalisation.

**Nationalisation.** `NAM_isl_nationalise_pay` keeps the paid capital on the
capital state (`NAM_isl_nationalise_paid`) and sets `NAM_isl_nationalising`;
resistance above 40% or a lost state cancels with the capital back.
`NAM_isl_nationalise_finish` rechecks the island held and resistance at most
40%, then on every state of the explicit list adds NAM's core, removes the old
tag's core and cancels resistance (Sharden after the promise: 672, 677, 678 and
679 keep CHD's core and get none); status 3; the operator +5; with
`supply_overseas` +1 naval base and a supply hub at the capital province
(6452, 1894, 1610); during an active war of return after "Посейдон" the
island's brigade at once; economy dirty; recount queued. From then on the
island counts for national recruitment and for the scripted economy's core
population. Between the annexation and the nationalisation native resistance
runs on the old cores; `NAM_isl_monthly` fires event 129 when a capital state
resists above 50%, at most once per island per 90 days (`NAM_isl_flare_<k>`)
and never while another 129 is open (`NAM_isl_flare_target`).

### D7. Partisans

Cells are the state variable `NAM_cells` (0-100) on the six mainland
districts: 67 and 688 for Eflor's holder, 689, 690, 700 and 719 for Azhar's.
Only `NAM_board_cells_add` (state scope, signed temp
`NAM_board_cells_change`, clamp 0-100) writes it.

- Seed: `mainland_inventory` gives +10 in every district
  (`NAM_board_cells_seed`); the partition night +15 in every district; events
  118, 122 and 123 add more.
- Programme `NAM_board_inv_cells` "Ячейка" (category `NAM_board_invasion`,
  visible after `mainland_inventory`, targets the six districts held by EFL or
  AZH and not controlled by NAM): 25 PP, 40 capital, 1500 rifles (750 with
  `NAM_board_inv_backing = 1`), 60 days, at most two runs at once
  (`NAM_board_cells_running`), visible while `NAM_board_cells_open` (council
  operating, no war of return active, return not won). The paid run is the
  state flag `NAM_board_cells_work` (value 1 for the 750-rifle price, 2 for
  1500). Result +20, +25 once the partition night has set
  `NAM_board_partition_fixed` (`NAM_board_cells_safehouse_cover`); a district
  lost or a closed programme returns capital and rifles. Every running run is
  refunded when the war starts, so the cover matters inside the window of D8.
- Monthly (`NAM_board_cells_monthly`, after the main `NAM_corp_capital_add` of
  `NAM_corp_monthly`, six explicit rows each): a network of 10-59 grows by 1;
  then each district of 40 or more without `NAM_cells_raided` rolls 8% for
  event 130 while no exposure event is pending
  (`NAM_board_cells_event_pending`, 30 days).
- Enemy answer: category `NAM_cells_counter` "Охранка" for EFL and AZH
  (`icon = military_operation`, visible after NAM's `mainland_inventory`, while
  the council has not ended and no war of return runs). Decision
  `NAM_cells_raid` "Облава": 25 PP, 30 days, a district of the raider with
  cells 30 or more and no `NAM_cells_raided`. Result -25 (-15 after the
  partition night), `NAM_cells_raided` for 120 days, then event 130 for NAM.
  The same category holds the counter-intelligence decision of appendix F.
- Rising (`NAM_board_cells_rise`, only after a successful start of the war of
  return, from "Посейдон" or the renewal decision): it clears
  `NAM_board_harbour_rose`, ensures the locked template "Mainland Partisans"
  (3 `ADISCORD_militia`, not recruitable) and runs each district that the
  enemy or NAM controls: 30+ sabotage (dynamic modifier
  `NAM_board_rising_sabotage` for 120 days, removed when NAM controls the
  state; infrastructure damaged); 50+ the hostile armies there are teleported
  out, NAM takes the rising province (67: 4287, 688: 3127, 689: 176, 690:
  2935, 700: 16881, 719: 461) and one partisan division forms (10%
  experience); 70+ a second division, and 688 after the partition night also
  gives NAM the port province 689. At most 8 divisions in all (temp
  `NAM_board_partisans_raised`, carried into the wartime tree as
  `NAM_rtw_partisans`). A rising in 700 from 50 sets NAM's
  `NAM_board_harbour_rose`. Then every network is spent
  (`NAM_board_cells_spend` returns a paid run first and clears `NAM_cells`).
- Southern harbour rule: `NAM_board_harbour_rising_ready` (the partition flag
  set and 700 at 70 or more) is read inside `NAM_wor_revenge_landing` before
  the cells are spent; every trained marine order then lands at the harbour
  instead of the island capital.
- Close: `NAM_board_cells_close` returns every paid run and clears all six
  networks; it runs at the end of the council, in the exile branch of a won
  return and in the dictated peace of appendix G. An armistice keeps the
  cells, so they can be rebuilt and rise again on the renewal.
  `NAM_war_of_return_close` removes the sabotage modifier from the six
  districts.

### D8. "Операция \"Посейдон\"" and its window

**`available`** (each line localised; `cancel_if_invalid = no`,
`continue_if_invalid = no`: the focus pauses, it is not cancelled):

1. the window: `has_country_flag = { flag = NAM_board_partition_fixed days > 89 }`
   (`NAM_board_poseidon_window_tt`);
2. `NAM_board_majority_held = yes`;
3. `NAM_board_invasion_backers_ready = yes` (section D5);
4. `NAM_war_of_return_can_start = yes` (no war, which also excludes an island
   war);
5. readiness 70 or more;
6. more than 7 divisions;
7. `NAM_board_poseidon_marines_ready`: two formed marine formations from paid
   orders (`NAM_marine_orders_paid`) and raised brigades
   (`NAM_board_inv_runs^7`; a run still training does not count);
8. 20 convoys.

**Why the window.** Everything the night opens ends when the war starts:
subversion (`NAM_sub_open`, operations of 45-90 days), cell runs (60 days,
refunded at the landing) and the night's story chain (81 day 1, 97 day 8, 180
day 13, 122 day 21, 123 day 41, 98 or 99 about day 45-60). Ninety days hold two
45-day operations or one 90-day operation per target, one cell run per
district pair and the whole chain. The AI plan reaches "Посейдон" about 112
days after the night.

**Reward.** Native +15 000 men and +60 PP, previews of the two spirits,
`NAM_rtw_tree_next_day_tt`, `NAM_board_operation_poseidon_reward_tt`; the
`hidden_effect` calls `NAM_board_poseidon_launch` and, only when the war of
return is active, fires event 124 the next day when
`NAM_board_expedition_flag > 0`, otherwise event 101, whose every answer
chains 124. `NAM_board_poseidon_launch`:

1. `NAM_war_of_return_start = yes`: the existing war (EFL and AZH registered
   and claimed, campaign major status, the coalition from
   `faction_template_ADISCORD_standard`, `annex_everything`, event
   `ADISCORD_nam_resource_war.60`, `NAM_wor_revenge_landing` with the harbour
   beachhead at 16716 and 2 free marines, 3 at readiness 70 or with a paid
   order; the other paid orders form on the island capital, or at the harbour
   under the southern rule);
2. only when `NAM_war_of_return_active = yes` and `NAM_wor_exile_war` is set:
   `NAM_board_cells_rise`; `NAM_board_poseidon_island_brigades` (one "Line
   Infantry Brigade" at 20% experience at each nationalised island's capital,
   6300 men without the template or the capital); the flagship division
   "Флагманский десант" ("Island Marines", 35% experience) at 16716 when NAM
   controls it, else at the capital; `NAM_board_poseidon_spirit` 120 days and
   `NAM_board_invasion_fleet_spirit` 365 days; `NAM_sub_apply_landing_charges`
   (appendix F); holders +5 and the chair's company +5 in one package;
   `NAM_rtw_begin` and the hidden event `ADISCORD_nam_story.168` one day later,
   which loads the wartime tree (appendix G); mission
   `NAM_board_poseidon_beachhead` (90 days);
3. otherwise nothing more: the renewal decision reopens the start.

**Outcomes** of the war are the contract of appendix G. The stalled-landing
armistice stays as built: at the beachhead mission's timeout, while the war
runs and NAM controls none of 67, 688, 689, 690, 700, 719
(`NAM_board_poseidon_no_homeland_held`), event 131 "Отлив" offers the
armistice (a, c call `NAM_board_send_armistice_offer` with the temp
`NAM_board_armistice_offer` 1 or 2) or "Держать пляжи" (b). The offer goes to
the first principal that can still decide (`NAM_rtw_can_decide`: exists, a
participant, at war with NAM, not capitulated) in the order of
`NAM_rtw_pick_decider` (the primary, Eflor, Azhar), without saving
`NAM_rtw_decider`, so a pending line or dictate offer keeps its decider; only
then are `NAM_board_armistice_terms` and the flag `NAM_board_armistice_sent`
written. With nobody left the war is won and no offer goes out. Event 133
requires `NAM_rtw_can_decide`; a human principal answers it, the AI by its
weights. 133 a saves itself as `NAM_board_armistice_acceptor` and calls
`NAM_board_poseidon_armistice` (terms 1: `NAM_board_poseidon_ebb` 180 days,
holders -5, the belt claims dropped; terms 2: holders -12, claimed belt land
NAM controls kept); `send_equipment` moves 3000 rifles to the acceptor; flag
`NAM_board_poseidon_truce` for 180 days; then `NAM_war_of_return_close`. 133 b
costs the principal 25 PP and sends event 134 to NAM, which clears the terms.
An offer whose 133 never fired lapses after 30 days (`NAM_rtw_expire_offers`).

**Renewal.** `NAM_exile_renew_war_of_return` is visible with
`NAM_wor_exile_war` or with "Посейдон" completed (a start that failed in the
same tick), plus `NAM_exile_return_programme_open`; `available` adds no
`NAM_board_poseidon_truce` and no `NAM_rtw_dictated_truce`. After the start it
calls `NAM_board_cells_rise` and `NAM_sub_apply_landing_charges` under
`NAM_corp_takeover`, restores the belt claims (`NAM_board_partition_claims`
behind `NAM_board_partition_fixed`) and reloads the wartime tree (appendix
G.2). The free landing does not repeat (`NAM_marines_orders_delivered`
stays); island brigades and the flagship do not repeat.

**Hook-up in existing script** (all in
`common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`):

- `NAM_wor_revenge_landing`: one branch after the harbour block and before the
  landing loop moves the island-capital orders to the harbour when
  `NAM_landing_at_harbour > 0` and `NAM_board_harbour_rising_ready = yes`;
- `NAM_war_of_return_close`: clears the rising sabotage on the six districts,
  removes `NAM_board_poseidon_beachhead` and ends with `NAM_rtw_close` behind
  `NAM_rtw_at_war`;
- `NAM_war_of_return_resolve_victory`: the cells close in its exile branch;
- `09_ADISCORD_scripted_peace_on_actions.txt`: no new country section; the
  island calls sit inside the existing `nam:` blocks of each native hook.

### D9. Events

Namespace `ADISCORD_nam_story`, file `events/ADISCORD_nam_resource_war_events.txt`,
registered in `tools/data/adiscord_event_ids.json` (subsystem `nam_story`).
Story events follow C.5 (`is_triggered_only`, `fire_only_once`, trigger
`NAM_board_opened` and `NAM_board_ended = 0`, answer a is the timeout default
and costs, prose only in the description). The operational events 125-134 are
not `fire_only_once` and keep their own validity. Ids 135-137 are the
subversion events (appendix F), 138-169 the wartime tree (appendix G, 170-179
reserved), 180 the backers' choice.

| Event | Source | Note |
| --- | --- | --- |
| 50-96 | the council focuses (appendix C.5) | eight absorbers fire a second, delayed event of a folded focus: 61, 69, 55, 65, 71, 58, 118, 100 |
| 81 | `partition_night` | its `immediate = { hidden_effect }` dispatches 97 (7 days), 180 (12), 122 (20) and 123 (40), so every answer and the timeout send the same chain |
| 97 | event 81 | "Двенадцать страниц", unchanged answers |
| 98, 99 | event 180 b / a, 30 days | the holders' advance, the pool's shares |
| 100 | `private_navy` (delayed) | b/c move the caps of programmes 5 and 2 |
| 101 | the first island launch, else "Посейдон" | writes `NAM_board_expedition_flag` (1 council, 2 chair's company, 3 old flag); each answer chains 124 while the war of return is active; before the partition night answer b charges the two vote leaders of the fresh ranking 3 trust each (tooltip `NAM_story_101_b_leaders_tt`, description `.d.leaders`), after it the two holders; no answer is a pure gain in either state |
| 102-117 | the outer-lane focuses that kept them (102-105 war economy, 106-109 supply, 110-113 fleet, 114-117 marines) | 104 c adds `NAM_board_porous_barrels`; 113 b raises the escort cap |
| 118 | `mainland_inventory` (delayed) | cells in all districts or in 688 and 700; answer b pays the two vote leaders |
| 119-121 | the three operation focuses | answer a gives readiness +5 |
| 122, 123 | event 81 (20 and 40 days) | holders and cells |
| 124 | "Посейдон" or event 101, only after a real start | descriptions `.d_rising` (flag `NAM_board_harbour_rose`) and `.d_cold`; every answer clears the flag |
| 125-127 | tenders of Ulven, Luren, Sharden | re-fired after a postponement; guarded by `NAM_isl_tender_done_<k>` |
| 128 | failed landing | reads `NAM_isl_last_target`; every answer clears it |
| 129 | unrest on an annexed island | reads `NAM_isl_flare_target`; every answer clears it |
| 130 | cell exposure | district in the global event target `NAM_board_cells_district` |
| 131 | "Отлив", Poseidon beachhead timeout | armistice offer or "Держать пляжи" |
| 132 | hidden | `NAM_isl_second_echelon` |
| 133 | to the first principal that can still decide (D8) | accept or refuse the armistice |
| 134 | refusal, to NAM | clears the terms |
| 180 | event 81 (12 days) | the backers' choice, section D5 |

### D10. Shared script and state

Effects (`common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`,
sections "Council of boards: mainland cells", "operation Poseidon", "invasion
preparation" and "island operations"):

| Effect | Scope and inputs | Does |
| --- | --- | --- |
| `NAM_board_holders_package` | NAM; temps `NAM_board_holders_gain`, `NAM_board_others_gain`, optional `NAM_board_chair_gain` | writes the six trust inputs itself (holders from `NAM_board_partition_efl` / `_azh`, the chair gain on `NAM_board_chair`) and calls `NAM_board_trust_package` once; callers set no trust inputs beforehand |
| `NAM_board_inv_cap_add` | NAM; temps `NAM_board_inv_k`, `NAM_board_inv_cap_change` | adds to a programme cap with its ceiling and the runs floor |
| `NAM_board_build_on_island` | NAM; temps `NAM_board_build_kind` (1 arms factory, 2 refinery, 3 dockyard, 4 conversion), `NAM_board_build_pref` (state) | tries the preferred state, then 228, 227, 225, 231, 226, 229, 230 (explicit rows), builds on the first held valid site, adds a slot where needed, leaves `NAM_board_site_built` |
| `NAM_board_pay_site_fallback` | NAM; temp `NAM_corp_capital_change` | pays the capital only when `NAM_board_site_built = 0` |
| `NAM_board_build_port_level`, `NAM_board_build_supply_hub`, `NAM_board_build_capital_naval_base` | state / NAM | port level or supply hub at the main port; set `NAM_board_site_built` |
| `NAM_board_raise_marine_division`, `NAM_board_raise_mercenary_brigade`, `NAM_board_launch_escorts` (temp `NAM_board_hulls`) | NAM | formations of the rewards and programmes |
| `NAM_board_inv_settle_<k>`, `NAM_board_inv_refund_<k>`, `NAM_board_inv_close` | NAM | programme result, refund, route-end refund of every running programme (nine explicit rows) |
| `NAM_isl_open_target` | NAM; temps `NAM_isl_k`, `NAM_isl_gain` | first readiness of an operation focus (+10 after `private_navy`) |
| `NAM_isl_op_launch`, `NAM_isl_launch_abort`, `NAM_isl_reinforce_defender`, `NAM_isl_land_first_wave`, `NAM_isl_second_echelon` | NAM (FROM, `NAM_isl_k`) / target | the landing (D6) |
| `NAM_isl_beachhead_check`, `NAM_isl_campaign_check`, `NAM_isl_monthly` | NAM | mission timeouts; dividends, unrest events and the capital hold |
| `NAM_isl_settle_victory` (temp `NAM_isl_member_stalled`), `_stalled` (temp `NAM_isl_quiet`), `_failed`, `NAM_isl_release`, `NAM_isl_close_external`, `NAM_isl_record_capitulation`, `NAM_isl_close_all` | NAM / any | terminal paths under the commit rule |
| `NAM_isl_island_rows` | NAM; temps `NAM_isl_rows_k`, `NAM_isl_rows_mode` (1 pacify, 2-4 event 129, 5 annexation transfer, 6 nationalisation) | one row per state of the island's explicit list |
| `NAM_isl_pacify_island`, `NAM_isl_nationalise_pay`, `NAM_isl_nationalise_finish`, `NAM_isl_tender_award`, `NAM_isl_tender_postpone`, `NAM_isl_flare_settle`, `NAM_isl_blame_pilots` | NAM | decisions and events of D6 |
| `NAM_board_cells_add` | state; temp `NAM_board_cells_change` | the only writer of `NAM_cells` |
| `NAM_board_cells_seed`, `_monthly`, `_rise`, `_close`, `NAM_board_partisan_template` | NAM | D7 |
| `NAM_board_poseidon_launch`, `NAM_board_poseidon_island_brigades`, `NAM_board_poseidon_island_brigade_1/2/3`, `NAM_board_poseidon_armistice` | NAM | D8 |

Triggers (`common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt`):
`NAM_board_holders_backing`, `NAM_board_inv_count_boycotts` (always true,
leaves the temp `NAM_board_inv_boycotts`), `NAM_board_invasion_backers_ready`,
`NAM_board_inv_arms_sponsor_ok_2` / `_4`, the site triggers
`NAM_board_inv_plant_site`, `_refinery_site`, `_port_site`,
`NAM_board_island_yard_ready`, `NAM_isl_staging_port_held`,
`NAM_isl_op_running`, `NAM_isl_island_held`, `NAM_isl_all_defeated`, the
`NAM_isl_from_*` launch conditions, `NAM_isl_pact_partner_ready`,
`NAM_isl_capitals_held`, `NAM_isl_main_capital_held`, `NAM_isl_any_foothold`,
`NAM_board_cells_open`, `NAM_board_cells_price_ready`,
`NAM_board_cells_safehouse_cover`, `NAM_board_harbour_rising_ready`,
`NAM_board_poseidon_marines_ready`, `NAM_board_poseidon_no_homeland_held`.

State (NAM unless noted):

- persistent for the campaign: `NAM_isl_status`, `NAM_board_isl_owner` (arrays
  created in `NAM_board_initialize`), the programme arrays,
  `NAM_board_expedition_flag`, `NAM_board_inv_backing` (written once by event
  180), `NAM_isl_tender_done_<k>`, `NAM_isl_sharden_promise_done`,
  `NAM_isl_sharden_blockade_done`; island cores stay when a state is later
  lost;
- one island war: `NAM_isl_op_target`, `NAM_isl_pact_member`,
  `NAM_isl_echelon_k`, `NAM_isl_echelon_day`, `NAM_isl_capital_hold` (40 days),
  `NAM_isl_capitulation_reserved` (2 days, on the defeated side); on the
  islands `NAM_isl_participant`, `NAM_isl_defence_mobilised`,
  `NAM_isl_pact_founder`; cleared by every terminal path;
- after a war: `NAM_isl_reopen_<k>` (90 or 120 days), `NAM_isl_alerted` (on
  the island), readiness on the capital state;
- running decisions: state flags `NAM_isl_prep_*`, `NAM_isl_bribed`,
  `NAM_isl_pacifying`, `NAM_isl_nationalising` with `NAM_isl_nationalise_paid`,
  `NAM_board_inv_work`, `NAM_board_cells_work`; country flags
  `NAM_isl_promise_running`, `NAM_isl_blockade_running`,
  `NAM_isl_insurance_running`, `NAM_isl_insured`;
- event records: `NAM_isl_last_target`, `NAM_isl_flare_target`,
  `NAM_isl_flare_<k>` (90 days), `NAM_board_cells_event_pending` (30 days),
  `NAM_board_armistice_terms`, `NAM_board_harbour_rose`;
- the return: `NAM_board_poseidon_truce` (180 days), `NAM_board_cells_running`,
  `NAM_cells` and `NAM_cells_raided` (120 days) on the six districts.

Pair routes and island rules are read through `has_completed_focus`; the
partition flag `NAM_board_partition_fixed` carries the safehouse rules, the
invasion category and the window, because those consumers must also work
while the wartime tree is loaded. Both trees are built as shared history
(`SHARED_HISTORY_SOURCES` of `tools/builders/build_adiscord_focus_trees.py`),
so completed corporate focuses stay completed across the swaps.

Scripted localisation (`common/scripted_localisation/ADISCORD_nam_resource_war_scripted_loc.txt`):
`NAMBoardHolderShortEfl` / `NAMBoardHolderShortAzh`, the invasion and island
reports, the island cost, wave, readiness and dividend lines, the cell price,
gain, tier and rising summary, and the district names of events 130 and the
raid.

### D11. Lifecycle

- End of the council (`NAM_board_end_operations`): `NAM_board_inv_close`,
  `NAM_isl_close_all` (refunds running preparations, pacifications,
  nationalisations, the blockade and the insurance; closes a running island war
  as a stalled landing without trust changes; clears the event records),
  `NAM_board_cells_close`, `NAM_board_inv_backing` cleared, and the wartime
  rows of appendix G.6 (`NAM_rtw_close` when the war still runs, then the
  bonds default) run before `NAM_dir_campaigns_close`, which stays last. The
  NAM categories hide at `NAM_board_ended = 1`, and so does the enemy's
  "Охранка".
- One island war at a time, never during another war or the war of return;
  pacification and nationalisation are peacetime decisions and do not block a
  new landing.
- Every island terminal path removes its missions; `NAM_war_of_return_close`
  removes the Poseidon mission.
- The cells end at the rising, at the end of the council, at a won return and
  at the dictated peace, never at an armistice.
- "Посейдон" hands the war to the wartime tree one day later; every terminal
  path of the war short of a won return restores this tree; the victory loads
  the mainland tree instead (appendices G and H).

### D12. AI

`NAM_exile_corporate_plan` (`common/ai_strategy_plans/ADISCORD_NAM_plans.txt`)
takes 44 focuses, one side of every pair: centre and Judas lanes first, then
the right wing to the fleet, the marines and Ulven, then the partition night,
then the left wing, war economy and supply inside the window, ending on
"Посейдон". Sides: `loren_receipt`, `factory_guard`, `hereditary_roll`,
`incumbents_credit`, `sole_vote_holder`, `cartel_prices`, `shore_depots`,
`shore_battalions`; answer a of event 180. Outside the plan:
`salt_monopoly`, `foundry_mark`, `harbour_exchange`, `residency_for_hire`,
`war_bonds`, `synthetic_plant`, `arsenal_of_the_boards`, `escort_flotilla`,
`company_docks`, Luren and Sharden. The AI takes Ulven only:
`luren_operation` and `sharden_operation` have `ai_will_do = { factor = 0 }`,
the launch weighs 50 on 648 only and needs more than 7 divisions, and the
Sharden decisions weigh 0. The subversion decisions read the age of
`NAM_board_partition_fixed` (45 days) to tell the network phase from the
landing phase of the window. Every NAM weight is quartered while capital is
below 100 or political power below 40. Strategies in
`common/ai_strategy/ADISCORD_nam_resource_war_ai.txt`: `NAM_isl_ai_landing`
(enabled by `NAM_isl_op_running`) and `NAM_board_poseidon_ai` (enabled by an
active war of return under the takeover).

### D13. Time and men

Points cost 7 days. Design estimates, not measured: on the AI plan the
partition night falls on about day 273, Ulven is taken on about day 259 and
settled before "Посейдон" checks `has_war = no`, and "Посейдон" falls on about
day 399. The AI route's focus rows give about 101 000 men, 65 000 rifles, 53
convoys and 45 000 fuel (the whole route about 104 000 men and 69 500 rifles).
Against the landing estimate of about 83 000 men and 65 000 rifles for a
coalition of 25-30 divisions, the AI route has about 118 500 men with the
interregnum, event answers, programmes and the native pool (110 500 without
the manpower answers) and about 100 000 rifles after six cell runs (82 000
without the arsenal orders). The Directory's own islands stay non-national, so
its native recruitable pool is about 1900. Cored islands at 1% recruitment:
Ulven 15 700 (Tarven 7200 of it), Luren 5400, Sharden 19 000 (18 740 after the
promise). Confirm the island wars and the return in recent text saves.

### D14. Tests

`tools/tests/test_adiscord_nam_focus.py`: `NamCompactTreeTests` (budget and
2-point focuses, removed ids, the backers' event, the window and the dispatch
of event 81, the delayed second events, the capstone requirements, the
fleet's island bonus, event 101 before the tenders, the invasion category on
the shortest route, the subversion AI window, the safehouse rules on the
partition flag); `NamInvasionBranchTests` (mirror and spacing, programmes,
islands, cells, "Посейдон", totals and the route end); the tree pins of
`test_island_focus_diagram_and_duration`, the reward-kinds table of
`test_every_playable_focus_gives_two_to_seven_kinds_of_reward` and the AI plan
test cover the whole tree. `tools/validators/inspect_nam_corporate_focus_layout.py`
checks the wiring.

### D15. What waits for the tree after the return

A won return no longer restores this tree: `NAM_rtw_restore_tree` skips the
reload when `NAM_war_of_return_won` is set, and `NAM_mdr_begin` loads
`NAM_mainland_directory_focus` (appendix H). An armistice, a dictated peace
or an external close still restores this tree. What the earlier versions of
this section listed as waiting is now in the script:

- the tree of the Directory on the mainland and its preparation for the War
  for the South (two to three years of focus time), with the great war against
  Rahma, Sardan and Kadir as its own stage (user decision 15); its loader does
  not call `NAM_board_end_operations`: the council runs on, and the route's
  end calls `NAM_mdr_close` before `NAM_dir_campaigns_close` (H.10);
- `admitted_owners_register` is the mainland focus `NAM_mdr_owners_register`
  with its old name, description and icon `GFX_focus_NAM_board_admitted_owners_register`;
  it calls `NAM_board_build_company_offices` on 700 behind
  `NAM_board_office_site`;
- the trunk pair is `NAM_mdr_union_of_boards` / `NAM_mdr_mainland_shares`;
  `NAM_mdr_begin` writes the snapshot `NAM_board_return_chair`; the course and
  the form of rule are read from completed focuses and `NAM_rtw_direct_rule`,
  never copied;
- the succession of every council and war law is the table of H.5.

What still waits is listed in H.13.

Runtime checks, all by the user after a full restart: the scripted landings
on 3094, 3313 and 3224 and `teleport_armies` inside a capital state;
`create_unit` on a province just taken; the rising provinces and their
teleport; resistance on annexed states and `cancel_resistance`; the
capital-hold settlement; the 90-day window and the dispatch of event 81; the
backers' choice answered and timed out; event 101 at the first launch; the
armistice offer and `NAM_war_of_return_close` after it; `send_equipment` of
the armistice; the refusal of a second target for the targeted programmes; the
war results in recent text saves.

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

## Appendix F. Subversive operations and the partition claims

Maintained contract of the layer opened by `NAM_board_partition_night`. The
script holds the values: decisions in `ADISCORD_nam_resource_war_decisions.txt`
(category `NAM_board_subversion`, counter `NAM_sub_counter` in
`NAM_cells_counter`), the section "Council of boards: subversive operations"
in the NAM effects and triggers, eight timed spirits in the NAM ideas file,
events `ADISCORD_nam_story.135`-`137`, scripted localisation `NAMSub*`, tests
`NamSubversionTests`.

### F.1 Opening and the partition night

The partition night's `completion_reward` opens the category with an
`unlock_decision_category_tooltip` pair at its head and calls
`NAM_board_partition_claims` once, before its story event 81. The
category is visible while `NAM_sub_open`: the council governs
(`NAM_board_operable`), `NAM_corp_takeover` and `NAM_board_partition_fixed`
are set (flags, so a tree swap keeps them), the war of return is not running
and has not been won. A target is valid (`NAM_sub_target_valid`) while it is
EFL or AZH, exists, is not NAM's subject, is not at war with NAM and owns and
controls its capital.

### F.2 Operations

Residency operations R1-R6 are targeted (EFL, AZH), run by company k and
covered by the holder of the target's partition share. Price is debited in
`complete_effect` behind `custom_cost_text` (`cost = 0`); the result settles in
`remove_effect`.

| Op | Decision | Runner | Price | Days | Success on the target | Spirit (days: 120 when the share holder is the runner, else 90) |
|---|---|---|---|---|---|---|
| R1 | `NAM_sub_sand_in_tanks_op` "Песок в цистернах" | 1 Лорэн | 20 PP, 80 capital | 45 | -5000 fuel | `NAM_sub_dry_tanks`: fuel gain -30%, max fuel -20% |
| R2 | `NAM_sub_bad_castings_op` "Брак на литейных заводах" | 2 Феррант | 20 PP, 80 capital | 45 | -2500 infantry equipment | `NAM_sub_bad_castings`: factory output -8%, max efficiency -5% |
| R3 | `NAM_sub_dock_fire_op` "Пожар в доках" | 3 Навис | 20 PP, 80 capital | 45 | -4 convoys | `NAM_sub_dock_fire`: dockyard output -15%, navy org -10% |
| R4 | `NAM_sub_bad_sights_op` "Сбитые прицелы" | 4 Арктур | 20 PP, 80 capital | 45 | charge `NAM_sub_sights_days` (90 or 60) waits for the landing | `NAM_sub_bad_sights` at the landing hour: army org -8%, defence -8% |
| R5 | `NAM_sub_labour_strike_op` "Стачка артелей" | 5 Сменком | 20 PP, 80 capital | 45 | -4000 manpower | `NAM_sub_labour_strike`: conscription -10%, mobilisation speed -15%, construction -10% |
| R6 | `NAM_sub_bond_crash_op` "Обвал облигаций" | 6 Рейдбанк | 20 PP, 80 capital | 45 | -40 PP | `NAM_sub_bond_crash`: PP gain -20%, consumer goods +3% |
| J1 | `NAM_sub_leaflets_op` "ПРОПАГАНДА: Листки с того берега" | chair, chancery slot | 30 PP, 60 capital | 60 | network +1 | `NAM_sub_leaflets` 120: war support -10%; cells in its mainland districts grow +3 a month (10-59 cells), raids take 10 fewer |
| J2 | `NAM_sub_trophy_quarrel_op` "Спор о трофеях" | chair, chancery slot | 40 PP, 100 capital | 60 | charge `NAM_sub_quarrel_ready`; holders +3, other four -2, chair +2 | `NAM_sub_trophy_quarrel` 120 on EFL and AZH at the landing hour: attack -5%, supply consumption +10% |

Availability. A residency operation needs: runner not boycotting
(`NAM_board_stance^k` not -1), the target's residency free (receipt
`NAM_sub_op_kind` absent, one per target), share holder not boycotting
(`NAM_sub_holder_backing`), the strike cap and no active own spirit (R4
instead: no waiting charge, `NAM_sub_sights_free_tt`). J1 needs a free slot,
no leaflets receipt, a valid target, the cap and no active leaflets spirit. J2
needs a free slot, both members valid and no waiting quarrel charge.

Strike cap. At most three strikes per target (`NAM_sub_below_cap`): the six
capped spirits (R1-R3, R5, R6, J1), the running residency operation and the
leaflets printed for it; the settling operation does not count itself
(`NAM_sub_cap_self`). R4 and J2 are landing charges outside the cap; one R4
charge per target.

Escrow. Residency receipt on the target (`NAM_sub_op_kind`,
`NAM_sub_op_capital` = 80); J1 receipt on NAM (`NAM_sub_leaflets_receipt` =
60, `NAM_sub_leaflets_target` 1/2); J2 receipt on NAM
(`NAM_sub_quarrel_receipt` = 100). Settlement, refund and exposure each clear
a receipt exactly once. Capital is refunded when the target became invalid,
the cap filled or the result is already in place, and on cancellation (war of
return, council stops governing, target invalid); political power and trust
are never refunded. No operation moves a resource to NAM or writes the cells.

### F.3 Risk, trust and network

`NAM_sub_risk_compute` (target scope, temp `NAM_sub_k`) is the one formula for
the roll, the tooltips and the report: base 20; residency run by the share
holder -10 (and -5 more with card index 1); cells cover (30+ cells in a
mainland district the target owns) -5; each network level -5 (max 2); card
index 2 -5; card index 3: Eflor -10, Azhar +5; alert `NAM_sub_vigilant` +15;
missed counter `NAM_sub_hunted` +10; clamped 5-50. Success: residency company
+2 and share holder +1 trust, the chair +2 for J1, network +1 (max 2). Event
137 (card index, fire once) follows a residency success once both targets
have a network. Exposure (`NAM_sub_expose`): no strike or charge, price lost,
residency company -4 and holder -2 (chair -4 for J1/J2), readiness -3, target
alert 120 days, network -1, event 136 for the target.

### F.4 The enemy's answer

Each launch rolls a hunch on the target (J2: on Eflor) with 50%, one flag per
operation: `NAM_sub_hunch_residency`, `NAM_sub_hunch_leaflets`,
`NAM_sub_hunch_quarrel`. Settlement, refund and exposure clear only their own
operation's hunch. `NAM_sub_counter` (EFL/AZH, 30 PP, 20 days) is visible
while `NAM_sub_counter_lead`: a smelled operation still runs. Available
without alert and without a war. At the end it picks a smelled running
operation in the order residency, leaflets, quarrel and catches it with 30%,
+10 against R4 or J2, -10 under cells cover, -10 when the share holder runs a
residency operation (10-40%). A catch exposes it and removes NAM's decision; a
miss sets the shared `NAM_sub_hunted` (+10 risk on the next operation against
that country to settle, cleared at any settlement). Either way the target is
on alert for 120 days. The category `NAM_cells_counter` also opens while an
operation runs against the country. Event 136 (EFL/AZH): open trial (+2% war
support) or quiet expulsion (+20 PP).

Event 135 hears one exposure at a time: `NAM_sub_expose` writes
`NAM_sub_exposed_target` and `_runner` and fires 135 only while no hearing is
pending; a second exposure before the answer pays all its costs but has no
hearing. Answers: blame the runner (-3 trust, or -15 PP without a chair), buy
silence (-40 capital, runner +3), or press the target (+3% war support, target
alert 180 days); each clears the record.

### F.5 Claims on the belt

`NAM_board_partition_claims`: claims on 720 Моренский округ, 721 Лоренское
порубежье, 723 Лоренский берег (Eflor's share) and 722 Ажарское взморье, 727
Западные промыслы (Azhar's share), each only while owned by EFL or AZH.
Consumers:

- victory in the exile war of return (`NAM_board_partition_take_belt`, before
  the participants are copied and released): every claimed belt state owned
  by a participant passes to NAM with control (`NAM_wor_take_state`), old
  cores stay; holders +5 trust when any passed;
- armistice on the council's terms (`NAM_board_armistice_terms` < 2): claims
  dropped (`NAM_board_partition_drop_claims`);
- armistice on the holders' terms (> 1): claimed belt states NAM controls and
  EFL/AZH still owns pass to NAM before the white peace
  (`NAM_board_partition_keep_belt`); the remaining claims stay;
- the recount: each share holder gets half a holding while NAM owns and
  controls belt land of its share (`NAM_board_belt_held_efl/azh`);
- event 133 AI: x1.5 acceptance with the trophy quarrel, x0.5 when the
  holders' terms would keep belt land;
- answer tooltips: 131 a and 133 a (council's terms) name the dropped claims
  while a claim exists (`NAM_board_belt_claimed`); 131 c names the kept land
  while a claim exists; 133 a names the ceded land when NAM controls claimed
  belt land on the holders' terms.

### F.6 Lifecycle

- Landing hour (`NAM_board_poseidon_launch` and the renewal decision):
  `NAM_sub_apply_landing_charges` turns R4 charges and the quarrel charge into
  spirits and clears them.
- Route end (`NAM_board_end_operations`): `NAM_sub_close` refunds every
  running operation's capital and slot, drops the landing charges and the
  hearing record.
- Victory: `NAM_sub_clear_target` on both targets (spirits, receipts,
  charges, network, alert, hunch and hunted flags), then `NAM_sub_close`.
- Defeat: `NAM_sub_clear_target` on both targets before the annexation.
- Armistice: operations stay closed during the war and reopen after it;
  spirits run out on their own timers.

### F.7 Unverified in the running game

Negative `add_fuel`, `add_equipment_to_stockpile` and `add_manpower` on a
foreign country; `remove_targeted_decision`/`remove_decision` called on NAM
from EFL/AZH scope; temp variables and `clamp_temp_variable` inside scripted
localisation triggers and FROM-scoped risk texts in decision tooltips; a
`random_list` entry raised from weight 0 by `add`; the belt transfer at
victory and armistice and native resistance in occupied claimed states.

## Appendix G. The wartime tree of the return

Maintained contract of `NAM_return_war_focus` "Война за возвращение", the
tree that the council plays during the war of return on the corporate route.
The script holds the values: source `focus_trees/NAM/return_war/focuses.txt`
(generated output `common/national_focus/ADISCORD_NAM_return_war.txt`, owner
`tools/builders/build_adiscord_focus_trees.py`), the section "Council of
boards: war of return" of the NAM effects, triggers, ideas, decisions and
scripted localisation, the category `NAM_rtw_war`, events
`ADISCORD_nam_story.138`-`169` (170-179 reserved), the AI plan
`NAM_return_war_plan`, tests `NamReturnWarTreeTests`. Nothing here was
checked in the running game.

**Author's orders (binding):** "Посейдон" declares the war through the
existing machinery and loads this tree ("последний фокус объявляет войну,
загружая другую ветку фокусов - военную на возвращение"); the tree is
mirrored around x 18 ("ветка должна быть такая же симметричная"); rewards as
in The Fire Rises, with locked laws and development trades ("пусть дают
законы разные, которые сменить нельзя. А ещё понижает уровень соц. развития,
но повышает другое"); partisans rise on enemy land; each enemy carries
penalties; defeat is the end and victory is complete dominion over Eflor and
Azhar with the Directory's own territory ("Поражение это полный конец; победа
это получение полностью владычества над Эфлором и Ажаром, ну и территории
своей, конечно"); wars and peace only through scripted focuses, decisions and
events.

### G.1 Identity and size

| Item | Value |
| --- | --- |
| Tree | `NAM_return_war_focus`, prefix `NAM_rtw_`, shared history, `default = no`, continuous focus position x 50, y 1600 |
| Weight | `factor = 0`; +300 for `original_tag = NAM` with `NAM_corp_takeover`, the global flag `NAM_wor_exile_war` and `NAM_war_of_return_active = yes` (above the south war tree's 200, so a hot reload keeps it) |
| Focuses | 32 on rows 0-10 in five lanes, 60 points (420 days); one side of each of the five pairs: 27 focuses, 48-50 points; shortest path to `return_treaty`: 14 focuses, 196 days |
| Icons | every focus binds its own `GFX_focus_NAM_rtw_<id>` (`interface/ADISCORD_national_focus.gfx`, shines in `interface/ADISCORD_focus_shines.gfx`, textures in `gfx/interface/goals/NAM/`) |
| AI plan | `NAM_return_war_plan`, 27 focuses, 49 points |

### G.2 Attachment and the swaps

- **Entry.** Inside the success branch of `NAM_board_poseidon_launch`, after
  the holders' package and before the beachhead mission: `NAM_rtw_begin`
  (flag `NAM_rtw_at_war`, whose age is the war's day count; `NAM_rtw_partisans`
  copied from the temp `NAM_board_partisans_raised` of the landing's rising;
  `NAM_rtw_renewed` cleared), then the hidden event `ADISCORD_nam_story.168`
  one day later, which runs `NAM_rtw_load_tree`: `load_focus_tree` with
  `keep_completed = yes` only while the war is active and the corporate tree
  is loaded, then `mark_focus_tree_layout_dirty`. The day's delay keeps the
  swap out of Poseidon's own `completion_reward`;
  `NAM_rtw_tree_next_day_tt` on "Посейдон" tells the player.
- **Exit.** `NAM_war_of_return_close` ends with `NAM_rtw_close` behind
  `NAM = { exists = yes has_country_flag = NAM_rtw_at_war }`, so every
  terminal path of the war (victory, defeat, armistices, dictated peace,
  external close) runs it. `NAM_rtw_close` first runs `NAM_rtw_fronts_close`
  (every receipt refunded by its holder, missions removed, offers and the
  decider cleared, NAM war spirits removed except `NAM_rtw_reparations` and
  `NAM_rtw_bond_default`, the enemy spirits removed through
  `NAM_rtw_clear_enemy_ideas`, administered and militia flags cleared), clears
  the war's counters and calls `NAM_rtw_restore_tree`: the corporate tree is
  loaded back with `keep_completed = yes` unless NAM has capitulated and
  `NAM_wor_pick_annexer` left `NAM_wor_annexer_found = 1`, or the return was
  won (`NAM_war_of_return_won`): then the war tree stays until
  `NAM_mdr_begin`, at the end of the victory's settlement, loads the mainland
  tree (appendix H.2).
- **Route end.** `NAM_board_end_operations` runs `NAM_rtw_close` while
  `NAM_rtw_at_war` is set, then `NAM_rtw_bonds_default`, then `NAM_mdr_close`,
  before `NAM_dir_campaigns_close`.
- **What the swap keeps.** Both trees are shared history, so completed
  corporate focuses and war focuses stay completed across every swap;
  running decisions (programmes, island pacification and nationalisation,
  development, campaigns, chancery, tenders) continue; the cells were spent
  by the rising and subversion is closed in the war (its charges were applied
  at the landing); the beachhead mission belongs to the war, not to a tree.
- **The way back.** `NAM_exile_renew_war_of_return` (not available during
  `NAM_board_poseidon_truce` or `NAM_rtw_dictated_truce`) restores the belt
  claims behind `NAM_board_partition_fixed`, and on the corporate route calls
  `NAM_rtw_begin`, sets `NAM_rtw_renewed` when the free landing was already
  spent (`NAM_marines_orders_delivered`) and loads the tree at once. Only
  principals that are still valid targets are registered again: a
  surrendered Eflor is a NAM subject and `NAM_wor_target_valid` refuses it.
  Completed war focuses, laws, trades and story events do not repeat; open
  focuses continue; bonds carry over.

### G.3 Lanes and pairs

```
row 0                                          [war_cabinet 18]
row 2         [north_front 7]   [strait_convoys 12]  [holders_war 16]x[chairmans_war 20]  [districts_rise 24]   [south_front 29]
row 4  [loren_coast 2] [svetlogorsk 5] [fields 9]             [war_bonds 18]             [dry_river 27] [harbour 31] [black_coast 34]
row 5                               [tankers 11]x[requisition 13]       [reprisals 23]x[amnesty 25]
row 6  [colonels 2]  [regime_crisis 6]x[march_loren 10]  [officers 16] [docks 20]  [storm_basin 26]x[concession 30]  [defectors 34]
row 7                                    [island_arsenals 12]           [district_militias 24]
row 8                [north_border 8]                  [left_behind 18]                  [south_border 28]
row 10                                         [return_treaty 18]
```

| id (`NAM_rtw_`) | Название | x,y | c | Prerequisites | Exclusive | Event |
| --- | --- | --- | --- | --- | --- | --- |
| `war_cabinet` | Военный кабинет на борту | 18,0 | 1 | - | | 138 |
| `holders_war` | Война держателей | 16,2 | 2 | war_cabinet | chairmans_war | 139 |
| `chairmans_war` | Чрезвычайные полномочия | 20,2 | 2 | war_cabinet | holders_war | 140 |
| `war_bonds` | Облигации возвращения | 18,4 | 2 | holders_war\|chairmans_war | | |
| `officers_at_front` | Офицеры на фронте | 16,6 | 2 | war_bonds | | 141 |
| `docks_at_war` | Доки в военное время | 20,6 | 2 | war_bonds | | 142 |
| `left_behind_registry` | Реестр оставленных | 18,8 | 2 | officers_at_front\|docks_at_war | | 143 |
| `return_treaty` | Договор о возвращении | 18,10 | 3 | left_behind_registry, north_border, south_border | | 144 |
| `north_front` | Северный фронт | 7,2 | 2 | war_cabinet | | 145 |
| `loren_coast_landing` | Десант на Лоренский берег | 2,4 | 1 | north_front | | |
| `svetlogorsk_rising` | Светлогорск встаёт | 5,4 | 2 | north_front | | |
| `northern_fields` | Северные промыслы | 9,4 | 2 | north_front | | |
| `loren_colonels` | Купленные полковники | 2,6 | 1 | loren_coast_landing\|svetlogorsk_rising | | |
| `loren_regime_crisis` | Кризис в Среднем Лорене | 6,6 | 2 | svetlogorsk_rising\|northern_fields | march_on_loren | 146 |
| `march_on_loren` | Марш на Средний Лорен | 10,6 | 3 | svetlogorsk_rising\|northern_fields | loren_regime_crisis | 147 |
| `north_border` | Северная граница | 8,8 | 2 | loren_regime_crisis\|march_on_loren | | 148 |
| `south_front` | Южный фронт | 29,2 | 2 | war_cabinet | | 149 |
| `dry_river` | Сухоречье | 27,4 | 2 | south_front | | |
| `harbour_fortress` | Крепость гавани | 31,4 | 2 | south_front | | |
| `black_coast_raid` | Налёт на Чёрный берег | 34,4 | 1 | south_front | | |
| `storm_black_basin` | Штурм Чёрного бассейна | 26,6 | 3 | harbour_fortress\|dry_river | basin_concession | 151 |
| `basin_concession` | Концессия семей бассейна | 30,6 | 2 | harbour_fortress\|dry_river | storm_black_basin | 150 |
| `basin_defectors` | Перебежчики бассейна | 34,6 | 1 | black_coast_raid\|harbour_fortress | | |
| `south_border` | Южная граница | 28,8 | 2 | basin_concession\|storm_black_basin | | 152 |
| `strait_convoys` | Конвойная линия | 12,2 | 1 | war_cabinet | | |
| `company_tankers` | Танкеры компаний | 11,5 | 2 | strait_convoys | strait_requisition | 153 |
| `strait_requisition` | Реквизиция пролива | 13,5 | 2 | strait_convoys | company_tankers | 154 |
| `island_arsenals` | Острова работают на фронт | 12,7 | 2 | company_tankers\|strait_requisition | | |
| `districts_rise` | Округа поднимаются | 24,2 | 1 | war_cabinet | | |
| `reprisals` | Суд над коллаборантами | 23,5 | 2 | districts_rise | amnesty | 156 |
| `amnesty` | Амнистия | 25,5 | 2 | districts_rise | reprisals | 155 |
| `district_militias` | Ополчение округов | 24,7 | 2 | amnesty\|reprisals | | |

Mirror of cells, not of content: the north (Eflor, a fragile regime with a
one-province capital) ends in a regime crisis that opens Eflor's surrender or
in the march on Middle Loren; the south (Azhar, a mobilised oil state) ends in
the Basin families' concession or the storm of the Black Basin; the strait
(hulls and fuel) faces the districts (people). Every cell has its mirror at
36 - x with mirrored prerequisites, partner and cost; same-row cards are at
least two columns apart; the longest single-prerequisite chain is two links;
the wiring model finds no card hit and two crossings, one OR merge per wing
pair.

Common blocks:

- every focus: `available = { has_capitulated = no custom_trigger_tooltip = { tooltip = NAM_rtw_war_live_tt NAM_war_of_return_active = yes } has_war = yes }`
  plus its own rows; `cancel_if_invalid = no`, `continue_if_invalid = no`;
- wing bypass: `north_front`, `svetlogorsk_rising`, `northern_fields`,
  `loren_coast_landing`, `march_on_loren`, `loren_colonels` bypass on
  `NAM_rtw_front_closed_efl` (Eflor gone, capitulated or out of the war with
  NAM), the six mirrored south focuses on `NAM_rtw_front_closed_azh`; the
  regime crisis, the concession and both borders never bypass, and the crisis
  and the concession require their front to be open, so a closed front leaves
  the bypassed side of the pair to satisfy the border's OR;
- map gates, explicit states without scans: `NAM_rtw_near_svetlogorsk`,
  `NAM_rtw_near_fields`, `NAM_rtw_near_loren` (720 or 691, the neighbours of
  701), `NAM_rtw_in_harbour` (province 16716), `NAM_rtw_near_dry_river`,
  `NAM_rtw_near_basin` (the neighbours of 69); the final needs
  `NAM_rtw_treaty_ready` (one front closed, or either principal above 40%
  surrender progress or with `NAM_rtw_capital_fallen`).

Five pairs:

| Lane | Side A | Side B |
| --- | --- | --- |
| Centre, the form of rule | `holders_war`: law `NAM_board_law_holders_contracts`, trade `NAM_board_trade_war_for_army`, men and rifles, holders' trust; victory gives the holders' company districts | `chairmans_war`: law `NAM_board_law_martial_rule`, trade `NAM_board_trade_war_for_state`, command power and experience; victory gives the council's direct rule (trigger `NAM_rtw_direct_rule`); an armed vote of no confidence is dissolved and none opens while a war of return runs |
| North | `loren_regime_crisis`: unlocks Eflor's surrender (W5), `NAM_rtw_loren_crisis` on Eflor, PP | `march_on_loren`: men, rifles and experience for the capital order on 701 |
| South | `basin_concession`: `NAM_rtw_families_turn` on Azhar, fuel, PP | `storm_black_basin`: men, support equipment, fuel, experience for the capital order on 69 |
| Strait | `company_tankers`: fuel, a refinery on the islands, Loren's charter line | `strait_requisition`: law `NAM_board_law_strait_requisition`, convoys, naval experience |
| Districts | `amnesty`: stability, men, the society programme, cheaper and faster administrations | `reprisals`: law `NAM_board_law_field_courts`, rifles, more men from each administration |

Moved corporate focuses: `war_cabinet` carries the beach masters' rifles,
support equipment, squad weapons, army experience and trust;
`districts_rise` carries `NAM_board_hospital_ships_spirit` (365 days) and the
social-system programme.

### G.4 Decisions

Category `NAM_rtw_war` "Война за возвращение" (`icon = military_operation`,
priority 27), visible with the tree loaded and `war_cabinet` completed; its
description is the scripted report `[NAMRtwWarReport]` (running order,
administrations, partisans, bonds, the two fronts, the form of rule, the day
of the line armistice). Every paid decision follows the custom cost contract
and is in `CUSTOM_COST_DECISIONS`.

**Refund rule.** Native removal runs no refund. Every paid run keeps a receipt
in the scope it belongs to (a district's state flag with a stored amount, or a
NAM variable); `cancel_effect`, the remove-time recheck and
`NAM_rtw_fronts_close` refund only while the receipt exists and clear it in
the same block, so a run is returned at most once.

| # | Decision | Opened by | Price | Days | Result |
| --- | --- | --- | --- | --- | --- |
| W1 | `NAM_rtw_order` "Приказ совета: [FROM.GetName]" (688, 67, 701, 700, 690, 69) | `war_cabinet`; each target by its front focus | 25 PP, 20 CP | instant | one order at a time: mission `NAM_rtw_order_mission` (75 days) or `NAM_rtw_capital_order_mission` (120 days, with `NAM_rtw_capital_assault`); success pays PP, war support, the share holder and a target result (701 / 69: `NAM_rtw_capital_fallen` on the owner); timeout `NAM_rtw_order_failed`; 30-day cooldown |
| W2 | `NAM_rtw_provisional_admin` "Временная администрация" (six districts) | `districts_rise` | 40 PP, 60 capital (20 PP and 30 days after `amnesty`) | 45 | state flag `NAM_rtw_administered`, compliance, men (more after `reprisals`); ownership does not change; two at once |
| W3a | `NAM_rtw_landing_loren_coast` "Десант на Лоренский берег" | `loren_coast_landing` | 60 capital, 25 PP, 4300 men, 3870 rifles; 15 convoys | 21 | port province 6495 seized and one marine division landed; once per campaign (`NAM_rtw_landed`) |
| W3b | `NAM_rtw_coal_raid` "Налёт на угольные причалы" | `black_coast_raid` | 50 capital, 25 PP, 1500 fuel; 15 convoys | 14 | naval base 493 damaged, `NAM_rtw_coal_blockade` on the owner; once per war |
| W4a | `NAM_rtw_buy_colonel` "Купить полковника Эфлора" | `loren_colonels` | 80 capital, 30 PP | 30 | `NAM_rtw_bought_colonels` and a manpower loss on Eflor, a defectors' brigade for NAM; twice per war |
| W4b | `NAM_rtw_lure_levy` "Переманить ополченцев бассейна" | `basin_defectors` | 60 capital, 30 PP | 30 | `NAM_rtw_levy_drained` and a manpower loss on Azhar, men for NAM; twice per war |
| W5 | `NAM_rtw_offer_surrender_efl` "Капитуляция Среднего Лорена" | `loren_regime_crisis`; the centre pair chosen; leverage (both of 67 and 688, Eflor above 25% surrender, its capital fallen or Azhar capitulated); no offer pending | 150 capital in escrow, 50 PP | instant | event 157 to Eflor; refusal or timeout returns the escrow (event 160, 60-day cooldown); acceptance spends it (G.6) |
| W6 | `NAM_rtw_sell_bonds` "Выпуск облигаций" | `war_bonds` | 10 PP | instant, re-enable 60 | 6000 rifles, one issue of `NAM_rtw_bonds` (at most three), Reidbank +2 |
| W7 | `NAM_rtw_boycott_measure` "Мера против бойкота" | `docks_at_war`; a boycotting company | 25 PP under direct rule, else 100 capital | instant, re-enable 90 | direct rule: requisition (6000 rifles, that company -15, the others -2, twice per war); otherwise buy-off (that company +15); event 165 |
| W8 | `NAM_rtw_line_armistice` "Перемирие по линии фронта" | `war_cabinet`; from day 180 of the war; a homeland district held; a principal able to answer; no offer pending | 50 PP | instant | event 161 to the decider (G.6) |
| W9 | `NAM_rtw_renewed_landing` "Повторная высадка" | `NAM_rtw_renewed` | 80 capital, 30 PP, 4300 men, 3870 rifles; 15 convoys | instant | the harbour province 16716 taken and one marine division landed |
| W10 | `NAM_rtw_district_militia` "Ополчение округа" | `district_militias`; administered district | 25 PP, 4000 men, 3600 rifles | 45 | one "Old Settlers Militia" on the district's rising province |
| W11 | `NAM_rtw_convoy_run` "Конвой через пролив" | `strait_convoys` | 30 capital, 1500 fuel | 60 | `NAM_rtw_convoy_line` for 60 days |
| W12 | `NAM_rtw_raise_district` "Поднять округ" | `districts_rise`; a district held by the enemy, not yet risen | 30 PP, 60 capital, 3000 rifles | 20 | `NAM_rtw_rise_state`: hostile armies leave, NAM takes the rising province, one partisan division, sabotage for 120 days; within the cap of eight partisan divisions per war (`NAM_rtw_partisans`) |

Both mission ids are registered in
`common/synchronized_dynamic_tokens/ADISCORD_tokens.txt`.

### G.5 War laws and development trades

Five locked laws in `common/ideas/ADISCORD_nam_resource_war_ideas.txt`
(`cost = 0`, `removal_cost = -1`, `available` scripted-only with a source
tooltip, `allowed_to_remove` false, economy refresh in `on_add` /
`on_remove`), enacted by `NAM_board_enact_<law>` with one `swap_ideas` branch
per law the slot can hold:

| Law | Slot | Enacted by | Succeeds | Repealed to |
| --- | --- | --- | --- | --- |
| `NAM_board_law_holders_contracts` "Подряды держателей" | `ADISCORD_industrial_policy_laws` | `holders_war` | the arsenal monopoly | `ADISCORD_industrial_policy_balanced_workshops` |
| `NAM_board_law_martial_rule` "Военное положение" | `ADISCORD_internal_security_laws` | `chairmans_war` | the district wardens | `ADISCORD_internal_security_local_garrisons` |
| `NAM_board_law_strait_requisition` "Реквизиция пролива" | `ADISCORD_infrastructure_laws` | `strait_requisition` | whatever the slot holds | `ADISCORD_infrastructure_patchwork_roads` |
| `NAM_board_law_field_courts` "Военно-полевые суды" | `ADISCORD_military_justice_laws` | `reprisals` | the concession courts | `ADISCORD_justice_regular_tribunals` |
| `NAM_board_law_veteran_reserve` "Резерв ветеранов возвращения" | `ADISCORD_training_laws` | `return_treaty` | whatever the slot holds | `ADISCORD_training_basic_drills` |

During the war only `NAM_board_repeal_laws` (the annexation) repeals them. A
route takes two or three of them. A slot holds one law (C.12): a council focus
completed after an armistice swaps the war law of its slot out by name, and
the war law does not return when the council law is repealed. After a won
return the mainland tree gives each of them its fate (appendix H.5): martial
rule is repealed at the first meeting on the mainland, the others are
succeeded by a law of the continent or kept.

Both sides of the centre pair carry one development trade
(`NAM_board_trade_war_for_army`, `NAM_board_trade_war_for_state`): the shared
`NAM_board_trade_war_lower_social` lowers whichever social track is above
level 1 (society first, then the social system) or, when both are at 1, adds
`NAM_rtw_home_front_strain` for 180 days; the raised track (army through
`NAM_board_dev_raise_army`, or state) pays 100 capital instead when it is
already at level 5; the economy is marked dirty.

### G.6 Endings

Terms: a principal is EFL or AZH while it is a participant of the war of
return; the form of rule is direct rule when `chairmans_war` is completed
(`NAM_rtw_direct_rule`), otherwise the holders' company districts. The form
decides how the Directory rules, never how much.

| Ending | Kind | Trigger | Transfers | Way back |
| --- | --- | --- | --- | --- |
| Victory | end of the war, won | every principal capitulated or gone (the capitulation callbacks), or Eflor's surrender with Azhar already down | see below | done: both are finished; the mainland tree loads (appendix H) |
| Eflor's surrender | Eflor finished, the war goes on | event 157 a after W5 | see below | Azhar by the war, or after a pause by the renewal |
| Armistice on the line | pause | event 161 a after W8 | every administered district still owned by a principal passes to NAM with its core; holders -5, the chair +3; 180-day `NAM_board_poseidon_truce`; claims kept | the renewal after 180 days |
| Stalled-landing armistice | pause | event 133 a of the first principal that can still decide (appendix D8) | 3000 rifles to the acceptor (terms 2 keep claimed belt land NAM controls); 180-day truce | the renewal after 180 days; it restores dropped belt claims |
| Dictated peace | pause, lost | monthly `NAM_rtw_dictate_check` -> event 158 a by the decider -> event 164 a or b | terms 1: an island (the most recently nationalised, else annexed, else state 230 unless it is the capital) to the decider, 10 000 rifles, capital debit up to 300, `NAM_rtw_reparations` 365 days, holders -15; terms 2 (or no island to cede): 20 000 rifles and 10 convoys (`convoy_1`, the variant of the `convoy` archetype; every grant and shipment of both trees names it; the shared island decision `NAM_island_convoy_service`, also opened by the main and defeated trees, keeps the archetype, a valid stockpile type), capital debit up to 500, `NAM_rtw_reparations` 540 days, holders -10, Reidbank +5; both: bonds defaulted, cells closed | the renewal after 360 days (`NAM_rtw_dictated_truce`); a ceded island returns at the victory, or at Eflor's surrender if Eflor holds it |
| External close | pause | `NAM_war_of_return_close_external` (not while `NAM_rtw_surrender_settling`) | none | the renewal at once |
| Defeat | end of the Directory | native capitulation of NAM -> `NAM_war_of_return_resolve_defeat` | the annexer takes the Directory with every island | none |

**Victory** (`NAM_war_of_return_resolve_victory`, in this order): the six
homeland fields return with NAM cores; ceded islands owned by EFL or AZH come
back with their status and concession owner
(`NAM_rtw_return_ceded_states`); the claimed belt passes
(`NAM_board_partition_take_belt`: 720, 721, 723, 722, 727); in the exile branch
the temp `NAM_rtw_settling_return = 1` makes `NAM_wor_settle_list_by_route`
call `NAM_rtw_settle_country` on each principal: its subjects become the
Directory's puppets, then under direct rule `NAM_wor_radical_annex` (the
country annexed, homeland cored, the rest flagged `NAM_conquered_state`), or
under the holders' form `NAM_wor_federal_district_join` with
`NAM_rtw_restore_district_control` (the district owns and controls all its
land; the holder of its share takes its concession). Then
`NAM_rtw_settle_victory`: a surrendered Eflor held as a provisional subject
is annexed (`NAM_rtw_annex_surrendered`), the homeland share taken at the
surrender is cored, bonds are repaid at 150 capital per issue (or defaulted:
`NAM_rtw_bond_default` and Reidbank -5), `left_behind_registry` pays its
restitution (10 000 men and 100 society progress), trust follows the form
(holders +10 and the other four -3, or the chair +10 and the holders -12),
and `return_treaty` fires event 169 "Доли материка". Nothing of Eflor or Azhar
stays independent. The same corporate block then calls `NAM_mdr_begin`
(appendix H.2).

**Eflor's surrender** (`NAM_rtw_accept_surrender_efl`, from 157 a), committed
before the white peace under the global flag `NAM_rtw_surrender_settling`:
whether Azhar is already down is recorded first; Eflor leaves the
participants, its major status and the coalition (Azhar becomes the primary);
the escrow is spent; every homeland state and belt state Eflor owns passes to
NAM (explicit rows, by ownership), and so does any island ceded to Eflor;
Eflor's field army is deleted; white peace; Eflor's war spirits and
subversion marks are cleared; the form of rule applies at once (holders'
district, or under direct rule `NAM_rtw_hold_surrendered`: a provisional
subject with no district flag, no concession and no dividend, annexed at the
victory); a live Azhar no longer at war is attacked again; then the campaign
routes to the victory when Azhar is down, else to the external close, which
closes only when nobody fights. Loren and Reidbank +3, event 159.

**The decider.** `NAM_rtw_pick_decider` saves the global target
`NAM_rtw_decider`: the primary, else Eflor, else Azhar, each only while at war
with NAM and not capitulated; every answer of 158, 161 and 164,
`NAM_rtw_dictated_peace` and `NAM_rtw_close` clear it. The dictated peace is
offered when no offer is pending, no cooldown runs, fewer than two refusals,
a decider exists, and either NAM's surrender progress passes the threshold
(0.35, after one refusal 0.45, without an owned core; 0.5 / 0.65 with one,
`NAM_rtw_holds_own_core`) or the war is past day 90 and NAM has been off the
mainland (`NAM_rtw_off_mainland`) for 60 days. An offer whose event never
fired lapses after 30 days (`NAM_rtw_expire_offers`).

**Symmetry.** The Directory always declares; no deadline or war-score award
decides; every ending short of capitulation needs the other side's answer
(157, 161, 158 and 164). The Directory can lose without annexation (the
dictated peace) and the coalition can lose a part (Eflor's surrender, the line
armistice). Both forms leave Eflor's land out of NAM's owned base until the
victory, so NAM's surrender maths is the same under either form. Verify in
recent text saves.

### G.7 Events

| Event | Source | Note |
| --- | --- | --- |
| 138-156 | the story focuses (centre 138-144, north 145-148, south 149-152, strait 153-154, districts 155-156) | three answers, C.5 rules, `fire_only_once`; in wartime also `NAM_war_of_return_active` except 143 and 144 |
| 157 | to Eflor from W5 | the refusal is the first (timeout) option; acceptance settles the surrender |
| 158 | to the decider from `NAM_rtw_dictate_check` | dictate terms or fight on |
| 159, 160 | NAM | the surrender signed (`.d_district` / `.d_annex`); the demand refused |
| 161 | to the decider from W8 | accept or refuse the line armistice |
| 162, 163 | NAM | the line holds; the line refused (90-day cooldown) |
| 164 | NAM from 158 a | accept terms 1, buy off with terms 2, or fight on (a second refusal ends the offers) |
| 165 | NAM from W7 | the company answers the measure |
| 166, 167 | NAM | order carried out; order failed |
| 168 | NAM, hidden | loads the tree one day after "Посейдон" |
| 169 | NAM from the victory with `return_treaty` | "Доли материка": spoils by votes, to the holders or to all six |

### G.8 State and lifecycle

War-scoped state, cleared by `NAM_rtw_close`: `NAM_rtw_at_war`,
`NAM_rtw_partisans`, `NAM_rtw_renewed`, `NAM_rtw_renewed_landed`, the order
variable, missions and cooldown, the administration and rising counters with
their state receipts, the landing, raid, colonel and levy receipts, the
surrender escrow, pending and cooldown flags, the line and dictate offers,
`NAM_rtw_off_mainland`, the decider, the requisitions, the NAM war spirits
and the enemy spirits. Kept across pauses: `NAM_wor_exile_war`, the claims, a
surrendered Eflor as NAM's subject (`NAM_rtw_annex_pending` under direct rule),
the laws, the completed war focuses, the bonds and the ceded-island arrays
(`NAM_rtw_ceded_states`, `NAM_rtw_ceded_status`, `NAM_rtw_ceded_owner`).
`NAM_rtw_landed` stays for the campaign. Nothing of this tree marks Eflor or
Azhar after it ends.

### G.9 AI

`NAM_return_war_plan` takes one side of each pair: the holders' war, the
regime crisis with Eflor's surrender, the storm of the Black Basin, the
company tankers and the amnesty, south first. `NAM_rtw_ai_fronts` shifts the
front requests towards Azhar (EFL -60, AZH +60) while both are participants at
war with NAM; `NAM_board_poseidon_ai` and the existing war-of-return
strategies stay. Decision weights are quartered below 40 PP or 100 capital.

### G.10 Unverified in the running game

The swap one day after "Посейдон" and the restore on every ending;
`keep_completed` with shared history in both directions; `delete_unit` without
a filter on Eflor; white peace and `declare_war_on` in one effect at the
surrender; `send_equipment` of convoys in the dictated peace; the
subject-of-an-annexed-overlord case at defeat; the map gates and bypasses on a
live front; the war results of two AI runs and one player run in recent text
saves.

## Appendix H. The Directory on the mainland

Maintained contract of `NAM_mainland_directory_focus` "Континент правлений",
the tree the council plays after a won war of return until the War for the
South. The script holds the values: source
`focus_trees/NAM/mainland_directory/focuses.txt` (generated output
`common/national_focus/ADISCORD_NAM_mainland_directory.txt`, owner
`tools/builders/build_adiscord_focus_trees.py`), the sections "Council of
boards: the continent" of the NAM effects, triggers, decisions, scripted
localisation and events, "Council of boards: laws of the continent" of
`common/ideas/ADISCORD_nam_resource_war_ideas.txt`, the categories
`NAM_mdr_army` and `NAM_mdr_south_office`, events
`ADISCORD_nam_story.181`-`222` (223-229 reserved in
`tools/data/adiscord_event_ids.json`), the AI plans
`NAM_mainland_directory_plan_holders` and `NAM_mainland_directory_plan_direct`,
tests `NamMainlandDirectoryTreeTests` and the `test_directory_*` tests of
`tools/tests/test_adiscord_south_final_war.py`. Nothing here was checked in
the running game.

**Author's orders (binding, his words):**

- "Сделай теперь ветку после возвращения и подготовке к войне за юг (фокус на
  2-3 года)": a separate tree loaded by the won war of return; the Directory on
  the mainland prepares the War for the South.
- Asked whether the great war against Rahma, Sardan and Kadir must remain its
  own stage between the return and the South: "Да, должна" (user decision 15).
  The desert war is a stage every playthrough passes; treaties may make it
  smaller but never replace it.
- Victory in the return is "получение полностью владычества над Эфлором и
  Ажаром, ну и территории своей, конечно": the tree starts with the homeland,
  the belt and the whole of Eflor and Azhar under the form of rule the wartime
  tree chose.
- "Ветка должна быть такая же симметричная" (mirror around the centre column,
  a free cell between neighbours, no straight chain longer than two); "по
  горизонтали можно расширить"; "пусть не всё обязательно выполнять будет".
- Rewards "как в the fire rises": several felt rewards of different kinds per
  focus, important focuses fire story events with three answers; "баффни
  фокусы. 300 людей условные - ни о чём"; "Пусть даёт не только эти награды
  просто! Также пусть дают законы разные, которые сменить нельзя. А ещё
  понижает уровень соц. развития, но повышает другое".
- Standing decisions 1-14 hold: the player is the council of six companies,
  not a chairman; the chair changes only by a vote of no confidence or the
  annual meeting; tenders are the player's choice; "99 на 1" is 99 percent
  poor and 1 percent rich; the state is "Светлогорская директория"; no
  mechanics in descriptions; wars, alliances and peace only through scripted
  focuses, decisions and events.

### H.1 Identity and size

| Item | Value |
| --- | --- |
| Tree | `NAM_mainland_directory_focus`, prefix `NAM_mdr_`, shared history (`SHARED_HISTORY_SOURCES`), `default = no`, continuous focus position x 50, y 1700 |
| Weight | `factor = 0`; +150 for `original_tag = NAM` with `NAM_corp_takeover`, the global flag `NAM_war_of_return_won`, `NOT = { ADISCORD_south_final_active = yes }` and `NOT = { has_global_flag = ADISCORD_south_hegemon_NAM }` (below the South war tree's 200 and the wartime tree's 300; after a won War for the South this modifier is off and the dominion tree's 160 wins a re-selection) |
| Focuses | 82 on rows 0-14 and columns 0-44 in nine branches, 154 points; ten exclusive pairs; every route (one side of each pair) is 64 focuses, 122 points, 854 days |
| Shortest path to "Час юга" | 8 focuses, 18 points by prerequisites; the real floor is the calendar of H.9 |
| Icons | every focus binds an existing corporate or wartime sprite (`GFX_focus_NAM_board_*`, `GFX_focus_NAM_rtw_*`), each used once; no `GFX_focus_NAM_mdr_*` sprite exists yet |
| AI plans | two plans of 50 focuses and 105 points (735 days), chosen by the form of rule (H.11) |
| Debug | `ADISCORD_nam_debug_tree_mainland_directory` in `common/decisions/ADISCORD_scenario_debug_decisions.txt` |

The title "Континент правлений" appears in the debug switch; like the other
NAM trees the tree id has no localisation key of its own.

### H.2 Attachment and loading

- **Entry.** `NAM_war_of_return_resolve_victory`, in its corporate block
  after `NAM_rtw_settle_victory`, calls `NAM = { NAM_mdr_begin = yes }`. The
  block runs only on the council's exile return. `NAM_mdr_begin` has its own
  limit (`tag = NAM`, `NAM_corp_takeover`, the global flags
  `NAM_wor_exile_war` and `NAM_war_of_return_won`, no `NAM_mdr_started`) and
  then: sets `NAM_mdr_started` (its age times the desert lapse), writes the
  snapshot `NAM_board_return_chair`, the display variables `NAM_mdr_lapse_day`
  and `NAM_mdr_lapse_left`, removes `NAM_metropolitan_garrison_charter` behind
  `has_idea` (the native mobilisation laws are free until a course locks the
  slot), creates the arrays `NAM_mdr_regiments` and `NAM_mdr_leases` (size 7),
  resizes `NAM_board_lot_awarded` to 7 (lots 4-6 are the mainland lots), creates
  the desert arrays
  `NAM_mdr_desert_escrow`, `NAM_mdr_offer_target`, `NAM_mdr_offer_dispatched`
  (size 4), sets the lot variables `NAM_mdr_lot_wells`, `_smelters`, `_yards`
  to 0, then `load_focus_tree = { tree = NAM_mainland_directory_focus
  keep_completed = yes }`, `mark_focus_tree_layout_dirty` and
  `ADISCORD_economy_mark_dirty`.
- **No corporate reload after a won return.** `NAM_rtw_restore_tree` reloads
  the corporate tree only without `NAM_war_of_return_won`; the victory sets the
  flag before `NAM_war_of_return_close` reaches the restore. Every armistice,
  the dictated peace and an external close still restore the corporate tree,
  and the victory of a renewed war loads this one.
- **The root.** Only `flag_over_harbour` carries `NAM_mdr_tree_live` (hidden:
  `NAM_corp_takeover`, `NAM_war_of_return_won`, `is_subject = no`); the other
  focuses have no common `available`. Every focus has `cancel_if_invalid = no`
  and `continue_if_invalid = no`.

Both forms of rule load the same tree; the form is never copied. Every reader
uses `NAM_rtw_direct_rule` (the completed `NAM_rtw_chairmans_war`):

| | Holders' company districts (`NAM_rtw_direct_rule = no`) | Council's direct rule (`NAM_rtw_direct_rule = yes`) |
| --- | --- | --- |
| Eflor and Azhar at the load | EFL and AZH are company districts (`autonomy_NAM_federal_district`) with armies, cores, dividends and disputes | annexed, non-core, in `NAM_conquered_states` |
| Integration side of a wing | `NAM_mdr_absorb_district`: the district is annexed with its army, its concession, recruits and dividend end, its land becomes conquered land (`NAM_wor_take_state`) and its capital state is cored; then nationalisation from compliance 20 | nationalisation from compliance 40 (30 on Eflor's land after "Лицеи Лорена") |
| Extraction side of a wing | the district's charter (`NAM_mdr_chartered_district`: dividend x1.5 in `NAM_corp_districts_monthly`) and the district regiments (D5) | state leases to companies (D4, event 213) |
| Building rows | on NAM land or on a company district's land (`NAM_mdr_owned_by_directory`) | on NAM land |
| Incidents below consolidation 70 | from `NAM_federal_districts` | the incident picker also reads `NAM_conquered_states` |
| AI plan | both extraction sides | Eflor's integration, Azhar's extraction |

The form decides how the wings play, never their extent: both forms reach
every focus.

What the tree keeps: completed corporate and war focuses (shared history);
every council and war law until a focus of this tree succeeds or repeals it
(H.5); the timed spirits of earlier trees to expiry; trust, stance, votes,
the chair, the chancery, campaign places, island status and owners, district
owners, the frozen partition holders `NAM_board_partition_efl` / `_azh` and
consolidation; the landing army, the war's formations and the partisan
divisions ("Mainland Partisans"), whose fate the home-district pair decides.

### H.3 Branches and pairs

Columns: Eflor's land and the army x 0-8, the home districts and the rear
x 10-16, the centre x 18-26, the council and the chancery x 28-34, Azhar's
land and oil, arsenal and fleet x 36-44. Upper stage rows 0-8 (ruling the
continent), lower stage rows 9-14 (the road south). Ids without `NAM_mdr_`:

```
row 0                                              [flag 22]
row 1  [governors 4]        [homes 13]                                   [register 31]        [wells 40]
row 2                                     [union 20]x[shares 24]
row 3 [colonels 2][alum 6] [harbour 11][svetl 15]                 [division 29][exchange 33] [hills 38][families 42]
row 4  [dextung 4]          [lists 13]   [regim 18] [meeting 22] [levy 26]  [constit 31]   [refin 40]
row 6 [prov 2]x[conc 6]    [trials 11]x[oblivion 15]  [desert_q 22]   [heirs 29]x[escheat 33] [oilconc 38]x[nation 42]
row 7 [lyc 0][legions 4][smelt 8] [home_distr 13]                        [six 31]   [divid 36][coast 40][levy 44]
row 8                      [gendarm 11][guards 15] [march 20]x[concess 24] [committees 29][garrisons 33]
row 9  [staff 4]            [damir 13]                                    [chancery 31]        [charter 40]
row 10                                           [south_distr 22]
row 11 [marines 2][school 6] [rail 11][depots 15]                 [agents 29][fenn 33]     [yards 38][crack 42]
row 12 [armies 4]           [line 13]   [s_charter 18][s_staff 22][nat_war 26] [mazar_q 31]  [arsenal 40]
row 13 [armour 2]x[infantry 6] [duty 11]x[contracts 15]          [protect 29]x[alliance 33] [tankers 38]x[fleet 42]
row 14 [mech 0][army_south 4][water 8] [rear 13]   [HOUR 22]   [north_charter 31] [fuel_tr 36][arsenal_dir 40][marines 44]
```

**Mirror rule.** Every cell (x, y) has its mirror at (44 - x, y) with
mirrored prerequisite groups, exclusive partner and equal cost; the root
stands on x 22; same-row cards are at least two columns apart; the longest
single-prerequisite chain is two links (the third step is an OR merge or a
pair); every exclusive pair stands on one row with no card between its cells.
Mirror of cells, not of content: Eflor (a fragile regime: governors, colonels,
Dekhtung's archive, aluminium) faces Azhar (a mobilised oil state: wells, the
Basin families, the hill levy, refineries, the coast); the home districts
(people) face the council (owners); the army faces oil, arsenal and fleet; the
rear faces the chancery.

| Branch | Focuses / points | Pair (row) | Side A | Side B | Rejoin |
| --- | --- | --- | --- | --- | --- |
| Centre: the state | 14 / 32 (with the desert) | `union_of_boards` "Союз правлений" / `mainland_shares` "Материковые акции" (2) | a federation of company domains: law `NAM_mdr_law_company_tithes`, trade `NAM_board_trade_war_for_economic`, domain votes, then `company_regiments` (law `NAM_mdr_law_company_levy`, D7) and `southern_charter` (D11; the South divided into company districts) | one joint-stock state: law `NAM_mdr_law_share_register`, trade `NAM_board_trade_war_for_state`, the golden share, then `shareholders_levy` (law `NAM_mdr_law_register_levy`, D8) and `national_war` (D12, D3 on desert land; the South annexed) | `first_mainland_meeting`; "Час юга" takes either course capstone |
| Centre: the desert | (same) | `desert_march` "Поход в пустыню" / `desert_concessions` "Пустынные концессии" (8) | the great war at once on Kadir, Sardan and Rahma: command power, experience, rifles, lorries, `NAM_mdr_desert_march_spirit` 180 days | treaties first (D13), then "Последний довод" (D14) on every emirate left; capital, Reidbank's trust; `ai_will_do = 0` | `southern_districts` |
| Eflor's land | 9 / 15 | `eflor_province` "Эфлорская губерния" / `eflor_concession` "Концессия Эфлор" (6) | integration (H.2), state programme, D3 on Eflor's land; event 217 later | extraction (H.2), economic trade, D5 or D4; event 218 later | `eflor_legions` |
| Azhar's land | 9 / 15 | `wells_nationalised` "Национализация скважин" / `basin_oil_concession` "Нефтяная концессия Бассейна" (6) | integration, `NAM_mdr_state_wells`, D3 on Azhar's land, then `basin_levy_reform` (`NAM_mdr_basin_levy`); event 219 later | extraction, `NAM_mdr_basin_lease`, economic trade, D5 or D4, then `oil_bonds`; event 220 later | `black_coast` |
| Home districts | 9 / 15 | `collaborator_trials` "Суд над пособниками" / `act_of_oblivion` "Акт о забвении" (6) | law `NAM_mdr_law_district_tribunals`, D2 purges, then `partisan_gendarmes` (partisans disbanded, law `NAM_mdr_law_gendarmerie`) | the regular courts back (`NAM_mdr_restore_regular_courts`), society programme, cheaper restitution, then `partisan_guards` (two line brigades) | `home_districts` |
| Council of six | 9 / 15 | `heirs_treaty` "Договор с наследниками" / `escheated_estates` "Выморочное наследство" (6) | the Judases' heirs sign: D9 veterans, then `exchange_committees` (society programme) | the council takes the estates (`NAM_mdr_grant_estates`: two holdings for the chair's company), then `estate_garrisons` (`NAM_mdr_estate_guards`) | `directory_of_six` |
| Army | 9 / 16 | `armoured_fist` "Бронированный кулак" / `infantry_corps` "Пехотные корпуса" (13) | armour research bonus, `NAM_mdr_armoured_doctrine`, D19 armoured columns, then `desert_mechanics` | artillery research bonus for the field divisions, then `desert_water` (`NAM_mdr_desert_water`) | `army_of_the_south` |
| Oil, arsenal, fleet | 9 / 16 | `fleet_of_the_coast` "Флот Чёрного берега" / `tanker_armada` "Танкерная армада" (13) | a cruiser (`ADISCORD_cruiser_2163`) and two escorts, then `coastal_marines` (marines, `NAM_mdr_coastal_landing`) | fuel, a silo, `NAM_mdr_fuel_logistics`, then `fuel_trains` (D21) | `arsenal_of_the_directory` |
| Rear and roads | 7 / 15 | `road_duty` "Дорожная повинность" / `road_contracts` "Дорожные подряды" (13) | law `NAM_mdr_law_road_duty`, state trade, infrastructure | law `NAM_mdr_law_road_contracts`, cheaper D6 (and D6 itself when the railway was not taken) | `rear_of_the_south` |
| Southern chancery | 7 / 15 | `mazar_protectorate` "Опека над Мазаром" / `mazar_alliance` "Союз с Мазаром" (13) | `MZR = { ADISCORD_south_demand_submission = yes }` through the shared South queue | `MZR = { ADISCORD_south_offer_alliance = yes }`, D23 after a refusal | `northern_charter` |

Other material rows by branch, all through the shared effects of H.8:
the centre's `flag_over_harbour` (political power, stability, command power,
consolidation, trust), `first_mainland_meeting` (martial rule repealed, a
fourth Directory campaign place, `NAM_dir_campaign_slots` clamped to 4),
`desert_question`, `southern_districts` (manpower, compliance +10 on every
conquered state, a supply node at 240 or 700), `southern_staff`
(`NAM_mdr_staff_spirit`, D10) and `hour_of_the_south` (H.9). Eflor: `loren_colonels`,
`loren_aluminium` (Ferrant's charter grant, a military factory),
`dextung_files` (`NAM_mdr_dextung_lists`), `loren_lyceums` (cultural
programme), `eflor_legions` (two field divisions), `smelter_shares` (a
military factory). Azhar: `basin_wells` (fuel reserve), `hill_villages`
(infrastructure), `basin_families`, `basin_refineries` (Loren's charter grant,
a synthetic refinery and a silo), `black_coast` (a dockyard, a cruiser
`ADISCORD_cruiser_2155` and two escorts). Home: `back_to_homes` (D1, society
programme), `harbour_rebuilt` (a civilian factory at 700 and a naval base level
on province 16716), `svetlogorsk_rebuilt` (civilian factories and
infrastructure, social-system programme), `collaborators_lists`,
`home_districts` (infrastructure). Council: `owners_register` (the former
corporate `admitted_owners_register`: state programme and the company offices
on 700 through `NAM_board_build_company_offices` behind `NAM_board_office_site`),
`division_of_continent` (D18), `continental_exchange` (law
`NAM_mdr_law_continental_exchange`), `boards_constitution`, `directory_of_six`.
Army: `general_staff` (law `NAM_mdr_law_general_staff`), `marines_to_line`
(D20), `loren_war_school` (`NAM_mdr_war_school`, army programme),
`field_armies` (law `NAM_mdr_law_field_armies`, two field divisions),
`army_of_the_south` (`NAM_mdr_army_of_south`, two field divisions). Oil:
`war_charter` (law `NAM_mdr_law_war_charter`, a military factory),
`black_coast_yards` (a dockyard), `cracking_plants` (a synthetic refinery),
`southern_arsenal` (Arktur's charter grant, the arsenal preview
`NAM_board_preview_mdr_arsenal`), `arsenal_of_the_directory` (a military
factory). Rear: `damir_road` (infrastructure), `southern_railway`
(infrastructure, a supply node, D6), `fuel_depots_south` (a silo,
`NAM_mdr_desert_depots`), `damir_line` (`NAM_mdr_build_line`: bunkers on
provinces 16722, 16743, 6193 and 2804), `rear_of_the_south`
(`NAM_mdr_rear_spirit`, a supply node, fuel). Chancery: `southern_chancery`,
`furnace_agents` (D15-D17, `NAM_mdr_furnace_rumours` on SHL), `fenn_guarantee`
(WEF: opinion `NAM_mdr_fenn_protection` +30 and 6000 rifles by
`send_equipment`; bypassed when WEF does not exist or is a subject),
`mazar_question` (Mazar's acceptance +25 in `ADISCORD_south.40`),
`northern_charter` (law `NAM_mdr_law_southern_mandate`,
`NAM_mdr_charter_published` on SHL).

Course gates: `company_regiments` and `southern_charter` carry `allow_branch =
{ NOT = { has_completed_focus = NAM_mdr_mainland_shares } }`,
`shareholders_levy` and `national_war` the mirror; `southern_charter` and
`national_war` also need their course focus in `available`. Bypasses: the
desert pair on `NAM_mdr_south_open` (both sides bypass and
`southern_districts` takes the OR); `fenn_guarantee` on WEF gone or a subject;
the Mazar pair on `NAM_mdr_mazar_settled`; "Час юга" on
`ADISCORD_south_final_started` or `ADISCORD_south_final_resolved`.

Reader order: a reward that changes the vote count queues the recount
(`NAM_board_queue_recount`) instead of recounting inline, so readers of
`has_completed_focus` already see the focus. No flag mirrors a completion:
the course, the domain votes, the golden share, the constitution, the
development caps, the oblivion price, the road contracts, the charter
dividend, the nationalisation and lease openings and the SLF condition read
`has_completed_focus`.

### H.4 The desert stage

- **The stage.** The desert closes only by the existing great war
  (`NAM_great_war_start`), on both sides of the centre pair. "Поход в
  пустыню" declares it on all three emirates in its reward; its `available`
  is `NAM_great_war_can_start` with the consolidation-70 and target tooltips.
  On "Пустынные концессии" the council first offers treaties (D13) to at most
  two emirates of its choice: `NAM_mdr_desert_treaty_room` is false once two
  of KDR, SDR and RHM are NAM's subjects or hold `NAM_mdr_offer_pending`. Then
  "Последний довод" (D14) declares the same great war on every emirate that is
  still a `NAM_wor_independent_target`. No third treaty can be offered, so at
  least one emirate is always left for the war; no route buys the whole desert.
- **The treaty.** D13 debits 50 political power and a 60 capital escrow
  (inside the decision: escrow `NAM_mdr_desert_escrow^<1 KDR, 2 SDR, 3
  RHM>`, timed flag `NAM_mdr_offer_pending` 30 days on the emirate, hidden event
  214 one day later). Event 214 runs `NAM_mdr_desert_dispatch`: each escrow not
  yet dispatched goes to its emirate as event 209 while
  `NAM_mdr_desert_offer_live` holds, otherwise it is refunded. Answer a
  (`NAM_mdr_desert_sign`) spends the escrow and makes the emirate a company
  district through `NAM_wor_federal_district_join` (temp
  `NAM_mdr_skip_tender_queue = 1`: the treaty has its own tender, event 210);
  answer b (`NAM_mdr_desert_refuse`) returns the escrow and sets
  `NAM_mdr_offer_refused` for 90 days, after which the emirate may be offered
  again while room remains; answer c (`NAM_mdr_desert_void`), shown only when
  the offer lapsed or a great war is active, refunds and makes no district.
  Acceptance AI: base 40, +20 when NAM is more than twice as strong, +15 with
  two neighbours that are NAM or its subjects, +15 when another emirate already
  signed, +10 after event 186 c (`NAM_mdr_council_seat_promised`), -30 in SHL's
  faction or SHL's subject; refusal 60.
- **The war with treaty districts.** `NAM_wor_register_target` registers only
  `NAM_wor_target_valid` countries, which excludes NAM's subjects: a treaty
  district is never a participant or the primary, enters the war as NAM's
  subject (`can_decline_call_to_war = no`) and is not settled again at the
  victory. D14 waits for every pending answer
  (`NAM_mdr_desert_no_offer_pending`) and event 209 refuses to act during an
  active great war, so no participant becomes a district mid-war.
- **Settlement by course.** `NAM_wor_settle_list_by_route` has, after the
  return temp and the radical branch, `else_if` NAM has `NAM_corp_takeover` and
  `NAM_mdr_mainland_shares`: `NAM_wor_radical_annex` (annexed, non-core,
  conquered array); the final `else` (`NAM_wor_federal_district_join`) serves
  "Союз правлений" and, on the corporate route after `NAM_mdr_started`, queues
  the district for event 212 (`NAM_mdr_queue_district_tender`). On the
  concession side only the emirates fought are settled.
- **The lapse (failure path).** `NAM_mdr_desert_lapse_check`, called at the end
  of `NAM_consolidation_monthly`: 540 days after `NAM_mdr_started`, with no
  great war in progress and `NAM_mdr_desert_closed` false, it sets the global
  flag `NAM_mdr_desert_lapsed`, refunds every open escrow, fires event 216
  (stability -0.05, war support -0.05, consolidation -10, Arktur -6, Loren -4)
  and calls `ADISCORD_south_begin_preparation`. `NAM_south_story_pending`
  reads the flag, so the South freeze ends; the desert pair is bypassed
  through `NAM_mdr_south_open`, D13 and D14 hide, and `NAM_renew_great_war`
  hides after the lapse, so a Mazar alliance made later is never broken by the
  great war's `leave_faction`. The emirates not bought stay independent and
  open to Shahrabad: the lasting cost of skipping the stage. No date row: the
  South deadline counts from contact.
- **Triggers.** `NAM_mdr_desert_closed` (no great war active, and the war won
  or no target left), `NAM_mdr_south_open` (no great war active, and the desert
  closed or lapsed; carries `NAM_mdr_south_open_tt`). The category text of
  `NAM_consolidation` ends with `[NAMMdrDesertStatus]` (not started, open with
  the lapse date, at war, closed, lapsed).

### H.5 Fate of every exile and war law

"Succeeded" means `NAM_mdr_enact_<law>` swaps the named law out first, then
every other law the slot can hold, `add_ideas` only for an empty slot, then
`NAM_board_law_lock_tt`. "Repealed" means a visible swap to the slot default.

| Slot | Held at the hand-over | Fate | By |
| --- | --- | --- | --- |
| taxation | `NAM_board_law_property_census` or a native tax law | succeeded by `NAM_mdr_law_company_tithes` "Десятина правлений" or `NAM_mdr_law_share_register` "Акционерный реестр" | the centre pair |
| information | `NAM_board_law_paid_publicity` or a native law | succeeded by `NAM_mdr_law_southern_mandate` "Южный мандат"; kept when the capstone is skipped | `northern_charter` |
| military justice | war `NAM_board_law_field_courts`, else `NAM_board_law_concession_courts` or the default | succeeded by `NAM_mdr_law_district_tribunals` "Окружные трибуналы", or repealed to `ADISCORD_justice_regular_tribunals` (`NAM_mdr_restore_regular_courts`) | the home-district pair |
| trade | `NAM_board_law_harbour_exchange` or a native trade law | succeeded by `NAM_mdr_law_continental_exchange` "Континентальная биржа" | `continental_exchange` |
| officer corps | `NAM_board_law_hereditary_patents`, `NAM_board_law_sworn_commanders` or a native law | succeeded by `NAM_mdr_law_general_staff` "Генеральный штаб Директории" | `general_staff` |
| internal security | direct rule: war `NAM_board_law_martial_rule`; holders: `NAM_board_law_district_wardens` or a native law | martial rule repealed to `ADISCORD_internal_security_local_garrisons` (`NAM_mdr_end_martial_rule`); the slot then succeeded by `NAM_mdr_law_gendarmerie` "Окружная жандармерия" on the trials route, kept on the oblivion route | `first_mainland_meeting`; `partisan_gendarmes` |
| industrial policy | holders: war `NAM_board_law_holders_contracts`; direct rule: `NAM_board_law_arsenal_monopoly` or a native law | succeeded by `NAM_mdr_law_war_charter` "Военный устав континента" | `war_charter` |
| military organisation | `NAM_board_law_factory_guard` or a native law | succeeded by `NAM_mdr_law_field_armies` "Полевые армии" | `field_armies` |
| infrastructure | war `NAM_board_law_strait_requisition` or a native law | succeeded by `NAM_mdr_law_road_duty` "Дорожная повинность" or `NAM_mdr_law_road_contracts` "Дорожные подряды" | the rear pair |
| mobilisation (`mobilization_laws`) | `disarmed_nation` (the garrison charter removed by `NAM_mdr_begin`) | locked by `NAM_mdr_law_company_levy` "Наём правлений" (union) or `NAM_mdr_law_register_levy` "Номер в реестре" (shares); the native choice stays free while the leaf is not taken | `company_regiments` / `shareholders_levy` |
| welfare | `NAM_welfare_society_99_1` | kept: the society of 99 to 1 is the Directory's own; the trades carry its price | - |
| cultural policy | `NAM_board_law_mourning_licence` or `NAM_board_law_permitted_dissent` | kept | - |
| labour policy | `NAM_board_law_residency_for_hire` or its default | kept | - |
| logistics | `NAM_board_law_captains_share` or its default | kept | - |
| training | war `NAM_board_law_veteran_reserve` or a native law | kept | - |

The thirteen laws follow the council-law template (`cost = 0`, `removal_cost =
-1`, `allowed = { tag = NAM }`, `visible` self, scripted-only `available`
behind `NAM_mdr_law_<x>_source_tt`, `allowed_to_remove` false behind
`NAM_board_law_locked_tt`, `cancel_if_invalid = no`, `ai_will_do = 0`, economy
refresh in `on_add` / `on_remove`). `NAM_board_repeal_laws` (annexation only)
repeals each to the slot default (`export_focus` for trade, `disarmed_nation`
for both mobilisation laws). A route enacts eight to ten of them.

**Development trades.** The centre pair carries one trade on each side
(`union_of_boards`: `NAM_board_trade_war_for_economic`; `mainland_shares`:
`NAM_board_trade_war_for_state`); both wing extraction sides carry
`NAM_board_trade_war_for_economic`; `road_duty` carries
`NAM_board_trade_war_for_state`. Each lowers a social track through the shared
`NAM_board_trade_war_lower_social` (society first, then the social system, or
`NAM_rtw_home_front_strain` for 180 days when both are at 1) and raises the
other track, or pays 100 capital when that track is already at level 5. The
economic raise passes `ADISCORD_economy_check_economic_development_upgrade`;
banked progress waits for the monthly tick. A route takes up to four trades.

### H.6 The council at the scale of a continent

The council continues unchanged: trust, stance, the recount and the majority,
blocked products, the annual meeting (the chair strictly to the top company,
decision 11), the vote of no confidence, the chancery, the cabinet and company
traits, tenders as the player's choice, the Directory campaigns, development
programmes, islands, free zones, the holders' dividends and disputes,
consolidation. What changes scale:

| Item | Mainland rule | Where |
| --- | --- | --- |
| Mainland lots | wells (Loren / Reidbank), smelters (Ferrant / Smenkom), yards (Navis / Arktur), one at a time by D18 and event 215 through `NAM_board_close_tender` with `NAM_board_lot_input` 4-6, in the cycle wells -> smelters -> yards -> wells from the first lot `NAM_mdr_lot_order` (1 wells, 2 smelters, 3 yards; unset reads 1) that event 200 writes (a drawn, b wells, c yards); the triggers `NAM_mdr_tender_next_wells`, `_smelters`, `_yards` pick the next open lot for event 215 and D18; an awarded lot stores the company and counts 3 votes as an industry; a lot kept in the treasury stores -1, counts nowhere and pays 10 capital a month | `NAM_board_count_industries`, `NAM_corp_monthly` |
| Domain votes ("Союз правлений") | one more vote for each district concession and each awarded mainland lot, two more for the estates (one holding = two votes) | `NAM_mdr_count_holdings` in `NAM_board_recount` |
| Golden share ("Материковые акции") | 4 votes on the council's side while the chair's company stands for the council | `NAM_board_recount` |
| Leases | one vote per two leases (one per lease on the union); rent 8 capital a month, 12 on the shares course, none while the tenant boycotts on the union | `NAM_mdr_count_holdings`, `NAM_mdr_conquered_monthly` |
| Estates | two holdings (4 votes) for `NAM_mdr_estates_owner`, three (6 votes) on the union | `NAM_mdr_count_holdings` |
| District tenders | treaty emirates: event 210 (Kadir Loren / Reidbank, Sardan Ferrant / Smenkom, Rahma Navis / Arktur); districts made by the great war on the union course and countries that submit to the Directory: the queue `NAM_mdr_tender_queue` and event 212 (Mazar Ferrant / Smenkom, any other keeps its rotation owner); winner +8, loser -5 (`NAM_mdr_tender_set_owner`) | events 210, 212 |
| Charter dividend | x1.5 for EFL or AZH with its concession focus (`NAM_mdr_chartered_district`) | `NAM_corp_districts_monthly` |
| Directory campaigns | a fourth place from `first_mainland_meeting` | focus reward |
| Development programmes | a third run of each `NAM_dev_runs` programme after `directory_of_six` | the `NAM_dev_*` decisions |
| No-confidence immunity | 270 days with one of `NAM_board_original_stays_home` and `NAM_mdr_boards_constitution`, 360 with both, else 180 | `NAM_board_settle_no_confidence` |
| Names | MZR as a company district takes `MZR_NAM_corp_1`-`_6`; other tags keep their names | `NAM_corp_district_set_name`, `common/countries/cosmetic.txt` |

Ended by code at the victory: the cells, subversion against Eflor and Azhar,
the beachhead mission, the exile drills and the garrison charter.

### H.7 Conquered land and the home districts

- **Conquered land** is the array `NAM_conquered_states` (owned states with
  `NAM_conquered_state`, old cores kept, no NAM core). One bounded monthly pass,
  `NAM_mdr_conquered_monthly` from `NAM_corp_monthly`, ends leases on land lost
  or cored, pays the rent and removes the tree's state modifiers
  (`NAM_mdr_basin_levy`, `NAM_mdr_estate_guards`, `NAM_mdr_company_guards`)
  from such land behind `has_dynamic_modifier`; no world scan.
- **Nationalisation (D3)** cores a conquered state: owned and controlled by
  NAM, not leased and not in work, on the land the focus opened
  (`NAM_mdr_nationalisation_land`: Eflor's after `eflor_province`, Azhar's
  after `wells_nationalised`, the desert's after `national_war`, the South's
  after `NAM_hgm_southern_province` through `NAM_hgm_southern_province_land`),
  from the compliance of `NAM_mdr_nationalisation_compliance` (30 on the South).
  `NAM_mdr_nationalise_settle` takes a lot state out of its lot
  (`NAM_ptn_lot_state_cored`, appendix I).
- **Leases (D4)** give a conquered state to a company chosen in event 213
  (Eflor's land Ferrant / Arktur, Azhar's Loren / Reidbank), only under direct
  rule after the wing's concession focus: `NAM_mdr_lease_state` writes
  `NAM_mdr_lease_owner`, counts in `NAM_mdr_leases` and adds
  `NAM_mdr_company_guards`. One lease is prepared at a time. The desert has no
  lease row: the union's great war makes districts, never conquered land.
  `NAM_mdr_leasable` and D4's `target_trigger` exclude every state that carries
  `NAM_ptn_lot` (a lot of the South's partition, appendix I).
- **Compliance and resistance** rows loop the same array through
  `NAM_mdr_conquered_compliance` / `NAM_mdr_conquered_resistance` with a land
  filter (0 all, 1 Eflor's land, 2 Azhar's land).
- **Home districts** are the six homeland states 67, 688, 689, 690, 700 and
  719: restitution (D1, the society programme on the first three runs), purges
  after the trials (D2), the rebuilt harbour and Svetlogorsk.
  `home_districts` is read by the War for the South: no SLF rising
  (`ADISCORD_south_raise_oil_uprising` rows) and the description
  `ADISCORD_south.44.d_directory`.

### H.8 Shared script

Effects (NAM scope unless named; temps are reset by the effect):

| Effect | Inputs |
| --- | --- |
| `NAM_mdr_build` | `NAM_mdr_build_kind` (1 military factory, 2 civilian factory, 3 dockyard, 4 synthetic refinery, 5 fuel silo, 6 infrastructure, 7 supply node), `NAM_mdr_build_levels` (1 or 2), `NAM_mdr_build_state_1`..`_3` (preference order, 0 unused), `NAM_mdr_build_fallback` (capital paid only when no listed state qualifies); the site is `NAM_mdr_build_site` (NAM or a company district owns and controls it; coastal for dockyards; infrastructure room; supply nodes once per state on 240, 700, 729, 692 or 689); shared-slot kinds bring their own slots; called inside the reward's `hidden_effect` |
| `NAM_mdr_build_line` | `NAM_mdr_build_fallback`; bunkers 2 on 16722, 16743, 6193, 2804 |
| `NAM_mdr_place_division` | `NAM_mdr_unit_kind` (1 "Directory Field Division" 7650 men, 2 "Company Guard Regiment" 4900, 3 "Desert Armoured Column" 4150, 4 "Line Infantry Brigade" 6300, 5 "Island Marines" 4300, 6 "Old Settlers Militia" 4000), `NAM_mdr_unit_count`, `NAM_mdr_unit_state` (0 the harbour), `NAM_mdr_unit_company` (kind 2 colours), `NAM_mdr_unit_district` (kind 4: 1 Eflor, 2 Azhar); the unit forms in the state while NAM controls it, else at 16716, else at the capital; without the template it pays the template's men. The first template of kinds 1-3 grants its support technology (`ADISCORD_tech_desert_water_columns`, `ADISCORD_tech_garrison_police_sections`; the column also `ADISCORD_tech_restored_armored_chassis` and `ADISCORD_tech_armored_carrier_program`); every caller that can still grant one shows it as native output (`effect_tooltip = { set_technology = { ... popup = no } }` behind `NOT = { has_template }` and `NOT = { has_tech }`) |
| `NAM_mdr_launch_ships` | `NAM_mdr_ship_cruiser` (1 `ADISCORD_cruiser_2155`, 2 `ADISCORD_cruiser_2163`), `NAM_mdr_ship_escorts` (0-3); launched while NAM owns and controls 700, else five `convoy_1` a hull |
| `NAM_mdr_conquered_compliance`, `NAM_mdr_conquered_resistance` | `NAM_mdr_compliance_add` / `NAM_mdr_resistance_add` (5 or 10), `NAM_mdr_core_filter` (0, 1, 2) |
| `NAM_mdr_absorb_district`, `NAM_mdr_charter_district` | scope EFL or AZH as NAM's district; no temp |
| `NAM_mdr_lease_state` / `NAM_mdr_lease_end` | state scope; `NAM_mdr_lease_company` (1-6) for the lease |
| `NAM_mdr_grant_estates` | `NAM_mdr_estates_to_rank_1` (1 sells to the first company by votes, event 201 c) |
| `NAM_mdr_tender_set_owner` | district scope; `NAM_mdr_tender_winner`, `NAM_mdr_tender_loser` |
| `NAM_mdr_desert_refund` | `NAM_mdr_offer_index` (1 KDR, 2 SDR, 3 RHM) |
| `NAM_mdr_state_work_open` / `_refund` and the three settles | state scope; `NAM_mdr_work_kind` (1 restitution, 2 nationalisation, 3 rail), `NAM_mdr_work_cap`, `NAM_mdr_work_men` |
| `NAM_mdr_enact_<law>` (13), `NAM_mdr_end_martial_rule`, `NAM_mdr_restore_regular_courts`, `NAM_board_trade_war_for_economic` | none |
| `NAM_board_trust_package`, `NAM_board_holders_package`, `NAM_board_support_change`, `NAM_consolidation_add`, `NAM_corp_capital_add` | as in the corporate tree; one package per reward or answer |

Every convoy row is `add_equipment_to_stockpile = { type = convoy_1 ... }`
(`convoy` is the archetype). Triggers: `NAM_mdr_tree_live`,
`NAM_mdr_unitary`, `NAM_mdr_union`, `NAM_mdr_desert_closed`,
`NAM_mdr_south_open`, `NAM_mdr_south_ready`, `NAM_mdr_desert_treaty_room`,
`NAM_mdr_desert_no_offer_pending`, `NAM_mdr_desert_offer_live`,
`NAM_mdr_mazar_settled`,
`NAM_mdr_owned_by_directory`, `NAM_mdr_build_site`,
`NAM_mdr_unit_template_ready`, `NAM_mdr_filtered_conquered_state`,
`NAM_mdr_chartered_district`, `NAM_mdr_nationalisation_land`,
`NAM_mdr_absorbed_land`, `NAM_mdr_nationalisable`,
`NAM_mdr_nationalisation_compliance`, `NAM_mdr_leasable`,
`NAM_mdr_restitution_site`, `NAM_mdr_purge_site`, `NAM_mdr_rail_site`,
`NAM_mdr_shl_penalised` (SHL scope: at most one of the tree's penalties at a
time), `NAM_mdr_tender_next_wells`, `NAM_mdr_tender_next_smelters`,
`NAM_mdr_tender_next_yards`.

### H.9 The southern lanes and the hand-over into the War for the South

- **Side.** The Directory is the northern champion and the north leader: after
  the return it is the only sovereign northern power, and its districts and
  emirates fight as its subjects.
- **Contact.** After the desert the Directory borders Mazar and Veyr, never
  Shahrabad, so the preparation (`ADISCORD_south_begin_preparation`, retried by
  the SHL cycle) starts only when the camps touch: Mazar joins the north camp
  (the alliance or the protectorate accepted, or the refusal war of the
  submission), or SHL's own course takes Mazar or Veyr. The Mazar pair is
  `available` only with `NAM_mdr_south_open`, so no faction is made while the
  desert is open. A country that submits to the Directory becomes a company
  district (`ADISCORD_south_finalize_submission`: a first corporate row
  `PREV = { NAM_wor_federal_district_join = yes }`).
- **Readiness.** `ADISCORD_south_nam_focus_ready` has the Directory branch:
  `southern_districts`, one course capstone (`southern_charter` or
  `national_war`) and any two of `army_of_the_south`,
  `arsenal_of_the_directory`, `rear_of_the_south`, `northern_charter` (the same
  rows as `NAM_mdr_south_ready`). The chancery opens the coalition decisions
  (`ADISCORD_south_north_invitation_unlocked`: `southern_chancery` for any
  target, plus `fenn_guarantee` for WEF).
- **The war order.** "Час юга" (3 points, 21 days): `available` is
  `ADISCORD_south_final_focus_available`, no war, not a subject; the hidden
  `ADISCORD_south_prepare_offensive` declares at once when the warning is older
  than 55 days, otherwise the order waits for the SHL cycle; political power,
  war support, `NAM_mdr_hour_spirit` for 120 days, trust to all six, event 190.
  If Shahrabad strikes first the focus is bypassed. D22 "Новый приказ на юг"
  gives the next order after a repel.
- **The swap.** `ADISCORD_south_load_war_tree` records
  `ADISCORD_south_prior_tree = 7` for `NAM_mainland_directory_focus` and loads
  `NAM_south_war_focus`; `ADISCORD_south_restore_prior_tree` loads this tree
  back for value 7 before its `else` (which still sends unknown values to the
  corporate tree). In the war the Directory plays the no-course branch
  `NAM_sw_n_*` of `NAM_south_war_focus`.
- **What the tree hands over.** Formations from focuses and decisions, eight
  to ten locked laws, the districts and emirates as subjects, Mazar (faction
  member or district), Fenn (invitation open), and values the war reads:
  the course (path spirit `ADISCORD_south_path_NAM_boards` "Поход правлений"
  or `ADISCORD_south_path_NAM_shares` "Народная война акционеров", added in
  the `NAM_corp_takeover` branch of `ADISCORD_south_add_path_spirit` and
  removed by `ADISCORD_south_remove_path_spirit`), `home_districts` (no SLF
  rising), `northern_charter` (one point off the strain base in
  `ADISCORD_south_strain_cycle_member`, as `NAM_sw_district_compact_at_war`).
- **Outcomes.** North victory: `ADISCORD_south_final_resolve_north_victory`
  sets subject type 7 on `NAM_corp_takeover` on both courses (terms stay 2:
  every loser is puppeted, then sequestered); superevent 50 follows, and
  `NAM_hgm_begin` loads `NAM_southern_dominion_focus` in place of the
  republic's heritage tree before `ADISCORD_south_close_campaign_state`, so the
  prior-tree restore finds no war tree and only clears value 7. The heritage
  tree's weight in `focus_trees/NAM/postwar/southern_settlement.txt` carries
  `NOT = { has_country_flag = NAM_corp_takeover }`, and this tree's weight
  carries `NOT = { has_global_flag = ADISCORD_south_hegemon_NAM }`, so a
  re-selection keeps the dominion tree. On day 1 the settlement sequesters the
  losers and lays the table of the partition; the course of this tree decides
  what a country lot becomes (appendix I). The reward tooltips of
  `southern_charter` and `national_war` promise the allies' fate by course and
  say that the partition decides Shahrabad's. Shahrabad's
  victory: the code's terms by SHL course; an annexation runs `nam:on_annex`
  (`NAM_board_end_operations` with `NAM_hgm_close` and `NAM_mdr_close`, then
  `NAM_board_repeal_laws`); a puppet Directory keeps this tree with the
  council paralysed (`NAM_board_operable` false). Repel or external close: this
  tree returns (value 7) and D22 gives the next order.
- **Calendar.** The South deadline is a day number set at the first
  preparation start (540 days later, 15 days less per pull of
  `global.ADISCORD_south_crisis_pull`, never under 180); the warning needs 180
  days of preparation, both champions ready and the early window (180 days
  before the deadline), so the hour comes about 360 days after contact (270
  with six pulls) whatever the Directory's readiness. Planned estimates: war
  about 2.2-2.6 years after the victory of the return on the AI routes, about
  three years in the worst combinations; the AI plans start the desert war long
  before the lapse. These are estimates from the code's rules, not results of
  a run.

### H.10 Events, decisions and lifecycle

Events (section "Council of boards: the continent" of
`events/ADISCORD_nam_resource_war_events.txt`). Story events follow C.5:
`is_triggered_only`, `fire_only_once`, trigger `NAM_board_opened` with
`NAM_board_ended = 0`, the first answer is the timeout answer and never a pure
gain, three answers, the chair named through `[NAMBoardChairLeader]`; AI a 60,
b and c 20, except 186 c, 194 c and 204 a at 60:

| Event | Source | Title |
| --- | --- | --- |
| 181-190 | centre: `flag_over_harbour`, `union_of_boards`, `mainland_shares`, `first_mainland_meeting`, `desert_march`, `desert_concessions`, `southern_districts`, `southern_charter`, `national_war`, `hour_of_the_south` | "Флаг над гаванью", "Шесть уставов", "Золотая акция", "Собрание в бирже", "Голосование о походе", "Два договора и пример", "Печать на пустыне" (`.d_lapsed` after the lapse), "Раздел юга на бумаге", "Речь на площади", "Последнее заседание" |
| 191-196 | wings: `loren_governors`, `eflor_province`, `eflor_concession`, `basin_wells`, `wells_nationalised`, `basin_oil_concession` | "Канцелярия Дехтунга", "Губернский устав", "Договор с держателем", "Первый танкер", "Скважины без хозяина", "Аренда на полвека" |
| 197-202 | home and council: `back_to_homes`, `collaborator_trials`, `act_of_oblivion`, `division_of_continent`, `escheated_estates`, `heirs_treaty` | "Чужие ключи", "Скамья в рыночном зале", "Костёр на причале", "Торговый зал", "Ключи от поместий", "Подписи наследников" |
| 203-208 | southern lanes: `general_staff`, `field_armies`, `war_charter`, `damir_road`, `southern_chancery`, `northern_charter` | "Карты Лорена", "Первый штаб армии", "Квоты", "Караванщики", "Досье на печи", "Подписи хартии" |
| 209 | to KDR, SDR or RHM from event 214 | "Договор о концессии": sign, refuse, or the fallback c (H.4) |
| 210 | NAM from 209 a | "Торги за эмират": the emirate's tender pair |
| 211 | NAM from 209 b | "Договор вернулся без подписи": notice with the refund line |
| 212 | NAM from the tender queue | "Округ на торгах" |
| 213 | NAM from D4 | "Арендатор для новой земли" |
| 214 | NAM, hidden, from D13 | dispatcher of the treaty offers |
| 215 | NAM from D18 | "Материковый лот": the open lot's rival pair, or c "Оставить в казне" |
| 216 | NAM from the lapse | "Срок пустынного вопроса": the price of the failure path |
| 217-220 | 90-120 days after `eflor_province`, `eflor_concession`, `wells_nationalised`, `basin_oil_concession`; dropped when the land or the concession is gone | "Подполье Дехтунга", "Забастовка плавилен", "Огонь на промыслах", "Стачка семей" |
| 221, 222 | `collaborators_lists`, `basin_families` | "Чьи имена в списке", "Доля семей" |

Event 200's answers set the order of the mainland tenders besides their
trust: a "По жребию" draws `NAM_mdr_lot_order` (1, 2 or 3 with equal weights:
the order is drawn, never the winner), b "Сначала скважины" sets 1, c
"Сначала верфи" sets 3; event 215 and D18 follow the cycle from that lot
(H.6), and D18 names the next lot in its launch key. Event 213 offers only
the two tenants of Eflor's or Azhar's land.

Decisions. Every paid decision follows the custom-cost contract and refunds
only through its receipt (a state flag with its paid variables, or a NAM
variable of that decision), cleared in the same block; `cancel_trigger`
includes `NAM_board_operable = no`. Prices are the values of the script:

| # | Decision | Category | Opened by | Price | Run | Result |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | `NAM_mdr_restitution` "Реституция округа" | `NAM_consolidation` | `back_to_homes` | 40 capital (25 after `act_of_oblivion`) | 60 days, two at once | men, stability, Smenkom's trust; society programme on the first three runs; `NAM_mdr_restituted` |
| D2 | `NAM_mdr_purge_district` "Чистка округа" | `NAM_consolidation` | `collaborator_trials` | 20 PP | 30 days | capital, consolidation, Reidbank's trust; `NAM_mdr_purged` |
| D3 | `NAM_mdr_nationalise_land` "Национализация земли" | `NAM_consolidation` | the integration sides, `national_war` (with its unlock line), and after the South war `NAM_hgm_southern_province` | 50 PP, 80 capital | 90 days, two at once | NAM core, consolidation; the state modifiers removed; a lot state leaves its lot |
| D4 | `NAM_mdr_lease_land` "Аренда земли" | `NAM_consolidation` | the extraction sides under direct rule | 25 PP | 30 days, one at a time | event 213 |
| D6 | `NAM_mdr_rail_brigades` "Путевые бригады" | `NAM_consolidation` | `southern_railway`, or `road_contracts` | 50 capital and 3000 men (40 capital after `road_contracts`) | 60 days, two at once | infrastructure on 240, 68, 70, 692, 724, 725, 726, 729, once each |
| D13 | `NAM_mdr_desert_offer` "Договор о концессии" | `NAM_consolidation` | `desert_concessions` | 50 PP, 60 capital escrow | instant | H.4 |
| D14 | `NAM_mdr_desert_last_argument` "Последний довод" | `NAM_consolidation` | `desert_concessions` | 50 PP | instant | the great war on every emirate left |
| D18 | `NAM_mdr_mainland_tender` "Материковые торги" | `NAM_free_zones` | `division_of_continent` | 25 PP | 30 days | event 215 for the open lot |
| D5 | `NAM_mdr_hire_district_regiments` "Полки округа" | `NAM_mdr_army` | the extraction sides under the holders | 30 capital, 6300 men | 45 days, three per district | a line brigade named after the district |
| D7 | `NAM_mdr_raise_company_regiment` "Полк правления" | `NAM_mdr_army` | `company_regiments` | 40 capital, 4900 men (3700 under `NAM_mdr_law_company_levy`), 4410 rifles | 45 days | a company regiment in the selected company's colours; one per company |
| D8 | `NAM_mdr_shareholder_battalions` "Батальоны реестра" | `NAM_mdr_army` | `shareholders_levy` | 30 PP, 7650 men, 6885 rifles | 60 days, cap 4 | a field division |
| D9 | `NAM_mdr_karamyshev_veterans` "Ветераны побережья" | `NAM_mdr_army` | `heirs_treaty` | 25 PP, 4000 men, 3600 rifles | 45 days, cap 2 | a militia division "Ветераны побережья" |
| D10 | `NAM_mdr_staff_exercises` "Штабные игры" | `NAM_mdr_army` | `southern_staff` | 50 PP | 60 days, re-enable 120 | army experience, `NAM_mdr_exercises_spirit` |
| D11 | `NAM_mdr_south_war_shares` "Акции южного похода" | `NAM_mdr_army` | `southern_charter` | 40 capital | 30 days, three runs | rifles, convoys, Reidbank's trust |
| D12 | `NAM_mdr_shareholder_mobilisation` "Мобилизация реестра" | `NAM_mdr_army` | `national_war` | 75 PP | instant, re-enable 240 | `NAM_mdr_shareholder_mobilisation_spirit` |
| D19 | `NAM_mdr_armoured_columns` "Бронеколонны пустыни" | `NAM_mdr_army` | `armoured_fist` | 40 capital, 25 PP, 4150 men, 400 motorized | 60 days, cap 3 | an armoured column |
| D20 | `NAM_mdr_training_camps` "Учебные лагеря" | `NAM_mdr_army` | `marines_to_line` | 30 PP | 60 days, re-enable 120 | army experience, `NAM_mdr_training_spirit` |
| D21 | `NAM_mdr_fuel_convoys` "Топливный эшелон" | `NAM_mdr_army` | `fuel_trains` | 30 capital | 30 days, cap 4 | fuel |
| D15 | `NAM_mdr_op_furnace_contracts` "Скупка печных подрядов" | `NAM_mdr_south_office` | `furnace_agents` | 25 PP, 60 capital | 60 days, re-enable 180 | `NAM_mdr_op_furnace_contracts_idea` on SHL, or exposure (`NAM_mdr_exposed_plot`) |
| D16 | `NAM_mdr_op_zarkhan_agents` "Агенты в Зархане" | `NAM_mdr_south_office` | `furnace_agents` | 30 PP, 40 capital | 90 days, re-enable 180 | `NAM_mdr_op_zarkhan_idea`, or exposure |
| D17 | `NAM_mdr_op_shortage_rumours` "Слухи о дефиците" | `NAM_mdr_south_office` | `furnace_agents` | 20 PP, 30 capital | 45 days, re-enable 120 | `NAM_mdr_op_rumours_idea`, or exposure |
| D22 | `NAM_mdr_new_south_order` "Новый приказ на юг" | `NAM_mdr_south_office` | `hour_of_the_south` | 50 PP | instant, re-enable 180 | `ADISCORD_south_prepare_offensive` |
| D23 | `NAM_mdr_mazar_retry` "Снова к Мазару" | `NAM_mdr_south_office` | `mazar_alliance` | 50 PP | instant | a new alliance offer, `NAM_mdr_mazar_offer_cooldown` 90 days |

The operations D15-D17 run one at a time (one receipt
`NAM_mdr_south_op_paid`) and need `SHL = { NAM_mdr_shl_penalised = no }`.
D15-D17, D22 and D23 are hidden once `ADISCORD_south_final_resolved` is set,
so none of them reappears against a sequestered Shahrabad after the war. The
army orders have their own category `NAM_mdr_army` "Армия континента"
(visible on the corporate route after `NAM_mdr_started` until
`NAM_board_ended`), because the republic's `NAM_mobilisation` stays closed on
the corporate route. `NAM_mdr_south_office` "Южная канцелярия" is visible from
`southern_chancery` (or `hour_of_the_south`) until `NAM_board_ended`.

**Lifecycle.** `NAM_mdr_begin` is the single entry and `NAM_mdr_close` the
single exit, called by `NAM_board_end_operations` after `NAM_hgm_close`
(appendix I) and before `NAM_dir_campaigns_close`. `NAM_mdr_close` refunds every running state work on
the home, rail and conquered states, ends every lease, removes the state
modifiers, refunds the NAM receipts of D5, D7-D9, D11, D15-D17, D19, D21 and
every open desert escrow (political power is never refunded), removes the NAM
spirits of the tree behind `has_idea`, clears `NAM_mdr_tender_queue`,
`NAM_mdr_council_seat_promised`, `NAM_mdr_mazar_offer_cooldown` and the estates
owner, and marks the economy dirty. It touches no law. Kept for the campaign:
`NAM_mdr_started`, `NAM_board_return_chair`, the global flag
`NAM_mdr_desert_lapsed`, the state flags `NAM_mdr_restituted`,
`NAM_mdr_purged`, `NAM_mdr_nationalised`, `NAM_mdr_rail_done`, the caps of the
decisions, the mainland lot variables. `NAM_mdr_council_seat_promised` (event
186 c) is cleared by `southern_districts`. The SHL spirits expire on SHL; no
effect removes them from another country. Prior-tree value 7 lives from the
swap to the restore.

### H.11 AI

`NAM_mainland_directory_plan_holders` (enable `NAM_rtw_direct_rule = no`) and
`NAM_mainland_directory_plan_direct` (`= yes`), each 50 focuses and 105
points: the union course, the desert march, the act of oblivion, the heirs'
treaty, the Mazar alliance, the infantry corps, the tanker armada and the road
contracts; the holders take both extraction sides, direct rule takes Eflor's
integration and Azhar's extraction. `NAM_mdr_ai_desert` (in
`common/ai_strategy/ADISCORD_nam_resource_war_ai.txt`) asks for front units
against KDR, SDR and RHM while the great war is active. `desert_concessions`
has `ai_will_do = 0`.

### H.12 Tests

`NamMainlandDirectoryTreeTests` in `tools/tests/test_adiscord_nam_focus.py`:
selection and owner, shared history, the load at the return's victory, the
South swap with value 7, the layout and mirror, rewards, wings that are not
clones, the tooltip layout standard, laws, trades, the custom-cost contract,
formations and fallbacks, receipts refunded once, the lifecycle, and the
events; `NamSouthernDominionTreeTests.test_mainland_leftovers_are_closed` pins
the lease rows, the removed receipt rows, the lot order of events 200 and 215,
the D3 unlock of `national_war`, the technology lines of the template callers
and the reworded Shahrabad lines of `southern_charter` and `national_war`.
`tools/tests/test_adiscord_south_final_war.py`:
`test_directory_mazar_uses_the_shared_queue`,
`test_directory_path_spirit_and_terms`,
`test_north_victory_partitions_for_the_council`,
`test_directory_readiness_invitations_and_rising`,
`test_directory_stages_on_the_mainland_road` and the lapse phase of
`test_exile_return_and_great_war_block_every_clock_and_first_strike`.

### H.13 Open items and what only a run of the game can prove

Not built yet: a Directory course in `NAM_south_war_focus` (today the
no-course `NAM_sw_n_*` branch) and dedicated `GFX_focus_NAM_mdr_*` artwork.
The Directory's tree after a won War for the South is appendix I.

Runtime checks, all by the user after a full restart: the load one step after
the victory's settlement in both forms of rule and `keep_completed` with three
shared-history trees; `annex_country` with `transfer_troops` on a district
and the coring of its capital; `remove_ideas` of the garrison charter and the
locked mobilisation laws; the treaty chain 214 -> 209 -> 210 / 211 with a
human and an AI emirate, and its timeout; the great war with one or two
treaty districts beside the Directory; the lapse on day 540 and the South
clock after it; the tender queue of event 212 with several districts;
`create_unit` of the new templates and their fallbacks; `create_ship` of both
cruisers at 700; the bunker provinces of `NAM_mdr_build_line`; the swap to
`NAM_south_war_focus` and back with value 7; the north victory's load of the
dominion tree on both courses (appendix I); the war dates in recent text saves.

## Appendix I. The partition of the South and "Владычество правлений"

Maintained contract of what follows a council of boards that wins the War for
the South: the partition of the South among the six companies (script prefix
`NAM_ptn_`) and the tree `NAM_southern_dominion_focus` "Владычество правлений"
(prefix `NAM_hgm_`), loaded in place of the republic's heritage tree. The
script holds the values: source `focus_trees/NAM/southern_dominion/focuses.txt`
(generated output `common/national_focus/ADISCORD_NAM_southern_dominion.txt`,
owner `tools/builders/build_adiscord_focus_trees.py`), the sections "Council of
boards: the South after the war" of
`common/scripted_effects/ADISCORD_nam_resource_war_effects.txt` and of the NAM
triggers, the category `NAM_hgm_dominion` with its decisions, the laws and
spirits in `common/ideas/ADISCORD_nam_resource_war_ideas.txt`, events
`ADISCORD_nam_story.230`-`287` (288-289 reserved in
`tools/data/adiscord_event_ids.json`), superevent request 79, the AI plans
`NAM_southern_dominion_plan_union` and `NAM_southern_dominion_plan_shares`, and
the tests of I.17. Nothing here was checked in the running game.

**Author's orders (binding, his words):**

- "Cделай уникальный раздел после войны за юг за корпоратов". On this route
  "раздел" carries two meanings and both are delivered: a unique partition of
  the South by the six companies when the Directory wins, in the line of
  "Одна ночь на раздел мира" (I.2-I.8), and a unique section of content after
  that war: the Directory's own tree with the route's finals instead of the
  republic's heritage tree (I.9-I.16).
- "Ветка должна быть такая же симметричная" (mirror around the centre column,
  a free cell between neighbours, no straight chain longer than two); "по
  горизонтали можно расширить"; "пусть не всё обязательно выполнять будет".
- Rewards "как в the fire rises": several felt rewards of different kinds per
  focus, important focuses fire story events with three answers; "баффни
  фокусы. 300 людей условные - ни о чём"; "Пусть даёт не только эти награды
  просто! Также пусть дают законы разные, которые сменить нельзя. А ещё
  понижает уровень соц. развития, но повышает другое".
- Standing decisions hold: the player is the council of six companies, not a
  chairman; the chair changes only by a no-confidence vote or the annual
  meeting; tenders are the player's choice; "99 на 1" is 99 percent poor and 1
  percent rich; the state is "Светлогорская директория"; no mechanics in
  descriptions; wars, alliances and peace only through scripted focuses,
  decisions and events.

**Working decisions of the lead, not the author's.** The author gave no size
and did not answer the open questions put to him with recommended answers;
until he answers, these stand and the rows that cite them follow:

| # | Working decision |
| --- | --- |
| W1 | 49 focuses; a normal playthrough takes about a year of focus time (the AI plans: 23 focuses, 52 points, 364 days); one whole route is 34 focuses, 76 points, 532 days from the root |
| W2 | all four finals: "Вечный совет шести", "Одно правление", "Лига округов", "Акции девяноста девяти" |
| W3 | Shahrabad's fate is the player's choice between "Печной трест" and "Хазар по описи"; no release tag |
| W4 | the game goes on after a final: council, districts, leases, the Cold Fire and the Khan's crisis keep running |
| W5 | the partition's superevent uses the existing unused picture; the finals fire their closing events without superevents until pictures exist |
| W6 | no new country names or flags: the finals rename the ruling party; South districts other than Mazar keep their own names |
| W7 | "Одно правление" is the holding model, never a life chairman |
| W8 | "Акции девяноста девяти" succeeds the law "99 на 1" |
| W9 | an unsigned protocol is settled at the deadline: Shahrabad's form by course, every open lot kept by the council, no bids, no grudges, no walk-outs |
| W10 | when Mazar is the Directory's sovereign ally, the Zarkhan lot may give 707 to Mazar |

### I.1 Identity and size

| Item | Value |
| --- | --- |
| Tree | `NAM_southern_dominion_focus`, prefix `NAM_hgm_`, shared history (`SHARED_HISTORY_SOURCES`), `default = no`, continuous focus position x 50, y 1800 |
| Weight | `factor = 0`; +160 for `original_tag = NAM` with `NAM_corp_takeover`, `ADISCORD_south_hegemon_NAM` and `ADISCORD_south_final_resolved`; the heritage tree's weight carries `NOT = { has_country_flag = NAM_corp_takeover }` and the mainland tree's `NOT = { has_global_flag = ADISCORD_south_hegemon_NAM }`, so a re-selection keeps this tree |
| Focuses | 49 on rows 0-10 and columns 0-44, 114 points; seven exclusive pairs and four finals of which one can be taken |
| Icons | every focus binds an existing corporate, wartime or mainland sprite (`GFX_focus_NAM_board_*` and others); no `GFX_focus_NAM_hgm_*` sprite exists yet |
| AI plans | two plans of 24 entries (23 focuses taken, 52 points; the last entry is the fallback final), chosen by the mainland course (I.16) |
| Debug | `ADISCORD_nam_debug_tree_southern_dominion` in `common/decisions/ADISCORD_scenario_debug_decisions.txt` |

### I.2 Settlement order and loading

1. `ADISCORD_south_final_resolve_north_victory`: after the republic's subject
   types, `NAM_corp_takeover` sets `global.ADISCORD_south_subject_type = 7` on
   both courses (terms stay 2). Then `ADISCORD_south_end_final_wars`,
   `ADISCORD_south_mark_losers` (each loser freed by its overlord, its faction
   dismantled or left), superevent 50, and in the NAM block the heritage load
   for the republic or `NAM_hgm_begin` for the council, both before
   `ADISCORD_south_close_campaign_state`: the prior-tree restore then finds no
   war tree and only clears `ADISCORD_south_prior_tree`. `ADISCORD_south.30`
   follows in a day and the news `ADISCORD_south.31` in two hours (desc
   `ADISCORD_south.31.d_nam_partition` on type 7; its option shows
   `NAM_hgm_dominion_unlocked_tt` behind this tree).
2. `NAM_hgm_begin` (NAM; `tag = NAM`, `NAM_corp_takeover`, the hegemon flag, no
   `NAM_hgm_started`): sets `NAM_hgm_started`, sizes the lot arrays (12) and
   the company arrays (7), loads the tree with `keep_completed = yes`, marks
   the layout and the economy dirty.
3. Day 1, `ADISCORD_south_apply_settlement`: each loser of the roster is
   settled once; `ADISCORD_south_apply_subject_type` row 7 calls
   `NAM_ptn_sequester` (puppet if needed, `autonomy_NAM_namestnik_office` at
   freedom 0.05, flag `NAM_ptn_sequestered`, control of its owned states
   restored to it, listed in `NAM_ptn_sequestered_tags`). The seal call
   `SHL = { SHL_seal_open_chapter = yes }` is skipped for a sequestered
   Shahrabad (the furnace trust opens it). After the SLF annexation and the
   terms-3 block, type 7 calls `NAM_ptn_open_table` with NAM as scope and
   ROOT, before `ADISCORD_south_clear_participants`.
4. The root's `available` is `NAM_hgm_tree_live` (`NAM_ptn_table_open`, not a
   subject), so nothing is taken before the table exists.

The tree keeps the completions of the corporate, wartime and mainland trees,
every locked law until a focus of this tree succeeds it, the timed spirits to
expiry, trust, votes, the chair, the chancery, districts and their owners,
mainland leases and lots, island concessions and consolidation. The course
is read, never copied: `NAM_ptn_union_rules` is
`NOT = { has_completed_focus = NAM_mdr_mainland_shares }`, so "Союз правлений"
and a South war begun before the mainland pair follow the same rules. The
chancery's D15-D17, D22 and D23 hide after `ADISCORD_south_final_resolved`.
The council's annual meeting and no-confidence vote continue through every
final.

Other outcomes of the War for the South are unchanged: a repel or an external
close restores the mainland tree (value 7); Shahrabad's victory ends the
route as coded (an annexation runs `NAM_board_end_operations`, which calls
`NAM_hgm_close`); a non-corporate NAM loads the heritage tree.

### I.3 The table

A lot is a set of states and a pair of bidding companies. `NAM_ptn_open_table`
opens lots 5-11 for each sequestered country of the roster and lots 1-4 when
Shahrabad is sequestered (otherwise it writes `NAM_ptn_shl_form = 2` at once).
A state with the core of a lot's country that no longer exists opens that lot
as a state lot. The deadline is set 179 days after the table.

| Lot | Name | States | Bidders (answer b / c) | Base bid |
| --- | --- | --- | --- | --- |
| 1 | "Зарханский пояс" | 707, 289, 731, 294 (furnaces 289, 294) | Ferrant / Arktur | 120 |
| 2 | "Сафирское взморье" | 288, 730 (the South's port; furnace 288) | Navis / Loren | 80 |
| 3 | "Хазар" | 699, 287, 290, 291 (furnaces 287, 290, 291) | Smenkom / Reidbank | 140 |
| 4 | "Байратские копи" | 732, 292, 293, 296, 733, 295 (furnaces 292, 293, 295) | Arktur / Smenkom | 100 |
| 5 | "Кейзан" | KYZ | Loren / Reidbank | 90 |
| 6 | "Вейр" | GLP | Navis / Arktur | 80 |
| 7 | "Мазар" | MZR | Ferrant / Smenkom | 110 |
| 8 | "Фенн" | WEF (states 174, 175, Eflor's cores) | the holder of Eflor's share `NAM_board_partition_efl` (Loren when unset) / Reidbank; when the first is Reidbank, the holder of Azhar's share `NAM_board_partition_azh`, or Smenkom when that is unset or Reidbank too | 40 |
| 9 | "Кадир" | KDR | Loren / Reidbank | 50 |
| 10 | "Сардан" | SDR | Ferrant / Smenkom | 50 |
| 11 | "Рахма" | RHM | Navis / Arktur | 50 |

Lots 9-11 appear only when the emirate fought for Shahrabad (the desert
lapsed on the mainland). Not on the table: the Directory's allies and
districts, countries that stayed out of the war, the SLF (annexed on day 1;
its core on 688 is removed), the furnace administrations as tags. The land
of every sequestered country is collected once into a temporary array and
sorted by `NAM_ptn_sort_state`:

- Shahrabad's sixteen states belong to lots 1-4 by the map; other land to the
  lot of its core (`NAM_ptn_state_lot_index`); such a state joins its lot
  (state variable `NAM_ptn_lot`, array `NAM_ptn_states`) and, for a country
  lot, moves to that country;
- a NAM core goes to NAM (`NAM_wor_take_state`: homeland);
- a core of a friendly country (NAM's subject or faction member, not
  sequestered: EFL, AZH, MZR, WEF, KYZ, GLP) goes to that country;
- land of a sequestered country lot without another lot's core stays in its
  lot;
- the rest becomes council land (`transfer_state`, `NAM_wor_take_state`).

A furnace administration (SFD, SCD, SMD, SOD, SDA) without lot land is
annexed at once; one with lot land at its last lot's award or at the deadline.

### I.4 The sequence

| Step | When | What happens |
| --- | --- | --- |
| Victory | day 0 | wars end, losers freed, superevent 50, `NAM_hgm_begin` |
| Sequestration | day 1 | every loser sequestered, the table laid, `NAM_ptn_table_open`, the deadline |
| "Юг под секвестром" | the root | opens the category `NAM_hgm_dominion` "Раздел и владычество" and the private tenders; event 230 |
| Shahrabad's fate | the centre pair | "Печной трест" or "Хазар по описи" writes `NAM_ptn_shl_form` once; the tenders of lots 1-4 wait for it |
| Private tenders | any time before the night | `NAM_ptn_tender_<n>` (25 PP, 7 days), the lot's event in tender mode |
| "Ночь раздела юга" | after the pair (bypassed once the protocol is signed) | `NAM_ptn_run_night`: dispatcher event 246 gives the open lot with the lowest index and no running tender its event, one an hour; while only tenders remain it waits a day |
| Walk-outs | after the last lot | each company with two grudges or more gets event 244 |
| Protocol | dawn | `NAM_ptn_sign_protocol`: flag `NAM_ptn_protocol_signed`, spirit `NAM_hgm_partition_charter` "Протокол раздела юга" for 365 days, +4 trust to every company that took a lot, superevent request 79, event 245 two hours later |
| Deadline | the first monthly tick on or after the deadline day, while no night runs | `NAM_ptn_deadline_settle`: Shahrabad's form by course (`NAM_ptn_settle_shl_default`: the inventory on "Материковые акции", otherwise the trust), running tenders closed with their 25 PP returned, every open lot kept in mode 4, the remaining administrations annexed, notice 247, the protocol |

A night left without an answer for 30 days is resumed by the monthly check.
The South branch opens at the protocol ("Конторы на юге"). The levers are the
order and the moment: early tenders bring less money and no grudges, the
night more money and more anger, and each award moves the ranks that decide
the next chair and the finals.

### I.5 How a lot is awarded

Lot events 233-243 read the mode stored for the lot (1 tender, 2 night, 3
re-tender) and call `NAM_ptn_award`; every answer of the night calls the
dispatcher again. Answers:

| Answer | Effect |
| --- | --- |
| a "Оставить совету" (lot 2 under the inventory: "Вольный порт"; lot 1 under the inventory while Mazar is the Directory's sovereign ally: "Доля Мазара") | the lot is kept: both bidders -3 trust (-1 on "Материковые акции") |
| "Снять с торгов" (re-tender only) | the lot stays kept; no trust change |
| b, c "Продать <компания>" | the bidder pays its bid into `NAM_corp_capital`; winner +6 / loser -3 at tender and re-tender, +8 / -5 at night with one grudge `NAM_ptn_grievance^<loser>`; `NAM_ptn_lots_won^<winner>` +1, owner `NAM_ptn_lot_owner^<lot>`; recount queued |

- **Bid** (`NAM_ptn_compute_bid`): base bid x0.75 at tender, x1.25 at night,
  x1.0 at re-tender; x0.5 when the winner already took a lot; x0.75 for lots
  1-4 under the furnace trust; rounded. `NAM_ptn_prepare_bids` writes the shown
  values in the event's immediate block; the award recomputes them.
- **Veto of the five.** A company's third lot costs 40 PP (the answer's native
  row) and -3 trust to each of the four companies that neither win nor lose.
- **Once.** A lot is settled from state 1, or from state 3 in re-tender mode
  while `NAM_ptn_retendered^<lot>` is 0; states 2 and 4 are final, so a stale
  or repeated answer changes nothing.
- **Re-tender** (`NAM_ptn_retender` after "Южная биржа": 40 PP, 14 days,
  re-enable 60): the lowest kept lot that is not the free port, not Mazar's
  share, not yet re-tendered, and not under "Вечный совет шести".
- **Walk-out** (event 244 for `NAM_ptn_walkout_company`): "Отпустить" sets its
  trust to 20 and its objection deadline to today, so it boycotts from the next
  recount; "Отступные" 60 capital, trust +10, grudges cleared; "Грамота" 50 PP,
  a charter line and trust +6.
- **AI** (lot events): a 10, b and c 40, +30 for the bidder with fewer lots,
  +20 for the bidder with lower trust, 0 when the answer needs the veto and
  the other bidder's does not.

### I.6 What each lot becomes

"Union" means `NAM_ptn_union_rules` ("Союз правлений" or neither course);
"shares" means "Материковые акции". `NAM_ptn_apply_lot` moves the lot to
state 2 (awarded) or 3 (kept) with `NAM_ptn_kept_form` (1 rotation district, 2
council land, 3 furnaces to the treasury, 4 free port, 5 Mazar's share) and
`NAM_ptn_lot_kind` (1 Shahrabad, 2 country lot, 3 state lot, 4 Fenn merged
into Eflor).

| Lot kind | Course / form | Awarded | Kept |
| --- | --- | --- | --- |
| country lot | union | company district (`NAM_ptn_make_district`): owner set to the winner, flag `NAM_hgm_owner_fixed`, temp `NAM_mdr_skip_tender_queue = 1`, then `NAM_wor_federal_district_join`; the army stays | district with the rotation owner, not fixed |
| country lot | shares | `NAM_wor_radical_annex`: conquered land owned by the winner as a lot | conquered council land, owner 0; +10 compliance under direct rule |
| state lot | either | NAM takes the lot's states from their holder (`NAM_ptn_take_state_lot`), owned by the winner | council land; +10 compliance under direct rule |
| lots 1-4 | "Печной трест" | furnace lease: the land stays Shahrabad's, the winner holds the lot while a furnace of it stays leased by the seal | the furnaces pay only the treasury |
| lots 1-4 | "Хазар по описи" | land owned by the winner as a lot | council land; lot 2 becomes "Вольный порт" (state flag and dynamic modifier `NAM_ptn_free_port` on 288 and 730, +10 capital a month); lot 1 with Mazar as sovereign ally and outside the deadline: 707 to MZR (`NAM_ptn_give_mazar_share`, opinion `NAM_hgm_mazar_share`), the rest kept |
| lot 8 "Фенн", first bidder | Eflor is NAM's district | Fenn's states go to EFL (`NAM_ptn_fenn_to_eflor`), WEF ends with its last state, kind 4: the holding counts through Eflor's district | - |
| lot 8 otherwise | either | the country-lot row of the course | the country-lot row |

Every award marks the economy dirty on NAM and on the lot's country; no
faction call and no claim. A country lot (5-11) queues its people's event
(281-287) 60-120 days after it is settled; the event rechecks its lot and land.

A land lot loses a state that NAM no longer owns or has cored
(`NAM_ptn_lot_state_cored`, also called by the mainland nationalisation and by
"Хазарские лицеи"); a lot without states closes (state 4: no holding, no rent,
no re-tender); a district lot closes when its country stops being NAM's
district. The winner keeps what it paid.

### I.7 Shahrabad's two fates

- **"Печной трест"** (`NAM_ptn_furnace_trust`): form 1, Shahrabad stays NAM's
  subject in the namestnik office, its sequestration flag is cleared and its
  seal chapter opens once (`SHL_seal_open_chapter`: all nine furnaces leased,
  share 80%, buy-backs, the Cold Fire). Shahrabad keeps its tree and its
  courses; a buy-back takes a furnace out of a company's lot. Law "Печной сбор",
  a social level traded for the economy, event 231; leaf "Печные дивиденды"
  (`allow_branch` on form 1).
- **"Хазар по описи"** (`NAM_ptn_khazar_inventory`): form 2, Shahrabad is
  annexed through `NAM_wor_radical_annex` (army disbanded, conquered land, the
  furnace mechanic ends) and its states take +15 resistance. Law "Подушная
  опись", a social level traded for the state, 20 000 rifles, event 232; leaf
  "Хазарская аренда" (`allow_branch` on form 2).

Each side is bypassed only on its own form (written by the deadline or by a
table without Shahrabad), so at most one side is bypassed and the exclusion
closes the other. Shahrabad's raid odds and petition weights in the SHL files
still read only the republic's post-war focuses (I.18).

### I.8 Holdings and rents

- **Recount** (`NAM_ptn_count_holdings` inside `NAM_board_recount`): an awarded
  lot counted by its lot row (`NAM_ptn_lot_counts_as_holding`: not a district
  lot, not kind 4, a furnace lot only while one of its furnaces is leased) is
  one holding (two votes) on the union and half a holding on shares;
  "Южный холдинг" adds half a holding per lot of `NAM_hgm_southern_holder`. On
  shares the kept lots give the council `NAM_ptn_kept_votes` (2-3 kept lots 1
  vote, 4-5 kept lots 2), added in `NAM_board_update_industrial_policy`.
- **Rent** (`NAM_ptn_monthly` from `NAM_corp_monthly`, with
  `NAM_ptn_deadline_check` and `NAM_hgm_loans_monthly`): per awarded land lot 6
  capital a month on the union and 8 on shares, plus the cadastre bonus of its
  owner (`NAM_ptn_lot_bonus`, +3 per award of event 280) and +4 for a Shahrabad
  lot after "Хазарская аренда"; per awarded furnace lot 4 for each leased
  furnace after "Печные дивиденды"; the sum x1.5 after "Юг как промысел" and
  x0.9 after "Доля девяноста девяти", then +10 for the free port. Nothing is
  paid for a lot whose owner boycotts on the union. The last sum is kept in
  `NAM_ptn_last_rent`.
- **Districts bought at the partition** carry `NAM_hgm_owner_fixed`: the
  dispute of `NAM_corp_open_dispute` and the auction `NAM_corp_auction_district`
  skip them. "Хартия владычества" halves the monthly dispute roll.
- **Category text** `NAM_hgm_dominion_desc` is `[NAMPtnTable]`: every lot with
  its states, bidders, base bid, state and owner, and the deadline.

### I.9 The tree

Columns: the partitioned South x 0-8, the ninety-nine and a hegemon's deals x
10-14, the centre x 16-28, the army and the last empire x 30-34, the council
after the last enemy x 36-44. Mirror x -> 44 - x. Ids without `NAM_hgm_`:

```
row 0                                               [sequestration 22]
row 1  [offices 4]   [share99 10]x[order 14]                              [demob 30]x[garrison 34]   [nothing_left 40]
row 2                                         [trust 20]x[inventory 24]
row 3 [houses 2][watch 6] [shops 10][cities 12][towns 14]       [artels 30][army 32][co_garr 34] [heirs 38][seal 42]
row 4  [cadastre 4]                    [dividends 18][night 22][leases 26]                         [count 40]
row 5                     [ledger 12]                                        [envoys 32]
row 6 [extract 2]x[prov 6]               [dominion 20]  [exchange 24]                    [covenant 38]x[mergers 42]
row 7                  [cartel 10]x[lanes 14]                          [arms 30]x[last_empire 34]
row 8 [quotas 0][boards 4][lyceums 8]          [last_meeting 22]                  [fund 36][charter 40][holding 44]
row 9                        [bank 12]                                      [price 32]
row 10                              [league 16][people 20]  [six 24][one_board 28]
```

Every cell has its mirror with mirrored prerequisite groups, partner and
cost; same-row cards are at least two columns apart; the longest
single-prerequisite chain is two links; every pair stands on one row with no
card between its cells. The four finals exclude each other through
`NAM_hgm_no_final_taken` in `available`, not `mutually_exclusive`, because an
exclusion line between x 16 and x 28 would cross the two finals between them.
Mirror of cells, not of content.

| Branch | Focuses | Pair (row) | Side A | Side B | Rejoin |
| --- | --- | --- | --- | --- | --- |
| Centre: the partition | 9 + 4 finals | `furnace_trust` "Печной трест" / `khazar_inventory` "Хазар по описи" (2) | I.7; leaf `furnace_dividends` "Печные дивиденды" (D2, a 150 advance) | I.7; leaf `khazar_leases` "Хазарская аренда" (+10 compliance, a 150 advance) | `night_of_the_south` "Ночь раздела юга", then `charter_of_dominion` "Хартия владычества" or `southern_exchange` "Южная биржа" (D1 re-tender, two civilian factories), then `last_meeting` "Последнее собрание" |
| Partitioned South | 9 | `southern_extraction` "Юг как промысел" / `southern_province` "Юг как провинция" (6) | law "Устав промысла", rent x1.5, a 150 advance, a social level traded for the army, D5 quotas; leaf `steel_quotas` "Стальные квоты" (military factories) | law "Южное подданство", D3 nationalisation of South land from compliance 30, +15 compliance, a social level traded for the economy; leaf `khazar_lyceums` "Хазарские лицеи" (a NAM core on Khazar, else Keyzan, Veyr or Mazar) | `south_under_the_boards` "Юг под правлениями" (spirit "Владычество на юге" 730 days, civilian factories) |
| Council after the last enemy | 9 | `mergers_and_buyouts` "Слияния и выкупы" / `covenant_of_six` "Устав шести" (6) | law "Кодекс слияний", a social level traded for the economy, D7 buy-outs; leaf `southern_holding` "Южный холдинг"; opens "Одно правление", closes "Вечный совет шести" | law "Устав шести" (the two last companies' resting trust +10); leaf `founders_fund` "Фонд основателей" (every grudge cleared, D8) | `charter_of_the_directory` "Устав Директории" (spirit 730 days, a campaign place) |
| The ninety-nine | 5 | `share_for_the_ninety_nine` "Доля девяноста девяти" / `order_of_the_one` "Порядок одного" (1) | law "Реестр жалованья", rent x0.9, D9 rations; leaf `people_shops` "Народные лавки"; opens "Акции девяноста девяти" | law "Кабальный найм", a social level traded for the state, military factories; leaf `factory_towns` "Посёлки при заводах" (D10) | `cities_of_the_continent` "Города континента" (spirit "Кварталы континента" 730 days) |
| Army | 5 | `demobilisation` "Демобилизация" / `continental_garrison` "Гарнизон континента" (1) | law "Резервный реестр", civilian factories; leaf `veteran_artels` "Ветеранские артели" (D11) | law "Гарнизонная служба", two company regiments, spirit 365 days; leaf `company_garrisons` "Полки правлений на юге" (a regiment for each of the three largest lot holders, D12) | `army_of_dominion` "Армия владычества" (spirit 730 days, two escorts) |
| A hegemon's deals | 4 | `steel_and_oil_cartel` "Картель стали и нефти" / `open_sea_lanes` "Открытые морские линии" (7) | spirit "Цены картеля", D14 export | spirit "Открытые линии", dockyards | `bank_of_the_south` "Хазарский банк" (spirit 730 days, loans repay 125) |
| The last empire | 4 | `against_the_last_empire` "Против последней империи" / `arms_on_credit` "Оружие в долг" (7) | `RUS_crisis_enter_second_wave` (open only through `NAM_hgm_khan_war_open`, the effect's whole gate; bypassed on `NAM_hgm_khan_war_closed`), spirit 180 days | D15 arms on credit, military factories | `hegemons_price` "Цена гегемона" (spirit 730 days, event 276) |

Focuses before the pairs: `southern_offices` "Конторы на юге" (`available`
on the signed protocol), `furnace_houses` "Печные дома", `cold_fire_watch`
"Дозор холодного огня" (two militia brigades), `southern_cadastre` "Кадастр
юга" (event 280); `nothing_left_to_divide` "Нечего больше делить" (D6),
`chairs_seal` "Печать председателя" (a chair vote, spirit 365 days),
`heirs_of_the_founders` "Наследники основателей" (event 278: heir votes for
good), `count_of_six` "Счёт шести" (event 279); `hegemons_ledger` "Гроссбух
гегемона" (Shahrabad's bonds 12 a month for 365 days, D13), the merge of the
ninety-nine lane; `envoys_beyond_the_desert` "Послы за пустыней" (D16), the
merge of the army lane. `charter_of_dominion` and `charter_of_the_directory`
each add a Directory campaign place (clamp 6) and compliance on conquered
land. Pair-only leaves carry `allow_branch` on the other side, the Shahrabad
leaves on the form. Every focus has `cancel_if_invalid = no` and
`continue_if_invalid = no`.

"Последнее собрание" needs either centre row-6 focus and any two of the six
closers (`south_under_the_boards`, `charter_of_the_directory`,
`cities_of_the_continent`, `army_of_dominion`, `bank_of_the_south`,
`hegemons_price`); it brings the annual meeting forward to 7 days when no
meeting is open. Every completion read elsewhere is read after its reward:
rewards queue the recount; no flag mirrors a completion.

### I.10 The four finals

| Final | Condition (`available`, with `NAM_hgm_no_final_taken`) | Law | Spirit | Result |
| --- | --- | --- | --- | --- |
| "Лига округов" (x 16) | `NAM_hgm_league_ready`: union rules, `southern_extraction`, `NAM_hgm_district_count` above 4 (operating districts, written monthly) | "Устав лиги" (trade, succeeds "Устав промысла") | "Лига правлений" | economic trade; every operating district keeps its owner for good and moves to `autonomy_NAM_oil_charter` (freedom 0.40); district dividends x2; party "Лига правлений"; trait `NAM_trait_arbiter_of_the_league`; district owners +10, the rest -5; event 268 |
| "Акции девяноста девяти" (x 20) | `NAM_hgm_people_ready`: `share_for_the_ninety_nine`, the law `NAM_welfare_society_99_1` held, stability above 59%, votes for above votes against | "Народный реестр" (welfare, succeeds "99 на 1") | "Купон на каждый номер" | `NAM_hgm_trade_economic_for_society` (the economy one level down, the society one up or a programme run at its cap), stability +10%, war support +5%; four votes on the council's side; party renamed; trait `NAM_trait_trustee_of_the_register`; all six -8; event 269 |
| "Вечный совет шести" (x 24) | `NAM_hgm_six_ready`: "Слияния и выкупы" not taken, no company boycotting, every company with a holding (`NAM_board_districts_<k>`) | "Вечный устав" (information, succeeds "Устав шести") | "Шесть имён" | 100 PP, 50 command power; every district owner fixed; re-tender, buy-out and auction closed; district dividends -25%; a boycott needs 60 days of distrust; immunity after a vote 360 days; party renamed; trait `NAM_trait_chair_of_the_perpetual_council`; all six +4; event 270 |
| "Одно правление" (x 28) | `NAM_hgm_one_board_ready`: "Слияния и выкупы", the first company's ballot at least one and a half times the second's or two buy-outs, its trust above 59, 300 capital | "Единоличный устав" (industrial policy, succeeds "Кодекс слияний") | "Одно правление" | -300 capital (held by `continue_if_invalid = no`); army trade; `NAM_hgm_holding` = the first company; party named after it; `NAM_trait_owner_of_the_directory` only while the holding chairs; military factories (two on 699, else 700 or 688; one on 700, else 688 or 67); while the holding's trust is above 59 (`NAM_hgm_holding_commands`) the five vote for the council and the holding casts ten more votes; the five -6; event 271 |

No route is left without a final: "Слияния и выкупы" always reaches "Одно
правление" through two buy-outs; "Устав шести" or neither side keeps "Вечный
совет шести" open; the share and the union with extraction add theirs. The
chair keeps changing only by the annual meeting or a no-confidence vote;
`NAM_hgm_sync_chair_traits` (from the finals and `NAM_board_install_chairman`)
seats the final's trait on each new chair. The game goes on after a final
(W4); its closing event ends the route's story.

### I.11 Laws

The fourteen laws follow the council-law template (`cost = 0`,
`removal_cost = -1`, scripted-only `available` behind
`NAM_hgm_law_<x>_source_tt`, `allowed_to_remove` false behind
`NAM_board_law_locked_tt`, economy refresh in `on_add` / `on_remove`).
`NAM_hgm_enact_<law>` swaps the named predecessor first, then every other law
the slot can hold (council, war, mainland, dominion and the republic's
`NAM_pw_law_*`), `add_ideas` only for an empty slot. `NAM_board_repeal_laws`
repeals them at an annexation.

| Slot | Law | By |
| --- | --- | --- |
| taxation | "Печной сбор" `NAM_hgm_law_furnace_levy` / "Подушная опись" `NAM_hgm_law_inventory_tax` (succeed the mainland tithes or register) | the Shahrabad pair |
| trade | "Устав промысла" `NAM_hgm_law_extraction_charter` (succeeds the continental exchange); "Устав лиги" `NAM_hgm_law_league_charter` | `southern_extraction`; "Лига округов" |
| cultural policy | "Южное подданство" `NAM_hgm_law_southern_subjects` | `southern_province` |
| industrial policy | "Кодекс слияний" `NAM_hgm_law_merger_code` (succeeds the war charter); "Единоличный устав" `NAM_hgm_law_sole_charter` | `mergers_and_buyouts`; "Одно правление" |
| information | "Устав шести" `NAM_hgm_law_covenant_of_six` (succeeds the southern mandate); "Вечный устав" `NAM_hgm_law_perpetual_covenant` | `covenant_of_six`; "Вечный совет шести" |
| labour policy | "Реестр жалованья" `NAM_hgm_law_wage_register` / "Кабальный найм" `NAM_hgm_law_indenture` | the ninety-nine pair |
| welfare | "Народный реестр" `NAM_hgm_law_people_register` | "Акции девяноста девяти" |
| mobilisation | "Гарнизонная служба" `NAM_hgm_law_garrison_service` / "Резервный реестр" `NAM_hgm_law_reserve_register` (succeed the mainland levies) | the army pair |

Development trades: `NAM_board_trade_war_for_economic` (furnace trust,
province, mergers, league), `NAM_board_trade_war_for_state` (inventory,
order of the one), `NAM_board_trade_war_for_army` (extraction, one board),
each lowering a social track; "Акции девяноста девяти" trades the economy for
the society instead.

### I.12 Spirits, traits, events

Timed spirits: "Протокол раздела юга" 365 days (protocol), "Владычество на
юге" 730, "Печать председателя" 365, "Устав Директории" 730, "Кварталы
континента" 730, "Гарнизон континента" 365, "Армия владычества" 730, "Цены
картеля" 365, "Открытые линии" 365, "Хазарский банк" 730, "Поход на последнюю
империю" 180, "Цена гегемона" 730. The four final spirits are permanent.
Traits: `NAM_trait_arbiter_of_the_league`, `NAM_trait_trustee_of_the_register`,
`NAM_trait_chair_of_the_perpetual_council`, `NAM_trait_owner_of_the_directory`
(`common/country_leader/ADISCORD_traits_NAM.txt`). Dynamic modifiers
`NAM_ptn_free_port`, `NAM_hgm_southern_watch`; opinion modifiers
`NAM_hgm_mazar_share`, `NAM_hgm_loan_goodwill`, `NAM_hgm_credit_goodwill`,
`NAM_hgm_supply_goodwill`, `NAM_hgm_price_refused`.

Events (section "Council of boards: the South after the war" of
`events/ADISCORD_nam_resource_war_events.txt`). Story events follow C.5 with
three answers, the first the timeout answer:

| Event | Source | Title |
| --- | --- | --- |
| 230-232 | root, `furnace_trust`, `khazar_inventory` | "Две описи", "Ключи от печей", "Гербы с ворот" |
| 233-243 | lots 1-11 (tender, night or re-tender) | "Лот: <name>" (I.5) |
| 244 | walk-out | "Пустое кресло" |
| 245 | protocol | "Протокол на рассвете" |
| 246 | hidden dispatcher of the night | - |
| 247 | deadline | "Протокол без ночи" (one answer) |
| 248-265 | `furnace_houses`, `southern_extraction`, `southern_province`, `south_under_the_boards`, `nothing_left_to_divide`, `covenant_of_six`, `mergers_and_buyouts`, `charter_of_the_directory`, `share_for_the_ninety_nine`, `order_of_the_one`, `cities_of_the_continent`, `demobilisation`, `continental_garrison`, `army_of_dominion`, `steel_and_oil_cartel`, `open_sea_lanes`, `arms_on_credit`, `against_the_last_empire` | "Девять домов", "Первая квота", "Губернаторы юга", "Отчёт из Хазара", "Облигации войны", "Подписи под уставом", "Первый холдинг", "Устав в типографии", "Купон на номер", "Кабальный договор", "Новые кварталы", "Последний парад", "Казармы в Хазаре", "Флаг на верфи", "Цена за тонну", "Портовые сборы", "Первый покупатель", "Поход на последнюю империю" |
| 266-271 | `charter_of_dominion`, `last_meeting`, the four finals | "Суд хартии", "Повестка из одного пункта", "Лига правлений", "Купон на каждый номер", "Шесть имён", "Одно правление" |
| 272-276 | `steel_quotas`, `khazar_lyceums`, `factory_towns`, `company_garrisons`, `hegemons_price` | "Забастовка в Девятипечье", "Первый выпуск", "Беглые номера", "Чужой полк", "Письмо в одну строку" |
| 277 | to the debtor of 276 | "Письмо из Директории": accept (tribute 10 a month for a year, 15 for Loren's concession) or refuse (its arms credit forfeited, opinion -50); with no debtor 150 capital |
| 278-280 | `heirs_of_the_founders`, `count_of_six`, `southern_cadastre` | "Места наследников", "Недоимки", "Межевые камни" |
| 281-287 | the people of lots 5-11, 60-120 days after the lot is settled | title by the lot's form; answers "Твёрдая рука", "Уступить через владельца", "Купить старшин" |

Superevent request 79 "Юг на шесть долей" (event `ADISCORD_superevent.77`,
window `superevent_south_partition` with its sound, sprite
`GFX_superevent_south_partition` on
`gfx/interface/superevents/NAM/superevent_south_boards.png`) at the protocol.
No superevent for the finals (W5).

### I.13 Decisions

Every paid decision follows the custom-cost contract, keeps its receipt
where it belongs (a NAM variable or a state flag), refunds only through it
and clears it in the same block; political power is never refunded, except
the native price of a tender closed by the deadline.

| # | Decision | Category | Opened by | Price | Run | Result |
| --- | --- | --- | --- | --- | --- | --- |
| T1-T11 | `NAM_ptn_tender_1`..`_11` "Торги: <лот>" | `NAM_hgm_dominion` | the root (lots 1-4 after the form) | 25 PP | 7 days | the lot's event in tender mode |
| D1 | `NAM_ptn_retender` "Повторные торги" | `NAM_hgm_dominion` | `southern_exchange` | 40 PP | 14 days, re-enable 60 | I.5 |
| D2 | `NAM_hgm_furnace_contracts` "Подряды печных домов" | `NAM_hgm_dominion` | `furnace_dividends` | 40 capital | 60 days, re-enable 90 | Shahrabad's heat -10, Ferrant +2 |
| D5 | `NAM_hgm_extraction_quota` "Квота добычи" | `NAM_hgm_dominion` | `southern_extraction` | 25 PP | 30 days | on a South state: capital +80, 5000 rifles, resistance +10, worked for 180 days |
| D6 | `NAM_ptn_compensate` "Отступные" | `NAM_hgm_dominion` | `nothing_left_to_divide` | 60 capital | instant, re-enable 30 | the selected company with a grudge or trust below 35: trust +10, one grudge off |
| D7 | `NAM_hgm_buyout` "Выкуп доли" | `NAM_hgm_dominion` | `mergers_and_buyouts` | 50 PP | 30 days, at most three | the seller's lowest awarded lot (a district lot with its district) or else its first district passes to the first company, owner fixed; capital +80, buyer +6, seller -15 |
| D8 | `NAM_hgm_founders_dividend` "Дивиденд основателей" | `NAM_hgm_dominion` | `founders_fund` | 100 capital | instant, re-enable 180 | all six +3 |
| D9 | `NAM_hgm_rations` "Пайки Директории" | `NAM_hgm_dominion` | `share_for_the_ninety_nine` | 40 capital | 60 days, re-enable 120 | stability +2%; society programme on the first two runs |
| D10 | `NAM_hgm_company_towns` "Заводской посёлок" | `NAM_hgm_dominion` | `factory_towns` | 60 capital, 4000 men | 60 days | on a state: a shared slot and a military factory |
| D11 | `NAM_hgm_veteran_artel` "Артель ветеранов" | `NAM_hgm_dominion` | `veteran_artels` | 30 capital, 3000 men | 45 days | on a state: compliance +8, infrastructure |
| D12 | `NAM_hgm_lot_regiment` "Полк лота" | `NAM_mdr_army` | `company_garrisons` | 40 capital, 4900 men, 4410 rifles | 45 days | a Company Guard Regiment at the company's lots, else the harbour |
| D13 | `NAM_hgm_foreign_loan` "Заём за морем" | `NAM_mdr_south_office` | `hegemons_ledger` | 80 capital | instant | 100 back after 365 days (125 after "Хазарский банк") while the debtor exists and is at peace with NAM |
| D14 | `NAM_hgm_export_contract` "Экспорт по цене картеля" | `NAM_mdr_south_office` | `steel_and_oil_cartel` | 15000 fuel | 60 days, re-enable 90 | capital +70, Loren and Ferrant +2 |
| D15 | `NAM_hgm_arms_credit_sale` "Продать оружие в долг" | `NAM_mdr_south_office` | `arms_on_credit` | 6000 rifles, 48 guns | instant | 120 capital back after 180 days while the buyer exists |
| D16 | `NAM_hgm_coalition_supply` "Поставки коалиции" | `NAM_mdr_south_office` | `envoys_beyond_the_desert` | 10000 fuel or 5000 rifles | 30 days, re-enable 60 | to a coalition member at war with the Khan: capital +90, opinion +20, Loren or Arktur +2 |

The category `NAM_hgm_dominion` "Раздел и владычество" is visible from
`NAM_hgm_started` until `NAM_board_ended`. Loans and arms credits come due in
`NAM_hgm_loans_monthly`, one of each a month, oldest first.

### I.14 Shared script

Effects (NAM scope unless named; temps are reset by the effect):

| Effect | Inputs |
| --- | --- |
| `NAM_ptn_award` | temps `NAM_ptn_lot_input`, `NAM_ptn_company_input` (1-6, 0 kept), `NAM_ptn_mode` (1 tender, 2 night, 3 re-tender, 4 deadline; 0 the mode stored for the lot) |
| `NAM_ptn_apply_lot` | the same temps, from the award only |
| `NAM_ptn_compute_bid` | `NAM_ptn_lot_input`, `NAM_ptn_bid_company` (0 the base bid), `NAM_ptn_bid_mode`; output temp `NAM_ptn_bid_value` |
| `NAM_ptn_prepare_bids` | `NAM_ptn_lot_input`; writes the shown values `NAM_ptn_bid_a` / `_b`, trust, veto markers and forms for the scripted localisation |
| `NAM_ptn_fire_lot_event` | `NAM_ptn_lot_input`; the lot's event one hour later |
| `NAM_ptn_start_tender`, `_finish_tender`, `_cancel_tender` | `NAM_ptn_lot_input` |
| `NAM_ptn_start_retender`, `_finish_retender` | none; the lot is fixed when the decision is taken (`NAM_ptn_retender_open`) |
| `NAM_ptn_lot_state_cored` | STATE scope; takes the state out of its lot and closes an empty lot |
| `NAM_ptn_sequester` | COUNTRY loser, ROOT NAM |
| `NAM_ptn_open_table`, `NAM_ptn_run_night`, `NAM_ptn_night_next`, `NAM_ptn_sign_protocol`, `NAM_ptn_deadline_check`, `NAM_ptn_deadline_settle`, `NAM_ptn_monthly`, `NAM_ptn_count_holdings` | none |
| `NAM_ptn_walkout_leave` / `_pay` / `_charter` | `NAM_ptn_walkout_company` |
| `NAM_ptn_cadastre_pick`, `NAM_ptn_cadastre_award` | award: temp `NAM_ptn_cadastre_winner` (1 the first, 2 the second) |
| `NAM_ptn_compensate_deliver`, `NAM_hgm_buyout_deliver` | `NAM_board_company_input` |
| `NAM_hgm_apply_league`, `_people`, `_six`, `_one_board`, `NAM_hgm_sync_chair_traits` | none |
| `NAM_hgm_enact_<law>` (14), `NAM_hgm_trade_economic_for_society` | none |
| `NAM_hgm_raise_lot_regiments`, `NAM_hgm_pick_debtor`, `NAM_hgm_send_price`, `NAM_hgm_forfeit_credit` | none |

Building, formation and ship rows reuse `NAM_mdr_build`,
`NAM_mdr_place_division` and `NAM_mdr_launch_ships` (H.8). Triggers:
`NAM_hgm_tree_live`, `NAM_ptn_shl_on_table`, `NAM_ptn_table_cleared`,
`NAM_ptn_lot_open`, `NAM_ptn_union_rules`, `NAM_hgm_mazar_ally`,
`NAM_ptn_furnace_administration`, `NAM_ptn_friendly_country`,
`NAM_ptn_friendly_core_state`, `NAM_ptn_country_lot_owner`, `NAM_ptn_land_lot`,
`NAM_ptn_district_lot_lost`, `NAM_ptn_lot_furnace_live`,
`NAM_ptn_lot_counts_as_holding`, `NAM_ptn_retender_candidate`,
`NAM_ptn_retender_available`, `NAM_hgm_south_land`,
`NAM_hgm_southern_province_land`, `NAM_hgm_holding_commands`,
`NAM_hgm_last_meeting_ready`, `NAM_hgm_no_final_taken`, `NAM_hgm_league_ready`,
`NAM_hgm_people_ready`, `NAM_hgm_six_ready`, `NAM_hgm_one_board_ready`,
`NAM_hgm_khan_war_open`, `NAM_hgm_khan_war_closed`, `NAM_hgm_debtor_eligible`.
No loop of the partition scans the world: lot states are listed once in
`NAM_ptn_states`, losers in `NAM_ptn_sequestered_tags`.

### I.15 Lifecycle

`NAM_hgm_begin` is the single entry and `NAM_hgm_close` the single exit,
called by `NAM_board_end_operations` before `NAM_mdr_close`. `NAM_hgm_close`
refunds the receipts of D2, D9, D12, D14, D16 and the state works of D10 and
D11, clears the buy-out, the lot marks and modifiers of the South states, the
sequestration flags, the timed spirits of the tree behind `has_idea`, the lot,
company, loan and credit arrays and the deadline and tribute variables, and
marks the economy dirty. It keeps the laws, the final spirits, traits and
party names and the owners of districts. Kept for the campaign:
`NAM_hgm_started`, `NAM_ptn_table_open`, `NAM_ptn_protocol_signed`,
`NAM_ptn_shl_form`, `NAM_hgm_owner_fixed` on districts, `NAM_hgm_holding`,
`NAM_hgm_heir_votes`.

### I.16 AI

`NAM_southern_dominion_plan_union` (enable `NAM_ptn_union_rules = yes`):
the furnace trust, extraction, covenant, order of the one, garrison, then
"Лига округов" or else "Вечный совет шести".
`NAM_southern_dominion_plan_shares` (enable `NAM_mdr_mainland_shares`): the
inventory, province, covenant, share for the ninety-nine, demobilisation, then
"Вечный совет шести" or else "Акции девяноста девяти". `furnace_trust` has
AI factor 0 off the union rules; the finals have AI factor 100.

### I.17 Tests

`NamSouthernDominionTreeTests` in `tools/tests/test_adiscord_nam_focus.py`:
selection and owner, shared history, layout and mirror, rewards, branches
that are not clones, the tooltip layout standard, the partition from tenders
through the night to the protocol, each lot settled once, the deadline by
course, bids and the veto, recount rows, rents and owner fixing, the finals,
laws, receipts refunded once, the world lane, the lifecycle, the events, and
the mainland leftovers. `tools/tests/test_adiscord_south_final_war.py`:
`test_north_victory_partitions_for_the_council`. The superevent window is in
`tools/validators/validate_adiscord_superevents.py` and its test.

### I.18 What stays outside

1. **The Directory's own course inside the War for the South**
   (`NAM_south_war_focus`): the Directory still plays the no-course branch
   `NAM_sw_n_*`, which pays the state treasury, not the council's capital, and
   knows nothing of companies. A Directory lane there (war shares of future
   lots that make a company a fixed bidder, company war contracts in
   `NAM_corp_capital`) would need one more row in `NAM_ptn_prepare_bids`.
2. **Shahrabad's side.** `SHL_seal_overlord_hardline` and
   `SHL_seal_overlord_conciliatory` read only `NAM_pw_southern_military_rule`
   and `NAM_pw_southern_local_offices`; the OR rows for
   `NAM_hgm_southern_extraction` (hardline) and `NAM_hgm_southern_province`
   (conciliatory) and a Directory weight for the buy-back petition
   `ADISCORD_SHL.202` belong to the SHL files' owner. Until then the extraction
   and province tooltips say nothing about the Cold Fire.
3. **Names and flags.** Keyzan, Veyr and Fenn as company districts keep their
   own names; Mazar takes `MZR_NAM_corp_1`-`_6`. New cosmetic names for the
   finals and districts are an art package (W6).
4. **The radical and humanist exiles' South victory** still loads the
   republic's heritage tree.
5. **Old republic data** (`NAM_prewar_balance`, `NAM_pw_operable`) still
   decides the autonomy of a later submission to the Directory; the audit
   belongs to the republic's rework.

### I.19 Art still needed

- 49 focus icons `GFX_focus_NAM_hgm_<id>` in the board style (the tree binds
  existing sprites until they exist).
- A partition superevent picture (six heads at the Khazar exchange at dawn):
  the current one shows company men testing oil at a desert refinery, while
  this South is a steel and furnace prize.
- Four final superevent pictures for requests 80-83 (W5).
- Cosmetic names and flags of the finals and of South districts (W6).

The author saves the originals himself.

### I.20 What only a run of the game can prove

All by the user after a full restart: the load of the dominion tree one step
before the campaign close and the restore that then only clears value 7;
`set_autonomy` to the namestnik office on a freshly freed loser and the
control restored to it; the sort of the administrations' land and the
annexation of an empty administration; the tender, night and re-tender chain
with its dispatcher (one lot an hour, the wait while tenders run, a stalled
night resumed after 30 days) and its timeout answers; the walk-out boycott at
the next recount; the deadline on the first monthly tick after day 179;
`NAM_wor_federal_district_join` on a sequestered subject and `NAM_wor_radical_annex`
on a lot country; Fenn's merger into Eflor; `SHL_seal_open_chapter` from the
furnace trust and the furnace dividends while buy-backs run; the free port
modifier; the recount rows and rents against the pyramid; `set_party_name`
of the finals and the traits through later chairs; the Khan's second-wave
entry from the focus; superevent 79 with its window and sound; the war,
partition and final dates and the AI's finals in recent text saves.
