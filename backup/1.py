from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://rdc28.cwa.gov.tw/TDB/public/warning_typhoon_list/", timeout=60000)

    page.wait_for_timeout(5000)  # 等待 JS 載入

    # 抓取表格
    table_html = page.inner_html("table")

    # 等待新分頁打開
    with page.context.expect_page() as new_page_info:
        page.click("a[href='https://rdc28.cwa.gov.tw/TDB/public/typhoon_detail?typhoon_id=202425']")
    new_page = new_page_info.value

    # 等待新分頁載入完成
    new_page.wait_for_load_state("load")

    # 停留 5 秒讓你查看
    new_page.wait_for_timeout(5000)

    browser.close()
