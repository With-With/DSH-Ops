# 演示用 codegen 录制脚本（目标：DSH-Ops 自带的演示登录页）
# 用于 P1 冒烟：录制接收 -> 解析 -> 带 trace 回放 全链自包含验证
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.goto("http://127.0.0.1:8001/api/demo/login/")
    page.get_by_role("textbox", name="请输入用户名").click()
    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")
    page.get_by_role("textbox", name="请输入密码").fill("admin123456")
    page.get_by_role("button", name="登录", exact=True).click()
    page.get_by_text("欢迎回来").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
