# Python Playground
A sandbox for exploring, learning and creating with Python!


# Player Scrape

This Python script scrapes player data from FantasyPros for a given list of player names. The scraped data includes player rankings, 'Last 15' statistics, and other detailed player data.

The 'Last 15' stats are the player's performance in the last 15 days and can be used for tracking recent performance trends.

The final output is provided as an HTML file named probable-pitchers.html, providing an easy-to-read overview of the data.

## Prerequisites

The script requires the following Python packages:

```bash
pip install requests beautifulsoup4 pandas
```

## Usage

Specify the list of players you're interested in by providing their full names and short names in the full_names and player_names variables respectively.

```python
full_names = ['Brayan Bello', 'Jose Berrios', ...]
player_names = ['B. Bello', 'J. Berrios', ...]
```

Run the script. It will scrape the data from the website for each player listed, output the DataFrame in the console, and write it as an HTML file (probable-pitchers.html) in your local directory.

*****************************************************************************************************************

# Strip Quotes

## JSON to JS Converter

This Python script converts a JSON file into a JavaScript (JS) file. It's useful when you need to use the data stored in a JSON file in a JavaScript context.

The script reads a JSON file, converts its contents to a JavaScript-compatible format, and writes the result into a new JS file.

Call the json_to_js(input_filename, output_filename) function, providing the name of your input JSON file and the desired name for your output JS file.

```javascript
json_to_js('input.json', 'output.js')
```

The function json_value_to_js(value) helps in recursively converting each value of JSON file into a JavaScript compatible format. This function handles JSON objects (dict in Python), arrays (list in Python), and other basic data types (strings, numbers, booleans, and null).

*****************************************************************************************************************

# Text Manip

## Text Manipulation Script

This Python script provides users with the capability to manipulate text from a file. The current functionalities include:
* Converting text into a sentence case (capitalizing the first word of each sentence).
* Converting the entire text to lowercase.
* Converting the entire text to uppercase.

Moreover, the script ensures that:
* All letters in the text (other than the first word of a sentence and the word 'I') are in lowercase for the sentence case.
* A period is added at the end if there isn't one already when using the sentence case.

## Usage

Save the text you want to manipulate in a file named input.txt.

Run the script using the following syntax:

```python
python3 text_manip.py [sentence|lower|upper]
```

The processed text will be saved to a file named output.txt in the same directory.

The script's structure allows for easy addition of other text manipulation functionalities. Simply add a new function for the desired operation and include it in the command-line argument parsing.

*****************************************************************************************************************

If you have any questions, suggestions, or issues, feel free to open an issue or a pull request. I am always open to new ideas and improvements. I look forward to seeing how you use this script in your own projects!

Remember, the key to great programming is experimentation. Don't be afraid to use this script as a starting point and then modify it to better suit your needs. Happy coding!
