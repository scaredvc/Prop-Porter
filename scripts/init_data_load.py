import psycopg2
import os
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.endpoints import leaguegamefinder
import time

season_to_load = ['2023-24']

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
        for season in season_to_load:
                game_finder = leaguegamefinder.LeagueGameFinder(season_nullable=season)
                all_games_for_season = game_finder.get_data_frames()[0]

                print(f'Loading {len(all_games_for_season)} games for {season}')
                time.sleep(0.75)
                
                for index, row in all_games_for_season.iterrows():
                        game_data = {
                            'season_id': row['SEASON_ID'],
                            'team_id': row['TEAM_ID'],
                            'team_abbreviation': row['TEAM_ABBREVIATION'],
                            'game_id': row['GAME_ID'],
                            'game_date': row['GAME_DATE'],
                            'matchup': row['MATCHUP'],
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
                                matchup, win_loss, minutes, points, fgm,
                                fga, fg_pct, fg3m, fg3a, fg3_pct,
                                ftm, fta, ft_pct, oreb, dreb,
                                reb, ast, stl, blk, tov,
                                pf, plus_minus

                            ) VALUES (
                            %(season_id)s, %(team_id)s, %(team_abbreviation)s, %(game_id)s, %(game_date)s,
                            %(matchup)s, %(win_loss)s, %(minutes)s, %(points)s, %(fgm)s,
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


def load_player_game_stats():
    try:
        all_players = players.get_active_players()
        print(f'Loading game stats for {len(all_players)} players')

        for player in all_players:
                player_id = player["id"]
                
                for season in season_to_load:
                        # Get player's game log for the season
                        gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                        player_games = gamelog.get_data_frames()[0]
                        
                        print(f'Loading {len(player_games)} games for player {player["full_name"]} in season {season}')
                        time.sleep(0.75)  # Rate limiting to avoid API issues
                        
                        for index, game in player_games.iterrows():

                                game_data = {
                                    'player_id': player_id,
                                    'game_id': game['Game_ID'],
                                    'team_id': game['TEAM_ID'],
                                    'minutes': float(game['MIN']) if game['MIN'] != '' else 0,
                                    'points': game['PTS'],
                                    'rebounds': game['REB'],
                                    'assists': game['AST'],
                                    'steals': game['STL'],
                                    'blocks': game['BLK'],
                                    'turnovers': game['TOV'],
                                    'fgm': game['FGM'],
                                    'fga': game['FGA'],
                                    'fg_pct': game['FG_PCT'],
                                    'fg3m': game['FG3M'],
                                    'fg3a': game['FG3A'],
                                    'fg3_pct': game['FG3_PCT'],
                                    'ftm': game['FTM'],
                                    'fta': game['FTA'],
                                    'ft_pct': game['FT_PCT']
                                }
                                
                                sql_command = """
                                    INSERT INTO player_game_stats (
                                        player_id, game_id, team_id, minutes, points,
                                        rebounds, assists, steals, blocks, turnovers,
                                        fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                                        ftm, fta, ft_pct
                                    ) VALUES (
                                        %(player_id)s, %(game_id)s, %(team_id)s, %(minutes)s, %(points)s,
                                        %(rebounds)s, %(assists)s, %(steals)s, %(blocks)s, %(turnovers)s,
                                        %(fgm)s, %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
                                        %(ftm)s, %(fta)s, %(ft_pct)s
                                    )
                                    ON CONFLICT (player_id, game_id) DO NOTHING;
                                """
                                
                                cur.execute(sql_command, game_data)
                                

        connection.commit()
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