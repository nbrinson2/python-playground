import requests
import time
import argparse
import gspread
import random
import logging
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class CoinGeckoAPI:
    BASE_URL = "https://api.coingecko.com/api/v3/coins"
    MARKETS_ENDPOINT = "/markets"
    LIST_ENDPOINT = "/list?include_platform=true"
    API_KEY = ""
    TOTAL_PAGES = 60

    def __init__(self, sheet_url):
        self.sheet_url = sheet_url
        self.sheet = self._connect_to_google_sheet()

    def _connect_to_google_sheet(self):
        # Set up Google Sheets API connection
        logging.info("Connecting to Google Sheets...")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            "/home/nbrinson2/workspace/python-playground/crypto-noobs-account-key.json",
            scopes=scope,
        )
        client = gspread.authorize(credentials)
        logging.info("Connected to Google Sheets successfully.")
        return client.open_by_url(self.sheet_url).sheet1

    def get_potential_coin_investments(self):
        logging.info("Fetching potential coin investments...")
        all_coins_list = self.get_coin_list()
        time.sleep(2.5)
        all_coins_market_data = []

        # Predefined platform-to-ID mapping
        platform_to_id_map = {
            "ethereum": "eth",
            "binance-smart-chain": "bsc",
            "polygon-pos": "polygon_pos",
            "avalanche": "avax",
            "moonriver": "movr",
            "cronos": "cro",
            "harmony-shard-0": "one",
            "boba": "boba",
            "fantom": "ftm",
            "aurora": "aurora",
            "arbitrum-one": "arbitrum",
            "sui": "sui-network",
        }

        for page in range(1, self.TOTAL_PAGES + 1):
            logging.info(f"Fetching data for page {page}...")
            coins = self.get_coin_list_with_market_data(page)
            if coins:
                all_coins_market_data.extend(coins)
            time.sleep(2.5)

        logging.info("Processing and filtering coin data...")
        potential_investments = []
        for coin in all_coins_market_data:
            classification = self.is_potential_coin_investment(coin)
            if classification:
                # Find the associated coin in the all_coins_list
                associated_coin = next(
                    (item for item in all_coins_list if item["id"] == coin["id"]), None
                )

                # Extract contract number and determine the associated platform
                contract_number = ""
                platform = ""
                if associated_coin and "platforms" in associated_coin:
                    platforms = associated_coin["platforms"]
                    if len(platforms) == 1:
                        # Only one platform available
                        platform, contract_number = next(iter(platforms.items()))
                    elif "ethereum" in platforms:
                        # Default to Ethereum if multiple platforms exist
                        platform = "ethereum"
                        contract_number = platforms["ethereum"]
                        # Map platform to its platform ID
                    if platform in platform_to_id_map:
                        platform = platform_to_id_map[platform]

                if not contract_number:
                    continue

                # Generate Gecko Terminal link dynamically based on the platform
                gecko_terminal_link = (
                    f"https://www.geckoterminal.com/{platform}/pools/{contract_number}"
                    if contract_number
                    else ""
                )

                potential_investments.append(
                    {
                        "id": coin["id"],
                        "name": coin["name"],
                        "link": f"https://www.coingecko.com/en/coins/{coin['id']}",
                        "image": coin["image"],
                        "classification": classification,
                        "contract_number": contract_number,
                        "gecko_terminal_link": gecko_terminal_link,
                    }
                )

        logging.info("Writing potential investments to Google Sheets...")
        self.write_to_sheet(potential_investments)
        logging.info("Finished writing to Google Sheets.")
        return potential_investments

    def get_coin_list(self):
        url = f"{self.BASE_URL}{self.LIST_ENDPOINT}"
        headers = {"accept": "application/json", "x-cg-demo-api-key": self.API_KEY}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data: {e}")

    def get_coin_list_with_market_data(self, page):
        url = f"{self.BASE_URL}{self.MARKETS_ENDPOINT}?vs_currency=usd&order=market_cap_asc&per_page=250&page={page}"
        headers = {"accept": "application/json", "x-cg-demo-api-key": self.API_KEY}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data for page {page}: {e}")
            return None

    def is_potential_coin_investment(self, coin):
        blacklisted_coin_ids = {
            "wrapped-bitcoin-universal",
            "wrapped-xrp-universal",
            "wrapped-solana-universal",
            "wrapped-ada-universal",
            "wrapped-near-universal",
            "wrapped-sei-universal",
            "l2-standard-bridged-weth-optimism",
            "arbitrum-bridged-weth-arbitrum-one",
            "l2-standard-bridged-weth-base",
        }

        # Skip evaluation for blacklisted coins
        if coin.get("id") in blacklisted_coin_ids:
            logging.info(
                f"Coin '{coin.get('id')}' is blacklisted. Skipping evaluation."
            )
            return None

        # Coin evaluation logic
        high = coin.get("high_24h") or 0
        low = coin.get("low_24h") or 0
        current = coin.get("current_price") or 0
        market_cap = coin.get("market_cap") or 0
        volume = coin.get("total_volume") or 0
        ath = coin.get("ath") or 0
        ath_diff = (ath - current) / ath if ath else 0
        ath_date = coin.get("ath_date") or ""

        is_today = False
        if ath_date:
            try:
                ath_datetime = datetime.strptime(ath_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                is_today = ath_datetime.date() == datetime.now(timezone.utc).date()
            except ValueError:
                logging.warning(f"Invalid ath_date format: {ath_date}")

        high_low_difference = high / low if low else 0
        current_high_difference = high / current if current else 0
        volume_ratio = volume / market_cap if market_cap else 0

        double_potential = (
            high_low_difference >= 2
            and current_high_difference >= 1.5
            and volume_ratio >= 1
        )
        broke_ath = is_today and ath_diff <= 0.1 and volume_ratio >= 1

        if double_potential:
            return "double_potential"
        elif broke_ath:
            return "broke_ath"
        return None

    def write_to_sheet(self, investments):
        def safe_write(func, *args, **kwargs):
            max_retries = 5
            delay = 1

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    if "Quota exceeded" in str(e):
                        logging.warning(
                            f"Quota exceeded. Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        delay *= 2 + random.uniform(0, 1)
                    else:
                        raise
            logging.error("Max retries reached. Write operation failed.")
            raise e

        # Clear existing data
        safe_write(self.sheet.clear)

        # Write the last run date and time at the top
        now = datetime.now()
        last_run_date = now.strftime("%Y-%m-%d")
        last_run_time = now.strftime("%H:%M:%S")
        safe_write(self.sheet.update, range_name="A1", values=[["Last Run:"]])
        safe_write(self.sheet.update, range_name="B1", values=[[last_run_date]])
        safe_write(self.sheet.update, range_name="C1", values=[[last_run_time]])

        # Leave a gap for better readability
        safe_write(self.sheet.append_row, [" "])

        # Write header below the gap
        safe_write(
            self.sheet.append_row,
            [
                "ID",
                "Name",
                "Classification",
                "Contract Number",
                "Gecko Terminal Link",
                "Link",
                "Image",
            ],
        )

        # Write data
        for investment in investments:
            safe_write(
                self.sheet.append_row,
                [
                    investment["id"],
                    investment["name"],
                    investment["classification"],
                    investment["contract_number"],
                    investment["gecko_terminal_link"],
                    investment["link"],
                    investment["image"],
                ],
            )


def main():
    parser = argparse.ArgumentParser(
        description="Fetch potential coin investments from CoinGecko."
    )
    parser.add_argument(
        "--sheet_url", required=True, help="URL of the Google Sheet to write data to."
    )
    args = parser.parse_args()

    logging.info("Starting script...")
    api = CoinGeckoAPI(args.sheet_url)
    api.get_potential_coin_investments()
    logging.info("Script finished successfully.")


if __name__ == "__main__":
    main()
