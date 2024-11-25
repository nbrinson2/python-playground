import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import sys
import json


def scrape_coin_data(url):
    # Initialize undetected Chrome without headless mode
    driver = uc.Chrome()

    try:
        driver.get(url)
        time.sleep(5)  # Wait for the page to load

        # Get the page source
        html_content = driver.page_source

        # Parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract the link from the parent <a> tag of the image
        image_tag = soup.find("img", class_="tw-h-4 tw-w-4")
        parent_a_tag = image_tag.find_parent("a") if image_tag else None
        parent_link = parent_a_tag["href"] if parent_a_tag else "Parent link not found"

        # Extract the contract number dynamically
        contract_span = soup.find("span", {"data-info-type": "contract"})
        contract_number = (
            contract_span["data-content"]
            if contract_span
            else "Contract number not found"
        )

        # Return results as a dictionary
        return {"Gecko Terminal Link": parent_link, "Contract Number": contract_number}

    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

    finally:
        driver.quit()


if __name__ == "__main__":
    # Check for URL argument
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    url = sys.argv[1]

    # Scrape the data and print as JSON
    result = scrape_coin_data(url)
    print(json.dumps(result))
