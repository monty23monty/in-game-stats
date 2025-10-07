const teamSelect = document.getElementById("team-select");
const gameId = document.querySelector('meta[name="game_id"]').getAttribute('content');
console.log("Game ID:", gameId);
let seasonStats = false;
const statSelects = Array.from(document.querySelectorAll('.stat-select'));

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

function clearStatSelects() {
    populateStatSelects([]);
}

async function fetchStatOptionsForSelection() {
    const teamId = teamSelect.value;
    const playerNumber = playerSelect.value;

    if (!teamId || !playerNumber) {
        clearStatSelects();
        return;
    }

    const params = new URLSearchParams({
        team_id: teamId,
        player_number: playerNumber,
        season_stats: seasonStats ? 'true' : 'false',
    });

    if (gameId) {
        params.append('game_id', gameId);
    }

    const url = `http://localhost:5000/player/stats-options?${params.toString()}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('Failed to fetch stat options:', response.statusText);
            clearStatSelects();
            return;
        }

        const data = await response.json();
        const stats = data.stats || [];
        populateStatSelects(stats);
    } catch (error) {
        console.error('Error fetching stat options:', error);
        clearStatSelects();
    }
}


async function SetPlayers() {
    const selectedTeamId = teamSelect.value;
    console.log(selectedTeamId);

    const teamStatus = await checkIfHomeTeam(selectedTeamId, gameId);

    if (!teamStatus) {
        return;
    }

    const roster = await getRosters(gameId, teamStatus.is_home_team ? 'True' : 'False');

    if (!roster) {
        return;
    }

    const selectElement = document.getElementById('player-select');
    if (!selectElement) {
        console.error('Select element not found!');
        return;
    }

    selectElement.innerHTML = '';

    roster.sort((a, b) => a.number - b.number);

    roster.forEach(player => {
        const option = document.createElement('option');
        option.value = player.number;
        option.textContent = `${player.number} - ${player.name}`;
        selectElement.appendChild(option);
    });

    if (selectElement.options.length > 0) {
        selectElement.selectedIndex = 0;
        selectElement.dispatchEvent(new Event('change'));
    } else {
        const nameElement = document.getElementById('name');
        if (nameElement) {
            nameElement.textContent = 'Name: ';
        }
        clearStatSelects();
    }
}

teamSelect.addEventListener('change', SetPlayers);


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

const playerSelect = document.getElementById("player-select");

playerSelect.addEventListener("change", function(event){
    const selectedPlayer = playerSelect.options[playerSelect.selectedIndex];
    const nameElement = document.getElementById("name");

    if (selectedPlayer) {
        nameElement.textContent = "Name: " + selectedPlayer.textContent;
    } else {
        nameElement.textContent = "Name: ";
    }

    fetchStatOptionsForSelection();

    console.log("Player: " + selectedPlayer);
});

const toggle = document.getElementById('toggle');

toggle.addEventListener('change', (event) => {
  if (event.target.checked) {
    console.log('Toggle is ON');
    seasonStats = false
  } else {
    console.log('Toggle is OFF');
    seasonStats = true
  }

  fetchStatOptionsForSelection();
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
        season_stats: seasonStats ? 'true' : 'false'
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
});

SetPlayers();
