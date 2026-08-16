from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPRITES = {
    "GFX_IVN_roar_of_freedom_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png",
    "GFX_IVN_emergency_committee_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png",
    "GFX_TVA_wartime_technocratic_worker_party_texticon": "gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png",
    "GFX_VAD_vorkerland_imperial_party_texticon": "gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png",
    "GFX_ZAO_independent_party_texticon": "gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png",
    "GFX_PWR_independent_party_texticon": "gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png",
    "GFX_VLA_independent_party_texticon": "gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png",
    "GFX_ROM_independent_party_texticon": "gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png",
    "GFX_SOL_independent_party_texticon": "gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png",
    "GFX_TRU_independent_party_texticon": "gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png",
}
PARTIES_LOCALISATION = "localisation/russian/parties_l_russian.yml"
COLLAPSE_LOCALISATION = "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml"
LOCALISATION_TEXTICON_KEYS = (
    (PARTIES_LOCALISATION, "IVN_humanism_party", "GFX_IVN_roar_of_freedom_party_texticon"),
    (PARTIES_LOCALISATION, "IVN_humanism_party_long", "GFX_IVN_roar_of_freedom_party_texticon"),
    (PARTIES_LOCALISATION, "IVN_etatism_party", "GFX_IVN_emergency_committee_party_texticon"),
    (PARTIES_LOCALISATION, "IVN_etatism_party_long", "GFX_IVN_emergency_committee_party_texticon"),
    (COLLAPSE_LOCALISATION, "TVA_technocracy_party", "GFX_TVA_wartime_technocratic_worker_party_texticon"),
    (COLLAPSE_LOCALISATION, "TVA_technocracy_party_long", "GFX_TVA_wartime_technocratic_worker_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_pragmatism_party_independent", "GFX_VAD_vorkerland_imperial_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_pragmatism_party_independent_long", "GFX_VAD_vorkerland_imperial_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_vorkerland_imperial_party", "GFX_VAD_vorkerland_imperial_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_vorkerland_imperial_party_long", "GFX_VAD_vorkerland_imperial_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_vorkerland_imperial_party_wrk_subject", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VAD_vorkerland_imperial_party_wrk_subject_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ZAO_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ZAO_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ZAO_pragmatism_party_independent", "GFX_ZAO_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ZAO_pragmatism_party_independent_long", "GFX_ZAO_independent_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_pragmatism_party_independent", "GFX_PWR_independent_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_pragmatism_party_independent_long", "GFX_PWR_independent_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_technocracy_party", "GFX_PWR_independent_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_technocracy_party_long", "GFX_PWR_independent_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_technocracy_party_wrk_subject", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "PWR_technocracy_party_wrk_subject_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VLA_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VLA_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "VLA_pragmatism_party_independent", "GFX_VLA_independent_party_texticon"),
    (PARTIES_LOCALISATION, "VLA_pragmatism_party_independent_long", "GFX_VLA_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_pragmatism_party_independent", "GFX_ROM_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_pragmatism_party_independent_long", "GFX_ROM_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_etatism_party", "GFX_ROM_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_etatism_party_long", "GFX_ROM_independent_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_etatism_party_wrk_subject", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "ROM_etatism_party_wrk_subject_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "SOL_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "SOL_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "SOL_pragmatism_party_independent", "GFX_SOL_independent_party_texticon"),
    (PARTIES_LOCALISATION, "SOL_pragmatism_party_independent_long", "GFX_SOL_independent_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_pragmatism_party", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_pragmatism_party_long", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_pragmatism_party_independent", "GFX_TRU_independent_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_pragmatism_party_independent_long", "GFX_TRU_independent_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_chauvinism_party", "GFX_TRU_independent_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_chauvinism_party_long", "GFX_TRU_independent_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_chauvinism_party_wrk_subject", "GFX_WRK_worker_revolutionary_party_texticon"),
    (PARTIES_LOCALISATION, "TRU_chauvinism_party_wrk_subject_long", "GFX_WRK_worker_revolutionary_party_texticon"),
)
SUCCESSOR_TAGS = ("VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU")
SUCCESSOR_PATTERN = "|".join(SUCCESSOR_TAGS)
SCRIPT_ROOTS = ("common", "events", "history")
EXPECTED_TRANSITIONS = Counter(
    {
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "VAD", "autonomy_district_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "ZAO", "autonomy_district_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "PWR", "autonomy_district_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "VLA", "autonomy_district_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "ROM", "autonomy_republic_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "SOL", "autonomy_republic_in_Vorkerland"): 1,
        ("history/countries/WRK - WorkerLand.txt", "set_autonomy", "TRU", "autonomy_republic_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "puppet", "VLA", ""): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "puppet", "ROM", ""): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "puppet", "TRU", ""): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "VLA", "autonomy_district_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "VAD", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "ZAO", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "PWR", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "VLA", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "ROM", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "SOL", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "TRU", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "ROM", "autonomy_republic_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "set_autonomy", "TRU", "autonomy_republic_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "puppet", "SOL", ""): 2,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "release_autonomy", "SOL", "autonomy_puppet"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "release_autonomy", "SOL", "autonomy_district_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "set_autonomy", "SOL", "autonomy_free"): 2,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "set_autonomy", "SOL", "autonomy_puppet"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "set_autonomy", "SOL", "autonomy_district_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "puppet", "SOL", ""): 2,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "set_autonomy", "VAD", "autonomy_free"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "set_autonomy", "SOL", "autonomy_free"): 4,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "set_autonomy", "SOL", "autonomy_district_in_Vorkerland"): 1,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "set_autonomy", "SOL", "autonomy_puppet"): 1,
    }
)
EXPECTED_SYNC_CALLERS = Counter(
    {
        ("events/ADISCORD_vorkerland_collapse_events.txt", "ADISCORD_vorkerland_sync_all_party_identities"): 1,
        ("history/countries/WRK - WorkerLand.txt", "ADISCORD_vorkerland_sync_all_party_identities"): 1,
        ("common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt", "ADISCORD_vorkerland_sync_party_identity"): 4,
        ("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", "ADISCORD_vorkerland_sync_party_identity"): 3,
        ("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt", "ADISCORD_vorkerland_sync_party_identity"): 4,
        ("common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt", "ADISCORD_vorkerland_sync_party_identity"): 7,
        ("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", "ADISCORD_vorkerland_sync_party_identity"): 2,
    }
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise AssertionError(f"unclosed block {name}")


def block_at(text: str, start: int) -> tuple[str, int]:
    opening = text.find("{", start)
    if opening == -1:
        raise AssertionError(f"missing opening brace at {start}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if quoted and character == "\\" and not escaped:
            escaped = True
            continue
        if character == '"' and not escaped:
            quoted = not quoted
            continue
        escaped = False
        if quoted:
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1], index + 1
    raise AssertionError(f"unclosed block at {start}")


def strip_script_comments(text: str) -> str:
    stripped_lines = []
    for line in text.splitlines(keepends=True):
        quoted = False
        escaped = False
        comment = None
        for index, character in enumerate(line):
            if quoted and character == "\\" and not escaped:
                escaped = True
                continue
            if character == '"' and not escaped:
                quoted = not quoted
            elif character == "#" and not quoted:
                comment = index
                break
            escaped = False
        if comment is None:
            stripped_lines.append(line)
        else:
            newline = "\n" if line.endswith("\n") else ""
            stripped_lines.append(line[:comment] + newline)
    return "".join(stripped_lines)


def script_sources() -> dict[str, str]:
    sources = {}
    for root_name in SCRIPT_ROOTS:
        for path in sorted((ROOT / root_name).rglob("*.txt")):
            relative = path.relative_to(ROOT).as_posix()
            sources[relative] = strip_script_comments(path.read_text(encoding="utf-8-sig"))
    return sources


def transition_sites(sources: dict[str, str]) -> list[tuple[str, str, str, str, int, int]]:
    sites = []
    for relative, text in sources.items():
        for match in re.finditer(rf"(?m)^\s*puppet\s*=\s*({SUCCESSOR_PATTERN})\s*$", text):
            sites.append((relative, "puppet", match.group(1), "", match.start(), match.end()))
        for command in ("release_autonomy", "set_autonomy"):
            for match in re.finditer(rf"\b{command}\s*=\s*\{{", text):
                block, end = block_at(text, match.start())
                target = re.search(rf"\btarget\s*=\s*({SUCCESSOR_PATTERN})\b", block)
                if target is None:
                    continue
                autonomy = re.search(r"\bautonom(?:y|ous)_state\s*=\s*([A-Za-z0-9_]+)", block)
                self_description = f"{relative}:{command}:{target.group(1)}"
                if autonomy is None:
                    raise AssertionError(f"missing literal autonomy state in {self_description}")
                sites.append(
                    (relative, command, target.group(1), autonomy.group(1), match.start(), end)
                )
    return sites


def named_blocks(text: str, name: str) -> list[str]:
    blocks = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text):
        block, _ = block_at(text, match.start())
        blocks.append(block)
    return blocks


class PartyTexticonContractTests(unittest.TestCase):
    def test_all_new_sprites_resolve_to_generated_icons(self) -> None:
        gfx = read("interface/parties_texticons.gfx")
        for sprite, texture in SPRITES.items():
            with self.subTest(sprite=sprite):
                self.assertEqual(
                    len(re.findall(rf'\bname\s*=\s*"{re.escape(sprite)}"', gfx)),
                    1,
                    f"sprite declaration count: {sprite}",
                )
                block = re.search(
                    rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{sprite}"(?:(?!spriteType).)*\}}',
                    gfx,
                )
                self.assertIsNotNone(block)
                self.assertIn(f'texturefile = "{texture}"', block.group(0))
                self.assertIn("legacy_lazy_load = no", block.group(0))
                self.assertTrue((ROOT / texture).is_file())

    def test_requested_ivn_and_tva_names_have_unique_icons(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        collapse = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertIn('IVN_humanism_party: "£GFX_IVN_roar_of_freedom_party_texticon Рёв свободы"', parties)
        self.assertIn('IVN_etatism_party: "£GFX_IVN_emergency_committee_party_texticon Чрезвычайный комитет Иторы"', parties)
        self.assertIn('TVA_technocracy_party: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)
        self.assertIn('TVA_technocracy_party_long: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)

    def test_successor_helper_keys_cover_dependency_and_independence(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        for tag in ("VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"):
            self.assertIn(f"{tag}_pragmatism_party_independent:", parties)
        for key in (
            "VAD_vorkerland_imperial_party",
            "VAD_vorkerland_imperial_party_wrk_subject",
            "PWR_technocracy_party_wrk_subject",
            "ROM_etatism_party_wrk_subject",
            "TRU_chauvinism_party_wrk_subject",
        ):
            self.assertIn(f"{key}:", parties)
        for key in (
            "VAD_pragmatism_party",
            "ZAO_pragmatism_party",
            "PWR_pragmatism_party",
            "VLA_pragmatism_party",
            "ROM_pragmatism_party",
            "SOL_pragmatism_party",
            "TRU_pragmatism_party",
        ):
            line = next(line for line in parties.splitlines() if line.strip().startswith(f"{key}:"))
            self.assertIn("£GFX_WRK_worker_revolutionary_party_texticon", line)

    def test_every_required_party_key_has_one_leading_declared_texticon(self) -> None:
        self.assertEqual(len(LOCALISATION_TEXTICON_KEYS), 50)
        self.assertEqual(
            len({key for _, key, _ in LOCALISATION_TEXTICON_KEYS}),
            len(LOCALISATION_TEXTICON_KEYS),
        )
        occurrences: dict[str, list[tuple[str, str]]] = {}
        entry = re.compile(r'(?m)^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s*"([^"\r\n]*)"\s*$')
        for path in sorted((ROOT / "localisation").rglob("*.yml")):
            relative = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8-sig")
            for match in entry.finditer(text):
                occurrences.setdefault(match.group(1), []).append((relative, match.group(2)))

        gfx = read("interface/parties_texticons.gfx")
        for expected_file, key, sprite in LOCALISATION_TEXTICON_KEYS:
            with self.subTest(key=key):
                self.assertEqual(len(occurrences.get(key, [])), 1, f"localisation count: {key}")
                actual_file, value = occurrences[key][0]
                self.assertEqual(actual_file, expected_file)
                self.assertTrue(
                    value.startswith(f"£{sprite} "),
                    f"{key} must start with £{sprite}, got {value!r}",
                )
        for sprite in sorted({sprite for _, _, sprite in LOCALISATION_TEXTICON_KEYS}):
            with self.subTest(sprite=sprite):
                self.assertEqual(
                    len(re.findall(rf'\bname\s*=\s*"{re.escape(sprite)}"', gfx)),
                    1,
                    f"referenced sprite declaration count: {sprite}",
                )

    def test_russian_localisation_files_keep_utf8_bom(self) -> None:
        for relative in (
            "localisation/russian/parties_l_russian.yml",
            "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        ):
            self.assertTrue((ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"), relative)


class PartyIdentityLifecycleTests(unittest.TestCase):
    def test_sync_effect_covers_exact_successors_and_never_changes_politics(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt")
        sync = named_block(effects, "ADISCORD_vorkerland_sync_party_identity")
        self.assertEqual(set(re.findall(r"\btag\s*=\s*([A-Z]{3})", sync)), {"VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"})
        self.assertIn("OR = { is_subject_of = WRK is_subject_of = WKR }", sync)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_started", sync)
        for ideology in ("pragmatism", "technocracy", "etatism", "chauvinism"):
            self.assertIn(f"ideology = {ideology}", sync)
        for forbidden in ("set_politics", "set_popularities", "add_popularity", "elections_allowed", "promote_character", "country_leader"):
            self.assertNotIn(forbidden, sync)
        self.assertNotIn("tag = NAM", sync)
        self.assertNotIn("tag = DAN", sync)

    def test_fresh_collapse_and_autonomy_entry_points_are_bounded(self) -> None:
        history = read("history/countries/WRK - WorkerLand.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt")
        self.assertIn("ADISCORD_vorkerland_sync_all_party_identities = yes", history)
        apply_cosmetics = events.index("ADISCORD_vorkerland_apply_claimant_cosmetics = yes")
        sync_parties = events.index("ADISCORD_vorkerland_sync_all_party_identities = yes", apply_cosmetics)
        repair_identities = events.index("ADISCORD_vorkerland_repair_claimant_identities = yes", apply_cosmetics)
        self.assertLess(apply_cosmetics, sync_parties)
        self.assertLess(sync_parties, repair_identities)
        for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free", "on_subject_free"):
            blocks = named_blocks(on_actions, hook)
            self.assertEqual(len(blocks), 1, hook)
            block = blocks[0]
            self.assertEqual(
                set(re.findall(r"\btag\s*=\s*([A-Z]{3})", block)),
                set(SUCCESSOR_TAGS),
                hook,
            )
            self.assertIn("ADISCORD_vorkerland_sync_party_identity = yes", block)

    def test_repository_transition_inventory_and_sync_coverage_are_explicit(self) -> None:
        sources = script_sources()
        sites = transition_sites(sources)
        actual = Counter((relative, command, tag, autonomy) for relative, command, tag, autonomy, _, _ in sites)
        self.assertEqual(actual, EXPECTED_TRANSITIONS)

        for relative, command, tag, autonomy, start, end in sites:
            text = sources[relative]
            if command == "puppet":
                autonomy_match = re.match(r"\s*set_autonomy\s*=\s*\{", text[end:])
                self.assertIsNotNone(
                    autonomy_match,
                    f"scripted puppet lacks immediate autonomy transition: {relative}:{tag}",
                )
                autonomy_start = end + autonomy_match.start()
                autonomy_block, autonomy_end = block_at(text, autonomy_start)
                self.assertRegex(autonomy_block, rf"\btarget\s*=\s*{tag}\b")
                self.assertRegex(
                    text[autonomy_end:autonomy_end + 250],
                    rf"(?s)^\s*{tag}\s*=\s*\{{\s*ADISCORD_vorkerland_sync_party_identity\s*=\s*yes",
                    f"unsynchronized scripted puppet: {relative}:{tag}",
                )
            elif command == "release_autonomy":
                self.assertRegex(
                    text[end:end + 250],
                    rf"(?s)^\s*{tag}\s*=\s*\{{\s*ADISCORD_vorkerland_sync_party_identity\s*=\s*yes",
                    f"unsynchronized scripted release: {relative}:{tag}",
                )
            elif autonomy == "autonomy_free":
                subject_free = named_blocks(
                    sources["common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt"],
                    "on_subject_free",
                )
                self.assertEqual(len(subject_free), 1)
                self.assertIn("ADISCORD_vorkerland_sync_party_identity = yes", subject_free[0])
                self.assertIn(tag, set(re.findall(r"\btag\s*=\s*([A-Z]{3})", subject_free[0])))
            elif relative == "history/countries/WRK - WorkerLand.txt":
                self.assertIn("ADISCORD_vorkerland_sync_all_party_identities = yes", text[end:])
            else:
                self.assertRegex(
                    text[end:end + 250],
                    rf"(?s)^\s*{tag}\s*=\s*\{{\s*ADISCORD_vorkerland_sync_party_identity\s*=\s*yes",
                    f"unsynchronized set_autonomy: {relative}:{tag}:{autonomy}",
                )

    def test_sync_callers_are_explicit_and_never_recurring(self) -> None:
        sources = script_sources()
        sync_call = re.compile(
            r"\b(ADISCORD_vorkerland_sync_(?:all_party_identities|party_identity))\s*=\s*yes\b"
        )
        actual = Counter(
            (relative, match.group(1))
            for relative, text in sources.items()
            for match in sync_call.finditer(text)
        )
        self.assertEqual(actual, EXPECTED_SYNC_CALLERS)

        recurring_callers = []
        for relative, text in sources.items():
            for hook in ("on_daily", "on_weekly", "on_monthly"):
                for block in named_blocks(text, hook):
                    if sync_call.search(block):
                        recurring_callers.append((relative, hook))
        self.assertEqual(recurring_callers, [], "party identity sync must never use recurring hooks")


if __name__ == "__main__":
    unittest.main()
