import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.ptt.cc/bbs/hotboards.html"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

extracted_data = []
for board_entry_div in soup.find_all('div', class_='b-ent'):
    board_name = board_entry_div.find('div', class_='board-name').get_text().strip() if board_entry_div.find('div', class_='board-name') else "N/A"
    board_nuser = board_entry_div.find('div', class_='board-nuser').get_text().strip() if board_entry_div.find('div', class_='board-nuser') else "N/A"
    board_class = board_entry_div.find('div', class_='board-class').get_text().strip() if board_entry_div.find('div', class_='board-class') else "N/A"
    board_title = board_entry_div.find('div', class_='board-title').get_text().strip() if board_entry_div.find('div', class_='board-title') else "N/A"
    board_link_tag = board_entry_div.find('a', class_='board')
    board_link = "https://www.ptt.cc" + board_link_tag['href'] if board_link_tag and 'href' in board_link_tag.attrs else "N/A"

    extracted_data.append({
        "看板名稱": board_name,
        "人數": board_nuser,
        "分類": board_class,
        "標題": board_title,
        "連結": board_link
    })

df = pd.DataFrame(extracted_data)
df.to_csv('ptt_hotboards.csv', index=False, encoding='utf-8-sig')

print("資料已成功提取並儲存至 ptt_hotboards.csv")