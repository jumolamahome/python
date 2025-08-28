from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://packages.eztravel.com.tw/", timeout=60000)

    page.wait_for_timeout(5000)  # 等待 JS 載入
    browser.close()