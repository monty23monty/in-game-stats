const teamSelect = document.getElementById("team-select");
const gameId = document.querySelector('meta[name="game_id"]').getAttribute('content');
console.log("Game ID:", gameId);
let seasonStats = false;
const statSelects = Array.from(document.querySelectorAll('.stat-select'));

async function fetchStatOptions() {
    const url = 'http://localhost:5000/player/stats-options';
    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('Failed to fetch stat options:', response.statusText);
            return;
        }

        const data = await response.json();
        const stats = data.stats || [];
        populateStatSelects(stats);
    } catch (error) {
        console.error('Error fetching stat options:', error);
    }
}

function populateStatSelects(stats) {
    statSelects.forEach((select) => {
        select.innerHTML = '';
        const placeholderOption = document.createElement('option');
        placeholderOption.value = '';
        placeholderOption.textContent = 'Select a stat';
        select.appendChild(placeholderOption);

        stats.forEach((stat) => {
            const option = document.createElement('option');
            option.value = stat;
            option.textContent = stat;
            select.appendChild(option);
        });
    });
}

fetchStatOptions();


//teamSelect.addEventListener("change", SetPlayers())

teamSelect.addEventListener("change", function SetPlayers (event) {
    console.log(teamSelect.value);

    checkIfHomeTeam(teamSelect.value, gameId).then(r => {
    if (r) {
        if (r.is_home_team) {
            console.log("Home Team");
            getRosters(gameId, 'True').then(response => {
                if (response) {
                    console.log(response);

                    const selectElement = document.getElementById('player-select');
                    if (!selectElement) {
                        console.error('Select element not found!');
                        return;
                    }

                    // Clear existing options
                    selectElement.innerHTML = '';

                    // Sort players by number
                    response.sort((a, b) => a.number - b.number);

                    // Add players as options
                    response.forEach(player => {
                        const option = document.createElement('option');
                        option.value = player.number;
                        option.textContent = `${player.number} - ${player.name}`;
                        selectElement.appendChild(option);
                    });
                }
            });
        } else {
            getRosters(gameId, 'False').then(response => {
                if (response) {
                    console.log(response);

                    const selectElement = document.getElementById('player-select');
                    if (!selectElement) {
                        console.error('Select element not found!');
                        return;
                    }

                    // Clear existing options
                    selectElement.innerHTML = '';

                    // Sort players by number
                    response.sort((a, b) => a.number - b.number);

                    // Add players as options
                    response.forEach(player => {
                        const option = document.createElement('option');
                        option.value = player.number;
                        option.textContent = `${player.number} - ${player.name}`;
                        selectElement.appendChild(option);
                    });
                }
            });
        }
    }
});

})


async function checkIfHomeTeam(gameId, teamId) {
    const url = `http://localhost:5000/is_home_team?game_id=${gameId}&team_id=${teamId}`;

    try {
        const response = await fetch(url);

        if (!response.ok) {
            const errorData = await response.json();
            console.error("Error:", errorData.error, errorData.details || '');
            return null;
        }

        const data = await response.json();
        console.log("Response:", data);
        return data;
    } catch (error) {
        console.error("Error fetching data:", error);
        return null;
    }
}

async function getRosters(gameId, homeTeam) {
    const url = `http://localhost:5000/rosters/${gameId}/${homeTeam}`;

    try {
        const response = await fetch(url);

        if (!response.ok) {
            const errorData = await response.json();
            console.error("Error:", errorData.error, errorData.details || '');
            return null;
        }

        const data = await response.json();
        console.log("Response:", data);
        return data;
    } catch (error) {
        console.error("Error fetching data:", error);
        return null;
    }
}

const playerSelect = document.getElementById("player-select")

playerSelect.addEventListener("change", function(event){
    const selectedPlayer = playerSelect.options[playerSelect.selectedIndex];
    const nameElement = document.getElementById("name")
    nameElement.textContent = "Name: " + selectedPlayer.textContent

    console.log("Player: " + selectedPlayer);
})

const toggle = document.getElementById('toggle');

toggle.addEventListener('change', (event) => {
  if (event.target.checked) {
    console.log('Toggle is ON');
    seasonStats = false
  } else {
    console.log('Toggle is OFF');
    seasonStats = true
  }
});

const sendButton = document.getElementById("player-send-button")

sendButton.addEventListener("click", function(e){
    let playerNumber = playerSelect.options[playerSelect.selectedIndex].value;
    let teamId = teamSelect.options[teamSelect.selectedIndex].value;
    const selectedStats = statSelects
        .map((select) => select.value)
        .filter((value) => value !== '');

    const params = new URLSearchParams({
        team_id: teamId,
        player_number: playerNumber,
        game_id: gameId,
        season_stats: seasonStats
    });

    selectedStats.forEach((stat) => params.append('stats', stat));

    const url = `http://127.0.0.1:5000/output/player?${params.toString()}`

    fetch(url, {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
    }, // Convert data object to JSON string
})
    .then((response) => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json(); // Parse the JSON response
    })
    .then((data) => {
        console.log("Success:", data);
    })
    .catch((error) => {
        console.error("Error:", error);
    });
})