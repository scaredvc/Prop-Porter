import psycopg2
import os
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import leaguegamefinder
import time
import pandas as pd
from requests.exceptions import Timeout, ConnectionError
import random
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Retry configuration
MAX_RETRIES = 3
BASE_TIMEOUT = 120  # Increased timeout to 120 seconds
RATE_LIMIT_MIN = 1.5  # Minimum seconds between requests
RATE_LIMIT_MAX = 2.5  # Maximum seconds between requests

season_to_load = ['2023-24']

connection = psycopg2.connect(
    dbname = os.getenv("DB_NAME"),
    user = os.getenv("DB_USER"),
    password = os.getenv("DB_PASSWORD"),
    host = os.getenv("DB_HOST"),
    port = os.getenv("DB_PORT"),
)

cur = connection.cursor()
print("connected to database")

def rate_limit_sleep():
    """Sleep for a random duration to avoid rate limiting"""
    time.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))

def make_api_request(request_func, *args, **kwargs) -> pd.DataFrame:
    """Make an API request with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{MAX_RETRIES}")
            result = request_func(*args, **kwargs)
            if result is None:
                raise ValueError("API request returned None")
            df = result.get_data_frames()[0]
            if not isinstance(df, pd.DataFrame) or df.empty:
                raise ValueError("No data returned from API")
            return df
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"Request failed with error: {str(e)}")
            # Exponential backoff
            time.sleep((attempt + 1) * 2)
    raise ValueError("Failed to get valid response after all retries")

def load_players_data():
    try:
        all_players = players.get_active_players()
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
        
    except Exception as e:
        print(f'Fatal error in load_players_data: {str(e)}')
        connection.rollback()
        raise

def load_teams_data():
    try:
        all_teams = teams.get_teams()
        print(f'Retrieving {len(all_teams)} teams')

        for team in all_teams:
                sql_command = """
                    INSERT INTO teams(
                        id, 
                        full_name,
                        abbreviation,
                        nickname,
                        city,
                        state,
                        year_founded
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING;
                """ 
                values_to_insert = (team['id'], team['full_name'], team['abbreviation'], team['nickname'], team['city'], team['state'], team['year_founded'])
                cur.execute(sql_command, values_to_insert)
                
        connection.commit()
        print('Done loading teams')
        
    except Exception as e:
        print(f'Fatal error in load_teams_data: {str(e)}')
        connection.rollback()
        raise

def load_games_data():
    try:

        active_teams = teams.get_teams()
        valid_teams_set = {team['id'] for team in active_teams}
        abbr_to_id = {team['abbreviation']: team['id'] for team in active_teams}

        def parse_matchup(matchup_str: str):
            # Expected formats: "LAL vs. GSW" (home) or "LAL @ GSW" (away)
            try:
                parts = str(matchup_str).split()
                if len(parts) >= 3:
                    # parts[0] = team abbr, parts[1] = 'vs.' or '@', parts[2] = opponent abbr
                    is_home_local = True if parts[1] == 'vs.' else False if parts[1] == '@' else None
                    opponent_abbr_local = parts[2]
                    return is_home_local, opponent_abbr_local
            except Exception:
                pass
            return None, None

        for season in season_to_load:
                game_finder = leaguegamefinder.LeagueGameFinder(season_nullable=season)
                all_games_for_season = game_finder.get_data_frames()[0]

                print(f'Loading {len(all_games_for_season)} games for {season}')
                time.sleep(0.75)
                
                for index, row in all_games_for_season.iterrows():
                        if row['TEAM_ID'] not in valid_teams_set:
                            continue
                    
                        is_home, opponent_abbr = parse_matchup(row['MATCHUP'])
                        opponent_team_id = abbr_to_id.get(opponent_abbr) if opponent_abbr else None

                        game_data = {
                            'season_id': row['SEASON_ID'],
                            'team_id': row['TEAM_ID'],
                            'team_abbreviation': row['TEAM_ABBREVIATION'],
                            'game_id': row['GAME_ID'],
                            'game_date': row['GAME_DATE'],
                            'matchup': row['MATCHUP'],
                            'is_home': is_home,
                            'opponent_team_id': opponent_team_id,
                            'win_loss': row['WL'],
                            'minutes': row['MIN'],
                            'points': row['PTS'],
                            'fgm': row['FGM'],
                            'fga': row['FGA'],
                            'fg_pct': row['FG_PCT'],
                            'fg3m': row['FG3M'],
                            'fg3a': row['FG3A'],
                            'fg3_pct': row['FG3_PCT'],
                            'ftm': row['FTM'],
                            'fta': row['FTA'],
                            'ft_pct': row['FT_PCT'],
                            'oreb': row['OREB'],
                            'dreb': row['DREB'],
                            'reb': row['REB'],
                            'ast': row['AST'],
                            'stl': row['STL'],
                            'blk': row['BLK'],
                            'tov': row['TOV'],
                            'pf': row['PF'],
                            'plus_minus': row['PLUS_MINUS']
                        }
                        
                        sql_command = """
                            INSERT INTO games (
                                season_id, team_id, team_abbreviation, game_id, game_date,
                                matchup, opponent_team_id, is_home,
                                win_loss, minutes, points, fgm,
                                fga, fg_pct, fg3m, fg3a, fg3_pct,
                                ftm, fta, ft_pct, oreb, dreb,
                                reb, ast, stl, blk, tov,
                                pf, plus_minus

                            ) VALUES (
                                %(season_id)s, %(team_id)s, %(team_abbreviation)s, %(game_id)s, %(game_date)s,
                                %(matchup)s, %(opponent_team_id)s, %(is_home)s,
                                %(win_loss)s, %(minutes)s, %(points)s, %(fgm)s,
                                %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
                                %(ftm)s, %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s,
                                %(reb)s, %(ast)s, %(stl)s, %(blk)s, %(tov)s,
                                %(pf)s, %(plus_minus)s
                            )
                            ON CONFLICT (game_id, team_id) DO NOTHING;
                        """

                        cur.execute(sql_command, game_data)
                        
        connection.commit()
        print(f'Done loading games for {season}')
        
    except Exception as e:
        print(f'Fatal error in load_games_data: {str(e)}')
        connection.rollback()
        raise

def convert_time_to_minutes(time_str):
    if not time_str or time_str == '':
        return 0
    try:
        minutes, seconds = time_str.split(':')
        return float(minutes) + float(seconds)/60
    except:
        return 0

def load_player_game_stats():
    try:
        cur.execute("SELECT id FROM players")
        active_player_ids = {row[0] for row in cur.fetchall()}
        print(f"Active player IDs: {len(active_player_ids)} players found")

        # Get already processed games
        cur.execute("SELECT DISTINCT game_id FROM player_game_stats")
        processed_games = {row[0] for row in cur.fetchall()}
        print(f"Found {len(processed_games)} already processed games")

        from_games_table = """
            SELECT DISTINCT game_id
            FROM games
            WHERE season_id IN (22023)
        """

        cur.execute(from_games_table)
        all_games = cur.fetchall()
        total_games = len(all_games)
        print(f"Processing {total_games} games")

        for game_index, game_row in enumerate(all_games, 1):
                game_id = game_row[0]
                
                # Skip if already processed
                if game_id in processed_games:
                    print(f"Skipping already processed game {game_index}/{total_games} (ID: {game_id})")
                    continue
                
                print(f"Processing game {game_index}/{total_games} (ID: {game_id})")
  
                for season in season_to_load:
                        try:
                            player_games = make_api_request(
                                boxscoretraditionalv2.BoxScoreTraditionalV2,
                                game_id=game_id,
                                timeout=BASE_TIMEOUT
                            )
                            
                            print(f'Loading {len(player_games)} player stats for game {game_id} in season {season}')
                            rate_limit_sleep()
                            
                            for index, game in player_games.iterrows():
                                    player_id = int(game['PLAYER_ID'])
                                     
                                    if player_id not in active_player_ids:
                                        continue

                                    game_data = {
                                        'player_id': player_id,
                                        'game_id': game['GAME_ID'],
                                        'team_id': game['TEAM_ID'],
                                        'minutes': convert_time_to_minutes(game['MIN']),
                                        'points': 0 if pd.isna(game['PTS']) else game['PTS'],
                                        'rebounds': 0 if pd.isna(game['REB']) else game['REB'],
                                        'oreb': 0 if pd.isna(game.get('OREB')) else game.get('OREB'),
                                        'dreb': 0 if pd.isna(game.get('DREB')) else game.get('DREB'),
                                        'assists': 0 if pd.isna(game['AST']) else game['AST'],
                                        'steals': 0 if pd.isna(game['STL']) else game['STL'],
                                        'blocks': 0 if pd.isna(game['BLK']) else game['BLK'],
                                        'turnovers': 0 if pd.isna(game['TO']) else game['TO'],
                                        'fgm': 0 if pd.isna(game['FGM']) else game['FGM'],
                                        'fga': 0 if pd.isna(game['FGA']) else game['FGA'],
                                        'fg_pct': 0 if pd.isna(game['FG_PCT']) else game['FG_PCT'],
                                        'fg3m': 0 if pd.isna(game['FG3M']) else game['FG3M'],
                                        'fg3a': 0 if pd.isna(game['FG3A']) else game['FG3A'],
                                        'fg3_pct': 0 if pd.isna(game['FG3_PCT']) else game['FG3_PCT'],
                                        'ftm': 0 if pd.isna(game['FTM']) else game['FTM'],
                                        'fta': 0 if pd.isna(game['FTA']) else game['FTA'],
                                        'ft_pct': 0 if pd.isna(game['FT_PCT']) else game['FT_PCT'],
                                        'starter': bool(str(game.get('START_POSITION', '') or '').strip())
                                    }
                                    
                                    sql_command = """
                                        INSERT INTO player_game_stats (
                                            player_id, game_id, team_id, minutes, points,
                                            rebounds, oreb, dreb, assists, steals, blocks, turnovers,
                                            fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                                            ftm, fta, ft_pct, starter
                                        ) VALUES (
                                            %(player_id)s, %(game_id)s, %(team_id)s, %(minutes)s, %(points)s,
                                            %(rebounds)s, %(oreb)s, %(dreb)s, %(assists)s, %(steals)s, %(blocks)s, %(turnovers)s,
                                            %(fgm)s, %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
                                            %(ftm)s, %(fta)s, %(ft_pct)s, %(starter)s
                                        )
                                        ON CONFLICT (player_id, game_id) DO NOTHING;
                                    """
                                    
                                    cur.execute(sql_command, game_data)
                                    
                            # Commit after each game to save progress
                            connection.commit()
                            print(f'Successfully processed game {game_id}')
                            
                        except Exception as e:
                            print(f'Error processing game {game_id}: {str(e)}')
                            # Continue with next game instead of failing completely
                            continue

        print('Done loading player game stats')
        
    except Exception as e:
        print(f'Fatal error in load_player_game_stats: {str(e)}')
        connection.rollback()
        raise


if __name__ == "__main__":
    try:
        load_players_data() 
        load_teams_data()
        load_games_data()
        load_player_game_stats()

    except Exception as e:
        print(f'Fatal error in main execution: {str(e)}')
        connection.rollback()

    finally:
        if cur is not None:
            cur.close()
        if connection is not None:
            connection.close()
        print("Connection to database closed")