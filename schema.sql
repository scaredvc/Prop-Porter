
-- id is the team id from the NBA API
CREATE TABLE teams (
    id INTEGER PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    abbreviation VARCHAR(10) NOT NULL,
    nickname VARCHAR(255),
    city VARCHAR(255),
    state VARCHAR(255),
    year_founded INTEGER
);

-- id is the player id from the NBA API
CREATE TABLE players (
    id INTEGER PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_active BOOLEAN,
    position VARCHAR(10),
    height_inches INTEGER,
    weight_lbs INTEGER,
    age INTEGER
);

-- id is the game id from the NBA API
CREATE TABLE games (
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    team_abbreviation VARCHAR(10) NOT NULL,
    game_id VARCHAR(20) NOT NULL, -- The NBA's ID for the game, e.g., "0022300001"
    game_date DATE NOT NULL,
    matchup VARCHAR(50),          -- e.g., "LAL vs. GSW"
    opponent_team_id INTEGER,
    is_home BOOLEAN,
    season_type VARCHAR(20) DEFAULT 'Regular',
    tipoff_datetime TIMESTAMPTZ,

    win_loss CHAR(1),
    minutes INTEGER,
    points INTEGER,
    fgm INTEGER,
    fga INTEGER,
    fg_pct FLOAT,
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct FLOAT,
    ftm INTEGER,
    fta INTEGER,
    ft_pct FLOAT,
    oreb INTEGER,
    dreb INTEGER,
    reb INTEGER,
    ast INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    plus_minus INTEGER,

    


    PRIMARY KEY (game_id, team_id),
    CONSTRAINT fk_team FOREIGN KEY(team_id) REFERENCES teams(id),
    CONSTRAINT fk_opp_team FOREIGN KEY(opponent_team_id) REFERENCES teams(id)
);

--the performance of a single player in a single game.

CREATE TABLE player_game_stats (
    id SERIAL PRIMARY KEY, -- Using SERIAL creates an auto-incrementing integer for a unique row ID.
    player_id INTEGER NOT NULL,
    game_id VARCHAR(20) NOT NULL,
    team_id INTEGER NOT NULL,
    
    minutes FLOAT,
    points INTEGER,
    rebounds INTEGER,
    oreb INTEGER,
    dreb INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    turnovers INTEGER,
    fgm INTEGER,
    fga INTEGER,
    fg_pct FLOAT,
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct FLOAT,
    ftm INTEGER,
    fta INTEGER,
    ft_pct FLOAT,
    starter BOOLEAN,
    
    CONSTRAINT fk_player FOREIGN KEY(player_id) REFERENCES players(id),
    CONSTRAINT fk_game FOREIGN KEY(game_id, team_id) REFERENCES games(game_id, team_id),
    
    -- Add a unique constraint to prevent duplicate entries for the same player in the same game.
    UNIQUE (player_id, game_id)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_games_team_date ON games(team_id, game_date);
CREATE INDEX IF NOT EXISTS idx_games_opp_date ON games(opponent_team_id, game_date);
CREATE INDEX IF NOT EXISTS idx_pgs_player_date ON player_game_stats(player_id, game_id);
CREATE INDEX IF NOT EXISTS idx_pgs_team_date ON player_game_stats(team_id, game_id);

-- Optional: historical game lines (timestamped to avoid leakage)
CREATE TABLE IF NOT EXISTS game_lines (
  game_id VARCHAR(20) NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL,
  source VARCHAR(50) NOT NULL,
  home_spread NUMERIC,
  total NUMERIC,
  home_ml INTEGER,
  away_ml INTEGER,
  PRIMARY KEY (game_id, retrieved_at, source)
);

-- Optional: injury reports (timestamped)
CREATE TABLE IF NOT EXISTS injury_reports (
  player_id INTEGER NOT NULL,
  report_time TIMESTAMPTZ NOT NULL,
  status VARCHAR(50),
  detail TEXT,
  source VARCHAR(50),
  PRIMARY KEY (player_id, report_time, source),
  FOREIGN KEY (player_id) REFERENCES players(id)
);

