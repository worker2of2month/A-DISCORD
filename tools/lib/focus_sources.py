"""Read native focus outputs, including former combined country source views."""

from pathlib import Path

from tools.lib.paths import repository_root
from tools.builders.build_adiscord_focus_trees import SOURCES


FOCUS_SOURCE_GROUPS = {
    "ADISCORD_national_focus_STP.txt": ("STP/",),
    "ADISCORD_national_focus_VAL_defeated.txt": ("VAL/defeated/", "VAL/administration/"),
    "ADISCORD_vorkerland_focus.txt": ("Vorkerland/",),
}


def read_focus_source(path: Path | str, encoding: str = "utf-8-sig") -> str:
    """Read one focus file or aggregate a former multi-tree source path for tooling."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repository_root() / resolved
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
    return "\n".join(source.read_text(encoding=encoding) for source in sources)
