"""Regression contracts for major A-DISCORD world-news broadcasts."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    file = ROOT / path
    return file.read_text(encoding="utf-8-sig") if file.exists() else ""


def named_block(text: str, name: str) -> str:
    match = re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\s*=\s*\{", text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    in_string = False
    escaped = False
    for index in range(start, len(text)):
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
                return text[start:index]
    raise AssertionError(f"Unclosed block {name}")


def event_block(text: str, event_id: str) -> str:
    for match in re.finditer(r"(?m)^\s*news_event\s*=\s*\{", text):
        start = match.end()
        depth = 1
        in_string = False
        escaped = False
        for index in range(start, len(text)):
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
                    block = text[start:index]
                    if re.search(r"\bid\s*=\s*" + re.escape(event_id) + r"\b", block):
                        return block
                    break
    return ""


class WorldNewsContracts(unittest.TestCase):
    def setUp(self):
        self.events = read("events/ADISCORD_world_news.txt")
        self.stp_events = read("events/ADISCORD_STP_events.txt")
        self.on_actions = read("common/on_actions/06_ADISCORD_world_news_on_actions.txt")
        self.debug_categories = read("common/decisions/categories/ADISCORD_scenario_debug_categories.txt")
        self.ru_path = ROOT / "localisation/russian/ADISCORD_world_news_l_russian.yml"
        self.en_path = ROOT / "localisation/english/ADISCORD_world_news_l_english.yml"
        self.ru = read("localisation/russian/ADISCORD_world_news_l_russian.yml")
        self.en = read("localisation/english/ADISCORD_world_news_l_english.yml")

    def test_required_war_broadcasts_are_major_and_not_globally_one_shot(self):
        for number in range(1, 6):
            event = event_block(self.events, f"ADISCORD_world_news.{number}")
            self.assertTrue(event, number)
            self.assertIn("major = yes", event)
            self.assertIn("is_triggered_only = yes", event)
            self.assertNotIn("fire_only_once = yes", event)
            self.assertIn("fire_only_once = no", event)
            self.assertNotIn("fire_for_sender = no", event)

    def test_actual_war_relations_publish_each_story_once(self):
        war = named_block(self.on_actions, "on_war_relation_added")
        for flag in (
            "ADISCORD_news_vorkerland_fighting_published",
            "ADISCORD_news_nodrul_northern_war_published",
            "ADISCORD_news_stelander_civil_war_published",
            "ADISCORD_news_kefreyt_intervention_published",
            "ADISCORD_news_itora_intervention_published",
        ):
            self.assertIn(f"NOT = {{ has_global_flag = {flag} }}", war)
            self.assertIn(f"set_global_flag = {flag}", war)

        for event_id in (1, 2, 4, 5):
            self.assertIn(
                f"news_event = {{ id = ADISCORD_world_news.{event_id} hours = 1 }}",
                war,
            )

        # STP already owns a richer public outbreak report. Publish that report
        # from the reliable war-relation hook instead of showing a second generic
        # headline. Delay the window past declare_war_on; fire_only_once still
        # suppresses a second same-hour fallback call.
        self.assertIn("news_event = { id = ADISCORD_STP_cw.70 hours = 1 }", war)
        self.assertNotIn("news_event = { id = ADISCORD_world_news.3 }", war)
        stp_outbreak = event_block(self.stp_events, "ADISCORD_STP_cw.70")
        self.assertTrue(stp_outbreak)
        self.assertIn("major = yes", stp_outbreak)
        self.assertIn("is_triggered_only = yes", stp_outbreak)
        self.assertIn("fire_only_once = yes", stp_outbreak)

        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(f"tag = {tag}", war)
        for tag in ("NOD", "YPR", "COF", "TFF"):
            self.assertIn(f"tag = {tag}", war)
        for tag in ("STP", "STS", "SRP", "VAL"):
            self.assertIn(f"tag = {tag}", war)
        for tag in ("IVN", "ZAO", "WPA", "WPS", "PWR", "PSD"):
            self.assertIn(f"tag = {tag}", war)

    def test_world_news_has_bilingual_localisation(self):
        for number in range(1, 6):
            for suffix in ("t", "d", "a"):
                key = f"ADISCORD_world_news.{number}.{suffix}:"
                self.assertIn(key, self.ru)
                self.assertIn(key, self.en)

    def test_world_news_localisation_uses_utf8_bom(self):
        self.assertTrue(self.ru_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue(self.en_path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_world_news_debug_smoke_decisions_are_not_shipped(self):
        self.assertFalse(
            (ROOT / "common/decisions/ADISCORD_world_news_debug_decisions.txt").exists()
        )
        self.assertNotIn("ADISCORD_debug_world_news_", self.ru)
        self.assertNotIn("ADISCORD_debug_world_news_", self.en)

    def test_world_news_does_not_expand_shared_debug_category(self):
        category = named_block(self.debug_categories, "ADISCORD_scenario_debug_category")
        for tag in (
            "ZAO", "WPA", "WPS", "PWR", "PSD",
            "NOD", "YPR", "COF", "TFF",
            "STP", "STS", "SRP", "VAL",
        ):
            self.assertNotIn(f"tag = {tag}", category, tag)
        for tag in ("WRK", "WKR", "VAD", "TVA", "IVN", "NAM", "EFL", "AZH", "SLF"):
            self.assertIn(f"tag = {tag}", category, tag)


if __name__ == "__main__":
    unittest.main()
