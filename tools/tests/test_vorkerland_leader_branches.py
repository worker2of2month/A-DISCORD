"""Contracts of the four leader branches in the Vorkerland civil-war trees.

The branches of Nikita Worcker, Anton Bagley, Vlad Petrichev and Dorian Worx
are sized after the TFR USC tree and built from programmes: these tests keep
that size, the exclusive choices, the decision unlocks, the exact aggregate
previews and the lifecycle guards from eroding in later edits.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.lib import vorkerland_leader_branches as branches
from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    _blocks,
    _mutually_exclusive_focuses,
    _prerequisite_groups,
    focus_blocks,
)

ROOT = Path(__file__).resolve().parents[2]
TREES = {
    "WKR": ROOT / "focus_trees/Vorkerland/wkr/focuses.txt",
    "VAD": ROOT / "focus_trees/Vorkerland/vad/focuses.txt",
    "TVA": ROOT / "focus_trees/Vorkerland/tva/focuses.txt",
}
DECISIONS = ROOT / "common/decisions/ADISCORD_vorkerland_decisions.txt"
CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_vorkerland_categories.txt"
EVENTS = ROOT / "events/ADISCORD_vorkerland_events.txt"
IDEAS = ROOT / "common/ideas/ADISCORD_vorkerland_ideas.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
PLANS = ROOT / "common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt"

LEADERS = {
    "worker": ("WKR", branches.WKR_WORKER_BRANCH_FOCUSES),
    "executive": ("WKR", branches.WKR_EXECUTIVE_BRANCH_FOCUSES),
    "petrichev": ("VAD", branches.VAD_LEADER_BRANCH_FOCUSES),
    "worx": ("TVA", branches.TVA_LEADER_BRANCH_FOCUSES),
}
AGGREGATE_PREFIXES = ("WKR_srm_", "WKR_lrm_", "VAD_rgm_", "TVA_prm_")
GUARDS = {
    "ADISCORD_vorkerland_worker_cw": "WKR_administration_active = yes",
    "ADISCORD_vorkerland_executive_cw": "WKR_administration_active = yes",
    "ADISCORD_vorkerland_restoration_cw": "VAD_administration_active = yes",
    "ADISCORD_vorkerland_directorate_cw": "TVA_administration_active = yes",
}
# Partner requests and the replies that settle accepted deals resolve whatever
# happens to the requesting administration.
PARTNER_EVENTS = {
    "ADISCORD_vorkerland_worker_cw.64",
    "ADISCORD_vorkerland_worker_cw.65",
    "ADISCORD_vorkerland_directorate_cw.64",
    "ADISCORD_vorkerland_directorate_cw.65",
    "ADISCORD_vorkerland_directorate_cw.66",
    "ADISCORD_vorkerland_directorate_cw.67",
    "ADISCORD_vorkerland_directorate_cw.68",
    "ADISCORD_vorkerland_directorate_cw.69",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def tail(text: str, marker: str) -> str:
    return text[text.index(marker):]


def top_level_blocks(text: str, indent: str) -> dict[str, str]:
    pattern = re.compile(rf"(?m)^{indent}([A-Za-z0-9_]+) = \{{\n")
    found: dict[str, str] = {}
    for match in pattern.finditer(text):
        end = text.index(f"\n{indent}}}\n", match.end())
        found[match.group(1)] = text[match.end():end]
    return found


class LeaderBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = {tag: focus_blocks(read(path)) for tag, path in TREES.items()}
        cls.all_blocks = {fid: block for tree in cls.blocks.values() for fid, block in tree.items()}
        cls.decisions = top_level_blocks(tail(read(DECISIONS), "# --- leader_branch_decisions ---"), "\t")
        cls.categories = top_level_blocks(read(CATEGORIES), "")
        cls.events = tail(read(EVENTS), "# --- leader_branch_events ---")
        cls.ideas = top_level_blocks(tail(read(IDEAS), "# --- leader_branch_ideas ---"), "\t\t")

    def leader_view(self, leader: str) -> set[str]:
        """Focuses one campaign of a leader can see: one course or fate view."""
        tag, own = LEADERS[leader]
        others = set(branches.LEADER_BRANCH_FOCUS_IDS) - set(own)
        views: dict[tuple[str, ...], set[str]] = {}
        for focus_id in own:
            views.setdefault(branches.leader_branch_view(focus_id), set()).add(focus_id)
        visible = set(views.get((), set())) | set(views.get(("worker",), set())) | set(views.get(("executive",), set()))
        sub_views = [ids for view, ids in views.items() if len(view) == 2 or view in {("imperial",), ("joint",), ("collegial",)}]
        if sub_views:
            visible |= min(sub_views, key=len)
        foreign = {"worker": "WKR_executive_course = yes", "executive": "WKR_presidential_course = yes"}.get(leader)
        for focus_id, block in self.blocks[tag].items():
            if focus_id in others or focus_id in own:
                continue
            if foreign and foreign in block:
                continue
            visible.add(focus_id)
        return visible

    def test_every_leader_sees_a_branch_the_size_of_the_tfr_usc_tree(self) -> None:
        for leader, (_tag, own) in LEADERS.items():
            with self.subTest(leader=leader):
                self.assertGreaterEqual(len(own), 150)
                # USC, the Trump tree of TFR, shows 176 focuses.
                self.assertGreaterEqual(len(self.leader_view(leader)), 176)

    def test_every_exclusive_choice_continues_on_both_sides(self) -> None:
        followers: dict[str, set[str]] = {}
        for focus_id, block in self.all_blocks.items():
            for group in _prerequisite_groups(block):
                for parent in group:
                    followers.setdefault(parent, set()).add(focus_id)
        for focus_id in branches.LEADER_BRANCH_FOCUS_IDS:
            for other in _mutually_exclusive_focuses(self.all_blocks[focus_id]):
                with self.subTest(pair=(focus_id, other)):
                    self.assertIn(focus_id, _mutually_exclusive_focuses(self.all_blocks[other]))
                    self.assertEqual(bool(followers.get(focus_id)), bool(followers.get(other)))

    def test_branches_branch_instead_of_running_in_straight_chains(self) -> None:
        # USC has no straight chain longer than three focuses; these branches keep
        # every chain of single prerequisites to two focuses.
        for leader, (_tag, own) in LEADERS.items():
            own_set = set(own)
            children: dict[str, list[str]] = {}
            single_parent: dict[str, str] = {}
            for focus_id in own:
                groups = _prerequisite_groups(self.all_blocks[focus_id])
                for group in groups:
                    for parent in group:
                        children.setdefault(parent, []).append(focus_id)
                if len(groups) == 1 and len(groups[0]) == 1:
                    single_parent[focus_id] = next(iter(groups[0]))
            for focus_id in own:
                chain = [focus_id]
                while (
                    chain[-1] in single_parent
                    and single_parent[chain[-1]] in own_set
                    and children[single_parent[chain[-1]]] == [chain[-1]]
                ):
                    chain.append(single_parent[chain[-1]])
                with self.subTest(leader=leader, focus=focus_id):
                    self.assertLessEqual(len(chain), 2, " < ".join(chain))

    def test_every_branch_block_offers_an_exclusive_choice(self) -> None:
        for leader, (_tag, own) in LEADERS.items():
            pairs = sum(1 for focus_id in own if _mutually_exclusive_focuses(self.all_blocks[focus_id])) // 2
            with self.subTest(leader=leader):
                self.assertGreaterEqual(pairs, 18)

    def test_unlocked_decisions_exist_and_wait_for_their_focus(self) -> None:
        category_of = {}
        decisions_text = tail(read(DECISIONS), "# --- leader_branch_decisions ---")
        for category, body in top_level_blocks(decisions_text, "").items():
            for decision in top_level_blocks(body + "\n", "\t"):
                category_of[decision] = category
        for focus_id in branches.LEADER_BRANCH_FOCUS_IDS:
            for decision in re.findall(r"unlock_decision_tooltip = ([A-Za-z0-9_]+)", self.all_blocks[focus_id]):
                with self.subTest(focus=focus_id, decision=decision):
                    self.assertIn(decision, self.decisions)
                    gate = self.decisions[decision] + self.categories.get(category_of.get(decision, ""), "")
                    self.assertIn("has_completed_focus", gate)

    def test_aggregate_previews_equal_the_applied_values(self) -> None:
        for focus_id in branches.LEADER_BRANCH_FOCUS_IDS:
            block = self.all_blocks[focus_id]
            reward = "\n".join(_blocks(block, "completion_reward"))
            shown_ideas = re.findall(r"add_idea = ([A-Za-z0-9_]+_delta_idea)", reward)
            applied: dict[str, float] = {}
            for field, value in re.findall(r"add_to_variable = \{ var = (?:WKR_srm|WKR_lrm|VAD_rgm|TVA_prm)_([a-z_]+) value = (-?[0-9.]+) \}", reward):
                applied[field] = round(applied.get(field, 0.0) + float(value), 4)
            shown: dict[str, float] = {}
            for idea in shown_ideas:
                modifier = _blocks(self.ideas[idea], "modifier")[0]
                for field, value in re.findall(r"\b([a-z_]+) = (-?[0-9.]+)", modifier):
                    shown[field] = round(shown.get(field, 0.0) + float(value), 4)
            with self.subTest(focus=focus_id):
                self.assertEqual(shown, applied)

    def test_branch_events_act_only_while_their_administration_lives(self) -> None:
        for match in re.finditer(r"(?ms)^country_event = \{\n(.*?)^\}\n", self.events):
            body = match.group(1)
            event_id = re.search(r"(?m)^\tid = (\S+)$", body).group(1)
            guard = GUARDS[event_id.rsplit(".", 1)[0]]
            with self.subTest(event=event_id):
                header = body.split("\toption = {", 1)[0]
                if event_id in PARTNER_EVENTS:
                    self.assertNotIn(guard, header)
                else:
                    self.assertIn(guard, header)

    def test_treasury_changes_are_booked_in_the_monthly_ledger(self) -> None:
        sources = [tail(read(path), "# Leader branch:") for path in TREES.values()]
        sources += [
            tail(read(DECISIONS), "# --- leader_branch_decisions ---"),
            self.events,
            tail(read(EFFECTS), "# --- leader_branch_effects ---"),
        ]
        for source in sources:
            lines = source.split("\n")
            for index, line in enumerate(lines):
                if "var = ADISCORD_economy_treasury value" not in line or "effect_tooltip" in "\n".join(lines[max(0, index - 3):index]):
                    continue
                window = "\n".join(lines[max(0, index - 3):index + 6])
                with self.subTest(line=line.strip()):
                    self.assertIn("ADISCORD_economy_current_month_action_", window)

    def test_ai_plans_follow_one_side_of_each_choice(self) -> None:
        plans = top_level_blocks(tail(read(PLANS), "# --- leader_branch_plans ---"), "")
        self.assertEqual(len(plans), 4)
        for name, body in plans.items():
            focuses = re.findall(r"(?m)^\t\t([A-Za-z0-9_]+)$", _blocks(body, "ai_national_focuses")[0])
            chosen = set(focuses)
            with self.subTest(plan=name):
                self.assertGreater(len(focuses), 40)
                for focus_id in focuses:
                    self.assertIn(focus_id, self.all_blocks)
                    self.assertFalse(_mutually_exclusive_focuses(self.all_blocks[focus_id]) & chosen, focus_id)


if __name__ == "__main__":
    unittest.main()
