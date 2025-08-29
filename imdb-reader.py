# -*- coding: utf-8 -*-
"""
Playwright（同步版）擷取 IMDb Top 250（繁中介面）→ 依年份由舊到新排序 → 產生可點連結的 HTML
輸出：imdb_top250_by_year.html（內含可點擊超連結）
"""

import re
import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://www.imdb.com/chart/top/"
BASE = "https://www.imdb.com"

# ====== 可調參數 ======
HEADLESS = True              # 想看瀏覽器視窗就改 False
TARGET_COUNT = 250
MAX_SCROLLS = 50
SCROLL_PAUSE = 0.6           # 每次滾動暫停（秒）
FIRST_LOAD_TIMEOUT = 20_000  # 首批元素等待上限 (ms)
SAVE_HTML_DEBUG = False      # 若想除錯，改成 True 會把 page_source 存檔

def _to_year(val):
    if val is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(val))
    return int(m.group(0)) if m else None

def _clean(x):
    return None if x is None else str(x).strip()

def lazy_scroll_to_load_all(page):
    """滾動到底觸發懶載入，直到數量達標或不再增加。"""
    last_count = 0
    same_rounds = 0
    for i in range(1, MAX_SCROLLS + 1):
        count = page.locator("li[class*='ipc-metadata-list-summary-item']").count()
        print(f"[scroll {i}] 目前項目數：{count}", file=sys.stderr)
        if count >= TARGET_COUNT:
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)
        page.evaluate("window.scrollBy(0, -300)")
        time.sleep(SCROLL_PAUSE * 0.6)

        new_count = page.locator("li[class*='ipc-metadata-list-summary-item']").count()
        if new_count == last_count:
            same_rounds += 1
        else:
            same_rounds = 0
        last_count = new_count

        if same_rounds >= 3:
            break

def extract_rows_from_html(html):
    """將整頁 HTML 解析成資料列。"""
    soup = BeautifulSoup(html, "html.parser")
    lis = soup.select("li[class*='ipc-metadata-list-summary-item']")
    rows = []

    for li in lis:
        # 連結：<a class="ipc-title-link-wrapper" href="/title/tt0111161/?ref_=...">
        a_tag = li.select_one("a.ipc-title-link-wrapper")
        link = None
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            # IMDb 提供的是相對路徑，組成完整網址
            link = BASE + href

        # 標題+排名：<h3 class="ipc-title__text">1. 刺激1995</h3>
        h3 = li.select_one("h3.ipc-title__text") or li.find("h3")
        if not h3:
            continue
        h3_text = h3.get_text(strip=True)
        m = re.match(r"^(\d+)\.\s*(.+)$", h3_text)
        if m:
            rank = int(m.group(1))
            title = m.group(2).strip()
        else:
            rank = None
            title = h3_text.strip()

        # 年份 / 時長 / 分級
        meta_div = li.select_one("div[class*='cli-title-metadata']")
        year = runtime = cert = None
        if meta_div:
            spans = meta_div.select("span[class*='cli-title-metadata-item']")
            if len(spans) >= 1:
                year = _to_year(spans[0].get_text(" ", strip=True))
            if len(spans) >= 2:
                runtime = _clean(spans[1].get_text(" ", strip=True))
            if len(spans) >= 3:
                cert = _clean(spans[2].get_text(" ", strip=True))

        rows.append({
            "排名": rank,
            "片名": title,
            "年份": year,
            "時長": runtime,
            "分級": cert,
            "連結": link
        })

    return rows

def build_html(df: pd.DataFrame) -> str:
    """把 DataFrame 輸出成含可點連結的漂亮 HTML。"""
    # 產出可點擊的超連結欄（新分頁）
    df_html = df.copy()
    def make_anchor(url):
        if pd.isna(url) or not str(url).strip():
            return ""
        safe = str(url).strip()
        return f'<a href="{safe}" target="_blank" rel="noopener noreferrer">{safe}</a>'
    df_html["連結"] = df_html["連結"].map(make_anchor)

    # 欄位順序
    df_html = df_html[["排名", "片名", "年份", "時長", "分級", "連結"]]

    # 用 to_html 輸出（escape=False 讓 <a> 保持為連結）
    table_html = df_html.to_html(index=False, escape=False)

    # 簡單樣式
    page = f"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
  <meta charset="utf-8">
  <title>IMDb Top 250（依年份排序）</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; margin: 24px; }}
    h1 {{ font-size: 22px; margin-bottom: 12px; }}
    .desc {{ color: #555; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #f7f7f7; text-align: left; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>IMDb Top 250（依年份由舊到新）</h1>
  <div class="desc">欄位：排名、片名、年份、時長、分級、連結（可點擊，於新分頁開啟）。</div>
  {table_html}
</body>
</html>"""
    return page

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
            viewport={"width": 1400, "height": 1000},
        )
        page = context.new_page()
        print("[info] 開啟頁面中…", file=sys.stderr)

        try:
            page.goto(URL, timeout=60_000, wait_until="domcontentloaded")
            page.wait_for_selector("li[class*='ipc-metadata-list-summary-item']", timeout=FIRST_LOAD_TIMEOUT)
        except PlaywrightTimeoutError:
            print("[error] 首批清單載入逾時", file=sys.stderr)
            browser.close()
            sys.exit(1)

        lazy_scroll_to_load_all(page)

        html = page.content()
        if SAVE_HTML_DEBUG:
            with open("imdb_top250_page_source.html", "w", encoding="utf-8") as f:
                f.write(html)

        browser.close()

    # ------- 解析 / 整理 / 排序 / 產生 HTML -------
    rows = extract_rows_from_html(html)
    print(f"[info] 解析到 {len(rows)} 筆（理想 250）", file=sys.stderr)

    df = pd.DataFrame(rows)
    df = df[df["片名"].notna()].copy()

    # 依年份→排名排序；沒有年份的排最後
    sort_cols = ["年份", "排名"]
    df = df.sort_values(by=sort_cols, ascending=[True, True], na_position="last").reset_index(drop=True)

    # 避免重複排名（若有）
    df = df.drop_duplicates(subset=["排名"], keep="first").reset_index(drop=True)

    # 產生 HTML
    page_html = build_html(df)
    out_html = "imdb_top250_by_year.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"[info] 已輸出 HTML：{out_html}", file=sys.stderr)

    # 預覽前 5 筆
    print("\n=== 前 5 筆預覽（年份升冪）===")
    with pd.option_context("display.max_colwidth", 80):
        print(df.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
