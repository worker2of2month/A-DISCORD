"""Focused tests for the fresh-only Vorkerland anti-stalemate contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_stalemate import (
    ACTIVE_FLAGS,
    EFFECTS,
    ON_ACTIONS,
    ROOT,
    RUSSIAN,
    SCOPED_FILES,
    collect_issues,
)


def _fixture() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    for relative in SCOPED_FILES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return temporary, root


class VorkerlandStalemateValidatorTests(unittest.TestCase):
    def test_live_contract_is_clean(self) -> None:
        self.assertEqual(collect_issues(ROOT), [])

    def test_forbids_new_wars_and_unity_tower_mutation(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        path = root / EFFECTS
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\nfixture = { declare_war_on = { target = REV } 40 = { province = 16428 } }\n",
            encoding="utf-8",
        )
        issues = collect_issues(root)
        self.assertTrue(any("declare_war_on" in issue for issue in issues), issues)
        self.assertTrue(any("state 40" in issue for issue in issues), issues)
        self.assertTrue(any("province 16428" in issue for issue in issues), issues)

    def test_deadlines_and_window_length_are_exact(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        path = root / EFFECTS
        text = path.read_text(encoding="utf-8").replace("days = 240", "days = 241", 1)
        text = text.replace("days = 75", "days = 90", 1)
        path.write_text(text, encoding="utf-8")
        issues = collect_issues(root)
        self.assertTrue(any("wrong delay" in issue for issue in issues), issues)
        self.assertTrue(any(ACTIVE_FLAGS[0] in issue or "75-day" in issue for issue in issues), issues)

    def test_deadline_guard_must_precede_payload(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        path = root / EFFECTS
        text = path.read_text(encoding="utf-8")
        guard = "set_country_flag = ADISCORD_vorkerland_central_stalemate_deadline_resolved"
        payload = "set_country_flag = { flag = ADISCORD_vorkerland_central_breakthrough_window_active days = 75 }"
        text = text.replace(guard, "__GUARD__", 1).replace(payload, guard, 1).replace("__GUARD__", payload, 1)
        path.write_text(text, encoding="utf-8")
        issues = collect_issues(root)
        self.assertTrue(any("guard before its payload" in issue for issue in issues), issues)

    def test_ai_only_actual_war_gate_is_required(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        trigger_path = root / "common/scripted_triggers/ADISCORD_vorkerland_stalemate_triggers.txt"
        text = trigger_path.read_text(encoding="utf-8").replace("\tis_ai = yes\n", "", 1)
        text = text.replace("has_war_with = EYR", "has_opinion = EYR", 1)
        trigger_path.write_text(text, encoding="utf-8")
        issues = collect_issues(root)
        self.assertTrue(any("AI-only" in issue for issue in issues), issues)
        self.assertTrue(any("missing EYR" in issue for issue in issues), issues)

    def test_no_startup_polling_or_retry_is_allowed(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        path = root / ON_ACTIONS
        path.write_text(
            path.read_text(encoding="utf-8") + "\non_startup = { effect = { retry = yes } }\n",
            encoding="utf-8",
        )
        issues = collect_issues(root)
        self.assertTrue(any("startup/save repair" in issue for issue in issues), issues)
        self.assertTrue(any("forbidden behavior: retry" in issue for issue in issues), issues)

    def test_russian_localisation_requires_bom(self) -> None:
        temporary, root = _fixture()
        self.addCleanup(temporary.cleanup)
        path = root / RUSSIAN
        path.write_bytes(path.read_bytes().removeprefix(b"\xef\xbb\xbf"))
        issues = collect_issues(root)
        self.assertTrue(any("UTF-8 BOM" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
