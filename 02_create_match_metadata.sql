USE ipl_normalized;

-- --------------------------------------------------
-- 5. Create match_details table
-- --------------------------------------------------
CREATE TABLE match_details AS 
WITH first_ball AS (
    SELECT *, 
           ROW_NUMBER() OVER(PARTITION BY match_id ORDER BY `over`, `ball`) as rn
    FROM ipl_raw
)
SELECT 
    f.match_id,
    f.season,
    f.date,
    v.venue_id,
    COALESCE(NULLIF(NULLIF(NULLIF(TRIM(f.stage), ''), 'Unknown'), 'NA'), 'League') AS match_type
FROM first_ball f
LEFT JOIN venues v ON f.venue = v.venue_name AND f.city = v.venue_city
WHERE f.rn = 1;

-- --------------------------------------------------
-- 6. Create match_result table
-- --------------------------------------------------
CREATE TABLE match_result AS
WITH first_ball AS (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY match_id ORDER BY `over`, `ball`) as rn FROM ipl_raw
)
SELECT 
    f.match_id,
    t.team_id AS winner_id,
    p.player_id AS player_of_match_id,
    
    CASE 
        WHEN LOWER(TRIM(f.win_outcome)) LIKE '%run%' THEN 'run'
        WHEN LOWER(TRIM(f.win_outcome)) LIKE '%wicket%' THEN 'wicket'
        ELSE 'super'
    END AS result,
    
    CAST(COALESCE(REGEXP_SUBSTR(f.win_outcome, '[0-9]+'), '0') AS UNSIGNED) AS result_margin,
    
    f.runs_target AS target_run,
    f.overs AS target_over,
    CASE 
        WHEN f.superover_winner IS NULL OR TRIM(f.superover_winner) IN ('NA', '') THEN 'N' 
        ELSE 'Y' 
    END AS super_over,
    NULLIF(NULLIF(TRIM(f.method), ''), 'NA') AS method
FROM first_ball f
LEFT JOIN teams t ON COALESCE(
    NULLIF(NULLIF(NULLIF(TRIM(f.match_won_by), ''), 'Unknown'), 'NA'),
    NULLIF(NULLIF(f.superover_winner, ''), 'NA')
) = t.team_name
LEFT JOIN players p ON NULLIF(NULLIF(TRIM(f.player_of_match), ''), 'NA') = p.player_name
WHERE f.rn = 1;

-- --------------------------------------------------
-- 7. Create match_toss table
-- --------------------------------------------------
CREATE TABLE match_toss AS
WITH first_ball AS (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY match_id ORDER BY `over`, `ball`) as rn FROM ipl_raw
)
SELECT 
    f.match_id,
    t.team_id AS toss_winner_id,
    COALESCE(NULLIF(NULLIF(TRIM(f.toss_decision), ''), 'NA'), 'Unknown') AS toss_decision
FROM first_ball f
LEFT JOIN teams t ON NULLIF(NULLIF(TRIM(f.toss_winner), ''), 'NA') = t.team_name
WHERE f.rn = 1;

-- --------------------------------------------------
-- 8. Create match_teams table
-- --------------------------------------------------
CREATE TABLE match_teams AS
WITH match_all_teams AS (
    SELECT match_id, batting_team AS team_name FROM ipl_raw WHERE batting_team IS NOT NULL AND batting_team != ''
    UNION 
    SELECT match_id, bowling_team AS team_name FROM ipl_raw WHERE bowling_team IS NOT NULL AND bowling_team != ''
),
numbered_teams AS (
    SELECT match_id, team_name, 
           ROW_NUMBER() OVER(PARTITION BY match_id ORDER BY team_name) as team_rank
    FROM match_all_teams
)
SELECT 
    t1.match_id,
    tm1.team_id AS team1_id,
    tm2.team_id AS team2_id
FROM (SELECT match_id, team_name FROM numbered_teams WHERE team_rank = 1) t1
JOIN (SELECT match_id, team_name FROM numbered_teams WHERE team_rank = 2) t2 ON t1.match_id = t2.match_id
LEFT JOIN teams tm1 ON t1.team_name = tm1.team_name
LEFT JOIN teams tm2 ON t2.team_name = tm2.team_name;

-- --------------------------------------------------
-- 9. Create match_umpire table
-- --------------------------------------------------
CREATE TABLE match_umpire AS
SELECT DISTINCT 
    i.match_id, 
    u.umpire_id
FROM ipl_raw i
JOIN umpires u ON i.umpire = u.umpire_name
WHERE i.umpire IS NOT NULL AND TRIM(i.umpire) != '' AND i.umpire != 'False'
ORDER BY i.match_id, u.umpire_id;
