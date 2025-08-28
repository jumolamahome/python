# -*- coding: utf-8 -*-
"""
目的：在 ezTravel（易遊網）的套裝行程頁面，點擊熱門目的地中的「洛杉磯」。
精簡版：僅保留這次 LOG 證實有效的作法。
"""

import re
import time
from playwright.sync_api import sync_playwright

def log(msg: str):
    """簡易時間戳記 logger（用 print，符合你的需求）。"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def click_lax(page) -> bool:
    """
    直接用純文字精確比對在主頁面點『洛杉磯』。
    （本次 LOG 顯示此策略可行，移除其餘冗餘策略/iframe/JS 兜底）
    """
    log("在主頁面用『純文字精確比對』嘗試點擊『洛杉磯』")
    try:
        loc = page.get_by_text("洛杉磯", exact=True).first

        # 看看目前匹配到幾個（純紀錄/除錯用）
        try:
            cnt = page.get_by_text("洛杉磯", exact=True).count()
            log(f"  - 匹配到 {cnt} 個候選元素")
        except Exception:
            pass

        loc.wait_for(state="visible", timeout=5000)
        log("  - 元素可見，準備點擊")

        loc.scroll_into_view_if_needed()
        log("  - 已滾動到可視範圍")

        loc.click()
        log("  ✅ 一般 click 成功")
        return True

    except Exception as e:
        log(f"  ✖ 點擊失敗：{e.__class__.__name__}")
        return False


with sync_playwright() as p:
    log("啟動 Playwright")
    browser = p.chromium.launch(headless=False)
    log("已啟動 Chromium（headless=False）")

    # 調大 viewport，避免 RWD 把元素藏起來
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    log("開新分頁並設定 viewport=1440x900")

    url = "https://packages.eztravel.com.tw/"
    log(f"前往 {url}")
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    log("頁面主結構載入完成 (domcontentloaded)")

    # 等待一點點，讓熱門區塊有機會載入
    page.wait_for_timeout(1200)
    log("稍等 1.2 秒，讓動態區塊出現")

    # 嘗試關閉可能的彈窗（cookie/公告）
    log("嘗試關閉可能的彈窗（cookies/公告）")
    try:
        page.get_by_role("button", name="接受").click(timeout=1200)
        log("已點擊彈窗按鈕：接受")
    except Exception:
        log("沒有偵測到可關閉的『接受』彈窗按鈕")

    # 有些網站會把熱門目的地放在分頁或折疊區塊，先試著打開（本次 LOG 有執行，先保留）
    log("嘗試打開『目的地/熱門目的地』區塊（若無則略過）")
    try:
        page.get_by_text(re.compile("目的地|熱門目的地")).first.click(timeout=1500)
        log("已嘗試點擊『目的地/熱門目的地』相關字樣")
    except Exception:
        log("找不到可點的『目的地/熱門目的地』字樣，可能不需要")

    # 往下捲一下，避免元素在視窗外
    try:
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(300)
        log("已向下滾動 500 像素")
    except Exception:
        log("滾動失敗（可忽略）")

    log("開始執行點擊『洛杉磯』")
    success = click_lax(page)
    if success:
        log("🎉 全流程成功：已嘗試點擊『洛杉磯』")
    else:
        log("⚠ 未成功點擊『洛杉磯』，可能在隱藏分頁/滾動容器，或需先觸發其他 UI")

    # 観察一下結果（正式自動化可改為等待條件，如 URL 或欄位值變更）
    page.wait_for_timeout(20000)
    log("關閉瀏覽器")
    browser.close()
    log("流程結束")
