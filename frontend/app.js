const API_BASE_URL = "https://g352wmgkfk.us-west-2.awsapprunner.com/api/v1";

// DOM Elements
const playerSelect = document.getElementById("player-select");
const teamSelect = document.getElementById("team-select");
const predictButton = document.getElementById("predict-button");
const resultContainer = document.getElementById("result-container");
const predictionStatus = document.getElementById("prediction-status");
const predictedPlayerEl = document.getElementById("predicted-player-name");
const predictedOpponentEl = document.getElementById("predicted-opponent-name");
const predictedPtsEl = document.getElementById("predicted-points");
const predictedRebEl = document.getElementById("predicted-rebounds");
const predictedAstEl = document.getElementById("predicted-assists");
const customMode = document.getElementById("custom-mode");
const dailyMode = document.getElementById("daily-mode");
const customPrediction = document.getElementById("custom-prediction");
const dailyGames = document.getElementById("daily-games");
const todayDate = document.getElementById("today-date");
const gamesContainer = document.getElementById("games-container");

// Mode switching
customMode.addEventListener('click', () => switchMode('custom'));
dailyMode.addEventListener('click', () => switchMode('daily'));

function switchMode(mode) {
    if (mode === 'custom') {
        customMode.classList.add('active');
        dailyMode.classList.remove('active');
        customPrediction.classList.remove('hidden');
        dailyGames.classList.add('hidden');
    } else {
        customMode.classList.remove('active');
        dailyMode.classList.add('active');
        customPrediction.classList.add('hidden');
        dailyGames.classList.remove('hidden');
        loadDailyGames();
    }
}

// Format date for display
function formatDate(date) {
    return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function formatMaybe(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num.toFixed(1) : 'N/A';
}

// Load daily games
async function loadDailyGames() {
    todayDate.textContent = formatDate(new Date());
    
    try {
        // Show loading state
        gamesContainer.innerHTML = '<div class="loading">Loading today\'s games...</div>';
        
        const response = await fetch(`${API_BASE_URL}/games/today`);
        if (!response.ok) {
            throw new Error(`Failed to fetch daily games: ${response.status}`);
        }
        
        const data = await response.json();
        const games = Array.isArray(data) ? data : (data?.games || []);
        
        if (!games || games.length === 0) {
            gamesContainer.innerHTML = '<div class="no-games">No games scheduled for today</div>';
            return;
        }
        
        gamesContainer.innerHTML = games.map(game => `
            <div class="game-card">
                <div class="game-header">
                    <span>${game.time || 'TBD'}</span>
                    <span>${game.venue || 'TBD'}</span>
                </div>
                <div class="game-teams">
                    <div class="team">
                        <div class="team-name">${game.home_team}</div>
                    </div>
                    <div class="vs">VS</div>
                    <div class="team">
                        <div class="team-name">${game.away_team}</div>
                    </div>
                </div>
                <table class="stats-table" aria-label="Predicted player stats">
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>PTS</th>
                            <th>REB</th>
                            <th>AST</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${(game.key_players || []).map(player => `
                            <tr>
                                <td>${player.name}</td>
                                <td>${formatMaybe(player.predictions?.points)}</td>
                                <td>${formatMaybe(player.predictions?.rebounds)}</td>
                                <td>${formatMaybe(player.predictions?.assists)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading daily games:', error);
        gamesContainer.innerHTML = `
            <div class="error-message">
                Failed to load today's games. Please try again later.
                <button onclick="loadDailyGames()" class="retry-button">Retry</button>
            </div>
        `;
    }
}

async function fetchData(endpoint) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`API request failed ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        throw error;
    }
}

// Initialize the custom prediction view
async function initializeCustomPrediction() {
    try {
        const [playersRaw, teamsRaw] = await Promise.all([
            fetchData('/players'),
            fetchData('/teams')
        ]);

        // Normalize possible response shapes
        const playersAll = Array.isArray(playersRaw) ? playersRaw : (playersRaw?.players || []);
        const teamsAll = Array.isArray(teamsRaw) ? teamsRaw : (teamsRaw?.teams || []);

        // Filter only active players (default to true if undefined), and sort
        const players = playersAll
            .filter(p => p && (p.is_active !== false))
            .sort((a, b) => (a.full_name || '').localeCompare(b.full_name || ''));

        // Sort teams alphabetically by full name
        const teams = teamsAll
            .filter(t => t)
            .sort((a, b) => (a.full_name || '').localeCompare(b.full_name || ''));

        populateDropdown(playerSelect, players, 'full_name', 'id');
        populateDropdown(teamSelect, teams, 'full_name', 'id');
        
        console.log("Custom prediction view initialized");
    } catch (error) {
        console.error("Failed to initialize custom prediction view:", error);
        const errorMessage = `
            <div class="error-message">
                Failed to load players and teams. Please try again later.
                <button onclick="initializeCustomPrediction()" class="retry-button">Retry</button>
            </div>
        `;
        playerSelect.parentElement.innerHTML = errorMessage;
        teamSelect.parentElement.innerHTML = errorMessage;
    }
}

// Call initialization when the page loads
initializeCustomPrediction();

function populateDropdown(selectElement, data, nameKey, valueKey) {
    if (!data || data.length === 0) return;

    // Clear existing options
    selectElement.innerHTML = '';

    // Add default option
    const defaultOption = document.createElement('option');
    const isPlayerSelect = (selectElement.id || '').includes('player');
    defaultOption.textContent = `Select a ${isPlayerSelect ? 'Player' : 'Team'}...`;
    defaultOption.value = "";
    defaultOption.disabled = true;
    defaultOption.selected = true;
    selectElement.appendChild(defaultOption);

    // Add data options
    data.forEach(item => {
        const option = document.createElement('option');
        option.textContent = item[nameKey];
        option.value = item[valueKey];
        selectElement.appendChild(option);
    });
}

predictButton.addEventListener('click', async() =>{
    console.log("button is clicked");

    const selectedPlayerId = playerSelect.value;
    const selectedTeamId = teamSelect.value;

    console.log("Selected Player ID:", selectedPlayerId);
    console.log("Selected Team ID:", selectedTeamId);

    if(selectedPlayerId === "" || selectedTeamId === "") return; 
    predictionStatus.textContent = 'Asking Porter...';

    try{
        const fullUrl = `${API_BASE_URL}/predict?player_id=${selectedPlayerId}&opponent_team_id=${selectedTeamId}`;
        console.log("Fetching URL:", fullUrl);
        const response = await fetch(fullUrl);

        if (!response.ok){
            throw new Error(`prediction api failed ${response.status}`);
        }
        const predictionData = await response.json();

        // Validate and update table (points required, others optional)
        const pointsRaw = predictionData.predicted_points;
        const reboundsRaw = predictionData.predicted_rebounds;
        const assistsRaw = predictionData.predicted_assists;

        const points = Number(pointsRaw);
        const rebounds = Number(reboundsRaw);
        const assists = Number(assistsRaw);

        if (!Number.isFinite(points)) {
            throw new Error('Missing or invalid predicted_points');
        }

        // Update header cells
        const selectedPlayerName = playerSelect.options[playerSelect.selectedIndex]?.textContent || '';
        const selectedOpponentName = teamSelect.options[teamSelect.selectedIndex]?.textContent || '';
        predictedPlayerEl.textContent = selectedPlayerName;
        predictedOpponentEl.textContent = selectedOpponentName;

        // Update stat cells
        predictedPtsEl.textContent = points.toFixed(1);
        predictedRebEl.textContent = Number.isFinite(rebounds) ? rebounds.toFixed(1) : 'N/A';
        predictedAstEl.textContent = Number.isFinite(assists) ? assists.toFixed(1) : 'N/A';

        predictionStatus.textContent = '';
    }
    catch (error){
        console.error(`error during prediction`, error)
        predictionStatus.textContent = 'Error getting prediction. Please try again.';
    }
    })
