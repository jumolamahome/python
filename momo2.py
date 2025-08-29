from playwright.sync_api import sync_playwright
import pandas as pd

def scrape_sync():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.momoshop.com.tw/main/Main.jsp", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        print("Page loaded successfully.")

        # Locate product elements
        product_elements = page.locator('li[class*="prd"]').all()

        print(f"Found {len(product_elements)} potential product elements.")

        products_data = []
        for product_element in product_elements:
            # Locate the anchor tag within the product element
            link_element = product_element.locator('a').first

            # Try to get the product name from the 'title' attribute of the anchor tag
            name = link_element.get_attribute('title') if link_element.count() > 0 else None

            # If the title attribute is not available, fall back to the .prdname class
            if not name:
                name_element = product_element.locator('.prdname').first
                name = name_element.text_content() if name_element.count() > 0 else 'N/A'

            # Locate elements relative to the current product element for prices
            # Based on the provided HTML:
            # Original Price: <span class="oPrice">$<b>...</b></span>
            # Current Price: <span class="price">$<b>...</b></span>
            original_price_element = product_element.locator('.oPrice b').first
            current_price_element = product_element.locator('.price b').first

            # Extract text content for prices, handling cases where elements might not exist
            original_price = original_price_element.text_content() if original_price_element.count() > 0 else 'N/A'
            current_price = current_price_element.text_content() if current_price_element.count() > 0 else 'N/A'

            products_data.append({
                'name': name.strip() if name else 'N/A',
                'original_price': original_price.strip() if original_price else 'N/A',
                'current_price': current_price.strip() if current_price else 'N/A'
            })

        browser.close()
        return products_data

# Running the sync function and storing the result
products_data_sync = scrape_sync()

# Convert the list of product dictionaries to a pandas DataFrame
products_df_sync = pd.DataFrame(products_data_sync)

# Display the DataFrame using print for standard Python environments
print(products_df_sync)

# Save the DataFrame to a CSV file with utf-8-sig encoding
products_df_sync.to_csv('momo_products_sync.csv', index=False, encoding='utf-8-sig')

print("\n商品資訊已儲存至 momo_products_sync.csv 檔案。")