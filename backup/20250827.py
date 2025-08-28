from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://rdc28.cwa.gov.tw/TDB/public/warning_typhoon_list/", timeout=60000)
    page.wait_for_timeout(5000) # 等待 JS 載入
    table_html = page.inner_html("table")
    browser.close()
# 解析 HTML 表格
soup = BeautifulSoup(table_html, "html.parser")
rows = soup.find_all("tr")[1:] # 忽略表頭
data = []
for row in rows:
    cells = [td.get_text(strip=True) for td in row.find_all("td")]
    if cells and len(cells) >= 8:
        data.append(cells[1:8])
columns = ["年度", "編號", "名稱", "英文名稱", "近臺強度", "最低氣壓(hPa)", "最大風速(m/s)"]
df = pd.DataFrame(data, columns=columns)
# 儲存為 Excel
df.to_excel("歷年有發布警報颱風列表.xlsx", index=False)
print("✅ 資料已儲存為 Excel：歷年有發布警報颱風列表.xlsx")
