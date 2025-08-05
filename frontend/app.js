const API_BASE_URL = "https://g352wmgkfk.us-west-2.awsapprunner.com/api/v1";

// DOM Elements
const playerSelect = document.getElementById("player-select");
const teamSelect = document.getElementById("team-select");
const predictButton = document.getElementById("predict-button");
const resultContainer = document.getElementById("result-container");
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
        
        const games = await response.json();
        
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
                <div class="player-list">
                    ${(game.key_players || []).map(player => `
                        <div class="player-item">
                            <span class="player-name">${player.name}</span>
                            <div class="prediction-stats">
                                <span class="prediction-badge">PTS: ${player.predictions?.points?.toFixed(1) || 'N/A'}</span>
                                <span class="prediction-badge">REB: ${player.predictions?.rebounds?.toFixed(1) || 'N/A'}</span>
                                <span class="prediction-badge">AST: ${player.predictions?.assists?.toFixed(1) || 'N/A'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
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
        const [playerData, teamData] = await Promise.all([
            fetchData('/players'),
            fetchData('/teams')
        ]);

        populateDropdown(playerSelect, playerData, 'full_name', 'id');
        populateDropdown(teamSelect, teamData, 'full_name', 'id');
        
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
    defaultOption.textContent = `Select a ${nameKey.includes('player') ? 'Player' : 'Team'}...`;
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
    resultContainer.innerHTML = `<h2>Asking Porter...</h2>`

    try{
        const fullUrl = `${API_BASE_URL}/predict?player_id=${selectedPlayerId}&opponent_team_id=${selectedTeamId}`;
        console.log("Fetching URL:", fullUrl);
        const response = await fetch(fullUrl);

        if (!response.ok){
            throw new Error(`prediction api failed ${response.status}`);
        }
        const predictionData = await response.json();
        
        // Check if we have all required predictions
        if (!predictionData.predicted_points || !predictionData.predicted_rebounds || !predictionData.predicted_assists) {
            throw new Error('Missing prediction data');
        }

        // Update each stat value
        document.getElementById('predicted-points').textContent = predictionData.predicted_points.toFixed(1);
        document.getElementById('predicted-assists').textContent = predictionData.predicted_assists.toFixed(1);
        document.getElementById('predicted-rebounds').textContent = predictionData.predicted_rebounds.toFixed(1);
    }
    catch (error){
        console.error(`error during prediction`, error)
        resultContainer.innerHTML = `<h2>Error getting prediction please try again</h2>`
    }
    })
