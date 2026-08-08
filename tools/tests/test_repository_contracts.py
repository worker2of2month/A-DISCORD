"""Regression contracts for files that must never enter the repository."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRANSIENT_PATTERNS = (
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "console_history.txt",
    "**/console_history.txt",
    "**/*~",
    "**/*.bak",
    "**/*.tmp",
    "**/*.swp",
    "**/*.swo",
    "**/.#*",
)


def tracked_transient_paths(repository_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *TRANSIENT_PATTERNS],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return sorted(path for path in result.stdout.decode("utf-8").split("\0") if path)


class RepositoryHygieneTests(unittest.TestCase):
    def test_tracked_repository_hygiene_contract(self) -> None:
        """The contract rejects tracked transient artifacts at every path depth."""
        self.assertEqual(tracked_transient_paths(REPOSITORY_ROOT), [])
        fixture_paths = [
            "notes/.#scratch",
            "notes/console_history.txt",
            "notes/session.swo",
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            subprocess.run(
                ["git", "init", "-q"],
                cwd=fixture_root,
                check=True,
                capture_output=True,
            )
            for relative_path in fixture_paths:
                fixture_path = fixture_root / relative_path
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text("transient", encoding="utf-8")
            subprocess.run(
                ["git", "add", "--", *fixture_paths],
                cwd=fixture_root,
                check=True,
                capture_output=True,
            )

            self.assertEqual(tracked_transient_paths(fixture_root), fixture_paths)
