"""Read explicit authored focus views for tooling, separate from native assembly."""

from pathlib import Path

from tools.lib.paths import repository_root
from tools.builders.build_adiscord_focus_trees import (
    SHARED_HISTORY_SOURCES,
    SOURCES,
    render_source,
)


FOCUS_SOURCE_GROUPS = {
    "ADISCORD_national_focus_STP.txt": ("STP/",),
    "ADISCORD_national_focus_VAL_defeated.txt": (
        "VAL/defeated/",
        "VAL/administration/",
    ),
    "ADISCORD_vorkerland_focus.txt": ("Vorkerland/",),
}


def read_focus_source(path: Path | str, encoding: str = "utf-8-sig") -> str:
    """Read authored VAL structure or aggregate former multi-tree paths for tooling.

    VAL's native output uses shared definitions to preserve completion history.
    Existing semantic readers need the owning authored tree and its original
    nesting. Native composition checks must use read_native_focus_source instead.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repository_root() / resolved
    for source in SHARED_HISTORY_SOURCES:
        output = repository_root() / "common/national_focus" / SOURCES[source]
        if resolved.resolve() == output.resolve():
            return render_source(source)
    if resolved.is_file():
        return resolved.read_text(encoding=encoding)

    prefixes = FOCUS_SOURCE_GROUPS.get(resolved.name)
    if resolved.name in {source.split("/", 1)[0] for source in SOURCES}:
        prefixes = (resolved.name + "/",)
    if prefixes is None:
        raise FileNotFoundError(resolved)
    sources = [
        repository_root() / "common/national_focus" / output
        for source, output in SOURCES.items()
        if source.startswith(prefixes)
    ]
    if not sources:
        raise FileNotFoundError(f"No focus sources found for {resolved}")
    return "\n".join(read_focus_source(source, encoding=encoding) for source in sources)


def read_native_focus_source(path: Path | str, encoding: str = "utf-8-sig") -> str:
    """Read actual engine bytes as text, without authored-view substitution."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repository_root() / resolved
    return resolved.read_text(encoding=encoding)
