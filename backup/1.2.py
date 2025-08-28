# -*- coding: utf-8 -*-
"""
目的：在 ezTravel（易遊網）的套裝行程頁面，點擊熱門目的地中的「洛杉磯」。
特色：每個關鍵步驟都 print log，方便你追流程與除錯。
"""

import re
import time
from playwright.sync_api import sync_playwright

def log(msg: str):
    """簡易時間戳記 logger（用 print，符合你的需求）。"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def click_lax_anywhere(page) -> bool:
    """
    在主頁 + 所有 iframe 逐一嘗試點擊『洛杉磯』。
    - 多種定位策略（CSS/Role/Text/XPath/JS 兜底）
    - 若抓到 <span>，會往上找到最近的 <li> 來點
    - 一般 click 失敗時會退而求其次用 force=True
    - 每個步驟都會印出 log
    """
    strategies = [
        ("CSS :has 結構匹配 (li > span)",
         lambda ctx: ctx.locator("li", has=ctx.locator("span", has_text="洛杉磯"))),
        ("ARIA Role=listitem + 名稱比對",
         lambda ctx: ctx.get_by_role("listitem", name=re.compile(r"^\s*洛杉磯\s*$"))),
        ("純文字比對（精確）",
         lambda ctx: ctx.get_by_text("洛杉磯", exact=True)),
        ("XPath: //li[span[normalize-space()='洛杉磯']]",
         lambda ctx: ctx.locator("xpath=//li[span[normalize-space()='洛杉磯']]")),
        ("先抓 span 再往上找最近 li",
         lambda ctx: ctx.locator("span:has-text('洛杉磯')")),
    ]

    def try_click_on_ctx(ctx, ctx_name: str) -> bool:
        log(f"在 {ctx_name} 嘗試點擊『洛杉磯』")
        for i, (label, build) in enumerate(strategies, start=1):
            try:
                log(f"  策略 {i}: {label}")
                loc = build(ctx).first

                # 可選：看一下目前這個策略匹配到幾個節點（方便理解）
                try:
                    cnt = build(ctx).count()
                    log(f"    - 匹配到 {cnt} 個候選元素")
                except Exception:
                    pass

                loc.wait_for(state="visible", timeout=5000)
                log("    - 元素可見，準備點擊")

                # 如果拿到的是 span，就往上找 li 再點
                try:
                    tag = loc.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "span":
                        log("    - 目前抓到的是 <span>，往上找最近的 <li>")
                        loc = loc.locator("xpath=ancestor::li[1]")
                except Exception:
                    log("    - 無法確認節點標籤，直接點原元素")

                # 確保在視口內，避免因為在可滾動容器外而點不到
                loc.scroll_into_view_if_needed()
                log("    - 已滾動到可視範圍")

                # 先一般 click，不行再 force
                try:
                    loc.click()
                    log("    ✅ 一般 click 成功")
                except Exception as e:
                    log(f"    - 一般 click 失敗：{e.__class__.__name__}，改用 force=True")
                    loc.click(force=True)
                    log("    ✅ force click 成功")

                return True
            except Exception as e:
                log(f"    ✖ 策略失敗：{e.__class__.__name__}，換下一個策略")
                continue
        log(f"  所有策略在 {ctx_name} 都沒成功")
        return False

    # 1) 先在主頁面試
    if try_click_on_ctx(page, "主頁面"):
        return True

    # 2) 再試所有 iframe
    frames = [f for f in page.frames if f != page.main_frame]
    log(f"準備嘗試所有 iframe（共 {len(frames)} 個）")
    for idx, frame in enumerate(frames, start=1):
        # 有些 frame.url 可能是空字串
        log(f"- 進入 iframe #{idx}（URL: {getattr(frame, 'url', '') or '(空)'}）")
        if try_click_on_ctx(frame, f"iframe #{idx}"):
            return True

    # 3) JS 兜底
    log("前述策略都失敗，使用 JS 兜底")
    js = """
    const nodes = Array.from(document.querySelectorAll('li span'));
    const el = nodes.find(n => (n.textContent || '').trim() === '洛杉磯');
    if (el) {
        const li = el.closest('li');
        if (li) {
            li.click();
            return true;
        }
    }
    return false;
    """
    try:
        ok = page.evaluate(js)
        if ok:
            log("✅ JS 兜底點擊成功")
        else:
            log("✖ JS 兜底失敗，沒有找到符合條件的 span/li")
        return bool(ok)
    except Exception as e:
        log(f"✖ JS evaluate 失敗：{e.__class__.__name__}")
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
    closed_popup = False
    for txt in ["同意", "接受", "我知道了", "關閉", "我同意", "OK", "確定"]:
        try:
            page.get_by_role("button", name=txt).click(timeout=1200)
            log(f"已點擊彈窗按鈕：{txt}")
            closed_popup = True
            break
        except Exception:
            continue
    if not closed_popup:
        log("沒有偵測到可關閉的彈窗或按鈕")

    # 有些網站會把熱門目的地放在分頁或折疊區塊，先試著打開
    log("嘗試打開『目的地/熱門目的地』區塊（若無則略過）")
    opened_tab = False
    try:
        page.get_by_text(re.compile("目的地|熱門目的地")).first.click(timeout=1500)
        log("已嘗試點擊『目的地/熱門目的地』相關字樣")
        opened_tab = True
    except Exception:
        log("找不到可點的『目的地/熱門目的地』字樣，可能不需要")

    # 往下捲一下，避免元素在視窗外
    try:
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(300)
        log("已向下滾動 500 像素")
    except Exception:
        log("滾動失敗（可忽略）")

    log("開始執行多手段點擊『洛杉磯』")
    success = click_lax_anywhere(page)
    if success:
        log("🎉 全流程成功：已嘗試點擊『洛杉磯』")
    else:
        log("⚠ 仍未成功點擊『洛杉磯』，可能在隱藏分頁/滾動容器/跨網域 iframe，或需先觸發其他 UI")

    # 観察一下結果（正式自動化可改為等待條件，如 URL 或欄位值變更）
    page.wait_for_timeout(20000)
    log("關閉瀏覽器")
    browser.close()
    log("流程結束")
