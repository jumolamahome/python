import requests
from bs4 import BeautifulSoup

def momo_search(keyword):
    url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={keyword}&curPage=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    items = soup.select(".listArea .goodsItemLi")
    results = []
    for item in items:
        name = item.select_one(".prdName").get_text(strip=True)
        price = item.select_one(".price").get_text(strip=True)
        link = "https://www.momoshop.com.tw" + item.select_one("a")["href"]
        results.append({"name": name, "price": price, "url": link})
    return results

# 測試 MOMO
data = momo_search("iPhone 15")
for d in data[:5]:
    print(d)
