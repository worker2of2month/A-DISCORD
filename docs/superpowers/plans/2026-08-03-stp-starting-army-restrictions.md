# STP Starting Army Restrictions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать сопротивленческие ополчения из стартовых шаблонов STP, связать ограничение регулярной армии только с духом STP и усилить единственную Capital Guard.

**Architecture:** Стартовая история STP применяет официальный страновой lock всех дивизионных шаблонов, а дух STP объясняет и снимает его через `on_remove`; NOD получает отдельную копию прежнего духа без lock. Militia-шаблоны определяются идемпотентно внутри событийных эффектов непосредственно на стороне сопротивления, а OOB содержит только довоенные шаблоны. Существующий STP/VAL crisis validator становится постоянным контрактом для всех новых инвариантов.

**Tech Stack:** Clausewitz/HOI4 1.19.2 script, Python 3 `unittest`, `tools/validate_adiscord_stp_val_crisis.py`, `tools/validate_tc.py`.

## Global Constraints

- Ограничение шаблонов действует только на STP; NOD сохраняет прежние числовые эффекты духа без армейской блокировки.
- Стартовые 14 дивизий STP, их расположение, опыт и коэффициенты оснащения не меняются.
- `STP Mountain Resistance Militia` и `STP Urban Resistance Militia` отсутствуют в `history/units/STP.txt` и создаются только на стороне сопротивления во время гражданской войны.
- Capital Guard остаётся `is_locked = yes`, `force_allow_recruiting = no`, `division_cap = 1` и существует на старте в одном экземпляре.
- Утверждённая разведрота реализуется существующим `ADISCORD_recon_platform`, а линейная артиллерия — `ADISCORD_line_artillery`; STP уже начинает с `ADISCORD_tech_drone_recon_swarms`, поэтому новый юнит и новая технология не добавляются.
- Русская локализация сохраняет UTF-8 BOM.
- Не изменять и не включать в коммиты существующие dirty-файлы экономики: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`, `interface/ADISCORD_economy.gui`, `localisation/russian/ADISCORD_economy_l_russian.yml`, `tools/test_validate_adiscord_gui_contracts.py`.
- Каждый task-коммит содержит только перечисленные в нём файлы; перед коммитом проверять `git diff --cached --name-status`.

---

## File map

- `common/ideas/steland.txt` — STP-версия духа, tooltip и безопасный `on_remove` unlock.
- `common/ideas/nodral.txt` — отдельная NOD-версия прежнего духа без армейского ограничения.
- `history/countries/STP - StepanLand.txt` — стартовый страновой lock с локализованной причиной.
- `history/countries/NOD - Nodral.txt` — перевод NOD на отдельный дух.
- `localisation/russian/ADISCORD_ideas_l_russian.yml` — описание STP-lock, причина блокировки и прежний текст для NOD.
- `history/units/STP.txt` — только стартовые шаблоны и усиленная Capital Guard.
- `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt` — позднее идемпотентное создание militia-шаблонов.
- `tools/validate_adiscord_stp_val_crisis.py` — read-only контракт STP-only lock, militia lifecycle и Capital Guard.
- `tools/test_validate_adiscord_stp_val_crisis.py` — RED/GREEN тесты контракта и защита валидатора от регрессий.

### Task 1: Привязать армейский lock только к духу STP

**Files:**
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `common/ideas/steland.txt`
- Modify: `common/ideas/nodral.txt`
- Modify: `history/countries/STP - StepanLand.txt`
- Modify: `history/countries/NOD - Nodral.txt`
- Modify: `localisation/russian/ADISCORD_ideas_l_russian.yml`

**Interfaces:**
- Consumes: существующий `STP_hedonism_with_no_bondaries`, официальный HOI4 effect `country_lock_all_division_template`, parser helpers `extract_named_block`, `_iter_named_blocks`, `_direct_scalar_values`.
- Produces: `NOD_hedonism_with_no_bondaries`, localisation keys `STP_hedonism_army_restriction_tt` и `STP_hedonism_army_restriction_reason`, валидаторные findings для нарушения STP-only lock.

- [ ] **Step 1: Добавить test-only helper для изолированных копий файлов**

В `CrisisValidatorTests` рядом с `_write_required_files` добавить:

```python
    def _copy_repo_files(self, root: Path, *relative_paths: str) -> None:
        for relative in relative_paths:
            source = validator.ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
```

- [ ] **Step 2: Написать падающий production-contract test**

Добавить в `CrisisValidatorTests`:

```python
    def test_stp_hedonism_spirit_owns_an_stp_only_army_lock(self):
        root = validator.ROOT
        stp_ideas = validator.read(root / "common/ideas/steland.txt") or ""
        nod_ideas = validator.read(root / "common/ideas/nodral.txt") or ""
        stp_history = validator.read(
            root / "history/countries/STP - StepanLand.txt"
        ) or ""
        nod_history = validator.read(
            root / "history/countries/NOD - Nodral.txt"
        ) or ""

        stp_idea = validator.extract_named_block(
            stp_ideas, "STP_hedonism_with_no_bondaries"
        ) or ""
        nod_idea = validator.extract_named_block(
            nod_ideas, "NOD_hedonism_with_no_bondaries"
        ) or ""
        stp_lock = list(
            validator._iter_named_blocks(
                stp_history, "country_lock_all_division_template"
            )
        )

        self.assertEqual(len(stp_lock), 1)
        self.assertEqual(
            validator._direct_scalar_values(stp_lock[0], "is_locked"), ["yes"]
        )
        self.assertEqual(
            validator._direct_scalar_values(stp_lock[0], "desc"),
            ["STP_hedonism_army_restriction_reason"],
        )
        self.assertIn(
            "custom_modifier_tooltip = STP_hedonism_army_restriction_tt",
            validator.extract_named_block(stp_idea, "modifier") or "",
        )
        self.assertIn(
            "country_lock_all_division_template = no",
            validator.extract_named_block(stp_idea, "on_remove") or "",
        )
        self.assertTrue(nod_idea)
        self.assertNotIn("country_lock_all_division_template", nod_idea)
        self.assertIn("NOD_hedonism_with_no_bondaries", nod_history)
        self.assertNotIn("STP_hedonism_with_no_bondaries", nod_history)

        loc_path = root / "localisation/russian/ADISCORD_ideas_l_russian.yml"
        self.assertTrue(loc_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        loc = validator.read(loc_path) or ""
        for key in (
            "NOD_hedonism_with_no_bondaries",
            "NOD_hedonism_with_no_bondaries_desc",
            "STP_hedonism_army_restriction_tt",
            "STP_hedonism_army_restriction_reason",
        ):
            self.assertIn(f" {key}:", loc)
```

- [ ] **Step 3: Написать падающий mutation-test валидатора**

```python
    def test_stp_validator_rejects_missing_country_army_lock(self):
        paths = tuple(relative for relative, _ in validator.REQUIRED_FILES["stp"]) + (
            "common/ideas/steland.txt",
            "common/ideas/nodral.txt",
            "history/countries/STP - StepanLand.txt",
            "history/countries/NOD - Nodral.txt",
            "localisation/russian/ADISCORD_ideas_l_russian.yml",
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_repo_files(root, *paths)
            history = root / "history/countries/STP - StepanLand.txt"
            text = history.read_text(encoding="utf-8-sig")
            text = re.sub(
                r"country_lock_all_division_template\s*=\s*\{.*?\}\s*",
                "",
                text,
                count=1,
                flags=re.DOTALL,
            )
            history.write_text(text, encoding="utf-8-sig")
            issues = validator.validate(root, "stp")

        self.assertTrue(any("STP starting army lock" in issue for issue in issues))
```

- [ ] **Step 4: Запустить новые тесты и подтвердить RED**

Run:

```powershell
python -m unittest `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_stp_hedonism_spirit_owns_an_stp_only_army_lock `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_stp_validator_rejects_missing_country_army_lock
```

Expected: оба теста `FAIL`; первый не находит NOD-идею/lock, второй не получает finding `STP starting army lock`.

- [ ] **Step 5: Расширить список обязательных STP-файлов и валидатор**

В `REQUIRED_FILES["stp"]` добавить:

```python
        ("common/ideas/steland.txt", "STP starting national spirits"),
        ("common/ideas/nodral.txt", "NOD starting national spirits"),
        ("history/countries/STP - StepanLand.txt", "STP starting history"),
        ("history/countries/NOD - Nodral.txt", "NOD starting history"),
        ("localisation/russian/ADISCORD_ideas_l_russian.yml", "STP/NOD ideas localisation"),
```

В `_validate_stp_contract` прочитать эти пять файлов и проверить:

```python
    stp_idea = extract_named_block(stp_ideas, "STP_hedonism_with_no_bondaries") or ""
    nod_idea = extract_named_block(nod_ideas, "NOD_hedonism_with_no_bondaries") or ""
    locks = list(_iter_named_blocks(stp_history, "country_lock_all_division_template"))
    if (
        len(locks) != 1
        or _direct_scalar_values(locks[0], "is_locked") != ["yes"]
        or _direct_scalar_values(locks[0], "desc")
        != ["STP_hedonism_army_restriction_reason"]
    ):
        issues.append("STP starting army lock must use the hedonism restriction reason")
```

Дополнительно выдать findings, если STP-идея не содержит tooltip и `on_remove` unlock, NOD history всё ещё использует STP-идею, NOD-идея содержит lock-токен, любой из четырёх localisation keys отсутствует или файл локализации потерял BOM. Сравнить восемь существующих числовых модификаторов STP/NOD через `_direct_scalar_values`, чтобы NOD не потерял прежний баланс.

- [ ] **Step 6: Реализовать STP lock и отделить дух NOD**

В `history/countries/STP - StepanLand.txt` перед `add_ideas` добавить:

```hoi4
country_lock_all_division_template = {
	is_locked = yes
	desc = STP_hedonism_army_restriction_reason
}
```

В modifier `STP_hedonism_with_no_bondaries` добавить:

```hoi4
				custom_modifier_tooltip = STP_hedonism_army_restriction_tt
```

После modifier добавить:

```hoi4
			on_remove = {
				country_lock_all_division_template = no
			}
```

В `common/ideas/nodral.txt` определить `NOD_hedonism_with_no_bondaries` с теми же `allowed`, `allowed_civil_war`, `removal_cost`, picture и восемью текущими числовыми модификаторами STP, но без tooltip/on_remove. В `history/countries/NOD - Nodral.txt` заменить только выданный ключ `STP_hedonism_with_no_bondaries` на `NOD_hedonism_with_no_bondaries`.

В `ADISCORD_ideas_l_russian.yml` сохранить старый текст для новых NOD-ключей и добавить:

```yaml
 NOD_hedonism_with_no_bondaries: "Политика гедонизма без границ"
 NOD_hedonism_with_no_bondaries_desc: "Государство перестало притворяться воспитателем и стало продавцом удовольствий. Границы открыты для капитала, пороков и туристов, а мораль заменена прайс-листом.\n\nПока витрины сияют, система учится одному: держать людей сытыми, занятыми и слегка одурманенными. Это работает - до тех пор, пока праздник не кончается и счет не приносят всем сразу."
 STP_hedonism_army_restriction_tt: "§RПолитика режима запрещает создавать и изменять дивизионные шаблоны, обучать новые дивизии и расформировывать существующие части.§!"
 STP_hedonism_army_restriction_reason: "Регулярная армия ограничена политикой гедонизма без границ"
```

- [ ] **Step 7: Запустить GREEN-проверки Task 1**

Run:

```powershell
python -m unittest `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_stp_hedonism_spirit_owns_an_stp_only_army_lock `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_stp_validator_rejects_missing_country_army_lock
python -B tools/validate_adiscord_stp_val_crisis.py --section stp
```

Expected: два теста `OK`; validator выводит `Stelander Kefreyt crisis validation passed.`

- [ ] **Step 8: Закоммитить только STP/NOD lock**

```powershell
git add -- common/ideas/steland.txt common/ideas/nodral.txt `
  'history/countries/STP - StepanLand.txt' `
  'history/countries/NOD - Nodral.txt' `
  localisation/russian/ADISCORD_ideas_l_russian.yml `
  tools/validate_adiscord_stp_val_crisis.py `
  tools/test_validate_adiscord_stp_val_crisis.py
git diff --cached --name-status
git commit -m "balance: restrict the STP starting army"
```

Expected staged scope: только семь перечисленных файлов; dirty economy files отсутствуют.

### Task 2: Перенести militia в гражданскую войну и усилить Capital Guard

**Files:**
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `history/units/STP.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt`

**Interfaces:**
- Consumes: `STP_create_empty_mountain_militia`, `STP_create_empty_urban_militia`, `has_template`, `division_template`, существующий `STP_materialize_resistance_packages`.
- Produces: идемпотентное создание каждого militia-шаблона в resistance scope; Capital Guard 24 width из 9 infantry + 2 `ADISCORD_line_artillery`, с `engineer`, `artillery`, `ADISCORD_recon_platform`.

- [ ] **Step 1: Написать падающий lifecycle test militia**

```python
    def test_resistance_militia_templates_exist_only_during_the_revolt(self):
        root = validator.ROOT
        oob = validator.read(root / "history/units/STP.txt") or ""
        war = validator.read(
            root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt"
        ) or ""
        for effect_name, template_name, cap in (
            ("STP_create_empty_mountain_militia", "STP Mountain Resistance Militia", "3"),
            ("STP_create_empty_urban_militia", "STP Urban Resistance Militia", "2"),
        ):
            self.assertNotIn(f'name = "{template_name}"', oob)
            creator = validator.extract_named_block(war, effect_name) or ""
            definition = next(
                (
                    block
                    for block in validator._iter_named_blocks(
                        creator, "division_template"
                    )
                    if f'name = "{template_name}"' in block
                ),
                "",
            )
            self.assertTrue(definition)
            self.assertIn(f'NOT = {{ has_template = "{template_name}" }}', creator)
            self.assertIn("is_locked = yes", definition)
            self.assertIn("force_allow_recruiting = no", definition)
            self.assertIn(f"division_cap = {cap}", definition)
            self.assertLess(
                creator.index(f'name = "{template_name}"'),
                creator.index("create_unit ="),
            )
```

- [ ] **Step 2: Написать падающий Capital Guard composition test**

```python
    def test_capital_guard_is_the_unique_elite_defensive_template(self):
        oob = validator.read(validator.ROOT / "history/units/STP.txt") or ""
        guard = self._block_with_assignment(
            oob, "division_template", 'name = "Capital Guard"'
        )
        regiments = validator.extract_named_block(guard, "regiments") or ""
        support = validator.extract_named_block(guard, "support") or ""

        self.assertEqual(len(list(validator._iter_named_blocks(regiments, "infantry"))), 9)
        self.assertEqual(
            len(list(validator._iter_named_blocks(regiments, "ADISCORD_line_artillery"))),
            2,
        )
        for company in ("engineer", "artillery", "ADISCORD_recon_platform"):
            self.assertEqual(len(list(validator._iter_named_blocks(support, company))), 1)
        self.assertEqual(validator._direct_scalar_values(guard, "is_locked"), ["yes"])
        self.assertEqual(
            validator._direct_scalar_values(guard, "force_allow_recruiting"), ["no"]
        )
        self.assertEqual(validator._direct_scalar_values(guard, "division_cap"), ["1"])
```

- [ ] **Step 3: Написать падающий mutation-test валидатора OOB**

```python
    def test_civil_war_validator_rejects_a_starting_resistance_template(self):
        paths = tuple(relative for relative, _ in validator.REQUIRED_FILES["civil_war"]) + (
            "history/units/STP.txt",
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_repo_files(root, *paths)
            units = root / "history/units/STP.txt"
            units.write_text(
                units.read_text(encoding="utf-8-sig")
                + '\ndivision_template = { name = "STP Mountain Resistance Militia" }\n',
                encoding="utf-8-sig",
            )
            issues = validator.validate(root, "civil_war")

        self.assertTrue(any("must not exist in the STP starting OOB" in issue for issue in issues))
```

- [ ] **Step 4: Запустить новые тесты и подтвердить RED**

Run:

```powershell
python -m unittest `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_resistance_militia_templates_exist_only_during_the_revolt `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_capital_guard_is_the_unique_elite_defensive_template `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_civil_war_validator_rejects_a_starting_resistance_template
```

Expected: militia и Capital Guard tests `FAIL` на текущем OOB; mutation-test не находит нового finding.

- [ ] **Step 5: Обновить civil-war validator**

Добавить `("history/units/STP.txt", "STP starting OOB")` в `REQUIRED_FILES["civil_war"]`. В `_validate_civil_war_contract` заменить прежнее требование стартовых militia-шаблонов следующими инвариантами:

```python
    starting_templates = tuple(_iter_named_blocks(units, "division_template"))
    for effect_name, template_name, cap in (
        ("STP_create_empty_mountain_militia", "STP Mountain Resistance Militia", "3"),
        ("STP_create_empty_urban_militia", "STP Urban Resistance Militia", "2"),
    ):
        if any(f'name = "{template_name}"' in block for block in starting_templates):
            issues.append(f"{template_name} must not exist in the STP starting OOB")
        creator = extract_named_block(war, effect_name) or ""
        definition = next(
            (
                block
                for block in _iter_named_blocks(creator, "division_template")
                if f'name = "{template_name}"' in block
            ),
            "",
        )
        if not definition:
            issues.append(f"{effect_name} must define {template_name} before spawning it")
        elif (
            _direct_scalar_values(definition, "is_locked") != ["yes"]
            or _direct_scalar_values(definition, "force_allow_recruiting") != ["no"]
            or _direct_scalar_values(definition, "division_cap") != [cap]
            or "ADISCORD_militia" not in definition
        ):
            issues.append(f"late militia template {template_name} has an invalid locked definition")
        if f'NOT = {{ has_template = "{template_name}" }}' not in creator:
            issues.append(f"late militia template {template_name} must be idempotent")
```

В этом же validator проверить точные количества батальонов/рот Capital Guard и прежние lock/cap значения. Finding names: `Capital Guard must contain exactly 9 infantry battalions`, `Capital Guard must contain exactly 2 line artillery battalions`, `Capital Guard support companies are noncanonical`.

- [ ] **Step 6: Удалить militia из OOB и создавать их внутри spawn-effects**

Удалить два полных `division_template` блока сопротивления из `history/units/STP.txt`.

В начало каждого `STP_create_empty_*_militia` перед `capital_scope` добавить idempotent branch. Для mountain-варианта:

```hoi4
	if = {
		limit = {
			NOT = { has_template = "STP Mountain Resistance Militia" }
		}
		division_template = {
			name = "STP Mountain Resistance Militia"
			division_names_group = STP_INF_01
			is_locked = yes
			force_allow_recruiting = no
			division_cap = 3
			regiments = {
				ADISCORD_militia = { x = 0 y = 0 }
				ADISCORD_militia = { x = 0 y = 1 }
				ADISCORD_militia = { x = 1 y = 0 }
			}
		}
	}
```

Urban-вариант повторяет блок с именем `STP Urban Resistance Militia` и `division_cap = 2`. Существующие `create_unit` строки не менять.

- [ ] **Step 7: Усилить Capital Guard точным утверждённым составом**

Сохранить девять существующих infantry-батальонов и добавить в `regiments`:

```hoi4
		ADISCORD_line_artillery = { x = 3 y = 0 }
		ADISCORD_line_artillery = { x = 3 y = 1 }
```

Support block сделать ровно таким:

```hoi4
	support = {
		engineer = { x = 0 y = 0 }
		artillery = { x = 0 y = 1 }
		ADISCORD_recon_platform = { x = 0 y = 2 }
	}
```

- [ ] **Step 8: Запустить GREEN-проверки Task 2**

Run:

```powershell
python -m unittest `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_resistance_militia_templates_exist_only_during_the_revolt `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_capital_guard_is_the_unique_elite_defensive_template `
  tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests.test_civil_war_validator_rejects_a_starting_resistance_template
python -B tools/validate_adiscord_stp_val_crisis.py --section civil_war
```

Expected: три теста `OK`; validator выводит `Stelander Kefreyt crisis validation passed.`

- [ ] **Step 9: Закоммитить только шаблоны и civil-war контракт**

```powershell
git add -- history/units/STP.txt `
  common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt `
  tools/validate_adiscord_stp_val_crisis.py `
  tools/test_validate_adiscord_stp_val_crisis.py
git diff --cached --name-status
git commit -m "balance: hide STP resistance templates until revolt"
```

Expected staged scope: только четыре перечисленных файла.

### Task 3: Полная статическая и runtime-проверка

**Files:**
- Verify only: все файлы Tasks 1–2
- Inspect only: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log`
- Inspect only: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs/game.log`

**Interfaces:**
- Consumes: два task-коммита и установленную HOI4 1.19.2 по `Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/hoi4.exe`.
- Produces: подтверждение static gate и отдельный статус runtime: подтверждён в свежей кампании либо явно оставлен неподтверждённым.

- [ ] **Step 1: Прогнать полный STP/VAL unit suite**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis
```

Expected: `OK`, без failures/errors.

- [ ] **Step 2: Прогнать feature validator и общий TC gate**

```powershell
python -B tools/validate_adiscord_stp_val_crisis.py
python tools/validate_tc.py --limit 300
git diff --check
```

Expected: оба валидатора завершаются с exit code `0`; `git diff --check` не печатает ошибок.

- [ ] **Step 3: Проверить чистоту целевого diff и сохранность чужой работы**

```powershell
git status --short
git show --stat --oneline HEAD~1..HEAD
git diff --name-only 619dfb1..HEAD
```

Expected: целевой диапазон содержит только девять файлов из File map; четыре dirty economy files остаются unstaged и не входят ни в один task-коммит.

- [ ] **Step 4: Выполнить свежий parse-smoke HOI4**

Убедиться, что `hoi4.exe` не запущен, затем запустить отдельный скрытый экземпляр:

```powershell
$game = 'Z:\SteamLibrary\steamapps\common\Hearts of Iron IV'
$exe = Join-Path $game 'hoi4.exe'
$started = Start-Process -FilePath $exe `
  -ArgumentList @('--crash_data_log','--debug','--windowed') `
  -WorkingDirectory $game -WindowStyle Hidden -PassThru
```

Дождаться строки `Active Mod: A-Discord` в свежем `system.log` не более 55 секунд. После загрузки меню проверить свежий `error.log`:

```powershell
$errorLog = 'C:\Users\Admin\Documents\Paradox Interactive\Hearts of Iron IV\logs\error.log'
rg -n -i 'country_lock_all_division_template|STP_hedonism_army_restriction|NOD_hedonism_with_no_bondaries|STP Mountain Resistance Militia|STP Urban Resistance Militia|ADISCORD_line_artillery|ADISCORD_recon_platform|Unknown effect|Unknown trigger|Invalid|Unexpected token|Could not find' $errorLog
```

Expected: нет новых строк, связанных с перечисленными ключами/шаблонами/юнитами; после проверки остановить только PID `$started.Id`.

- [ ] **Step 5: Проверить новую кампанию STP в интерфейсе**

Запустить новую кампанию за STP на дате `2160.1.1.12`, открыть Recruit & Deploy и подтвердить:

- доступны только `Police division`, `Regular army`, `Capital Guard`; обоих Resistance Militia нет;
- кнопки создания/редактирования/обучения заблокированы с причиной `Регулярная армия ограничена политикой гедонизма без границ`;
- в духе «Политика гедонизма без границ» виден красный tooltip армейского ограничения;
- Capital Guard показывает 9 infantry, 2 line artillery, engineer, support artillery и recon platform;
- на карте остаются ровно 14 стартовых дивизий и одна Capital Guard.

Сохранить время свежих `error.log` и `game.log`; просканировать их тем же targeted regex. Если управление окном недоступно, не считать этот step пройденным и в финальном отчёте написать: `static and parse-smoke passed; new-game UI runtime remains unconfirmed`.

- [ ] **Step 6: Финальный отчёт без дополнительного коммита**

Сообщить пользователю два task commit hash, результаты unit/feature/TC gates, статус свежего parse-smoke, статус новой кампании и список оставшихся нетронутыми economy-файлов. Не заявлять, что поведение подтверждено в игре, если Step 5 не выполнен полностью.
