from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://rdc28.cwa.gov.tw/TDB/public/warning_typhoon_list/", timeout=60000)

    # 等待頁面表格載入（或你也可保留原本的 sleep）
    page.wait_for_selector("table")

    # 抓取表格 HTML（如果後面還要用得到）
    table_html = page.inner_html("table")

    # 這個連結 target="_blank" 會開新分頁，用 expect_page 抓到它
    with page.context.expect_page() as new_page_info:
        page.click("a[href='https://rdc28.cwa.gov.tw/TDB/public/typhoon_detail?typhoon_id=202425']")
    new_page = new_page_info.value

    # 等新分頁載入完成
    new_page.wait_for_load_state("load")

    # 等「颱風概況表」這個可折疊卡片的 header 出現
    new_page.wait_for_selector("#typhoon_abstract_header")

    # 點擊「颱風概況表」讓內容展開
    new_page.click("#typhoon_abstract_header")

    # 等待內容區塊展開（Bootstrap collapse 展開後會有 .show）
    new_page.wait_for_selector("#typhoon_abstract.show", state="visible", timeout=10000)

    # 停留 5 秒讓你查看
    new_page.wait_for_timeout(5000)

    browser.close()
