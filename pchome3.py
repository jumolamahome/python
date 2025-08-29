import requests, urllib.parse

q = urllib.parse.quote("iphone 15")
url = f"https://ecshweb.pchome.com.tw/search/v3.3/all/results?q={q}&page=1&sort=sale/dc"
data = requests.get(url, timeout=10).json()
for p in data.get("prods", [])[:10]:
    print(p["name"], p["price"], "https://24h.pchome.com.tw/prod/" + p["Id"])
