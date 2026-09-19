"""Explicit source views for country contracts spanning native on_action files.

Gameplay is read from its actual owners. Country validators can inspect the
country lifecycle and its shared peace section without seeing other treaties.
The independent scripted-peace tests validate the complete native dispatch.
"""
from __future__ import annotations
import re
from pathlib import Path
from tools.lib.paths import repository_root

SCRIPTED_PEACE = '09_ADISCORD_scripted_peace_on_actions.txt'
_SECTION = re.compile(
    r'(?m)^[ \t]*# BEGIN ([a-z_]+):(on_[A-Za-z_]+)[ \t]*\n'
    r'(.*?)^[ \t]*# END \1:\2[ \t]*$', re.DOTALL,
)

def _path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else repository_root() / path

def _body(source: str) -> str:
    match = re.fullmatch(r'\s*on_actions\s*=\s*\{(.*)\}\s*', source, re.DOTALL)
    if match is None:
        raise ValueError('Expected one on_actions source container')
    return match[1]

def read_scripted_peace(path: str | Path, section: str) -> str:
    """Read one explicitly named treaty group from the shared native owner."""
    source = _path(path).read_text(encoding='utf-8')
    matches = [m for m in _SECTION.finditer(source) if m[1] == section]
    if not matches or len({m[2] for m in matches}) != len(matches):
        raise ValueError(f'Missing or duplicated scripted-peace section: {section}')
    body = '\n'.join(f'\t{m[2]} = {{\n\t\teffect = {{\n{m[3]}\t\t}}\n\t}}' for m in matches)
    return 'on_actions = {\n' + body + '\n}\n'

def read_country_on_actions(path: str | Path, section: str) -> str:
    """Read an existing country file plus its explicitly selected peace hooks."""
    path = _path(path)
    country = path.read_text(encoding='utf-8')
    peace = read_scripted_peace(path.with_name(SCRIPTED_PEACE), section)
    return 'on_actions = {\n' + _body(country).strip('\n') + '\n' + _body(peace).strip('\n') + '\n}\n'

def country_on_actions_entries(path: str | Path, section: str):
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    return parse_clausewitz(read_country_on_actions(path, section))

def scripted_peace_entries(path: str | Path, section: str):
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    return parse_clausewitz(read_scripted_peace(path, section))
