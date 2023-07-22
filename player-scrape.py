import requests
from bs4 import BeautifulSoup
import pandas as pd


def get_last_15_data(player_names):
    url = "https://www.fantasypros.com/mlb/stats/pitchers.php?range=15&page=ALL"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    for player_name in player_names:
        # Search for the player in the table
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if cells:
                # The player's name is in the second column
                player_cell = cells[1]
                if player_name in player_cell.text:
                    # If this is the row for the player, extract the data you're interested in
                    # 'IP' data is in the third column
                    ip_data = float(cells[2].text)
                    # 'K' data is in the fourth column
                    k_data = float(cells[3].text)
                    # 'W' data is in the fifth column
                    w_data = float(cells[4].text)
                    # 'QS' data is in the sixth column
                    qs_data = float(cells[5].text)
                    # 'ERA' data is in the eighth column
                    era_data = float(cells[7].text)
                    # 'H' data is in the eleventh column
                    h_data = float(cells[10].text)
                    # 'BB' data is in the twelfth column
                    bb_data = float(cells[11].text)
                    # 'HR' data is in the thirteenth column
                    hr_data = float(cells[12].text)
                    # 'L' data is in the sixteenth column
                    l_data = float(cells[15].text)

                    # Perform calculation
                    result = round(k_data / bb_data - era_data - h_data -
                                   hr_data + w_data - l_data + ip_data + qs_data) + 100
                    results.append(result)
                    break  # break after finding the player
        else:
            # If player was not found in the table, append ''
            results.append('')

    return results


def scrape_player_data(player_names):
    url = "https://www.fantasypros.com/mlb/probable-pitchers.php"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Get table headers
    table = soup.find('table')
    headers = [header.text for header in table.find_all('th')]
    headers[0] = 'Player'

    # Prepare data frame
    data = {header: [""]*len(player_names) for header in headers}
    data[headers[0]] = player_names  # Set player names as first column

    # Prepare player ranks list
    player_ranks = [""]*len(player_names)
    last_15 = [""]*len(player_names)  # Prepare list for 'Last 15' data

    # Loop over table rows
    for row in table.find_all('tr'):
        cells = row.find_all('td')

        # Check if cells is not empty
        if cells:
            # Get spans from other cells
            for i in range(1, len(cells)):
                player_cell_div = cells[i].find(
                    'div', {'class': 'player-cell'})
                if player_cell_div:
                    for player_name in player_names:
                        if player_name in player_cell_div.text:
                            player_index = player_names.index(player_name)

                            # Extract player rank from the span title
                            span_title = player_cell_div.find(
                                'span', {'title': True})
                            if span_title:
                                rank = span_title['title'].split(': ')[1]
                                player_ranks[player_index] = rank

                            # Extract player opponent from span
                            span_opponent = player_cell_div.find(
                                'span', {'data-woba': True})
                            data[headers[i]][player_index] = span_opponent.text

        else:
            continue

    # Call get_last_15_data() for the list of players
    last_15 = get_last_15_data(
        [name_mapping.get(player_name, player_name) for player_name in player_names])

    # Convert dictionary to data frame
    df = pd.DataFrame(data)

    # Insert 'Last 15' and player ranks as the first columns
    df.insert(0, 'Last 15', last_15)
    df.insert(0, 'Rank', player_ranks)

    return df


# List of players
full_names = ['Brayan Bello', 'Jose Berrios', 'Tanner Bibee', 'Paul Blackburn', 'Kyle Bradish', 'Taj Bradley', 'Hunter Brown', 'Griffin Canning', 'Dylan Cease', 'Aaron Civale', 'Reid Detmers', 'Bryce Elder', 'Brusdar Graterol', 'Logan Gilbert', 'Lucas Giolito', 'Hunter Greene', 'Hogan Harris', 'Merrill Kelly', 'Yusei Kikuchi', 'George Kirby', 'Michael Kopech', 'Dean Kremer',
              'Pablo Lopez', 'Bryce Miller', 'Bobby Miller', 'Joe Musgrove', 'Bailey Ober', 'Johan Oviedo', 'James Paxton', 'Freddy Peralta', 'Eury Perez', 'Cal Quantrill', 'Eduardo Rodriguez', 'Patrick Sandoval', 'JP Sears', 'Kodai Senga', 'Emmet Sheehan', 'Brady Singer', 'Blake Snell', 'Ranger Suarez', 'Julio Teheran', 'Michael Wacha', 'Taijuan Walker', 'Tyler Wells', 'Bryan Woo', 'Yu Darvish', 'Matt Manning', 'Michael Lorenzen', 'Nick Pivetta']

player_names = ['B. Bello', 'J. Berrios', 'T. Bibee', 'P. Blackburn', 'K. Bradish', 'T. Bradley', 'H. Brown', 'G. Canning', 'D. Cease', 'A. Civale', 'R. Detmers', 'B. Elder', 'B. Garrett', 'L. Gilbert', 'L. Giolito', 'H. Greene', 'H. Harris', 'M. Kelly', 'Y. Kikuchi', 'G. Kirby', 'M. Kopech', 'D. Kremer',
                'P. Lopez', 'B. Miller', 'B. Miller', 'J. Musgrove', 'B. Ober', 'J. Oviedo', 'J. Paxton', 'F. Peralta', 'E. Perez', 'C. Quantrill', 'E. Rodriguez', 'P. Sandoval', 'J. Sears', 'K. Senga', 'E. Sheehan', 'B. Singer', 'B. Snell', 'R. Suarez', 'J. Teheran', 'M. Wacha', 'T. Walker', 'T. Wells', 'B. Woo', 'Y. Darvish', 'M. Manning', 'M. Lorenzen', 'N. Pivetta']
name_mapping = dict(zip(player_names, full_names))


# Scrape data:
df = scrape_player_data(player_names)
print(df)

# Convert the DataFrame to HTML
html_table = df.to_html()

# HTML script for sortable table
sortable_table_script = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            background-color: black;
            color: white;
        }
        
        table th {
            cursor: pointer;
        }
        
        table td, table th {
            padding: 10px;
        }

        table tr:nth-child(even) {
            background-color: rgba(114,111,112,0.5);
            font-weight: 600;
        }
    </style>
</head>
<body>
    """ + html_table + """
<script>
function makeTableSortable(table) {
    // Get all the headers of the table
    var headers = table.querySelectorAll('th');
    
    // Loop through each header
    headers.forEach(function(header, index) {
        // Add a click event listener to the header
        header.addEventListener('click', function() {
            // Get the current sort direction
            var direction = header.getAttribute('data-sort') || 'asc';
            
            // Reverse the direction
            direction = (direction === 'asc') ? 'desc' : 'asc';
            
            // Get all the rows of the table
            var rows = Array.from(table.querySelectorAll('tr'));
            
            // Remove the header row
            var headerRow = rows.shift();
            
            // Sort the rows
            rows.sort(function(rowA, rowB) {
                var cellA = rowA.children[index].textContent;
                var cellB = rowB.children[index].textContent;
                
                if (!isNaN(cellA) && !isNaN(cellB)) {
                    // Parse cells as numbers
                    cellA = parseFloat(cellA);
                    cellB = parseFloat(cellB);
                }
                
                if (cellA < cellB) return direction === 'asc' ? -1 : 1;
                if (cellA > cellB) return direction === 'asc' ? 1 : -1;
                return 0;
            });
            
            // Clear the table
            while (table.firstChild) {
                table.firstChild.remove();
            }
            
            // Add the sorted rows back to the table
            table.appendChild(headerRow);
            rows.forEach(function(row) {
                table.appendChild(row);
            });
            
            // Update the sort direction
            header.setAttribute('data-sort', direction);
        });
    });
}

// Make all tables sortable when the page loads
window.addEventListener('DOMContentLoaded', function() {
    var tables = document.querySelectorAll('table');
    tables.forEach(makeTableSortable);
});
</script>
</body>
</html>
"""

# Write the HTML to a file
with open('probable-pitchers.html', 'w') as f:
    f.write(sortable_table_script)
