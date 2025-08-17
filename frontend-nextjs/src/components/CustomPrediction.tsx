'use client'

import { useState, useEffect } from 'react'
import { fetchData } from '@/lib/api'

interface Player {
  id: string
  full_name: string
  is_active?: boolean
}

interface Team {
  id: string
  full_name: string
}

interface Prediction {
  predicted_points: number
  predicted_rebounds?: number
  predicted_assists?: number
}

export default function CustomPrediction() {
  const [players, setPlayers] = useState<Player[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [selectedPlayerId, setSelectedPlayerId] = useState('')
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [predictionStatus, setPredictionStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    initializeData()
  }, [])

  const initializeData = async () => {
    try {
      setLoading(true)
      const [playersRaw, teamsRaw] = await Promise.all([
        fetchData('/players'),
        fetchData('/teams')
      ])

      // Normalize possible response shapes
      const playersAll = Array.isArray(playersRaw) ? playersRaw : (playersRaw?.players || [])
      const teamsAll = Array.isArray(teamsRaw) ? teamsRaw : (teamsRaw?.teams || [])

      // Filter only active players and sort
      const filteredPlayers = playersAll
        .filter((p: Player) => p && (p.is_active !== false))
        .sort((a: Player, b: Player) => (a.full_name || '').localeCompare(b.full_name || ''))

      // Sort teams alphabetically
      const sortedTeams = teamsAll
        .filter((t: Team) => t)
        .sort((a: Team, b: Team) => (a.full_name || '').localeCompare(b.full_name || ''))

      setPlayers(filteredPlayers)
      setTeams(sortedTeams)
    } catch (error) {
      console.error('Failed to initialize data:', error)
      setError('Failed to load players and teams. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handlePrediction = async () => {
    if (!selectedPlayerId || !selectedTeamId) return

    setPredictionStatus('Asking Porter...')
    setPrediction(null)

    try {
      const predictionData = await fetchData(`/predict?player_id=${selectedPlayerId}&opponent_team_id=${selectedTeamId}`)
      
      // Validate prediction data
      const points = Number(predictionData.predicted_points)
      if (!Number.isFinite(points)) {
        throw new Error('Missing or invalid predicted_points')
      }

      setPrediction(predictionData)
      setPredictionStatus('')
    } catch (error) {
      console.error('Error during prediction:', error)
      setPredictionStatus('Error getting prediction. Please try again.')
    }
  }

  const getSelectedPlayerName = () => {
    const player = players.find(p => p.id === selectedPlayerId)
    return player?.full_name || '—'
  }

  const getSelectedTeamName = () => {
    const team = teams.find(t => t.id === selectedTeamId)
    return team?.full_name || '—'
  }

  const formatMaybe = (value: any) => {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(1) : 'N/A'
  }

  if (loading) {
    return (
      <div className="card">
        <div className="loading">Loading players and teams...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="error-message">
          {error}
          <button onClick={initializeData} className="retry-button">Retry</button>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h1>Prop-Porter</h1>
        <p>NBA Player Stat Predictor</p>
      </div>
      
      <div className="card-body">
        <div className="selectors">
          <div className="select-group">
            <label htmlFor="player-select">Select a Player:</label>
            <select 
              id="player-select"
              value={selectedPlayerId}
              onChange={(e) => setSelectedPlayerId(e.target.value)}
            >
              <option value="" disabled>Select a Player...</option>
              {players.map(player => (
                <option key={player.id} value={player.id}>
                  {player.full_name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="select-group">
            <label htmlFor="team-select">Select an Opponent:</label>
            <select 
              id="team-select"
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
            >
              <option value="" disabled>Select a Team...</option>
              {teams.map(team => (
                <option key={team.id} value={team.id}>
                  {team.full_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        <button 
          className="predict-button"
          onClick={handlePrediction}
          disabled={!selectedPlayerId || !selectedTeamId}
        >
          Get Prediction
        </button>
      </div>

      <div className="card-footer">
        <div id="result-container">
          <div className="prediction-status">{predictionStatus}</div>
          {prediction && (
            <table className="stats-table" aria-label="Predicted stats">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Opponent</th>
                  <th>PTS</th>
                  <th>REB</th>
                  <th>AST</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{getSelectedPlayerName()}</td>
                  <td>{getSelectedTeamName()}</td>
                  <td>{formatMaybe(prediction.predicted_points)}</td>
                  <td>{formatMaybe(prediction.predicted_rebounds)}</td>
                  <td>{formatMaybe(prediction.predicted_assists)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
} 