import pandas as pd

print("Loading files...")

# Main ball-by-ball dataset
ipl = pd.read_csv("IPL.csv")

# Master tables
teams = pd.read_csv("teams.csv")
players = pd.read_csv("players.csv")

# --------------------------------------------------
# Create lookup dictionaries
# --------------------------------------------------

team_lookup = dict(
    zip(
        teams['team_name'],
        teams['team_id']
    )
)

player_lookup = dict(
    zip(
        players['player_name'],
        players['player_id']
    )
)

# --------------------------------------------------
# Create delivery table
# --------------------------------------------------

delivery = pd.DataFrame()

delivery['match_id'] = ipl['match_id']
delivery['innings'] = ipl['innings']
delivery['over'] = ipl['over']
delivery['ball'] = ipl['ball']

# Team IDs
delivery['batting_team_id'] = (
    ipl['batting_team']
    .map(team_lookup)
)

delivery['bowling_team_id'] = (
    ipl['bowling_team']
    .map(team_lookup)
)

# Player IDs
delivery['batter_id'] = (
    ipl['batter']
    .map(player_lookup)
)

delivery['bowler_id'] = (
    ipl['bowler']
    .map(player_lookup)
)

delivery['non_striker_id'] = (
    ipl['non_striker']
    .map(player_lookup)
)

# Runs
delivery['runs_batter'] = ipl['runs_batter']
delivery['runs_extras'] = ipl['runs_extras']
delivery['runs_total'] = ipl['runs_total']

# --------------------------------------------------
# Check missing mappings
# --------------------------------------------------

print("\nMissing Team IDs:")

print(
    delivery[
        delivery['batting_team_id'].isna()
    ].shape[0],
    "batting teams"
)

print(
    delivery[
        delivery['bowling_team_id'].isna()
    ].shape[0],
    "bowling teams"
)

print("\nMissing Player IDs:")

print(
    delivery[
        delivery['batter_id'].isna()
    ].shape[0],
    "batters"
)

print(
    delivery[
        delivery['bowler_id'].isna()
    ].shape[0],
    "bowlers"
)

print(
    delivery[
        delivery['non_striker_id'].isna()
    ].shape[0],
    "non-strikers"
)

# --------------------------------------------------
# Save
# --------------------------------------------------

delivery.to_csv(
    "delivery.csv",
    index=False
)

print(
    f"\nCreated delivery.csv with {len(delivery):,} rows"
)

print(delivery.head())