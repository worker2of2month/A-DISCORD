# Startup Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution or superpowers:subagent-driven-development if the user selects delegation. Steps use checkbox syntax for tracking.

**Goal:** Добавить стартовую справку STP/VAL с описанием страны, гайдом и обзором путей.

**Architecture:** Одно общее окно scripted GUI в player context, отдельный launcher в политическом окне и маршрутизация текста через scripted localisation. UI хранит только состояние навигации; существующая защищённая стартовая инициализация открывает окно человеческим STP/VAL новой кампании 2160 года.

**Tech Stack:** Clausewitz GUI, scripted GUI, scripted localisation, UTF-8 YAML, Python unittest.

**Spec:** `docs/superpowers/specs/2026-09-20-startup-guide-design.md`.

## Global Constraints

- «Первая версия содержит Стеландер (STP) и Кефрейт (VAL).»
- «Справка не выдаёт наград, не выбирает политический курс и не завершает фокусы.»
- «Окно не изменяет скорость игры или состояние паузы, в том числе в мультиплеере.»
- «При каждом открытии выбрана «Страна», подробности путей скрыты.»
- «Нет ежедневных событий, пульсов и периодического сканирования стран.»
- «Русская и английская версии имеют одинаковую структуру и смысл.»
- Русский YAML сохраняет BOM; игровые TXT используют UTF-8 без BOM.
- Существующие грязные изменения сохраняются; не коммитить общие файлы автоматически.
- «Запуск или перезапуск игры проводится после отдельного разрешения пользователя.»

## Review Focus

1. Загрузка старого сохранения: не открывает окно и не повторяет инициализацию экономики; ручное открытие работает.
2. Смена STP на STS/SRP и наблюдатель: окно и launcher скрыты, текст другого тега не появляется.
3. Повторное открытие после раскрытия пути: выбран раздел страны, спойлеры снова скрыты.
4. Длинный русский текст и 1366 x 768: видна последняя строка, все кнопки доступны.
5. Два игрока STP/VAL: навигация одного не влияет на другого; управление одной страной проверяется как разделяемое состояние.

## Файлы и интерфейсы

Создать:

- `tools/builders/build_adiscord_startup_ui_assets.py`, `interface/ADISCORD_startup_menu.gfx` и `gfx/interface/startup/`: собственная оболочка и сменные иллюстрации.

- `interface/ADISCORD_startup_menu.gui`: `ADISCORD_startup_window`, `ADISCORD_startup_launcher`.
- `common/scripted_guis/ADISCORD_startup_menu.txt`: `ADISCORDStartupMenu`, `ADISCORDStartupLauncher`.
- `common/scripted_localisation/ADISCORD_startup_menu.txt`: `ADISCORDGetStartupBody`, `ADISCORDGetStartupPageTitle0`, `ADISCORDGetStartupPageTitle1`.
- `localisation/russian/ADISCORD_startup_menu_l_russian.yml` и английский аналог: общие подписи и страницы.

Расширить:

- `common/on_actions/00_ADISCORD_on_actions.txt`: guarded startup only.
- `localisation/russian/ADISCORD_STP_l_russian.yml` и английский аналог: национальный раздел справки.
- `localisation/russian/ADISCORD_VAL_decisions_l_russian.yml` и английский аналог: национальный раздел справки.
- `tools/tests/test_validate_adiscord_gui_contracts.py`: один класс `StartupGuideContractTests`, существующие помощники разбора GUI.

Не нужны новый event namespace, отдельные страновые GUI, ежедневный hook или новые gameplay effects.

Страновые UI-переменные:

| Переменная | Значения | Значение при открытии |
|---|---|---|
| `ADISCORD_startup_open` | 0 закрыто, 1 открыто | 1 |
| `ADISCORD_startup_tab` | 0 страна, 1 гайд, 2 пути | 0 |
| `ADISCORD_startup_page` | гайд 0 бюджет, 1 армия, 2 дипломатия, 3 страна; пути 0/1 | 0 |
| `ADISCORD_startup_spoilers` | 0 скрыты, 1 раскрыты | 0 |

Все сравнения используют явный `compare = equals`. Отсутствующие значения трактуются как 0.

### Task 1: Оболочка и ручная навигация

**Files:** новые GUI/scripted GUI и существующий тестовый файл из списка выше.

**Consumes:** существующие политическое окно, шрифты и спрайты.
**Produces:** окно, launcher и обработчики `ADISCORD_startup_<action>_click` для действий `open`, `close`, `play`, `country`, `guide`, `paths`, `page_0`–`page_3`, `spoilers`.

- [x] Прочитать `git diff` общих GUI и тестового файла; зафиксировать исходный результат профильных тестов до добавления проверок.
- [x] Создать собственную рамку и кнопки через tools/builders/build_adiscord_startup_ui_assets.py. Проверить --check до --apply и идемпотентность после; новые рисунки сохранить как *_generated.png, а подключённые stp.png/val.png оставить серыми 220 x 440 по указанию пользователя.
- [x] Добавить начальную проверку связности обработчиков:

```python
class StartupGuideContractTests(unittest.TestCase):
    def test_buttons_have_handlers(self):
        root = ROOT
        gui = (root / 'interface/ADISCORD_startup_menu.gui').read_text(encoding='utf-8-sig')
        script = (root / 'common/scripted_guis/ADISCORD_startup_menu.txt').read_text(encoding='utf-8-sig')
        names = [name for kind, name, _ in named_gui_nodes(gui)
                 if kind.lower() == 'buttontype']
        self.assertIn('ADISCORD_startup_open', names)
        self.assertIn('ADISCORD_startup_close', names)
        for name in names:
            self.assertRegex(script, rf'\b{re.escape(name)}_click\s*=\s*\{{')
```

- [x] Запустить `python -B -m unittest tools.tests.test_validate_adiscord_gui_contracts.StartupGuideContractTests -v`; сначала подтвердить отказ из-за отсутствующего нового GUI.
- [x] Создать окно 1000 x 620, центрированное через нативные поля ориентации; нижние вкладки на y=570, иллюстрация 220 x 440 в позиции (746,108), текст введения слева шириной 675 px. Проверить принятые в репозитории поля центрирования до записи.
- [x] Создать launcher с `parent_window_name = "countrypoliticsview"`; использовать свободную строку (454,516), размер 98 x 26, выше законов и ниже панели развития. Главное окно не должно быть дочерним политическому: закрытие политики не должно скрывать автопоказ.
- [x] Использовать в обоих scripted GUI `context_type = player_context`, `ai_enabled = { always = no }` и `visible = { is_ai = no OR = { tag = STP tag = VAL } }`; главное окно дополнительно требует `ADISCORD_startup_open = 1` через `check_variable`.
- [x] Реализовать открытие следующим payload, а закрытие и «К игре» — только `clear_variable = ADISCORD_startup_open`:

```text
ADISCORD_startup_open_click = {
    set_variable = { var = ADISCORD_startup_open value = 1 }
    clear_variable = ADISCORD_startup_tab
    clear_variable = ADISCORD_startup_page
    clear_variable = ADISCORD_startup_spoilers
}
```

- [x] Для вкладок установить tab 0/1/2 и очистить page/spoilers. Для выбора страницы установить page и очистить spoilers. Для spoilers переключать 0/1; кнопку показывать только в путях. Страновые условия никогда не используют выбранного дипломатического адресата.
- [x] Проверить через извлечённые тела обработчиков: открытие содержит все три сброса, обе кнопки закрытия одинаковы, эффекты пишут только четыре разрешённые UI-переменные. Проверить player context и фильтры обоих окон. Повторить профильные тесты.

### Task 2: Тексты и маршрутизация

**Files:** scripted localisation, общий YAML и национальные YAML из списка выше; тот же класс тестов.

**Consumes:** tab/page/spoilers из Task 1.
**Produces:** полные RU/EN тексты, маршрутизатор тела и два названия путей.

- [x] Прочитать существующие `STP_BOOKMARK_DESC`, `VAL_BOOKMARK_DESC`, национальные фокусы и условия в effects/triggers/events. Для VAL обязательно проверить `VAL_Trading_Partners` и `VAL_October_Of_2160`; для STP — фактические условия мандата, соглашения, районов и вмешательства.
- [x] Написать общий набор ключей `ADISCORD_startup_title`, `country`, `guide`, `paths`, `play`, `open`, `spoilers`, `budget`, `army`, `diplomacy`, `national`, `unsupported`, `guide_budget`, `guide_army`, `guide_diplomacy` с единым префиксом `ADISCORD_startup_`.
- [x] В национальные файлы добавить по восемь ключей с префиксом `STP_startup_`/`VAL_startup_`: `country`, `guide`, `path_0_title`, `path_1_title`, `path_0`, `path_1`, `path_0_details`, `path_1_details`. Тексты соответствуют разделу «Содержание» спецификации; до 1200 символов на страницу, точные сроки/числа — только из проверенного скрипта.
- [x] Связать поле тела GUI с `[ADISCORDGetStartupBody]`. Маршрутизатор проверяет подробный путь раньше краткого и заканчивается безопасной общей заглушкой. Пример ветки:

```text
defined_text = {
    name = ADISCORDGetStartupPageTitle0
    text = { trigger = { tag = STP } localization_key = STP_startup_path_0_title }
    text = { trigger = { tag = VAL } localization_key = VAL_startup_path_0_title }
    text = { localization_key = ADISCORD_startup_unsupported }
}
```

- [x] Для tab 0 выбрать национальное введение; tab 1/page 0–2 общие темы, page 3 национальную; tab 2/page 0–1 национальный путь, подробный только при spoilers 1. Название второй карточки маршрутизируется тем же порядком тегов с ключами `path_1_title`.
- [x] Добавить проверки каждого `localization_key` в RU/EN, однострочного quoted value, совпадения новых ключей языков, BOM и длины страниц. Для каждого тега проверить введение, четыре темы гайда, два кратких и два подробных пути; не создавать тестовый расширитель неподдерживаемого синтаксиса.
- [x] Повторить профильные тесты и вручную прочитать тексты на обещания несуществующих путей, обычной дипломатии и бесплатных ресурсов.

### Task 3: Автопоказ и жизненный цикл

**Files:** `common/on_actions/00_ADISCORD_on_actions.txt`, тот же тестовый файл.

**Consumes:** UI-переменные Task 1 и существующий fresh-campaign guard.
**Produces:** однократное открытие для стартовых человеческих STP/VAL.

- [x] Внутри существующего guard `ADISCORD_fresh_campaign_contract_v1` плюс отсутствие `ADISCORD_starting_technology_profiles_applied`, перед записью completion sentinel, добавить прямые STP и VAL scopes. Не добавлять новый `every_country`.
- [x] В каждом scope использовать следующий блок (дата ограничивает стартовый сценарий; проверить нативный синтаксис `date` по локальным примерам):

```text
if = {
    limit = { is_ai = no date < 2160.1.2 }
    set_variable = { var = ADISCORD_startup_open value = 1 }
    clear_variable = ADISCORD_startup_tab
    clear_variable = ADISCORD_startup_page
    clear_variable = ADISCORD_startup_spoilers
}
```

- [x] Добавить структурную проверку вложенности обоих блоков в fresh guard до sentinel и отсутствия UI-переменных в recurring hooks. Существующий тестовый парсер может проверить вложенность, но не объявлять нативное выполнение доказанным.
- [x] Статически проверить закрытое состояние по умолчанию при отсутствии open, сохранение закрытого состояния при загрузке и доступность launcher без fresh guard. Подготовить нативную матрицу: свежие STP/VAL, reload после закрытия, старый save, сценарий 2183, STS/SRP, наблюдатель, два разных игрока.
- [x] Повторить профильные тесты. Убедиться, что порядок STP initializer и economy initializer не изменён.

### Task 4: Приёмка целого меню

**Files:** все изменённые файлы; исправления в их владельцах без дополнительной фрагментации.

**Consumes:** готовая оболочка, контент и startup integration.
**Produces:** проверенный diff и точное разделение статических/нативных результатов.

- [x] Выполнить `python -B -m unittest tools.tests.test_validate_adiscord_gui_contracts -v`.
- [x] Выполнить `python -B tools/validate_tc.py --limit 300` и `git diff --check`; сравнить возможные ошибки с исходным состоянием общего checkout.
- [x] Просмотреть весь собственный diff: нет копирования TFR, изменений gameplay rewards, автокоммитов, новых пульсов или изменения чужих правок.
- [ ] При разрешённой проверке игры получить SHA-256 всех загружаемых файлов меню и изменённых национальных YAML через `Get-FileHash -Algorithm SHA256`, затем полностью перезапустить игру с финальными файлами.
- [ ] Проверить всю матрицу Task 3; на 1920 x 1080 и 1366 x 768 при UI scale 1.0 снять открытые вкладки, последние строки каждой страницы и позицию launcher. Отдельно проверить увеличенный масштаб и отсутствие перекрытий с политическим окном.
- [ ] Проверить в двухклиентной кампании независимость STP/VAL; совместное управление одним тегом отметить как разделяемую навигацию, если это подтверждено. Без второго клиента не заявлять прохождение мультиплеера.
- [x] При отсутствии разрешения на запуск закончить статическую часть и перечислить непроверенные нативные сценарии. Не запускать игру автоматически и не заменять runtime acceptance Python-имитацией.
- [x] Передать итог: реализованные функции, команды и результаты проверок, ограничения и ссылки на основные файлы. Коммит или release-копирование выполняются только по отдельному запросу.
