'use client'

import { useEffect, useState } from 'react'

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

interface LastMatchup {
  game_date: string
  points: number | null
  minutes: number | null
  fga: number | null
}

interface Prediction {
  predicted_points: number
  last_matchup?: LastMatchup | null
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
      setError('')

      const [playersRaw, teamsRaw] = await Promise.all([
        fetchData('/players'),
        fetchData('/teams'),
      ])
      const playersAll = Array.isArray(playersRaw) ? playersRaw : (playersRaw?.players || [])
      const teamsAll = Array.isArray(teamsRaw) ? teamsRaw : (teamsRaw?.teams || [])

      const filteredPlayers = playersAll
        .filter((player: Player) => player && player.is_active !== false)
        .sort((a: Player, b: Player) => (a.full_name || '').localeCompare(b.full_name || ''))

      const sortedTeams = teamsAll
        .filter((team: Team) => team)
        .sort((a: Team, b: Team) => (a.full_name || '').localeCompare(b.full_name || ''))

      setPlayers(filteredPlayers)
      setTeams(sortedTeams)
    } catch (loadError) {
      console.error('Failed to load data:', loadError)
      setError('Failed to load players and teams. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handlePrediction = async () => {
    if (!selectedPlayerId || !selectedTeamId) {
      return
    }

    setPredictionStatus('Running model...')
    setPrediction(null)

    try {
      const predictionData = await fetchData(
        `/predict?player_id=${selectedPlayerId}&opponent_team_id=${selectedTeamId}`
      )
      const points = Number(predictionData.predicted_points)

      if (!Number.isFinite(points)) {
        throw new Error('Missing or invalid predicted_points')
      }

      setPrediction(predictionData)
      setPredictionStatus('')
    } catch (predictionError) {
      console.error('Prediction error:', predictionError)
      setPredictionStatus('Error getting prediction. Please try again.')
    }
  }

  const formatMaybe = (value: number | string | null | undefined, digits = 1) => {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(digits) : 'N/A'
  }

  const matchup = prediction?.last_matchup

  if (loading) {
    return (
      <section className="card">
        <div className="loading">Loading players and opponents...</div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="card">
        <div className="error-message">
          {error}
          <button onClick={initializeData} className="retry-button">Retry</button>
        </div>
      </section>
    )
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Estimate Expected Points</h2>
        <p>Select a player and opponent. The model returns one points estimate.</p>
      </div>

      <div className="card-body">
        <div className="selectors">
          <div className="select-group">
            <label htmlFor="player-select">Player</label>
            <select
              id="player-select"
              value={selectedPlayerId}
              onChange={(event) => setSelectedPlayerId(event.target.value)}
            >
              <option value="" disabled>Select a player</option>
              {players.map((player) => (
                <option key={player.id} value={player.id}>
                  {player.full_name}
                </option>
              ))}
            </select>
          </div>

          <div className="select-group">
            <label htmlFor="team-select">Opponent</label>
            <select
              id="team-select"
              value={selectedTeamId}
              onChange={(event) => setSelectedTeamId(event.target.value)}
            >
              <option value="" disabled>Select an opponent</option>
              {teams.map((team) => (
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
          Estimate Points
        </button>
      </div>

      <div className="card-footer">
        <div className="prediction-status">{predictionStatus}</div>
        {prediction && (
          <div className="prediction-result">
            <div className="stat-item">
              <div className="stat-label">Predicted points</div>
              <div className="stat-value">{formatMaybe(prediction.predicted_points, 2)}</div>
            </div>

            {matchup && (
              <div className="secondary-block">
                <div className="secondary-label">Last recorded game vs this opponent</div>
                <div className="secondary-grid">
                  <div>
                    <span className="secondary-key">Date</span>
                    <span className="secondary-value">{matchup.game_date}</span>
                  </div>
                  <div>
                    <span className="secondary-key">Points</span>
                    <span className="secondary-value">{formatMaybe(matchup.points)}</span>
                  </div>
                  <div>
                    <span className="secondary-key">Minutes</span>
                    <span className="secondary-value">{formatMaybe(matchup.minutes)}</span>
                  </div>
                  <div>
                    <span className="secondary-key">FGA</span>
                    <span className="secondary-value">{formatMaybe(matchup.fga)}</span>
                  </div>
                </div>
              </div>
            )}

            {!matchup && (
              <p className="prediction-note">
                No prior game against this opponent was found in the current database snapshot.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
