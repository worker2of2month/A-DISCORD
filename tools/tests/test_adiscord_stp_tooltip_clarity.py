from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import matches_conditions, scalar
from tools.tests.test_adiscord_stp_party_qol import StelanderDecisionTooltipTests
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
TOOLTIPS = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


class STPTooltipClarityTests(unittest.TestCase):
    def selected_text(self, name, facts):
        source = (
            ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
        ).read_text(encoding="utf-8-sig")
        definition = next(
            entry.value for entry in parse_clausewitz(source)
            if entry.key == "defined_text" and scalar(entry.value, "name") == name
        )
        for entry in definition:
            if entry.key != "text":
                continue
            trigger = next((e.value for e in entry.value if e.key == "trigger"), [])
            if matches_conditions(trigger, facts, "2"):
                return scalar(entry.value, "localization_key")
        self.fail(f"No text for {name}")

    def test_administration_countdown_uses_continuous_flag_age(self):
        flag = "STP_resistance_administration_asset"
        for age in range(22):
            with self.subTest(age=age):
                facts = {
                    ("2", "has_state_flag", flag): True,
                    ("2", "flag_days", flag): age,
                }
                asset = self.selected_text("STPGetAdministrationAsset", facts)
                if age >= 21:
                    self.assertEqual(asset, "STP_REGION_ASSET_ADMINISTRATION_READY")
                else:
                    self.assertEqual(asset, "STP_REGION_ASSET_ADMINISTRATION_RECENT")
                    self.assertEqual(
                        self.selected_text("STPGetAdministrationDaysRemaining", facts),
                        f"STP_REGION_ADMIN_DAYS_{21 - age}",
                    )
        self.assertEqual(
            self.selected_text("STPGetAdministrationAsset", {}),
            "STP_REGION_EMPTY_LINE",
        )

    def test_ready_cache_and_pending_delivery_can_both_be_reported(self):
        facts = {
            ("2", "variable", "STP_cw_cached_rifles"): 480,
            ("2", "variable", "STP_cw_pending_rifles"): 960,
        }
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_CW_CACHE_READY")
        self.assertEqual(self.selected_text("STPGetPendingRifleCache", facts), "STP_CW_CACHE_PENDING")
        facts[("2", "variable", "STP_cw_cached_rifles")] = 0
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_CW_CACHE_PENDING")
        facts[("2", "variable", "STP_cw_pending_rifles")] = 0
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_REGION_EMPTY_LINE")

    def test_concession_is_reported_before_waiting_but_never_overrides_transfer(self):
        facts = {
            ("2", "has_state_flag", "STP_inspection_concession_prepared"): True,
            ("2", "STP_region_resistance_entrenched", "yes"): True,
            ("2", "has_state_flag", "STP_resistance_administration_asset"): True,
        }
        self.assertEqual(
            self.selected_text("STPGetCivilWarForecastReason", facts),
            "STP_CW_FORECAST_REASON_CONCESSION",
        )
        facts[("2", "STP_cw_region_goes_to_resistance", "yes")] = True
        facts[("2", "STP_region_resistance_overwhelming", "yes")] = True
        self.assertEqual(
            self.selected_text("STPGetCivilWarForecastReason", facts),
            "STP_CW_FORECAST_REASON_OVERWHELMING",
        )

    def test_niansas_transfer_requirements_are_explicit_at_every_decision_point(
        self,
    ) -> None:
        self.assertTrue(TOOLTIPS.is_file(), "missing canonical STP localisation")
        self.assertTrue(
            TOOLTIPS.read_bytes().startswith(b"\xef\xbb\xbf"),
            "tooltip override must keep UTF-8 BOM",
        )
        localisation = TOOLTIPS.read_text(encoding="utf-8-sig")

        required_keys = (
            "STP_regions_panel_tt",
            "STP_region_3_map_tt",
            "STP_cw_repair_niansas_desc",
            "STP_cw_port_budget_desc",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertEqual(
                    len(re.findall(rf"(?m)^\s*{re.escape(key)}:\s*", localisation)), 1
                )

        for phrase in (
            "90%",
            "21 день",
            "выше §Y55%§!",
            "Дорога через Ниансас",
            "Перехватить областное управление",
            "положительного перевеса легитимности",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, localisation)

        niansas_tooltip = re.search(
            r'(?ms)^\s*STP_region_3_map_tt:\s*"(?P<body>.*?)"\s*$', localisation
        )
        self.assertIsNotNone(niansas_tooltip)
        body = niansas_tooltip.group("body")
        self.assertIn("§YТекущий прогноз при восстании:§!", body)
        self.assertIn("[3.STPGetCivilWarForecast]", body)
        self.assertIn("[3.STPGetCivilWarForecastReason]", body)
        self.assertIn("[3.STPGetAdministrationAsset]", body)


class STPFocusTooltipTests(StelanderDecisionTooltipTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.focuses = {}

        def collect(entries):
            for entry in entries:
                if entry.key == "focus" and isinstance(entry.value, list):
                    cls.focuses[scalar(entry.value, "id")] = entry.value
                elif isinstance(entry.value, list):
                    collect(entry.value)

        for path in (ROOT / "focus_trees/STP").rglob("*.txt"):
            collect(parse_clausewitz(path.read_text(encoding="utf-8")))

    def test_focus_conditions_and_rewards_do_not_expand_bookkeeping(self):
        self.assertGreater(len(self.focuses), 600)
        for name, entries in self.focuses.items():
            for entry in entries:
                if entry.key in ("available", "bypass", "select_effect", "completion_reward"):
                    with self.subTest(focus=name, field=entry.key):
                        self.assertEqual(list(self.exposed_bookkeeping(entry.value)), [])

    def test_focus_condition_labels_exist_in_both_languages(self):
        pattern = r'^\s+([\w.]+):\d*[ \t]*"([^"\r\n]*)"'
        for language in ("russian", "english"):
            values = dict(re.findall(pattern, (
                ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            ).read_text(encoding="utf-8-sig"), re.M))
            for name in self.localisation:
                if name.startswith("STP_focus_"):
                    with self.subTest(language=language, key=name):
                        self.assertTrue(values.get(name))

    def test_native_research_slots_and_decision_deliveries_are_not_repeated(self):
        for name in ("STP_pc_development_reopen_universities",
                     "STP_pc_development_national_research_institutes"):
            reward = next(e.value for e in self.focuses[name] if e.key == "completion_reward")
            self.assertEqual(scalar(reward, "add_research_slot"), "1")
            self.assertNotIn("ячейк", self.localisation[name + "_tt"])
        removed = {
            "STP_cw_repair_rifle_batch_unlock_summary_tt",
            "STP_cw_train_reserve_brigades_unlock_summary_tt",
            "STP_pm_order_attack_aircraft_unlock_summary_tt",
            "STP_pm_order_fighters_unlock_summary_tt",
        }
        for name, entries in self.focuses.items():
            reward = next((e.value for e in entries if e.key == "completion_reward"), [])
            for entry in reward:
                if entry.key == "custom_effect_tooltip":
                    self.assertNotIn(entry.value, removed, name)

    def test_hidden_treasury_grants_keep_their_amount_visible(self):
        for name in ("STP_pc_economy_count_the_cost", "STP_pc_economy_recovery_budget"):
            reward = next(e.value for e in self.focuses[name] if e.key == "completion_reward")
            self.assertIn("STP_pw_treasury_900_tt", [
                e.value for e in reward if e.key == "custom_effect_tooltip"
            ])
        self.assertIn("§G+900§! £ADISCORD_economy_treasury_texticon",
                      self.localisation["STP_pw_treasury_900_tt"])
        for key in ("STP_cw_officers_tt", "STP_cw_early_orders_tt", "STP_cw_young_officers_tt"):
            self.assertIn("£army_experience", self.localisation[key])
            self.assertNotIn("опыта армии", self.localisation[key])


class STPEventOptionTooltipTests(StelanderDecisionTooltipTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8")
        cls.options = {
            (scalar(event.value, "id"), scalar(option.value, "name")): option.value
            for event in parse_clausewitz(source)
            if isinstance(event.value, list)
            for option in event.value if option.key == "option"
        }

    def visible_nodes(self, entries, stack=()):
        for entry in entries:
            if entry.key in ("hidden_effect", "hidden_trigger", "trigger", "ai_chance"):
                continue
            yield entry
            if entry.key in self.definitions and entry.key not in stack:
                yield from self.visible_nodes(self.definitions[entry.key], stack + (entry.key,))
            elif isinstance(entry.value, list):
                yield from self.visible_nodes(entry.value, stack)

    def test_event_options_do_not_expose_bookkeeping(self):
        self.assertGreater(len(self.options), 400)
        for name, entries in self.options.items():
            payload = [entry for entry in entries if entry.key not in (
                "name", "trigger", "ai_chance", "highlight", "default_option"
            )]
            with self.subTest(option=name):
                self.assertEqual(list(self.exposed_bookkeeping(payload)), [])

    def test_custom_resource_prices_and_refund_conditions_remain_visible(self):
        nodes = list(self.visible_nodes(self.options[("ADISCORD_STP_pc.81", "ADISCORD_STP_pc.81.a")]))
        self.assertIn("STP_event_treasury_300_cost_tt", [
            n.value for n in nodes if n.key == "custom_effect_tooltip"
        ])
        self.assertEqual([n.value for n in nodes if n.key == "add_political_power"], ["-40"])
        for event in ("ADISCORD_STP_pc.65", "ADISCORD_STP_pc.80"):
            nodes = list(self.visible_nodes(self.options[(event, "ADISCORD_STP_pc.5.closed")]))
            self.assertIn("STP_event_justice_payment_tt", [n.value for n in nodes if n.key == "tooltip"])
            self.assertIn("50", [n.value for n in nodes if n.key == "add_political_power"])

    def test_decision_unlocks_keep_their_details_in_the_decisions(self):
        for name, entries in self.options.items():
            for node in self.visible_nodes(entries):
                if node.key == "unlock_decision_tooltip":
                    with self.subTest(option=name):
                        self.assertIsInstance(node.value, str)

    def test_option_tooltip_numbers_and_texticons_are_valid_in_both_languages(self):
        keys = {
            node.value for entries in self.options.values() for node in self.visible_nodes(entries)
            if node.key in ("custom_effect_tooltip", "tooltip") and isinstance(node.value, str)
        }
        sprites = set()
        for path in (ROOT / "interface").glob("*.gfx"):
            sprites.update(re.findall(r'name\s*=\s*"GFX_(\w+)"', path.read_text(encoding="utf-8-sig")))
        for language in ("russian", "english"):
            values = {}
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                values.update(dict(re.findall(
                    r'^ ([\w.]+):\d*[ \t]*"([^"\r\n]*)"',
                    path.read_text(encoding="utf-8-sig"), re.M
                )))
            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertTrue(values.get(key), "Missing option tooltip")
                    value = values[key]
                    for icon in re.findall(r'£(\w+)', value):
                        self.assertIn(icon, sprites)
                    plain = re.sub(r'§[A-Za-z0-9][^§]*§!|\[[^]]*\]|\$[\w.]+\$|£\w+', '', value)
                    self.assertNotRegex(plain, r'(?<![\w.,])\d+(?:[.,]\d+)?%?(?![\w]|[.,]\d)')
            self.assertEqual(values["STP_event_treasury_300_cost_tt"],
                             "§R-300§! £ADISCORD_economy_treasury_texticon")


class STPSpiritTooltipTests(StelanderDecisionTooltipTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = (ROOT / "common/ideas/ADISCORD_STP_civil_war_ideas.txt").read_text(encoding="utf-8")
        cls.spirits = {
            idea.key: idea.value for outer in parse_clausewitz(source)
            for group in outer.value if group.key == "country" for idea in group.value
        }
        cls.spirits.update({entry.key: entry.value for entry in parse_clausewitz(
            (ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt").read_text(encoding="utf-8")
        )})

    def test_spirit_conditions_and_lifecycle_effects_hide_bookkeeping(self):
        self.assertGreater(len(self.spirits), 400)
        for name, entries in self.spirits.items():
            for entry in entries:
                if entry.key in ("allowed", "available", "cancel", "enable", "on_add", "on_remove"):
                    with self.subTest(spirit=name, field=entry.key):
                        self.assertEqual(list(self.exposed_bookkeeping(entry.value)), [])

    def test_spirit_names_and_cancellation_labels_are_localised(self):
        for language in ("russian", "english"):
            values = {}
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                values.update(dict(re.findall(
                    r'^ ([\w.]+):\d*[ \t]*"([^"\r\n]*)"',
                    path.read_text(encoding="utf-8-sig"), re.M
                )))
            for name, entries in self.spirits.items():
                key = next((e.value for e in entries if e.key == "name"), name)
                with self.subTest(language=language, spirit=name):
                    self.assertTrue(values.get(key))
                    self.assertNotRegex(values[key], r'\b(?:STP|STS|SRP)_[A-Za-z0-9_]+')
            for key in self.localisation:
                if key.startswith("STP_spirit_"):
                    self.assertTrue(values.get(key), (language, key))

    def test_native_effects_are_not_repeated_but_future_timers_remain(self):
        for language in ("russian", "english"):
            values = dict(re.findall(r'^ ([\w.]+):\d*[ \t]*"([^"\r\n]*)"', (
                ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            ).read_text(encoding="utf-8-sig"), re.M))
            for key in ("SRP_council_supply_desc", "STP_cw_central_authority_desc",
                        "STP_cw_arsenal_shifts_desc", "STP_cw_prepared_supply_lines_desc"):
                self.assertNotRegex(values[key], r'\d', (language, key))
            self.assertNotIn("[?STP_ps_", values["STP_ps_defence_dynamic_desc"])
            for key in ("STP_kc_defence_prepared_desc", "STP_pw_party_nod_staff_prepared_desc"):
                self.assertIn("§Y180§!", values[key])
            self.assertIn("£stability_texticon", values["STP_apparatus_faction_effects"])
            for variable in ("conservatives", "borons", "security", "army", "advisers", "merchants", "radicals"):
                self.assertIn("[?STP_pf_" + variable + "_effect|", values["STP_apparatus_faction_effects"])


if __name__ == "__main__":
    unittest.main()
