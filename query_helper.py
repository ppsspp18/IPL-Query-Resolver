import pandas as pd
import os

# Determine the base directory where CSV files are located.
# Assuming they are in the same directory as this helper module.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV file from the BASE_DIR.

    Args:
        filename: Name of the CSV file.
    Returns:
        pandas DataFrame with the CSV contents.
    """
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")
    return pd.read_csv(path)

def get_teams() -> pd.DataFrame:
    """Return the list of all teams with columns `team_id` and `team_name`."""
    return _load_csv('teams.csv')

def get_players() -> pd.DataFrame:
    """Return the list of all players with columns `player_id` and `player_name`."""
    return _load_csv('players.csv')

def get_umpires() -> pd.DataFrame:
    """Return the list of all umpires with columns `umpire_id` and `umpire_name`.
    If the umpires CSV does not exist, an empty DataFrame is returned.
    """
    try:
        return _load_csv('umpires.csv')
    except FileNotFoundError:
        return pd.DataFrame(columns=['umpire_id', 'umpire_name'])

def get_match_dates() -> pd.DataFrame:
    """Load match.csv containing match_id, season, date, venue_id, match_type columns."""
    return _load_csv('match.csv')

def get_match_info() -> pd.DataFrame:
    """Load match_result.csv with match result information."""
    return _load_csv('match_result.csv')

