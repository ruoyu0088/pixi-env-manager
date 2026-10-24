import unittest

from app import i18n


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("zh")

    def test_chinese_is_identity(self):
        i18n.set_language("zh")
        self.assertEqual(i18n.t("打开环境"), "打开环境")
        self.assertEqual(i18n.translate_dynamic("已打开 1 / 2"), "已打开 1 / 2")

    def test_english_exact_and_templates(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("打开环境"), "Open Environment")
        self.assertEqual(
            i18n.translate_dynamic("已打开 1 / 2"), "Opened 1 / 2"
        )
        self.assertEqual(
            i18n.translate_dynamic("发现 3 个兼容更新"),
            "3 compatible updates found",
        )
        self.assertEqual(
            i18n.t("[完成] 用时 {:.1f}s\n", 1.25), "[done] 1.2s\n"
        )
        self.assertEqual(
            i18n.translate_dynamic("⚠ 当前环境尚未安装，库列表和运行功能可能不可用。"),
            "⚠ The current environment is not installed; packages and run functions may be unavailable.",
        )

    def test_japanese_and_english_fallback(self):
        i18n.set_language("ja")
        self.assertEqual(i18n.t("打开环境"), "環境を開く")
        # Some less common strings intentionally fall back to English rather
        # than showing Chinese in a Japanese UI.
        self.assertNotIn("打开环境", i18n.t("打开环境"))

    def test_unknown_text_falls_through(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("Some raw pixi output"), "Some raw pixi output")


if __name__ == "__main__":
    unittest.main()
