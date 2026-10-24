import unittest

from app.toml_highlight import tokenize


def kinds_at(tokens, text, needle):
    start = text.index(needle)
    return [
        token.kind
        for token in tokens
        if token.start <= start < token.end
    ]


class TomlHighlightTests(unittest.TestCase):
    def test_common_tokens(self):
        text = (
            '# comment\n'
            '[workspace]\n'
            'name = "demo"  # trailing\n'
            'count = 3\n'
            'flag = true\n'
            'when = 2024-01-02T03:04:05Z\n'
            'items = [1, 2, "x"]\n'
        )
        tokens = tokenize(text)
        self.assertIn("comment", kinds_at(tokens, text, "# comment"))
        self.assertIn("table", kinds_at(tokens, text, "[workspace]"))
        self.assertIn("key", kinds_at(tokens, text, "name"))
        self.assertIn("string", kinds_at(tokens, text, '"demo"'))
        self.assertIn("number", kinds_at(tokens, text, "3"))
        self.assertIn("boolean", kinds_at(tokens, text, "true"))
        self.assertIn("date", kinds_at(tokens, text, "2024-01-02"))

    def test_hash_inside_string_is_not_a_comment(self):
        text = 'value = "a # not comment" # real comment\n'
        tokens = tokenize(text)
        string_start = text.index('"a #')
        comment_start = text.index("# real")
        self.assertEqual(kinds_at(tokens, text, '"a #')[0], "string")
        self.assertEqual(kinds_at(tokens, text, "# real")[0], "comment")
        for token in tokens:
            if token.kind == "string":
                self.assertLess(token.end, comment_start)
        self.assertGreater(len(tokens), 0)

    def test_multiline_string(self):
        text = 'text = """line one\nline two # inside\nline three"""\nnext = 1\n'
        tokens = tokenize(text)
        string_tokens = [token for token in tokens if token.kind == "string"]
        self.assertGreaterEqual(len(string_tokens), 1)
        self.assertGreaterEqual(max(token.end for token in string_tokens), text.index("line three"))
        self.assertEqual(kinds_at(tokens, text, "# inside")[0], "string")
        self.assertEqual(kinds_at(tokens, text, "next")[0], "key")

    def test_inline_table(self):
        text = 'point = { x = 1, y = "two" }\n'
        tokens = tokenize(text)
        self.assertIn("key", kinds_at(tokens, text, "x"))
        self.assertIn("number", kinds_at(tokens, text, "1"))
        self.assertIn("string", kinds_at(tokens, text, '"two"'))


if __name__ == "__main__":
    unittest.main()
