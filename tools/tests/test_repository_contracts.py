"""Regression contracts for files that must never enter the repository."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from hashlib import sha256
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

LEGACY_VENDOR_PREFIX = "tools/hoi4_flag_maker_gui/"
VENDOR_PREFIX = "third_party/hoi4_flag_maker/"
VENDOR_DOCUMENTATION = "third_party/hoi4_flag_maker/README.adiscord.md"
REFERENCE_BINARY_HASHES = {
    "tools/assets/reference/REV'S COMPREHENSIVE BASIC ICON GUIDE v1.0.docx": "12d318f1681509c0d7919a7a9bcd4cb6c76af08324bc2f0d05512f5c09dc0b83",
    "tools/assets/reference/Sudin‘s TFR Icon Guide.docx": "b6c05cc68eafceef01af4b1185bdfe2696b0794c90cdde648f73948746458f6a",
    "tools/assets/reference/TFR 图标教程 Icon Guide CN.docx": "6f252790c399d4448ed641542ed09d0303e50492022be38cc4648b34078b44a7",
    "tools/assets/reference/focus.psd": "ade29c1bdece678057a165a566abaaf52cbe81b9908b488dfa9dc014efa4f1f0",
    "tools/assets/reference/人像比例Framing.png": "864b6522d7c7576147a9fa7ee1e452bcb16d4f822503fa67a8a2a8ad6953d7bb",
    "tools/assets/reference/色彩Color.png": "f8da09d5fed8b22ae87445139db1d133d3a40a59fd0fe52f26a0235af7300f21",
}
EDITABLE_SOURCE_PATHS = (
    "tools/assets/source/decisions.psd",
    "tools/assets/source/portrait.psd",
    "tools/assets/source/STP_Operation_Last_Banquette.psd",
    "tools/assets/source/terrain_view.psd",
    "tools/assets/source/val_ideology.psd",
    "tools/assets/source/wrk_ideology.psd",
    "tools/assets/source/wrk_ideology_2.psd",
)
CONSOLIDATED_CONTENT_CONTAINERS = {
    "common/opinion_modifiers/00_adiscord_option_modifiers.txt": (
        "common/opinion_modifiers/00_opinion_modifiers.txt",
        "VAL_trading_partners = {",
    ),
    "common/opinion_modifiers/00_diplomatic.txt": (
        "common/opinion_modifiers/00_opinion_modifiers.txt",
        "faction_traitor = {",
    ),
    "common/scripted_triggers/debug_triggers.txt": (
        "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt",
        "test_game_reached_1948 = {",
    ),
    "common/scripted_triggers/Elections_scripted_triggers.txt": (
        "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt",
        "can_lose_unity = {",
    ),
    "common/scripted_effects/SP_scripted_effects.txt": (
        "common/scripted_effects/ADISCORD_scripted_effects_119_compat.txt",
        "SP_create_variant_of_habakkuk_for_production_line = {",
    ),
}


def tracked_transient_paths(repository_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *TRANSIENT_PATTERNS],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return sorted(path for path in result.stdout.decode("utf-8").split("\0") if path)


def tracked_paths(repository_root: Path, pathspec: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", pathspec],
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

    def test_vendor_bundle_and_moved_reference_binaries_are_documented(self) -> None:
        """A vendor GUI stays outside tooling and every moved reference blob is attributable."""
        self.assertEqual(tracked_paths(REPOSITORY_ROOT, f"{LEGACY_VENDOR_PREFIX}**"), [])

        vendor_paths = tracked_paths(REPOSITORY_ROOT, f"{VENDOR_PREFIX}**")
        self.assertIn(f"{VENDOR_PREFIX}hoi4_flag_maker_gui.exe", vendor_paths)

        vendor_documentation = REPOSITORY_ROOT / VENDOR_DOCUMENTATION
        self.assertTrue(vendor_documentation.is_file())
        documentation = vendor_documentation.read_text(encoding="utf-8")
        self.assertIn("atthematyo/hoi4_flag_maker", documentation)
        self.assertIn("Version 1.1.0", documentation)

        tools_documentation = (REPOSITORY_ROOT / "tools/README.md").read_text(
            encoding="utf-8"
        )
        for relative_path, expected_hash in REFERENCE_BINARY_HASHES.items():
            binary_path = REPOSITORY_ROOT / relative_path
            self.assertTrue(binary_path.is_file(), relative_path)
            self.assertEqual(sha256(binary_path.read_bytes()).hexdigest(), expected_hash)
            self.assertIn(relative_path, tools_documentation)
            self.assertIn(expected_hash, tools_documentation)

    def test_editable_sources_do_not_clutter_the_tools_root(self) -> None:
        tools_documentation = (REPOSITORY_ROOT / "tools/README.md").read_text(
            encoding="utf-8"
        )
        self.assertFalse((REPOSITORY_ROOT / "A-Discord.7z").exists())
        self.assertEqual(list((REPOSITORY_ROOT / "tools").glob("*.psd")), [])
        for relative_path in EDITABLE_SOURCE_PATHS:
            self.assertTrue((REPOSITORY_ROOT / relative_path).is_file(), relative_path)
            self.assertIn(relative_path.removeprefix("tools/assets/source/"), tools_documentation)

    def test_small_generic_content_uses_canonical_containers(self) -> None:
        for old_path, (target_path, representative_definition) in (
            CONSOLIDATED_CONTENT_CONTAINERS.items()
        ):
            self.assertFalse((REPOSITORY_ROOT / old_path).exists(), old_path)
            target_text = (REPOSITORY_ROOT / target_path).read_text(encoding="utf-8-sig")
            self.assertEqual(target_text.count(representative_definition), 1, target_path)
