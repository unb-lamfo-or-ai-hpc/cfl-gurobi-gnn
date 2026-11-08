import unittest
from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "scripts/evidence/mvp2_concurrent_mip.py"
SPEC = spec_from_file_location("mvp2_concurrent_mip", SOURCE)
CAMPAIGN = module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


class CampaignDesignTests(unittest.TestCase):
    def test_five_profiles_and_three_methods_have_complete_pairing(self):
        rows = CAMPAIGN.matrix()
        self.assertEqual(len({row["id"] for row in rows}), 330)
        self.assertEqual(len(rows), 330)
        self.assertEqual(Counter(row["difficulty"] for row in rows),
                         {"easy": 90, "medium": 150, "hard": 90})
        self.assertEqual({row["instance"] for row in rows if row["difficulty"] == "hard"},
                         {"H0", "H5", "H10", "H15", "H20", "H25"})
        self.assertEqual({(row["threads"], row["concurrent"]) for row in rows},
                         {(1, 1), (4, 1), (4, 2), (8, 1), (8, 2)})
        for row in rows:
            self.assertEqual(set(row["methods"]), {"M0", "M1", "M2"})
            self.assertLessEqual(row["concurrent"], row["threads"])
            self.assertNotIn("F", row["instance"])

    def test_allocations_and_complete_array_indexing(self):
        rows = CAMPAIGN.matrix()
        self.assertEqual(CAMPAIGN.budget(rows), {
            "instances": 22, "blocks": 330, "solves": 990,
            "solver_physical_core_hours_ceiling": 4950,
            "reserved_physical_core_hours_ceiling": 6600,
            "peak_blocks": 4, "memory_mib_per_block": 65536,
            "peak_memory_mib": 262144, "peak_physical_cores": 32,
        })
        for threads, count in ((1, 66), (4, 132), (8, 132)):
            actual = [CAMPAIGN.block_at(threads, i) for i in range(count)]
            self.assertEqual(actual, [row for row in rows if row["threads"] == threads])
            with self.assertRaises(ValueError):
                CAMPAIGN.block_at(threads, count)


if __name__ == "__main__":
    unittest.main()
