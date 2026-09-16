from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TEXT_ROOTS = (
    ROOT / "localisation" / "russian",
    ROOT / "localisation" / "english",
    ROOT / "localisation" / "replace",
    ROOT / "docs" / "lore",
)

# Historical/internal file stems may still contain e.g. IvanLand/NamestnikLand.
# These exact player-facing aliases must not appear in localisation or lore prose.
FORBIDDEN_ALIASES = (
    "Иванланд",
    "иванланд",
    "Ivanland",
    "Наместникленд",
    "Витланд",
)


def iter_text_files():
    for root in TEXT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in {".yml", ".md", ".txt"}:
                yield path


class CanonicalCountryNameTests(unittest.TestCase):
    def test_legacy_country_aliases_do_not_leak_into_visible_text(self) -> None:
        failures: list[str] = []
        for path in iter_text_files():
            text = path.read_text(encoding="utf-8-sig")
            for alias in FORBIDDEN_ALIASES:
                if alias in text:
                    failures.append(f"{path.relative_to(ROOT)}: {alias}")
        self.assertEqual(failures, [], "legacy country aliases remain in visible text")

    def test_svetlogorye_localisation_does_not_show_internal_nam_tag(self) -> None:
        path = ROOT / "localisation" / "russian" / "ADISCORD_nam_resource_war_l_russian.yml"
        text = path.read_text(encoding="utf-8-sig")
        visible_values = "\n".join(
            match.group(1)
            for match in re.finditer(r'^\s*[^#\n][^:]*:\s*"(.*)"\s*$', text, flags=re.MULTILINE)
        )
        self.assertNotRegex(visible_values, r"\bNAM\b")


if __name__ == "__main__":
    unittest.main()
