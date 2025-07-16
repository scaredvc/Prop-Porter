from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog
def get_all_teams():
    return teams.get_teams()

def get_game_logs_for_player(player_id, season, season_type):

    return playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star=season_type)

def main():
    teams = get_all_teams()

    try: 
        game_logs = get_game_logs_for_player(2544, '2023-24', 'Regular Season')

        if game_logs.get_data_frames()[0].empty:
            print("No game logs found for player")
        else:
            print(game_logs.get_data_frames()[0])
            print(game_logs.get_data_frames()[0].columns)

    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()