import requests
import pandas as pd

def pchome_search(keyword, page=1):
    url = f"https://ecshweb.pchome.com.tw/search/v3.3/all/results?q={keyword}&page={page}&sort=sale/dc"
    resp = requests.get(url)
    data = resp.json()
    items = data['prods']

    results = []
    for item in items:
        results.append({
            "name": item["name"],
            "price": item["price"],
            "url": f"https://24h.pchome.com.tw/prod/{item['Id']}"
        })
    return results

# 測試抓 iPhone 15
data = pchome_search("iPhone 15")
df = pd.DataFrame(data)
print(df.head())
