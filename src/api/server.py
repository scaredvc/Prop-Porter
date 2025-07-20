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

        cur.execute("SELECT id, full_name, abbreviation FROM teams ORDER BY full_name;")
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
