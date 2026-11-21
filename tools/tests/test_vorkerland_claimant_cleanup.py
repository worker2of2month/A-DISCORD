from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ON_ACTIONS = ROOT / "common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"
EFFECTS = ROOT / "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
ROUTER = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
ABSORBED = "event_target:ADISCORD_vorkerland_absorbed_country"


def read(path: Path = ON_ACTIONS) -> str:
    return path.read_text(encoding="utf-8-sig")


def compact(text: str) -> str:
    return " ".join(text.split())


def named_block(text: str, name: str) -> str:
    start = text.index(f"{name} = {{")
    depth = 0
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unclosed block: {name}")


class VorkerlandClaimantCleanupTests(unittest.TestCase):
    def test_reserved_losing_claimant_is_consumed_by_the_live_winner(self) -> None:
        source = compact(read())
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_claimant_cleanup_reserved",
            source,
        )
        self.assertIn(
            "ROOT = { ADISCORD_vorkerland_fold_worx_protectorates = yes "
            "ADISCORD_vorkerland_absorb_into_central_victor = yes }",
            source,
        )
        absorb = compact(named_block(read(EFFECTS), "ADISCORD_vorkerland_absorb_into_central_victor"))
        self.assertTrue(absorb.startswith(
            "ADISCORD_vorkerland_absorb_into_central_victor = { "
            "save_event_target_as = ADISCORD_vorkerland_absorbed_country"
        ))
        self.assertNotIn("ROOT", absorb)
        self.assertGreaterEqual(
            absorb.count(f"annex_country = {{ target = {ABSORBED} transfer_troops = yes }}"),
            5,
        )
        for route in (
            "ADISCORD_vorkerland_is_main_claimant = yes",
            "is_subject = yes",
            "OVERLORD = {",
            "tag = WTD",
            "TVA = {",
            "tag = VLA",
            "WKR = {",
            "tag = SOL",
            "VAD = {",
            "tag = event_target:ADISCORD_vorkerland_nation",
        ):
            with self.subTest(route=route):
                self.assertIn(route, absorb)
        # The unified country is the claimant that kept its tag; the retired
        # WRK tag is never the live winner.
        self.assertNotIn("tag = WRK", absorb)

    def test_tva_aligned_ostfort_is_annexed_before_defeated_tva(self) -> None:
        fold = compact(named_block(read(EFFECTS), "ADISCORD_vorkerland_fold_worx_protectorates"))
        self.assertIn("tag = TVA", fold)
        self.assertNotIn("ROOT", fold)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_worx_aligned_technocrats", fold)
        self.assertIn("annex_country = { target = WTD transfer_troops = no }", fold)
        for block in (
            "ROOT = { ADISCORD_vorkerland_fold_worx_protectorates = yes "
            "ADISCORD_vorkerland_absorb_into_central_victor = yes }",
            "ADISCORD_vorkerland_fold_worx_protectorates = yes "
            "ADISCORD_vorkerland_absorb_into_central_victor = yes } }",
        ):
            with self.subTest(block=block):
                self.assertIn(block, compact(read()))

    def test_tva_authored_technocrat_satellites_do_not_become_orphans(self) -> None:
        fold = compact(named_block(read(EFFECTS), "ADISCORD_vorkerland_fold_worx_protectorates"))
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_joined_worx_directorate",
            fold,
        )
        self.assertIn("annex_country = { target = TGD transfer_troops = no }", fold)

    def test_last_ally_of_a_reserved_claimant_releases_the_shell(self) -> None:
        router = read(ROUTER)
        router = router.split("# BEGIN vorkerland_collapse:on_capitulation\n", 1)[1]
        router = compact(router.split("# END vorkerland_collapse:on_capitulation", 1)[0])
        self.assertEqual(router.count("FROM = { ADISCORD_vorkerland_central_claimant_victor = yes }"), 2)
        release = router[router.index("ROOT = { ADISCORD_vorkerland_releases_claimant_shell = yes }"):]
        release = release[: release.index("# Dirty-zone neighbours")]
        self.assertIn("set_global_flag = skip_default_capitulation", release)
        self.assertIn("ADISCORD_vorkerland_distribute_central_states_to_cobelligerents = yes", release)
        self.assertIn("flag = ADISCORD_vorkerland_shell_release_current value = 1 days = 1", release)

        generic = compact(read())
        consume = generic[generic.index("ROOT = { has_country_flag = ADISCORD_vorkerland_shell_release_current }"):]
        self.assertIn("ROOT = { clr_country_flag = ADISCORD_vorkerland_shell_release_current }", consume)
        for claimant in ("WKR", "VAD", "TVA"):
            with self.subTest(claimant=claimant):
                self.assertIn(
                    f"{claimant} = {{ if = {{ limit = {{ ADISCORD_vorkerland_shell_released_by_root = yes }} "
                    "ADISCORD_vorkerland_distribute_central_states_to_cobelligerents = yes",
                    consume,
                )
        self.assertLess(
            consume.index("TVA = {"),
            consume.index("ROOT = { if = { limit = { exists = yes } ADISCORD_vorkerland_absorb_into_central_victor = yes } }"),
        )

        triggers = read(TRIGGERS)
        shell = compact(named_block(triggers, "ADISCORD_vorkerland_shell_released_by_root"))
        self.assertIn("has_country_flag = ADISCORD_vorkerland_claimant_cleanup_reserved", shell)
        self.assertIn("NOT = { tag = ROOT }", shell)
        released = compact(named_block(triggers, "ADISCORD_vorkerland_releases_claimant_shell"))
        self.assertIn("NOT = { ADISCORD_vorkerland_is_main_claimant = yes }", released)
        victor = compact(named_block(triggers, "ADISCORD_vorkerland_central_claimant_victor"))
        for route in ("tag = WTD", "tag = VLA", "tag = SOL", "ADISCORD_vorkerland_has_live_claimant_leader = yes"):
            with self.subTest(route=route):
                self.assertIn(route, victor)


    def test_minor_subject_of_a_defeated_claimant_falls_with_it(self):
        # Such a subject leaves the war with its overlord and never sends its own
        # capitulation callback, so it can neither hold the shell nor stay outside.
        triggers = read(TRIGGERS)
        exclusion = "NOT = { AND = { is_subject_of = PREV is_major = no } }"
        for name in (
            "ADISCORD_vorkerland_has_surviving_coalition_partner",
            "ADISCORD_vorkerland_shell_released_by_root",
        ):
            with self.subTest(trigger=name):
                self.assertIn(exclusion, compact(named_block(triggers, name)))
        distribute = compact(
            named_block(read(EFFECTS), "ADISCORD_vorkerland_distribute_central_states_to_cobelligerents")
        )
        self.assertIn(
            "OR = { has_war_together_with = FROM has_war_with = PREV.PREV }", distribute
        )
        self.assertIn("ADISCORD_vorkerland_is_main_claimant = yes", distribute)
        self.assertIn("NOT = { has_capitulated = yes }", distribute)
        fold = compact(named_block(read(EFFECTS), "ADISCORD_vorkerland_fold_worx_protectorates"))
        for protectorate in ("WTD", "TGD"):
            with self.subTest(protectorate=protectorate):
                self.assertIn(
                    f"{protectorate} = {{ exists = yes OR = {{ has_capitulated = yes is_subject_of = TVA }}",
                    fold,
                )

if __name__ == "__main__":
    unittest.main()
