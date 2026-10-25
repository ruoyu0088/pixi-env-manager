import ast
import re
import unittest
from pathlib import Path

from app import i18n


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("zh")

    def test_english_source_is_identity(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("Environment"), "Environment")
        self.assertEqual(
            i18n.t("Current environment: {}", "default"),
            "Current environment: default",
        )
        self.assertEqual(i18n.translate_dynamic("Opened 1 / 2"), "Opened 1 / 2")

    def test_chinese_exact_and_templates(self):
        i18n.set_language("zh")
        self.assertEqual(i18n.t("Environment"), "环境")
        self.assertEqual(
            i18n.t("Current environment: {}", "default"),
            "当前环境: default",
        )
        self.assertEqual(
            i18n.translate_dynamic("Opened 1 / 2"), "已打开 1 / 2"
        )
        self.assertEqual(
            i18n.translate_dynamic("3 compatible updates found"),
            "发现 3 个兼容更新",
        )
        self.assertEqual(
            i18n.t("[done] {:.1f}s\n", 1.25), "[完成] 用时 1.2s\n"
        )
        self.assertEqual(
            i18n.translate_dynamic(
                "⚠ The current environment is not installed; packages and run "
                "functions may be unavailable."
            ),
            "⚠ 当前环境尚未安装，库列表和运行功能可能不可用。",
        )

    def test_japanese_and_english_fallback(self):
        i18n.set_language("ja")
        self.assertEqual(i18n.t("Environment"), "環境")
        # Some less common strings intentionally fall back to English rather
        # than showing Chinese in a Japanese UI.
        self.assertEqual(
            i18n.translate_dynamic("Opened 1 / 2"), "Opened 1 / 2"
        )
        self.assertNotIn("环境", i18n.t("Environment"))

    def test_unknown_text_falls_through(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("Some raw pixi output"), "Some raw pixi output")
        i18n.set_language("zh")
        self.assertEqual(i18n.t("Some raw pixi output"), "Some raw pixi output")

    def test_json_catalogs_are_complete(self):
        i18n.set_language("zh")
        self.assertEqual(i18n.missing_translation_keys("ja"), [])
        self.assertIn("Environment", i18n._load_catalog("zh"))
        self.assertIn("Environment", i18n._load_catalog("ja"))

    def test_ui_source_literals_are_english(self):
        root = Path(__file__).resolve().parent.parent / "app"
        for path in root.rglob("*.py"):
            if path.name == "i18n.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertIsNone(
                        re.search(r"[\u4e00-\u9fff]", node.value),
                        "{}:{}: {}".format(path, node.lineno, node.value),
                    )


if __name__ == "__main__":
    unittest.main()
