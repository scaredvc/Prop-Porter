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
    """
    Connects to the database, joins tables, and creates the master DataFrame
    for model training.
    """
    print("Connecting to the database...")
    conn = get_db_connection()

    sql_query = """
        -- YOUR SQL QUERY GOES HERE
        SELECT 
            pgs.*,  -- pgs.* is a shortcut for "all columns from player_game_stats"
            g.matchup
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

if __name__ == '__main__':
    master_df = create_training_dataframe()

    # In the next steps, we will add code here to do feature engineering
    # and train our Scikit-learn model using this `master_df`.

