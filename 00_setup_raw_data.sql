-- 1. Create the database and switch to it
CREATE DATABASE IF NOT EXISTS ipl_normalized;
USE ipl_normalized;

-- 2. Drop the raw table if it already exists
DROP TABLE IF EXISTS ipl_raw;

-- 3. Create the raw table structure
CREATE TABLE ipl_raw (
    match_id INT, season VARCHAR(10), date DATE, venue VARCHAR(255), city VARCHAR(100), 
    stage VARCHAR(50), toss_winner VARCHAR(100), toss_decision VARCHAR(50), 
    match_won_by VARCHAR(100), superover_winner VARCHAR(100), win_outcome VARCHAR(100), 
    runs_target INT, overs INT, method VARCHAR(50), player_of_match VARCHAR(150), 
    umpire VARCHAR(150), innings INT, `over` INT, ball INT, batting_team VARCHAR(100), 
    bowling_team VARCHAR(100), batter VARCHAR(150), bowler VARCHAR(150), 
    non_striker VARCHAR(150), runs_batter INT, runs_extras INT, runs_total INT, 
    player_out VARCHAR(150), wicket_kind VARCHAR(50), fielders VARCHAR(255)
);

-- 4. Load the data
--    CSV has an unnamed index column as field 1; column order differs from raw table.
--    We use @dummy to skip the index and map remaining CSV columns to the correct table columns.
LOAD DATA LOCAL INFILE '/home/ppsspp18/projects/IPL-Query-Resolver/IPL.csv'
INTO TABLE ipl_raw
FIELDS TERMINATED BY ',' 
ENCLOSED BY '"'
LINES TERMINATED BY '\n' 
IGNORE 1 ROWS
(
  @dummy,
  match_id, date, @match_type, @event_name,
  innings, batting_team, bowling_team, `over`, ball, @ball_no,
  batter, @bat_pos, runs_batter, @balls_faced,
  bowler, @valid_ball, runs_extras, runs_total,
  @runs_bowler, @runs_not_boundary, @extra_type,
  non_striker, @non_striker_pos, wicket_kind, player_out, fielders,
  @runs_target, @review_batter, @team_reviewed, @review_decision,
  umpire, @umpires_call, player_of_match, match_won_by, win_outcome,
  toss_winner, toss_decision, venue, city,
  @day, @month, @year, season, @gender, @team_type,
  superover_winner, @result_type, method, @balls_per_over, @overs,
  @event_match_no, stage, @match_number,
  @team_runs, @team_balls, @team_wicket, @new_batter,
  @power_surge_start, @batter_runs, @batter_balls, @bowler_wicket,
  @batting_partners, @next_batter, @striker_out
)
SET
  runs_target = NULLIF(@runs_target, ''),
  overs = NULLIF(@overs, '');
