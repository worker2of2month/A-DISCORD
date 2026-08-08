"""Regression contracts for files that must never enter the repository."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRANSIENT_PATTERNS = (
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "console_history.txt",
    "**/*~",
    "**/*.bak",
    "**/*.tmp",
    "**/*.swp",
)


class RepositoryHygieneTests(unittest.TestCase):
    def test_tracked_repository_contains_no_transient_artifacts(self) -> None:
        """Tracked cache files and editor backups would pollute source history."""
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *TRANSIENT_PATTERNS],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        )

        transient_paths = sorted(
            path for path in result.stdout.decode("utf-8").split("\0") if path
        )

        self.assertEqual(transient_paths, [])
