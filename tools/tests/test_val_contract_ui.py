from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    start = match.start()
    brace = text.find("{", match.start(), match.end())
    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unclosed block {name}")


class TestValContractUi(unittest.TestCase):
    def test_contract_state_is_visible_and_reports_live_authority(self) -> None:
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        contract_state = named_block(dynamic, "VAL_contract_state")
        self.assertIn("icon = GFX_idea_VAL_contract_state", contract_state)

        on_actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        weekly = named_block(on_actions, "on_weekly_VAL")
        for recovery in (startup, weekly):
            self.assertIn("has_dynamic_modifier = { modifier = VAL_contract_state }", recovery)
            self.assertIn("VAL_initialize_contract_authority = yes", recovery)

        history = read("history/countries/VAL - ValeraLand.txt")
        self.assertIn("VAL_mercenary_state", history)

        english = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")
        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.assertIn('VAL_contract_state: "Contract System Authority"', english)
        self.assertIn('VAL_contract_state: "Авторитет контрактной системы"', russian)
        for localisation in (english, russian):
            self.assertIn("[?VAL_contract_authority|0]/100", localisation)
            self.assertIn("[VALGetContractAuthorityBand]", localisation)

    def test_authority_labels_match_modifier_bands(self) -> None:
        scripted = read("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        band = named_block(scripted, "defined_text")
        marker = scripted.index("name = VALGetContractAuthorityBand")
        start = scripted.rfind("defined_text", 0, marker)
        authority_band = named_block(scripted[start:], "defined_text")

        expected = (
            ("90", "VAL_CONTRACT_AUTHORITY_DOMINANT"),
            ("75", "VAL_CONTRACT_AUTHORITY_CENTRALIZED"),
            ("50", "VAL_CONTRACT_AUTHORITY_COHERENT"),
            ("25", "VAL_CONTRACT_AUTHORITY_BROKERED"),
        )
        for value, key in expected:
            self.assertIn(f"value = {value} compare = greater_than_or_equals", authority_band)
            self.assertIn(f"localization_key = {key}", authority_band)
        self.assertIn("localization_key = VAL_CONTRACT_AUTHORITY_FRAGMENTED", authority_band)

    def test_decision_categories_are_consolidated_without_losing_decisions(self) -> None:
        categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")

        for current in ("VAL_contract_management", "VAL_postwar_administration"):
            self.assertIn(f"{current} = {{", categories)
            self.assertIn(f"{current} = {{", decisions)

        for obsolete in (
            "VAL_propaganda_campaigns",
            "VAL_contract_obligations",
            "VAL_regional_integration",
            "VAL_commonwealth_formation",
        ):
            self.assertNotRegex(categories, rf"(?m)^\s*{obsolete}\s*=\s*\{{")
            self.assertNotRegex(decisions, rf"(?m)^\s*{obsolete}\s*=\s*\{{")

        contract = named_block(decisions, "VAL_contract_management")
        for decision in (
            "VAL_campaign_rifles_and_bread",
            "VAL_campaign_contracts_feed_families",
            "VAL_campaign_no_promise_without_payment",
            "VAL_campaign_the_mine_was_stolen",
            "VAL_quarterly_contract_deadline",
            "VAL_pay_quarterly_contract_norm",
        ):
            self.assertIn(f"{decision} = {{", contract)

        postwar = named_block(decisions, "VAL_postwar_administration")
        for decision in (
            "VAL_establish_regional_administration",
            "VAL_nationalise_region",
            "VAL_proclaim_commonwealth",
        ):
            self.assertIn(f"{decision} = {{", postwar)


if __name__ == "__main__":
    unittest.main()
