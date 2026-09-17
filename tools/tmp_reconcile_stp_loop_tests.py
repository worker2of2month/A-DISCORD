from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str, *, encoding: str = "utf-8") -> None:
    target = ROOT / path
    text = target.read_text(encoding=encoding)
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old[:80]!r}; got {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding=encoding, newline="\n")


def patch_shared_fixture() -> None:
    replace_once(
        "tools/tests/test_adiscord_stp_preparation.py",
        '        if entry.key == "state":\n            return scope == entry.value\n',
        '        if entry.key == "state":\n            return scope == entry.value or facts.get((scope, "state", entry.value), False)\n',
    )


def patch_civil_war_tests() -> None:
    path = "tools/tests/test_adiscord_stp_civil_war.py"
    replace_once(
        path,
        '''            if event_id == "ADISCORD_STP_cw.20":\n                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.committed"]\n                self.assertEqual(len(closing), 1)\n                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],\n                                 "the committed-route option only closes the event")\n                options = [o for o in options if o not in closing]\n            self.assertEqual(len(options), len(choices))\n''',
        '''            if event_id == "ADISCORD_STP_cw.20":\n                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.committed"]\n                self.assertEqual(len(closing), 1)\n                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],\n                                 "the committed-route option only closes the event")\n                options = [o for o in options if o not in closing]\n            else:\n                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.42.c"]\n                self.assertEqual(len(closing), 1)\n                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],\n                                 "a stale intervention card must only close")\n                options = [o for o in options if o not in closing]\n            self.assertEqual(len(options), len(choices))\n''',
    )
    replace_once(
        path,
        '''            self.assertEqual(scalar(decision, "cost"), "0")\n            self.assertEqual(scalar(decision, "fire_only_once"), "no")\n            self.assertGreaterEqual(int(scalar(decision, "days_re_enable")), duration + 21)\n''',
        '''            self.assertEqual(scalar(decision, "cost"), "0")\n            if name == "STP_cw_launch_last_banquet":\n                self.assertEqual(scalar(decision, "fire_only_once"), "yes")\n                self.assertFalse(any(e.key == "days_re_enable" for e in decision))\n            else:\n                self.assertEqual(scalar(decision, "fire_only_once"), "no")\n                self.assertGreaterEqual(int(scalar(decision, "days_re_enable")), duration + 21)\n''',
    )


def patch_preparation_tests() -> None:
    path = "tools/tests/test_adiscord_stp_preparation.py"
    replace_once(
        path,
        '''                facts = {("STP", "has_completed_focus", "STP_Count_The_Loyalists"): True,\n                         ("STP", "has_active_mission", mission): True,\n                         ("STP", "STP_has_political_action_slot", "yes"): has_slot}\n''',
        '''                facts = {("STP", "has_completed_focus", "STP_Count_The_Loyalists"): True,\n                         ("STP", "has_active_mission", mission): True,\n                         ("STP", "STP_has_political_action_slot", "yes"): has_slot,\n                         ("FROM", "has_state_flag", "STP_party_inspection_active"): True,\n                         ("FROM", "state", str(state)): True}\n''',
    )
    replace_once(
        path,
        '''                self.assertEqual(scalar(decision, "fire_only_once"), "no")\n                available = block(decision, "available")\n''',
        '''                self.assertEqual(scalar(decision, "fire_only_once"),\n                                 "yes" if decision_id == "STP_cw_launch_last_banquet" else "no")\n                available = block(decision, "available")\n''',
    )
    replace_once(
        path,
        '''            if name == "STP_cw_delay_inspection":\n                facts[("STP", "has_active_mission", "STP_party_inspection_state_2")] = True\n''',
        '''            if name == "STP_cw_delay_inspection":\n                facts[("STP", "has_active_mission", "STP_party_inspection_state_2")] = True\n                facts[("FROM", "has_state_flag", "STP_party_inspection_active")] = True\n                facts[("FROM", "state", "2")] = True\n''',
    )


def patch_region_tests() -> None:
    replace_once(
        "tools/tests/test_adiscord_stp_regions.py",
        '''        self.assertNotIn("activate_mission", reward)\n        for state in OPERABLE_STATES:\n            self.assertIn(f"has_active_mission = STP_party_inspection_state_{state}", reward)\n''',
        '''        self.assertNotIn("activate_mission", reward)\n        self.assertIn("FROM = { has_state_flag = STP_party_inspection_active }", named_block(decision, "available"))\n        for state in OPERABLE_STATES:\n            self.assertIn(f"FROM = {{ state = {state} }}", reward)\n            self.assertEqual(reward.count(f"mission = STP_party_inspection_state_{state} days = 14"), 1)\n''',
    )


def patch_docs_and_localisation() -> None:
    replace_once(
        "docs/development/focus-effects.md",
        '''`STP_cw_last_banquet` и `STP_cw_guard_the_pier` открывают приказы в [существующем военном совете](../../common/decisions/ADISCORD_STP_decisions.txt). Само завершение фокуса не включает таймер. За 25 командного ресурса игрок запускает 21-дневное наступление либо 35-дневную оборону; требуются нужная война и контроль соответствующего региона. Перегруппировку на 21 день за те же 25 CP открывают `STP_cw_supply_routes` или `STP_cw_road_to_fada`. Проверка цены учитывает дробный запас: `NOT = { command_power < 25 }`. Наступление, оборона и перегруппировка взаимно исключаются и ждут окончания обеих идей стартовой подготовки.\n''',
        '''`STP_cw_last_banquet` и `STP_cw_guard_the_pier` открывают приказы в [существующем военном совете](../../common/decisions/ADISCORD_STP_decisions.txt). Само завершение фокуса не включает таймер. За 25 командного ресурса «Последний банкет» запускается один раз из контролируемого Ниансаса: наступательный бонус действует 21 день, и за тот же срок сопротивление должно взять Фаду, иначе теряет 10% поддержки войны. Успех закрывает ещё не начавшуюся интервенцию Нодрула. Оборона набережной остаётся повторяемым 35-дневным приказом. Перегруппировку на 21 день за те же 25 CP открывают `STP_cw_supply_routes` или `STP_cw_road_to_fada`. Проверка цены учитывает дробный запас: `NOT = { command_power < 25 }`. Наступление, оборона и перегруппировка взаимно исключаются и ждут окончания обеих идей стартовой подготовки.\n''',
    )
    path = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
    text = path.read_text(encoding="utf-8-sig")
    old = ' STP_cw_launch_last_banquet_desc: "Наступление требует войны с партией и контроля Ниансаса. Приказ стоит 25 командного ресурса; повторный запуск возможен через 42 дня. Во время наступления нельзя начать оборонительный план или перегруппировку."'
    new = ' STP_cw_launch_last_banquet_desc: "Наступление требует войны с партией и контроля Ниансаса. Приказ стоит 25 командного ресурса и отдаётся только один раз. После запуска есть §Y21 день§!, чтобы взять Фаду; провал срока снизит поддержку войны на §R10%§!. Во время операции нельзя начать оборонительный план или перегруппировку."'
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one Last Banquet decision description; got {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8-sig", newline="\n")


def main() -> None:
    patch_shared_fixture()
    patch_civil_war_tests()
    patch_preparation_tests()
    patch_region_tests()
    patch_docs_and_localisation()


if __name__ == "__main__":
    main()
