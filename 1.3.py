# -*- coding: utf-8 -*-
"""
目標：
1) 進入 https://packages.eztravel.com.tw/
2) 點選熱門目的地「洛杉磯」
3) 設定出發日：2025/09/01 (一)
   設定回國日：2025/09/12 (五)

特色：
- 全程 print log，方便追蹤
- 日期欄位採「多選擇器 + 跨 iframe 掃描」策略
- 先 fill()，不行就以 JS 設值並觸發 input/change 事件
"""

import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ------------------- 基礎工具 -------------------

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------- 點選「洛杉磯」 -------------------

def click_lax_anywhere(page) -> bool:
    """嘗試用多種方式點擊『洛杉磯』選項；包含主頁、所有 iframe，以及 JS 兜底。"""
    candidates = [
        # 依你提供的結構：li > span
        lambda ctx: ctx.locator("li", has=ctx.locator("span", has_text="洛杉磯")),
        # ARIA role
        lambda ctx: ctx.get_by_role("listitem", name=re.compile(r"^\s*洛杉磯\s*$")),
        # 直接用文字（可能抓到 span）
        lambda ctx: ctx.get_by_text("洛杉磯", exact=True),
        # XPath（針對 li[span[text()='洛杉磯']]）
        lambda ctx: ctx.locator("xpath=//li[span[normalize-space()='洛杉磯']]"),
        # 再保險：先找到 span 再往上找 li
        lambda ctx: ctx.locator("span:has-text('洛杉磯')"),
    ]

    def try_click_on_ctx(ctx) -> bool:
        for build in candidates:
            try:
                loc = build(ctx).first
                loc.wait_for(state="visible", timeout=5000)

                # 若抓到的是 span，就往上找到最近的 li
                try:
                    tag = loc.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "span":
                        loc = loc.locator("xpath=ancestor::li[1]")
                except Exception:
                    pass

                loc.scroll_into_view_if_needed()
                # 先一般 click，不行就強制
                try:
                    loc.click()
                except Exception:
                    loc.click(force=True)
                return True
            except Exception:
                continue
        return False

    # 1) 先在主頁面試
    if try_click_on_ctx(page):
        return True

    # 2) 再到所有 iframe 試（有些站把卡片/推薦清單放在 iframe）
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        if try_click_on_ctx(frame):
            return True

    # 3) 最後用 JS 兜底（直接找到文字等於『洛杉磯』的 span，點它的最近 li）
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
        return bool(ok)
    except Exception:
        return False


# ------------------- 日期欄位：尋找與填寫 -------------------

def try_fill_or_js(ctx, locator, value, label) -> bool:
    """先 fill，不行再用 JS，最後驗證 input_value。"""
    try:
        locator.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        locator.click(timeout=1500)
    except Exception:
        pass

    # 方式一：fill()
    try:
        locator.fill(value, timeout=2000)
        try:
            locator.evaluate("el => el.blur && el.blur()")
        except Exception:
            pass
        got = locator.input_value(timeout=2000)
        if got == value:
            log(f"✅ {label}（{value}）以 fill() 設定成功")
            return True
    except Exception as e:
        log(f"fill 失敗（{label}）：{e.__class__.__name__}，改走 JS")

    # 方式二：JS 設值 + 事件
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


def find_candidate_inputs(ctx, which: str):
    """
    回傳一組 Locator（可能有多個），按可靠度排序。
    which: 'start' or 'end'
    """
    # 你提供的正式 id
    ids = {
        "start": "#flight-search-date-range-0-select-start",
        "end":   "#flight-search-date-range-0-select-end",
    }
    locators = []

    # (A) 精確 id
    locators.append(ctx.locator(ids[which]))

    # (B) 前綴/後綴模式（避免索引變動）
    if which == "start":
        locators.append(ctx.locator("input[id^='flight-search-date-range'][id$='select-start']"))
    else:
        locators.append(ctx.locator("input[id^='flight-search-date-range'][id$='select-end']"))

    # (C) 依「附近文字」找 input（出發/去程 vs 回國/回程）
    if which == "start":
        near_words = ["出發", "去程", "去程日期", "出發日"]
    else:
        near_words = ["回國", "回程", "回程日期", "回程日"]

    for w in near_words:
        # 用三引號 f-string，內層一律雙引號，避免字串終止問題
        locators.append(
            ctx.locator(
                f'''xpath=(//*[contains(normalize-space(.), "{w}")])[1]//following::*[self::input or self::div]//input[@placeholder="請選擇"][1]'''
            )
        )
        locators.append(
            ctx.locator(
                f'''xpath=(//*[contains(normalize-space(.), "{w}")])[1]//following::input[1]'''
            )
        )

    # (D) 退而求其次：所有 placeholder=請選擇 的 input
    locators.append(ctx.get_by_placeholder("請選擇"))

    return locators


def set_date_in_contexts(page, which: str, value: str, label: str) -> bool:
    """
    在主頁與所有 iframe 逐一嘗試找到日期欄位並填值。
    which: 'start' -> 出發日；'end' -> 回國日
    """
    contexts = [page] + [f for f in page.frames if f != page.main_frame]
    for idx, ctx in enumerate(contexts):
        ctx_name = "主頁面" if idx == 0 else f"iframe#{idx}"
        try:
            log(f"在 {ctx_name} 尋找 {label} 欄位…")
            locators = find_candidate_inputs(ctx, which)
            for j, cand in enumerate(locators, start=1):
                try:
                    # 過濾 disabled、取第一個可見 input
                    cand = cand.filter(has_not=ctx.locator("[disabled]")).first
                    cand.wait_for(state="visible", timeout=2500)
                    log(f"  匹配到候選 {j}，嘗試填寫 {label}")
                    if try_fill_or_js(ctx, cand, value, label):
                        return True
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue
        except Exception as e:
            log(f"  在 {ctx_name} 搜尋 {label} 例外：{e.__class__.__name__}")
    log(f"✖ 所有情境皆找不到或無法設定 {label}")
    return False


# ------------------- 主流程 -------------------

if __name__ == "__main__":
    with sync_playwright() as p:
        log("啟動 Playwright")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        url = "https://packages.eztravel.com.tw/"
        log(f"前往 {url}")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # 可能的 cookie/彈窗先關掉，避免遮擋
        log("嘗試關閉可能的彈窗")
        for txt in ["同意", "接受", "我知道了", "關閉", "我同意", "OK", "確定"]:
            try:
                page.get_by_role("button", name=txt).click(timeout=1500)
                log(f"已處理彈窗按鈕：{txt}")
                break
            except Exception:
                pass

        # 有些頁面要先打開「目的地」分頁/區塊才看得到清單（可忽略失敗）
        try:
            page.get_by_text("目的地", exact=False).click(timeout=1500)
            log("已嘗試打開『目的地』區塊")
        except Exception:
            pass

        page.wait_for_timeout(1000)

        # 點選「洛杉磯」
        log("嘗試點擊『洛杉磯』")
        if click_lax_anywhere(page):
            log("✅ 已點擊『洛杉磯』")
        else:
            log("⚠ 未能點擊『洛杉磯』（可能在隱藏分頁/iframe）")

        # === 設定日期 ===
        dep_value = "2025/09/01 (一)"
        ret_value = "2025/09/12 (五)"

        ok_dep = set_date_in_contexts(page, which="start", value=dep_value, label="出發日")
        ok_ret = set_date_in_contexts(page, which="end",   value=ret_value, label="回國日")

        if ok_dep and ok_ret:
            log("🎉 日期欄位皆設定完成")
        else:
            log("⚠ 還是找不到/設不進日期；可能該頁是列表頁或日期在另一個分頁/表單或 Shadow DOM 中")

        # 保留時間觀察結果
        page.wait_for_timeout(50000)
        browser.close()
        log("流程結束")
