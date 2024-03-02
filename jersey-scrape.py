import requests
from bs4 import BeautifulSoup
import pandas as pd
import random
import re
import time
import math
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

start_time = time.time()  # Record start time

# Target URL
base_url_shoprsa = 'https://www.shoprsa.com/collections/signed-baseball-jerseys'
page_size_fanaticsauthentics = 96
base_url_fanaticsauthentics_template = 'https://www.fanaticsauthentic.com/mlb-authentic/jerseys-autographed/o-5676+d-74006653+fa-01+z-812-1128347476?pageSize={}&sortOption=TopSellers'
base_url_shoplegends = 'https://shoplegends.com/collections/jerseys'
base_url_sportsintegrity = 'https://www.sportsintegrity.com/collections/signed-mlb-baseball-jerseys'
base_url_hollywoodcollectibles = 'https://hollywoodcollectibles.com/collections/autographed-jerseys'


# Format the base URL with the dynamic page size
base_url_fanaticsauthentics = base_url_fanaticsauthentics_template.format(page_size_fanaticsauthentics)

jerseys = []

def scrape_fanaticsauthentics_with_chrome(url):
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Ensures Chrome runs in headless mode
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model, REQUIRED for Docker and some Linux environments
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    chrome_options.add_argument('window-size=1920x1080')  # Optional, set window size

    # Initialize the WebDriver with the specified options
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Navigate to the URL
    driver.get(url)

    # Introduce a wait to ensure the page has loaded. Consider using WebDriverWait for more robust handling.
    driver.implicitly_wait(10)

    # Extract total number of pages from 'pageCount' (e.g., "1 of 6")
    item_count_element = driver.find_element(By.CSS_SELECTOR, ".page-count")
    print("Page count element: ", item_count_element)
    item_count_element_text = item_count_element.text  # e.g., "1 of 6"
    print("Total pages text: ", item_count_element_text)
    total_items = int(item_count_element_text.split(' ')[-1])  # Extract '6' and convert to int
    total_pages = math.ceil(total_items / page_size_fanaticsauthentics)

    current_page = 1  # Start at the first page
    while current_page <= total_pages:  # Loop to navigate through pagination

        print(f"Scraping page {current_page} of {total_pages}")

        # Selector setup (adjust these based on the actual webpage structure)
        product_selector = '.product-card'  # Example selector for product cards
        name_selector = '.product-card-title a'  # Selector for the product name within the card
        description_selector = '.product-image-container img'  # Assuming description can be derived from the image alt text
        price_selector = '.price-card .lowest .price'  # Selector for the product price

        # Find all product elements
        product_elements = driver.find_elements("css selector", product_selector)
        for product_element in product_elements:
            # Extracting the jersey name
            name = product_element.find_element("css selector", name_selector).text
            
            # Extracting the link
            link_element = product_element.find_element("css selector", name_selector)
            full_link = link_element.get_attribute('href')
            
            # Attempting to use the 'alt' attribute of the product image as the description
            description = product_element.find_element("css selector", description_selector).get_attribute('alt')
            
            # Extracting the price
            price_element = product_element.find_element("css selector", price_selector)
            price = price_element.text
            
            # Split the name and description
            name = ' '.join(name.split(' ')[:2])
            description = ' '.join(description.split(' ')[2:])

            # Using regular expressions to find the first dollar amount in the Price
            price_pattern = r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?'
            price_match = re.search(price_pattern, price)
            if price_match:
                price = price_match.group(0)


            # Append the extracted information to the jerseys list
            jerseys.append({
                'Name': name,
                'Description': description,
                'Price': price,
                'Link': full_link,
                'Website': "Fanatics Authentic"
            })
        
        # Navigate to the next page if not on the last page
        if current_page < total_pages:
            next_page_link = driver.find_element(By.CSS_SELECTOR, ".next-page a")
            next_page_link.click()
            # Wait for the next page to load
            time.sleep(5)  # Adjust sleep time based on your internet speed and page response time
        
        current_page += 1

    # It's good practice to close the browser once you're done
    driver.quit()
    

def scrape_jersey_data_shoprsa(url):
    # Initial setup for pagination (Assuming pagination logic is correct or dynamically fetched)
    start_page = 1  # Starting at the first page
    total_pages = 16  # Placeholder, adjust as needed

    for page in range(start_page, total_pages + 1):
        page_url = f'{url}?page={page}&grid_list=grid-view'
        response = requests.get(page_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            scraped_jerseys = soup.findAll('div', class_='productitem')

            for jersey in scraped_jerseys:
                # Name
                name = jersey.find('h2', class_='productitem--title').text.strip()
                # Assuming the first two words are the Name and the rest is Description
                name_parts = name.split(' ', 2)
                jersey_name = ' '.join(name_parts[:2])
                description = name_parts[2] if len(name_parts) > 2 else 'No description'

                # Price
                price_div = jersey.find('div', class_='price--main')
                price = price_div.find('span', class_='money').text.strip() if price_div else 'Price not available'

                # Link
                link = jersey.find('a', class_='productitem--image-link')['href']
                full_link = f'https://www.shoprsa.com{link}'

                # Append jersey data
                jerseys.append({
                    "Name": jersey_name,
                    "Description": description,
                    "Price": price,
                    "Link": full_link,
                    "Website": "ShopRSA"
                })
        else:
            print(f'Failed to retrieve page {page}')


def clean_price(raw_price):
    # First, try to find the sale price in the raw_price string
    sale_price_match = re.search(r'Sale price\$ (\d+)', raw_price.replace(',', ''))
    if sale_price_match:
        # If a sale price is found, use it
        price_numeric = int(sale_price_match.group(1))
    else:
        # If no sale price, try to extract any price
        price_match = re.search(r'\$\s*(\d+)', raw_price.replace(',', ''))
        if price_match:
            price_numeric = int(price_match.group(1))
        else:
            return 'Price not available'
    
    # Format the price with commas and prepend a dollar sign
    formatted_price = f"${price_numeric:,}"
    return formatted_price

def clean_price_hollywood(price_str):
    # Removing letters and splitting by '|' to handle multiple prices
    prices = re.findall(r'\d+\.\d+', price_str)
    # Converting strings to floats to compare prices
    prices = [float(price) for price in prices]
    # Finding the lowest price
    lowest_price = min(prices) if prices else None
    # Formatting the lowest price with commas and a dollar sign
    if lowest_price is not None:
        formatted_price = f"${lowest_price:,.2f}"
        return formatted_price
    else:
        return 'Price not available'

def scrape_jersey_data_shoplegends(url):
    current_page = 1
    last_page = None  # We will set this after finding the number of pages

    while True:
        if last_page and current_page > last_page:
            break  # Exit the loop if we've processed all pages
        
        print(f"Scraping page: {current_page}")
        url = f"{base_url_shoplegends}?page={current_page}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to retrieve the webpage: {url}")
            break  # Exit the loop if the page request fails
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all the jersey product cards on the current page
        jersey_elements = soup.select('.grid__item .product-card')
        for jersey in jersey_elements:

            price_raw = jersey.select_one('.product-card__price').get_text(strip=True) if jersey.select_one('.product-card__price') else 'Price not available'
            if price_raw == 'Price not available':
                continue # Skip this jersey if the price is not available
            price = clean_price(price_raw)  # Clean the raw price string to extract the price

            name = jersey.select_one('.product-card__name').get_text(strip=True) if jersey.select_one('.product-card__name') else 'No name available'
            name = ' '.join(name.split(' ')[:2])
            if 'Unsigned' in name or 'UNSIGNED' in name:
                continue

            description = jersey.select_one('.product-card__image-wrapper img')['alt'] if jersey.select_one('.product-card__image-wrapper img') else 'No description available'
            link_suffix = jersey['href'] if jersey.get('href') else ''
            full_link = f'https://shoplegends.com{link_suffix}'

            # Split the name and description
            description = ' '.join(description.split(' ')[2:])

            
            jerseys.append({
                "Name": name,
                "Description": description,
                "Price": price,
                "Link": full_link,
                "Website": "ShopLegends"  # Adjusted to the correct website name
            })
        
        # Set the last_page value if it's not already set
        if last_page is None:
            pagination_links = soup.select('.pagination .page a')
            if pagination_links:
                last_page = int(pagination_links[-1].get_text(strip=True))
            else:  # If there's no pagination, assume only one page
                last_page = 1
        
        current_page += 1  # Move to the next page


def scrape_jersey_data_sportsintegrity(url):
    page_number = 1

    while True:
        # Constructing URL for each page
        paginated_url = f'{url}?page={page_number}'
        print(f"Scraping page: {page_number}")
        
        # Fetch the page
        response = requests.get(paginated_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Finding jersey items based on the provided HTML structure
            jersey_elements = soup.find_all('div', class_='grid-item')
            
            if not jersey_elements:
                break  # Exit loop if no items found on the page
            
            for jersey_element in jersey_elements:
                name_tag = jersey_element.find('p')
                name = name_tag.text.strip() if name_tag else 'No name available'
                if name == 'No name available':
                    continue

                description = ' '.join(name.split(' ')[2:])
                name = ' '.join(name.split(' ')[:2])
                
                price_tag = jersey_element.find('small')
                price = price_tag.text.strip() if price_tag else 'Price not available'
                if price == 'Price not available':
                    continue

                link_tag = jersey_element.find('a', class_='product-grid-item')
                link = link_tag['href'] if link_tag else 'No link available'
                full_link = f'https://www.sportsintegrity.com{link}'

                jerseys.append({
                    "Name": name,
                    "Description": description,
                    "Price": price,
                    "Link": full_link,
                    "Website": "Sports Integrity"
                })
            
            # Check for "next" link to decide if we should continue
            next_page_link = soup.find('li', class_='disabled')
            if next_page_link and '→' in next_page_link.text:
                break  # If "next" is disabled, we've reached the last page
            else:
                page_number += 1
        else:
            print("Failed to retrieve the webpage")
            break

def scrape_jersey_data_hollywoodcollectibles(url):
    page_number = 1
    has_next_page = True
    filter_suffix = '?filter.p.product_type=Autographed+Baseball+Jerseys'
    while has_next_page:
        # Constructing the URL for each page, including filtering for autographed baseball jerseys
        paginated_url = f'{url}{filter_suffix}&page={page_number}'
        print(f"Scraping page: {page_number}")

        # Fetch the page
        response = requests.get(paginated_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Finding jersey items
            jersey_elements = soup.find_all('div', class_='product')
            if not jersey_elements:
                print("No more products found.")
                break  # Exit loop if no items found on the page

            for jersey_element in jersey_elements:
                name_tag = jersey_element.find('h4')
                name = name_tag.text.strip() if name_tag else 'No name available'

                description = ' '.join(name.split(' ')[2:])
                name = ' '.join(name.split(' ')[:2])

                price_tag = jersey_element.find('h6')
                raw_price = price_tag.text.strip() if price_tag else 'Price not available'
                price = clean_price_hollywood(raw_price)  # Parse and find the lowest price

                link_tag = jersey_element.find('a', class_='img-align')
                link = link_tag['href'] if link_tag else 'No link available'
                full_link = f'https://hollywoodcollectibles.com{link}'

                jerseys.append({
                    "Name": name,
                    "Description": description,
                    "Price": price,
                    "Link": full_link,
                    "Website": "Hollywood Collectibles"
                })

            # Check if there is a "Next" page link
            next_page_link = soup.find('a', class_='next')
            has_next_page = True if next_page_link else False
            page_number += 1
        else:
            print("Failed to retrieve the webpage")
            break


scrape_jersey_data_shoprsa(base_url_shoprsa)
scrape_fanaticsauthentics_with_chrome(base_url_fanaticsauthentics)
scrape_jersey_data_shoplegends(base_url_shoplegends)
scrape_jersey_data_sportsintegrity(base_url_sportsintegrity)
scrape_jersey_data_hollywoodcollectibles(base_url_hollywoodcollectibles)

# Convert the list of dictionaries to a pandas DataFrame
df_jerseys = pd.DataFrame(jerseys)
print(df_jerseys.columns)

# Convert the DataFrame to HTML, making the 'Link' column hyperlinks
df_jerseys['Link'] = df_jerseys['Link'].apply(lambda x: f'<a href="{x}">Link</a>')
df_jerseys['Description'] = df_jerseys['Description'].apply(lambda x: x.replace('Authentic', '<b>Authentic</b>'))

# Add the 'Style' column based on the 'Description' column content
df_jerseys['Style'] = df_jerseys['Description'].apply(lambda x: 'Authentic' if 'Authentic' in x else 'Custom')

html_table = df_jerseys.to_html(escape=False)

# HTML script for sortable table
sortable_table_script = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f8f9fa;
            color: #333;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }
        table, th, td {
            border: 1px solid #dee2e6;
        }
        th, td {
            text-align: left;
            padding: 8px;
        }
        th {
            background-color: #007bff;
            color: white;
            cursor: pointer;
        }
        tr:nth-child(even) {background-color: #f2f2f2;}
    </style>
</head>
<body>
    <h2>Available Jerseys</h2>
    """ + html_table + """
<script>
function makeTableSortable(table) {
    var headers = table.querySelectorAll('th');
    headers.forEach(function(header, index) {
        // Skip the first empty header
        if (index === 0) return;

        header.addEventListener('click', function() {
            // Toggle the sort direction; if it was not set, default to ascending
            var currentDirection = header.getAttribute('data-sort');
            var direction = currentDirection === 'asc' ? 'desc' : 'asc';

            var rows = Array.from(table.querySelectorAll('tbody tr')); // Ensure we're only sorting rows within tbody

            rows.sort(function(a, b) {
                var aText = a.querySelectorAll('td')[index - 1].innerText; // Adjust index for empty header
                var bText = b.querySelectorAll('td')[index - 1].innerText;

                // Attempt to convert strings to numbers for a proper numeric comparison
                var aNumber = parseFloat(aText.replace(/[\$,]/g, ''));
                var bNumber = parseFloat(bText.replace(/[\$,]/g, ''));

                if (!isNaN(aNumber) && !isNaN(bNumber)) {
                    // Both aText and bText are valid numbers
                    return (aNumber - bNumber) * (direction === 'asc' ? 1 : -1);
                } else {
                    // Fallback to string comparison
                    return aText.localeCompare(bText, undefined, {numeric: true}) * (direction === 'asc' ? 1 : -1);
                }
            });

            // Reattach sorted rows to the table
            rows.forEach(row => table.querySelector('tbody').appendChild(row));

            // Update the sort direction in the header for the next click
            header.setAttribute('data-sort', direction);

            // Update all headers' data-sort attributes to ensure consistency
            headers.forEach(h => {
                if (h !== header) h.setAttribute('data-sort', ''); // Reset other headers' sort direction
            });
        });
    });
}

// Apply the function to your table after the page content is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    var table = document.querySelector('table'); // Adjust the selector if needed
    makeTableSortable(table);
});
</script>
</body>
</html>
"""

# Write the HTML to a file
with open('jersey_data.html', 'w') as f:
    f.write(sortable_table_script)

print("HTML file with jersey data has been created.")

end_time = time.time()  # Record end time
total_time = end_time - start_time  # Calculate total execution time
print(f"Total execution time: {total_time:.2f} seconds.")  # Print total execution time

