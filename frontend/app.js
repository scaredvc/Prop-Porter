const API_BASE_URL = "https://g352wmgkfk.us-west-2.awsapprunner.com/api/v1";

const playerSelect = document.getElementById("player-select");
const teamSelect = document.getElementById("team-select");
const predictButton = document.getElementById("predict-button");
const resultContainer = document.getElementById("result-container");


async function fetchData(endpoint) {
    try{
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`API request failed ${response.status}`);
        }
        return await response.json();
    } catch (error){
        console.error(`error fetching ${endpoint}`);
        resultContainer.innerHTML = `<h2>Error loading data. Please check the console.</h2>`;
        return []
    }
}

function populateDropdown(selectElement, data, nameKey, valueKey) {
    if (!data || data == 0) return;

    selectElement.innterHTML = '';

    const defaultOption = document.createElement('option');
    defaultOption.textContent = `Select a ${nameKey.includes('player') ? 'Player' : 'Team'}...`;
    defaultOption.value = "";
    defaultOption.disabled = true;
    defaultOption.selected = true;
    selectElement.appendChild(defaultOption);

    data.forEach(item => {
        const option = document.createElement('option');
        option.textContent = item[nameKey];
        option.value = item[valueKey];
        selectElement.appendChild(option)
    });
}

(async function initializeApp() {
    console.log("initializing application...");
    const [playerData, teamData] = await Promise.all([
        fetchData('/players'),
        fetchData('/teams')
    ]);

    populateDropdown(playerSelect, playerData, 'full_name', 'id')
    populateDropdown(teamSelect, teamData, 'full_name', 'id')

    console.log("app initialized");

})();

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

        const predicted_points = predictionData.predicted_points;

        if (predicted_points !== undefined){
            resultContainer.innerHTML = `<h2>predicted points: <span class = "prediction-value">${predicted_points}</span></h2>`;
        } else {
            throw new Error(`Prediction data is missing`);
        }
    }
    catch (error){
        console.error(`error during prediction`, error)
        resultContainer.innerHTML = `<h2>Error getting prediction please try again</h2>`
    }
})