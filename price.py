from playwright.sync_api import sync_playwright
import requests
import urllib.parse
import pandas as pd
from fuzzywuzzy import fuzz

# Function to scrape data from momoshop search results (Synchronous version)
def scrape_momo_data_sync(keyword):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={encoded_keyword}&_isFuzzy=0&searchType=1"
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        print(f"Momo search page for '{keyword}' loaded successfully.")

        # Locate product elements
        product_elements = page.locator('li.listAreaLi').all()

        print(f"Found {len(product_elements)} potential product elements on Momo for '{keyword}'.")

        products_data = []
        for product_element in product_elements:
            link_element = product_element.locator('.goods-img-url').first

            # Get the product name from the 'title' attribute of the anchor tag
            name = link_element.get_attribute('title') if link_element.count() > 0 else 'N/A'

            # Locate the element containing the current price using the .price class and the bold tag within it
            current_price_element = product_element.locator('.price b').first
            current_price = current_price_element.text_content() if current_price_element.count() > 0 else 'N/A'

            product_url = link_element.get_attribute('href') if link_element.count() > 0 else 'N/A'

            products_data.append({
                'name': name.strip() if name else 'N/A',
                'current_price': current_price.strip() if current_price else 'N/A',
                'url': product_url
            })

        browser.close()
        return products_data

# Function to scrape data from PChome search results (using requests - Synchronous version)
def scrape_pchome_data_sync(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://ecshweb.pchome.com.tw/search/v3.3/all/results?q={encoded_keyword}"
    print(f"Fetching PChome search results for '{keyword}' from: {url}")
    try:
        resp = requests.get(url)
        resp.raise_for_status() # Raise an exception for bad status codes
        data = resp.json()
        print(f"PChome search results for '{keyword}' fetched successfully.")
        pchome_products_data = []
        if data and 'prods' in data:
            for product in data['prods']:
                name = product.get('name', 'N/A')
                price = product.get('price', 'N/A')
                product_id = product.get('Id', None)
                product_url = f"https://24h.pchome.com.tw/prod/{product_id}" if product_id else 'N/A'

                pchome_products_data.append({
                    'name': name,
                    'current_price': str(price) if price != 'N/A' else 'N/A',
                    'url': product_url
                })
        return pchome_products_data
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch PChome search results: {e}")
        return []


# Define a synchronous function to get and combine data
def get_combined_data_sync(keyword):
    # Run scraping functions (synchronously)
    momo_results = scrape_momo_data_sync(keyword)
    pchome_results = scrape_pchome_data_sync(keyword)

    # Convert results to DataFrames and add source
    momo_df = pd.DataFrame(momo_results)
    momo_df['Source'] = 'Momo'

    pchome_df = pd.DataFrame(pchome_results)
    pchome_df['Source'] = 'PChome'

    # Combine DataFrames
    combined_df = pd.concat([momo_df, pchome_df], ignore_index=True)

    # Clean and convert price to numeric for sorting
    combined_df['current_price'] = combined_df['current_price'].astype(str).str.replace(',', '', regex=False)
    combined_df['current_price'] = pd.to_numeric(combined_df['current_price'], errors='coerce')

    # Sort by price (ascending)
    sorted_df = combined_df.sort_values(by='current_price', ascending=True).reset_index(drop=True)

    # Reorder columns to have 'Source' as the first column
    cols = sorted_df.columns.tolist()
    cols.remove('Source')
    cols.insert(0, 'Source')
    sorted_df = sorted_df[cols]

    return sorted_df

# Example usage: Get and display combined and sorted data for "iphone 15"
# This part should be run in a standard Python environment like PyCharm
if __name__ == "__main__":
    combined_sorted_df_sync = get_combined_data_sync("iphone 15")

    # Display the DataFrame using print for standard Python environments
    print("\nCombined and Sorted Product Data:")
    print(combined_sorted_df_sync.to_markdown(index=False)) # Use to_markdown for better console display

    # Save the combined and sorted DataFrame to a CSV file with utf-8-sig encoding
    combined_sorted_df_sync.to_csv('combined_products_sync.csv', index=False, encoding='utf-8-sig')
    print("\n合併後的商品資訊已儲存至 combined_products_sync.csv 檔案。")

    # Convert DataFrame to HTML with clickable links and styling
    def make_clickable(url):
        return f'<a href="{url}" target="_blank">{url}</a>'

    # Add CSS styling
    html_style = """
<style>
  table {
    border-collapse: collapse;
    width: 100%;
    font-family: sans-serif;
  }
  th, td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
  }
  th {
    background-color: #f2f2f2;
  }
  tr:nth-child(even) {
    background-color: #f9f9f9;
  }
  tr:hover {
    background-color: #e9e9e9;
  }
  a {
    color: #007bff;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
</style>
"""

    html_output = combined_sorted_df_sync.to_html(escape=False, formatters=dict(url=make_clickable))

    # Combine style and html
    html_output = html_style + html_output

    # Save the HTML to a file
    with open('combined_products_sync.html', 'w', encoding='utf-8') as f:
        f.write(html_output)

    print("合併後的商品資訊已儲存至 combined_products_sync.html 檔案。")