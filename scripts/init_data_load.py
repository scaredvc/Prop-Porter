import psycopg2
import os
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import playergamelog
import time

connection = psycopg2.connect(
    dbname = "postgres",
    user = "postgres",
    password = "beattheodds",
    host = "localhost",
    port = "5432",
)

cur = connection.cursor()
print("connected to database")

def load_players_data():
    all_players = players.get_players()
    print(f'Retrieving {len(all_players)} players')

    for player in all_players:
        player_id = player["id"]
        player_full_name = player["full_name"]
        player_first_name = player["first_name"]
        player_last_name = player["last_name"]
        player_active_status = player["is_active"]

        sql_command = """
        INSERT INTO players (
            id, 
            full_name, 
            first_name, 
            last_name, 
            is_active
            ) VALUES (%s,%s,%s,%s,%s) 
            ON CONFLICT (id) DO NOTHING;
        """

        values_to_insert = (player_id, player_full_name, player_first_name, player_last_name, player_active_status)

        cur.execute(sql_command, values_to_insert)

    connection.commit()
    print("Done loading players")

if __name__ == "__main__":

    try:
        load_players_data() 

    except Exception as e:
        print(e)
        connection.rollback

    finally:
        if cur is not None:
            cur.close()
        if connection is not None:
            connection.close()
        print("Connection to database closed")