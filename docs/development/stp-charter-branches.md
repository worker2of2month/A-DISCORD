# Charter governments

## Scope

The existing Freedom against Slavery event chooses the first Charter government.
The three exclusive programmes each contain 30 authored focuses: Grigory
Sotnikov (humanism), Maksim Shabrat (chauvinism), and Vera Tikhoreva (utilitarism).
The preceding After Us event still chooses Charter versus hegemony. Completing
the freedom-opening focus dispatches the cabinet choice; no programme completes
automatically and the hegemony route remains closed.

The Charter is a common constitutional commitment. Sotnikov's existing military
directory remains a separate new-campaign route. Civil-war balance is unchanged.
The new programmes share reconstruction and external liberation systems rather
than duplicating wars, peace settlements, research trees or territorial claims.

## State and ownership

- `STP_pc_charter_cabinet`: 1 = Sotnikov, 2 = Shabrat, 3 = Tikhoreva.
- `STP_pc_course = 2` and the existing course lock retain the Charter's foreign
  policy and institutional continuity regardless of the leader's ideology group.
- `STP_pc_charter_sotnikov_current`, `STP_pc_charter_shabrat_current`, and
  `STP_pc_charter_tikhoreva_current` identify the selected serving government.
- `STP_pc_charter_government_current` is their union. The mandate persists across
  ordinary current-version save/load; selection cannot overwrite an existing one.
- All characters are already recruited through the campaign lifecycle. Appointment
  activates/promotes the registered character, never calls `recruit_character`.
- Common Charter focuses and transactions remain available to all three cabinets.
  Generic succession must not replace a selected cabinet behind its programme.

## Focus programmes

IDs use `STP_pc_charter_sotnikov_*`, `STP_pc_charter_shabrat_*`, and
`STP_pc_charter_tikhoreva_*`. Each programme has 25 focuses; three
mutually exclusive forks leave 22 completed focuses on any route. Programmes
occupy the original Charter area, immediately below `STP_pc_lib_lock`, beside the
shared liberation and coalition route. Their absolute bounds are x = 9..21,
y = 10..19. Only the selected cabinet's programme is visible. Shared Charter
ancestors stay visible after appointment, and the founder's personal hegemony
focus remains within the hegemony route.

Each cabinet has its own graph shape:

- Sotnikov, a shield: justice, civilian return and army-under-law pillars. Each
  pillar has one fork (open hearings or prison review, clinics or housing,
  citizens' reserve or professional service). Two cross-links join neighbouring
  pillars before the review.
- Shabrat, a chain of diamonds: citizenship and suppliers join at the registers;
  memory or national service sits beside two mandatory district works; the
  protection focus opens a six-way fan with arsenal or civil economy and district
  reserves or border drills forks.
- Tikhoreva, a ladder: records and reconstruction rails share rungs (published
  accounts, accountable service, reconstruction balance) beside a research rail.
  Forks choose service baselines or the limits of measurement, open tenders or
  standard designs, technical institutes or field trials.

Every fork keeps identical parents, and every child that follows a fork accepts
either branch in one `prerequisite` block. The review joins the final focus of
each pillar or wing. Most focuses last 21 days; construction, the review and the
capstone last 28 days.

Rewards combine:

- A leader trait added by the mandate and replaced by a stronger trait at the
  capstone (`common/country_leader/ADISCORD_traits_STP.txt`).
- Free adoption of the programme's laws. A law that is already active gives its
  stated political power instead, so a reward never reapplies the same tier.
- Exact `STP_pw_*` increments through the postwar dynamic modifier with dummy
  delta previews. Each field stays within 10 percent per programme, and
  administration savings within -10 percent.
- Factories in owned controlled states with free slots, research bonuses,
  equipment, manpower, army experience and command power.
- A hireable advisor role for Ravel (Sotnikov) or Barchel (Shabrat) when the
  character serves STS and is not arrested; otherwise command power.

Three repeatable programmes, one per candidate, give a meaningful focus unlock:
`STP_pc_charter_sotnikov_reintegration`, `STP_pc_charter_shabrat_civic_grants`,
`STP_pc_charter_tikhoreva_procurement`. Each has an explicit full price, cooldown,
government and completed-focus predicates; no delayed escrow is needed. Open
tenders is exclusive with standard designs, so Tikhoreva's procurement is a
deliberate choice.

Each cabinet has four events in the existing STP event file and registry:

- Sotnikov: `.65` prison review, `.80` the commandant's trial, `.81` the first
  strike under the Charter, `.68` conclusion.
- Shabrat: `.83` a settlement off the register, `.66` the common voice, `.82` the
  citizen's oath, `.69` conclusion.
- Tikhoreva: `.67` an error in a correct table, `.84` an unsigned expense line,
  `.85` a target against the person, `.70` conclusion.

Mid-programme events offer immediate trade-offs or timed spirits (labour
arbitration, trusted accounts, hard norms). Each conclusion chooses one of two
permanent legacy spirits. Every option rechecks the current cabinet, and a closed
answer remains when the cabinet has changed. Both languages preserve canon and
visible effects. Every event remains within 3000 characters and 5500 UTF-8 bytes
per description.

## Files and verification

All three cabinets use the shared liberation route against VAL and NOD. Local
contacts open each unresolved neighbour's political crisis even during a truce;
the truce still blocks paid preparation and declaration. Each campaign uses the
existing 900-treasury, 35-day preparation and 90-day readiness window. Successful
declaration consumes readiness, and an active war or resolved political outcome
blocks another declaration. NOD's earlier limited border defeat does not settle
the later political campaign. Its liberation receipt is captured before white
peace callbacks and cleared at settlement, peace or annexation. Already resolved
neighbours allow the foreign-policy focuses to advance without another war;
optional transition packages remain available only to eligible independent
recipients, and a pending package cannot be bypassed.

Keep focuses in `focus_trees/STP/postwar/shabrat/focuses.txt`, adding one named
section and its include in the existing civil-war authoring source. All other
content extends existing STP effects, triggers, events, decisions, ideas and RU/EN
localisation files. Regenerate the native focus tree with the owning builder.

Static checks cover cabinet selection and ideology, late institutional rewards,
blocked alternate routes, exact focus counts, prerequisites, positions, modifier
consumers, paid decisions, event registration and bilingual quoted values.

```powershell
python -B -m tools.builders.build_adiscord_focus_trees --source STP/civil_war/focuses.txt --check
python -B -m unittest tools.tests.test_adiscord_stp_postwar_story tools.tests.test_adiscord_stp_hegemony_expansion
python -B -m tools.validators.validate_focus_rewards --limit 300
python -B tools/validate_tc.py --limit 300
git diff --check
```

Native acceptance requires a cold start and fresh campaigns through each cabinet,
including an unanswered event, both Sotnikov availability states, shared Charter
focuses, the existing directory route, paid programme balances and readable UI.
Static verification must not be reported as native-game proof.

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
