"""Small helpers for safely updating shared HOI4 localisation files."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path


def replace_generated_localisation_block(
    path: Path,
    marker: str,
    entries: Mapping[str, str],
) -> None:
    """Replace one generator-owned block while preserving the shared file."""
    if not path.exists():
        raise RuntimeError(f"shared localisation file is missing: {path}")
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise RuntimeError(f"shared localisation file must use UTF-8 BOM: {path}")

    source = path.read_text(encoding="utf-8-sig", errors="strict")
    if not re.match(r"^l_[a-z_]+:\s*(?:\n|$)", source):
        raise RuntimeError(f"shared localisation file has an invalid language header: {path}")

    begin = f" # BEGIN GENERATED: {marker}"
    end = f" # END GENERATED: {marker}"
    if source.count(begin) != source.count(end) or source.count(begin) > 1:
        raise RuntimeError(f"generated localisation block markers are unbalanced: {marker}")

    rendered_entries: list[str] = []
    for key, value in entries.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
            raise ValueError(f"invalid localisation key {key!r}")
        if any(character in value for character in ('"', "\r", "\n")):
            raise ValueError(f"localisation value for {key} cannot be rendered safely")
        rendered_entries.append(f' {key}: "{value}"')
    block = "\n".join((begin, *rendered_entries, end))

    if begin in source:
        pattern = rf"(?ms)^{re.escape(begin)}\n.*?^{re.escape(end)}$"
        updated, count = re.subn(pattern, lambda _match: block, source)
        if count != 1:
            raise RuntimeError(f"expected one generated localisation block for {marker}, found {count}")
    else:
        updated = source.rstrip() + "\n" + block + "\n"

    path.write_text(updated.rstrip() + "\n", encoding="utf-8-sig", newline="\n")
