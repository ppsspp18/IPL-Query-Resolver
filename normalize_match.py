import pandas as pd
import numpy as np
import re


ipl = pd.read_csv("IPL.csv")

teams = pd.read_csv("teams.csv")
venues = pd.read_csv("venues.csv")

players = pd.read_csv("players.csv")

player_lookup = dict(
    zip(
        players["player_name"].str.strip(),
        players["player_id"]
    )
)


team_lookup = dict(
    zip(
        teams["team_name"].str.strip(),
        teams["team_id"]
    )
)

venue_lookup = dict(
    zip(
        venues["venue_name"].str.strip(),
        venues["venue_id"]
    )
)

match_df = (
    ipl.groupby("match_id")
    .first()
    .reset_index()
)


match_csv = pd.DataFrame()

match_csv["match_id"] = match_df["match_id"]
match_csv["season"] = match_df["season"]
match_csv["date"] = match_df["date"]

match_csv["venue_id"] = (
    match_df["venue"]
    .str.strip()
    .map(venue_lookup)
)

match_csv["match_type"] = (
    match_df["stage"]
    .fillna("League")
    .replace("Unknown", "League")
)

match_csv.to_csv("match.csv", index=False)

print("match.csv created")


def extract_margin(win_outcome):
    """
    Examples:
    140 runs -> 140
    6 wickets -> 6
    blank -> 0
    """
    if pd.isna(win_outcome):
        return 0

    text = str(win_outcome).strip()

    if text == "":
        return 0

    m = re.search(r"(\d+)", text)

    return int(m.group(1)) if m else 0


def extract_result_type(win_outcome):
    """
    Examples:
    140 runs -> run
    6 wickets -> wicket
    blank -> super
    """
    if pd.isna(win_outcome):
        return "super"

    text = str(win_outcome).lower().strip()

    if text == "":
        return "super"

    if "run" in text:
        return "run"

    if "wicket" in text:
        return "wicket"

    return "super"


match_result = pd.DataFrame()

match_result["match_id"] = match_df["match_id"]

# Winner logic
winner = []

for _, row in match_df.iterrows():

    match_winner = str(row["match_won_by"]).strip()

    if (
        pd.isna(row["match_won_by"])
        or match_winner == ""
        or match_winner.lower() == "unknown"
    ):
        match_winner = row["superover_winner"]

    winner.append(team_lookup.get(match_winner))

match_result["winner_id"] = winner

match_result["player_of_match_id"] = (
    match_df["player_of_match"]
    .astype(str)
    .str.strip()
    .map(player_lookup)
)

# Result type
match_result["result"] = (
    match_df["win_outcome"]
    .apply(extract_result_type)
)

# Winning margin
match_result["result_margin"] = (
    match_df["win_outcome"]
    .apply(extract_margin)
)

# Target run
match_result["target_run"] = match_df["runs_target"]

# Target over
match_result["target_over"] = match_df["overs"]

# Super over flag
match_result["super_over"] = np.where(
    match_df["superover_winner"].isna(),
    "N",
    "Y"
)

# Method
match_result["method"] = match_df["method"]

match_result.to_csv("match_result.csv", index=False)

print("match_result.csv created")

match_teams = []

for match_id, grp in ipl.groupby("match_id"):

    teams_in_match = (
        pd.concat([
            grp["batting_team"],
            grp["bowling_team"]
        ])
        .dropna()
        .unique()
        .tolist()
    )

    if len(teams_in_match) != 2:
        print(
            f"Warning: Match {match_id} has "
            f"{len(teams_in_match)} teams."
        )
        continue

    team1 = team_lookup.get(teams_in_match[0])
    team2 = team_lookup.get(teams_in_match[1])

    match_teams.append([
        match_id,
        team1,
        team2
    ])

match_teams_df = pd.DataFrame(
    match_teams,
    columns=[
        "match_id",
        "team1_id",
        "team2_id"
    ]
)

match_teams_df.to_csv(
    "match_teams.csv",
    index=False
)

print("match_teams.csv created")


# =========================
# MATCH_TOSS.CSV
# =========================

match_toss = pd.DataFrame()

match_toss["match_id"] = match_df["match_id"]

match_toss["toss_winner_id"] = (
    match_df["toss_winner"]
    .astype(str)
    .str.strip()
    .map(team_lookup)
)

match_toss["toss_decision"] = (
    match_df["toss_decision"]
    .fillna("Unknown")
)

match_toss.to_csv(
    "match_toss.csv",
    index=False
)

print("match_toss.csv created")