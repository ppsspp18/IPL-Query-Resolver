import pandas as pd

print("Loading files...")

# Main dataset
ipl = pd.read_csv("IPL.csv")

# Players master table
players = pd.read_csv("players.csv")

player_lookup = dict(
    zip(
        players['player_name'],
        players['player_id']
    )
)

dismissal = ipl[
    ipl['wicket_kind'].notna()
].copy()

dismissal = dismissal[
    dismissal['wicket_kind'].astype(str).str.strip() != ''
]

dismissal_table = pd.DataFrame()

dismissal_table['match_id'] = dismissal['match_id']
dismissal_table['innings'] = dismissal['innings']
dismissal_table['over'] = dismissal['over']
dismissal_table['ball'] = dismissal['ball']

dismissal_table['player_out_id'] = (
    dismissal['player_out']
    .map(player_lookup)
)

dismissal_table['wicket_kind'] = dismissal['wicket_kind']

dismissal_table['fielder_id'] = (
    dismissal['fielders']
    .map(player_lookup)
)

dismissal_table.to_csv(
    'dismissal.csv',
    index=False
)

print(
    f"Created dismissal.csv with {len(dismissal_table):,} dismissals"
)

print(dismissal_table.head())