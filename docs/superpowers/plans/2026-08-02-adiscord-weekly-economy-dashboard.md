# A-Discord Weekly Economy Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести денежное исполнение A-Discord на прозрачный недельный тик, сделать компактный TDA-подобный интерфейс со шкалами и иконкой казны, проверить экономические здания и выпустить документированный API экономических модификаторов.

**Architecture:** Текущие месячные формулы остаются базовым прогнозом, а новый country-scoped недельный обработчик переводит их в недельные значения через `3 / 13` и единожды применяет к казне. Месячный обработчик сохраняет только макроэкономику и решения ИИ; тяжёлый обход регионов остаётся квартальным или dirty-triggered. GUI использует одно окно, штатные стрелки и движущийся маркер пятиступенчатой шкалы; подробности находятся в подсказках.

**Tech Stack:** Hearts of Iron IV Clausewitz script, scripted GUI, `.gui`/`.gfx`, UTF-8 BOM YAML localisation, DDS UI assets, Python `unittest` static contracts, project validators.

## Global Constraints

- Недельный денежный тик применяется только к игроку и primary-tier странам; secondary-tier ИИ остаётся годовым.
- В `on_weekly` и вызываемых им эффектах запрещены `every_country`, `every_owned_state`, `all_owned_state` и другие обходы карты.
- Недельные доходы и расходы равны месячным базовым значениям, умноженным на `3` и разделённым на `13`.
- Месячный стратегический тик не изменяет казну и не вызывает недельный/периодный денежный apply.
- Показанный недельный баланс обязан равняться фактически применённому изменению казны до прямых операций, финансирования и cap write-off.
- `ADISCORD_economy_reserve_growth_factor` удаляется из активного API; скрытого множителя профицита нет.
- Схема сохранения повышается с `5` до `6` без сброса казны, долга, бюджетных режимов, развития и строительных счётчиков.
- ИИ меняет бюджетные режимы только в месячном тике.
- Полный пересчёт экономических зданий остаётся раз в три месяца или после dirty-сигнала.
- Видимый интерфейс содержит только решения и ключевые показатели; бухгалтерские подробности находятся в тултипах.
- Русская локализация сохраняет UTF-8 BOM.
- Временная иконка копируется из TDA с разрешения пользователя, получает имя A-Discord и пометку о последующей замене.
- Торговая интеграция TFR не входит в этот релиз и проектируется отдельно после завершения основной экономики.
- Не изменять несвязанные ошибки карты, тегов, армейских иконок, радио и ванильных GUI.
- Перед любым заявлением о готовности выполнить свежий запуск HOI4 и проверить новый `error.log`.

## File Map

- `common/on_actions/00_ADISCORD_on_actions.txt` — частота weekly/monthly/yearly.
- `common/scripted_effects/ADISCORD_economy_effects.txt` — миграция schema 7, прогноз, недельное и годовое денежное исполнение, бухгалтерия.
- `common/scripted_triggers/ADISCORD_economy_triggers.txt` — eligibility уровней симуляции.
- `common/scripted_effects/ADISCORD_economy_modifier_effects.txt` — потребление публичных modifier definitions.
- `common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt` — публичный API модификаторов.
- `common/synchronized_dynamic_tokens/ADISCORD_tokens.txt` — список разрешённых синхронизируемых modifier tokens.
- `common/scripted_guis/ADISCORD_economy_scripted_gui.txt` — click/enabled/visible bindings GUI.
- `interface/ADISCORD_economy.gui` — топбар, KPI, статус, бюджетные шкалы и действия.
- `interface/ADISCORD_economy.gfx` — A-Discord sprite для временной иконки казны.
- `gfx/interface/ADISCORD_economy_gui/treasury_icon.dds` — временный бинарный ассет из TDA.
- `common/buildings/00_buildings.txt` — три экономических здания.
- `common/ai_strategy/ADISCORD_economy_ai.txt` — строительные приоритеты ИИ по фискальному состоянию.
- `localisation/russian/ADISCORD_economy_l_russian.yml` — недельные подписи, тултипы GUI и здания.
- `localisation/russian/ADISCORD_economy_modifiers_l_russian.yml` — названия публичных модификаторов.
- `docs/economy/economic-modifiers.md` — API для фокусов, идей и событий.
- `docs/economy/economic-buildings.md` — технический баланс зданий и их игровые роли.
- `docs/economy/temporary-assets.md` — происхождение и точка замены временной иконки.
- `tools/test_adiscord_economy_weekly_contracts.py` — регрессии частоты, бухгалтерии, миграции и API.
- `tools/test_validate_adiscord_gui_contracts.py` — структура топбара и бюджетных шкал.
- `tools/validate_adiscord_economy_ai.py` — интеграционный статический валидатор экономики/ИИ.
- `tools/validate_tc.py` — общий gate total conversion и запрет тяжёлых weekly scans.

---

### Task 1: Недельный денежный контракт и schema 7

**Files:**
- Create: `tools/test_adiscord_economy_weekly_contracts.py`
- Modify: `common/on_actions/00_ADISCORD_on_actions.txt:91-132`
- Modify: `common/scripted_triggers/ADISCORD_economy_triggers.txt:4-51`
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt:3-240,256-365,940-1092,2090-2170`
- Modify: `tools/test_validate_adiscord_gui_contracts.py:158-167`
- Modify: `tools/validate_adiscord_economy_ai.py:100-180`

**Interfaces:**
- Consumes: `ADISCORD_economy_should_monthly_update`, monthly income/expense formula variables, existing auto-loan and accounting variables.
- Produces: `ADISCORD_economy_should_weekly_update`, `ADISCORD_economy_weekly_update`, `ADISCORD_economy_calculate_weekly_budget`, `ADISCORD_economy_apply_weekly_balance`, weekly forecast variables and schema version `6`.

- [ ] **Step 1: Write the failing weekly contracts**

Create tests that extract balanced Clausewitz blocks and assert the new architecture:

```python
def block(text, name):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:index]
    raise AssertionError(f"unclosed block: {name}")

class WeeklyEconomyContracts(unittest.TestCase):
    def test_weekly_pulse_is_country_scoped_and_applies_once(self):
        weekly = block(ON_ACTIONS, "on_weekly")
        self.assertIn("ADISCORD_economy_should_weekly_update", weekly)
        self.assertEqual(weekly.count("ADISCORD_economy_weekly_update = yes"), 1)
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotIn(forbidden, weekly)

    def test_weekly_budget_uses_exact_annual_parity_ratio(self):
        weekly = block(EFFECTS, "ADISCORD_economy_calculate_weekly_budget")
        self.assertRegex(weekly, r"weekly_income[\s\S]*multiply_variable[\s\S]*value\s*=\s*3")
        self.assertRegex(weekly, r"weekly_income[\s\S]*divide_variable[\s\S]*value\s*=\s*13")
        self.assertRegex(weekly, r"weekly_expenses[\s\S]*multiply_variable[\s\S]*value\s*=\s*3")
        self.assertRegex(weekly, r"weekly_expenses[\s\S]*divide_variable[\s\S]*value\s*=\s*13")

    def test_monthly_tick_does_not_apply_cash(self):
        monthly = block(EFFECTS, "ADISCORD_economy_monthly_update")
        self.assertNotIn("apply_weekly_balance", monthly)
        self.assertNotIn("apply_monthly_balance", monthly)
        self.assertNotIn("apply_budget_period", monthly)

    def test_schema_six_preserves_existing_treasury(self):
        migration = block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn("value = 6", migration)
        self.assertNotRegex(migration, r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_treasury\s+value\s*=\s*100")
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B -m unittest tools.test_validate_adiscord_gui_contracts.RuntimePulseTests -v
```

Expected: failures for missing `on_weekly`, missing weekly variables/effects and schema still equal to `5`.

- [ ] **Step 3: Add weekly eligibility and country-scoped pulse**

Add the trigger as an alias over the existing player/primary tier contract:

```txt
ADISCORD_economy_should_weekly_update = {
	OR = {
		ADISCORD_economy_is_player_tier_country = yes
		ADISCORD_economy_is_primary_tier_country = yes
	}
}
```

Add a top-level country-scoped pulse without `every_country`:

```txt
on_weekly = {
	effect = {
		if = {
			limit = { ADISCORD_economy_should_weekly_update = yes }
			ADISCORD_economy_weekly_update = yes
		}
	}
}
```

Keep `on_monthly` for strategic effects and `on_yearly` for secondary-tier AI.

- [x] **Step 4: Add schema 7 variables without resetting saves**

Initialize these variables in defaults and guarded migration:

```txt
ADISCORD_economy_weekly_income
ADISCORD_economy_weekly_expenses
ADISCORD_economy_weekly_balance
ADISCORD_economy_last_weekly_balance_applied
ADISCORD_economy_accounting_period_treasury_start
ADISCORD_economy_last_period_treasury_before
ADISCORD_economy_last_period_treasury_after
ADISCORD_economy_last_period_income
ADISCORD_economy_last_period_expenses
ADISCORD_economy_last_period_balance
ADISCORD_economy_last_period_action_income
ADISCORD_economy_last_period_action_costs
ADISCORD_economy_last_period_building_costs
ADISCORD_economy_last_period_debt_added
ADISCORD_economy_last_period_debt_paid
ADISCORD_economy_last_period_cap_writeoff
ADISCORD_economy_last_period_unexplained_delta
```

Set `ADISCORD_economy_schema_version = 6` only after guarded initialization. Do not call `ADISCORD_economy_set_default_values` from the version-5 migration path.

- [ ] **Step 5: Implement weekly forecast and one cash apply**

Calculate weekly values explicitly:

```txt
ADISCORD_economy_calculate_weekly_budget = {
	set_variable = { var = ADISCORD_economy_weekly_income value = ADISCORD_economy_monthly_income }
	multiply_variable = { var = ADISCORD_economy_weekly_income value = 3 }
	divide_variable = { var = ADISCORD_economy_weekly_income value = 13 }
	set_variable = { var = ADISCORD_economy_weekly_expenses value = ADISCORD_economy_monthly_expenses }
	multiply_variable = { var = ADISCORD_economy_weekly_expenses value = 3 }
	divide_variable = { var = ADISCORD_economy_weekly_expenses value = 13 }
	set_variable = { var = ADISCORD_economy_weekly_balance value = ADISCORD_economy_weekly_income }
	subtract_from_variable = { var = ADISCORD_economy_weekly_balance value = ADISCORD_economy_weekly_expenses }
}
```

`ADISCORD_economy_apply_weekly_balance` must add exactly `ADISCORD_economy_weekly_balance`, cover only uncovered negative treasury with debt-room-limited auto borrowing, apply the treasury cap once, record period accounting, reset direct-operation counters, and advance the accounting-period start. Do not multiply positive balance by another factor.

The weekly orchestrator is:

```txt
ADISCORD_economy_weekly_update = {
	ADISCORD_economy_initialize_country = yes
	ADISCORD_economy_light_update = yes
	ADISCORD_economy_calculate_weekly_budget = yes
	ADISCORD_economy_apply_weekly_balance = yes
	ADISCORD_economy_update_gui = yes
}
```

- [ ] **Step 6: Split monthly strategy from cash execution**

Remove the cash apply from `ADISCORD_economy_monthly_update`. Retain dirty/full refresh processing, quarterly recount, modifier refresh, AI monthly policy, inflation, stress, fatigue, development, spending ideas, action-flag cleanup and cooldown ticks. Keep the yearly secondary path at `monthly forecast × 12`, but have it use the same raw-balance accounting rules without the removed reserve multiplier.

- [ ] **Step 7: Run contracts and economy validator**

Run:

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B -m unittest tools.test_validate_adiscord_gui_contracts.RuntimePulseTests -v
python -B tools/validate_adiscord_economy_ai.py
```

Expected: all PASS and `A-DISCORD economy/AI validation: OK`.

- [ ] **Step 8: Commit the weekly engine slice**

```powershell
git add -- common/on_actions/00_ADISCORD_on_actions.txt common/scripted_triggers/ADISCORD_economy_triggers.txt common/scripted_effects/ADISCORD_economy_effects.txt tools/test_adiscord_economy_weekly_contracts.py tools/test_validate_adiscord_gui_contracts.py tools/validate_adiscord_economy_ai.py
git commit -m "feat: settle primary economies weekly"
```

### Task 2: Удаление скрытого reserve multiplier и бухгалтерские тултипы

**Files:**
- Modify: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt:6-190,240-470`
- Modify: `common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt:266-273`
- Modify: `common/synchronized_dynamic_tokens/ADISCORD_tokens.txt:54`
- Modify: `localisation/russian/ADISCORD_economy_modifiers_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml:3-31,70-75`
- Modify: `tools/test_adiscord_economy_weekly_contracts.py`

**Interfaces:**
- Consumes: period variables from Task 1.
- Produces: one transparent accounting identity and no remaining public/internal `reserve_growth_factor` path.

- [ ] **Step 1: Add failing tests for reserve removal and accounting disclosure**

```python
def test_reserve_growth_factor_is_fully_retired(self):
    for text in (MODIFIER_EFFECTS, MODIFIER_DEFINITIONS, TOKENS, MODIFIER_LOC):
        self.assertNotIn("ADISCORD_economy_reserve_growth_factor", text)

def test_treasury_tooltip_uses_weekly_and_period_values(self):
    self.assertIn("ADISCORD_economy_weekly_balance", ECONOMY_LOC)
    self.assertIn("ADISCORD_economy_last_period_unexplained_delta", ECONOMY_LOC)
    self.assertNotIn("Фактическое изменение казны происходит раз в месяц", ECONOMY_LOC)
```

- [ ] **Step 2: Run tests and confirm RED**

Run `python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v`.

Expected: reserve key and monthly player-facing wording are still present.

- [ ] **Step 3: Remove the full reserve-growth chain**

Delete the modifier definition, localization, synchronized token, static/policy/final variables, visible `modifier@` read and clamp for `ADISCORD_economy_reserve_growth_factor`. Confirm `rg -n "reserve_growth_factor" common localisation` returns no active result.

- [ ] **Step 4: Rewrite player-facing accounting text**

Use `ADISCORD_economy_weekly_income`, `weekly_expenses`, `weekly_balance` for the forecast. Label the snapshot `Последняя неделя` and show:

```text
Казна: начало -> конец
Доходы / расходы / операционный баланс
Разовые доходы / действия / здания
Заёмное финансирование / погашение
Списано сверх лимита
Необъяснённая разница
```

Keep explanation text in tooltips; do not add another visible ledger panel.

- [ ] **Step 5: Verify BOM and tests**

Run:

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B tools/validate_adiscord_economy_ai.py
```

Verify the first three bytes of both Russian YAML files remain `EF BB BF`.

- [ ] **Step 6: Commit transparent accounting**

```powershell
git add -- common/scripted_effects/ADISCORD_economy_modifier_effects.txt common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt common/synchronized_dynamic_tokens/ADISCORD_tokens.txt localisation/russian/ADISCORD_economy_modifiers_l_russian.yml localisation/russian/ADISCORD_economy_l_russian.yml tools/test_adiscord_economy_weekly_contracts.py
git commit -m "fix: make treasury accounting match the forecast"
```

### Task 3: TDA-подобный топбар и пятиступенчатые бюджетные шкалы

**Files:**
- Create: `gfx/interface/ADISCORD_economy_gui/treasury_icon.dds`
- Create: `docs/economy/temporary-assets.md`
- Modify: `interface/ADISCORD_economy.gfx`
- Modify: `interface/ADISCORD_economy.gui`
- Modify: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml`
- Modify: `tools/test_validate_adiscord_gui_contracts.py`
- Modify: `tools/validate_adiscord_economy_ai.py`

**Interfaces:**
- Consumes: four existing mode variables and eight existing increase/decrease effects/triggers; weekly forecast variables from Task 1.
- Produces: numeric-only topbar treasury indicator, temporary `GFX_ADISCORD_treasury_icon`, four arrow-controlled five-step scales and non-overlapping dashboard text zones.

- [ ] **Step 1: Add failing GUI structure tests**

Add `EconomyDashboardGuiContractTests` with assertions equivalent to:

```python
class EconomyDashboardGuiContractTests(unittest.TestCase):
    def setUp(self):
        self.gui = (ROOT / "interface" / "ADISCORD_economy.gui").read_text(encoding="utf-8-sig")
        self.nodes = set(named_gui_nodes(self.gui))

    def test_topbar_uses_icon_and_numeric_value(self):
        self.assertIn(('iconType', 'ADISCORD_economy_topbar_icon', ('ADISCORD_economy_topbar_window',)), self.nodes)
        self.assertIn(('instantTextboxType', 'ADISCORD_economy_topbar_value', ('ADISCORD_economy_topbar_window',)), self.nodes)
        self.assertNotRegex(self.gui, r'buttonText\s*=\s*"ADISCORD_economy_topbar_treasury_text"')

    def test_four_budget_rows_use_arrows_and_five_step_markers(self):
        for policy in ('tax', 'army', 'construction', 'social'):
            self.assertRegex(self.gui, rf'name\s*=\s*"ADISCORD_economy_{policy}_decrease"[\s\S]{{0,200}}spriteType\s*=\s*"button_left"')
            self.assertRegex(self.gui, rf'name\s*=\s*"ADISCORD_economy_{policy}_increase"[\s\S]{{0,200}}spriteType\s*=\s*"button_right"')
            for level in range(1, 6):
                self.assertIn(f'ADISCORD_economy_{policy}_step_{level}', self.gui)
        self.assertNotRegex(self.gui, r'buttonText\s*=\s*"[+-]"')
```

Also assert `ADISCORD_economy_automation_note` is absent and the status/advice/building text boxes occupy non-overlapping y ranges.

- [ ] **Step 2: Run GUI tests and confirm RED**

Run `python -B -m unittest tools.test_validate_adiscord_gui_contracts.EconomyDashboardGuiContractTests -v`.

Expected: missing test class requirements, existing literal `+/-` and text-only topbar fail.

- [ ] **Step 3: Copy and rename the temporary money icon**

Copy exactly:

```powershell
Copy-Item -LiteralPath 'Z:\SteamLibrary\steamapps\workshop\content\394360\3607150697\gfx\interface\money_icon_interface.dds' -Destination 'gfx\interface\ADISCORD_economy_gui\treasury_icon.dds'
```

Register it independently:

```txt
spriteType = {
	name = "GFX_ADISCORD_treasury_icon"
	texturefile = "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds"
	legacy_lazy_load = no
}
```

Document workshop ID `3607150697`, source relative path, temporary status, target sprite name and the rule that replacement must preserve dimensions/alpha or update GUI scale.

- [ ] **Step 4: Rebuild the topbar indicator**

Make the scripted-GUI window approximately `112x28`. Place a transparent full-size button first, then `ADISCORD_economy_topbar_icon`, then a centered numeric textbox using:

```yml
ADISCORD_economy_topbar_treasury_value: "[?ADISCORD_economy_treasury|0]"
```

Do not render `Казна:` in the topbar. Keep the existing click binding on the full background button and move weekly balance, cap, debt and breakdown into its tooltip.

- [ ] **Step 5: Replace blank squares with TDA arrow structure**

For each policy row, use passive frame-1 steps at x offsets `0, 24, 48, 72, 96`, one frame-2 active marker, and `button_left`/`button_right` controls. The active marker position is selected from the matching mode variable by scripted-GUI visible binding using x positions `0/24/48/72/96`. Arrow `click_enabled` bindings continue to call existing `ADISCORD_economy_can_*` triggers.

Do not make the five step markers separate policy-changing buttons. They communicate state; only arrows change the policy, avoiding twenty extra click actions.

- [ ] **Step 6: Remove the left-panel overlap**

Delete the visible automation paragraph. Reserve fixed zones:

```text
summary: y 14, maxHeight 126
advice: y 154, maxHeight 112
buildings: y 342, maxHeight 58
```

Shorten the visible localization until it fits those contracts. Keep the automation explanation on the treasury/accounting tooltip.

- [ ] **Step 7: Run GUI and economy contracts**

Run:

```powershell
python -B -m unittest tools.test_validate_adiscord_gui_contracts -v
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B tools/validate_adiscord_economy_ai.py
```

Expected: all PASS.

- [ ] **Step 8: Commit the GUI slice**

```powershell
git add -- interface/ADISCORD_economy.gfx interface/ADISCORD_economy.gui common/scripted_guis/ADISCORD_economy_scripted_gui.txt localisation/russian/ADISCORD_economy_l_russian.yml gfx/interface/ADISCORD_economy_gui/treasury_icon.dds docs/economy/temporary-assets.md tools/test_validate_adiscord_gui_contracts.py tools/validate_adiscord_economy_ai.py
git commit -m "feat: add compact treasury and budget controls"
```

### Task 4: Экономические здания как три понятных игровых роли

**Files:**
- Modify: `common/buildings/00_buildings.txt:729-785`
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt:367-800,1285-1301,1782-1902`
- Modify: `common/ai_strategy/ADISCORD_economy_ai.txt`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml:217-225,338-340`
- Create: `docs/economy/economic-buildings.md`
- Modify: `tools/test_adiscord_economy_weekly_contracts.py`
- Modify: `tools/validate_adiscord_economy_ai.py`

**Interfaces:**
- Consumes: cached building counters and quarterly recount.
- Produces: validated business/science/industrial roles, documented cost/upkeep/output and bounded AI construction targets.

- [ ] **Step 1: Add failing building-role contracts**

Assert all three buildings are normal state buildings with `show_on_map = 0`, escalating `per_controlled_building_extra_cost`, bounded `state_max`, distinct state modifiers and cached country-level economy effects. Assert weekly effects do not recount them. Assert Russian copy does not contain `Строятся в обычном меню`.

- [ ] **Step 2: Run contracts and confirm RED where copy/docs are absent**

Run `python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v`.

Expected: failure for the old construction-menu sentence and missing developer documentation; structural building assertions may already pass and should remain unchanged.

- [ ] **Step 3: Audit annualized value and preserve distinct roles**

Record current formulas in `economic-buildings.md`:

```text
Business center: direct business/building income, debt capacity, development, admin upkeep.
Science center: small direct income, research/development network bonus, research/admin upkeep.
Industrial cluster: civilian/building income, conditional military-industry income, factory-output network bonus, subsidy/admin upkeep and energy burden.
```

Calculate annual net treasury contribution using the same 12-month total as the weekly `3/13` conversion. Keep the current costs/caps when payback and role are coherent; change only values that make a building strictly dominate another or never repay within a normal campaign.

- [ ] **Step 4: Keep AI behavior bounded**

Retain zero custom-building targets in crisis/stress, business-only target `1` in recovery, balanced `2/1/1` targets during healthy peace and industrial-cluster target `2` during healthy war. Add validator assertions for these exact bounds so AI cannot spam economic buildings.

- [ ] **Step 5: Simplify player-facing building copy**

Keep one-line dashboard counts and the existing detailed tooltip, but remove ordinary construction-menu instructions. Lead each tooltip section with the building's role, main benefit and upkeep; keep exact weekly equivalents and technical formulas in `economic-buildings.md`.

- [ ] **Step 6: Run building/economy validators**

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B tools/validate_adiscord_economy_ai.py
python -B tools/validate_tc.py --limit 300
```

- [ ] **Step 7: Commit the building audit**

```powershell
git add -- common/buildings/00_buildings.txt common/scripted_effects/ADISCORD_economy_effects.txt common/ai_strategy/ADISCORD_economy_ai.txt localisation/russian/ADISCORD_economy_l_russian.yml docs/economy/economic-buildings.md tools/test_adiscord_economy_weekly_contracts.py tools/validate_adiscord_economy_ai.py
git commit -m "balance: clarify economic building roles"
```

### Task 5: Документированный API модификаторов для фокусов

**Files:**
- Create: `docs/economy/economic-modifiers.md`
- Modify: `common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt`
- Modify: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt`
- Modify: `localisation/russian/ADISCORD_economy_modifiers_l_russian.yml`
- Modify: `tools/test_adiscord_economy_weekly_contracts.py`
- Modify: `tools/validate_adiscord_economy_ai.py`

**Interfaces:**
- Consumes: active custom modifier definitions and their `modifier@KEY` reads.
- Produces: one-to-one documented, localized and formula-connected public modifier API.

- [ ] **Step 1: Add failing API completeness test**

Parse every `ADISCORD_economy_*` and `ADISCORD_country_development_*` definition. For each key assert:

```python
self.assertIn(f"modifier@{key}", MODIFIER_EFFECTS)
self.assertRegex(MODIFIER_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+\"")
self.assertIn(f"`{key}`", MODIFIER_DOCS)
```

Explicitly assert `ADISCORD_economy_resource_rent_income_factor` exists and `ADISCORD_economy_reserve_growth_factor` does not.

- [ ] **Step 2: Run API test and confirm RED**

Run `python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v`.

Expected: documentation file missing and any currently disconnected keys identified by name.

- [ ] **Step 3: Reconcile definitions, reads and localization**

For every remaining public key, ensure exactly one definition, one Russian localization and one `modifier@KEY` read feeding a clamped final factor. Remove rather than document any unused key unless a concrete formula consumer is added in the same step.

- [ ] **Step 4: Write the focus-facing reference**

Organize `economic-modifiers.md` into income, expenses, debt/credit, inflation/stress, state pressure and development. Each table row contains key, positive-value meaning, safe focus range and formula target. Include this persistent national-spirit example:

```txt
ideas = {
	country = {
		ADISCORD_example_resource_concessions = {
			picture = generic_industry
			allowed = { always = yes }
			modifier = {
				ADISCORD_economy_resource_rent_income_factor = 0.15
			}
		}
	}
}
```

And the focus reward:

```txt
completion_reward = {
	add_ideas = ADISCORD_example_resource_concessions
}
```

State plainly that `0.15` means `+15%`, income factor `+` is good, expense factor `+` means higher expense, and `-0.10` on an expense factor means a 10% saving.

- [ ] **Step 5: Run API/economy validation**

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B tools/validate_adiscord_economy_ai.py
python -B tools/validate_tc.py --limit 300
```

- [ ] **Step 6: Commit the modifier API**

```powershell
git add -- docs/economy/economic-modifiers.md common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt common/scripted_effects/ADISCORD_economy_modifier_effects.txt localisation/russian/ADISCORD_economy_modifiers_l_russian.yml tools/test_adiscord_economy_weekly_contracts.py tools/validate_adiscord_economy_ai.py
git commit -m "docs: publish focus-ready economy modifiers"
```

### Task 6: Полная статическая и игровая проверка

**Files:**
- Modify only if a test exposes an economy regression in files already listed above.
- Inspect: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log`
- Inspect: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs/game.log`

**Interfaces:**
- Consumes: all deliverables from Tasks 1-5.
- Produces: evidence that static contracts, performance constraints, new-game accounting and actual GUI behavior work together.

- [ ] **Step 1: Run focused test suite**

```powershell
python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
python -B -m unittest tools.test_validate_adiscord_gui_contracts -v
python -B tools/validate_adiscord_economy_ai.py
```

Expected: all PASS and economy validator `OK`.

- [ ] **Step 2: Run project gates**

```powershell
python -B -m unittest discover -s tools -p 'test_*.py'
python -B tools/validate_tc.py --limit 300
git diff --check
```

Record unrelated baseline failures separately; do not weaken tests to hide them.

- [ ] **Step 3: Verify source-level performance contract**

Confirm the balanced `on_weekly` and `ADISCORD_economy_weekly_update` call tree contain no country/state iteration. Confirm `ADISCORD_economy_recount_economic_buildings` remains reachable only from full/dirty refresh, not weekly GUI refresh.

- [ ] **Step 4: Start a fresh HOI4 process and new game**

Clear or timestamp the previous log evidence, launch the mod, start a new 2160 game and inspect the real interface. Do not use a pre-change save as the only runtime check.

- [ ] **Step 5: Check runtime accounting dates**

At 1 January record initial treasury and weekly forecast. At 8 January verify the treasury delta equals the displayed weekly balance within display rounding. At 1 February confirm the month boundary does not add a second cash settlement. At 2 May verify cumulative treasury movement matches the sum of weekly periods and the accounting unexplained delta is zero.

- [ ] **Step 6: Check interaction and layout**

Verify:

```text
topbar shows icon + number without "Казна:"
clicking icon/number opens the dashboard
dashboard content remains after every click
four left/right arrow pairs render and work
all four active markers move across five steps
disabled arrows explain their state
left text blocks do not overlap
building counts fit on one line
treasury tooltip shows weekly breakdown and last-period identity
```

- [ ] **Step 7: Inspect fresh logs**

Search fresh logs for `ADISCORD_economy`, new sprite/widget names, modifier keys, scripted GUI errors, unknown effects/triggers and localization collisions. Classify pre-existing state/tag/army-icon/radio/frontend errors as unrelated baseline only when their timestamps and paths support that conclusion.

- [ ] **Step 8: Final review and commit only required corrections**

If runtime verification required fixes, rerun Steps 1-7 and commit the coherent correction set:

```powershell
git add -- common/on_actions/00_ADISCORD_on_actions.txt common/scripted_effects/ADISCORD_economy_effects.txt common/scripted_effects/ADISCORD_economy_modifier_effects.txt common/scripted_triggers/ADISCORD_economy_triggers.txt common/scripted_guis/ADISCORD_economy_scripted_gui.txt common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt common/synchronized_dynamic_tokens/ADISCORD_tokens.txt common/buildings/00_buildings.txt common/ai_strategy/ADISCORD_economy_ai.txt interface/ADISCORD_economy.gui interface/ADISCORD_economy.gfx localisation/russian/ADISCORD_economy_l_russian.yml localisation/russian/ADISCORD_economy_modifiers_l_russian.yml tools/test_adiscord_economy_weekly_contracts.py tools/test_validate_adiscord_gui_contracts.py tools/validate_adiscord_economy_ai.py docs/economy/economic-modifiers.md docs/economy/economic-buildings.md docs/economy/temporary-assets.md
git commit -m "fix: complete weekly economy runtime verification"
```

Do not commit logs, screenshots, save games or unrelated working-tree files.

## Deferred Follow-up: TFR Trade Integration

After this plan is complete, audit workshop `3350890356` as a separate design task. Compare `00_TFR_scripted_effects_ZZZ_trade_effects.txt`, `TFR_trade_econ` localization, the economy ledger and market decisions against A-Discord's existing resource-rent and trade-income formulas. The follow-up must propose no more than one player-facing trade decision loop and reuse existing trade screens where possible; it must not add another accounting dashboard or weekly state scan.
