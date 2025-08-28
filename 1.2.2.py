# -*- coding: utf-8 -*-
import re, os, time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def click_lax(page) -> bool:
    log("在主頁面用『純文字精確比對』嘗試點擊『洛杉磯』")
    try:
        loc = page.get_by_text("洛杉磯", exact=True).first
        loc.wait_for(state="visible", timeout=5000)
        loc.scroll_into_view_if_needed()
        loc.click()
        log("  ✅ 已點擊『洛杉磯』，等待新頁面載入")
        return True
    except Exception as e:
        log(f"  ✖ 點擊失敗：{e.__class__.__name__}")
        return False

def wait_new_search_bar(page):
    """等待跳轉後的新搜尋條出現（寬鬆條件，擇一即通過）"""
    candidates = [
        "#package-search-date-select-start",
        "#package-search-date-select-end",
        "text=機加酒搜尋",
        "text=去程",
        "text=回程",
    ]
    for sel in candidates:
        try:
            page.wait_for_selector(sel, timeout=8000)
            log(f"  - 新頁面搜尋條偵測到：{sel}")
            return True
        except PWTimeout:
            continue
    log("  ✖ 等待新頁面搜尋條逾時（但可能仍已載入，繼續嘗試）")
    return False

def find_date_input(page, label_text: str, pref_ids: list):
    """
    按優先序找日期 input：
    1) 指定 id
    2) input[id*='start'/'end']
    3) 以『去程/回程』文字區塊為錨點，往下找第一個 placeholder=請選擇 的 input
    """
    # 1) 指定 id
    for sid in pref_ids:
        loc = page.locator(f"input{sid}")
        if loc.count():
            return loc.first

    # 2) 模糊 id
    key = "start" if "去程" in label_text else "end"
    loc = page.locator(f"input[id*='{key}']").first
    if loc.count():
        return loc

    # 3) 文字錨點鄰近搜尋
    block = page.get_by_text(re.compile(label_text)).first
    if block.count():
        # 往祖先找容器，再在容器內找 input
        container = block.locator("xpath=ancestor-or-self::*[self::div or self::section or self::form][1]")
        cand = container.locator("input[placeholder='請選擇']").first
        if cand.count():
            return cand

    return None

def safe_fill_date(page, label: str, want: str) -> bool:
    log(f"填入 {label}：{want}")
    pref_ids = ["#package-search-date-select-start"] if label == "去程" else ["#package-search-date-select-end"]
    loc = find_date_input(page, label, pref_ids)

    if not loc:
        log(f"  ✖ 找不到 {label} 的輸入框")
        return False

    try:
        loc.wait_for(state="visible", timeout=5000)
        loc.scroll_into_view_if_needed()
        loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        loc.fill(want)
        page.keyboard.press("Enter")
        time.sleep(0.2)
    except Exception as e:
        log(f"  - {label} fill() 失敗：{e.__class__.__name__}，改用 JS 兜底")
        try:
            ok = page.evaluate(
                """
                (el, val) => {
                    if (!el) return false;
                    el.focus();
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.blur && el.blur();
                    return true;
                }
                """,
                loc.element_handle(),
                want,
            )
            if not ok:
                log(f"  ✖ {label} JS 兜底返回 false")
                return False
        except Exception as ee:
            log(f"  ✖ {label} JS 兜底失敗：{ee.__class__.__name__}")
            return False

    # 驗證實際值（只比對日期前 10 碼）
    try:
        real = loc.input_value(timeout=2000)[:10]
        if real == want:
            log(f"  ✅ {label} 寫入並驗證成功：{real}")
            return True
        else:
            log(f"  ⚠ {label} 寫入後不相符：目前是 {real}（期望 {want}）")
            return False
    except Exception:
        log("  ⚠ 無法讀回 input 值，可能被框架替換")
        return False

def take_final_screenshots(page):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("screenshots", exist_ok=True)
    vp = f"screenshots/eztravel_viewport_{ts}.png"
    fp = f"screenshots/eztravel_fullpage_{ts}.png"
    log("擷取截圖（可視區）"); page.screenshot(path=vp); log(f"  ✅ {vp}")
    log("擷取截圖（整頁）");   page.screenshot(path=fp, full_page=True); log(f"  ✅ {fp}")

with sync_playwright() as p:
    log("啟動 Playwright")
    browser = p.chromium.launch(headless=False)
    log("已啟動 Chromium（headless=False）")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    log("開新分頁並設定 viewport=1440x900")

    url = "https://packages.eztravel.com.tw/"
    log(f"前往 {url}")
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    log("頁面主結構載入完成 (domcontentloaded)")

    page.wait_for_timeout(1200)
    log("稍等 1.2 秒，讓動態區塊出現")

    log("嘗試關閉可能的彈窗（cookies/公告）")
    try:
        page.get_by_role("button", name="接受").click(timeout=1500)
        log("已點擊彈窗按鈕：接受")
    except Exception:
        log("沒有偵測到可關閉的『接受』彈窗按鈕")

    # 1) 先點『洛杉磯』，讓站方完成路由與搜尋條初始化
    if not click_lax(page):
        log("⚠ 點擊『洛杉磯』失敗，結束")
    else:
        # 2) 等新搜尋條出現
        wait_new_search_bar(page)

        # 3) 在新頁面填日期
        ok1 = safe_fill_date(page, "去程", "2025/09/01")
        ok2 = safe_fill_date(page, "回程", "2025/09/10")
        if ok1 and ok2:
            log("🎉 新頁面日期填入完成")
        else:
            log("⚠ 新頁面日期未完全寫入成功，請檢查選擇器或日曆互動")

        # 4) 點擊搜尋
        log("嘗試點擊『搜尋』按鈕")
        try:
            page.locator("button.ez-btn.search-lg", has_text="搜尋").click(timeout=3000)
            log("✅ 已點擊『搜尋』按鈕")
        except Exception as e:
            log(f"✖ 點擊搜尋按鈕失敗：{e.__class__.__name__}")

    # 截圖
    page.wait_for_timeout(10000)
    take_final_screenshots(page)

    page.wait_for_timeout(1500)
    log("關閉瀏覽器")
    browser.close()
    log("流程結束")
