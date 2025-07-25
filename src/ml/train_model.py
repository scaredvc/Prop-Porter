import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

def create_training_dataframe():

    print("Connecting to the database...")
    conn = get_db_connection()

    sql_query = """
            WITH game_opponents AS (
                -- First, create a temporary helper table to find every team's opponent for each game
                SELECT
                    g1.game_id,
                    g1.team_id,
                    g2.team_id AS opponent_team_id,
                    g2.points AS opponent_points -- Also grab the opponent's points
                FROM games g1
                JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
            )
            -- Now, build the main query using the helper table
            SELECT 
                -- Player Stats (aliased for clarity)
                pgs.player_id,
                pgs.game_id,
                pgs.team_id,
                pgs.minutes AS player_minutes,
                pgs.points AS player_points,
                pgs.rebounds AS player_rebounds,
                pgs.assists AS player_assists,
                pgs.steals AS player_steals,
                pgs.blocks AS player_blocks,
                pgs.turnovers AS player_turnovers,
                
                -- Game Context
                g.game_date,
                g.matchup,
                
                -- Player's Team Stats (aliased to avoid conflict)
                g.win_loss AS team_win_loss,
                g.points AS team_points,
                
                -- Opponent Information (from our helper table)
                go.opponent_team_id,
                go.opponent_points AS points_allowed
            FROM 
                player_game_stats pgs
            -- Join player stats with their team's game stats
            JOIN 
                games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
            -- Join with our helper table to get opponent info
            JOIN
                game_opponents go ON pgs.game_id = go.game_id AND pgs.team_id = go.team_id
            WHERE
                pgs.minutes > 0 -- Only include games where the player actually played
            ORDER BY 
                pgs.player_id, g.game_date;
        """

    training_df = pd.read_sql_query(sql_query, conn)

    print(f"Successfully created DataFrame with {len(training_df)} rows.")
    print("Here are the first 5 rows:")
    print(training_df.head())

    conn.close()

    return training_df

def feature_engineering(df):


    # player points last 10
    df["player_points_last_10"] = df.groupby("player_id")["player_points"].transform(
        lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
        )
    df['player_points_last_10'] = df['player_points_last_10'].fillna(0)


    # opponent defensive strength
    team_points_allowed = df[['game_id', 'team_id', 'opponent_team_id', 'player_points']].copy()
    team_points_allowed = team_points_allowed.rename(columns={'player_points': 'opponent_points'})

    df = pd.merge(
        df,
        team_points_allowed[['game_id', 'team_id', 'opponent_points']],
        left_on=['game_id', 'opponent_team_id']
    )

    
    return df

def train_model(df):
    df = df.dropna()
    features = ['player_points_last_10']
    target = 'player_points'

    x = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    print(f"Mean Absolute Error: {mae}")

    return model

if __name__ == '__main__':
    master_df = create_training_dataframe()
    featured_df = feature_engineering(master_df)
    
    trained_model = train_model(featured_df)
    

