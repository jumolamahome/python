from playwright.sync_api import sync_playwright
import pandas as pd

def scrape_iphone_data():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.momoshop.com.tw/search/searchShop.jsp?keyword=iphone%2015&_isFuzzy=0&searchType=1", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        print("Page loaded successfully.")

        # Locate product elements. Based on the provided HTML, each product seems to be within an li with class listAreaLi
        # Let's refine the selector to be more specific if needed after testing.
        # Looking at the HTML snippet, the link to the product has class 'goods-img-url' and the title attribute seems to contain the name.
        # The price is within a div with class 'money', and the current price is within a span with class 'price' and a bold tag.
        iphone_product_elements = page.locator('li.listAreaLi').all()

        print(f"Found {len(iphone_product_elements)} potential iPhone 15 product elements.")

        products_data = []
        for product_element in iphone_product_elements:
            # Locate the anchor tag with class 'goods-img-url' within the product element
            link_element = product_element.locator('.goods-img-url').first

            # Get the product name from the 'title' attribute of the anchor tag
            name = link_element.get_attribute('title') if link_element.count() > 0 else 'N/A'

            # Locate the element containing the current price using the .price class and the bold tag within it
            current_price_element = product_element.locator('.price b').first
            current_price = current_price_element.text_content() if current_price_element.count() > 0 else 'N/A'

            products_data.append({
                'name': name.strip() if name else 'N/A',
                'current_price': current_price.strip() if current_price else 'N/A'
            })

        browser.close()
        return products_data

# Running the sync function and storing the result
products_data = scrape_iphone_data()

# Convert the list of product dictionaries to a pandas DataFrame
products_df = pd.DataFrame(products_data)

# Display the DataFrame using print for standard Python environments
print(products_df.head().to_markdown(index=False))

# Save the DataFrame to a CSV file with utf-8-sig encoding
products_df.to_csv('iphone_15_products.csv', index=False, encoding='utf-8-sig')

print("\n商品資訊已儲存至 iphone_15_products.csv 檔案。")