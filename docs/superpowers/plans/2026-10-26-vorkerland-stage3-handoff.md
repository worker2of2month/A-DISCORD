# Воркерланд, этап 3: передача незавершённой работы

Задание для исполнителя без доступа к исходному разговору. Общий замысел - в
[спецификации](../specs/2026-10-26-vorkerland-civil-war-rework-design.md), разделы
"Довоенный этап", "Зависимости сдвига срока" и "Этапы реализации". Соблюдать AGENTS.md.
Чекаут грязный и общий: не делать reset/checkout, не коммитить, править только
перечисленное. Файлы STP и иконок параллельно правит другая сессия: перед правкой
перечитать файл и вставлять точечно.

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
- 17 фокусов WRK (корень `WRK_face_the_hourglass`, якорь (7,7)) и 5 фокусов автономий
  (`VAD_assess_central_demands` и далее) в `focus_trees/Vorkerland/prewar/focuses.txt`;
  `shared_focus = WRK_face_the_hourglass` в дереве WKR. Выходы пересобраны.
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
- Манифест `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py` (новые
  кортежи, 268 определений, 68 иконок WRK, якорь, полосы, `_can_share_view` по деревьям):
  `collect_issues()` возвращает 0.

## Осталось сделать

1. **Старые значения таймера в инструментах** (175/21 → 350/30):
   `validate_adiscord_vorkerland_recovery.py:581`, `validate_adiscord_vorkerland_collapse.py:1253-1254`,
   `tests/test_adiscord_vorkerland_recovery.py:131-132`,
   `tests/test_validate_adiscord_vorkerland_collapse.py:379-380`. Проверить
   `tests/test_vorkerland_preparation.py:482` (окно подготовки 175 → 350) и
   `tests/test_adiscord_rus_campaign.py:5075` - относится ли 175 к распаду.
2. **Тесты дерева:** `test_adiscord_vorkerland_civil_war_focus.py:216` (286 → 308 блоков),
   `test_wrk_focus_icons.py` (число иконок WRK). Прогнать модули Воркерланда и поправить
   ожидания, привязанные к старой разметке: варианты `phase.1` (теперь `hidden_effect`),
   `random_list` в `prep_resolve_fate`, `prep_slot_free`, `prep_release_slot`,
   `initialize_legitimacy`, `inherit_wrk_prewar_preparations`, порядок в `collapse.1`.
   Менять тест только если он проверяет старую форму, а не смысл.
3. **Перенос двух фокусов STP** `STP_cw_seize_vorkerland_stores` / `_accounts` из
   `focus_trees/STP/preparation/focuses.txt` в военное дерево Шабрата
   (`focus_trees/STP/civil_war/focuses.txt`, ветка стороны Шабрата) с условием
   `has_global_flag = ADISCORD_vorkerland_collapse_started`; сохранить ID и награды, обновить
   `tests/test_adiscord_stp_preparation.py:8011-8059`, `tests/test_adiscord_economy_rebalance.py:1321`
   и текст `STP_cw_seize_vorkerland_stores_desc`, если он упоминает подготовку. Собрать STP
   через `--source`.
4. **Порог наград:** `python -B -m tools.validators.validate_focus_rewards` (или через
   `validate_tc.py`) для новых фокусов; при слабой награде усилить её, не заменяя механику.
5. **Документация:** `docs/lore/countries/WRK.md:18` и `:85` ("175-196 дней" → "350-380 дней"),
   `docs/superpowers/specs/2026-10-22-nam-package-3-design.md:43` (фаза колонии `0 - 350..380`),
   отметить этап 3 выполненным в спецификации переработки.
6. **Проверки:** сборщик `--check` → `--apply` → `--check`; модули тестов Воркерланда, NAM,
   STP preparation/civil_war; `python -B tools/validate_tc.py --limit 300`; `git diff --check`.
   Сравнивать с базовой линией по HEAD: до этапа падали 282 теста в фокусных модулях
   (в основном `test_adiscord_country_vehicles`), в NAM - 3 старых падения
   (`test_tree_selection_and_generated_owner`, новости `.8/.9`).
7. **Проверка в игре (сообщить, если не делалась):** BOP видна в категории "Наследство
   Конфедерации"; кризисные события приходят раз в 21-42 дня; решения баланса работают;
   при распаде (день 350-380) претенденты получают пакеты лагерей; `phase.1` показывает
   пакеты и прогноз; `error.log` без ошибок BOP, событий и фокусов.

## Не трогать

Механику Воркса (`WRK_worx_*`, `on_daily_WRK`, события `postwar.20-23`, GUI Воркса) и
текущую работу над иконками STP - это параллельная сессия.
