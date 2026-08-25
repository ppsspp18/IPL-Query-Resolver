USE ipl_normalized;

-- --------------------------------------------------
-- 1. Create Teams Master Table
-- --------------------------------------------------
CREATE TABLE teams (
    team_id INT AUTO_INCREMENT PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL UNIQUE
);

INSERT INTO teams (team_name)
SELECT DISTINCT team_name FROM (
    SELECT batting_team AS team_name FROM ipl_raw WHERE batting_team IS NOT NULL
    UNION 
    SELECT bowling_team AS team_name FROM ipl_raw WHERE bowling_team IS NOT NULL
) t;

-- --------------------------------------------------
-- 2. Create Venues Master Table
-- --------------------------------------------------
CREATE TABLE venues (
    venue_id INT AUTO_INCREMENT PRIMARY KEY,
    venue_name VARCHAR(255) NOT NULL,
    venue_city VARCHAR(100)
);

INSERT INTO venues (venue_name, venue_city)
SELECT DISTINCT venue, city 
FROM ipl_raw 
WHERE venue IS NOT NULL AND venue != '';

-- --------------------------------------------------
-- 3. Create Umpires Master Table
-- --------------------------------------------------
CREATE TABLE umpires (
    umpire_id INT AUTO_INCREMENT PRIMARY KEY,
    umpire_name VARCHAR(150) NOT NULL UNIQUE
);

INSERT INTO umpires (umpire_name)
SELECT DISTINCT umpire 
FROM ipl_raw 
WHERE umpire IS NOT NULL AND TRIM(umpire) != '' AND umpire != 'False';

-- --------------------------------------------------
-- 4. Create Players Master Table
-- --------------------------------------------------
CREATE TABLE players (
    player_id INT AUTO_INCREMENT PRIMARY KEY,
    player_name VARCHAR(150) NOT NULL UNIQUE
);

-- Split comma-separated fielders into individual player names
-- e.g. "('BB McCullum', 'SC Ganguly')" -> "BB McCullum" and "SC Ganguly"
CREATE TEMPORARY TABLE tmp_split_fielders AS
WITH RECURSIVE clean_fielders AS (
    SELECT REPLACE(REPLACE(REPLACE(fielders, '(', ''), ')', ''), '''', '') AS fielders_clean
    FROM ipl_raw 
    WHERE fielders IS NOT NULL AND TRIM(fielders) != ''
),
split_fielders AS (
    SELECT 
        TRIM(SUBSTRING_INDEX(fielders_clean, ',', 1)) AS player,
        CASE 
            WHEN LOCATE(',', fielders_clean) > 0 
            THEN TRIM(SUBSTRING(fielders_clean, LOCATE(',', fielders_clean) + 1))
            ELSE NULL 
        END AS remainder
    FROM clean_fielders
    UNION ALL
    SELECT 
        TRIM(SUBSTRING_INDEX(remainder, ',', 1)),
        CASE 
            WHEN LOCATE(',', remainder) > 0 
            THEN TRIM(SUBSTRING(remainder, LOCATE(',', remainder) + 1))
            ELSE NULL 
        END
    FROM split_fielders WHERE remainder IS NOT NULL AND remainder != ''
)
SELECT player FROM split_fielders WHERE player IS NOT NULL AND player != '';

INSERT IGNORE INTO players (player_name)
SELECT DISTINCT player FROM (
    SELECT batter AS player FROM ipl_raw WHERE batter IS NOT NULL AND batter != ''
    UNION SELECT bowler FROM ipl_raw WHERE bowler IS NOT NULL AND bowler != ''
    UNION SELECT player_of_match FROM ipl_raw WHERE player_of_match IS NOT NULL AND player_of_match != ''
    UNION SELECT player_out FROM ipl_raw WHERE player_out IS NOT NULL AND player_out != ''
    UNION SELECT player FROM tmp_split_fielders WHERE player IS NOT NULL AND player != ''
) all_players;

DROP TEMPORARY TABLE tmp_split_fielders;
