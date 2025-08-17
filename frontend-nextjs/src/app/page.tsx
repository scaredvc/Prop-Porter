'use client'

import { useState, useEffect } from 'react'
import CustomPrediction from '@/components/CustomPrediction'
import DailyGames from '@/components/DailyGames'

export default function Home() {
  const [mode, setMode] = useState<'custom' | 'daily'>('custom')

  return (
    <main className="container">
      {/* Mode Toggle */}
      <div className="mode-toggle">
        <button 
          className={`mode-button ${mode === 'custom' ? 'active' : ''}`}
          onClick={() => setMode('custom')}
        >
          Custom Prediction
        </button>
        <button 
          className={`mode-button ${mode === 'daily' ? 'active' : ''}`}
          onClick={() => setMode('daily')}
        >
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