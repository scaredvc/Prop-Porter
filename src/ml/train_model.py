import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

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
        -- YOUR SQL QUERY GOES HERE
        SELECT 
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
            pgs.fgm AS player_fgm,
            pgs.fga AS player_fga,
            pgs.fg_pct AS player_fg_pct,
            pgs.fg3m AS player_fg3m,
            pgs.fg3a AS player_fg3a,
            pgs.fg3_pct AS player_fg3_pct,
            pgs.ftm AS player_ftm,
            pgs.fta AS player_fta,
            pgs.ft_pct AS player_ft_pct,
            g.season_id,
            g.team_id,
            g.team_abbreviation,
            g.game_id,
            g.game_date,
            g.matchup,
            g.win_loss,
            g.minutes AS game_minutes,
            g.points AS game_points,
            g.fgm AS game_fgm,
            g.fga AS game_fga,
            g.fg_pct AS game_fg_pct,
            g.fg3m AS game_fg3m,
            g.fg3a AS game_fg3a,
            g.fg3_pct AS game_fg3_pct,
            g.ftm AS game_ftm,
            g.fta AS game_fta,
            g.ft_pct AS game_ft_pct,
            g.oreb AS game_oreb,
            g.dreb AS game_dreb,
            g.ast AS game_ast,
            g.stl AS game_stl,
            g.blk AS game_blk,
            g.tov AS game_tov,
            g.pf AS game_pf,
            g.plus_minus AS game_plus_minus
        FROM 
            player_game_stats pgs
        JOIN 
            games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id;
    """

    training_df = pd.read_sql_query(sql_query, conn)

    print(f"Successfully created DataFrame with {len(training_df)} rows.")
    print("Here are the first 5 rows:")
    print(training_df.head())

    conn.close()

    return training_df

def feature_engineering(df):
    df["player_points_last_10"] = df.groupby("player_id")["player_points"].transform(
        lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
        )

if __name__ == '__main__':
    master_df = create_training_dataframe()


