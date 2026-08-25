import pandas as pd

# Load the full IPL dataset
df = pd.read_csv('IPL.csv')

# ------------------- Teams -------------------
team_names = pd.concat([df['batting_team'], df['bowling_team']]).dropna().unique()
teams_df = pd.DataFrame({'team_name': team_names})
teams_df.insert(0, 'team_id', range(1, len(teams_df) + 1))
teams_df.to_csv('teams.csv', index=False)
print(f"Created teams.csv with {len(teams_df)} records")

# ------------------- Venues -------------------
venues_df = df[['venue', 'city']].drop_duplicates().rename(columns={'venue': 'venue_name', 'city': 'venue_city'})
venues_df.insert(0, 'venue_id', range(1, len(venues_df) + 1))
venues_df.to_csv('venues.csv', index=False)
print(f"Created venues.csv with {len(venues_df)} records")

# ------------------- Umpires -------------------
if 'umpire' in df.columns:
    umpire_names = df['umpire'].dropna().unique()
    umpires_df = pd.DataFrame({'umpire_name': umpire_names})
    umpires_df.insert(0, 'umpire_id', range(1, len(umpires_df) + 1))
    umpires_df.to_csv('umpires.csv', index=False)
    print(f"Created umpires.csv with {len(umpires_df)} records")
else:
    print("No 'umpire' column found; umpires.csv not created")

# ------------------- Players -------------------
player_columns = ['batter', 'bowler', 'player_of_match', 'player_out', 'fielders']
players_series = []
for col in player_columns:
    if col in df.columns:
        series = df[col].dropna()
        if col == 'fielders':
            series = (
                series
                .str.replace(r"[\(\)']", '', regex=True)
                .str.split(',')
                .str.strip()
                .explode()
            )
        players_series.append(series)
if players_series:
    all_players = pd.concat(players_series).astype(str).str.strip().dropna().unique()
    players_df = pd.DataFrame({'player_name': all_players})
    players_df.insert(0, 'player_id', range(1, len(players_df) + 1))
    players_df.to_csv('players.csv', index=False)
    print(f"Created players.csv with {len(players_df)} records")
else:
    print("No player columns found; players.csv not created")
