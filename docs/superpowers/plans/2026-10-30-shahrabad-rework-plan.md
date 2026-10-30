# Шахрабад: план содержимого деревьев курсов (этап 3)

Рабочий план к [спеке переработки](../specs/2026-10-30-shahrabad-rework-design.md),
раздел M3-M4. Этап 2 разнёс существующие курсовые фокусы по пяти деревьям;
этот план задаёт новое содержимое каждого дерева и контракт решений, которые
его обслуживают. Фокусы пишут авторы деревьев, решения, эффекты, триггеры и
миссии - один автор скриптовых файлов SHL; оба читают этот документ.

## Общие правила

- Стоимости: 2 - короткий шаг, 3 - программа, 4 - институт, 5 - финал.
- Награда фокуса: разблокировка решения (`unlock_decision_tooltip` + одна
  строка результата), материальный результат, политическое изменение,
  сдвиг `SHL_conclave_balance` или постоянный модификатор через `SHL_pow_*`
  с dummy-превью (не больше одного на секцию).
- Переменные и эффекты, которыми может пользоваться автор дерева без
  нового скрипта: `add_power_balance_value`, `SHL_pow_*` + `SHL_refresh_conclave_power`,
  `SHL_unrest`, `SHL_house_pressure`, `SHL_city_support`, `SHL_refresh_furnaces`,
  `SHL_raise_paid_levies_2/3`, `SHL_create_levy`, казна через
  `ADISCORD_economy_treasury` + `ADISCORD_economy_mark_dirty`, владение печью
  через `SHL_assign_site_owner_house/city` в скоупе области, существующие
  духи SHL, `add_building_construction`, `add_equipment_to_stockpile`,
  `add_tech_bonus`, `add_manpower`, `army_experience`, события `ADISCORD_SHL.*`,
  `ADISCORD_south_*` эффекты консолидации.
- Все новые решения живут в `ADISCORD_SHL_decisions.txt`; категории не
  добавляются: устройство и хозяйство курса - в `SHL_quarters_and_borders`
  (секция курса), печные заказы - в `SHL_conclave`.
- Платные решения: `custom_cost_text`, `cost = 0`, одна проверка и одно
  списание, квитанция, возврат один раз. Миссии: `available = { hidden_trigger = { always = no } }`,
  регистрация в `ADISCORD_tokens.txt`.
- Локализация: авторы деревьев пишут фрагменты `scratchpad/loc/<дерево>_ru.yml`
  и `_en.yml`; ведущий сливает их в хабы. Описания - повествование без
  пересказа эффектов.
- Раскладка: свободная клетка между соседями, ветки по центру под корнем.

## Контракт решений и миссий (автор скрипта)

| ID | Курс | Тип | Цена / срок | Результат |
| --- | --- | --- | --- | --- |
| `SHL_cargo_insurance` | 1 | нац. | 100 казны, 60 дн. | +5 конвоев; дух `SHL_insured_cargo` 180 дн.: -5% расхода снабжения |
| `SHL_house_credit` | 1 | цель RHM/SDR/KDR/MZR | 150 казны | цель получает `ADISCORD_south_indebted_to_SHL`; SHL +25 казны в 6 следующих циклах (`SHL_credit_cycles`) |
| `SHL_metal_exchange_toggle` | 1 | нац. | 25 PP | переключает `SHL_export_mode` 0 (картель, 60) / 1 (биржа: выручка экспортной печи 45-75 по циклу); требует фокуса биржи |
| `SHL_cons_debt_term` | 1 | миссия 180 дн. | - | старт от `SHL_south_debt_network`; успех - RHM и SDR подчинились/в союзе; таймаут - `ADISCORD_south_demand_annexation` должникам |
| `SHL_council_election` | 2 | миссия 180 дн., повторная | - | при `SHL_city_support >= 40`: +50 PP, +3% стабильности, BOP +0.03; иначе BOP -0.05, недовольство +5 |
| `SHL_furnace_school` | 2 | цель печь | 100 казны, 42 дн. | `SHL_furnace_training` +1 (макс 2), недовольство -2 |
| `SHL_quarter_hospital` | 2 | цель печь | 120 казны, 56 дн. | флаг области `SHL_quarter_hospital`; недовольство -4, `SHL_city_support` +3; один раз на область |
| `SHL_cons_charter_round` | 2 | миссия 150 дн. | - | старт от `SHL_south_wells_charters`; успех - два союзника договора; таймаут - второе предложение всем отказавшим |
| `SHL_mobilisation_quota` | 3 | цель печь | 0, 2 цикла | получатель печи принудительно арсенал на 2 цикла; недовольство +4; по завершении +600 винтовок сверх плавки |
| `SHL_directorate_railway` | 3 | нац. | 200 казны, 70 дн. | +1 инфраструктура в 294 и 699 (проверка места при доставке) |
| `SHL_state_concession` | 3 | цель печь (владелец 2) | - | аренда дому: владелец 2 -> 0, +100 казны, BOP -0.05; требует фокуса концессий |
| `SHL_cons_ultimatum` | 3 | миссия 120 дн. | - | старт от `SHL_south_water_and_sea`; таймаут - `ADISCORD_south_demand_annexation` неподчинившимся KYZ/GLP |
| `SHL_sell_concessions` | 4 | нац., раз в 180 дн. | - | +300 казны, `ADISCORD_economy_debt` +500, давление гербов -5 |
| `SHL_regent_guard` | 4 | нац. | 150 казны, 3000 людей, 21 дн. | `SHL_create_levy` (одна дружина), дух `SHL_restored_house_guard` если его нет |
| `SHL_debt_tribunal` | 4 | цель печь с залогом | 40 PP | взыскание без ожидания срока; недовольство +8 |
| `SHL_cons_toll_term` | 4 | миссия 150 дн. | - | старт от `SHL_south_toll_debtors`; таймаут - `ADISCORD_south_demand_annexation` SDR/RHM |
| `SHL_brotherly_supply` | 5 | цель печь | 0, 7 дн. | донор (печь с запасом >= 2) отдаёт 1 пакет получателю; недовольство -2 |
| `SHL_shift_school` | 5 | нац. | 80 казны, 35 дн. | `SHL_furnace_training` +1 печи с наибольшим износом |
| `SHL_strike_support` | 5 | цель GLP/MZR | 50 казны, 20 PP, 60 дн. | `SHL_cons_councils_support@цель` +25; при 75 цель получает предложение союза повторно с бонусом согласия |
| `SHL_cons_councils` | 5 | миссия 180 дн. | - | старт от `SHL_south_councils_abroad`; успех - MZR или GLP в союзе; таймаут - повтор предложения |
| `SHL_house_demand` | все | миссия 45 дн. | - | второй акт: событие `ADISCORD_SHL.140` раз в 120 дней после ратификации от дома с худшей печью; таймаут - дом в оппозиции 180 дн. (флаг `SHL_house_opposed@дом`, советник недоступен), давление +10 |
| `SHL_neighbour_revanche` | все | событие `ADISCORD_SHL.76` | - | через 365 дн. после проигранной соседом ограниченной войны, если он не цель консолидации: претензия и предложение пересмотра за казну |

Эффекты, нужные деревьям: `SHL_commit_metal_exchange` (экспортный режим),
`SHL_lease_all_state_furnaces` (концессии), `SHL_annex_integration_<course>`
(эпилог: интеграция сателлитов по таблице спеки Юга).

## Деревья

Структура каждого дерева: корень = первый фокус старой цепочки курса;
секция "Устройство" слева от него, "Хозяйство" справа, "Консолидация" под
старыми фокусами, общий фронт в отдельной колонке, "После войны" внизу
под `allow_branch = { has_global_flag = ADISCORD_south_hegemon_SHL }`.

### 1. Десятый дом - `SHL_houses_focus`

Устройство (корень `SHL_golden_gate_cartel` остаётся):
- `SHL_h_cartel_price` (3) <-> `SHL_h_metal_exchange` (3): фиксированная цена
  60 с +5% прироста эффективности через `SHL_pow_efficiency_gain` против
  разблокировки `SHL_metal_exchange_toggle`; обе требуют `SHL_golden_gate_cartel`.
- `SHL_h_council_of_ten` (4): голос десятой печи оформлен - `SHL_house_votes`
  учитывает десятую, BOP -0.05, +25 PP.
- `SHL_h_house_guards_charter` (3) <-> `SHL_h_conclave_mercenaries` (3):
  существующий `SHL_house_guards` остаётся корнем пары; хартия даёт
  `SHL_raise_paid_levies_2` и давление -10; наёмники - `SHL_hire_desert_guard`
  дешевле на 25% (переменная `SHL_guard_discount`).
- `SHL_h_heralds_court` (3): суд гербов - аресты в кризисе гербов доступны
  домам (снимает ограничение дирекции в `SHL_can_arrest_crests`); недовольство +5.
- `SHL_h_guild_schools` (3): `add_tech_bonus` 1x промышленность 50%; `SHL_pow_max_efficiency` +0.02.
- `SHL_h_golden_gate_festival` (2): стабильность +5%, `SHL_campaign_golden_gates_open` открыта без фокуса кварталов.
- `SHL_h_tenth_house_seat` (4, финал устройства): требует `SHL_conclave_of_ten`;
  дух `SHL_conclave_of_ten_spirit` (+0.10 PP, +3% эффективности, -2% стабильности), суперсобытие позже.

Хозяйство:
- `SHL_h_cargo_insurance` (3): разблокировка `SHL_cargo_insurance`.
- `SHL_h_house_credit` (3): разблокировка `SHL_house_credit`.
- `SHL_h_export_houses` (3): экспортные контракты (`SHL_export_contract`) дают аванс 90 вместо 60.
- `SHL_h_veyr_harbour_share` (4): требует `SHL_veyr_partnership` и партнёрства; +10 конвоев, GLP opinion +20, `SHL_pow_trade_opinion` +0.1.
- `SHL_h_rail_to_sea` (4) <-> `SHL_h_rail_to_qanats` (4): +1 инфраструктура в 292 и 296 либо в 287 и 289 (проверка места).
- `SHL_h_bank_of_houses` (4): казна +200, `SHL_treasury_capacity_bonus` +0.05.

Консолидация (существующие `SHL_south_debt_network` -> `SHL_south_trade_protectorates` -> `SHL_south_great_road` -> `SHL_south_oil_for_furnaces`):
- `SHL_h_debt_term` (2) после debt_network: запускает `SHL_cons_debt_term`.
- `SHL_h_kerdan_trading_house` (3): GLP предложение подчинения без войны при `SHL_veyr_partner`; иначе bypass.
- `SHL_h_road_stations` (3) после great_road: при победе над KDR +1 инфраструктура 234/240 или продажа станций за 150 казны (решение `SHL_sell_stations` - в контракт добавить как нац. решение, 1 раз).
- Убрать `ADISCORD_south_nam_story_clear` из `available` всех трёх цепных фокусов; оставить на `SHL_south_oil_for_furnaces`.

Война (общий фронт + финал `SHL_south_oil_for_furnaces`):
- `SHL_h_hired_contracts` (2): наёмные контракты - `SHL_hire_desert_guard` без лимита на время войны.
- `SHL_h_buy_garrisons` (3): -300 казны, +15% сопротивление... заменить на материальное: 2 дружины `SHL_create_levy` у столицы.

После войны (6): `SHL_h_concession_of_svetlogorye` (3): интеграция сателлита выкупом (`SHL_annex_integration_houses`), `SHL_h_southern_exchange` (4) <-> `SHL_h_southern_bank` (4): +2 гражданские фабрики в 699 против казна +400 и `SHL_treasury_capacity_bonus` +0.10; `SHL_h_veyr_junior_partner` (3): GLP остаётся сателлитом - opinion +30; `SHL_h_crown_of_trade` (5): дух победы курса; `SHL_h_ten_crests_forever` (2): BOP -0.10.

### 2. Открытый Конклав - `SHL_cities_focus`

Устройство (корень `SHL_council_of_cities`):
- `SHL_c_council_delegates` (3) <-> `SHL_c_shift_assembly` (3): делегаты от городов (BOP +0.10, стабильность +3%) против собрания смен (BOP +0.20, недовольство -10, `SHL_city_support` +10).
- `SHL_c_regular_elections` (4): разблокировка `SHL_council_election`.
- `SHL_c_quarter_militia` (3) <-> `SHL_c_compact_army` (3): дружины (`SHL_raise_paid_levies_2`, -6000 людей не списывать - цена внутри эффекта) против договорной армии (`add_tech_bonus` сухопутная доктрина 1x50%, `SHL_pow_army_org` +0.05).
- `SHL_c_registry_of_all` (3): снимает `SHL_unregistered_quarters` если есть; `SHL_city_support` +10.
- `SHL_c_open_ledger` (3): казначейская палата - `SHL_pow_political_power_gain` +0.05, коррупционные кризисы `shl_crisis.4/.5` отключены (флаг `SHL_open_ledger`).
- `SHL_c_mariam_cabinet` (2): Мариам Арбин назначает кабинет - событие `.123` вариант уже вызван; +50 PP.
- `SHL_c_charter_of_cities` (4, финал): дух `SHL_southern_compact_spirit` (+5% стабильности, -0.05 PP, +2% людские).

Хозяйство:
- `SHL_c_furnace_schools` (3): `SHL_furnace_school`.
- `SHL_c_quarter_hospitals` (3): `SHL_quarter_hospital`.
- `SHL_c_civic_orders_plus` (3): `SHL_civic_order` депозит 90 вместо 120 (цена уже переменная `SHL_civic_price`).
- `SHL_c_water_works` (4) <-> `SHL_c_harbour_works` (4): скважины `SHL_artesian_wells` дешевле на 50 либо гавань `SHL_harbour_project` дешевле на 50 (переменные цен ввести в контракт).
- `SHL_c_common_rail` (4): +1 инфраструктура 290 и 293.
- `SHL_c_cooperative_bank` (3): казна +150, `SHL_treasury_capacity_bonus` +0.05.

Консолидация (существующие `SHL_south_wells_charters` -> `SHL_south_compact_staff` -> `SHL_south_free_road` -> `SHL_south_war_of_charters`):
- `SHL_c_charter_round` (2): `SHL_cons_charter_round`.
- `SHL_c_cistern_charter` (3): `SHL_offer_cistern_charter` открыт до войны с Мазаром если Мазар не враг.
- `SHL_c_compact_court` (3): члены договора - opinion +20, `SHL_pow_stability_factor` +0.03.
- Убрать `nam_story_clear` кроме финала.

Война: `SHL_c_charters_for_occupied` (2): дух `SHL_charter_occupation` (-20% сопротивления) на время войны; `SHL_c_compact_volunteers` (3): `SHL_create_levy` x2.

После войны: `SHL_c_svetlogorye_charter` (3): интеграция по согласию (`SHL_annex_integration_cities`); `SHL_c_southern_council` (4) <-> `SHL_c_southern_commons` (4): +1 слот исследований против +3 инфраструктуры в трёх районах; `SHL_c_compact_assembly` (3): BOP +0.10; `SHL_c_treaty_of_the_south` (5): дух победы; `SHL_c_open_seats` (2): стабильность +5%.

### 3. Дирекция Нура - `SHL_directorate_focus`

Устройство (корень `SHL_war_directorate`):
- `SHL_d_state_furnaces_law` (3) <-> `SHL_d_concessions_law` (3): все печи владелец 2 (уже) и `SHL_pow_efficiency_gain` +0.04 против разблокировки `SHL_state_concession` и BOP -0.05.
- `SHL_d_military_directorate` (3) <-> `SHL_d_industrial_directorate` (3): +1 военный завод в 294 и `SHL_pow_arms_speed` +0.05 против +1 гражданской фабрики в 699 и `SHL_pow_infrastructure_speed` +0.1.
- `SHL_d_darban_engineers` (3): Рауф Дарбан - `add_tech_bonus` 2x промышленность 30%.
- `SHL_d_directorate_courts` (3): аресты гербов доступны (уже у дирекции), недовольство +5, давление -10.
- `SHL_d_quotas_law` (4): `SHL_mobilisation_quota`.
- `SHL_d_nur_director` (2): +50 PP, стабильность +3%.
- `SHL_d_iron_charter` (4, финал): дух `SHL_iron_directorate_spirit` (+10% поддержки войны, +5% орг., -5% стабильности).

Хозяйство: `SHL_d_directorate_railway` (3): `SHL_directorate_railway`; `SHL_d_arsenal_orders_plus` (3): `SHL_arsenal_price` 90; `SHL_d_fuel_depots` (3): +2000 топлива, `SHL_pow_max_dig_in`? нет - `supply_consumption` через дух `SHL_prepared_columns`; `SHL_d_cannon_works` (4) <-> `SHL_d_truck_works` (4): артиллерия 100 в запас против грузовики 200; `SHL_d_state_bank` (3): казна +200; `SHL_d_evacuation_plan` (3): `SHL_industrial_evacuation` без фокуса обороны (bypass если есть).

Консолидация (существующие `SHL_south_water_and_sea` -> `SHL_south_last_ration` -> `SHL_south_iron_march` -> `SHL_south_last_pour`): `SHL_d_ultimatum_term` (2): `SHL_cons_ultimatum`; `SHL_d_occupation_administration` (3): дух `SHL_general_governorate` (-10% сопротивления, +0.05 compliance); `SHL_d_march_logistics` (3): `SHL_forge_campaign_convoy` депозит 90. Убрать `nam_story_clear` кроме финала.

Война: `SHL_d_war_orders_all` (2): `SHL_war_orders` для всех печей; `SHL_d_guard_to_front` (3): `SHL_raise_furnace_guard` x2 без лимита.

После войны: `SHL_d_general_governorate` (3): интеграция с сопротивлением; `SHL_d_iron_south_rail` (4) <-> `SHL_d_iron_south_garrisons` (4): инфраструктура против гарнизонных шаблонов (дух -30% подавления); `SHL_d_directorate_eternal` (3): BOP 0 (set через shift к равновесию не нужен - стабильность +5%); `SHL_d_iron_crown` (5): дух победы; `SHL_d_nur_legacy` (2): +100 PP.

### 4. Регентство - `SHL_regency_focus`

Устройство (корень `SHL_regency_council`):
- `SHL_r_old_registry` (3) <-> `SHL_r_new_registry` (3): старый реестр - семь гербов, BOP -0.10, давление -10; новый - дома с работающей печью, `SHL_house_votes` пересчёт, стабильность +3%.
- `SHL_r_private_armies_charter` (3) <-> `SHL_r_regent_guard` (3): `SHL_raise_paid_levies_3` против `SHL_regent_guard`.
- `SHL_r_debt_courts` (3): `SHL_debt_tribunal`.
- `SHL_r_safir_cabinet` (2): +50 PP.
- `SHL_r_crest_press` (3): `SHL_pow_stability_factor` +0.03, недовольство +5.
- `SHL_r_hereditary_seats_restored` (4): дух `SHL_hereditary_seats` возвращён (если нет) с +0.10 PP.
- `SHL_r_regency_charter` (4, финал): дух `SHL_hereditary_republic_spirit`.

Хозяйство: `SHL_r_sell_concessions` (3): `SHL_sell_concessions`; `SHL_r_pledge_plus` (3): `SHL_pledge_price` 150; `SHL_r_house_mines` (4) <-> `SHL_r_house_rails` (4): +ресурс в 291 (`add_resource` сталь 6) против +1 инфраструктуры 288/295; `SHL_r_crest_bank` (3): казна +250, долг +200; `SHL_r_tolls` (3): `SHL_pow_consumer_goods` -0.02.

Консолидация (существующие `SHL_south_throne_and_crests` -> `SHL_south_toll_debtors` -> `SHL_south_veyr_debt` -> `SHL_south_war_of_arms`): `SHL_r_toll_term` (2): `SHL_cons_toll_term`; `SHL_r_kadir_marriage` (3): KDR opinion +40, если союз - +1 конвой x10; `SHL_r_fief_promises` (3): дух `SHL_promised_fiefs` раньше войны (давление +10 после).

Война: `SHL_r_hire_armies` (2): `SHL_hire_desert_guard` без лимита; `SHL_r_sell_future` (3): `SHL_sell_concessions` без кулдауна на время войны.

После войны: `SHL_r_fiefs_of_the_south` (3): интеграция ленами; `SHL_r_debt_empire` (4) <-> `SHL_r_crest_empire` (4): казна +500/долг +300 против BOP -0.20 и стабильность +5%; `SHL_r_kadir_junior` (3): KDR сателлит остаётся; `SHL_r_crown_of_crests` (5): дух победы; `SHL_r_regent_forever` (2): +100 PP.

### 5. Коммуна огня - `SHL_commune_focus`

Устройство (корень `SHL_shift_councils`):
- `SHL_k_rotating_smelting` (3) <-> `SHL_k_furnaces_to_workers_law` (3): общая плавка по очереди (все печи владелец 1, `SHL_pow_efficiency_gain` +0.03) против печей рабочим (существующий `SHL_furnaces_to_workers` остаётся корнем пары; недовольство -10).
- `SHL_k_delegates` (3) <-> `SHL_k_standing_council` (3): делегаты (BOP +0.10, стабильность +3%) против постоянного совета с дежурным мастером (Салима Дарзи - `promote_character` как лидер anarchism вместо коллективного; +0.10 PP).
- `SHL_k_shift_school` (3): `SHL_shift_school`.
- `SHL_k_no_crests` (3): давление 0 навсегда (флаг `SHL_no_crests`, `SHL_update_tensions` пропускает давление), BOP +0.10.
- `SHL_k_common_treasury` (3): казна +100, `SHL_treasury_capacity_bonus` +0.05.
- `SHL_k_commune_charter` (4, финал): дух `SHL_commune_of_fire_spirit` (+5% стабильности, +5% призыва, -0.05 PP).

Хозяйство: `SHL_k_brotherly_supply` (3): `SHL_brotherly_supply`; `SHL_k_cauldron_plus` (3): `SHL_common_cauldron` ремонт 40 вместо 30; `SHL_k_workers_rail` (4) <-> `SHL_k_workers_wells` (4): инфраструктура 293/287 против `SHL_artesian_wells` бесплатно один раз; `SHL_k_arms_for_shifts` (3): +2700 винтовок.

Консолидация (существующие `SHL_south_councils_abroad` -> `SHL_south_oil_underground` -> `SHL_south_oil_uprising`): `SHL_k_councils_term` (2): `SHL_cons_councils`; `SHL_k_strike_support` (3): `SHL_strike_support`; `SHL_k_weber_contact` (3): `ADISCORD_south_underground_armed` готовится раньше - -1500 винтовок, флаг. Убрать `nam_story_clear` кроме финала.

Война: `SHL_k_strikes_on_fields` (2): `SHL_south_raid_oil` без PP; `SHL_k_shift_brigades` (3): `SHL_create_levy` x2.

После войны: `SHL_k_union_of_councils` (3): слияние советов; `SHL_k_oil_commune` (4) <-> `SHL_k_furnace_commune` (4): +2 нефтедобычи в 67 против +2 гражданские фабрики 699; `SHL_k_no_more_crests` (3): BOP +0.20; `SHL_k_fire_of_the_south` (5): дух победы; `SHL_k_duty_master` (2): +100 PP.

## Порядок

1. Автор скрипта реализует контракт решений, миссий, эффектов и `.140`/`.76`
   с тестами в `test_adiscord_shl_furnaces.py` (новый класс `CourseProgrammeTests`).
2. Пять авторов деревьев пишут свои источники параллельно, ссылаясь на ID
   контракта, и фрагменты локализации.
3. Ведущий сливает локализацию, собирает деревья, обновляет AI-планы и тесты
   раскладки, прогоняет полный набор проверок.

## Итог этапа 3

Все пять деревьев и контракт решений реализованы; отступления от таблиц выше
зафиксированы в спеке ("Уточнения, принятые при реализации M3-M5"): цены
программ выводятся из завершённых фокусов, хозяйственный блок растёт от корня
курса, новости идут через `show_major`, миссии консолидации имеют реальную
цель. Фокусы `SHL_c_regular_elections`, `SHL_k_arms_for_shifts`,
`SHL_d_state_bank`, `SHL_d_cannon_works`, `SHL_d_truck_works` получили
усиленные награды по редакторскому порогу `validate_focus_rewards`.
