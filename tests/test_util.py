import unittest

from app.util import split_user_args


class ArgumentSplitTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(split_user_args("--a 1 --b two"), ["--a", "1", "--b", "two"])

    def test_quoted_windows_path(self):
        self.assertEqual(
            split_user_args('--input "C:\\a b\\data.csv"'),
            ["--input", "C:\\a b\\data.csv"],
        )

    def test_quotes_after_equals(self):
        self.assertEqual(
            split_user_args('--name="hello world"'), ["--name=hello world"]
        )

    def test_single_quotes(self):
        self.assertEqual(split_user_args("a 'b c' d"), ["a", "b c", "d"])

    def test_backslashes_preserved(self):
        self.assertEqual(split_user_args(r"--path C:\work\out"), ["--path", "C:\\work\\out"])


if __name__ == "__main__":
    unittest.main()
