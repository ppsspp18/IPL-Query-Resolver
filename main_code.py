import pandas as pd
import numpy as np
import time
from collections import defaultdict

def display_projection(df, column_name, label):
    start_time = time.time()

    print("This is a projection type of query")
    print(f"This query uses the {label}.csv and performs a projection on the attribute {column_name}")

    values = df[column_name].tolist()
    print(f"List of all {label}s in IPL:")
    for i, val in enumerate(values, 1):
        print(f"{i}. {val}")
    print(f"Total number of {label}s in IPL: {len(values)}")

    print(f" Time taken: {time.time() - start_time:.4f} seconds\n")

if __name__ == "__main__":
    # Create a DataFrame with random data
    delivery=pd.read_csv('normalized csvs/delivery.csv')
    # delivery['delivery_time'] = pd.to_datetime(delivery['delivery_time'])
    dismissals=pd.read_csv('normalized csvs/dismissals.csv')
    match_result=pd.read_csv('normalized csvs/match_result.csv')
    match_teams=pd.read_csv('normalized csvs/match_teams.csv')
    match=pd.read_csv('normalized csvs/match.csv')
    player_of_the_match=pd.read_csv('normalized csvs/player_of_the_match.csv')
    players=pd.read_csv('normalized csvs/players.csv')
    teams=pd.read_csv('normalized csvs/teams.csv')
    toss=pd.read_csv('normalized csvs/toss.csv')
    umpire=pd.read_csv('normalized csvs/umpire.csv')
    umpire_match=pd.read_csv('normalized csvs/umpire_match.csv')
    venue=pd.read_csv('normalized csvs/venue.csv')

    print("Welcome to the IPL Data Analysis Program!")
    time.sleep(1)
    print("This program consists of the data of all IPL matches from 2008 to 2024")
    time.sleep(1)

    while(True):
        print("\n")
        print("------------------------------------------------------")
        print("Please select any one of the below query")
        print("1 - List of all teams in IPL")
        print("2 - List of all players played in IPL")
        print("3 - List of all umpires in IPL")
        print("4 - List of all venues in IPL")
        print("5 - List of all matches played in IPL and all information about them")
        print("6 - Particular player stats in IPL")
        print("7 - How many times has a particular player became the man of match and in which matches")
        print("8 - Input any 2 teams and find out the head to head stats")
        print("9 - Individual team stats")
        print("10 - Player team history (player played from which team in which season)")
        print("11 - For a given stadium, winning while batting first and winning while batting second")
        print("12 - For a given stadium, average first innings score")
        print("13 - Total number of 4s or 6s per season")
        print("14 - Select a team and find out the average powerplay score for each season")
        print("15 - Select a team and find out the average wickets taken in powerplay for each season")
        print("16 - Each season stats - purple cap, orange cap, most 4s, most 6s,most number of dots balls,winner, runner up")
        print("17 - Number of matches judged by a particular umpire")
        print("18 - Most hundreds and fifties per season")
        print("19 - Most 5 wicket takers in a match per season")
        print("20 - Bowler vs Batter comparison")
        # print("21 - Update player name")
        print("21 - Update team name")
        # print("23 - Update umpire name")
        print("22 - Update venue name")
        
        print("23 - Exit the program")
        print("\n")
        choice=int(input("Enter your choice: "))
        if choice==1:
            display_projection(teams, 'team', 'team')
        elif choice==2:
            display_projection(players, 'player', 'player')
        elif choice==3:
            display_projection(umpire, 'umpire', 'umpire')
        elif choice==4:
            display_projection(venue, 'venue', 'venue')
        elif choice==5:
            start_time = time.time()
            print("This query uses the following csvs:")
            print("1. match.csv -> match_id, season, date, venue_id")
            print("2. match_teams.csv -> match_id, team_id1, team_id2")
            print("3. teams.csv -> team_id, team_name")
            print("4. venue.csv -> venue_id, venue_name")
            print("5. umpire_match.csv -> match_id, umpire_id1, umpire_id2")
            print("6. umpire.csv -> umpire_id, umpire_name")
            print("7. match_result.csv -> match_id, winner_id")
            print("8. player_of_the_match.csv -> match_id, player_of_the_match_id")
            print("9. players.csv -> player_id, player")
            print("10. toss.csv -> match_id, team_id, toss_winner")
            print("\nThe below is the information about the matches:")
            print("Match ID | Season | Date | Venue | Team 1 | Team 2 | Umpire 1 | Umpire 2 | Winner | Player of the Match")

            merged = match.merge(venue, on='venue_id', how='left') \
                  .merge(match_teams, on='match_id', how='left') \
                  .merge(teams.rename(columns={'team_id': 'team_id1', 'team': 'team1_name'}), on='team_id1', how='left') \
                  .merge(teams.rename(columns={'team_id': 'team_id2', 'team': 'team2_name'}), on='team_id2', how='left') \
                  .merge(umpire_match, on='match_id', how='left') \
                  .merge(umpire.rename(columns={'umpire_id': 'umpire_id1', 'umpire': 'umpire1_name'}), on='umpire_id1', how='left') \
                  .merge(umpire.rename(columns={'umpire_id': 'umpire_id2', 'umpire': 'umpire2_name'}), on='umpire_id2', how='left') \
                  .merge(match_result, on='match_id', how='left') \
                  .merge(teams.rename(columns={'team_id': 'winner_id', 'team': 'winner_name'}), on='winner_id', how='left') \
                  .merge(player_of_the_match, on='match_id', how='left') \
                  .merge(players.rename(columns={'player_id': 'player_of_the_match_id', 'player': 'pom_name'}), on='player_of_the_match_id', how='left')
            for i, row in merged.iterrows():
                print(f"{row['match_id']} | {row['season']} | {row['date']} | {row['venue']} | "
                    f"{row['team1_name']} | {row['team2_name']} | {row['umpire1_name']} | {row['umpire2_name']} | "
                    f"{row['winner_name']} | {row['pom_name']}")
            print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
        elif choice==6:
            
            player_name = input("Enter the name of the player: ")
            start_time = time.time()
            try:
                player_id = players[players['player'] == player_name]['player_id'].values[0]
                batter_deliveries = delivery[delivery['batter_id'] == player_id]
                runs_scored = batter_deliveries['batsman_runs'].sum()
                matches_batted = batter_deliveries['match_id'].unique()
                bowler_deliveries = delivery[(delivery['bowler_id'] == player_id) & (dismissals['is_wicket'] == 1)]
                wickets_taken = len(bowler_deliveries)
                matches_bowled = bowler_deliveries['match_id'].unique()
                catches = dismissals[(dismissals['is_wicket'] == 1) &
                             (dismissals['dismissal_kind'] == 'caught') &
                             (dismissals['fielder_id'] == player_id)]
                catches_taken = len(catches)
                matches_fielded = catches['match_id'].unique()
                all_matches = set(matches_batted) | set(matches_bowled) | set(matches_fielded)
                print(f"Player Name: {player_name}")
                print(f"Runs Scored: {runs_scored}")
                print(f"Wickets Taken: {wickets_taken}")
                print(f"Catches Taken: {catches_taken}")
                print("Total number of matches played by the player:", len(all_matches))
                print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
            except IndexError:
                 print("Player not found. Please check the name.")
            
        elif choice==7:
            
            player_name = input("Enter the name of the player: ")
            start_time= time.time()
            try:
                player_id = players[players['player'] == player_name]['player_id'].values[0]
                potm_matches = player_of_the_match[player_of_the_match['player_of_the_match_id'] == player_id]
                if potm_matches.empty:
                    print(f"{player_name} has never been Player of the Match.")
                else:
                    merged_df = potm_matches.merge(match, on='match_id').merge(venue, on='venue_id')
                    print(f"Player Name: {player_name}")
                    print("Total number of matches in which the player was Player of the Match:", len(merged_df))
                    print("Player of the Match in the following matches:")
                    for idx, row in merged_df.iterrows():
                        print(f"{idx+1} | {player_name} | {row['date']} | {row['venue']}")
                print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
            except IndexError:
                print("Player not found. Please check the name.")
        elif choice==8:

            
            team1_name=input("Enter the name of the first team: ")
            team2_name=input("Enter the name of the second team: ")
            start_time= time.time()
            team_id_map = dict(zip(teams['team'], teams['team_id']))
            team1_id = team_id_map.get(team1_name)
            team2_id = team_id_map.get(team2_name)
            if team1_id is None or team2_id is None:
                print("One or both team names are invalid.")
            else:
                mask = (
                    ((match_teams['team_id1'] == team1_id) & (match_teams['team_id2'] == team2_id)) |
                    ((match_teams['team_id1'] == team2_id) & (match_teams['team_id2'] == team1_id))
                )
                relevant_matches = match_teams[mask]
                match_ids = relevant_matches['match_id'].unique()
                matches_played = len(match_ids)
                relevant_results = match_result[match_result['match_id'].isin(match_ids)]
                team1_wins = (relevant_results['winner_id'] == team1_id).sum()
                team2_wins = (relevant_results['winner_id'] == team2_id).sum()
                relevant_tosses = toss[toss['match_id'].isin(match_ids)]
                team1_toss_winds = (relevant_tosses['toss_winner'] == team1_id).sum()
                team2_toss_winds = (relevant_tosses['toss_winner'] == team2_id).sum()
                print(f"Head to head stats between {team1_name} and {team2_name}:")
                print(f"Total matches played: {matches_played}")
                print(f"{team1_name} wins: {team1_wins}")
                print(f"{team2_name} wins: {team2_wins}")
                print(f"{team1_name} toss wins: {team1_toss_winds}")
                print(f"{team2_name} toss wins: {team2_toss_winds}")
            end_time = time.time()
            print(f"Execution time: {end_time - start_time:.4f} seconds")
            
        elif choice==9:
            
            team_name = input("Enter the name of the team: ")
            start_time = time.time()
            team_id_row = teams[teams['team'] == team_name]

            if team_id_row.empty:
                print("Invalid team name.")
            else:
                team_id = team_id_row['team_id'].values[0]

                # Filter matches involving the team
                team_matches = match_teams[
                    (match_teams['team_id1'] == team_id) | (match_teams['team_id2'] == team_id)
                ]
                match_ids = team_matches['match_id'].unique()
                matches_played = len(match_ids)

                # Relevant results
                relevant_results = match_result[match_result['match_id'].isin(match_ids)]

                # Count outcomes
                winner_counts = relevant_results['winner_id'].value_counts()
                matches_won = winner_counts.get(team_id, 0)
                matches_lost = len(relevant_results) - matches_won

                # No result and abandoned
                match_result_counts = relevant_results['match_id'].value_counts()
                no_result_ids = set(match_ids) - set(match_result_counts.index)
                matches_no_result = len(no_result_ids)

                abandoned_ids = match_result_counts[match_result_counts > 1].index
                matches_abandoned = len(abandoned_ids)

                # Output
                print(f"Stats for {team_name}:")
                print(f"Total matches played: {matches_played}")
                print(f"Matches won: {matches_won}")
                print(f"Matches lost: {matches_lost}")
                print(f"Matches no result: {matches_no_result}")
                print(f"Matches abandoned: {matches_abandoned}")

            end_time = time.time()
            print(f"Execution time: {end_time - start_time:.4f} seconds")
        elif choice==10:
            
            player_name = input("Enter the name of the player: ")
            start_time = time.time()
            player_row = players[players['player'] == player_name]
            if player_row.empty:
                print("Invalid player name.")
            else:
                player_id = player_row['player_id'].values[0]
                delivery_season = delivery.merge(match[['match_id', 'season']], on='match_id', how='left')
                is_batter = delivery_season['batter_id'] == player_id
                is_bowler = delivery_season['bowler_id'] == player_id
                is_fielder = (
                    (dismissals['is_wicket'] == 1) &
                    (dismissals['dismissal_kind'] == 'caught') &
                    (dismissals['fielder_id'] == player_id)
                )
                batter_rows = delivery_season[is_batter][['season', 'batting_team_id']].drop_duplicates('season')
                bowler_rows = delivery_season[is_bowler][['season', 'bowling_team_id']].drop_duplicates('season')
                fielder_rows = delivery_season[is_fielder][['season', 'bowling_team_id']].drop_duplicates('season')
                team_history = {}
                for _, row in batter_rows.iterrows():
                    team_history[row['season']] = row['batting_team_id']
                for _, row in bowler_rows.iterrows():
                    team_history.setdefault(row['season'], row['bowling_team_id'])
                for _, row in fielder_rows.iterrows():
                    team_history.setdefault(row['season'], row['bowling_team_id'])
                print(f"Player Name: {player_name}")
                print("Team history:")
                for season in sorted(team_history.keys()):
                    team_id = team_history[season]
                    team_name_row = teams[teams['team_id'] == team_id]['team']
                    team_name = team_name_row.values[0] if not team_name_row.empty else "Not Played"
                    print(f"Season {season}: {team_name}")
                end_time = time.time()
                print(f"Execution time: {end_time - start_time:.4f} seconds")
            
        elif choice==11:
            
            venue_name=input("Enter the name of the venue: ")
            start_time = time.time()
            venue_row = venue[venue['venue'] == venue_name]
            if venue_row.empty:
                print("Invalid venue name.")
            else:
                venue_id = venue_row['venue_id'].values[0]
                venue_matches = match[match['venue_id'] == venue_id]
                if venue_matches.empty:
                    print("No matches played at this venue.")
                else:
                    venue_match_results = venue_matches.merge(match_result, on='match_id', how='left')
                    venue_match_results = venue_match_results.merge(toss, on='match_id', how='left')
                    # venue_match_results = venue_match_results[venue_match_results['winner_id']]
                    matches_played = len(venue_match_results)
                    first_bat_wins=0
                    second_bat_wins=0
                    matches_abandoned=0
                    for _, row in venue_match_results.iterrows():
                        
                        winner = row['winner_id']
                        toss_winner = row['toss_winner']
                        toss_decision = row['toss_decision']
                        if pd.isna(winner):
                            matches_abandoned += 1
                            continue
                        if toss_decision == 'bat':
                            if winner == toss_winner:
                                first_bat_wins += 1
                            else:
                                second_bat_wins += 1
                        elif toss_decision == 'field':
                            if winner == toss_winner:
                                second_bat_wins += 1
                            else:
                                first_bat_wins += 1
                    print(f"Venue Name: {venue_name}")
                    print("Stats:")
                    print(f"Total matches played: {matches_played}")
                    print(f"Matches won while batting first: {first_bat_wins}")
                    print(f"Matches won while batting second: {second_bat_wins}")
                    print(f"Matches abandoned: {matches_abandoned}")

            end_time = time.time()
            print(f"Execution time: {end_time - start_time:.4f} seconds")
                        
        elif choice==12:
            
            venue1=input("Enter the name of the venue: ")
            start_time = time.time()
            venue_row = venue[venue['venue'] == venue1]
            if venue_row.empty:
                print("Invalid venue name.")
            else:
                venue_id = venue_row['venue_id'].values[0]
                venue_matches = match[match['venue_id'] == venue_id]
                if venue_matches.empty:
                    print("No matches played in this venue.")
                else:
                    first_innings = delivery[
                        (delivery['match_id'].isin(venue_matches['match_id'])) &
                        (delivery['inning'] == 1)
                    ]
                    total_runs = first_innings['total_runs'].sum()
                    matches_played = venue_matches.shape[0]
                    average_runs = total_runs / matches_played if matches_played > 0 else 0
                    print(f"Venue Name: {venue1}")
                    print("Stats:")
                    print(f"Total matches played: {matches_played}")
                    print(f"Average first innings score: {average_runs:.2f}")
                end_time = time.time()
                print(f"Execution time: {end_time - start_time:.4f} seconds")
        elif choice==13:
            start_time = time.time()
            delivery_season = delivery.merge(match[['match_id', 'season']], on='match_id', how='left')
            delivery_season['four'] = (delivery_season['batsman_runs'] == 4).astype(int)
            delivery_season['six'] = (delivery_season['batsman_runs'] == 6).astype(int)
            season_totals = delivery_season.groupby('season')[['four', 'six']].sum().reset_index()
            print("Total number of 4s and 6s per season:")
            for _, row in season_totals.iterrows():
                print(f"Season {(row['season'])}: 4s = {row['four']}, 6s = {row['six']}")
            end_time = time.time()
            print(f"\nExecution time: {end_time - start_time:.4f} seconds")
        elif choice==14:
            
            team_name = input("Enter the name of the team: ")
            start_time = time.time()
            team_id = teams[teams['team'] == team_name]['team_id'].values[0]
            delivery_season = delivery.merge(match[['match_id', 'season']], on='match_id', how='left')
            powerplay = delivery_season[(delivery_season['batting_team_id'] == team_id) & (delivery_season['over'] < 6)]
            runs_by_season = powerplay.groupby('season')['total_runs'].sum().reset_index()
            matches_by_season = powerplay[['season', 'match_id']].drop_duplicates().groupby('season').size().reset_index(name='matches')
            stats = runs_by_season.merge(matches_by_season, on='season')
            stats['avg_powerplay'] = stats['total_runs'] / stats['matches']
            print("Average powerplay score for each season:")
            for _, row in stats.iterrows():
                 print(f"Season {(row['season'])}: Average powerplay score = {row['avg_powerplay']:.2f}")
            end_time = time.time()
            print(f"\nExecution time: {end_time - start_time:.4f} seconds")
        elif choice==15:
            
            team_name = input("Enter the name of the team: ")
            start_time = time.time()
            team_id = teams[teams['team'] == team_name]['team_id'].values[0]
            delivery_season = delivery.merge(match[['match_id', 'season']], on='match_id', how='left')
            delivery_season['is_wicket'] = dismissals['is_wicket']
            powerplay = delivery_season[
                (delivery_season['bowling_team_id'] == team_id) &
                (delivery_season['over'] < 6) &
                (delivery_season['is_wicket'] == 1)
            ]
            wickets_by_season = powerplay.groupby('season').size().reset_index(name='wickets')
            matches_by_season = powerplay[['season', 'match_id']].drop_duplicates().groupby('season').size().reset_index(name='matches')
            stats = wickets_by_season.merge(matches_by_season, on='season')
            stats['avg_powerplay'] = stats['wickets'] / stats['matches']
            print("Average wickets taken in powerplay for each season:")
            for _, row in stats.iterrows():
                 print(f"Season {(row['season'])}: Average wickets taken = {row['avg_powerplay']:.2f}")
            end_time = time.time()
            print(f"\nExecution time: {end_time - start_time:.4f} seconds")
        elif choice==16:
            start_time = time.time()
            player_stats = defaultdict(lambda: defaultdict(lambda: {
                'sixes': 0, 'fours': 0, 'dot_balls': 0, 'wickets': 0, 'runs': 0
            }))
            winner_ipl={}
            # season1=0
            runner_up_ipl={}
            match_season = dict(zip(match['match_id'], match['season']))
            match_type=dict(zip(match['match_id'], match['match_type']))
            match_result_dict = dict(zip(match_result['match_id'], match_result['winner_id']))
            match_teams_dict = match_teams.set_index('match_id')[['team_id1', 'team_id2']].to_dict(orient='index')
            team_names = teams.set_index('team_id')['team'].to_dict()
            player_names = players.set_index('player_id')['player'].to_dict()
            is_wicket_dict = dismissals['is_wicket'].to_dict()
            for idx, row in delivery.iterrows():
                match_id = row['match_id']
                season = match_season.get(match_id)
                batter_id = row['batter_id']
                type= match_type.get(match_id)
                bowler_id = row['bowler_id']
                runs = row['batsman_runs']
                total_runs = row['total_runs']
                delivery_id = idx
                if type=='Final' and season not in winner_ipl:
                    winner_id = match_result_dict.get(match_id)
                    team1_id = match_teams_dict.get(match_id, {}).get('team_id1')
                    team2_id = match_teams_dict.get(match_id, {}).get('team_id2')
                    if winner_id:
                        winner_ipl[season] = team_names.get(winner_id, "Unknown")
                        runner_up_id = team2_id if winner_id == team1_id else team1_id
                        runner_up_ipl[season] = team_names.get(runner_up_id, "Unknown")
                stats = player_stats[batter_id][season]
                stats['runs'] += runs
                if runs == 4:
                    stats['fours'] += 1
                elif runs == 6:
                    stats['sixes'] += 1
                stats = player_stats[bowler_id][season]
                if is_wicket_dict.get(idx, 0) == 1:
                    stats['wickets'] += 1
                elif total_runs == 0:
                    stats['dot_balls'] += 1
            orange_cap = defaultdict(lambda: (None, 0))   # player_id, runs
            purple_cap = defaultdict(lambda: (None, 0))   # player_id, wickets
            most_sixes = defaultdict(lambda: (None, 0))   # player_id, sixes
            most_fours = defaultdict(lambda: (None, 0))   # player_id, fours
            for player_id, seasons in player_stats.items():
                for season, stats in seasons.items():
                    if stats['runs'] > orange_cap[season][1]:
                        orange_cap[season] = (player_id, stats['runs'])
                    if stats['wickets'] > purple_cap[season][1]:
                        purple_cap[season] = (player_id, stats['wickets'])
                    if stats['sixes'] > most_sixes[season][1]:
                        most_sixes[season] = (player_id, stats['sixes'])
                    if stats['fours'] > most_fours[season][1]:
                        most_fours[season] = (player_id, stats['fours'])           
            
            print("Season Awards:")
            for season in sorted(orange_cap.keys()):
                orange_player = players[players['player_id'] == orange_cap[season][0]]['player'].values[0]
                purple_player = players[players['player_id'] == purple_cap[season][0]]['player'].values[0]
                sixes_player = players[players['player_id'] == most_sixes[season][0]]['player'].values[0]
                fours_player = players[players['player_id'] == most_fours[season][0]]['player'].values[0]
                print(f"\n Season {season}:")
                print(f" Orange Cap: {orange_player} ({orange_cap[season][1]} runs)")
                print(f" Purple Cap: {purple_player} ({purple_cap[season][1]} wickets)")
                print(f" Most Sixes: {sixes_player} ({most_sixes[season][1]} sixes)")
                print(f" Most Fours: {fours_player} ({most_fours[season][1]} fours)")
                print(f" Winner: {winner_ipl[season]}")
                print(f" Runner Up: {runner_up_ipl[season]}")
            end_time = time.time()
            print(f"\nExecution time: {end_time - start_time:.4f} seconds")
        elif choice==17:
            
            umpire_name = input("Enter the name of the umpire: ").strip()
            start_time= time.time()
            umpire_row = umpire[umpire['umpire'].str.lower() == umpire_name.lower()]
            if umpire_row.empty:
                print(f"Umpire '{umpire_name}' not found.")
            else:
                umpire_id = umpire_row['umpire_id'].values[0]
                matches_judged = (umpire_match['umpire_id1'] == umpire_id).sum()
                matches_judged+=(umpire_match['umpire_id2'] == umpire_id).sum()
                print(f"Umpire Name: {umpire_name}")
                print("Total number of matches judged by the umpire:", matches_judged)
                print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
        elif choice==18:
            start_time= time.time()
            print("Calculating most 50s and 100s per season...")
            delivery_with_season = delivery.merge(match[['match_id', 'season']], on='match_id')
            match_runs = delivery_with_season.groupby(['batter_id', 'season', 'match_id'])['batsman_runs'].sum().reset_index()
            match_runs['fifty'] = match_runs['batsman_runs'].between(50, 99)
            match_runs['hundred'] = match_runs['batsman_runs'] >= 100
            fifties_count = match_runs.groupby(['batter_id', 'season'])['fifty'].sum().reset_index()
            hundreds_count = match_runs.groupby(['batter_id', 'season'])['hundred'].sum().reset_index()
            stats = fifties_count.merge(hundreds_count, on=['batter_id', 'season'])
            most_fifties = stats.loc[stats.groupby('season')['fifty'].idxmax()]
            most_hundreds = stats.loc[stats.groupby('season')['hundred'].idxmax()]
            print("Most Fifties and Hundreds per season:")
            for season in sorted(stats['season'].unique()):
                fifties_row = most_fifties[most_fifties['season'] == season]
                hundreds_row = most_hundreds[most_hundreds['season'] == season]
                fifties_player = players[players['player_id'] == fifties_row['batter_id'].values[0]]['player'].values[0]
                hundreds_player = players[players['player_id'] == hundreds_row['batter_id'].values[0]]['player'].values[0]
                print(f"\n Season {season}:")
                print(f" Most Fifties: {fifties_player} ({fifties_row['fifty'].values[0]} fifties)")
                print(f" Most Hundreds: {hundreds_player} ({hundreds_row['hundred'].values[0]} hundreds)")
            print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
                                
        elif choice==19:
            start_time=time.time()
            delivery_with_season = delivery.merge(match[['match_id', 'season']], on='match_id')
            delivery_with_season['is_wicket'] = dismissals['is_wicket']
            wickets_per_match = delivery_with_season[delivery_with_season['is_wicket'] == 1] \
                .groupby(['bowler_id', 'season', 'match_id']).size().reset_index(name='wicket_count')
            wickets_per_match = wickets_per_match[wickets_per_match['wicket_count'] >= 5]
            five_wicket_hauls = wickets_per_match.groupby(['bowler_id', 'season']).size().reset_index(name='five_wicket_hauls')
            most_five_wickets = five_wicket_hauls.loc[five_wicket_hauls.groupby('season')['five_wicket_hauls'].idxmax()]
            print("Most 5-Wicket Takers per Season:")
            for _, row in most_five_wickets.iterrows():
                player_name = players[players['player_id'] == row['bowler_id']]['player'].values[0]
                print(f"\n Season {row['season']}:")
                print(f" Most 5-Wicket Taker: {player_name} ({row['five_wicket_hauls']} times)") 
            print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")       
        elif choice==20:
            
            print("Bowler vs Batter Comparison")
            bowler_name = input("Enter the name of the bowler: ").strip()
            batter_name = input("Enter the name of the batter: ").strip()
            start_time=time.time()
            bowler_row = players[players['player'].str.lower() == bowler_name.lower()]
            batter_row = players[players['player'].str.lower() == batter_name.lower()]
            if bowler_row.empty or batter_row.empty:
                print(" Invalid bowler or batter name.")
            else:
                bowler_id = bowler_row['player_id'].values[0]
                batter_id = batter_row['player_id'].values[0]
                vs_df = delivery[(delivery['bowler_id'] == bowler_id) & (delivery['batter_id'] == batter_id)]
                if vs_df.empty:
                    print(" No deliveries found between this bowler and batter.")
                else:
                    vs_df = vs_df.copy()
                    vs_df['is_wicket'] = dismissals.loc[vs_df.index, 'is_wicket']
                    total_balls = len(vs_df)
                    total_runs = vs_df['batsman_runs'].sum()
                    dot_balls = (vs_df['total_runs'] == 0).sum()
                    wickets = vs_df['is_wicket'].sum()
                    print(f"\n Head-to-Head: {bowler_name} vs {batter_name}")
                    print(f" Balls Bowled: {total_balls}")
                    print(f" Runs Scored: {total_runs}")
                    print(f" Wickets Taken: {wickets}")
                    print(f" Dot Balls: {dot_balls}")
                    print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")                       
        elif choice==21:
            
            old_team_name = input("Enter the old name of the team: ").strip()
            new_team_name = input("Enter the new name of the team: ").strip()
            start_time= time.time()

            # Check if input is empty
            if not old_team_name or not new_team_name:
                print("Team names cannot be empty.")
            else:
                team_id = teams[teams['team'].str.lower() == old_team_name.lower()]['team_id'].values

                if len(team_id) == 0:
                    print(f"Team '{old_team_name}' not found.")
                else:
                    team_id = team_id[0]
                    teams.loc[teams['team_id'] == team_id, 'team'] = new_team_name
                    teams.to_csv('normalized csvs/teams.csv', index=False)
                    print(f"Team name updated successfully from '{old_team_name}' to '{new_team_name}'.")
                    print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
            # print("To implement")
        elif choice==22:
            
            old_venue_name = input("Enter the old name of the venue: ").strip()
            new_venue_name = input("Enter the new name of the venue: ").strip()
            start_time= time.time()

            # Check if input is empty
            if not old_venue_name or not new_venue_name:
                print("Venue names cannot be empty.")
            else:
                venue_id = venue[venue['venue'].str.lower() == old_venue_name.lower()]['venue_id'].values

                if len(venue_id) == 0:
                    print(f"Venue '{old_venue_name}' not found.")
                else:
                    venue_id = venue_id[0]
                    venue.loc[venue['venue_id'] == venue_id, 'venue'] = new_venue_name
                    venue.to_csv('normalized csvs/venue.csv', index=False)
                    print(f"Venue name updated successfully from '{old_venue_name}' to '{new_venue_name}'.")
                    print(f"\n Time taken: {time.time() - start_time:.4f} seconds\n")
       

        
        elif choice==23:
            print("Exiting the program...")
            time.sleep(1)
            print("Thank you for using the IPL Data Analysis Program!")
            time.sleep(1)
            print("Goodbye!")
            break
        else:
            print("Invalid choice! Please try again.")
            time.sleep(1)
            



                

        
        
        



            
        time.sleep(1)
        
        # break