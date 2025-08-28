from playwright.sync_api import sync_playwright
import os


def shot(page, name):
    os.makedirs("debug", exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()
    page.set_default_timeout(30000)  # 增加預設超時時間

    # =====================
    # 開啟 ezTravel
    # =====================
    print("🔹 開啟 ezTravel...")
    page.goto("https://www.eztravel.com.tw/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "01_home")

    # =====================
    # 目的地：洛杉磯
    # =====================
    print("🔹 輸入目的地：洛杉磯...")
    dest = page.locator("#search-flight-arrival-0")
    dest.click()
    dest.fill("")
    dest.type("洛杉磯", delay=150)
    page.wait_for_timeout(1500)

    # 點「美洲」分頁
    page.locator("span.ez-tab-item", has_text="美洲").click()

    # 選「洛杉磯」
    page.locator("ul li span", has_text="洛杉磯").first.click()
    shot(page, "02_after_pick_destination")

    # =====================
    # 選去程日期 2025/09/01
    # =====================
    print("🔹 選擇去程日期 2025/09/01...")
    depart_input = page.locator("#flight-search-date-range-0-select-start")
    depart_input.click()
    depart_input.fill("2025/09/01 (一)")
    shot(page, "03_depart_date")

    # =====================
    # 選回程日期 2025/09/30
    # =====================
    print("🔹 選擇回程日期 2025/09/30...")
    return_input = page.locator("#flight-search-date-range-0-select-end")
    return_input.click()
    return_input.fill("2025/09/30 (二)")
    shot(page, "04_return_date")

    # =====================
    # 選人數（改成 2 成人）
    # =====================
    print("🔹 調整人數為 2 成人...")
    people_box = page.locator("#flight-search-people")
    people_box.click()
    page.wait_for_timeout(1000)

    # 成人 +1
    plus_adult = page.locator("div.Engine_room_people-modal_row___ZS3l", has_text="成人") \
        .locator("svg.ez-icon.content-open").first
    plus_adult.click()
    page.wait_for_timeout(500)

    # 收回人數選單
    page.locator("span.ez-search-engine-text-field_with-drop_select-text", has_text="2 成人・0 孩童・0 嬰兒").click()
    shot(page, "05_member")

    # =====================
    # 按搜尋並等待結果載入
    # =====================
    print("🔹 按下搜尋按鈕...")
    page.locator("button.ez-btn.search-lg").first.click()

    # 等待搜尋結果區塊出現（改為等待機票「選擇」按鈕）
    print("🔹 等待搜尋結果載入...")
    page.wait_for_selector("a.flight-list-button", timeout=30000)
    shot(page, "06_search_result")
    print("🔹 搜尋結果頁已載入，停留在同一頁面")

    # =====================
    # 選擇去程機票
    # =====================
    print("🔹 選擇去程機票...")
    departure_btn = page.locator("a.flight-list-button").first
    departure_btn.click()
    shot(page, "07_after_select_departure")

    # =====================
    # 選擇回程機票
    # =====================
    print("🔹 等待回程機票列表載入...")
    page.wait_for_selector("a.flight-prices-button", timeout=30000)
    print("🔹 選擇回程機票...")
    return_btn = page.locator("a.flight-prices-button").first
    return_btn.click()
    shot(page, "08_after_select_return")

    # =====================
    # 點選「訂購」按鈕
    # =====================
    # 等待「訂購」按鈕所在的區塊載入
    # 透過等待父元素 li.flight-seat-item 來確保網頁已載入完成
    print("🔹 等待「訂購」按鈕所在區塊載入...")
    page.wait_for_selector("li.flight-seat-item", timeout=30000)

    # 使用 locator() 搭配 has_text 精準定位並點擊按鈕
    print("🔹 點選「訂購」按鈕...")
    order_btn = page.locator("a.flight-commit-button", has_text="訂購").first
    order_btn.click()
    shot(page, "09_after_click_order")

    # =====================
    # 等待進入訂單確認頁
    # =====================
    print("🔹 等待進入訂單確認頁...")
    page.wait_for_load_state("networkidle", timeout=30000)
    print("🔹 已進入訂單確認頁")
    shot(page, "10_checkout_page")

    # 暫停程式，手動確認
    input("🔹 按 Enter 鍵結束程式並關閉瀏覽器...")
    browser.close()
