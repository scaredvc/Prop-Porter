'use client'

import { useState, useEffect } from 'react'
import { fetchData } from '@/lib/api'

interface KeyPlayer {
  name: string
  predictions?: {
    points?: number
    rebounds?: number
    assists?: number
  }
}

interface Game {
  time?: string
  venue?: string
  home_team: string
  away_team: string
  key_players?: KeyPlayer[]
}

export default function DailyGames() {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadDailyGames()
  }, [])

  const loadDailyGames = async () => {
    try {
      setLoading(true)
      setError('')
      
      const data = await fetchData('/games/today')
      const gamesData = Array.isArray(data) ? data : (data?.games || [])
      
      if (!gamesData || gamesData.length === 0) {
        setGames([])
        return
      }
      
      setGames(gamesData)
    } catch (error) {
      console.error('Error loading daily games:', error)
      setError('Failed to load today&apos;s games. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const formatMaybe = (value: any) => {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(1) : 'N/A'
  }

  if (loading) {
    return (
      <div className="card">
        <div className="card-header">
          <h1>Today&apos;s Games</h1>
          <p>Live predictions for {formatDate(new Date())}</p>
        </div>
        <div className="card-body">
          <div className="loading">Loading today&apos;s games...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="card-header">
          <h1>Today&apos;s Games</h1>
          <p>Live predictions for {formatDate(new Date())}</p>
        </div>
        <div className="card-body">
          <div className="error-message">
            {error}
            <button onClick={loadDailyGames} className="retry-button">Retry</button>
          </div>
        </div>
      </div>
    )
  }

  if (games.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h1>Today&apos;s Games</h1>
          <p>Live predictions for {formatDate(new Date())}</p>
        </div>
        <div className="card-body">
          <div className="no-games">No games scheduled for today</div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h1>Today&apos;s Games</h1>
        <p>Live predictions for {formatDate(new Date())}</p>
      </div>
      
      <div className="card-body">
        <div className="games-grid">
          {games.map((game, index) => (
            <div key={index} className="game-card">
              <div className="game-header">
                <span>{game.time || 'TBD'}</span>
                <span>{game.venue || 'TBD'}</span>
              </div>
              <div className="game-teams">
                <div className="team">
                  <div className="team-name">{game.home_team}</div>
                </div>
                <div className="vs">VS</div>
                <div className="team">
                  <div className="team-name">{game.away_team}</div>
                </div>
              </div>
              {game.key_players && game.key_players.length > 0 && (
                <table className="stats-table" aria-label="Predicted player stats">
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>PTS</th>
                      <th>REB</th>
                      <th>AST</th>
                    </tr>
                  </thead>
                  <tbody>
                    {game.key_players.map((player, playerIndex) => (
                      <tr key={playerIndex}>
                        <td>{player.name}</td>
                        <td>{formatMaybe(player.predictions?.points)}</td>
                        <td>{formatMaybe(player.predictions?.rebounds)}</td>
                        <td>{formatMaybe(player.predictions?.assists)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
} 