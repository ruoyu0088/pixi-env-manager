import unittest

from app.versions import compare_versions, is_newer


class VersionComparisonTests(unittest.TestCase):
    def test_basic_ordering(self):
        self.assertEqual(compare_versions("1.0", "1.0.0"), 0)
        self.assertEqual(compare_versions("2.5.4", "2.4.2"), 1)
        self.assertEqual(compare_versions("2.4.2", "2.5.4"), -1)

    def test_prerelease(self):
        self.assertLess(compare_versions("1.0rc1", "1.0"), 0)
        self.assertLess(compare_versions("1.0a1", "1.0b1"), 0)
        self.assertLess(compare_versions("1.0b1", "1.0rc1"), 0)
        self.assertLess(compare_versions("1.0.dev1", "1.0a1"), 0)
        self.assertGreater(compare_versions("1.0.post1", "1.0"), 0)

    def test_epoch(self):
        self.assertGreater(compare_versions("1!1.0", "2.0"), 0)

    def test_conda_style(self):
        self.assertGreater(compare_versions("2025.0", "2024.12"), 0)
        self.assertGreater(compare_versions("3.14.1", "3.14.0"), 0)
        self.assertEqual(compare_versions("1.0.0_1", "1.0.0.1"), 0)

    def test_is_newer(self):
        self.assertTrue(is_newer("2.5.4", "2.4.2"))
        self.assertFalse(is_newer("2.4.2", "2.5.4"))
        self.assertFalse(is_newer("2.4.2", "2.4.2"))


if __name__ == "__main__":
    unittest.main()
