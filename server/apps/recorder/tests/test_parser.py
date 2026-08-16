"""recorder.parser 单元测试（纯函数，无 Django 依赖）。"""
import os
import unittest

from apps.recorder.parser import (
    detect_language,
    extract_actions,
    extract_locators,
    extract_start_url,
    parse_recording,
)


# 金样本脚本路径（仓库根 scripts/demo_login_recorded.py）
GOLD_SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "scripts", "demo_login_recorded.py",
)


class TestDetectLanguage(unittest.TestCase):
    def test_python_by_extension(self):
        self.assertEqual(detect_language("", "test.py"), "python")

    def test_javascript_by_extension(self):
        self.assertEqual(detect_language("", "test.js"), "javascript")
        self.assertEqual(detect_language("", "test.ts"), "javascript")

    def test_python_by_import(self):
        self.assertEqual(detect_language("from playwright.sync_api import sync_playwright"), "python")

    def test_javascript_by_require(self):
        self.assertEqual(detect_language("const { chromium } = require('playwright');"), "javascript")

    def test_default_python(self):
        self.assertEqual(detect_language("some random code"), "python")


class TestExtractStartUrl(unittest.TestCase):
    def test_extract_http(self):
        content = 'page.goto("http://example.com")'
        self.assertEqual(extract_start_url(content), "http://example.com")

    def test_extract_https(self):
        content = "page.goto('https://example.com/path?q=1')"
        self.assertEqual(extract_start_url(content), "https://example.com/path?q=1")

    def test_no_url(self):
        self.assertEqual(extract_start_url("page.click()"), "")


class TestExtractLocators(unittest.TestCase):
    def test_multiple_locators(self):
        content = (
            'page.get_by_role("textbox", name="用户").fill("a")\n'
            'page.get_by_text("登录").click()\n'
            'page.locator("#btn").click()\n'
        )
        locs = extract_locators(content)
        self.assertGreaterEqual(len(locs), 3)


class TestExtractActions(unittest.TestCase):
    def test_goto(self):
        content = 'page.goto("http://example.com")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "goto")
        self.assertEqual(actions[0]["value"], "http://example.com")
        self.assertEqual(warnings, [])

    def test_click_by_role(self):
        content = 'page.get_by_role("button", name="登录", exact=True).click()'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertEqual(a["type"], "click")
        self.assertEqual(a["locator_type"], "role")
        self.assertEqual(a["locator_value"], "button")
        self.assertEqual(a["name"], "登录")
        self.assertEqual(warnings, [])

    def test_fill_chinese_value(self):
        content = 'page.get_by_role("textbox", name="请输入用户名").fill("测试用户123")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertEqual(a["type"], "fill")
        self.assertEqual(a["value"], "测试用户123")
        self.assertEqual(a["name"], "请输入用户名")
        self.assertEqual(warnings, [])

    def test_fill_escaped_quotes(self):
        content = 'page.get_by_role("textbox").fill("he said \\"hello\\"")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["value"], 'he said "hello"')
        self.assertEqual(warnings, [])

    def test_press_enter(self):
        content = 'page.get_by_role("textbox").press("Enter")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "press")
        self.assertEqual(actions[0]["value"], "Enter")

    def test_get_by_text_click(self):
        content = 'page.get_by_text("欢迎回来").click()'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertEqual(a["type"], "click")
        self.assertEqual(a["locator_type"], "text")
        self.assertEqual(a["locator_value"], "欢迎回来")

    def test_locator_css(self):
        content = 'page.locator("#submit-btn").click()'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["locator_type"], "css")
        self.assertEqual(actions[0]["locator_value"], "#submit-btn")

    def test_check_uncheck(self):
        content = (
            'page.get_by_role("checkbox").check()\n'
            'page.get_by_role("checkbox").uncheck()\n'
        )
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["type"], "check")
        self.assertEqual(actions[1]["type"], "uncheck")

    def test_select_option(self):
        content = 'page.get_by_role("combobox").select_option("选项A")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "select_option")
        self.assertEqual(actions[0]["value"], "选项A")

    def test_popup_marker(self):
        content = "with page.expect_popup() as page1_info:\n    page.get_by_role('button').click()"
        actions, warnings = extract_actions(content)
        # popup 标记 + 一个 click
        self.assertGreaterEqual(len(actions), 1)
        popup_actions = [a for a in actions if a["type"] == "popup"]
        self.assertEqual(len(popup_actions), 1)

    def test_unknown_action_warning(self):
        content = 'page.some_unknown_method("arg")'
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 0)
        self.assertGreater(len(warnings), 0)

    def test_unknown_line_no_false_positive(self):
        # import 语句不应触发 warning
        content = "from playwright.sync_api import sync_playwright\nimport os\n"
        actions, warnings = extract_actions(content)
        self.assertEqual(len(actions), 0)
        self.assertEqual(warnings, [])


class TestParseRecordingGoldSample(unittest.TestCase):
    """用金样本 demo_login_recorded.py 做完整断言。"""

    @classmethod
    def setUpClass(cls):
        with open(GOLD_SAMPLE_PATH, "r", encoding="utf-8") as f:
            cls.content = f.read()
        cls.result = parse_recording(cls.content)

    def test_language(self):
        self.assertEqual(self.result["language"], "python")

    def test_framework(self):
        self.assertEqual(self.result["framework"], "playwright")

    def test_start_url(self):
        self.assertIn("127.0.0.1:8001", self.result["start_url"])
        self.assertIn("/demo/login/", self.result["start_url"])

    def test_locators_count(self):
        self.assertGreater(self.result["locators_count"], 0)

    def test_actions_count(self):
        # goto + 2 click + 2 fill + 1 click + 1 click(text) = 6 个动作
        # 实际：goto(1) + click(role textbox)(1) + fill(user)(1) + fill(pwd)(1) + click(login btn)(1) + click(欢迎回来)(1) = 6
        self.assertEqual(self.result["actions_count"], 6)

    def test_action_types(self):
        types = [a["type"] for a in self.result["actions"]]
        self.assertEqual(types[0], "goto")
        self.assertIn("click", types)
        self.assertIn("fill", types)

    def test_warnings_empty_or_popup_only(self):
        # 金样本应该 0 warnings（或只有 popup 相关，但 demo 里没有 popup）
        # 忽略与起始 URL 相关的 warning（因为有 URL 所以不应该有）
        non_trivial = [w for w in self.result["warnings"] if "起始 URL" not in w]
        self.assertEqual(non_trivial, [])

    def test_normalized_content_has_headless_env(self):
        self.assertIn('os.environ.get("HEADLESS"', self.result["normalized_content"])

    def test_normalized_content_has_import_os(self):
        self.assertIn("import os", self.result["normalized_content"])


if __name__ == "__main__":
    unittest.main()
