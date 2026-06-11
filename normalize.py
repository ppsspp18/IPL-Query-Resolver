import pandas as pd


def create_match_venue_df():
    """
    Creates a DataFrame with match_id and venue columns from IPL.csv.
    Removes duplicates and resets index.
    
    Returns:
        pd.DataFrame: DataFrame with match_id and venue columns
    """
    # Read the IPL.csv file
    ipl_df = pd.read_csv('IPL.csv')
    
    # Extract match_id and venue columns
    match_venue_df = ipl_df[['match_id', 'venue']].copy()
    
    # Remove duplicates if any
    match_venue_df = match_venue_df.drop_duplicates()
    
    # Reset index
    match_venue_df = match_venue_df.reset_index(drop=True)
    
    return match_venue_df


def create_player_of_match_df():
    """
    Creates a DataFrame with match_id and player_of_match columns from IPL.csv.
    Removes duplicates and resets index.
    
    Returns:
        pd.DataFrame: DataFrame with match_id and player_of_match columns
    """
    # Read the IPL.csv file
    ipl_df = pd.read_csv('IPL.csv')
    
    # Extract match_id and player_of_match columns
    player_of_match_df = ipl_df[['match_id', 'player_of_match']].copy()
    
    # Remove duplicates if any
    player_of_match_df = player_of_match_df.drop_duplicates()
    
    # Reset index
    player_of_match_df = player_of_match_df.reset_index(drop=True)
    
    return player_of_match_df


if __name__ == "__main__":
    # Create match_venue DataFrame and save to CSV
    match_venue_df = create_match_venue_df()
    match_venue_df.to_csv('match_venue.csv', index=False)
    print("match_venue.csv created successfully!")
    print(f"Total records: {len(match_venue_df)}")
    print(match_venue_df.head())
    
    print("\n" + "="*50 + "\n")
    
    # Create player_of_match DataFrame and save to CSV
    player_of_match_df = create_player_of_match_df()
    player_of_match_df.to_csv('player_of_match.csv', index=False)
    print("player_of_match.csv created successfully!")
    print(f"Total records: {len(player_of_match_df)}")
    print(player_of_match_df.head())


