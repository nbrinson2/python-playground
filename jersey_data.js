document.addEventListener('DOMContentLoaded', function () {
    // Initialize counts for all teams and divisions
    let teamCounts = {};
    let divisionCounts = {
        "AL East": 0,
        "AL Central": 0,
        "AL West": 0,
        "NL East": 0,
        "NL Central": 0,
        "NL West": 0
    };
    let mlbTeams = [
        "Angels",
        "Astros",
        "Athletics",
        "Blue Jays",
        "Braves",
        "Brewers",
        "Cardinals",
        "Cubs",
        "Diamondbacks",
        "Dodgers",
        "Expos",
        "Giants",
        "Guardians",
        "Marlins",
        "Mets",
        "Nationals",
        "Orioles",
        "Padres",
        "Phillies",
        "Pirates",
        "Rangers",
        "Rays",
        "Reds",
        "Red Sox",
        "Rockies",
        "Royals",
        "Tigers",
        "Twins",
        "White Sox",
        "Yankees"
    ];

    // Prepopulate teamCounts with all teams set to zero
    mlbTeams.forEach(team => {
        teamCounts[team] = 0;
    });
    
    const table = document.querySelector('table'); // Adjust the selector if needed
    makeTableSortable(table);

    const summaryTable = document.getElementById('summary-table');
    const checkboxes = document.querySelectorAll('.checkbox-column input[type="checkbox"]');
    const selectAllCheckbox = document.createElement('input');
    selectAllCheckbox.type = 'checkbox';
    selectAllCheckbox.id = 'select-all-checkbox';
    const selectAllCheckboxContainer = document.querySelector('table th:nth-child(2)');
    if (selectAllCheckboxContainer) {
        selectAllCheckboxContainer.appendChild(selectAllCheckbox);
    }
    // Checkbox change event listener
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateSummary);
    });

    // Select/Deselect All functionality
    selectAllCheckbox.addEventListener('change', function () {
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
        updateSummary();
    });

    // Initial update
    updateSummary();

    function updateSummary() {
        const TEAM_COLUMN_INDEX = 7;
        const DIVISION_COLUMN_INDEX = 8;
        const PRICE_COLUMN_INDEX = 4;
        const STYLE_COLUMN_INDEX = 9;

        // Reset counts
        Object.keys(teamCounts).forEach(team => teamCounts[team] = 0);
        Object.keys(divisionCounts).forEach(division => divisionCounts[division] = 0);

        let customCount = 0;
        let authenticCount = 0;
        let selectedCount = 0;
        let totalPrice = 0;

        checkboxes.forEach((checkbox, index) => {
            if (checkbox.checked) {
                selectedCount++;
                const row = checkbox.closest('tr');
                const style = row.cells[STYLE_COLUMN_INDEX].innerText;
                if (style === 'Custom') {
                    customCount++;
                } else if (style === 'Authentic') {
                    authenticCount++;
                }
                const team = row.cells[TEAM_COLUMN_INDEX].innerText;
                const division = row.cells[DIVISION_COLUMN_INDEX].innerText;
                const priceText = row.cells[PRICE_COLUMN_INDEX].innerText;
                const price = parseFloat(priceText.replace(/[^0-9.-]+/g, ""));

                teamCounts[team] = (teamCounts[team] || 0) + 1;
                divisionCounts[division] = (divisionCounts[division] || 0) + 1;
                totalPrice += price;
            }
        });


        // Generate HTML for the team and division counts
        let teamCountsHtml = Object.entries(teamCounts).map(([team, count]) => `<tr><td>${team}</td><td>${count}</td></tr>`).join('');
        let divisionCountsHtml = Object.entries(divisionCounts).map(([division, count]) => `<tr><td>${division}</td><td>${count}</td></tr>`).join('');
        let authenticPercentage = selectedCount > 0 ? (authenticCount / selectedCount * 100).toFixed(2) + '%' : '0%';

        // Display summary
        summaryTable.innerHTML = `
            <table class="summary-content">
                <tr><th>Team</th><th>Count</th></tr>
                ${teamCountsHtml}
                <tr><th>Division</th><th>Count</th></tr>
                ${divisionCountsHtml}
                <tr><th>Total Custom</th><td>${customCount}</td></tr>
                <tr><th>Total Authentic</th><td>${authenticCount}</td></tr>
                <tr><th>Total Selected</th><td>${selectedCount}</td></tr>
                <tr><th>Total Price</th><td>$${totalPrice.toFixed(2)}</td></tr>
                <tr><th>Authentic Percentage</th><td>${authenticPercentage}</td></tr>
            </table>
        `;
    }
});


function makeTableSortable(table) {
    var headers = table.querySelectorAll('th');
    headers.forEach(function (header, index) {
        // Skip the first empty header
        if (index === 0) return;

        header.addEventListener('click', function () {
            // Toggle the sort direction; if it was not set, default to ascending
            var currentDirection = header.getAttribute('data-sort');
            var direction = currentDirection === 'asc' ? 'desc' : 'asc';

            var rows = Array.from(table.querySelectorAll('tbody tr')); // Ensure we're only sorting rows within tbody

            rows.sort(function (a, b) {
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
                    return aText.localeCompare(bText, undefined, { numeric: true }) * (direction === 'asc' ? 1 : -1);
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