from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import block, scalar, walk


ROOT = Path(__file__).resolve().parents[2]
FOCUS_DIR = ROOT / "common" / "national_focus"


class FocusTooltipCompactnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = {}
        for path in FOCUS_DIR.glob("*.txt"):
            for entry in walk(parse_clausewitz(path.read_text(encoding="utf-8-sig"))):
                if entry.key in ("focus", "shared_focus") and isinstance(entry.value, list):
                    cls.focuses[scalar(entry.value, "id")] = entry.value
        cls.stp_decisions = parse_clausewitz(
            (ROOT / "common/decisions/ADISCORD_STP_decisions.txt").read_text(encoding="utf-8")
        )
        cls.localisation = {}
        for language in ("russian", "english"):
            source = (ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml").read_text(
                encoding="utf-8-sig"
            )
            cls.localisation[language] = dict(
                re.findall(r'^\s*([^:\s]+):\d*\s+"(.*)"\s*$', source, re.M)
            )

    def test_delayed_event_previews_state_the_actual_delay(self) -> None:
        for focus_id in (
            "STP_pc_heg_personal_oath",
            "STP_pc_heg_rewrite_mandate",
            "STP_pc_heg_public_trial",
            "STP_pc_heg_closed_session",
        ):
            reward = block(self.focuses[focus_id], "completion_reward")
            days = scalar(block(reward, "country_event"), "days")
            tooltip = f"{focus_id}_delay_tt"
            with self.subTest(focus=focus_id):
                self.assertIn(tooltip, [e.value for e in reward if e.key == "custom_effect_tooltip"])
                for language, entries in self.localisation.items():
                    with self.subTest(language=language):
                        self.assertIn(f"§Y{days}", entries.get(tooltip, ""))

    def test_audit_unlock_preview_matches_the_selected_decision_method(self) -> None:
        reward = block(self.focuses["STP_pc_charter_tikhoreva_independent_audit"], "completion_reward")
        self.assertFalse(any(e.key == "unlock_decision_tooltip" for e in reward))
        branches = [e.value for e in reward if e.key in ("if", "else_if")]
        self.assertEqual(len(branches), 2)
        for branch in branches:
            decision_id = scalar(branch, "unlock_decision_tooltip")
            decision = next(e.value for e in walk(self.stp_decisions) if e.key == decision_id)
            preview_method = block(block(block(branch, "limit"), "hidden_trigger"), "check_variable")
            actual_method = block(block(decision, "visible"), "check_variable")
            self.assertEqual(
                [(e.key, e.value) for e in preview_method],
                [(e.key, e.value) for e in actual_method],
            )

    def test_repair_and_air_unlock_summaries_are_translated(self) -> None:
        for decision_id in (
            "STP_cw_complete_air_reserve",
            "STP_cw_launch_air_operation",
            "STP_cw_repair_rifle_batch",
        ):
            tooltip = f"{decision_id}_unlock_summary_tt"
            for language, entries in self.localisation.items():
                with self.subTest(decision=decision_id, language=language):
                    self.assertTrue(entries.get(tooltip))

    def test_focus_and_decision_prose_has_no_mechanical_values(self) -> None:
        descriptions = set()
        for focus_id, entries in self.focuses.items():
            descriptions.add(focus_id + "_desc")
            for entry in entries:
                if entry.key == "desc":
                    if isinstance(entry.value, str):
                        descriptions.add(entry.value)
                    else:
                        descriptions.update(
                            item.value for item in walk(entry.value)
                            if item.key == "text" and isinstance(item.value, str)
                        )
        for path in (ROOT / "common/decisions").glob("*.txt"):
            for category in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if not isinstance(category.value, list):
                    continue
                for decision in category.value:
                    if not isinstance(decision.value, list):
                        continue
                    descriptions.add(decision.key + "_desc")
                    for entry in decision.value:
                        if entry.key != "desc":
                            continue
                        if isinstance(entry.value, str):
                            descriptions.add(entry.value)
                        else:
                            descriptions.update(
                                item.value for item in walk(entry.value)
                                if item.key == "text" and isinstance(item.value, str)
                            )

        scripted_text = {}
        for path in (ROOT / "common/scripted_localisation").glob("*.txt"):
            for entry in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if isinstance(entry.value, list):
                    scripted_text[scalar(entry.value, "name")] = {
                        item.value for item in walk(entry.value)
                        if item.key == "localization_key"
                    }

        mechanics = re.compile(
            r"£(?!GFX_)|\[\?|[+-]?\d+(?:[.,]\d+)?\s*%|"
            r"\b\d+[ -]?(?:дн(?:я|ей|ев)|дивизи|человек|days?\b|day-|divisions?\b|personnel\b)",
            re.I,
        )
        offenders = []
        for language in ("russian", "english"):
            catalog = {}
            paths = list((ROOT / "localisation" / language).rglob("*.yml"))
            paths += list((ROOT / "localisation/replace").glob(f"*_l_{language}.yml"))
            for path in paths:
                for key, value in re.findall(
                    r'^\s*([^:\s]+):\d*\s+"((?:[^"\\\r\n]|\\.)*)"\s*$',
                    path.read_text(encoding="utf-8-sig"), re.M,
                ):
                    catalog.setdefault(key, set()).add(value)
            pending = list(descriptions)
            checked = set()
            while pending:
                key = pending.pop()
                if key in checked:
                    continue
                checked.add(key)
                for value in catalog.get(key, ()):
                    # Formatting must not conceal a numeric reward; only the
                    # decorative GFX banner is exempt from the texticon rule.
                    prose = re.sub(r"§.", "", value)
                    if mechanics.search(prose):
                        offenders.append((language, key))
                    pending.extend(re.findall(r"\$([^$|]+)(?:\|[^$]*)?\$", value))
                    for token in re.findall(r"\[([^\]]+)\]", value):
                        pending.extend(scripted_text.get(token.split(".")[-1], ()))
        self.assertEqual(sorted(set(offenders)), [])

    def test_effect_previews_do_not_use_narrative_description_keys(self) -> None:
        offenders = []
        for folder in ("common/decisions", "common/national_focus", "common/scripted_effects"):
            for path in (ROOT / folder).glob("*.txt"):
                for entry in walk(parse_clausewitz(path.read_text(encoding="utf-8-sig"))):
                    if entry.key == "custom_effect_tooltip" and isinstance(entry.value, str):
                        if entry.value.endswith("_desc"):
                            offenders.append((path.name, entry.value))
        self.assertEqual(offenders, [])

    def test_decision_unlocks_use_scalar_form(self) -> None:
        offenders = []
        pattern = re.compile(r"unlock_decision_tooltip\s*=\s*\{")
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_decision_unlocks_do_not_inline_full_decision_effects(self) -> None:
        offenders = []
        pattern = re.compile(
            r"unlock_decision_tooltip\s*=\s*\{[^{}]*"
            r"show_effect_tooltip\s*=\s*yes[^{}]*\}",
            re.S,
        )
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_decision_unlocks_do_not_repeat_the_decision_description(self) -> None:
        offenders = []
        pattern = re.compile(
            r"unlock_decision_tooltip\s*=\s*([A-Za-z0-9_]+)"
            r"[ \t\r\n]+custom_effect_tooltip\s*=\s*\1_desc\b"
        )
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
