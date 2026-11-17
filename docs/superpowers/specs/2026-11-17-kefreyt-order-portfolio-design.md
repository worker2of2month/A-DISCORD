# Кефрейт: портфель заказов и переход в "Мир без заказов"

Дополняет `2026-11-10-kefreyt-peace-reckoning-design.md` и
`2026-11-11-kefreyt-eastern-republics-design.md`. Если документы расходятся,
действует этот.

## Согласованные решения (2026-11-17)

- Ветки старого дерева, которые раньше сгорали при смене дерева, становятся
  общими (`shared_focus`). Компенсации вместо них нет.
- Кризис "Два счёта" требует одного фронта, а не обоих.
- Портфель заказов тает за 6 мирных месяцев.

## Принцип

- Провозглашение Содружества больше не даёт вечной премии. Оно открывает
  портфель заказов на полгода.
- Пока идёт война, заказы есть, но эта заморозка ограничена.
- Когда портфель пустеет, линии простаивают. Глава "Мир без заказов"
  наступает сама, на худших условиях.
- Игрок может войти раньше по графику и получить мягкий старт и деньги за
  закрытые накладные.
- Ни одна незавершённая ветка, которая снимает штрафы войны, при переходе
  не сгорает.
- Без провозглашения портфель не открывается и глава не наступает. Старое
  дерево в этом случае остаётся без простоя и без премии.

## Этап 1. Портфель заказов

### Состояние

Все переменные страновые, в скоупе VAL.

| Переменная | Диапазон | Смысл |
| --- | --- | --- |
| `VAL_order_portfolio` | 0..6 | месяцы заказов |
| `VAL_order_portfolio_idle` | 0..20 | очки простоя линий |
| `VAL_order_portfolio_frozen` | 0..6 | месяцы войны, в которые портфель не таял |
| `VAL_order_portfolio_extended` | 0..2 | месяцы, добавленные поставками на сторону |
| `VAL_order_portfolio_stability` | расчётная | `0.01 * portfolio` |
| `VAL_order_portfolio_income` | расчётная | `1.5 * portfolio` |
| `VAL_order_portfolio_output` | расчётная | `-0.004 * idle` |
| `VAL_order_portfolio_payout` | расчётная | `50 * portfolio`, выплата за досрочный вход |
| `VAL_side_order_buyers` | 0..5 | покупатели за кампанию; не сбрасывается |

- Префикс `VAL_order_portfolio_` выбран намеренно. Закрытие кризиса требует,
  чтобы не осталось переменных `VAL_peace_*`, кроме `VAL_peace_order_*`.
- Каждый `clamp_variable` указывает и `min`, и `max`.
- Флаг `VAL_order_portfolio_notice` ставится один раз: при первом
  уведомлении о пустом портфеле.

**Динамический модификатор `VAL_order_portfolio`.**

- Файл `ADISCORD_VAL_contract_dynamic_modifier.txt`, `enable = { tag = VAL }`.
- Поля:
  - `stability_factor = VAL_order_portfolio_stability`;
  - `ADISCORD_economy_weekly_income = VAL_order_portfolio_income`;
  - `industrial_capacity_factory = VAL_order_portfolio_output`.
- При открытии он даёт +6% стабильности и +9 дохода в неделю.

**Удаление `VAL_regional_settlement`.** Идея удаляется вместе с её
локализацией, и `VAL_Campaign_Secured` больше её не выдаёт. Взамен фокус
получает собственную постоянную материальную награду: 300 казны через
`ADISCORD_economy_receive_300` с существующей подсказкой казны и 10800
винтовок.

### Эффекты

Новая секция `# --- order_portfolio ---` в `ADISCORD_VAL_effects.txt`.

**`VAL_order_portfolio_open`.**

- Ставит portfolio 6, idle 0, frozen 0, extended 0 и вызывает refresh.
- Срабатывает один раз, при всех условиях:
  - нет переменной `VAL_order_portfolio`;
  - `has_focus_tree = VAL_focus`;
  - `VAL_nw_operational`.
- Единственный вызов стоит внутри `if` в `VAL_adopt_commonwealth`, после
  `set_country_flag = VAL_commonwealth_proclaimed`. `CouncilWorld` из
  `test_adiscord_val_council.py` требует `days` у каждого
  `add_dynamic_modifier`, а модификатор портфеля бессрочный, поэтому вызов
  входит в список исключений этого теста.
- Решение о провозглашении показывает `VAL_order_portfolio_open_tt`:
  +6% стабильности и +9 дохода в неделю на старте, затем -1 месяц в каждый
  мирный месяц и простой при пустом портфеле.
- Модификатор убывает, поэтому превью через пустую идею не подходит:
  валидатор принимает только аддитивные изменения. Отсюда custom tooltip.

**`VAL_order_portfolio_refresh`.**

- Пересчитывает четыре расчётные переменные.
- Добавляет модификатор, если его нет.
- Выполняет `force_update_dynamic_modifier` и `ADISCORD_economy_mark_dirty`.

**`VAL_order_portfolio_close`.**

- Снимает модификатор под `has_dynamic_modifier`.
- Очищает все переменные `VAL_order_portfolio_*` и снимает флаг уведомления.
  `VAL_side_order_buyers` не трогает.
- Выполняет mark_dirty.
- Вызывается из `VAL_peace_begin` (после чтения idle) и из
  `VAL_enter_stelander_defeat`. Снятый флаг уведомления останавливает цикл
  `val_rework.223`.

**`VAL_order_portfolio_monthly`.**

- Вызывается из `on_monthly_VAL` до `VAL_peace_monthly`.
- Внешняя проверка: `has_variable VAL_order_portfolio` и
  `has_focus_tree = VAL_focus`.
- Шаги:
  1. Таяние.
     - Мир: при portfolio > 0 вычесть 1.
     - Война при frozen < 6: frozen +1, portfolio не меняется.
     - Война при frozen = 6: портфель тает как в мирное время.
  2. Простой. Если после шага 1 portfolio <= 1, войны нет и уведомления
     ещё не было, idle +5 (не выше 20). Первое начисление, когда idle был 0,
     отправляет `val_rework.221`. После уведомления простой не растёт, поэтому
     стартовая забастовка в `val_rework.222` совпадает с применённой.
  3. Вызывает refresh.
  4. Если portfolio = 0, флага уведомления нет и
     `VAL_order_portfolio_notice_ready = yes`: ставит флаг, отправляет
     `val_rework.222` (видимое, один раз за кампанию) и `val_rework.223`
     через 30 дней.
- `val_rework.221` и `val_rework.222` отправляются без задержки и имеют
  `fire_only_once = yes` поверх собственных проверок.

**`VAL_order_portfolio_settle_operations`.**

- Вызывается из `VAL_peace_begin` при любом входе.
- Для каждого префикса `nod/bjk/nc/stl` с
  `VAL_<op>_op_moment_passed = no` очищает подготовку:
  - переменную `VAL_<op>_op_readiness`;
  - переменную `VAL_<op>_op_profile` (у NOD - `VAL_nod_op_axis`);
  - флаги `VAL_<op>_op_noticed` и `VAL_<op>_op_deception_ready`.
- Эти операции запускаются фокусами старого дерева, поэтому после смены
  дерева подготовка теряет смысл. `VAL_bjk_op_can_prepare` и
  `VAL_nc_op_can_prepare` требуют `has_focus_tree = VAL_focus`: идущие
  подготовительные решения отменяются по своему `cancel_trigger` с возвратом
  оплаты, и готовность больше не растёт. NOD и STL к провозглашению уже
  закрыты целями кампании.
- ERT и IRT запускаются решениями `VAL_operation_expand_southern_bridgehead`
  и `VAL_operation_eastern_security_belt`, которые остаются доступными в новом
  дереве, поэтому их подготовка сохраняется.
- Депозит дорог NOD (`VAL_nod_op_roads_deposit`) при входе не возвращается:
  `remove_effect` того решения строит дороги без проверки депозита, и возврат
  сделал бы их бесплатными.
- Ответ `val_rework.222` и фокус `VAL_Peace_Without_Orders` предупреждают
  об этой потере подсказкой `VAL_peace_operations_lost_tt` по триггеру
  `VAL_order_portfolio_has_lost_operations` (готовность выше 0 у одной из
  четырёх операций с `moment_passed = no`).

### Триггеры

Секция `# --- order_portfolio ---` в `ADISCORD_VAL_rework_triggers.txt`.

**`VAL_order_portfolio_notice_ready`.** Все условия, кроме первых трёх,
ограничены по времени:

- `tag = VAL`, `VAL_nw_operational = yes`, `has_focus_tree = VAL_focus`;
- `has_country_flag = VAL_commonwealth_proclaimed`;
- `has_war = no`;
- нет `VAL_peace_order_deposit`;
- нет `VAL_command_consolidation_kind`, нет
  `VAL_stelander_alliance_offer_pending`;
- `ADISCORD_nam_resource_war_active = no`, нет глобального флага
  `ADISCORD_nam_resource_war_scheduled`;
**`VAL_order_portfolio_entry_ready`.** `VAL_order_portfolio_notice_ready`
и одно из двух:

  - `NOT = { focus_progress = { focus = VAL_Peace_Without_Orders progress > 0 } }`;
  - `has_country_flag = { flag = VAL_order_portfolio_notice days > 60 }`.

  Начатый фокус задерживает переход не дольше 60 дней после уведомления.

**`VAL_order_portfolio_auto_entry_due`.** Все условия:

- `has_variable = VAL_order_portfolio`;
- portfolio = 0;
- флаг уведомления;
- `VAL_order_portfolio_entry_ready = yes`.

**`VAL_side_order_available`.** `VAL_side_order_buyers` < 5.

Пять проверок `has_focus_tree = VAL_focus` в
`ADISCORD_nam_resource_war_effects.txt` - это только обновление раскладки и
событие `.3`. Обязательств они не несут.

### Переход

**`VAL_nw_open_chapter`.**

- Перед загрузкой ставит временную переменную `VAL_peace_entry_voluntary`
  (1, если `has_completed_focus = VAL_Peace_Without_Orders`, иначе 0).
- `has_completed_focus = VAL_Peace_Without_Orders` в `limit` заменяется на
  `OR = { has_completed_focus = VAL_Peace_Without_Orders VAL_order_portfolio_auto_entry_due = yes }`.
- Остаётся один `load_focus_tree`.
- Внутри нет `clear_variable`, `clr_country_flag`, `remove_decision` и
  `remove_mission`. Вызов эффекта, который их содержит, допустим.

**`val_rework.223`** (скрытое).

- Если `VAL_order_portfolio_auto_entry_due = yes`, отправляет
  `val_rework.124`: его `immediate` открывает главу.
- Иначе, пока есть флаг уведомления и `has_focus_tree = VAL_focus`,
  отправляет себя же через 7 дней. Флаг не снимает, повторного видимого
  уведомления не будет.

**`VAL_peace_begin`.**

Порядок внутри ограниченного блока:

1. Читает idle во временную `VAL_peace_entry_idle`. Портфель после закрытия
   ничем не читается, поэтому его значение не сохраняется.
2. Вызывает `VAL_peace_write_off_tails`. Тот записывает число списанных
   хвостов во временную `VAL_peace_tails_written_off`.
3. Вызывает `VAL_order_portfolio_settle_operations`.
4. Вызывает `VAL_order_portfolio_close`.
5. Задаёт баланс, забастовку и долг по виду входа (таблица ниже).

| | Добровольный | Автоматический |
| --- | --- | --- |
| Забастовка | 10 + idle + 10 x хвосты | 25 + idle + 10 x хвосты |
| Долг ротам | 0 | 1, при совете 0 |
| Баланс | 0, при совете 0.15 | 0.05, при совете 0.15 |

- Стартовая забастовка ограничена 49, чтобы порог 50 не срабатывал в первый
  день. При автоматическом входе с двумя хвостами и простоем потолок
  поглощает часть цены хвостов, и это сделано сознательно.
- Совет при автоматическом входе получает только надбавку к забастовке. Его
  база 0.15 при еженедельном дрейфе от долга иначе закрыла бы трон
  (`<= 0.20`) за неделю.
- `VAL_peace_orders` стартует с `VAL_side_order_buyers`, но не больше 5.
- `VAL_peace_months` стартует с 0.

**`VAL_Peace_Without_Orders`.**

- Позиция x22 y18, предпосылки прежние, `has_war = no`.
- Награда "Демобилизация по графику", по порядку:
  - подсказки `VAL_next_chapter_tt` и `VAL_peace_scheduled_demobilisation_tt`
    с суммой
    `§Y[?VAL_order_portfolio_payout]§! £ADISCORD_economy_treasury_texticon`
    и мягким стартом;
  - `effect_tooltip = { VAL_peace_write_off_tails = yes }`;
  - условная подсказка цены хвостов: `if`/`else_if` по тем же двум фактам,
    что и эффект списания, включая `has_variable = VAL_contract_reputation_level`.
    Варианты 0, 1 и 2 хвоста, у каждого свой ключ с фиксированным числом:
    `VAL_peace_tails_strike_1_tt`, `VAL_peace_tails_strike_2_tt`;
  - `VAL_peace_operations_lost_tt`, если есть подготовленная операция;
  - `VAL_peace_without_orders_crisis_tt` с перечнем переносимых общих веток;
  - в `hidden_effect`: выплата `VAL_order_portfolio_payout` под
    `has_variable = VAL_order_portfolio_payout` в казну и в
    `ADISCORD_economy_current_month_action_income`, mark_dirty, затем
    `val_rework.124`. Выплата идёт до события, потому что его `immediate`
    закрывает портфель;
  - событие только `val_rework.124`, `remove_ideas` нет.
- Тот же набор подсказок без выплаты стоит в ответе `val_rework.222`.
  `VAL_order_portfolio_auto_entry_tt` поясняет, что дерево загрузится через
  30 дней и что переносится: флот, экономика и рекультивация.

**События.**

- `val_rework.221` "Первые простои" и `val_rework.222` "Последняя накладная"
  видимые; описания только художественные.
- Номера `val_rework.221-223`, `val_peace.14` и `val_peace.15` вносятся в
  `tools/data/adiscord_event_ids.json`.

### Списание хвостов

`VAL_peace_write_off_tails` состоит из двух блоков, и каждый срабатывает
только при наличии своего хвоста:

- **Металлический голод.** Если есть идея `VAL_vorkerland_metal_shortage`:
  `remove_ideas`, хвост +1.
  - `VAL_assert_vorkerland_metal_shortage` не возвращает идею при
    `has_focus_tree = VAL_new_world_focus`.
- **Контрактная репутация.** Если переменная `VAL_contract_reputation_level`
  есть и не выше 1: уровень ставится в 2, вызывается
  `VAL_refresh_contract_reputation`, хвост +1.
  - `VAL_Quarterly_Contract_Norm` не обязательный предок
    `VAL_Contracts_Outlive_Kings`, поэтому переменной может не быть; без
    проверки страна без системы репутации получила бы идею и цену хвоста.
  - Сами применения репутации скрыты, поэтому блок явно показывает
    `effect_tooltip = { add_ideas = VAL_contract_reputation_2 }`.

Остальные штрафы не списываются:

- **Ступени восстановления.** `VAL_peace_complete_recovery` сохраняет
  порядок: флаг, затем вызов.
  - Внутри проверки `VAL_vorkerland_contracts_disrupted`: если ступеней
    меньше 8, ставит 8. Затем на верхнем уровне один раз вызывает
    `VAL_advance_economic_recovery = yes`, который сам проверяет тот же флаг.
  - Подсказка `VAL_peace_recovery_complete_tt` показывается только при
    `VAL_vorkerland_contracts_disrupted` и `VAL_economic_recovery_steps < 9`.
    Она стоит в ответах `val_peace.40` a, b, c и e.
  - Новые награды не добавляют вызовов `VAL_advance_economic_recovery`:
    тест считает 8 вызовов в главном дереве и 2 в новом.
- **Репутация арсенала.** Каждая поставка на сторону поднимает ступень на 1,
  пока `VAL_arsenal_reputation_stage < 3`. Подсказка показывается только при
  этом условии.
- **Жалованье рот** хвоста не оставляет. Обязательные реформы, реформа
  завершения кризиса и общая экономическая ветка снимают надбавку
  полностью. Повтора реформы в корнях режимов нет.
- **"Земля пепла" и экономика** становятся общими ветками (см. ниже).

### Заказ на стороне

**Решение `VAL_side_order`.**

- Категория `VAL_contract_management`. Её `visible` получает ещё одну ветвь
  в OR: `AND = { has_variable = VAL_order_portfolio has_focus_tree = VAL_focus }`.
- `visible`: `has_variable VAL_order_portfolio`, `has_focus_tree = VAL_focus`.
- `available` (последние три условия - локализованные
  `custom_trigger_tooltip`):
  - `VAL_nw_operational`;
  - `VAL_side_order_available`;
  - нет `VAL_peace_order_deposit`;
  - нет флага уведомления.
- Цена и срок:
  - `cost = 0`, `custom_cost_text = VAL_peace_foreign_order_cost`,
    `custom_cost_trigger = { VAL_peace_order_payable = yes }`. Цена та же, что
    у кризисного заказа, поэтому решение использует его ключ цены и его
    существующие варианты `_blocked` и `_tooltip`;
  - `days_remove = 30`.
- При снятии показывает результат, продление портфеля, пока extended < 2,
  и превью репутации арсенала, пока ступень < 3.
- Эффекты: `VAL_peace_begin_foreign_order`, а при снятии
  `VAL_peace_deliver_foreign_order`.
- `ai_will_do`: base 0.

**Решение `VAL_peace_foreign_order`.**

- `visible`: `OR = { VAL_peace_crisis_active = yes AND = { has_variable = VAL_peace_order_deposit has_focus_tree = VAL_new_world_focus } }`.
- `VAL_peace_two_bills` больше не требуется.
- `available` добавляет `VAL_side_order_available`.
- При снятии показывает то же условное превью репутации арсенала, что и
  `VAL_side_order`.
- `ai_will_do`: base 0, пока действует `VAL_nw_khan_threat`, иначе base 4.
- `visible` категории `VAL_peace_payroll_category` использует то же выражение.

**`VAL_peace_deliver_foreign_order`.**

- Всегда:
  - +200 казны;
  - `VAL_side_order_buyers +1`, не выше 5;
  - `VAL_restore_arsenal_reputation`, если ступень < 3.
- Во время кризиса: прежний результат.
- Вне кризиса, если есть `VAL_order_portfolio`, extended < 2 и portfolio < 6:
  portfolio +1, extended +1, refresh.
- Поставка, отправленная до перехода и пришедшая в кризис, засчитывается
  как кризисная. Автоматический вход ждёт её прихода.

### Общие ветки

**Источник.** Фокусы остаются в `focus_trees/VAL/main/focuses.txt`. Файл
`focus_trees/VAL/new_world/focuses.txt` ссылается на корни рядом с флотом:

```
shared_focus = VAL_econ_development_fund
shared_focus = VAL_reclamation_survey
```

**Смещения.** Каждый фокус обеих веток получает
`offset = { x = <dx> y = <dy> trigger = { has_focus_tree = VAL_new_world_focus } }`.
Советских смещений и `relative_position_id` у этих фокусов нет. Новых
`allow_branch` нет.

| Ветка | Фокусов | В VAL_focus | Смещение | В новом дереве |
| --- | --- | --- | --- | --- |
| Экономика `VAL_econ_*` | 11 | x 8-16, y 9-14 | x +44, y -9 | x 52-60, y 0-5 |
| Рекультивация и "Урожай пепла" | 11 | x 0-8, y 2-7 | x +62, y -2 | x 62-70, y 0-5 |

Флот остаётся на x 38-42, y 0-3. Корни зависят от `VAL_Industrial_Mobilization_Plan`
и `VAL_Factories_Like_Cathedrals`, а оба они всегда выполнены до
провозглашения; прежний `allow_branch` корня экономики сохраняется.

В `VAL_new_world_focus` 27 общих фокусов (5 флота, 11 экономики, 11
рекультивации; другие потомки не подтягиваются) и 89 собственных. Клетки не
пересекаются ни с Советом, ни без него; собственные фокусы занимают x 0-48.

## Этап 2. Кризис с выбором

### Один фронт

- `VAL_peace_ash_shifts` (смены) и `VAL_peace_captains_bill` (роты)
  взаимоисключающие; оба стоят на y1.
- `VAL_peace_two_bills` требует:
  - `prerequisite = { focus = VAL_peace_silent_lines }`;
  - `prerequisite = { focus = VAL_peace_tishin_list focus = VAL_peace_kilnet }`.
- `VAL_peace_silent_lines` получает `bypass = { VAL_peace_regime_chosen = yes }`.
- Ствол до развязки: 26 недель через смены, 25 через роты.

### Запущенный фронт

| | Выбраны смены | Выбраны роты |
| --- | --- | --- |
| Корень отправляет | `val_peace.14` "Роты без жалованья" | `val_peace.15` "Линии без смен" |
| Обострение в `VAL_peace_monthly` | ещё +1 к долгу ротам | ещё +3 к забастовке |
| Обострение стоит, пока нет флага | `VAL_peace_companies_settled` | `VAL_peace_shifts_settled` |
| Решение | `VAL_peace_settle_companies` | `VAL_peace_settle_shifts` |
| Цена | 40 политвласти и 250 казны | 200 казны |
| Результат | долг 0, баланс -0.10 | забастовка -20 |

Корень показывает обострение подсказкой (`VAL_peace_companies_unpaid_tt` у
смен, `VAL_peace_shifts_unmanned_tt` у рот) рядом с
`unlock_decision_tooltip` своего решения и отправляет событие скрыто, без
задержки. Событие тоже показывает обострение и открытие решения.

Оба решения:

- лежат в `VAL_peace_payroll_category`;
- `visible`: выполнен корень другого фронта и кризис идёт;
- `cost = 0`, `custom_cost_text`,
  `custom_cost_trigger = { VAL_peace_settle_<x>_payable = yes }` (новые
  триггеры), варианты `_blocked` и `_tooltip`;
- `complete_effect` вызывает `VAL_peace_settle_<x>_start`: оплата
  списывается один раз и ставится флаг-квитанция `VAL_peace_settle_<x>_paid`;
- `days_remove = 45`. `remove_effect` всегда вызывает
  `VAL_peace_settle_<x>_finish`: в кризисе он применяет результат и ставит
  флаг `_settled`, иначе возвращает оплату. Подсказки результата показаны
  только при `VAL_peace_crisis_active = yes`;
- скрытый `cancel_trigger = { VAL_peace_crisis_active = no }`. `cancel_effect`
  вызывает `VAL_peace_settle_<x>_refund`: казна и политвласть возвращаются
  один раз по квитанции;
- `fire_only_once = yes`;
- ИИ берёт решение запущенного фронта при первой возможности (base 100).

Флаги `_settled` снимаются в `VAL_peace_close_crisis`. Квитанция снимается
только результатом или возвратом, поэтому отмена после закрытия кризиса
тоже возвращает оплату.

### Выплата пропущенного

`VAL_peace_settle_open_bills`:

- не платит за фокусы фронта, если выполнен корень другого фронта;
- если не выполнен ни один корень, платит за общий ствол и фронт смен;
- выплачивает постоянную часть новых наград `tishin_list`, `kilnet`,
  `archive` и `two_bills`, если фокус не выполнен;
- не платит 25 очков командования `captains_bill`: фронт рот оплачивается
  только при выполненном корне, поэтому этот долг не может возникнуть.

### Нарастание штрафов

- `VAL_peace_months` растёт в `VAL_peace_monthly` и очищается при закрытии
  кризиса.
- `VAL_peace_refresh` берёт базовые значения по месяцу кризиса:

  | Месяц кризиса | Политвласть | Военный доход |
  | --- | --- | --- |
  | 0 (первые 1-30 дней) | -0.05 | -0.09 |
  | 1 | -0.10 | -0.17 |
  | 2 и далее, или нет переменной | -0.15 | -0.25 |

- К военному доходу прибавляется `+0.05 x orders`, затем
  `clamp_variable = { var = VAL_peace_military_income min = -0.25 max = 0 }`.

### Материальные награды

Каждую награду задаёт эффект в `ADISCORD_VAL_effects.txt`. Фокус вызывает его
напрямую, чтобы вывод был нативным, а `VAL_peace_settle_open_bills`
вызывает его, если фокус не выполнен. Событие остаётся у каждого фокуса.

| Фокус | Эффект | Награда |
| --- | --- | --- |
| `VAL_peace_tishin_list` | `VAL_peace_reward_tishin_list` | +1 гражданский завод в коренной области, предпочтительно state 48 (при нехватке места - слот), забастовка -5 только пока идёт кризис |
| `VAL_peace_kilnet` | `VAL_peace_reward_kilnet` | +6000 живой силы, +15 опыта армии; заменяет прежние 2500 в выплате |
| `VAL_peace_archive` | `VAL_peace_reward_archive` | `add_tech_bonus` industry 0.75, 1 использование, +50 политвласти |
| `VAL_peace_two_bills` | `VAL_peace_reward_two_bills` | `ADISCORD_economy_receive_300` с подсказкой казны |

### ИИ

- ИИ идёт через роты: `captains_bill`, `registry_audit`,
  `loyal_battalions`, `kilnet`. Это единственный путь, на котором есть
  смягчение мятежа.
- `VAL_peace_ash_shifts`: base 5, `VAL_peace_captains_bill`: base 10. ИИ
  выбирает `VAL_peace_settle_shifts`.
- План `VAL_new_world_plan` не называет фокусы фронта смен. После полос
  режимов он берёт `VAL_east_arsenal` и `VAL_east_final`, затем общие ветки и
  реакторный пояс, чтобы срок состязания не уходил на боковые ветки. В
  исключающих парах общих веток он называет `VAL_econ_export_finance` и
  `VAL_Field_Surgeons`.

## Этап 3. Режимы и боковые ветки

Этап выполняет один исполнитель. Он владеет всеми файлами этапа, поэтому
цифры не нужно согласовывать между владельцами.

**Режимы.**

- Два фокуса в каждом из режимов трона, кабинета и хартии и один у
  капитанов вместо процента в `VAL_peace_order` открывают программу:
  решение с ценой, сроком и материальным результатом.
- Такой фокус теряет добавку `VAL_peace_order_*`, её превью и
  `VAL_peace_order_update`. Взамен он получает `unlock_decision_tooltip`,
  короткую подсказку `<decision>_unlock_tt`, разовую нативную награду и
  фильтр решений. Фокусы, у которых уже была материальная награда, её
  сохраняют. Клетки, полосы и исключающие пары не меняются.
- Превью `VAL_nw_arbitration`, `VAL_nw_army_guarantee`,
  `VAL_cabinet_bread_delta`, `VAL_charter_staff_delta` и
  `VAL_captains_shares_delta` закреплены тестом. Поэтому кабинет, хартия и
  капитаны переводят не `open_estimates`, `highland_bread` и
  `single_staff`, а соседние фокусы. `open_estimates` к тому же стоит до
  "Гражданского комбината", который открывает `VAL_peace_order_category`.
- Что разбирает каждый режим (цена - политвласть и казна):

  | Режим | Наследие войны | Фокус и разовая награда | Программа | Цена, срок, повторы | Результат |
  | --- | --- | --- | --- | --- | --- |
  | Трон | заводы | `VAL_throne_memorial`, +5% поддержки войны | `VAL_throne_memorial_combine` | 75 + 450, 120 дней, один раз | state 48: +2 слота, военный и гражданский завод |
  | Трон | заводы | `VAL_throne_arsenal_monopoly`, бонус стрелкового оружия сохраняется, +10% военного дохода снят | `VAL_throne_crown_acceptance` | 25 + 200, 45 дней, до 3 | 150 артиллерии, 150 вспомогательного снаряжения |
  | Кабинет | поселения | `VAL_cabinet_not_for_sale`, +5% стабильности | `VAL_cabinet_settlement_services` | 200, 60 дней, до 3 | +1 инфраструктура в случайной коренной области ниже 5, 3000 живой силы |
  | Кабинет | поселения | `VAL_cabinet_reconstruction_loans`, 300 казны сохраняются | `VAL_cabinet_settlement_loans` | 300, 120 дней, до 2 | 420 казны, 2000 живой силы |
  | Хартия | гарнизоны республик | `VAL_charter_silence`, +30 опыта армии | `VAL_charter_recall_garrisons` | 50 + 150, 60 дней, один раз | 6000 живой силы, 5400 винтовок, 15 опыта армии |
  | Хартия | гарнизоны республик | `VAL_charter_veteran_reserve`, 8000 живой силы сохраняются | `VAL_charter_frontier_posts` | 25 + 200, 60 дней, до 3 | 2 уровня сухопутных укреплений на граничных провинциях пограничной коренной области, +1 инфраструктура ниже 5 |
  | Капитаны | ротные рынки | `VAL_captains_officers_assembly`, 50 политвласти и +5% стабильности | `VAL_captains_company_exchange` | 25 + 250, 45 дней, до 3 | 5000 живой силы, 15 опыта армии |

- Шесть программ стоят в `VAL_peace_order_category`.
  `VAL_charter_recall_garrisons` стоит в `VAL_new_world_category`: "Молчание
  ради армии" предшествует `VAL_charter_mercenary_power`, который открывает
  `VAL_peace_order_category` для хартии.
- Каждая программа держит свой депозит (`VAL_throne_combine_deposit`,
  `VAL_throne_acceptance_deposit`, `VAL_cabinet_service_deposit`,
  `VAL_cabinet_loan_deposit`, `VAL_charter_recall_deposit`,
  `VAL_charter_post_deposit`, `VAL_captains_exchange_deposit`) с учётом
  движения казны, которого требует валидатор, проверяет обе валюты в
  `custom_cost_trigger`, списывает их один раз и возвращает при отмене.
  Результат, требующий площадки, проверяет её повторно
  (`VAL_cabinet_settlement_site`, `VAL_charter_frontier_post_site`) или
  возвращает оплату.
- Удалены превью, потерявшие потребителей: `VAL_throne_memorial_delta`,
  `VAL_throne_monopoly_delta`, `VAL_cabinet_not_for_sale_delta`,
  `VAL_cabinet_loans_delta`, `VAL_charter_silence_delta`,
  `VAL_charter_veterans_delta`, `VAL_captains_assembly_delta`. Остальные
  процентные фокусы не менялись, их превью равны применяемым значениям.
- В парах memorial/confession и silence/tribunal оба фокуса дают реальную
  награду.

**Реакторный пояс.**

- Бонус к исследованиям дают только `VAL_nw_archives` (электроника) и
  `VAL_nw_alloys` (промышленность).
- `VAL_nw_perimeter` даёт 300 казны (`ADISCORD_economy_receive_300` с
  подсказкой казны), `VAL_nw_foundries` - 150 артиллерии,
  `VAL_nw_dispatch` - 300 грузовиков (`motorized_equipment`): исключающая
  пара выбирает между орудиями и грузовиками. `VAL_nw_inventory` и
  `VAL_nw_restart` не менялись.
- `VAL_nw_generation` даёт +5% стабильности и открывает `VAL_nw_power_block`
  в `VAL_new_world_category` (после `VAL_nw_rebuild_roads`). Решение
  нацелено на области пояса 176, 177, 187, 188, 189, 192 и использует
  существующую очередь `VAL_nw_project_deposit` как вид 4: 50 политвласти и
  500 казны, 120 дней. Первая постройка на восстановленной площадке даёт +2
  слота и +2 гражданских завода и ставит флаг области
  `VAL_nw_power_block_built`; затем программа только заменяет одну
  утраченную линию при свободном слоте (`VAL_nw_power_block_needed`).
  Площадка проверяется повторно в `VAL_nw_finish_project`, иначе цена
  возвращается полностью; возврат сохраняет фиксированные 50 политвласти
  очереди.

**Требования к наградам.**

- Минимальная награда фокуса не ниже 75 политвласти, 4000 живой силы или
  600 казны в материальном эквиваленте.
- Программы проверяют место для зданий при выдаче.
- В описаниях нет механики.

**Сроки.**

Недели от загрузки нового дерева до `VAL_east_final`, по одному фокусу за
раз:

- ствол до `VAL_peace_night_of_registers`: 25 недель через роты, 26 через
  смены;
- полоса режима от корня до повода: престол 27, кабинет 28, хартия 27,
  капитаны 20;
- восток: вопрос 3 + миссии или сеть 4 + посты 4 + осколки или арсенал 4 +
  последняя война 3 = 18;
- обязательный итог: престол 70/71, кабинет 71/72, хартия 70/71, капитаны
  63/64.

Срок состязания 360 дней (51.4 недели) начинается с завершения
`VAL_east_question` (не раньше 28-29-й недели) либо сам через 4 месяца после
выбора режима, если вопрос ещё не взят. После вопроса остаётся не больше 42 недель обязательного пути
(престол, хартия), 43 (кабинет) или 35 (капитаны), то есть 9.4, 8.4 и 16.4
недели запаса. Последняя война открывается раньше ультиматума при любом
режиме.

Необязательные ветки: экономика около 42 недель, рекультивация около 25,
пояс 20, флот 15-21, республики около 7, Хан около 11, боковые фокусы
режимов 7-11. Они помещаются в 365-дневное окно кризиса (52 недели при
стволе 25-26, то есть 26-27 свободных недель) или до `VAL_east_question`,
но не после начала состязания. ИИ с текущим порядком плана выходит к
последней войне примерно на 70-83-й неделе при сроке на 84.4-й.

## Сроки до кризиса (худший случай)

От провозглашения до начала кризиса проходит:

- 6 месяцев портфеля;
- 2 месяца от поставок на сторону;
- до 6 месяцев заморозки войной;
- 30 дней уведомления;
- по 30 дней за каждую поставку в пути;
- остаток любой войны после конца заморозки;
- до 60 дней ожидания начатого фокуса.

Внутренние сроки кризиса (365 дней, 4 месяца до режима, 360 дней
состязания) отсчитываются от его начала.

### Выбор момента входа

Цифры по чистым значениям, без поставок и войны.

| Портфель при входе | Выплата | Стартовая забастовка (0 хвостов) | Доход с портфеля, накопленный до входа |
| --- | --- | --- | --- |
| 6 | 300 | 10 | 0 |
| 4 | 200 | 10 | около 72 |
| 2 | 100 | 10 | около 117 |
| 1 | 50 | 15 | около 124 |
| 0, вход сам | 0 | 25 + 10 = 35 | около 130 |

- В первые месяцы ожидание выгоднее примерно на 0-10 в месяц, что почти
  нейтрально.
- При портфеле 3 и ниже ожидание убыточно: падает выплата и растёт
  забастовка.

## Тесты, которые меняются

- `test_adiscord_val_new_world.py`:
  - `:947`: проверка `has_completed_focus` переходит внутрь `OR`;
  - число и уникальность клеток нового дерева. Добавить тест уникальности
    по `focus_layout_coordinates(..., "VAL_new_world_focus")` вместе с
    общими ветками;
  - группы исключающих фокусов (`:981`).
- `test_adiscord_val_peace_reckoning.py`:
  - константы refresh (`:289-303`), включая строки нарастания;
  - условия выплаты пропущенного (`:352-372`);
  - поставка после кризиса (`:444-458`);
  - список bypass (`:1267`).
- `test_build_adiscord_focus_trees.py:182-185`: ссылки `shared_focus`
  нового дерева.
- `test_adiscord_val_focus_layout.py`: позиции общих веток в новом дереве.
- `test_adiscord_val_focus_staging.py`: подсказки
  `VAL_focus_progression_*` для `VAL_Campaign_Secured` и
  `VAL_Peace_Without_Orders`.
- `test_adiscord_val_council.py`: `VAL_order_portfolio_open` в списке
  исключений тела провозглашения.
- `test_adiscord_val_new_world.py`: план ИИ называет общие фокусы главного
  дерева, а пара water_convoys/gate_garrison фронта смен в нём намеренно не
  представлена.

## Не проверено в игре

- Что происходит с фокусом, который выполнялся в момент `load_focus_tree`.
- Сохраняется ли `focus_progress > 0` у отменённого `VAL_Peace_Without_Orders`.
- Видны ли общие ветки в новом дереве.
- Срабатывает ли `remove_effect` у решения `days_remove`, `visible` которого
  стало ложным после смены дерева.
- Отмечает ли `bypass` оба взаимоисключающих корня выполненными.
