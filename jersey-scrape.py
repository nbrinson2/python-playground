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

mlb_teams = [
    "Diamondbacks",
    "Braves",
    "Orioles",
    "Red Sox",
    "White Sox",
    "Cubs",
    "Expos",
    "Reds",
    "Guardians",
    "Rockies",
    "Tigers",
    "Astros",
    "Royals",
    "Angels",
    "Dodgers",
    "Marlins",
    "Brewers",
    "Twins",
    "Yankees",
    "Mets",
    "Athletics",
    "Phillies",
    "Pirates",
    "Padres",
    "Giants",
    "Mariners",
    "Cardinals",
    "Rays",
    "Rangers",
    "Blue Jays",
    "Nationals"
]

mlb_team_cities = [
    "Arizona",
    "Atlanta", 
    "Baltimore",
    "Boston",
    "Brooklyn",
    "Chicago",
    "Cleveland",
    "Cincinnati",
    "Colorado",
    "Detroit",
    "Florida",
    "Houston",
    "Kansas City",
    "Los Angeles",
    "Miami",
    "Milwaukee",
    "Minnesota",
    "Montreal",
    "New York",
    "Oakland",
    "Philadelphia",
    "Pittsburgh",
    "San Diego",
    "San Francisco",
    "Seattle",
    "St. Louis",
    "St Louis",
    "Tampa Bay",
    "Texas",
    "Toronto",
    "Washington"
]

city_to_team = {
    "Arizona": "Diamondbacks",
    "Atlanta": "Braves", 
    "Baltimore": "Orioles",
    "Boston": "Red Sox",
    "Brooklyn": "Dodgers",
    "Chicago": ["White Sox", "Cubs"],  # Special case: two teams
    "Cleveland": "Guardians",
    "Cincinnati": "Reds",
    "Colorado": "Rockies",
    "Detroit": "Tigers",
    "Florida": "Marlins",
    "Houston": "Astros",
    "Kansas City": "Royals",
    "Los Angeles": ["Dodgers", "Angels"],  # Special case: two teams
    "Miami": "Marlins",
    "Milwaukee": "Brewers",
    "Minnesota": "Twins",
    "Montreal": "Expos",
    "New York": ["Yankees", "Mets"],  # Special case: two teams
    "Oakland": "Athletics",
    "Philadelphia": "Phillies",
    "Pittsburgh": "Pirates",
    "San Diego": "Padres",
    "San Francisco": "Giants",
    "Seattle": "Mariners",
    "St. Louis": "Cardinals",
    "St Louis": "Cardinals",
    "Tampa Bay": "Rays",
    "Texas": "Rangers",
    "Toronto": "Blue Jays",
    "Washington": "Nationals"
}

player_to_team_combined = {
    "Aaron Judge": "Yankees",
    "Alex Rodriguez": "Yankees",
    "Alfonso Soriano": "Yankees",
    "Andre Dawson": "Cubs",
    "Andrew Vaughn": "White Sox",
    "Aroldis Chapman": "Yankees",
    "Bo Jackson": "White Sox",
    "Bobby Bonilla": "Mets",
    "Bobby Richardson": "Yankees",
    "Bret Saberhagen": "Mets",
    "Carl Everett": "White Sox",
    "Carlton Fisk": "Red Sox",
    "Cecil Fielder": "Yankees",
    "Charlie Hayes": "Yankees",
    "Chris Chambliss": "Yankees",
    "Chris Taylor": "Dodgers",
    "Chuck Knoblauch": "Yankees",
    "Clayton Kershaw": "Dodgers",
    "Cleon Jones": "Mets",
    "Dave Kingman": "Mets",
    "Dave Righetti": "Yankees",
    "Dave Winfield": "Yankees",
    "Derek Jeter": "Yankees",
    "Domingo German": "Yankees",
    "Don Larsen": "Yankees",
    "Don Sutton": "Dodgers",
    "Dwight Gooden": "Mets",
    "Darryl Strawberry": "Mets",
    "Ed Kranepool": "Mets",
    "Eric Gagne": "Dodgers",
    "Fergie Jenkins": "Cubs",
    "Francisco Alvarez": "Mets",
    "Frank Thomas": "White Sox",
    "Gary Sheffield": "Yankees",
    "Geoff Blum": "White Sox",
    "Gleyber Torres": "Yankees",
    "Goose Gossage": "Yankees",
    "Gregg Jefferies": "Mets",
    "Howard Johnson": "Mets",
    "Jacob DeGrom": "Mets",
    "Jason Giambi": "Yankees",
    "Jermaine Dye": "White Sox",
    "Jerome Walton": "Cubs",
    "Joe Girardi": "Yankees",
    "Joe Torre": "Yankees",
    "John Franco": "Mets",
    "John Wetteland": "Yankees",
    "Jose Ramirez": "Guardians",
    "Juan Soto": "Yankees",
    "Keith Foulke": "White Sox",
    "Keith Hernandez": "Mets",
    "Kevin McReynolds": "Mets",
    "Lee Smith": "Cubs",
    "Lenny Dykstra": "Mets",
    "Lou Piniella": "Yankees",
    "Luis Robert": "White Sox",
    "Mariano Rivera": "Yankees",
    "Mark Grace": "Cubs",
    "Mookie Betts": "Dodgers",
    "Mike Piazza": "Mets",
    "Mike Trout": "Angels",
    "Nico Hoerner": "Cubs",
    "Oswaldo Cabrera": "Yankees",
    "Ozzie Guillen": "White Sox",
    "Pete Alonso": "Mets",
    "Rafael Palmeiro": "Cubs",
    "Reggie Jackson": "Yankees",
    "Rod Carew": "Angels",
    "Ron Darling": "Mets",
    "Ron Swoboda": "Mets",
    "Ronny Mauricio": "Mets",
    "Scott Brosius": "Yankees",
    "Shane Spencer": "Yankees",
    "Shawon Dunston": "Cubs",
    "Sid Fernandez": "Mets",
    "Starlin Castro": "Cubs",
    "Steve Garvey": "Dodgers",
    "Steve Sax": "Dodgers",
    "Tim Raines": "Yankees",
    "Tino Martinez": "Yankees",
    "Vladimir Guerrero": "Angels",
    "Wade Boggs": "Yankees",
    "Walker Buehler": "Dodgers",
    "Yasiel Puig": "Dodgers",
    "Yermin Mercedes": "White Sox",
}

mlb_divisions = [
    {
        "division": "AL East",
        "teams": ["Orioles", "Red Sox", "Yankees", "Rays", "Blue Jays"],
        "cities": ["Baltimore", "Boston", "New York", "Tampa Bay", "Toronto"]
    },
    {
        "division": "AL Central",
        "teams": ["White Sox", "Guardians", "Tigers", "Royals", "Twins"],
        "cities": ["Chicago", "Cleveland", "Detroit", "Kansas City", "Minnesota"]
    },
    {
        "division": "AL West",
        "teams": ["Astros", "Angels", "Athletics", "Mariners", "Rangers"],
        "cities": ["Houston", "Los Angeles", "Oakland", "Seattle", "Texas"]
    },
    {
        "division": "NL East",
        "teams": ["Braves", "Marlins", "Mets", "Phillies", "Nationals"],
        "cities": ["Atlanta", "Florida", "Miami", "New York", "Philadelphia", "Washington"]
    },
    {
        "division": "NL Central",
        "teams": ["Cubs", "Reds", "Brewers", "Pirates", "Cardinals"],
        "cities": ["Chicago", "Cincinnati", "Milwaukee", "Pittsburgh", "St. Louis"]
    },
    {
        "division": "NL West",
        "teams": ["Diamondbacks", "Rockies", "Dodgers", "Padres", "Giants"],
        "cities": ["Arizona", "Colorado", "Los Angeles", "San Diego", "San Francisco"]
    }
]

authentic_keywords = [
    "Authentic",
    "Nike",
    "Mitchell & Ness",
]


def generic_scrape(pagination_url_format, jersey_list_selector, jersey_processors, get_total_pages):
    jerseys = []
    page_number = 1

    # Fetch the initial page to determine the total number of pages
    initial_page_url = pagination_url_format.format(1)
    response = requests.get(initial_page_url)
    if response.status_code != 200:
        print('Failed to retrieve the initial page for pagination details.')
        return jerseys
    soup = BeautifulSoup(response.text, 'html.parser')

    # Use the provided get_total_pages function to determine the total number of pages
    total_pages = get_total_pages(soup)

    while page_number <= total_pages:
        page_url = pagination_url_format.format(page_number)
        print("URL: ", page_url)
        response = requests.get(page_url)
        if response.status_code != 200:
            print(f"Failed to retrieve page {page_number}.")
            break
        soup = BeautifulSoup(response.text, 'html.parser')
        jersey_elements = soup.select(jersey_list_selector)
        for jersey_element in jersey_elements:
            jersey_data = {}
            include_jersey = True
            for key, processor in jersey_processors.items():
                processed_value = processor(jersey_element) if callable(processor) else processor
                jersey_data[key] = processed_value
                # Specifically check the Description for 'jersey' keyword
                if key == "Description" and processed_value and ('jersey' not in processed_value.lower() or 'jr' in processed_value.lower(), 'card' in processed_value.lower() or 'photo' in processed_value.lower()):
                    include_jersey = False
                    break
            if include_jersey and jersey_data.get("Price") and jersey_data["Price"] != 'Price not available':
                jersey_data["Team"] = get_team_from_description(jersey_data["Description"])
                jersey_data["Division"] = get_division(jersey_data["Team"])
                jerseys.append(jersey_data)
        page_number += 1
    return jerseys

def get_division(team):
    for division in mlb_divisions:
        if team in division["teams"]:
            return division["division"]

def get_team_from_description(description):
    for player, team in player_to_team.items():
        if player.lower() in description.lower():
            return team
        
    for team in mlb_teams:
        if team.lower() in description.lower():
            return team

    # Check each team and city in the mapping
    for city, teams in city_to_team.items():
        if city.lower() in description.lower():
            # If the city has multiple teams, additional context is needed
            if isinstance(teams, list):
                # Attempt to determine the team based on known players
                for team in teams:
                    for player, player_team in player_to_team.items():
                        if team == player_team and player.lower() in description.lower():
                            return team
                return ', '.join(teams)  # Return a list of teams if unable to determine
            else:
                return teams
                
    return "Miscellaneous"

def scrape_shoprsa():
    base_url = 'https://www.shoprsa.com/collections/signed-baseball-jerseys'

    def get_name(jersey):
        name_tag = jersey.find('h2', class_='productitem--title')
        if name_tag:
            name = name_tag.text.strip()
            name_parts = name.split(' ', 2)
            return ' '.join(name_parts[:2])  # Assuming the first two words are the Name
        return 'No name available'

    def get_description(jersey):
        name_tag = jersey.find('h2', class_='productitem--title')
        if name_tag:
            name = name_tag.text.strip()
            name_parts = name.split(' ', 2)
            if len(name_parts) > 2:
                return name_parts[2]  # The rest is considered as Description
        return 'No description'
    
    def get_price(jersey):
        price_div = jersey.find('div', class_='price--main')
        if price_div:
            price_raw = price_div.find('span', class_='money').text.strip()
            return clean_price(price_raw)
        return 'Price not available'

    def get_link(jersey):
        link_tag = jersey.find('a', class_='productitem--image-link')
        if link_tag:
            return f"https://www.shoprsa.com{link_tag['href']}"
        return 'No link available'
        
    def get_total_pages(soup):
        pagination_container = soup.find('nav', class_='pagination--container')
        if pagination_container:
            # Find the last numeric page link, which indicates the total number of pages
            last_page_link = pagination_container.find_all('a', class_='pagination--item')[-2]
            return int(last_page_link.text.strip())
        return 1

    jersey_processors = {
        "Name": get_name,
        "Description": get_description,
        "Price": get_price,
        "Link": get_link,
        "Website": "ShopRSA"
    }

    pagination_url_format = base_url + "?page={}&grid_list=grid-view"
    return generic_scrape(pagination_url_format, 'div.productitem', jersey_processors, get_total_pages)

def scrape_shoplegends():
    base_url = 'https://shoplegends.com/collections/jerseys'

    def get_name(jersey):
        name = jersey.select_one('.product-card__name').get_text(strip=True) if jersey.select_one('.product-card__name') else 'No name available'
        name = ' '.join(name.split(' ')[:2])
        if 'Unsigned' in name or 'UNSIGNED' in name:
            return None
        return name

    def get_description(jersey):
        description = jersey.select_one('.product-card__image-wrapper img')['alt'] if jersey.select_one('.product-card__image-wrapper img') else 'No description available'
        return ' '.join(description.split(' ')[2:])
                
    def get_price(jersey):
        price_raw = jersey.select_one('.product-card__price').get_text(strip=True) if jersey.select_one('.product-card__price') else 'Price not available'
        return clean_price(price_raw)

    def get_link(jersey):
        link_suffix = jersey['href'] if jersey.get('href') else ''
        return f'https://shoplegends.com{link_suffix}'

    def get_total_pages(soup):
        pagination_links = soup.select('.pagination .page a')
        if pagination_links:
            return int(pagination_links[-1].get_text(strip=True))
        return 1

    jersey_processors = {
        "Name": get_name,
        "Description": get_description,
        "Price": get_price,
        "Link": get_link,
        "Website": "ShopLegends"
    }

    pagination_url_format = base_url + "?page={}"
    return generic_scrape(pagination_url_format, '.grid__item .product-card', jersey_processors, get_total_pages)

def scrape_sportsintegrity():
    base_url = 'https://www.sportsintegrity.com/collections/signed-mlb-baseball-jerseys'
    
    def get_name(jersey):
        name_tag = jersey.find('p')
        name = name_tag.text.strip() if name_tag else 'No name available'
        if name == 'No name available':
            return None
        return ' '.join(name.split(' ')[:2])
    
    def get_description(jersey):
        name_tag = jersey.find('p')
        name = name_tag.text.strip() if name_tag else 'No name available'
        if name == 'No name available':
            return None
        return ' '.join(name.split(' ')[2:])
    
    def get_price(jersey):
        price_div = jersey.find('div', class_='product-item--price')
        price_raw = price_div.text.strip()
        return clean_price(price_raw)
    
    def get_link(jersey):
        link_tag = jersey.find('a', class_='product-grid-item')
        link = link_tag['href'] if link_tag else 'No link available'
        return f'https://www.sportsintegrity.com{link}'
    
    def get_total_pages(soup):
        pagination_links = soup.select('.pagination-custom a')
        if pagination_links:
            return int(pagination_links[-2].get_text(strip=True))
        return 1
        
    jersey_processors = {
        "Name": get_name,
        "Description": get_description,
        "Price": get_price,
        "Link": get_link,
        "Website": "Sports Integrity"
    }
    
    pagination_url_format = base_url + "?page={}"
    return generic_scrape(pagination_url_format, '.grid-uniform .grid-item', jersey_processors, get_total_pages)

def scrape_hollywoodcollectibles():
    base_url = 'https://hollywoodcollectibles.com'
    url_filter = '/collections/mlb-all'
    sorting_suffix = '&sort_by=price-descending'

    def get_name(jersey):
        name_tag = jersey.find('h4')
        name = name_tag.text.strip() if name_tag else 'No name available'
        if name == 'No name available':
            return None
        return ' '.join(name.split(' ')[:2])
    
    def get_description(jersey):
        name_tag = jersey.find('h4')
        name = name_tag.text.strip() if name_tag else 'No name available'
        if name == 'No name available':
            return None
        return ' '.join(name.split(' ')[2:])
    
    def get_price(jersey):
        price_tag = jersey.find('h6')
        price_raw = price_tag.text.strip() if price_tag else 'Price not available'
        return clean_price(price_raw)
    
    def get_link(jersey):
        link_tag = jersey.find('a', class_='img-align')
        link = link_tag['href'] if link_tag else 'No link available'
        return f'{base_url}{link}'

    def get_total_pages(soup):
        return 200
    
    jersey_processors = {
        "Name": get_name,
        "Description": get_description,
        "Price": get_price,
        "Link": get_link,
        "Website": "Hollywood Collectibles"
    }
    
    pagination_url_format = f"{base_url}{url_filter}?page={{}}{sorting_suffix}"
    return generic_scrape(pagination_url_format, 'div.product', jersey_processors, get_total_pages)

def setup_selenium_driver():
    """
    Initializes and returns a Selenium WebDriver with common options.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('window-size=1920x1080')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_fanaticsauthentics_with_chrome():
    base_url = 'https://www.fanaticsauthentic.com/mlb-authentic/jerseys-autographed/o-5676+d-74006653+fa-01+z-812-1128347476?pageSize=96&sortOption=TopSellers'
    driver = setup_selenium_driver()

    driver.get(base_url)

    # Introduce a wait to ensure the page has loaded.
    driver.implicitly_wait(10)
    
    jerseys = []

    # Extract total number of pages from 'pageCount' (e.g., "1 of 6")
    item_count_element = driver.find_element(By.CSS_SELECTOR, ".page-count")
    print("Page count element: ", item_count_element)
    item_count_element_text = item_count_element.text
    print("Total pages text: ", item_count_element_text)
    total_items = int(item_count_element_text.split(' ')[-1])
    total_pages = math.ceil(total_items / 96)

    current_page = 1
    while current_page <= total_pages:

        print(f"Scraping page {current_page} of {total_pages}")

        product_selector = '.product-card' 
        name_selector = '.product-card-title a'
        description_selector = '.product-image-container img'  # Assuming description can be derived from the image alt text
        price_selector = '.price-card .lowest .price'

        product_elements = driver.find_elements("css selector", product_selector)
        for product_element in product_elements:
            name = product_element.find_element("css selector", name_selector).text
            
            link_element = product_element.find_element("css selector", name_selector)
            full_link = link_element.get_attribute('href')
            
            # Attempting to use the 'alt' attribute of the product image as the description
            description = product_element.find_element("css selector", description_selector).get_attribute('alt')
            team = get_team_from_description(description)
            division = get_division(team)
            
            price_element = product_element.find_element("css selector", price_selector)
            price = clean_price(price_element.text)
            
            name = ' '.join(name.split(' ')[:2])
            description = ' '.join(description.split(' ')[2:])

            jerseys.append({
                'Name': name,
                'Description': description,
                'Price': price,
                'Link': full_link,
                'Website': "Fanatics Authentic",
                'Team': team,
                'Division': division
            })
        
        if current_page < total_pages:
            next_page_link = driver.find_element(By.CSS_SELECTOR, ".next-page a")
            next_page_link.click()
            # Wait for the next page to load
            time.sleep(5)  # Adjust sleep time based on your internet speed and page response time
        
        current_page += 1

    driver.quit()
    return jerseys

def scrape_steelcitycollectibles_with_chrome():
    base_url = 'https://www.steelcitycollectibles.com/c/autographs/baseball?item_type=jersey&sport=baseball'
    
    driver = setup_selenium_driver()
    driver.get(base_url)

    # Wait for the page to load
    driver.implicitly_wait(10)
    
    jerseys = []

    # Extract total number of pages
    pagination_elements = driver.find_elements(By.CSS_SELECTOR, '.pager-container .pagination .page-item a')
    if pagination_elements:
        # The last page number is in the second last 'a' tag before the next arrow (if there's a "...", it's the last 'a' tag before the next arrow)
        total_pages = int(pagination_elements[-2].text) if pagination_elements[-1].get_attribute('rel') == 'next' else int(pagination_elements[-1].text)
        print(f"Total pages: {total_pages}")
    else:
        total_pages = 1  # Default to 1 if pagination is not found

    print("Scraping page 1 of", total_pages)
    for current_page in range(1, total_pages + 1):
        if current_page > 1:
            print("Scraping page", current_page, "of", total_pages)
            # Construct URL for each page
            page_url = f"{base_url}&page={current_page}"
            print("Navigating to", page_url)
            driver.get(page_url)
            # Wait for the page to load
            time.sleep(5)  # Adjust this sleep time based on your internet speed and server response time

        product_elements = driver.find_elements(By.CSS_SELECTOR, '.pr')
        print("Number of products found:", len(product_elements))
        for product_element in product_elements:
            name_element = product_element.find_element(By.CSS_SELECTOR, '.pr-info .pr-title a')
            name = name_element.text.strip()
            if 'basketball' in name.lower() or 'football' in name.lower() or 'hockey' in name.lower():
                continue
            price_element = product_element.find_element(By.CSS_SELECTOR, '.pr-price')
            link_element = product_element.find_element(By.CSS_SELECTOR, '.pr-image a')

            team = get_team_from_description(name)
            division = get_division(team)

            description = ' '.join(name.split(' ')[2:])
            name = ' '.join(name.split(' ')[:2])

            link = link_element.get_attribute('href')
            price_raw = price_element.text.strip()
            price = clean_price(price_raw)
            
            jerseys.append({
                "Name": name,
                "Description": description,
                "Price": price,
                "Link": link,
                "Website": "Steel City Collectibles",
                "Team": team,
                "Division": division
            })
        current_page += 1

    driver.quit()
    return jerseys

def clean_price(price_str):
    """
    Extracts and returns the lowest price from a string that might contain prices in various formats,
    prioritizing sale prices.
    """
    # Normalize the string by removing spaces around the dollar sign to simplify regex patterns
    normalized_price_str = price_str.replace(' $', '$').replace('$ ', '$')
    
    # Try to find a specifically denoted sale price first
    sale_price_match = re.search(r'Sale price\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)', normalized_price_str)
    if sale_price_match:
        # Convert found price to float, removing commas, and return it
        sale_price = float(sale_price_match.group(1).replace(',', ''))
        return f"${sale_price:,.2f}"

    # If no specific sale price, find the lowest price from all available prices
    prices = re.findall(r'\$([\d,]+(?:\.\d+)?)', normalized_price_str)
    # Convert found prices to float, removing commas
    prices = [float(price.replace(',', '')) for price in prices]

    # Return the lowest price formatted as a string with a dollar sign and two decimal places
    if prices:
        lowest_price = min(prices)
        return f"${lowest_price:,.2f}"
    else:
        # If no prices are found at all, return a message indicating the price is not available
        return "Price not available"

def scrape_jerseys():
    jerseys = []
    jerseys.extend(scrape_sportsintegrity())
    jerseys.extend(scrape_shoplegends())
    jerseys.extend(scrape_shoprsa())
    jerseys.extend(scrape_hollywoodcollectibles())
    jerseys.extend(scrape_steelcitycollectibles_with_chrome())
    jerseys.extend(scrape_fanaticsauthentics_with_chrome())
    return jerseys

jerseys = scrape_jerseys()

# Convert the list of dictionaries to a pandas DataFrame
df_jerseys = pd.DataFrame(jerseys)
print(df_jerseys.columns)

# Convert the DataFrame to HTML, making the 'Link' column hyperlinks
df_jerseys['Link'] = df_jerseys['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Link</a>')

# Add the 'Style' column based on the 'Description' column content
df_jerseys['Style'] = df_jerseys['Description'].apply(
    lambda x: 'Authentic' if any(keyword in x for keyword in authentic_keywords) else 'Custom'
)
df_jerseys['Style'] = df_jerseys['Style'].apply(
    lambda style: f"<b>{style}</b>" if style == 'Authentic' else style
)

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

