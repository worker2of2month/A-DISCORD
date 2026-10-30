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


def source_focus_ids(relative):
    """Inventory raw inputs independently of the assembly result."""
    source = (ROOT / "focus_trees" / relative).read_text(encoding="utf-8")
    tree = one(parse_clausewitz(source), "focus_tree")
    focuses = [row for row in tree if row.key == "focus"]
    for line in source.splitlines():
        if not line.startswith("# @include "):
            continue
        path, section = line.removeprefix("# @include ").split("#")
        fragment = (ROOT / "focus_trees" / path).read_text(encoding="utf-8")
        marker = f"# @section {section}\n"
        if fragment.count(marker) != 1:
            raise AssertionError(f"Expected one section {section} in {path}")
        selected = fragment.split(marker, 1)[1].split("# @section ", 1)[0]
        rows = parse_clausewitz(selected)
        if any(row.key != "focus" for row in rows):
            raise AssertionError(f"Non-focus definition in {path}#{section}")
        focuses.extend(rows)
    return [one(row.value, "id") for row in focuses]


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
        self.assertCountEqual(self.old_focuses, source_focus_ids(VAL_SOURCE))
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

    def test_root_references_cover_every_original_focus(self):
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
        new_ids = [one(row.value, "id") for row in new_tree if row.key == "focus"]
        self.assertCountEqual(new_ids, source_focus_ids("VAL/new_world/focuses.txt"))
        self.assertEqual(len(new_ids), len(set(new_ids)))
        self.assertTrue(set(new_ids).isdisjoint(self.old_focuses))
        self.assertEqual({key: counts[key] for key in new_ids}, dict.fromkeys(new_ids, 1))
        self.assertEqual(
            [row.value for row in new_tree if row.key == "shared_focus"],
            ["VAL_Naval_Contract_Office"],
        )
        self.assertFalse(any(row.key == "shared_focus" for row in new_native))

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


class JointPostwarAssemblyTests(unittest.TestCase):
    SOURCE = "Vorkerland/joint_postwar/focuses.txt"

    @classmethod
    def setUpClass(cls):
        cls.authored_text = render_source(cls.SOURCE)
        cls.authored = one(parse_clausewitz(cls.authored_text), "focus_tree")
        cls.output = OUTPUT_ROOT / SOURCES[cls.SOURCE]
        cls.native_text = read_native_focus_source(cls.output)
        cls.native = parse_clausewitz(cls.native_text)
        cls.focuses = {one(row.value, "id"): row for row in cls.authored if row.key == "focus"}
        cls.shared = {one(row.value, "id"): row for row in cls.native if row.key == "shared_focus"}

    def test_unique_native_bodies_match_their_authoring_source(self):
        self.assertEqual(len(self.focuses), 52)
        self.assertEqual(self.focuses.keys(), self.shared.keys())
        self.assertEqual(self.output.read_bytes(), expected_outputs()[self.output])
        self.assertFalse(self.output.read_bytes().startswith(b"\xef\xbb\xbf"))
        for name, row in self.focuses.items():
            with self.subTest(focus=name):
                self.assertEqual(body_text(self.authored_text, row), body_text(self.native_text, self.shared[name]))
        tree = one(self.native, "focus_tree")
        self.assertFalse(any(row.key == "focus" for row in tree))
        self.assertEqual([row.value for row in tree if row.key == "shared_focus"],
                         ["WRK_joint_convene_restoration_council"])

    def test_root_covers_the_whole_graph_without_external_prerequisites(self):
        parents = {
            name: {child.value for row in focus.value if row.key == "prerequisite" for child in row.value}
            for name, focus in self.focuses.items()
        }
        self.assertFalse(set().union(*parents.values()) - self.focuses.keys())
        roots = {name for name, references in parents.items() if not references}
        self.assertEqual(roots, {"WRK_joint_convene_restoration_council"})
        covered = set(roots)
        while True:
            expanded = covered | {name for name, references in parents.items() if references & covered}
            if expanded == covered:
                break
            covered = expanded
        self.assertEqual(covered, self.focuses.keys())
        root = self.focuses["WRK_joint_convene_restoration_council"].value
        self.assertEqual(one(root, "y"), "0")

    def test_definitions_are_not_duplicated_and_other_trees_do_not_display_the_old_root(self):
        counts = Counter()
        for path in OUTPUT_ROOT.glob("*.txt"):
            for row in parse_clausewitz(read_native_focus_source(path)):
                if row.key == "shared_focus" and isinstance(row.value, list):
                    counts[one(row.value, "id")] += 1
                elif row.key == "focus_tree":
                    for focus in row.value:
                        if focus.key == "focus":
                            counts[one(focus.value, "id")] += 1
                    if path != self.output:
                        self.assertFalse({focus.value for focus in row.value if focus.key == "shared_focus"}
                                         & self.focuses.keys(), path)
        self.assertEqual({name: counts[name] for name in self.focuses}, dict.fromkeys(self.focuses, 1))
        settlement = parse_clausewitz(read_native_focus_source(OUTPUT_ROOT / SOURCES["Vorkerland/settlement/focuses.txt"]))
        self.assertFalse({one(row.value, "id") for row in one(settlement, "focus_tree") if row.key == "focus"}
                         & self.focuses.keys())


class STPCharterAssemblyTests(unittest.TestCase):
    SOURCE = "STP/civil_war/focuses.txt"
    CANDIDATES = ("sotnikov", "shabrat", "tikhoreva")

    @classmethod
    def setUpClass(cls):
        cls.root_text = (ROOT / "focus_trees" / cls.SOURCE).read_text(encoding="utf-8")
        cls.authored_text = render_source(cls.SOURCE)
        cls.authored = parse_clausewitz(cls.authored_text)
        cls.output = OUTPUT_ROOT / SOURCES[cls.SOURCE]
        cls.native_text = read_native_focus_source(cls.output)
        cls.native = parse_clausewitz(cls.native_text)

    def test_each_cabinet_is_one_explicit_fragment_with_25_unique_focuses(self):
        all_ids = []
        for candidate in self.CANDIDATES:
            with self.subTest(candidate=candidate):
                relative = f"STP/postwar/charter/{candidate}.txt"
                path = ROOT / "focus_trees" / relative
                self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                text = path.read_text(encoding="utf-8")
                section = f"# @section charter_{candidate}\n"
                self.assertEqual(text.count("# @section "), 1)
                self.assertIn(section, text)
                self.assertNotIn("# @include", text)
                rows = parse_clausewitz(text)
                self.assertEqual(len(rows), 25)
                self.assertTrue(all(row.key == "focus" for row in rows))
                ids = [one(row.value, "id") for row in rows]
                self.assertEqual(len(set(ids)), 25)
                self.assertTrue(all(name.startswith(f"STP_pc_charter_{candidate}_") for name in ids))
                all_ids.extend(ids)
                include = f"# @include {relative}#charter_{candidate}\n"
                self.assertEqual(self.root_text.count(include), 1)
        self.assertEqual(len(set(all_ids)), 75)
        common = (ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt").read_text(encoding="utf-8")
        self.assertNotIn("# @section charter_programmes", common)
        self.assertFalse(any(
            row.key == "focus" and one(row.value, "id").startswith("STP_pc_charter_")
            for row in parse_clausewitz(common)
        ))

    def test_all_authored_focuses_keep_native_scope_order_and_semantics(self):
        expected_ids = source_focus_ids(self.SOURCE)
        self.assertEqual(len(expected_ids), len(set(expected_ids)))
        for label, rows in (("authored", self.authored), ("native", self.native)):
            with self.subTest(source=label):
                self.assertEqual([row.key for row in rows], ["focus_tree"])
                tree = one(rows, "focus_tree")
                self.assertEqual(one(tree, "id"), "STP_cw_focus")
                ids = [one(row.value, "id") for row in tree if row.key == "focus"]
                self.assertCountEqual(ids, expected_ids)
                self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(semantic(self.native), semantic(self.authored))

    def test_native_header_and_fragment_expansion_match_exact_bytes(self):
        header = (
            "# Generated by tools/builders/build_adiscord_focus_trees.py; do not edit.\n"
            f"# Source: focus_trees/{self.SOURCE}\n\n"
        )
        self.assertEqual(self.output.read_bytes(), (header + self.authored_text).encode("utf-8"))
        self.assertNotIn("# @include", self.authored_text)
        self.assertNotIn("# @section", self.authored_text)
        native_tree = one(self.native, "focus_tree")
        native_focuses = {one(row.value, "id"): row for row in native_tree if row.key == "focus"}
        for candidate in self.CANDIDATES:
            text = (ROOT / f"focus_trees/STP/postwar/charter/{candidate}.txt").read_text(encoding="utf-8")
            for row in parse_clausewitz(text):
                focus_id = one(row.value, "id")
                with self.subTest(focus=focus_id):
                    self.assertEqual(body_text(text, row), body_text(self.native_text, native_focuses[focus_id]))


if __name__ == "__main__":
    unittest.main()
