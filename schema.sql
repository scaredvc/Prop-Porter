
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
    is_active BOOLEAN
);

-- id is the game id from the NBA API
CREATE TABLE games (
    id INTEGER PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_team_score INTEGER,
    away_team_score INTEGER,
    season VARCHAR(10),
    

    CONSTRAINT fk_home_team FOREIGN KEY(home_team_id) REFERENCES teams(id),
    CONSTRAINT fk_away_team FOREIGN KEY(away_team_id) REFERENCES teams(id)
);

--the performance of a single player in a single game.

CREATE TABLE player_game_stats (
    id SERIAL PRIMARY KEY, -- Using SERIAL creates an auto-incrementing integer for a unique row ID.
    player_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    minutes FLOAT,
    points INTEGER,
    rebounds INTEGER,
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
    
    CONSTRAINT fk_player FOREIGN KEY(player_id) REFERENCES players(id),
    CONSTRAINT fk_game FOREIGN KEY(game_id) REFERENCES games(id),
    CONSTRAINT fk_team FOREIGN KEY(team_id) REFERENCES teams(id),
    
    -- Add a unique constraint to prevent duplicate entries for the same player in the same game.
    UNIQUE (player_id, game_id)
);

