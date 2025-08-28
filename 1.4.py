# -*- coding: utf-8 -*-
"""
目標：
1) 進入 https://packages.eztravel.com.tw/
2) 點選熱門目的地「洛杉磯」
3) 設定出發日：2025/09/01 (一)
   設定回國日：2025/10/01 (三)

特色：
- 全程 print log，方便追蹤
- 先以「打開日曆 → 點日期」為主；找不到日曆才退回填 input（含 JS 兜底）
- 日期欄位採「多選擇器 + 跨 iframe 掃描」策略
- 針對常見日曆元件提供多組 selector（flatpickr / aria-label / data-date / RDP 等）
- 設完後讀取畫面上的「去程/回程」顯示文字做驗證，必要時重試
"""

import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ------------------- 基礎工具 -------------------

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def tw_aria_labels(dt: datetime):
    # 產出一些常見 aria-label 變體（中文/數字/零補齊/斜線/破折）
    y, m, d = dt.year, dt.month, dt.day
    w_map = ["一", "二", "三", "四", "五", "六", "日"]
    # 星期幾（有些 aria 會帶，但我們不強依賴）
    # labels 不加星期，避免過度擬合
    return [
        f"{y}年{m}月{d}日",
        f"{y}-{m:02d}-{d:02d}",
        f"{y}/{m:02d}/{d:02d}",
        f"{y}/{m}/{d}",
        f"{y}-{m}-{d}",
    ]

def to_dt(s: str) -> datetime:
    # 接受 "2025/09/01 (一)" 或 "2025/09/01"
    s = s.strip()
    s = s.split()[0]  # 去掉 (一)
    return datetime.strptime(s, "%Y/%m/%d")

# ------------------- 點選「洛杉磯」 -------------------

def click_lax_anywhere(page) -> bool:
    candidates = [
        lambda ctx: ctx.locator("li", has=ctx.locator("span", has_text="洛杉磯")),
        lambda ctx: ctx.get_by_role("listitem", name=re.compile(r"^\s*洛杉磯\s*$")),
        lambda ctx: ctx.get_by_text("洛杉磯", exact=True),
        lambda ctx: ctx.locator("xpath=//li[span[normalize-space()='洛杉磯']]"),
        lambda ctx: ctx.locator("span:has-text('洛杉磯')"),
    ]

    def try_click_on_ctx(ctx):
        for build in candidates:
            try:
                loc = build(ctx).first
                loc.wait_for(state="visible", timeout=4000)
                try:
                    tag = loc.evaluate("el => el.tagName?.toLowerCase && el.tagName.toLowerCase()")
                    if tag == "span":
                        loc = loc.locator("xpath=ancestor::li[1]") or loc
                except Exception:
                    pass
                loc.scroll_into_view_if_needed()
                try:
                    loc.click()
                except Exception:
                    loc.click(force=True)
                return True
            except Exception:
                continue
        return False

    if try_click_on_ctx(page):
        return True
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        if try_click_on_ctx(fr):
            return True

    # JS 兜底
    js = """
    const nodes = Array.from(document.querySelectorAll('li span, span'));
    const el = nodes.find(n => (n.textContent || '').trim() === '洛杉磯');
    if (el) {
        (el.closest('li') || el).click();
        return true;
    }
    return false;
    """
    try:
        return bool(page.evaluate(js))
    except Exception:
        return False

# ------------------- 找到日期區塊 / 打開日曆 -------------------

def find_date_inputs(ctx, which: str):
    # which: start / end
    locs = []
    if which == "start":
        locs += [
            ctx.locator("#flight-search-date-range-0-select-start"),
            ctx.locator("input[id^='flight-search-date-range'][id$='select-start']"),
            ctx.locator("input[id*='date-range'][id$='select-start']"),
        ]
        near = ["出發", "去程", "去程日期", "出發日"]
    else:
        locs += [
            ctx.locator("#flight-search-date-range-0-select-end"),
            ctx.locator("input[id^='flight-search-date-range'][id$='select-end']"),
            ctx.locator("input[id*='date-range'][id$='select-end']"),
        ]
        near = ["回國", "回程", "回程日期", "回程日", "返程"]

    for w in near:
        locs.append(
            ctx.locator(
                f'''xpath=(//*[contains(normalize-space(.), "{w}")])[1]'''
            ).locator('xpath=.//following::*[self::input or self::div]//input[@placeholder="請選擇"][1]')
        )
        locs.append(
            ctx.locator(
                f'''xpath=(//*[contains(normalize-space(.), "{w}")])[1]//following::input[1]'''
            )
        )

    locs.append(ctx.get_by_placeholder("請選擇"))
    return locs

def open_calendar_for(ctx, which: str) -> bool:
    for i, cand in enumerate(find_date_inputs(ctx, which), start=1):
        try:
            el = cand.filter(has_not=ctx.locator("[disabled]")).first
            el.wait_for(state="visible", timeout=2000)
            el.scroll_into_view_if_needed()
            el.click()
            return True
        except Exception:
            continue
    return False

# ------------------- 在日曆面板選日期 -------------------

def pick_date_on_any_calendar(ctx, target_dt: datetime) -> bool:
    """
    嘗試在目前可見的日曆面板選到 target_dt。
    支援常見 selector：
      - button[aria-label*='yyyy年m月d日' / 'yyyy-mm-dd' / 'yyyy/mm/dd']
      - [data-date='yyyy-mm-dd'] / [data-date='yyyy/mm/dd']
      - .flatpickr-day[aria-label] / .rdp-day[aria-label]
      - 回退：當月面板中找 .day/.rdp-day 文字=日數，並確保屬於當月
    另外提供月份導航（下一月 / 下一頁）按鈕常見 selector。
    """
    labels = tw_aria_labels(target_dt)
    y, m, d = target_dt.year, target_dt.month, target_dt.day

    # 所有可能含日曆的容器（dialog、popover、.calendar、.flatpickr）
    containers = [
        "[role='dialog']",
        "[role='application']",
        ".flatpickr-calendar",
        ".datepicker",
        ".calendar",
        ".date-picker",
        ".rdp",         # react-day-picker
        "body",         # 最後退回整頁找
    ]

    # 月份導航按鈕（盡量通用）
    next_btn_sel = [
        "[aria-label*='下']",
        "[aria-label*='next']",
        ".flatpickr-next-month",
        ".rdp-nav_button_next",
        "button:has-text('下一月')",
        "button:has-text('下一步')",
        "button:has-text('Next')",
        "button:has-text('›')",
        "button:has-text('>')",
    ]
    prev_btn_sel = [
        "[aria-label*='上']",
        "[aria-label*='prev']",
        ".flatpickr-prev-month",
        ".rdp-nav_button_prev",
        "button:has-text('上一月')",
        "button:has-text('上一步')",
        "button:has-text('Prev')",
        "button:has-text('‹')",
        "button:has-text('<')",
    ]

    def try_click_date_in(container):
        # 1) aria-label 精準/包含搜尋
        for lbl in labels:
            loc = container.locator(f"[aria-label='{lbl}'], [aria-label*='{lbl}']").first
            if loc.count() > 0:
                try:
                    loc.scroll_into_view_if_needed()
                    loc.click()
                    return True
                except Exception:
                    pass
        # 2) data-date 格式
        for pat in [f"{y}-{m:02d}-{d:02d}", f"{y}/{m:02d}/{d:02d}", f"{y}-{m}-{d}", f"{y}/{m}/{d}"]:
            loc = container.locator(f"[data-date='{pat}'], [data-value='{pat}']").first
            if loc.count() > 0:
                try:
                    loc.scroll_into_view_if_needed()
                    loc.click()
                    return True
                except Exception:
                    pass
        # 3) 常見日格 class（flatpickr / react-day-picker 等）
        day_loc = container.locator(
            ".flatpickr-day, .rdp-day, .day, [role='gridcell'] button, [role='gridcell'] .day"
        ).filter(has_text=str(d)).first
        if day_loc.count() > 0:
            try:
                day_loc.scroll_into_view_if_needed()
                day_loc.click()
                return True
            except Exception:
                pass
        return False

    # 先嘗試直接找到日期；找不到時試著翻月（最多前後各 18 個月，避免無限迴圈）
    for cont_sel in containers:
        container = ctx.locator(cont_sel).first
        if container.count() == 0:
            continue

        # 先試直接點（有些會自動對到輸入框當月）
        if try_click_date_in(container):
            return True

        # 嘗試翻月
        # 找到月份標頭（盡量通用：包含年/月字樣）
        # 若抓不到標頭，我們也會盲翻 next 若存在
        try:
            def month_title_text():
                for s in [
                    ".flatpickr-current-month",
                    ".rdp-caption_label",
                    "[class*='month']",
                    "[class*='caption']",
                ]:
                    t = container.locator(s).first
                    if t.count() > 0:
                        try:
                            return t.inner_text().strip()
                        except Exception:
                            continue
                return ""

            # 定義翻頁器
            def click_first_exist(selectors):
                for s in selectors:
                    btn = container.locator(s).first
                    if btn.count() > 0 and btn.is_enabled():
                        try:
                            btn.click()
                            return True
                        except Exception:
                            continue
                return False

            # 為了保守，不從現在月算；直接最多往後點 24 次找得到為止
            for _ in range(24):
                if try_click_date_in(container):
                    return True
                if not click_first_exist(next_btn_sel):
                    break
                ctx.wait_for_timeout(100)

            # 再往前找一輪
            for _ in range(24):
                if try_click_date_in(container):
                    return True
                if not click_first_exist(prev_btn_sel):
                    break
                ctx.wait_for_timeout(100)
        except Exception:
            pass

    return False

# ------------------- 填 input（最後手段） -------------------

def try_fill_or_js(ctx, locator, value, label) -> bool:
    try:
        locator.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        locator.click(timeout=1500)
    except Exception:
        pass
    # 選取清空
    for key in ("Control+A", "Meta+A"):
        try:
            locator.press(key)
            break
        except Exception:
            continue
    try:
        locator.press("Delete")
    except Exception:
        pass

    # fill
    try:
        locator.fill(value, timeout=2000)
        try:
            locator.evaluate("el => el.dispatchEvent(new Event('input', {bubbles:true}))")
            locator.evaluate("el => el.dispatchEvent(new Event('change', {bubbles:true}))")
            locator.evaluate("el => el.blur && el.blur()")
        except Exception:
            pass
        got = locator.input_value(timeout=2000)
        if got == value:
            log(f"✅ {label}（{value}）以 fill() 設定成功")
            return True
    except Exception as e:
        log(f"fill 失敗（{label}）：{e.__class__.__name__}，改走 JS")

    # JS 設值
    try:
        ok = ctx.evaluate("""([el, val]) => {
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.blur && el.blur();
            return true;
        }""", [locator.element_handle(), value])
        if ok:
            got = locator.input_value(timeout=2000)
            if got == value:
                log(f"✅ {label}（{value}）以 JS 設定成功")
                return True
    except Exception as e:
        log(f"JS 設值失敗（{label}）：{e.__class__.__name__}")
    return False

def set_date_via_ui(page, which: str, value: str) -> bool:
    dt = to_dt(value)
    contexts = [page] + [f for f in page.frames if f != page.main_frame]
    for idx, ctx in enumerate(contexts):
        ctx_name = "主頁面" if idx == 0 else f"iframe#{idx}"
        try:
            log(f"在 {ctx_name} 嘗試以『日曆點選』設定 {which}：{value}")
            if not open_calendar_for(ctx, which):
                continue
            # 等日曆出現一會兒
            ctx.wait_for_timeout(150)
            if pick_date_on_any_calendar(ctx, dt):
                log(f"✅ 以日曆完成 {which} = {value}")
                return True
        except Exception as e:
            log(f"  {ctx_name} 點日曆例外：{e.__class__.__name__}")
    log(f"✖ 未能以日曆設定 {which}，將退回填 input")
    # 退回填 input
    for idx, ctx in enumerate(contexts):
        ctx_name = "主頁面" if idx == 0 else f"iframe#{idx}"
        try:
            for cand in find_date_inputs(ctx, which):
                try:
                    inp = cand.filter(has_not=ctx.locator("[disabled]")).first
                    inp.wait_for(state="visible", timeout=2000)
                    if try_fill_or_js(ctx, inp, value, "出發日" if which=="start" else "回國日"):
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False

# ------------------- 驗證目前畫面上的日期 -------------------

def read_display_values(page):
    """
    嘗試從畫面上讀「去程 / 回程」的顯示文字。
    依據常見結構，抓包含『去程』『回程』附近的日期字樣。
    """
    texts = {"start": "", "end": ""}
    containers = [
        page.locator("section, form, .date, .date-range, .range, .search, body")
    ]
    # 簡單做法：找含「去程」的元素的後續文字，與含「回程」的後續文字
    def grab(which, words):
        for w in words:
            locator = page.locator(f"xpath=//*[contains(normalize-space(),'${w}')] | //*[contains(normalize-space(), '{w}')]").first
            if locator.count() == 0:
                continue
            try:
                # 往後找可能的日期元素
                next_el = locator.locator("xpath=.//following::*[contains(text(),'2025') or contains(text(),'20')][1]").first
                if next_el.count() > 0:
                    t = next_el.inner_text().strip()
                    if re.search(r"\d{4}[/\-]\d{1,2}[/\-]\d{1,2}", t):
                        return t
            except Exception:
                continue
        return ""

    texts["start"] = grab("start", ["去程", "出發"])
    texts["end"]   = grab("end",   ["回程", "回國", "返程"])
    return texts

# ------------------- 主流程 -------------------

if __name__ == "__main__":
    with sync_playwright() as p:
        log("啟動 Playwright")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        url = "https://packages.eztravel.com.tw/"
        log(f"前往 {url}")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # 可能的 cookie/彈窗先關掉
        log("嘗試關閉可能的彈窗")
        for txt in ["同意", "接受", "我知道了", "關閉", "我同意", "OK", "確定"]:
            try:
                page.get_by_role("button", name=txt).click(timeout=1500)
                log(f"已處理彈窗按鈕：{txt}")
                break
            except Exception:
                pass

        # 有些頁面需要點「目的地」區塊才出現清單
        try:
            page.get_by_text("目的地", exact=False).click(timeout=1500)
            log("已嘗試打開『目的地』區塊")
        except Exception:
            pass

        page.wait_for_timeout(800)

        # 點選「洛杉磯」
        log("嘗試點擊『洛杉磯』")
        if click_lax_anywhere(page):
            log("✅ 已點擊『洛杉磯』")
        else:
            log("⚠ 未能點擊『洛杉磯』（可能在隱藏分頁/iframe）")

        # === 以「日曆點選」設定日期 ===
        dep_value = "2025/09/01 (一)"
        ret_value = "2025/10/01 (三)"

        ok_dep = set_date_via_ui(page, which="start", value=dep_value)
        page.wait_for_timeout(200)
        ok_ret = set_date_via_ui(page, which="end",   value=ret_value)

        # 最終驗證
        page.wait_for_timeout(300)
        shown = read_display_values(page)
        log(f"畫面顯示 → 去程: {shown.get('start')!r}；回程: {shown.get('end')!r}")

        dep_ok = "2025/09/01" in (shown.get("start") or "")
        ret_ok = "2025/10/01" in (shown.get("end") or "")

        # 若顯示未正確，再各重試一次以日曆點選
        if not dep_ok:
            log("去程顯示不正確，重試一次日曆點選")
            set_date_via_ui(page, which="start", value=dep_value)
        if not ret_ok:
            log("回程顯示不正確，重試一次日曆點選")
            set_date_via_ui(page, which="end", value=ret_value)

        # 再讀一次
        page.wait_for_timeout(300)
        shown = read_display_values(page)
        log(f"二次驗證 → 去程: {shown.get('start')!r}；回程: {shown.get('end')!r}")

        # 收尾
        page.wait_for_timeout(12000)
        browser.close()
        log("流程結束")
