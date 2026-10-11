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
`STP_pc_charter_tikhoreva_*`. Programmes occupy the original Charter area,
immediately below `STP_pc_lib_lock`, beside the shared liberation and coalition
route. Their absolute bounds are x = 9..19, y = 10..19. The three policy families
use short forks and joins with distinct graph shapes; each join requires all of
its contributing focuses. The programme review requires all six terminal leaves.
Only the selected cabinet's programme is visible. Shared Charter ancestors stay
visible after appointment, and the founder's personal hegemony focus remains
within the hegemony route.

Most focuses last 21 days; substantive construction or capstones may last 28
days. Layout and ordering do not change their total costs or rewards. Existing
textures illustrate records, courts, public services, logistics and defence.

- Sotnikov: independent courts, civilian oversight, veterans' reintegration,
  social recovery, defensive readiness and voluntary external cooperation.
- Shabrat: equal national citizenship, resistance memory, district integration,
  domestic industry, national defence and protection of citizens under the Charter.
- Tikhoreva: public records, accountable appointments, measured reconstruction,
  applied research, procurement oversight and transparent public expenditure.

Use the existing postwar dynamic modifier and exact dummy deltas. Limit each
programme's permanent output/research/organisation/construction improvements to
modest totals, normally 5-10 percent per field, and administration savings to
at most 10 percent. Mix capabilities, factories, research bonuses, equipment and
paid repeatable follow-ups; never install preview-only ideas. Every economic
change invalidates the existing cache. Treasury rewards/debits update the monthly
action ledger. Construction is in owned controlled states with enough slots.

Three repeatable programmes, one per candidate, give a meaningful focus unlock:
`STP_pc_charter_sotnikov_reintegration`, `STP_pc_charter_shabrat_civic_grants`,
`STP_pc_charter_tikhoreva_procurement`. Each has an explicit full price, cooldown,
government and completed-focus predicates; no delayed escrow is needed.

Mid-programme narrative dilemmas use events `.65`, `.66`, `.67` respectively;
programme conclusions use `.68`, `.69`, `.70`. They stay in the existing STP
event file and event registry. Both languages preserve canon and visible effects.
Every event remains within 3000 characters and 5500 UTF-8 bytes per description.

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
| 3 | Право на защиту | Память сопротивления | Назначения по делу |
| 4 | Открытое разбирательство | Служба общей стране | Исходная мера услуг |
| 5 | Районные приёмные | Свести районные реестры | Публиковать счета |
| 6 | Пересмотр заключений | Предел национального требования | За пределами показателя |
| 7 | Гражданский надзор | Национальные районные гранты | Проверка вне ведомства |
| 8 | Самоуправление по Хартии | Защита граждан | Обжалование по существу |
| 9 | Учить свободе | Школа общей страны | Публичный разбор результатов |
| 10 | Гарантии без исключений | Обязательство перед страной | Ответственная государственная служба |
| 11 | Возвращение к мирной жизни | Опора на своих поставщиков | Обследовать разрушения |
| 12 | Восстановить семейные записи | Учёт рабочего инструмента | Очередность ремонта |
| 13 | Районные лечебницы | Мастерская для района | Открытые закупки |
| 14 | Дома для семей | Единый промышленный стандарт | Проверенные типовые решения |
| 15 | Голос работников | Общие строительные бригады | Опытная мастерская |
| 16 | Мастерские мирного труда | Национальный арсенал | Приёмка по результату |
| 17 | Освоить мирное ремесло | Испытать свои материалы | График обслуживания |
| 18 | Безопасный рабочий день | Связать районные хозяйства | Расчёт районной логистики |
| 19 | Общественный договор труда | Хозяйственная самостоятельность | Баланс восстановления |
| 20 | Армия в рамках закона | Защита национального дома | Исследования для практики |
| 21 | Опыт без культа войны | Присяга государству | Открытый лабораторный журнал |
| 22 | Служба спасения раненых | Проверить пограничную готовность | Технические наставники |
| 23 | Учения ради защиты | Районный резерв | Полевые испытания |
| 24 | Снабжение без реквизиций | Отечественное снабжение | Арсенал проверенного образца |
| 25 | Запасы для спасения | Имущество для обороны | Подготовка с обратной связью |
| 26 | Сотрудничество по доброй воле | Единая работа штабов | Единый каталог запчастей |
| 27 | Ответственность командира | Устойчивый тыл граждан | Обратная связь штабов |
| 28 | Готовность беречь мир | Армия своих граждан | Знание на службе общества |
| 29 | Проверка обещаний | Собрать результаты районов | Сводная проверка программы |
| 30 | Свобода становится привычкой | Сильная страна под Хартией | Полезное государство по Хартии |
