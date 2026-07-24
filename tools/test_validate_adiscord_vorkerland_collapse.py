import unittest

from tools.vorkerland_collapse_manifest import (
    CAPITALS,
    CONTAMINATED_STATES,
    DIRTY_GROUPS,
    STATE_PARTITIONS,
    TAGS,
)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_unique_and_complete(self):
        self.assertEqual(len(TAGS), len(set(TAGS)))
        self.assertEqual(len(TAGS), 16)
        self.assertEqual(len(CONTAMINATED_STATES), 37)
        self.assertEqual(
            set().union(*map(set, DIRTY_GROUPS.values())),
            CONTAMINATED_STATES - {23, 24, 57, 59, 60},
        )
        self.assertEqual(set(STATE_PARTITIONS), {71, 72, 74, 76, 80})
        self.assertEqual(set(CAPITALS), set(TAGS))
