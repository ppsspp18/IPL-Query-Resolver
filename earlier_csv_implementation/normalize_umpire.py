# normalize_umpire.py

import pandas as pd

# Load datasets
ipl = pd.read_csv("IPL.csv")
umpires = pd.read_csv("umpires.csv")

# Keep only required columns
match_umpire = ipl[['match_id', 'umpire']].copy()

# Remove blank umpire names
match_umpire = match_umpire.dropna(subset=['umpire'])

# Remove duplicate match_id + umpire combinations
match_umpire = match_umpire.drop_duplicates()

# Join with umpire master table
match_umpire = match_umpire.merge(
    umpires,
    left_on='umpire',
    right_on='umpire_name',
    how='left'
)

# Keep only IDs
match_umpire = match_umpire[['match_id', 'umpire_id']]

# Sort for readability
match_umpire = match_umpire.sort_values(
    ['match_id', 'umpire_id']
)

# Save output
match_umpire.to_csv(
    "match_umpire.csv",
    index=False
)

print(f"Created match_umpire.csv with {len(match_umpire)} records")
print(match_umpire.head())