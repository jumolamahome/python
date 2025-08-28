# -*- coding: utf-8 -*-
import re, os, time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ===== 可調參數 =====
FLIGHT_URL   = "https://flight.eztravel.com.tw/"
TRIP_TYPE    = "來回"           # 可填 "來回" 或 "單程"
ORIGIN_TEXT  = "台北 TPE"
DEST_TEXT    = "洛杉磯 LAX"
DEPART_DATE  = "2025/09/01"     # 格式以站方接受為準（常見：YYYY/MM/DD 或 YYYY-MM-DD）
RETURN_DATE  = "2025/09/10"

VIEW_W = 1440
VIEW_H = 900
HEADLESS = False
# ====================

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def click_if_exists(page, selector_or_role=None, name=None, timeout=1200, log_hit=None):
    try:
        if selector_or_role == "role:button":
            page.get_by_role("button", name=name).click(timeout=timeout)
        elif selector_or_role == "role:dialog-button":
            page.get_by_role("dialog").get_by_role("button", name=name).click(timeout=timeout)
        elif isinstance(selector_or_role, str):
            page.locator(selector_or_role).click(timeout=timeout)
        if log_hit:
            log(log_hit)
        return True
    except Exception:
        return False

def close_popups(page):
    log("嘗試關閉可能的彈窗（cookies/公告/訂閱）")
    # 常見關閉按鈕候選
    buttons = [
        ("role:button", "接受"), ("role:button", "我知道了"), ("role:button", "關閉"),
        ("role:button", "同意"), ("role:dialog-button", "關閉"), ("role:button", "OK"),
        ("role:button", "確定"),
        # 也嘗試直接用 selector
        ("button:has-text('接受')", None), ("button:has-text('同意')", None),
        (".close, button.close, .btn-close", None),
    ]
    for sel, name in buttons:
        hit = click_if_exists(page, sel, name=name, timeout=1200, log_hit=f"  - 點擊彈窗按鈕：{name or sel}")
        if hit:
            time.sleep(0.3)

def wait_search_form(page):
    log("等待純機票搜尋表單出現")
    candidates = [
        "text=機票搜尋", "text=搜尋機票", "text=出發地", "text=目的地",
        "input[placeholder='出發地']", "input[placeholder='目的地']",
        "text=單程", "text=來回",
    ]
    for sel in candidates:
        try:
            page.wait_for_selector(sel, timeout=8000)
            log(f"  - 搜尋表單偵測到：{sel}")
            return True
        except PWTimeout:
            continue
    log("  ✖ 等待搜尋表單逾時（仍將繼續嘗試互動）")
    return False

def ensure_roundtrip_or_oneway(page, trip_type: str):
    """切換來回/單程（盡量不依賴固定 id）"""
    log(f"切換行程類型為：{trip_type}")
    opts = [
        page.get_by_text(trip_type, exact=True),
        page.locator(f"label:has-text('{trip_type}')"),
        page.locator(f"[role='tab']:has-text('{trip_type}')"),
        page.locator(f"button:has-text('{trip_type}')"),
    ]
    for loc in opts:
        try:
            if loc.count():
                loc.first.click(timeout=1500)
                log("  ✅ 行程類型切換完成")
                return True
        except Exception:
            continue
    log("  ⚠ 找不到來回/單程切換，可能站方預設已為正確狀態")
    return False

def set_text_field(page, label_or_placeholder: str, value: str, is_origin=True) -> bool:
    """
    盡可能找到「出發地/目的地」輸入框並輸入，處理自動完成清單。
    """
    role_names = [label_or_placeholder]
    placeholders = [label_or_placeholder]
    # 常見備援關鍵字
    if is_origin:
        placeholders += ["出發地", "出發", "From", "出發城市", "城市/機場（出發）"]
    else:
        placeholders += ["目的地", "到達", "To", "目的城市", "城市/機場（到達）"]

    # 先找 input
    candidates = []
    for ph in placeholders:
        candidates.append(f"input[placeholder='{ph}']")
        candidates.append(f"input[aria-label='{ph}']")
    # 一些常見欄位 class/name 備援
    candidates += [
        "input[name*='origin']", "input[id*='origin']",
        "input[name*='from']", "input[id*='from']",
        "input[name*='destination']", "input[id*='destination']",
        "input[name*='to']", "input[id*='to']",
    ]

    # 也嘗試用 label 錨點找鄰近 input
    def by_label_neighbor(lbl: str):
        try:
            block = page.get_by_text(re.compile(lbl)).first
            if block.count():
                container = block.locator("xpath=ancestor-or-self::*[self::div or self::section or self::form][1]")
                cand = container.locator("input").first
                if cand.count():
                    return cand
        except Exception:
            pass
        return None

    # 搜尋候選 input
    loc = None
    for sel in candidates:
        try:
            l = page.locator(sel)
            if l.count():
                loc = l.first
                break
        except Exception:
            continue
    if not loc:
        loc = by_label_neighbor(label_or_placeholder)

    if not loc:
        log(f"  ✖ 找不到欄位：{label_or_placeholder}")
        return False

    try:
        loc.wait_for(state="visible", timeout=3000)
        loc.scroll_into_view_if_needed()
        loc.click()
        # 清空再填
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        loc.type(value, delay=50)  # 慢打讓自動完成彈出
        time.sleep(0.6)
        # 選第一筆候選（常見：按下 ArrowDown + Enter）
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        log(f"  ✅ 已輸入：{value}")
        return True
    except Exception as e:
        log(f"  ✖ 欄位輸入失敗：{e.__class__.__name__}")
        return False

def find_date_input(page, label_text: str, pref_ids: list):
    """找日期 input（寬鬆策略）"""
    # 1) 指定 id
    for sid in pref_ids:
        loc = page.locator(f"input{sid}")
        if loc.count():
            return loc.first

    # 2) 以 placeholder/aria-label
    keys = [label_text, "出發日期", "回程日期", "去程", "回程", "出發日", "返程"]
    for k in keys:
        for sel in [f"input[placeholder='{k}']", f"input[aria-label='{k}']"]:
            loc = page.locator(sel)
            if loc.count():
                return loc.first

    # 3) 模糊 id/name
    key = "start" if "去程" in label_text or "出發" in label_text else "end"
    fuzzy = [
        f"input[id*='{key}']", f"input[name*='{key}']",
        "input[name*='depart']", "input[id*='depart']",
        "input[name*='return']", "input[id*='return']",
        "input[name*='go']", "input[name*='back']",
        "input[name*='date']", "input[id*='date']",
    ]
    for sel in fuzzy:
        loc = page.locator(sel)
        if loc.count():
            return loc.first

    # 4) 文字錨點鄰近搜尋
    try:
        block = page.get_by_text(re.compile(label_text)).first
        if block.count():
            container = block.locator("xpath=ancestor-or-self::*[self::div or self::section or self::form][1]")
            cand = container.locator("input").first
            if cand.count():
                return cand
    except Exception:
        pass

    return None

def safe_fill_date(page, label: str, want: str) -> bool:
    log(f"填入 {label}：{want}")
    pref_ids = ["#departDate", "#goDate", "#flight-date-start"] if (label in ("去程","出發日期")) else ["#returnDate", "#backDate", "#flight-date-end"]
    loc = find_date_input(page, label, pref_ids)

    if not loc:
        log(f"  ✖ 找不到 {label} 的輸入框")
        return False

    try:
        loc.wait_for(state="visible", timeout=4000)
        loc.scroll_into_view_if_needed()
        loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        # 有些站用 readOnly + datepicker，只能點日曆；先填寫，若失敗再改走日曆點擊（此處先嘗試直填）
        loc.fill(want)
        page.keyboard.press("Enter")
        time.sleep(0.25)
    except Exception as e:
        log(f"  - {label} fill() 失敗：{e.__class__.__name__}，改用 JS 兜底")
        try:
            ok = page.evaluate(
                """
                (el, val) => {
                    if (!el) return false;
                    el.removeAttribute && el.removeAttribute('readonly');
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

    # 驗證
    try:
        real = loc.input_value(timeout=1500)[:10]
        if real == want[:10]:
            log(f"  ✅ {label} 寫入並驗證成功：{real}")
            return True
        else:
            log(f"  ⚠ {label} 寫入後不相符：目前是 {real}（期望 {want}）")
            return False
    except Exception:
        log("  ⚠ 無法讀回 input 值，可能由日曆元件接管")
        return False

def click_search(page):
    log("嘗試點擊『搜尋』按鈕")
    candidates = [
        "button:has-text('搜尋')",
        "button:has-text('搜尋機票')",
        "button:has-text('查詢')",
        "button.ez-btn.search-lg",
        "button[type='submit']",
        "[role='button']:has-text('搜尋')",
    ]
    for sel in candidates:
        try:
            page.locator(sel).first.click(timeout=3000)
            log(f"  ✅ 已點擊搜尋：{sel}")
            return True
        except Exception:
            continue
    log("  ✖ 沒有找到可點擊的搜尋按鈕")
    return False

def take_final_screenshots(page, prefix="eztravel_flight"):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("screenshots", exist_ok=True)
    vp = f"screenshots/{prefix}_viewport_{ts}.png"
    fp = f"screenshots/{prefix}_fullpage_{ts}.png"
    log("擷取截圖（可視區）"); page.screenshot(path=vp); log(f"  ✅ {vp}")
    log("擷取截圖（整頁）");   page.screenshot(path=fp, full_page=True); log(f"  ✅ {fp}")

with sync_playwright() as p:
    log("啟動 Playwright")
    browser = p.chromium.launch(headless=HEADLESS)
    log(f"已啟動 Chromium（headless={HEADLESS}）")
    page = browser.new_page(viewport={"width": VIEW_W, "height": VIEW_H})
    log(f"開新分頁並設定 viewport={VIEW_W}x{VIEW_H}")

    log(f"前往 {FLIGHT_URL}")
    page.goto(FLIGHT_URL, timeout=60000, wait_until="domcontentloaded")
    log("頁面主結構載入完成 (domcontentloaded)")

    page.wait_for_timeout(1200)
    close_popups(page)
    wait_search_form(page)

    # 切換來回 / 單程
    ensure_roundtrip_or_oneway(page, TRIP_TYPE)

    # 出發地 / 目的地
    ok_from = set_text_field(page, "出發地", ORIGIN_TEXT, is_origin=True)
    ok_to   = set_text_field(page, "目的地", DEST_TEXT,   is_origin=False)

    # 日期（單程時只填去程）
    ok_go = safe_fill_date(page, "出發日期", DEPART_DATE) or safe_fill_date(page, "去程", DEPART_DATE)
    ok_back = True
    if TRIP_TYPE == "來回":
        ok_back = safe_fill_date(page, "回程日期", RETURN_DATE) or safe_fill_date(page, "回程", RETURN_DATE)

    if ok_from and ok_to and ok_go and ok_back:
        log("🎉 純機票條件填寫完成")
    else:
        log("⚠ 純機票欄位未完全寫入成功，請檢查 selector 或日曆/自動完成互動")

    # 送出搜尋
    click_search(page)

    # 等幾秒讓結果頁載入，並截圖
    page.wait_for_timeout(8000)
    take_final_screenshots(page, prefix="eztravel_flight")

    page.wait_for_timeout(1000)
    log("關閉瀏覽器")
    browser.close()
    log("流程結束")
