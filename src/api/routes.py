import os
import psycopg2
import joblib
import pandas as pd
import traceback
from flask import Flask, jsonify, request
from dotenv import load_dotenv

from . import app
from .utils import get_db_connection

try: 
    model = joblib.load("player_points_predictor.pkl")
    print("Model loaded successfully")
except FileNotFoundError:
    print("Model not found")
    model = None

@app.route('/api/v1/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "API is healthy"}), 200

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
            columns = [desc[0] for desc in cur.description]
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
    

@app.route("/api/v1/predict", methods=['GET'])
def predict_player_points():
    if model is None:
        return jsonify({"error": "Model not loaded"}), 500
    
    player_id = request.args.get('player_id', type=int)
    opponent_team_id = request.args.get('opponent_team_id', type=int)

    if not player_id or not opponent_team_id:
        return jsonify({"error": "Missing required parameters"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        player_average_10_games_query = """
                SELECT AVG(points)
            FROM (
                SELECT pgs.points
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
                WHERE pgs.player_id = %s
                ORDER BY g.game_date DESC
                LIMIT 10
            ) AS last_10_games;
            """
        
        cur.execute(player_average_10_games_query, (player_id,))
        player_avg_result = cur.fetchone()
        player_points_last_10 = player_avg_result[0] if player_avg_result and player_avg_result[0] is not None else 0.0

        opponent_avg_query = """
                    WITH game_opponent AS (
                        SELECT g1.game_id, g1.team_id, g2.points AS points_allowed
                        FROM games g1 JOIN games g2 on g1.game_id = g2.game_id and g1.team_id != g2.team_id
                    )

                    SELECT AVG(points_allowed)
                    FROM (
                        SELECT go.points_allowed, g.game_date
                        FROM games g JOIN game_opponent go ON g.game_id = go.game_id AND g.team_id = go.team_id
                        WHERE g.team_id = %s
                        ORDER BY g.game_date DESC
                        LIMIT 10
                    ) AS last_10_opponent_games;
            """

        cur.execute(opponent_avg_query, (opponent_team_id,))
        opponent_avg_result = cur.fetchone()
        opponent_avg_points_allowed_last_10 = opponent_avg_result[0] if opponent_avg_result and opponent_avg_result[0] is not None else 115.0

        feature_df = pd.DataFrame({
            'player_points_last_10': [player_points_last_10],
            'opponent_avg_points_allowed_last_10': [opponent_avg_points_allowed_last_10]
        })

        prediction = model.predict(feature_df)
        predicted_points = round(prediction[0], 2)

        return jsonify ({
            "player_id": player_id,
            "opponent_team_id": opponent_team_id,
            "predicted_points": predicted_points
        })

    except Exception as e:
        print("Error during prediction")
        traceback.print_exc()
        return jsonify({"error": "An error occurred during prediction."}), 500
    
    finally:
        if conn:
            conn.close()