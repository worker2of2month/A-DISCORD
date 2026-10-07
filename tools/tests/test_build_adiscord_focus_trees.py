"""Check native shared-history assembly against the unchanged authored tree."""

from collections import Counter
from pathlib import Path
import unittest

from tools.builders.build_adiscord_focus_trees import (
    OUTPUT_ROOT,
    SOURCES,
    block_end,
    expected_outputs,
    render_shared_history_tree,
    render_source,
)
from tools.lib.focus_sources import read_focus_source, read_native_focus_source
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
VAL_SOURCE = "VAL/main/focuses.txt"
VAL_OUTPUT = OUTPUT_ROOT / SOURCES[VAL_SOURCE]


def one(rows, key):
    matches = [row.value for row in rows if row.key == key]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {key}, got {len(matches)}")
    return matches[0]


def semantic(rows):
    """Line positions differ after assembly; every script token must remain equal."""
    return [
        (row.key, row.quoted, semantic(row.value) if isinstance(row.value, list) else row.value)
        for row in rows
    ]


def body_text(source, row):
    start = sum(len(line) for line in source.splitlines(keepends=True)[:row.line - 1])
    opening = source.index("{", start)
    return source[opening:block_end(source, opening)]


class SharedFocusHistoryAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authored_text = render_source(VAL_SOURCE)
        cls.authored = one(parse_clausewitz(cls.authored_text), "focus_tree")
        cls.native_text = read_native_focus_source(VAL_OUTPUT)
        cls.native = parse_clausewitz(cls.native_text)
        cls.tree = one(cls.native, "focus_tree")
        cls.old_focuses = {
            one(row.value, "id"): row.value for row in cls.authored if row.key == "focus"
        }
        cls.shared_focuses = {
            one(row.value, "id"): row.value for row in cls.native if row.key == "shared_focus"
        }

    def test_actual_native_output_matches_generator(self):
        self.assertEqual(VAL_OUTPUT.read_bytes(), expected_outputs()[VAL_OUTPUT])
        self.assertIn("Native layout: shared focus history", self.native_text)

    def test_all_original_focus_bodies_and_tree_metadata_are_preserved(self):
        self.assertEqual(len(self.old_focuses), 144)
        self.assertEqual(self.old_focuses.keys(), self.shared_focuses.keys())
        self.assertFalse(any(row.key == "focus" for row in self.tree))
        for focus_id, original in self.old_focuses.items():
            with self.subTest(focus=focus_id):
                self.assertEqual(semantic(original), semantic(self.shared_focuses[focus_id]))
                authored = next(row for row in self.authored if row.key == "focus" and one(row.value, "id") == focus_id)
                native = next(row for row in self.native if row.key == "shared_focus" and one(row.value, "id") == focus_id)
                self.assertEqual(body_text(self.authored_text, authored), body_text(self.native_text, native))
        self.assertEqual(
            semantic([row for row in self.authored if row.key != "focus"]),
            semantic([row for row in self.tree if row.key != "shared_focus"]),
        )

    def test_two_root_references_cover_every_original_focus(self):
        roots = [row.value for row in self.tree if row.key == "shared_focus"]
        self.assertCountEqual(roots, ["VAL_The_Contract_State", "VAL_Stelander_Crisis_Opens"])
        prerequisites = {
            focus_id: {
                child.value
                for row in rows if row.key == "prerequisite"
                for child in row.value if child.key == "focus"
            }
            for focus_id, rows in self.shared_focuses.items()
        }
        self.assertEqual(set(roots), {key for key, parents in prerequisites.items() if not parents})
        covered = set(roots)
        while True:
            expanded = covered | {key for key, parents in prerequisites.items() if parents & covered}
            if covered == expanded:
                break
            covered = expanded
        self.assertEqual(covered, self.old_focuses.keys())

    def test_shared_ids_have_one_native_definition_and_new_tree_has_only_new_nodes(self):
        counts = Counter()
        for path in OUTPUT_ROOT.glob("*.txt"):
            for row in parse_clausewitz(read_native_focus_source(path)):
                if row.key == "shared_focus" and isinstance(row.value, list):
                    counts[one(row.value, "id")] += 1
                if row.key == "focus_tree":
                    for focus in row.value:
                        if focus.key == "focus":
                            counts[one(focus.value, "id")] += 1
        self.assertEqual({key: counts[key] for key in self.old_focuses}, dict.fromkeys(self.old_focuses, 1))
        new_native = parse_clausewitz(read_native_focus_source(OUTPUT_ROOT / SOURCES["VAL/new_world/focuses.txt"]))
        new_tree = one(new_native, "focus_tree")
        new_ids = {one(row.value, "id") for row in new_tree if row.key == "focus"}
        self.assertEqual(len(new_ids), 27)
        self.assertTrue(new_ids.isdisjoint(self.old_focuses))
        self.assertFalse(any(row.key == "shared_focus" for row in new_tree + new_native))

    def test_tooling_authored_view_is_explicitly_separate_from_native_bytes(self):
        self.assertEqual(read_focus_source(VAL_OUTPUT), self.authored_text)
        self.assertNotEqual(read_focus_source(VAL_OUTPUT), self.native_text)
        self.assertEqual(read_native_focus_source(VAL_OUTPUT), VAL_OUTPUT.read_text(encoding="utf-8-sig"))

    def test_conversion_preserves_quoted_payloads_and_comment_braces(self):
        source = '''focus_tree = {
\tid = probe
\tfocus = {
\t\tid = root
\t\tcompletion_reward = {
\t\t\tcreate_unit = "owner = VAL name = \\\"Quoted { unit }\\\""
\t\t\t# A comment can contain } without closing this reward.
\t\t\tadd_political_power = 7
\t\t}
\t}
\tfocus = {
\t\tid = child
\t\tprerequisite = { focus = root }
\t}
}
'''
        output = parse_clausewitz(render_shared_history_tree(source))
        originals = [row.value for row in one(parse_clausewitz(source), "focus_tree") if row.key == "focus"]
        converted = [row.value for row in output if row.key == "shared_focus"]
        self.assertEqual([semantic(rows) for rows in originals], [semantic(rows) for rows in converted])
        self.assertEqual([row.value for row in one(output, "focus_tree") if row.key == "shared_focus"], ["root"])

    def test_invalid_shared_graphs_fail_before_writing(self):
        for body in (
            "id = a prerequisite = { focus = missing }",
            "id = a prerequisite = { focus = a }",
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                render_shared_history_tree(f"focus_tree = {{\n\tfocus = {{ {body} }}\n}}\n")

    def test_native_shared_rewards_are_still_validated(self):
        from tools.validators.validate_adiscord_val_rework import validate_supplemental_rewards

        source = "focus_tree = {\n\tfocus = { id = probe completion_reward = { add_political_power = 10 } }\n}\n"
        ordinary = validate_supplemental_rewards(source, "")
        shared = validate_supplemental_rewards(render_shared_history_tree(source), "")
        self.assertEqual(len(ordinary), 1)
        self.assertEqual(shared, ordinary)


if __name__ == "__main__":
    unittest.main()
