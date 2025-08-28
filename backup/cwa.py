import time

from playwright.sync_api import sync_playwright

def open_typhoon(name: str | None = None, index: int | None = None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()  # 方便監聽是否開新頁籤
        page = context.new_page()
        page.goto("https://rdc28.cwa.gov.tw/TDB/public/warning_typhoon_list/", timeout=60_000)

        # 等表格出現（比 sleep 穩）
        page.wait_for_selector("table tbody tr")

        rows = page.locator("table tbody tr")

        # 鎖定第三個 td 裡的 <a>
        def link_locator(r):
            return r.locator("td:nth-child(3) a")

        target_row = None
        if name:
            # 依名稱找，名稱在第三個 td
            target_row = rows.filter(has=page.locator("td:nth-child(3)"),
                                     has_text=name).first
        elif index is not None:
            # 依索引找（0 為第一列資料）
            target_row = rows.nth(index)
        else:
            raise ValueError("請提供 name 或 index 其中一個參數")

        # 確認真的有找到
        if target_row.count() == 0:
            browser.close()
            raise RuntimeError("找不到指定的颱風列，請確認名稱或索引是否正確")

        link = link_locator(target_row)

        # 有些站點會「同頁導向」，有些會「開新分頁」；兩種都處理
        # 先嘗試等新頁；若沒有，就等同頁 navigation
        with context.expect_page() as new_page_info:
            try:
                link.click()
            except Exception:
                # 如果 click 被攔或沒成功，再直接用 href 導頁（保險作法）
                href = link.get_attribute("href")
                if not href:
                    browser.close()
                    raise RuntimeError("第三個 TD 沒有連結可點")
                page.goto(href)

        # 若有新分頁，取出來並等載入；若沒有，above context.expect_page 會 timeout
        try:
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")
            print("✅ 已開新分頁開啟該颱風資料")
        except Exception:
            # 沒開新分頁代表多半是同頁導向
            page.wait_for_load_state("domcontentloaded")
            print("✅ 已在同一頁導向到該颱風資料")
        #time.sleep(5)

        # 若有新分頁，取出來並等載入；若沒有，above context.expect_page 會 timeout
        try:
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")
            print("✅ 已開新分頁顯示該颱風資料")

            # 停 5 秒再點開「颱風概況表」
            #time.sleep(5)
            new_page.click("#typhoon_abstract_header")
            print("✅ 已展開『颱風概況表』")
            time.sleep(5)

        except Exception:
            # 沒開新分頁代表多半是同頁導向
            page.wait_for_load_state("domcontentloaded")
            print("✅ 已在同一頁導向到該颱風資料")

            # 停 5 秒再點開「颱風概況表」
            time.sleep(5)
            page.click("#typhoon_abstract_header")
            print("✅ 已展開『颱風概況表』")


        # 視需要保留瀏覽器讓你手動查看
        # browser.close()

# 用法 1：依名稱點開（精準）
open_typhoon(name="海葵")   # 例子：把這裡換成實際表格中的颱風名稱



# 用法 2：依列索引點開（0 為第一列）
# open_typhoon(index=0)
