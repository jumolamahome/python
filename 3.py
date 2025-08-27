from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://rdc28.cwa.gov.tw/TDB/public/warning_typhoon_list/", timeout=60000)

    page.wait_for_selector("table")  # 等待表格載入

    # 進入天兔颱風的詳細頁 (新分頁)
    with page.context.expect_page() as new_page_info:
        page.click("a[href='https://rdc28.cwa.gov.tw/TDB/public/typhoon_detail?typhoon_id=202425']")
    new_page = new_page_info.value
    new_page.wait_for_load_state("load")

    # ---- 點開「颱風概況表」 ----
    new_page.wait_for_selector("#typhoon_abstract_header")
    new_page.click("#typhoon_abstract_header")
    new_page.wait_for_selector("#typhoon_abstract.show", state="visible", timeout=10000)

    # ---- 點開「觀測資料」 ----
    new_page.wait_for_selector("div[data-target='#OBS']")
    new_page.click("div[data-target='#OBS']")
    new_page.wait_for_selector("#OBS.show", state="visible", timeout=10000)

    # 停留 5 秒給你查看
    new_page.wait_for_timeout(5000)

    browser.close()
