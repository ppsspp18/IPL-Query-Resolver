"""
These are the column names in our dataset : 
match_id,date,match_type,event_name,innings,batting_team,bowling_team,over,
ball,ball_no,batter,bat_pos,runs_batter,balls_faced,bowler,valid_ball,runs_extras,
runs_total,runs_bowler,runs_not_boundary,extra_type,non_striker,non_striker_pos,
wicket_kind,player_out,fielders,runs_target,review_batter,team_reviewed,
review_decision,umpire,umpires_call,player_of_match,match_won_by,win_outcome,
toss_winner,toss_decision,venue,city,day,month,year,season,gender,team_type,
superover_winner,result_type,method,balls_per_over,overs,event_match_no,
stage,match_number,team_runs,team_balls,team_wicket,new_batter,power_surge_start,
batter_runs,batter_balls,bowler_wicket,batting_partners,next_batter,striker_out


teams.cvs : team_id team name
venues.csv : venue id, venue name and venue city
players.csv : player_id, player name
umpires.csv : umpire_id, umpire name
"""

import pandas as pd

df = pd.read_csv('IPL.csv')
df.head(1).to_csv('first_rows.csv', index=False)
