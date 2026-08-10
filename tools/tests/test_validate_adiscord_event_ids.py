"""Tests for the central A-Discord event-ID inventory."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_event_ids import (
    COLLAPSE_OWNER,
    PLANNED_RECOVERY_IDS,
    REGISTRY_PATH,
    REQUIRED_ACTIVE_COLLAPSE_IDS,
    ROOT,
    validate,
)


def _entry(
    event_id: str,
    owner: str,
    *,
    status: str = "active",
    subsystem: str = "fixture",
) -> dict[str, object]:
    namespace, number = event_id.rsplit(".", 1)
    return {
        "id": event_id,
        "namespace": namespace,
        "number": int(number),
        "owner": owner,
        "subsystem": subsystem,
        "status": status,
    }


def _validate_fixture(
    event_files: dict[str, str],
    entries: list[dict[str, object]],
    *,
    gameplay_files: dict[str, str] | None = None,
    external_namespaces: list[str] | None = None,
) -> list[str]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative, content in event_files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for relative, content in (gameplay_files or {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        registry = root / "tools" / "data" / "adiscord_event_ids.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "external_namespaces": external_namespaces or [],
                    "events": entries,
                }
            ),
            encoding="utf-8",
        )
        return validate(
            root,
            registry,
            enforce_recovery_contract=False,
        )


class EventIdInventoryTests(unittest.TestCase):
    def test_live_registry_matches_all_definitions_references_and_recovery_ranges(self) -> None:
        self.assertEqual(validate(ROOT, REGISTRY_PATH), [])

        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        entries = {item["id"]: item for item in data["events"]}
        self.assertEqual(len(entries), len(data["events"]))

        for event_id in REQUIRED_ACTIVE_COLLAPSE_IDS:
            with self.subTest(event_id=event_id):
                self.assertEqual(entries[event_id]["status"], "active")
                self.assertEqual(entries[event_id]["owner"], COLLAPSE_OWNER)

        for event_id, owner in PLANNED_RECOVERY_IDS.items():
            with self.subTest(event_id=event_id):
                expected_status = "active" if (ROOT / owner).is_file() else "reserved"
                self.assertEqual(entries[event_id]["status"], expected_status)
                self.assertEqual(entries[event_id]["owner"], owner)

    def test_reserved_future_id_allows_absent_owner_file(self) -> None:
        issues = _validate_fixture(
            {},
            [
                _entry(
                    "ADISCORD_future.1",
                    "events/ADISCORD_future_events.txt",
                    status="reserved",
                )
            ],
        )
        self.assertEqual(issues, [])

    def test_duplicate_definition_is_rejected_even_when_nested_calls_exist(self) -> None:
        source = """add_namespace = ADISCORD_fixture
country_event = {
    id = ADISCORD_fixture.1
    immediate = { country_event = { id = ADISCORD_fixture.1 } }
}
"""
        issues = _validate_fixture(
            {
                "events/fixture_a.txt": source,
                "events/fixture_b.txt": source,
            },
            [_entry("ADISCORD_fixture.1", "events/fixture_a.txt")],
        )
        self.assertTrue(
            any("duplicate definition ADISCORD_fixture.1" in issue for issue in issues),
            issues,
        )

    def test_duplicate_registry_id_is_rejected(self) -> None:
        source = """add_namespace = ADISCORD_fixture
country_event = { id = ADISCORD_fixture.1 }
"""
        entry = _entry("ADISCORD_fixture.1", "events/fixture.txt")
        issues = _validate_fixture(
            {"events/fixture.txt": source},
            [entry, dict(entry)],
        )
        self.assertIn("duplicate registry ID: ADISCORD_fixture.1", issues)

    def test_unregistered_definition_and_reference_are_rejected(self) -> None:
        issues = _validate_fixture(
            {
                "events/fixture.txt": """add_namespace = ADISCORD_fixture
country_event = { id = ADISCORD_fixture.1 }
country_event = { id = ADISCORD_fixture.2 }
"""
            },
            [_entry("ADISCORD_fixture.1", "events/fixture.txt")],
            gameplay_files={
                "common/scripted_effects/fixture.txt":
                "effect = { country_event = { id = ADISCORD_fixture.3 } }\n"
            },
        )
        self.assertTrue(
            any("unregistered event definition ADISCORD_fixture.2" in issue for issue in issues),
            issues,
        )
        self.assertTrue(
            any("unregistered event reference ADISCORD_fixture.3" in issue for issue in issues),
            issues,
        )

    def test_owner_namespace_and_status_drift_are_rejected(self) -> None:
        issues = _validate_fixture(
            {
                "events/actual.txt": """add_namespace = ADISCORD_wrong
country_event = { id = ADISCORD_fixture.1 }
country_event = { id = ADISCORD_fixture.2 }
"""
            },
            [
                _entry("ADISCORD_fixture.1", "events/expected.txt"),
                _entry(
                    "ADISCORD_fixture.2",
                    "events/actual.txt",
                    status="reserved",
                ),
                _entry("ADISCORD_fixture.3", "events/actual.txt"),
            ],
        )
        self.assertTrue(any("owner drift for ADISCORD_fixture.1" in issue for issue in issues), issues)
        self.assertTrue(any("namespace drift for ADISCORD_fixture.1" in issue for issue in issues), issues)
        self.assertTrue(
            any(
                "status drift for ADISCORD_fixture.2: reserved entry has a live definition"
                in issue
                for issue in issues
            ),
            issues,
        )
        self.assertTrue(
            any(
                "status drift for ADISCORD_fixture.3: active entry has no live definition"
                in issue
                for issue in issues
            ),
            issues,
        )

    def test_comments_strings_and_registered_external_namespace_are_not_references(self) -> None:
        issues = _validate_fixture(
            {
                "events/fixture.txt": """add_namespace = ADISCORD_fixture
country_event = {
    id = ADISCORD_fixture.1
    desc = "ADISCORD_fixture.98"
    # country_event = { id = ADISCORD_fixture.99 }
}
"""
            },
            [_entry("ADISCORD_fixture.1", "events/fixture.txt")],
            gameplay_files={
                "common/operations/fixture.txt":
                "effect = { country_event = { id = vanilla_fixture.1 } }\n"
            },
            external_namespaces=["vanilla_fixture"],
        )
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
