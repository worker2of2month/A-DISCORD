# Воркерланд, этап 3: подготовка и границы проверки

Контракт подготовительного этапа. Общий замысел - в
[спецификации](../specs/2026-10-26-vorkerland-civil-war-rework-design.md), разделы
"Довоенный этап", "Зависимости сдвига срока" и "Этапы реализации". Соблюдать AGENTS.md.
Подготовка и сдвиг срока реализованы в исходниках. Повторная реализация этих
пунктов не нужна; незакрытые игровые проверки перечислены ниже. Общая переработка
сторон продолжается в объёме, указанном в разделе "Границы реализации" спецификации.
Чекаут грязный и общий: не делать reset/checkout и не включать чужие изменения.

## Уже сделано (не переделывать)

- Таймер распада: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`,
  `days = 350`, `random_days = 30`. Там же вызов `ADISCORD_vorkerland_prewar_crisis_initialize = yes`
  после `ADISCORD_vorkerland_set_phase_prewar = yes`.
- BOP `ADISCORD_vorkerland_prewar_bop` ("Центр ↔ Округа"): `common/bop/WRK.txt`. Инициализация
  один раз в `ADISCORD_vorkerland_prewar_crisis_initialize`, снимок перекоса и удаление BOP в
  `ADISCORD_vorkerland_prewar_balance_snapshot` (вызывается в `collapse.1` до аннексии WRK;
  пишет `global.ADISCORD_vorkerland_prewar_balance_lean` = -1/0/1).
- Влияние лагерей: `global.ADISCORD_vorkerland_camp_{committees,staff,engineers}` (старт 30,
  0-100). Эффекты `ADISCORD_vorkerland_camp_<лагерь>_{add,sub}_<n>`, `..._camp_clamp`,
  `..._camp_stake_on_patron`, `..._grant_camp_packages` (вызов из
  `ADISCORD_vorkerland_inherit_wrk_prewar_preparations`, там же бонус перекоса к центру),
  бонус легитимности наследнику при перекосе к округам - в
  `ADISCORD_vorkerland_initialize_legitimacy`; триггер `ADISCORD_vorkerland_is_preparation_heir`.
  Всё в разделах `preparation_effects` / `preparation_triggers`.
- Третий слот проектов подготовки после `WRK_last_common_budget`
  (`ADISCORD_vorkerland_prep_slot_free`, clamp в `ADISCORD_vorkerland_prep_release_slot` = 3).
- Судьба Уоркера: модификаторы весов в `ADISCORD_vorkerland_prep_resolve_fate` от
  `WRK_reinforce_the_tower_guard` / `WRK_disperse_the_government`.
- Подготовка WRK имеет общий корень `WRK_measure_confederation_fault_lines`;
  бюджет, лагеря и Башня входят в то же дерево. Фокусы автономий
  (`VAD_assess_central_demands` и далее) находятся в том же исходнике
  `focus_trees/Vorkerland/prewar/focuses.txt`, но доступны другим тегам.
  Дерево подготовки передаёт завершённые фокусы и скрывается после распада.
- Два решения баланса в `ADISCORD_vorkerland_prewar_category`:
  `ADISCORD_vorkerland_prewar_central_levy`, `ADISCORD_vorkerland_prewar_district_mandates`.
- Диспетчер `ADISCORD_vorkerland_preparation.40` и 8 кризисных событий `.41`-`.48`
  (`events/ADISCORD_vorkerland_events.txt`), ID зарегистрированы в
  `tools/data/adiscord_event_ids.json`.
- Выбор стороны `ADISCORD_vorkerland_phase.1`: подсказки пакетов лагерей и прогноз судьбы
  (`GetVorkerlandWorkerFateForecast` в `ADISCORD_vorkerland_scripted_loc.txt`); служебные
  флаги и вызов события скрыты в `hidden_effect`.
- Локализация RU/EN всего перечисленного, описание категории с лагерями и балансом.
- Спрайты и shine 22 фокусов в `interface/ADISCORD_national_focus.gfx` и
  `interface/ADISCORD_focus_shines.gfx` (ванильные текстуры).
- Манифест `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py`
  проверяет состав фокусов, якоря, полосы и совместную видимость по деревьям.
  Числа определений принадлежат текущему манифесту, а не этому плану.

## Завершённые зависимости подготовки

- Таймер 350/30 согласован в обработчике запуска и валидаторах recovery/collapse.
- `STP_cw_seize_vorkerland_stores` и `STP_cw_seize_vorkerland_accounts` принадлежат
  `focus_trees/STP/civil_war/focuses.txt`, а не подготовке STP. Допуск требует
  распада Воркерланда. Повторно перемещать фокусы не нужно.
- Лор `docs/lore/countries/WRK.md` и таблица колониальной фазы NAM используют
  окно 350-380 дней.
- `UnifiedPrewarTreeTests` проверяет единый корень подготовки;
  `test_wartime_tree_omits_prewar_branches_but_copies_shared_history_first`
  проверяет сохранение завершённой подготовки без её показа в военном дереве.
  `test_prewar_plans_leave_time_for_paid_preparation` учитывает длительность
  оплачиваемой программы вместе с маршрутом фокусов.
- Сборщик проверяется через
  `python -B -X utf8 -m tools.builders.build_adiscord_focus_trees --source Vorkerland/prewar/focuses.txt --check`.
  При изменении исходника обязательны `--check`, `--apply`, повторный `--check`
  и доказательство идемпотентности. Актуальный вывод не требует перезаписи.

## Незакрытая проверка в игре

Проверку выполняет пользователь вручную в новой кампании. Автоматизация
интерфейса, запуск, перезапуск и закрытие игры запрещены правилами репозитория.

- BOP видна в категории "Наследство Конфедерации", решения баланса меняют её.
- Кризисные события приходят раз в 21-42 дня; подготовительные программы можно
  оплатить и завершить до самого раннего распада.
- При распаде на 350-380 день претенденты получают свои пакеты лагерей;
  `phase.1` показывает пакет и прогноз. Проверяются немедленный выбор и отсутствие
  ответа до таймаута, владельцы и контролёры стартовых областей, оплаченные войска.
- После передачи игрока видимо только дерево выбранной стороны, при этом
  результаты завершённой подготовки сохраняются.
- Свежие логи не содержат ошибок загрузки соответствующих BOP, событий и фокусов.
  Перед проверкой фиксируются хеши загруженных исходников. Исходные тесты не
  заменяют эту проверку и не доказывают симметрию войны в AI-кампании.

## Не трогать

Механику Воркса (`WRK_worx_*`, `on_daily_WRK`, события `postwar.20-23`, GUI Воркса) и
текущую работу над иконками STP - это параллельная сессия.
