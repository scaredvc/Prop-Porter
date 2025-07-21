import psycopg2
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        dbname = os.getenv("DB_NAME"),
        user = os.getenv("DB_USER"),
        password = os.getenv("DB_PASSWORD"),
        host = os.getenv("DB_HOST"),
        port = os.getenv("DB_PORT"),
    )
    return conn

app = Flask(__name__)

@app.route('/api/v1/teams', methods=['GET'])
def get_teams():
    team_list = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
                    SELECT id, 
                        full_name, abbreviation, nickname, city, state, year_founded 
                    FROM 
                        teams 
                    ORDER BY 
                        full_name;
                    """)
        result = cur.fetchall()

        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            team_list = [dict(zip(columns, row)) for row in result]

        cur.close()

    except Exception as e:
        print(e)
        team_list = []

    finally:
        if conn is not None:
            conn.close()

    return jsonify(team_list)

@app.route('/api/v1/players', methods= ['GET'])
def get_player():
    player_list = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
                    SELECT 
                        id, full_name, first_name, last_name, is_active
                    FROM 
                        players 
                    ORDER BY 
                        full_name
                    """)
        
        result = cur.fetchall()
        
        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            player_list = [dict(zip(columns,row))for row in result]

        cur.close()

    except Exception as e:
        print(e)
        player_list = []

    finally:
        if conn is not None:
            conn.close()
        
        return jsonify(player_list)

@app.route("/api/v1/players/<int:player_id>/stats", methods = ["GET"])
def get_player_stats(player_id):
    
    player_stats = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql_query = ( """
            SELECT 
                id, player_id, game_id, team_id, minutes, points, 
                rebounds, assists, steals, blocks, turnovers, fgm, 
                fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct
            FROM 
                player_game_stats
            WHERE 
                player_id = %s
            ORDER BY 
                game_date;
            """)
        
        cur.execute(sql_query, (player_id,))
            
        result = cur.fetchall()

        if result and cur.description:
            columns = (desc[0] for desc in cur.description)
            player_stats = [dict(zip(columns,row)) for row in result]

        cur.close()

    except Exception as e:
        print(e)
        player_stats = []

    finally: 
        if conn is not None:
            conn.close()

        return jsonify(player_stats)
    
@app.route("/api/v1/teams/<int:id>/games", methods = ["GET"])
def get_games(id):
    games = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql_query = ("""
            SELECT season_id, team_id, team_abbreviation, game_id, game_date,
                     matchup, win_loss, minutes, points, fgm, fga, fg_pct,
                     fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb, dreb, 
                     reb, ast, stl, blk, tov, pf, plus_minus
            FROM 
                games
            WHERE 
                team_id = %s
            ORDER BY 
                game_date;
            """)
        
        cur.execute(sql_query, (id,))
        result = cur.fetchall()

        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            games = [dict(zip(columns, row)) for row in result]

        cur.close()
        
    except Exception as e:
        print(e)
        games = []

    finally:
        if conn is not None:
            conn.close()

        return jsonify(games)