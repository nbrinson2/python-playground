import requests
import time
import argparse
import gspread
import random
import logging
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials
from decimal import Decimal, getcontext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Set the precision to handle 30 decimal places
getcontext().prec = 35


class CoinInvestmentChecker:
    BASE_URL = "https://api.coingecko.com/api/v3/coins"
    MARKETS_ENDPOINT = "/markets"
    LIST_ENDPOINT = "/list?include_platform=true"
    HISTORICAL_DATA_ENDPOINT = "/market_chart?vs_currency=usd&days=1"
    API_KEY = ""
    TOTAL_PAGES = 60
    HISTORY_SHEET_HEADERS = [
        "Date",
        "ID",
        "Name",
        "Classification",
        "Contract Number",
        "RSI",
        "Current Price",
        "Date Doubled",
        "Date 50 % Gain",
        "Gecko Terminal Link",
        "Link",
        "Image",
    ]

    def __init__(self, sheet_url, history_sheet_name="History"):
        self.sheet_url = sheet_url
        self.sheet = self._connect_to_google_sheet(self.sheet_url)  # Main sheet
        self.history_sheet = self._connect_to_google_sheet(self.sheet_url, history_sheet_name)  # History sheet

    def _connect_to_google_sheet(self, url, sheet_name=None):
        # Set up Google Sheets API connection
        logging.info(f"Connecting to Google Sheet: {url}...")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            "/home/nbrinson2/workspace/python-playground/crypto-noobs-account-key.json",
            scopes=scope,
        )
        client = gspread.authorize(credentials)
        logging.info(f"Connected to Google Spreadsheet: {url} successfully.")
        spreadsheet = client.open_by_url(url)
        
        # If a specific sheet name is provided, return that sheet
        if sheet_name:
            logging.info(f"Accessing sheet: {sheet_name}")
            return spreadsheet.worksheet(sheet_name)
        else:
            logging.info("Accessing default sheet (sheet1).")
            return spreadsheet.sheet1
    
    def write_existing_data_to_history_sheet(self):
        try:
            # Read the date and time from B1 and C1 of the source sheet
            sheet_date = self.sheet.acell("B1").value or "N/A"
            sheet_time = self.sheet.acell("C1").value or "N/A"
            combined_datetime = f"{sheet_date} {sheet_time}" if sheet_date != "N/A" and sheet_time != "N/A" else "N/A"

            # Fetch all rows from the sheet and filter out rows where column A is not empty
            all_data = self.sheet.get_all_values()
            data = [row for row in all_data[2:] if row and row[0].strip()]  # Skip the first 2 rows and filter non-empty column A

            # Transform data
            transformed_data = self.transform_data_for_history_sheet(data, combined_datetime)

            # Check if the history sheet is empty
            history_data = self.history_sheet.get_all_values()
            if not history_data:
                # Append headers if the sheet is empty
                logging.info("History sheet is empty. Adding headers.")
                self.history_sheet.append_row(self.HISTORY_SHEET_HEADERS)

            # Write transformed data to the history sheet
            start_row = len(history_data) + 1 if history_data else 1  # Account for headers
            for i, row in enumerate(transformed_data):
                logging.info("Writing existing data to history sheet...")
                row_index = start_row + i

                # Insert the formula in the Current Price column
                formula_cell = f"B{row_index}"  # Adjust formula to point to the correct row
                formula = f"=GECKOPRICE({formula_cell})"
                row[6] = formula  # Add placeholder formula to the row

                # Ensure RSI is a numeric value
                if row[5].isdigit():
                    row[5] = float(row[5])  # Convert RSI to a float for numeric formatting

                # Write the row data (without the formula for now)
                self.history_sheet.update(
                    [row[:6] + [""] + row[7:]], range_name=f"A{row_index}:L{row_index}"
                )

                # Update the formula separately to ensure it's not escaped
                self.history_sheet.update_acell(f"G{row_index}", formula)

            logging.info("Successfully wrote data to history sheet.")
        except Exception as e:
            logging.error(f"Error writing data to history sheet: {e}")
            raise


        
    def transform_data_for_history_sheet(self, data, combined_datetime):
        logging.info("Transforming data for history sheet...")

        transformed_data = []

        for row in data:
            # Ensure rows have expected length (adjust based on your source sheet structure)
            if len(row) < 7:
                logging.warning(f"Skipping malformed row: {row}")
                continue

            transformed_row = [
                combined_datetime,  # Date
                row[0],  # ID
                row[1],  # Name
                row[2] if len(row) > 2 else "",  # Classification
                row[3] if len(row) > 3 else "",  # Contract Number
                row[4] if len(row) > 4 else "N/A",  # RSI
                "",  # Current Price
                "",  # Date Doubled (Placeholder)
                "",  # Date 50 % Gain (Placeholder)
                row[5] if len(row) > 6 else "",  # Gecko Terminal Link
                row[6] if len(row) > 7 else "",  # Link
                row[7] if len(row) > 8 else "",  # Image
            ]
            transformed_data.append(transformed_row)

        return transformed_data

    def get_potential_coin_investments(self):
        logging.info("Fetching potential coin investments...")

        # Fetch initial data
        all_coins_list = self.get_coin_list()
        time.sleep(2.5)

        # Fetch market data
        all_coins_market_data = self._fetch_all_market_data()

        # Filter and process potential investments
        platform_to_id_map = self._get_platform_to_id_map()
        potential_investments = self._filter_potential_investments(
            all_coins_market_data, all_coins_list, platform_to_id_map
        )

        # Write results to Google Sheets
        logging.info("Writing potential investments to Google Sheets...")
        self.write_to_sheet(potential_investments)
        logging.info("Finished writing to Google Sheets.")

        return potential_investments

    def _fetch_all_market_data(self):
        """Fetch market data for all pages."""
        all_coins_market_data = []
        for page in range(1, self.TOTAL_PAGES + 1):
            logging.info(f"Fetching data for page {page}...")
            coins = self.get_coin_list_with_market_data(page)
            if coins:
                all_coins_market_data.extend(coins)
            time.sleep(2.5)
        return all_coins_market_data

    def _get_platform_to_id_map(self):
        """Return the platform-to-ID mapping."""
        return {
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
            "klay-token": "kaia",
        }

    def _filter_potential_investments(
        self, market_data, all_coins_list, platform_to_id_map
    ):
        """Filter and process potential coin investments."""
        potential_investments = []
        for coin in market_data:
            classification = self.is_potential_coin_investment(coin)
            if not classification:
                continue

            associated_coin = next(
                (item for item in all_coins_list if item["id"] == coin["id"]), None
            )
            if not associated_coin:
                continue

            contract_number, platform = self._extract_platform_and_contract(
                associated_coin, platform_to_id_map
            )
            if not contract_number:
                continue

            gecko_terminal_link = (
                f"https://www.geckoterminal.com/{platform}/pools/{contract_number}"
            )
            rsi = self.get_coin_rsi(coin["id"]) or "N/A"

            potential_investments.append(
                {
                    "id": coin["id"],
                    "name": coin["name"],
                    "link": f"https://www.coingecko.com/en/coins/{coin['id']}",
                    "image": coin["image"],
                    "classification": classification,
                    "contract_number": contract_number,
                    "gecko_terminal_link": gecko_terminal_link,
                    "rsi": rsi,
                }
            )
        return potential_investments

    def _extract_platform_and_contract(self, associated_coin, platform_to_id_map):
        """Extract contract number and determine associated platform."""
        contract_number = ""
        platform = ""
        platforms = associated_coin.get("platforms", {})
        if len(platforms) == 1:
            platform, contract_number = next(iter(platforms.items()))
        elif "ethereum" in platforms:
            platform = "ethereum"
            contract_number = platforms["ethereum"]

        if platform in platform_to_id_map:
            platform = platform_to_id_map[platform]

        return contract_number, platform

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

    def calculate_rsi(self, closing_prices):
        if len(closing_prices) < 14:
            raise ValueError(
                "At least 14 closing prices are required to calculate RSI."
            )

        # Convert closing prices to Decimal for precision
        closing_prices = [Decimal(price) for price in closing_prices]

        # Step 1: Calculate gains and losses
        gains = [
            max(closing_prices[i] - closing_prices[i - 1], Decimal(0))
            for i in range(1, len(closing_prices))
        ]
        losses = [
            max(closing_prices[i - 1] - closing_prices[i], Decimal(0))
            for i in range(1, len(closing_prices))
        ]

        # Step 2: Calculate the average gain and average loss for the first 14 periods
        average_gain = sum(gains[:14]) / Decimal(14)
        average_loss = sum(losses[:14]) / Decimal(14)

        # Step 3: Calculate Relative Strength (RS)
        relative_strength = (
            average_gain / average_loss if average_loss != 0 else Decimal("Infinity")
        )

        # Step 4: Calculate RSI
        rsi = Decimal(100) - (Decimal(100) / (Decimal(1) + relative_strength))

        return float(rsi)  # Convert back to float for the final output

    def get_coin_rsi(self, coin_id):
        try:
            historical_data = self.get_coin_historical_data(coin_id)

            if not historical_data or "prices" not in historical_data:
                logging.warning(
                    f"Missing or invalid historical data for coin {coin_id}"
                )
                return None

            prices = historical_data[
                "prices"
            ]  # This is the array with [timestamp, price]

            if len(prices) < 14:
                logging.warning(
                    f"Not enough data to calculate RSI for {coin_id}. At least 14 data points are required."
                )
                return None

            prices_by_hour = self.filter_prices_by_hour(prices)

            closing_prices = [
                price[1] for price in prices_by_hour
            ]  # Extract only the closing prices

            if len(closing_prices) < 14:
                logging.warning(
                    f"Not enough hourly data to calculate RSI for {coin_id}. At least 14 closing prices are required."
                )
                return None

            rsi = self.calculate_rsi(closing_prices)
            rounded_rsi = round(rsi)  # Round RSI to the nearest whole number
            return rounded_rsi

        except Exception as e:
            logging.error(
                f"Error occurred while processing RSI for coin {coin_id}: {e}"
            )
            return None

    def get_coin_historical_data(self, coin_id):
        url = f"{self.BASE_URL}/{coin_id}{self.HISTORICAL_DATA_ENDPOINT}"
        headers = {"accept": "application/json", "x-cg-demo-api-key": self.API_KEY}

        try:
            logging.info(f"Fetching historical data for coin: {coin_id}")
            response = requests.get(
                url, headers=headers, timeout=10
            )  # Added timeout for better request handling
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching historical data for coin {coin_id}: {e}")
            return None

    def filter_prices_by_hour(self, prices):
        if not prices:
            return []

        filtered_prices = []
        last_timestamp = None

        for timestamp, price in reversed(prices):  # Iterate from the end
            if last_timestamp is None or (last_timestamp - timestamp) >= 3600000:
                filtered_prices.append([timestamp, price])
                last_timestamp = timestamp

        return filtered_prices[::-1]  # Reverse to maintain chronological order

    def is_potential_coin_investment(self, coin):
        blacklisted_coin_ids = {
            "wrapped-bitcoin-universal",
            "wrapped-xrp-universal",
            "wrapped-solana-universal",
            "wrapped-ada-universal",
            "wrapped-near-universal",
            "wrapped-sei-universal",
            "wrapped-aptos-universal",
            "l2-standard-bridged-weth-optimism",
            "arbitrum-bridged-weth-arbitrum-one",
            "l2-standard-bridged-weth-base",
            "avalanche-bridged-weth-avalanche",
            "wrapped-sui-universal",
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
                "RSI",
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
                    investment["rsi"],
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
        "--sheet_url", required=True, help="URL of the Google Spreadsheet to read/write data."
    )
    parser.add_argument(
        "--history_sheet_name",
        default="History",
        help="Name of the sheet within the spreadsheet to write existing data to (default: History).",
    )
    args = parser.parse_args()

    logging.info("Starting script...")
    checker = CoinInvestmentChecker(args.sheet_url, args.history_sheet_name)

    # Step 1: Write existing data to history sheet
    checker.write_existing_data_to_history_sheet()

    # Step 2: Fetch and write new potential investments
    checker.get_potential_coin_investments()

    logging.info("Script finished successfully.")


if __name__ == "__main__":
    main()
