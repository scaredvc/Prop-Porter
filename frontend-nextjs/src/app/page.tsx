'use client'

import { useState, useEffect } from 'react'
import CustomPrediction from '@/components/CustomPrediction'
import DailyGames from '@/components/DailyGames'

export default function Home() {
  const [mode, setMode] = useState<'custom' | 'daily'>('custom')

  return (
    <main className="container">
      {/* Brand Header */}
      <div className="brand-header">
        <div className="brand-logo">
          <span className="logo-icon">🏀</span>
          <span className="logo-text">Prop-Porter</span>
        </div>
        <div className="brand-tagline">
          <span className="tagline-text">Malik Beasley didn't gamble, he bet on himself</span>
          <div className="tagline-accent"></div>
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="mode-toggle">
        <button
          className={`mode-button ${mode === 'custom' ? 'active' : ''}`}
          onClick={() => setMode('custom')}
        >
          <span className="button-icon">🎯</span>
          Custom Prediction
        </button>
        <button
          className={`mode-button ${mode === 'daily' ? 'active' : ''}`}
          onClick={() => setMode('daily')}
        >
          <span className="button-icon">📅</span>
          Today&apos;s Games
        </button>
      </div>

      {/* Custom Prediction Mode */}
      {mode === 'custom' && <CustomPrediction />}

      {/* Daily Games Mode */}
      {mode === 'daily' && <DailyGames />}
    </main>
  )
} 