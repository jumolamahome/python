import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.ptt.cc/bbs/hotboards.html"
html_content = None

try:
    response = requests.get(url)
    response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
    html_content = response.text
    print("Successfully fetched the webpage content.")
except requests.exceptions.RequestException as e:
    print(f"Error fetching the webpage: {e}")

extracted_data = []

if html_content:
    soup = BeautifulSoup(html_content, 'html.parser')
    print("Successfully parsed the HTML content.")

    # Find all the board entries
    boards = soup.select('.b-ent a')

    for board in boards:
        title = board.select_one('.board-name').text.strip()
        link = board['href']
        nuser_element = board.select_one('.board-nuser')
        nuser = nuser_element.text.strip() if nuser_element else 'N/A'
        board_class_element = board.select_one('.board-class')
        board_class = board_class_element.text.strip() if board_class_element else 'N/A'
        board_title_element = board.select_one('.board-title')
        board_title = board_title_element.text.strip() if board_title_element else 'N/A'

        extracted_data.append({'title': title, 'link': link, 'nuser': nuser, 'class': board_class, 'board_title': board_title})

    if extracted_data:
        print("Extracted board information.")
    else:
        print("Could not find any board entries on the page.")

else:
    print("No HTML content to parse.")

if extracted_data:
    df = pd.DataFrame(extracted_data)
    df.to_csv('ptt_hotboards.csv', index=False)
    print("Successfully wrote data to ptt_hotboards.csv")
else:
    print("No data to write to file.")