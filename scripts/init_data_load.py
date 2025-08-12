import psycopg2
import os
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.endpoints import leaguegamefinder
import time
import pandas as pd
from requests.exceptions import Timeout, ConnectionError
import random
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

# Configuration helpers to read env values safely
def _get_env_int(name: str, default: int) -> int:
    try:
        value = os.getenv(name)
        return int(value) if value is not None and value != '' else default
    except Exception:
        return default

def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def _get_env_float(name: str, default: float) -> float:
    try:
        value = os.getenv(name)
        return float(value) if value is not None and value != '' else default
    except Exception:
        return default

# Retry/rate-limit configuration (overridable via env)
# API_MAX_RETRIES, API_BASE_TIMEOUT, API_RATE_LIMIT_MIN, API_RATE_LIMIT_MAX, API_COOL_OFF_ON_TIMEOUT
MAX_RETRIES = _get_env_int("API_MAX_RETRIES", 3)
BASE_TIMEOUT = _get_env_float("API_BASE_TIMEOUT", 45.0)  # seconds per attempt
RATE_LIMIT_MIN = _get_env_float("API_RATE_LIMIT_MIN", 3.0)
RATE_LIMIT_MAX = _get_env_float("API_RATE_LIMIT_MAX", 5.0)
COOL_OFF_ON_TIMEOUT = _get_env_float("API_COOL_OFF_ON_TIMEOUT", 0.0)

# Seasons to load, configurable via env: API_SEASONS="2021-22,2022-23,2023-24"
def _parse_env_seasons(env_value: Optional[str]) -> List[str]:
    if not env_value:
        return ['2023-24']
    seasons: List[str] = []
    for raw in env_value.split(','):
        s = raw.strip()
        if not s:
            continue
        # Basic validation: expect YYYY-YY shape
        if len(s) == 7 and s[4] == '-' and s[:4].isdigit() and s[5:].isdigit():
            seasons.append(s)
        else:
            # If invalid, skip silently
            continue
    return seasons or ['2023-24']

season_to_load: List[str] = _parse_env_seasons(os.getenv('API_SEASONS'))

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

def make_api_request(request_func, *args, context_label: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """Make an API request with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            label = context_label or getattr(request_func, '__name__', str(request_func))
            print(f"Attempt {attempt + 1}/{MAX_RETRIES} for {label}")
            # Light rate limit before attempting call
            time.sleep(random.uniform(max(0.0, RATE_LIMIT_MIN - 0.5), RATE_LIMIT_MIN))
            result = request_func(*args, **kwargs)
            if result is None:
                raise ValueError("API request returned None")
            df = result.get_data_frames()[0]
            if not isinstance(df, pd.DataFrame) or df.empty:
                raise ValueError("No data returned from API")
            return df
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Final attempt failed: {str(e)}")
                raise
            print(f"Request failed with error: {str(e)}")
            # Shorter backoff for transient network issues
            if isinstance(e, (Timeout, ConnectionError)):
                backoff_seconds = 1.0 + random.uniform(0, 1)
            else:
                backoff_seconds = (attempt + 1) * 2 + random.uniform(0, 1)
            time.sleep(backoff_seconds)
    raise ValueError("Failed to get valid response after all retries")

def load_players_data():
    try:
        all_players = players.get_active_players()
        print(f'Retrieving {len(all_players)} players')

        # Identify which players actually need enrichment (position/height/weight/age missing)
        refresh_all_meta = _get_env_bool("API_REFRESH_PLAYER_META", False)
        cur.execute("SELECT id, position, height_inches, weight_lbs, age FROM players")
        rows = cur.fetchall()
        ids_needing_meta = set()
        existing_meta = {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}
        for pid, (pos, h, w, age) in existing_meta.items():
            if pos is None or h is None or w is None or age is None:
                ids_needing_meta.add(pid)
        print(f"Players needing metadata: {len(ids_needing_meta)} (refresh_all={refresh_all_meta})")

        # Detect DB VARCHAR limit for players.position so we can truncate safely
        position_limit: Optional[int] = None
        try:
            cur.execute(
                """
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'players' AND column_name = 'position'
                """
            )
            row = cur.fetchone()
            if row and row[0]:
                position_limit = int(row[0])
        except Exception:
            position_limit = None

        for player in all_players:
                player_id = player["id"]
                player_full_name = player["full_name"]
                player_first_name = player["first_name"]
                player_last_name = player["last_name"]
                player_active_status = player["is_active"]
                # Enrich with detailed info: position, height, weight, age
                def _parse_height_to_inches(height_str: Optional[str]) -> Optional[int]:
                    try:
                        if not height_str:
                            return None
                        parts = str(height_str).split('-')
                        if len(parts) != 2:
                            return None
                        feet = int(parts[0])
                        inches = int(parts[1])
                        return feet * 12 + inches
                    except Exception:
                        return None

                def _parse_int_safe(value: object) -> Optional[int]:
                    try:
                        if value is None or value == '':
                            return None
                        return int(str(value).strip())
                    except Exception:
                        return None

                def _calculate_age(birthdate_str: Optional[str]) -> Optional[int]:
                    try:
                        if not birthdate_str:
                            return None
                        # CommonPlayerInfo uses ISO-like format
                        from datetime import datetime, timezone
                        # Handle possible timezone suffix
                        dt = datetime.fromisoformat(str(birthdate_str).replace('Z', '+00:00'))
                        today = datetime.now(timezone.utc)
                        age = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
                        return age
                    except Exception:
                        return None

                # Decide whether to fetch metadata from API
                should_fetch_meta = refresh_all_meta or (player_id in ids_needing_meta) or (player_id not in existing_meta)

                info_df = pd.DataFrame()
                if should_fetch_meta:
                    # Fetch details with retry/timeout only when needed
                    try:
                        info_df = make_api_request(
                            commonplayerinfo.CommonPlayerInfo,
                            context_label=f"CommonPlayerInfo player_id={player_id}",
                            player_id=player_id,
                            timeout=BASE_TIMEOUT
                        )
                    except Exception:
                        info_df = pd.DataFrame()

                position_val = None
                height_inches_val = None
                weight_lbs_val = None
                age_val = None

                if isinstance(info_df, pd.DataFrame) and not info_df.empty:
                    # First table has basic info
                    row0 = info_df.iloc[0]
                    position_val = str(row0.get('POSITION') or '').strip() or None
                    if position_val and position_limit:
                        position_val = position_val[:position_limit]
                    height_inches_val = _parse_height_to_inches(row0.get('HEIGHT'))
                    weight_lbs_val = _parse_int_safe(row0.get('WEIGHT'))
                    age_val = _calculate_age(row0.get('BIRTHDATE'))

                sql_command = """
                INSERT INTO players (
                    id,
                    full_name,
                    first_name,
                    last_name,
                    is_active,
                    position,
                    height_inches,
                    weight_lbs,
                    age
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    is_active = EXCLUDED.is_active,
                    position = COALESCE(EXCLUDED.position, players.position),
                    height_inches = COALESCE(EXCLUDED.height_inches, players.height_inches),
                    weight_lbs = COALESCE(EXCLUDED.weight_lbs, players.weight_lbs),
                    age = COALESCE(EXCLUDED.age, players.age);
                """

                values_to_insert = (
                    player_id,
                    player_full_name,
                    player_first_name,
                    player_last_name,
                    player_active_status,
                    position_val,
                    height_inches_val,
                    weight_lbs_val,
                    age_val,
                )
                cur.execute(sql_command, values_to_insert)
                if should_fetch_meta:
                    rate_limit_sleep()
                
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
                try:
                        all_games_for_season = make_api_request(
                            leaguegamefinder.LeagueGameFinder,
                            context_label=f"LeagueGameFinder season={season}",
                            season_nullable=season,
                            timeout=BASE_TIMEOUT
                        )

                        print(f'Loading {len(all_games_for_season)} games for {season}')
                        rate_limit_sleep()
                        
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
                except Exception as e:
                        print(f"Error loading games for {season}: {str(e)}")
                        if isinstance(e, (Timeout, ConnectionError)) and COOL_OFF_ON_TIMEOUT > 0:
                                try:
                                        print(f'Cooling off for {COOL_OFF_ON_TIMEOUT} seconds due to timeout while loading season {season}...')
                                        time.sleep(COOL_OFF_ON_TIMEOUT)
                                except Exception:
                                        pass
                        # continue with next season
                        continue
                        
        connection.commit()
        print(f'Done loading games for {season}')
        
    except Exception as e:
        print(f'Fatal error in load_games_data: {str(e)}')
        connection.rollback()
        raise


# Odds API ingestion removed as per cleanup decision (left intentionally empty)

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

        def _season_str_to_season_id(season_str: str) -> int:
            """Convert season like '2023-24' to numeric season_id 22023 used in DB."""
            try:
                start_year = int(season_str[:4])
                return 22000 + start_year - 2000
            except Exception:
                return 22023

        season_ids_clause = ','.join(str(_season_str_to_season_id(s)) for s in season_to_load)
        from_games_table = f"""
            SELECT DISTINCT game_id, season_id
            FROM games
            WHERE season_id IN ({season_ids_clause})
        """

        cur.execute(from_games_table)
        all_games = cur.fetchall()
        total_games = len(all_games)
        print(f"Processing {total_games} games")

        for game_index, game_row in enumerate(all_games, 1):
                game_id = game_row[0]
                season_id_for_game = game_row[1]
                
                # Skip if already processed
                if game_id in processed_games:
                    print(f"Skipping already processed game {game_index}/{total_games} (ID: {game_id})")
                    continue
                
                print(f"Processing game {game_index}/{total_games} (ID: {game_id})")

                try:
                    player_games = make_api_request(
                        boxscoretraditionalv2.BoxScoreTraditionalV2,
                        context_label=f"BoxScoreTraditionalV2 game_id={game_id}",
                        game_id=game_id,
                        timeout=BASE_TIMEOUT
                    )

                    print(f'Loading {len(player_games)} player stats for game {game_id}')
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
                    # Optional cool-off after network timeouts before moving on
                    if isinstance(e, (Timeout, ConnectionError)) and COOL_OFF_ON_TIMEOUT > 0:
                        try:
                            print(f'Cooling off for {COOL_OFF_ON_TIMEOUT} seconds due to timeout...')
                            time.sleep(COOL_OFF_ON_TIMEOUT)
                        except Exception:
                            pass
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