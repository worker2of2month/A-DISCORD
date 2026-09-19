"""Apply reviewed, assertion-guarded edits in an isolated source checkout."""
from pathlib import Path
import ast
import re
import shutil
import subprocess
import sys

ROOT = Path.cwd()
CONTROL = Path(__file__).resolve().parent
CHANGED = set()


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def write(path, text):
    file = ROOT / path
    bom = file.exists() and file.read_bytes().startswith(b"\xef\xbb\xbf")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    CHANGED.add(path)


def end_block(text, start):
    opening = text.index("{", start)
    depth = 0
    quoted = escaped = comment = False
    for pos in range(opening, len(text)):
        char = text[pos]
        if comment:
            if char == "\n": comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == '"': quoted = False
            continue
        if char == '#': comment = True
        elif char == '"': quoted = True
        elif char == '{': depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0: return pos + 1
    raise AssertionError("unclosed block")


def named_span(text, name):
    matches = list(re.finditer(r"(?m)^[ \t]*" + re.escape(name) + r"\s*=\s*\{", text))
    assert len(matches) == 1, (name, len(matches))
    start = matches[0].start()
    return start, end_block(text, start)


def edit_named(path, name, operation):
    text = read(path)
    start, end = named_span(text, name)
    original = text[start:end]
    revised = operation(original)
    assert revised != original, name
    write(path, text[:start] + revised + text[end:])


def edit_focus(path, name, operation):
    text = read(path)
    match = re.search(r"\bid\s*=\s*" + re.escape(name) + r"\b", text)
    assert match, name
    opening = list(re.finditer(r"(?m)^[ \t]*focus\s*=\s*\{", text[:match.start()]))[-1].start()
    end = end_block(text, opening)
    original = text[opening:end]
    revised = operation(original)
    assert revised != original, name
    write(path, text[:opening] + revised + text[end:])


def once(text, before, after):
    assert text.count(before) == 1, (before, text.count(before))
    return text.replace(before, after, 1)


def add_at_end(body, lines):
    return body[:-1].rstrip() + "\n" + lines + "\n}"


def set_loc(path, key, value):
    text = read(path)
    pattern = r'(?m)^([ \t]*' + re.escape(key) + r':(?:\d+)?[ \t]*)".*"[ \t]*$'
    matches = list(re.finditer(pattern, text))
    assert len(matches) == 1, (path, key, len(matches))
    match = matches[0]
    write(path, text[:match.start()] + match.group(1) + '"' + value + '"' + text[match.end():])


def run_tests(module):
    process = subprocess.run([sys.executable, "-B", "-m", "unittest", module, "-v"], text=True, capture_output=True)
    print(process.stdout, process.stderr, flush=True)
    return process


new_test = "tools/tests/test_adiscord_economy_balance.py"
write(new_test, (CONTROL / "economy_balance_tests.py").read_text(encoding="utf-8"))
print("RED: new behavior on the unmodified implementation", flush=True)
red = run_tests("tools.tests.test_adiscord_economy_balance")
assert red.returncode != 0, "regressions did not fail on baseline"
assert "ERROR:" not in red.stderr, "fix fixture errors before editing production"

EFFECTS = "common/scripted_effects/ADISCORD_economy_effects.txt"
MODIFIERS = "common/scripted_effects/ADISCORD_economy_modifier_effects.txt"
VAL_EFFECTS = "common/scripted_effects/ADISCORD_VAL_effects.txt"
VAL_FOCUS = "common/national_focus/ADISCORD_national_focus_VAL.txt"
STP_FOCUS = "common/national_focus/ADISCORD_national_focus_STP.txt"
STP_IDEAS = "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
STP_LOC = "localisation/russian/ADISCORD_STP_l_russian.yml"
VAL_LOC = "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"

# Raw production/tax bases are converted once, after their bounded source
# modifiers. The cached tax-only path uses the identical conversion.
helper = """# Monthly fiscal units for the four tax-sensitive source buckets. Raw policy
# bases remain unscaled so changing taxes cannot compound a previous forecast.
ADISCORD_economy_scale_taxable_income = {
\tmultiply_variable = { var = ADISCORD_economy_personal_income value = 16 }
\tmultiply_variable = { var = ADISCORD_economy_business_income value = 16 }
\tmultiply_variable = { var = ADISCORD_economy_consumer_goods_income value = 16 }
\tmultiply_variable = { var = ADISCORD_economy_factory_income value = 16 }
}

"""
text = read(MODIFIERS)
start, _ = named_span(text, "ADISCORD_economy_apply_income_modifier_factors")
write(MODIFIERS, text[:start] + helper + text[start:])
edit_named(MODIFIERS, "ADISCORD_economy_apply_income_modifier_factors", lambda body: add_at_end(body,
    "\tADISCORD_economy_scale_taxable_income = yes\n"
    "\tmultiply_variable = { var = ADISCORD_economy_resource_income value = 16 }\n"
    "\tmultiply_variable = { var = ADISCORD_economy_building_income value = 16 }"))
edit_named(EFFECTS, "ADISCORD_economy_recalculate_tax_dependent_income", lambda body: once(body,
    "\tset_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_personal_income }",
    "\tADISCORD_economy_scale_taxable_income = yes\n\tset_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_personal_income }"))
expense_sources = ("army", "airforce", "navy", "military_factory", "construction", "social", "research", "admin", "repair")
edit_named(MODIFIERS, "ADISCORD_economy_apply_expense_modifier_factors", lambda body: add_at_end(body,
    "\t# Operating appropriations have real fiscal weight. Interest is already\n"
    "\t# denominated in treasury units and must retain debt * annual_rate / 1200.\n" +
    "\n".join("\tmultiply_variable = { var = ADISCORD_economy_" + key + "_expenses value = 4 }" for key in expense_sources)))

# Each industrial recovery programme restores a bounded recurring order book.
edit_named(VAL_EFFECTS, "VAL_refresh_industrial_economy", lambda body: body.replace("{", "{\n\tset_variable = { var = VAL_industrial_weekly_income value = 0 }", 1))
edit_named(VAL_EFFECTS, "VAL_refresh_industrial_economy", lambda body: once(body,
    "\tremove_ideas = VAL_vorkerland_contract_disruptions",
    "\tif = {\n\t\tlimit = { has_country_flag = VAL_vorkerland_contracts_disrupted }\n"
    "\t\tset_variable = { var = VAL_industrial_weekly_income value = VAL_economic_recovery_steps }\n"
    "\t\tmultiply_variable = { var = VAL_industrial_weekly_income value = 4 }\n\t}\n"
    "\tremove_ideas = VAL_vorkerland_contract_disruptions"))
for path in (ROOT / "common/dynamic_modifiers").glob("*VAL*"):
    relative = path.relative_to(ROOT).as_posix()
    for name in ("VAL_contract_industry", "VAL_economic_collapse", "VAL_economic_miracle"):
        if re.search(r"(?m)^" + name + r"\s*=", read(relative)):
            edit_named(relative, name, lambda body: add_at_end(body,
                "\tADISCORD_economy_weekly_income = VAL_industrial_weekly_income"))
edit_named("common/ideas/ADISCORD_VAL_rework_ideas.txt", "VAL_economic_recovery_delta",
    lambda body: once(body, "modifier = {", "modifier = {\n\t\t\tADISCORD_economy_weekly_income = 4"))
edit_focus(VAL_FOCUS, "VAL_Export_Clearing_House", lambda body: once(body, "ADISCORD_economy_receive_15 = yes", "ADISCORD_economy_receive_100 = yes"))

# Five distinct programmes update the existing republican dynamic modifier.
reforms = {
    "count_the_cost": {
        "STP_pw_ADISCORD_economy_overall_income_factor": ("0.03", "0.10"),
        "STP_pw_ADISCORD_economy_treasury_capacity_factor": ("0.03", "0.10"),
    },
    "reopen_tax_offices": {
        "STP_pw_ADISCORD_economy_overall_income_factor": ("0.05", "0.20"),
        "STP_pw_ADISCORD_economy_admin_expense_factor": ("-0.03", "-0.10"),
    },
    "repair_workshops": {
        "STP_pw_production_speed_industrial_complex_factor": ("0.05", "0.15"),
        "STP_pw_ADISCORD_economy_treasury_capacity_factor": ("0.05", "0.10"),
    },
    "stabilize_currency": {
        "STP_pw_ADISCORD_economy_creditworthiness_factor": ("0.08", "0.15"),
        "STP_pw_ADISCORD_economy_treasury_capacity_factor": ("0.02", "0.10"),
    },
    "recovery_budget": {
        "STP_pw_ADISCORD_economy_overall_income_factor": ("0.07", "0.20"),
        "STP_pw_ADISCORD_economy_treasury_capacity_factor": ("0.05", "0.20"),
        "STP_pw_ADISCORD_economy_admin_expense_factor": ("-0.02", "-0.05"),
        "STP_pw_ADISCORD_country_development_economic_growth_factor": ("0.08", "0.15"),
    },
}
dummy_bodies = []
for suffix, changes in reforms.items():
    focus_id = "STP_pc_economy_" + suffix
    def revise(body, changes=changes, focus_id=focus_id, suffix=suffix):
        for variable, (old, new) in changes.items():
            body = once(body, "var = " + variable + " value = " + old, "var = " + variable + " value = " + new)
        marker = "custom_effect_tooltip = " + focus_id + "_tt"
        preview = "effect_tooltip = { add_ideas = " + focus_id + "_delta }"
        if suffix in ("count_the_cost", "stabilize_currency"):
            body = once(body, marker, marker + "\n\t\t\t" + preview)
        else:
            body = once(body, marker, preview)
        if suffix == "repair_workshops":
            body = once(body, "\t\t\thidden_effect = {", "\t\t\thidden_effect = {\n\t\t\t\tadd_to_variable = { var = STP_pw_ADISCORD_economy_overall_income_factor value = 0.10 }")
        if suffix == "stabilize_currency":
            body = once(body, "var = ADISCORD_economy_inflation value = -3", "var = ADISCORD_economy_inflation value = -6")
            body = once(body, "var = ADISCORD_economy_deficit_pressure value = -5", "var = ADISCORD_economy_deficit_pressure value = -10")
        return body
    edit_focus(STP_FOCUS, focus_id, revise)
    modifiers = {key.removeprefix("STP_pw_"): pair[1] for key,pair in changes.items()}
    if suffix == "repair_workshops": modifiers["ADISCORD_economy_overall_income_factor"] = "0.10"
    dummy_bodies.append("\t\t" + focus_id + "_delta = {\n\t\t\tallowed = { always = no }\n\t\t\tmodifier = {\n" +
                        "\n".join("\t\t\t\t" + key + " = " + value for key,value in modifiers.items()) + "\n\t\t\t}\n\t\t}")
text = read(STP_IDEAS)
start,end = named_span(text, "country")
write(STP_IDEAS, text[:end-1] + "\n\t\t# Postwar programme deltas are previews, never installed national spirits.\n" + "\n".join(dummy_bodies) + "\n\t" + text[end-1:])
text = read(STP_LOC)
write(STP_LOC, text.rstrip() + "\n" + "\n".join(' STP_pc_economy_' + suffix + '_delta: "Изменение программы восстановления"' for suffix in reforms) + "\n")
set_loc(STP_LOC, "STP_pc_economy_count_the_cost_tt", "Экономика будет немедленно пересчитана по всей объединённой территории.")
set_loc(STP_LOC, "STP_pc_economy_reopen_tax_offices_tt", "Единый реестр плательщиков расширяет постоянную доходную базу и сокращает стоимость управления.")
set_loc(STP_LOC, "STP_pc_economy_repair_workshops_tt", "Гражданское производство расширяет налоговую базу. При отсутствии места для фабрики государство получает денежную компенсацию, указанную в награде.")
set_loc(STP_LOC, "STP_pc_economy_stabilize_currency_tt", "Инфляция: §G-6§!. Давление дефицита: §G-10§!. Значения не могут стать отрицательными.")
set_loc(STP_LOC, "STP_pc_economy_recovery_budget_tt", "Доходы и расходы программы изменяются постоянно. Разовая выплата не заменяет её долгосрочный бюджетный результат.")

# Both AI entry points use actual fielded manpower, replenishment and fiscal
# solvency. The ordinary crisis label is not itself a permanent war veto.
ready = """
# COUNTRY VAL: shared readiness for issuing an ultimatum and acting on refusal.
VAL_ai_frontier_ready = {
\thas_capitulated = no
\tis_subject = no
\thas_war = no
\thas_army_manpower = { size > 59999 }
\tNOT = { has_equipment = { infantry_equipment < 1500 } }
\tcheck_variable = { var = ADISCORD_economy_treasury value = 25 compare = greater_than_or_equals }
\tcheck_variable = { var = ADISCORD_economy_debt_state value = 3 compare = less_than }
}
"""
triggers = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
write(triggers, read(triggers).rstrip() + "\n" + ready)
for target in ("CIN", "OSF", "APH", "ERT"):
    edit_named("common/decisions/ADISCORD_VAL_decisions.txt", "VAL_frontier_demand_" + target,
        lambda body: once(body,
            "ai_will_do = { base = 3 modifier = { factor = 0 num_divisions < 24 } modifier = { factor = 0 ADISCORD_economy_ai_is_crisis = yes } }",
            "ai_will_do = { base = 10 modifier = { factor = 0 NOT = { VAL_ai_frontier_ready = yes } } }"))
events = "events/ADISCORD_VAL_contract_events.txt"
text = read(events)
text = once(text,
    "ai_chance = { base = 70 modifier = { factor = 0 num_divisions < 24 } modifier = { factor = 0.3 has_manpower < 20000 } }",
    "ai_chance = { base = 90 modifier = { factor = 0 NOT = { VAL_ai_frontier_ready = yes } } modifier = { factor = 0.3 has_manpower < 20000 } }")
# Keep withdrawal possible, but do not make an already prepared campaign a
# near coin toss after the AI has paid for its diplomatic opening.
text = once(text, "ai_chance = { base = 30 } hidden_effect = { if = { limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } } VAL_frontier_close = yes } }",
    "ai_chance = { base = 10 } hidden_effect = { if = { limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } } VAL_frontier_close = yes } }")
write(events, text)
for focus_id, weight, short in (
    ("VAL_The_Steel_Contract", 20, False),
    ("VAL_frontier_conference", 18, True), ("VAL_frontier_logistics", 18, True),
    ("VAL_frontier_commissioners", 16, True), ("VAL_frontier_provincial_offices", 16, True),
    ("VAL_frontier_security_plan", 24, True),
):
    def priority(body, weight=weight, short=short, focus_id=focus_id):
        body, count = re.subn(r"ai_will_do\s*=\s*\{\s*base\s*=\s*\d+\s*\}", "ai_will_do = { base = " + str(weight) + " }", body)
        assert count == 1, focus_id
        if short: body = once(body, "cost = 5", "cost = 3")
        if focus_id == "VAL_frontier_security_plan":
            body = once(body, "available = { has_completed_focus = VAL_frontier_logistics }", "prerequisite = { focus = VAL_frontier_logistics }")
        return body
    edit_focus(VAL_FOCUS, focus_id, priority)
for key, title, description in (
    ("VAL_Vorkerland_Contracts_Burn", "Антикризисная комиссия", "Воркерландский рынок исчез вместе с прежними заказчиками. Комиссия отделит исполнимые заказы от безнадёжных требований, восстановит расчёты с работающими предприятиями и вернёт казне первые регулярные поступления."),
    ("VAL_Inventory_The_Empty_Yards", "Инвентаризация промышленности", "Государству нужен реестр действующих станков, рабочих и запасов, а не довоенная отчётность. Подтверждённые мощности получат новые заказы и войдут в программу восстановления."),
    ("VAL_Mobilize_Machine_Shops", "Поддержать ремонтные мастерские", "Мастерские вернут в строй простаивающие линии и обеспечат предприятия запасными частями. Подрядчики получат оплачиваемую работу, а государство восстановит часть постоянного контрактного дохода."),
    ("VAL_Three_Shift_Arsenals", "Возобновить серийный выпуск", "Возвращение серийного производства требует устойчивого снабжения, исправных станков и регулярной оплаты труда. Возобновлённые поставки расширят работающий портфель заказов."),
    ("VAL_Reserve_Accounting", "Обеспечить исполнение контрактов", "Заказчики должны видеть не обещания, а учтённые запасы и гарантированные сроки. Резервные партии оружия обеспечат исполнение договоров и восстановят регулярные расчёты."),
):
    set_loc(VAL_LOC, key, title)
    set_loc(VAL_LOC, key + "_desc", description)

# Preserve the already-authored stronger austerity schedule and bind validators
# to its exact five values instead of reverting the gameplay change.
validator = "tools/validators/validate_adiscord_economy_ai.py"
text = read(validator)
node = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name == "research_policy_flow_issues")
lines = text.splitlines(keepends=True)
body = "".join(lines[node.lineno-1:node.end_lineno])
revised = re.sub(r"(?<![\w.])0\.60?(?!\d)", "0.30", body)
revised = re.sub(r"(?<![\w.])0\.80?(?!\d)", "0.65", revised)
assert revised != body
lines[node.lineno-1:node.end_lineno] = [revised]
write(validator, "".join(lines))
tests = "tools/tests/test_adiscord_economy_weekly_contracts.py"
text = read(tests)
node = next(node for node in ast.walk(ast.parse(text)) if isinstance(node,ast.FunctionDef) and node.name == "test_live_research_policy_localisation_uses_canonical_ui_ids")
lines = text.splitlines(keepends=True)
body = "".join(lines[node.lineno-1:node.end_lineno])
revised = body.replace("§G-40%§!", "§G-70%§!").replace("§G-20%§!", "§G-35%§!")
assert revised != body
lines[node.lineno-1:node.end_lineno] = [revised]
write(tests, "".join(lines))
set_loc("localisation/english/ADISCORD_economy_l_english.yml", "ADISCORD_economy_research_controls_tt",
    "§YRESEARCH FUNDING — expenditure and research speed§!\\nCurrent level: [?ADISCORD_economy_research_spending_mode|0]/5 — [GetADISCORDResearchSpendingModeLoc]\\n\\n[GetADISCORDResearchSpendingEffectsLoc]\\n\\nResearch expenditure at levels 1–5: §G-70%§! / §G-35%§! / §Y0%§! / §R+30%§! / §R+60%§!.\\nResearch speed: §R-8%§! / §R-3%§! / §Y0%§! / §G+3%§! / §G+5%§!. Only level 5 also grants construction speed §G+2%§!.\\n\\nNext change in: [?ADISCORD_economy_research_budget_change_cooldown|0] months.")

doc = "docs/economy/economy-player-and-runtime.md"
write(doc, read(doc).rstrip() + """

## Масштаб доходов и достижимый профицит

Базы производительности остаются внутренними расчётными величинами. После
отраслевых модификаторов каждый из шести источников дохода переводится в
месячные фискальные единицы с коэффициентом 16. Операционные расходы,
включая ремонт, используют коэффициент 4. Проценты не масштабируются:
месячное обслуживание по-прежнему равно долгу, умноженному на годовую
ставку и делённому на 1200, с последующим модификатором обслуживания.
Недельный перевод остаётся точным `3 / 13`; разовые цены не переоцениваются.
Это увеличение покупательной способности бюджета, а не деноминация.

Кэш налоговых баз хранит немасштабированные значения. Полный пересчёт и
налоговый предпросмотр одинаково переводят четыре налоговых источника;
неналоговый кэш уже содержит переведённую ренту и доход зданий. Повторный
пересчёт не может второй раз умножить выручку или расходы.

Цель развитой региональной экономики — достижимый устойчивый профицит
100 единиц в неделю при штатном финансировании армии, науки и социальных
расходов. Это не стартовая гарантия каждому тегу. Развитие предприятий,
деловых центров, сырьевой базы и завершение экономических реформ должны
оставаться значимыми. Проверки в `test_adiscord_economy_balance.py` исполняют
арифметический срез действующих скриптов с явно заданными входами, включая
содержание полевой армии, авиации, флота и обслуживание долга. Они не
заменяют проверку темпа кампании и интерфейса в движке.
""")
doc = "docs/development/focus-effects.md"
write(doc, read(doc).rstrip() + """

## Доход восстановления и северная готовность

Шесть промышленных программ VAL дополнительно возвращают по 4 единицы
еженедельного контрактного дохода, до 24 на последней ступени.
`VAL_refresh_industrial_economy` заново выводит этот доход из текущей
ступени, а три состояния промышленности читают одну переменную
`VAL_industrial_weekly_income`. Повторное обновление не накапливает выплату.
Предкризисные вложения не считаются выполненными программами восстановления.

Пять экономических фокусов Шабрата увеличивают общий доход суммарно на
60 процентных пунктов, ёмкость казны на 60, сокращают административные
расходы на 15. Мастерские дополнительно ускоряют гражданское строительство
на 15%, денежная стабилизация снижает инфляцию на 6 и давление дефицита
на 10, повышает кредитоспособность на 15%. Итоговый бюджет добавляет 15%
роста экономического развития. Native dummy-превью показывают точную
прибавку каждой программы и никогда не устанавливаются как идеи.

`VAL_ai_frontier_ready` един для северных ультиматумов и решения о войне
после отказа: некапитулировавшая независимая страна в мире, полевая армия
не менее 60000 человек, не менее 1500 резервных винтовок, 25 единиц казны
и долговое состояние ниже чрезвычайного. Общий флаг экономического кризиса
сам по себе не запрещает кампанию. Условия ответа страны-цели, состав
коалиции, послевоенные ограничения и право игрока отказаться сохраняются.
""")
print("CHANGED_PATHS", sorted(CHANGED), flush=True)
(ROOT.parent / "changed-paths.txt").write_text("\n".join(sorted(CHANGED)) + "\n", encoding="utf-8")
print("GREEN: material budget and focus regressions", flush=True)
green = run_tests("tools.tests.test_adiscord_economy_balance")
assert green.returncode == 0, "new behavior failed; do not commit"
subprocess.run(["git", "diff", "--check"], check=True)
print("PATCH_READY", flush=True)
