from nba_api.stats.static import teams

def get_all_teams():
    return teams.get_teams()

def main():
    teams = get_all_teams()
    print(teams)

if __name__ == "__main__":
    main()