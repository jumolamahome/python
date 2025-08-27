from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re

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


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://packages.eztravel.com.tw/", timeout=60000, wait_until="domcontentloaded")

    # 可能的 cookie/彈窗先關掉，避免遮擋
    for txt in ["同意", "接受", "我知道了", "關閉"]:
        try:
            page.get_by_role("button", name=txt).click(timeout=2000)
            break
        except Exception:
            pass

    # 有些頁面要先打開「目的地」分頁/區塊才看得到清單（可忽略失敗）
    try:
        page.get_by_text("目的地", exact=False).click(timeout=2000)
    except Exception:
        pass

    # 等待清單載入一下
    page.wait_for_timeout(1500)

    success = click_lax_anywhere(page)
    if not success:
        print("找不到或無法點擊『洛杉磯』，可能在隱藏分頁/滾動區塊/iframe。請確認清單是否需要先滑動或切換分頁。")

    page.wait_for_timeout(10000)  # 觀察點擊結果
    browser.close()
