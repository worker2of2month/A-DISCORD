# Charter governments

## Scope and ownership

The existing Freedom against Slavery focus dispatches the choice of the first
Charter government: Grigory Sotnikov (humanism), Maksim Shabrat (chauvinism), or
Vera Tikhoreva (utilitarism). The preceding After Us event chooses Charter versus
hegemony. Appointment does not complete any programme automatically. Sotnikov's
military directory is a separate route.

Each government has **25 authored focuses and three exclusive pairs**. One
complete playthrough finishes 22 programme focuses. All three use the common
Charter institutions, reconstruction and external liberation systems; they do
not duplicate wars, peace settlements, research trees or territorial claims.

- `STP_pc_charter_cabinet`: 1 = Sotnikov, 2 = Shabrat, 3 = Tikhoreva.
- `STP_pc_course = 2` and the existing course lock preserve Charter foreign
  policy regardless of the leader's ideology.
- `STP_pc_charter_<leader>_current` checks the selected cabinet and its serving
  leader. `STP_pc_charter_government_current` is their union.
- Appointment activates an already recruited character. Selection cannot
  overwrite an existing mandate, and generic succession must not replace it.
- State persists through ordinary save/load of the current campaign. There is
  no old-save migration or reconstruction of historical choices from bonuses.

Programmes extend the existing `STP_postwar_administration` decision category.
It becomes visible after the selected cabinet's mandate, so the programmes do
not depend on a later territorial-integration focus.

## Focus structure

Programme IDs use `STP_pc_charter_sotnikov_*`,
`STP_pc_charter_shabrat_*` and `STP_pc_charter_tikhoreva_*`. Only the selected
cabinet's programme is visible. The shared ancestors remain visible after
appointment. Each exclusive pair has the same parents; a child accepting either
alternative uses one `prerequisite` block. Most focuses last 21 days;
construction, cabinet review and the capstone last 28 days.

- Sotnikov has three pillars: justice, civilian return and army under law.
  Choices are open hearings or detention review, clinics or housing, and
  citizens' reserves or professional service. The first two pairs choose the
  initial priority; decisions later fund the other service.
- Shabrat joins citizenship and domestic suppliers at the district registers.
  Memory or national service precedes citizens' protection. Its three wings
  cover citizenship, the district economy and common defence; further choices
  are an arsenal or economic sovereignty, and district reserves or border drills.
- Tikhoreva connects records, reconstruction and applied research. Choices are
  service baselines or the limits of measurement, open tenders or standard
  designs, and technical instructors or field trials.

The mandate gives the initial leader trait. The stronger trait, permanent legacy
and personal superevent belong to a validated outcome, not merely the last
focus. The capstone can produce a provisional conclusion with work still open.
Later decisions can complete it without replaying focuses or charging for
recognition.

Existing law rewards, postwar modifier increments and dummy delta previews
remain in their respective focuses. A programme that uses a building site checks
ownership, control and capacity when it pays and when it delivers. National
receipts and state flags serve different scopes and must not be substituted for
one another.

## Sotnikov: the victors answer to the law

The programme connects judicial precedent, civilian employment and an army under
civilian rules. Its four events are `.65` detention review, `.80` the
commandant's trial, `.81` the first strike and `.68` the conclusion.

Judicial outcomes are stored explicitly:

- `STP_pc_charter_sotnikov_command_ruling`: 1 = civilian jurisdiction,
  2 = a military panel awaiting civilian review, 3 = the veteran's exception.
- `STP_pc_charter_sotnikov_prison_ruling`: 1 = completed civilian review,
  2 = an officers' examination awaiting civilian review.
- `STP_pc_charter_sotnikov_labour_agreement`: 1 = funded agreement,
  2 = arbitration, 3 = postponement.

The veteran's exception enacts military immunity. It is not only a narrative
marker. Civilian oversight and the later review replace that exception with
military prosecution. Both judicial cases must be heard; reviewing an existing
military decision does not silently complete a case that was never opened.

Programme decisions, all with the `STP_pc_charter_sotnikov_` prefix:

- `complete_justice`: 50 political power to open the unchosen judicial strand
  after district petition offices. Its receipt remains until the event answer;
  closing it after a cabinet change refunds the payment.
- `review_command`: 50 political power after civilian oversight. It completes
  civilian review of military decisions already announced, removes the exception
  and adds 2 percent stability. Newly opened cases can still require another
  review.
- `reintegration`: 60 political power and 600 treasury, 35 days. One successful
  programme creates one civilian factory and adds 2 percent stability. It does
  not replenish manpower. A failed or cancelled programme refunds both prices
  and can be retried; a successful programme cannot repeat.
- `complete_social`: 50 political power and 300 treasury, immediate and
  one-time. After clinics, the housing programme adds 5 percent construction
  speed. After housing, it enacts public hospitals; an already active hospital
  law gives the stated 40 political power instead.
- `settle_labour`: 40 political power and 300 treasury, immediate. It fulfils
  arbitration or a postponed agreement, removes the arbitration spirit and
  adds 4 percent stability. The same price applies to accepting the workers'
  demands in `.81`. Expiry of arbitration does not discharge the obligation.
- `supply_contract`: 300 treasury, 21 days, after rescue stores. One successful
  delivery gives 150 support equipment, 50 trucks and 20 army experience.
  Civilian contracts must remain active; a failed contract refunds its payment.
- `confirm_legacy`: a free, guarded confirmation after the capstone.

Reintegration and supply have separate payment receipts. The receipt is consumed
before delivery or refund; cancellation and expiry cannot both settle it.
Reintegration also rechecks the availability of an owned, controlled factory
site. Cabinet changes, capitulation or loss of the required operation conditions
cancel the paid work. Treasury debits enter monthly action costs and refunds
enter monthly action income, with economy-cache invalidation.

Both legacies require civilian completion of both judicial cases, civilian
oversight without military immunity, an honoured labour agreement with collective
bargaining still active, the reintegration workshop, the funded second social
priority and the delivered supply contract with civilian contracts still active.
The professional-service focus with the current cadre-army law yields civilian
law; the citizen-reserve focus with current territorial reserves yields
citizen-defenders. The shared award effect checks the capstone and an unclaimed
legacy before granting the spirit, guarantor trait and superevent 22.

The preparatory public command agreement is consumed and cleared when elections
are resolved. This programme does not infer it from the old mandate's numeric
bonuses or grant a retrospective discount for it.

## Shabrat: citizenship carries obligations in both directions

The programme connects complete citizenship, actual district agreements and
common defence. Events `.83`, `.66` and `.82` determine registration,
the common political voice and the citizen's oath; `.69` concludes the route.

`STP_pc_charter_shabrat_registers = 1` records full registration and value 2
records the omitted settlement. `STP_pc_charter_shabrat_oath = 1` records equal
access to the oath; higher values retain an unresolved restriction.
`STP_pc_charter_shabrat_voice = 2` gives the districts participation in the
common decision. These outcomes govern programmes and final eligibility.

Decisions use the `STP_pc_charter_shabrat_` prefix:

- `complete_registers`: 40 political power, 21 days, to remedy omitted
  registration; completion adds 2 percent stability.
- `review_citizenship`: 50 political power, 28 days, to remove collective
  restrictions from the oath; completion adds 2 percent stability.
- `civic_grants`: 75 political power and 600 treasury, 35 days. The selected
  owned and controlled district receives one civilian factory, an agreement
  with the centre and 2 percent national stability. A functioning agreement
  requires current ownership, control and at least one local civilian factory.
  If all of that district's workshops are lost, it can be rebuilt for full
  price.
- `defence_contract`: 35 political power and 300 treasury, 28 days. It requires
  settled citizenship and an operating district agreement. One delivery gives
  900 rifles and 150 support equipment; district reserves give 20 command power,
  while border drills give 20 army experience.
- `ratify_districts` and `ratify_nation`: free confirmations once their
  respective outcome is earned.

One country receipt (`project_kind`, political-power and treasury deposits)
covers every paid programme and every district target. An existing receipt
blocks another payment, including at a different target. The district's pending
flag identifies the paid site through delivery or cancellation. Full refunds and
receipt cleanup occur on cancellation or failed delivery.

Both legacies require the completed focus programme, full registration, an equal
oath, an operating district agreement and no outstanding paid project. The
districts legacy additionally requires district participation in the common
decision; the national-defence legacy requires the completed defence delivery.
A provisional `.69` leaves these programmes available. Either successful award
grants its legacy and the first-citizen trait, then unlocks the free national
decision `STP_pc_proclaim_stelander_union` in the postwar administration category.
The decision adopts the `STS_stelander_union` name and flag and enqueues
superevent 23 once. Its effect rechecks the current Shabrat charter government,
completed capstone and either earned legacy before recording the proclamation.
The presentation-only console gateway remains `ADISCORD_superevent.20`.

The Union flag is defined geometrically in `tools/builders/build_adiscord_stp_flags.py`.
Its navy field, ivory band, gold mountain star and laurel branches are exported
in all three native sizes with `--flags-only STS_stelander_union`; run `--check`,
then `--apply`, then `--check`. The super-event retains the shared Shabrat
illustration. Its dedicated GUI sound is
`superevent_stelander_shabrat_republic_sound_e`: the opening 60 seconds of
Vangelis, *1492: Conquest of Paradise*, with a 30 ms onset fade, four-second
closing fade and constant gain of +3.06 dB. The PCM master uses stereo 44.1 kHz
and 16-bit samples, with an integrated level of approximately -20 LUFS and
peaks below -3 dBTP. The existing 60-second silent carrier covers the excerpt.
Regenerate its OGG mirror through `tools.builders.build_adiscord_superevent_music`
with `--track superevent_stelander_shabrat_republic`, using `--check`, `--apply`,
then `--check`.

## Tikhoreva: a reported result must survive inspection

The programme connects an expense audit, a working pilot workshop, corrected
service standards and optional replication. Event `.84` chooses the audit
method; `.67` handles workshop acceptance; `.85` chooses how to repair the
harmful standard. Event `.70` evaluates the actual completed work.

Decisions use the `STP_pc_charter_tikhoreva_` prefix:

- `public_audit`: 40 political power, 28 days; or
  `professional_audit`: 300 treasury, 42 days. Both publish the completed
  findings, grant trusted accounts for 180 days and unlock the paid pilot.
- `contract_pilot`: 900 treasury, 42 days, on the open-tenders route; or
  `standard_pilot`: 720 treasury, 56 days, on the standard-designs route.
  An eligible owned and controlled state is selected and recorded. Construction
  alone creates no factory and does not release the original deposit.
- `complete_acceptance`: another 180 treasury and 28 days, available only
  after `limits_of_measurement`; or
  `staged_acceptance`: another 120 treasury and 42 days. Both finish the
  workshop at its recorded site and only then deliver one civilian factory.
  A partial acceptance is not a production reward.
- `revise_norm`: 30 political power, 35 days; or
  `verify_norm`: 300 treasury, 28 days. Both require an operating pilot,
  remove hard norms, record a verified correction and add 2 percent stability.
- `replicate_pilot`: 450 treasury and 100 support equipment, 42 days. It requires
  corrected standards, the research-in-service focus and an operating pilot.
  Delivery creates one military factory at the recorded eligible site.
- `abandon_pilot` returns the full construction deposit before final acceptance
  without delivering a factory. `ratify_programme` reopens a deferred final
  review at no additional cost once the work is ready.

The country project kind and deposits reserve treasury, political power and
support equipment. State flags identify the pilot and replication sites.
Acceptance waiting state retains the construction deposit, so another programme
cannot overwrite it. Delivery consumes the receipt once; cancellation returns
all reserved currencies and clears the corresponding temporary site state.
Loss of a required site, capacity or operating pilot invalidates dependent work.

Open tenders also retain the existing optional procurement decision: 75
political power for 100 support equipment and two trains, repeatable after
120 days. This supply purchase does not replace the audited pilot or its
acceptance.

The open-ledger legacy requires a completed audit, an owned and controlled
operating pilot, verified correction of the standard and no unfinished project.
The useful-state legacy additionally requires successful replication. A
provisional final report preserves pending work and permits later ratification.
Recognition grants one legacy, the stronger cabinet trait and the personal
superevent; the provisional answer does not.

## Shared foreign policy and AI

All cabinets use the existing liberation route against VAL and NOD. Local
contacts open unresolved political crises even during a truce; the truce still
blocks paid preparation and declaration. Campaign preparation costs 900 treasury,
takes 35 days and grants a 90-day readiness window. Declaration consumes
readiness, and an active war or resolved political outcome blocks a duplicate
declaration. NOD's earlier limited border defeat does not settle the later
political campaign.

The NOD liberation receipt is captured before white-peace callbacks and cleared
at settlement, peace or annexation. Already resolved neighbours allow the common
foreign-policy focuses to advance without another war. Transition packages still
require an eligible independent recipient and its choice; a pending offer cannot
be bypassed. The coalition epilogue is separate from each cabinet's domestic
legacy.

Each Charter transition offer records the cabinet that quoted it. Acceptance
rechecks that government, the recipient and 300 treasury, then pays once and
delivers its programme to the accepting country. Sotnikov adds 25 social-system
development progress and 2 monthly growth. Shabrat delivers 900 rifles and 150
support equipment. Tikhoreva delivers 100 support equipment, 2 trains and one
50% industry research bonus. The quoted package cannot change into a successor
cabinet's programme while its event is open.

`common/ai_strategy_plans/ADISCORD_STP_plans.txt` contains three selected-cabinet
plans. Each first completes assembly, institutions, civilian army and the Charter
lock, then lists exactly 22 programme focuses and the shared foreign-policy
continuation. Each plan selects only one side of every exclusive pair:

- `STS_charter_sotnikov_plan`: open hearings, clinics, professional service.
- `STS_charter_shabrat_plan`: national service, national arsenal, border drills.
- `STS_charter_tikhoreva_plan`: limits of measurement, open tenders, field trials.

The earlier reconstruction and founder-hegemony plans stop when a Charter
cabinet has been selected. This also prevents a Shabrat Charter government from
continuing the founder's hegemony plan merely because the same character rules.
Cabinet plans stop if their government changes or both their capstone and the
coalition focus are complete. Decision and event AI remains responsible for
paying programmes and responding to their outcomes; listing focuses does not
prove that an unattended campaign reaches an earned legacy.

## Files and verification

Authored cabinet programmes are grouped in
`focus_trees/STP/postwar/charter/sotnikov.txt`, `shabrat.txt` and `tikhoreva.txt`,
with 25 focuses per file. Shared institutions, reconstruction and foreign policy
remain in `focus_trees/STP/postwar/shabrat/focuses.txt`. All fragments are included
directly by `focus_trees/STP/civil_war/focuses.txt` in their native order.
Effects, triggers, decisions, events,
ideas and RU/EN localisation extend the existing country files. Regenerate
`common/national_focus/ADISCORD_STP_civil_war.txt` through its owning builder,
using check before apply and then proving idempotence.

Static verification covers cabinet ownership, 25/22 focus counts, unique
positions, exclusive alternatives and prerequisites, native boolean scripted
calls, prices and affordability boundaries, currency accounting, receipt
consumption, cancellation, occupied or full delivery sites, unanswered events,
provisional and late final outcomes, AI focus IDs and bilingual quoted values.

```powershell
python -B -m tools.builders.build_adiscord_focus_trees --source STP/civil_war/focuses.txt --check
python -B -m unittest tools.tests.test_adiscord_stp_postwar_story tools.tests.test_adiscord_stp_hegemony_expansion
python -B -m tools.validators.validate_focus_rewards --limit 300
python -B tools/validate_tc.py --limit 300
git diff --check
```

Native acceptance still requires a complete restart and new campaigns through
all cabinets: record the loaded source hashes, inspect fresh logs, exercise an
unanswered event and cabinet change, verify before/after balances and cancellation
during paid work, inspect every final answer and confirm readable focus and
decision UI. Check both Sotnikov availability states and the separate directory
route. Static parsing, tests and AI-plan inventories are not native-game proof.

## Sword directory: the founder's return

When the party arrested Shabrat before the split, Sotnikov leads the sword
directory (`STP_pc_sdir_*`). The arrested founder stays on STP until the union
victory: `STP_cw_settle_union_victory` calls `STP_sdir_take_founder_into_custody`
before annexation, because an annexed tag keeps its characters.

- `.90` follows the oath and records `STP_sdir_founder_custody`: 1 = headquarters
  guard (+15 command power), 2 = honourable arrest (+3% stability), 3 = loyalist
  cells broken. The custody value sets the plot margin.
- `STP_sdir_loyalist_plot` is an activation mission. It starts when the directory
  is weak: stability below 30% (guard) or 45% (honourable), or surrender progress
  above 25%. Recovery to 40% or 55% stability with surrender progress no higher
  than 10% exposes the plot; `STP_sdir_purge_loyalist_cells` (75 political power)
  ends it at once. Both set value 3 and fire `.93`. The 60-day timeout is the
  coup: the founder returns, Sotnikov is arrested and loses his unit-leader role,
  with -10% stability and the 180-day `STP_sdir_loyalist_purge`; `.92` narrates it.
- `STP_pc_sdir_return_seal` is the exclusive alternative to
  `STP_pc_sdir_sword_directory`, with the same prerequisites. Its event `.91`
  keeps Sotnikov as an army-chief advisor (+5% stability) or gives 100 political
  power; both restore the founder.

`STP_sdir_restore_founder` takes `STP_sdir_restore_input` (1 = handover,
2 = coup). It refunds directory district, arsenal and naval receipts, clears the
founder's arrest, promotes him before switching the ruling party to chauvinism
and sets `STP_pc_course = 1` with `STP_pc_founder_choice = 1`. The existing course
lock keeps the Charter closed; the founder continues through
`STP_pc_shabrat_politics` and the hegemony branch and AI plan. Directory focuses
and subject autonomies already granted remain.

## Programme index

| # | Сотников | Шабрат | Тихорева |
|---|---|---|---|
| 1 | Мандат человеческого достоинства | Национальный мандат Хартии | Мандат измеримого результата |
| 2 | Суд вне приказа | Одно гражданство | Открытые государственные реестры |
| 3 | Открытое разбирательство | Опора на своих поставщиков | Назначения по делу |
| 4 | Пересмотр заключений | Свести районные реестры | Исходная мера услуг |
| 5 | Районные приёмные | Память сопротивления | За пределами показателя |
| 6 | Гражданский надзор | Национальные районные гранты | Обследовать разрушения |
| 7 | Гарантии без исключений | Учёт рабочего инструмента | Публиковать счета |
| 8 | Возвращение к мирной жизни | Служба общей стране | Проверка вне ведомства |
| 9 | Восстановить семейные записи | Защита граждан | Публичный разбор результатов |
| 10 | Районные лечебницы | Школа общей страны | Очередность ремонта |
| 11 | Дома для семей | Обязательство перед страной | Открытые закупки |
| 12 | Голос работников | Мастерская для района | Проверенные типовые решения |
| 13 | Мастерские мирного труда | Единый промышленный стандарт | Опытная мастерская |
| 14 | Освоить мирное ремесло | Защита национального дома | Ответственная государственная служба |
| 15 | Армия в рамках закона | Присяга государству | График обслуживания |
| 16 | Резерв граждан | Предел национального требования | Баланс восстановления |
| 17 | Профессиональная служба | Национальный арсенал | Исследования для практики |
| 18 | Служба спасения раненых | Хозяйственная самостоятельность | Открытый лабораторный журнал |
| 19 | Учения ради защиты | Районный резерв | Технические наставники |
| 20 | Снабжение без реквизиций | Проверить пограничную готовность | Полевые испытания |
| 21 | Запасы для спасения | Устойчивый тыл граждан | Арсенал проверенного образца |
| 22 | Ответственность командира | Связать районные хозяйства | Подготовка с обратной связью |
| 23 | Готовность беречь мир | Имущество для обороны | Знание на службе общества |
| 24 | Проверка обещаний | Собрать результаты районов | Сводная проверка программы |
| 25 | Свобода становится привычкой | Сильная страна под Хартией | Полезное государство по Хартии |
