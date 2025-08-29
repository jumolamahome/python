# -*- coding: utf-8 -*-
"""
Playwright（同步版）擷取 IMDb Top 250（繁中介面）→ 排序 → CSV
輸出欄位：排名、片名、年份、時長、分級、連結
"""

import re
import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://www.imdb.com/chart/top/"
BASE = "https://www.imdb.com"

HEADLESS = True
TARGET_COUNT = 250
MAX_SCROLLS = 50
SCROLL_PAUSE = 0.6
FIRST_LOAD_TIMEOUT = 20_000
SAVE_HTML_DEBUG = True

def _to_year(val):
    if val is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(val))
    return int(m.group(0)) if m else None

def _clean(x):
    return None if x is None else str(x).strip()

def lazy_scroll_to_load_all(page):
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
    soup = BeautifulSoup(html, "html.parser")
    lis = soup.select("li[class*='ipc-metadata-list-summary-item']")
    rows = []
    for li in lis:
        # <a href="..."><h3>1. 片名</h3></a>
        a_tag = li.select_one("a.ipc-title-link-wrapper")
        link = None
        if a_tag and a_tag.get("href"):
            link = BASE + a_tag["href"].split("?")[0]  # 去掉 ref_= 後面參數也可
            # 如果你要完整 query string，就不要 split("?")[0]
            link = BASE + a_tag["href"]

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

    rows = extract_rows_from_html(html)
    print(f"[info] 解析到 {len(rows)} 筆（理想 250）", file=sys.stderr)

    df = pd.DataFrame(rows)
    df = df[df["片名"].notna()].copy()
    sort_cols = ["年份", "排名"]
    df = df.sort_values(by=sort_cols, ascending=[True, True], na_position="last").reset_index(drop=True)
    if "排名" in df.columns:
        df = df.drop_duplicates(subset=["排名"], keep="first").reset_index(drop=True)

    out_csv = "imdb_top250_by_year.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[info] 已輸出：{out_csv}", file=sys.stderr)

    print("\n=== 前 5 筆預覽 ===")
    with pd.option_context("display.max_colwidth", 80):
        print(df.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
