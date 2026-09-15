"""Stable repository-path helpers for package modules and root-level facades.

``repository_root`` derives the root from this file's location, so it is
identical when imported as ``tools.lib.paths`` or as ``lib.paths`` by a tool
run directly from the legacy ``tools/`` directory.
"""

from __future__ import annotations

import re
from pathlib import Path


def repository_root() -> Path:
    """Return the A-Discord repository root containing the ``tools`` directory."""
    return Path(__file__).resolve().parents[2]


def source_section(text: str, *sections: str) -> str:
    """Select authored sections of a consolidated file for a scoped validator.

    Standalone snippets used by mutation tests have no section markers and are
    returned unchanged. A consolidated source must contain every requested
    section; a missing or duplicated marker is an error, not an empty check.
    """
    marker = re.compile(r"(?m)^# --- ([a-z_]+) ---[ \t]*$")
    markers = list(marker.finditer(text))
    if not markers:
        return text
    selected = []
    for section in sections:
        matches = [i for i, match in enumerate(markers) if match[1] == section]
        if len(matches) != 1:
            raise ValueError(f"Expected one source section {section!r}, found {len(matches)}")
        index = matches[0]
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[markers[index].end():end].strip("\n") + "\n"
        if text.lstrip().startswith("ideas = {"):
            body = "ideas = {\n\tcountry = {\n" + body + "\t}\n}\n"
        elif text.startswith(("l_english:", "l_russian:")):
            body = text.split("\n", 1)[0] + "\n" + body
        selected.append(body)
    return "\n".join(selected)
