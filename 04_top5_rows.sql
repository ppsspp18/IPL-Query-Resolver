-- ==== 04_top5_rows.sql ====
USE ipl_normalized;

-- Master Tables
SELECT '--- teams ---' AS table_name;
SELECT * FROM teams LIMIT 5;

SELECT '--- venues ---' AS table_name;
SELECT * FROM venues LIMIT 5;

SELECT '--- umpires ---' AS table_name;
SELECT * FROM umpires LIMIT 5;

SELECT '--- players ---' AS table_name;
SELECT * FROM players LIMIT 5;

-- Match Metadata Tables
SELECT '--- match_details ---' AS table_name;
SELECT * FROM match_details LIMIT 5;

SELECT '--- match_result ---' AS table_name;
SELECT * FROM match_result LIMIT 5;

SELECT '--- match_toss ---' AS table_name;
SELECT * FROM match_toss LIMIT 5;

SELECT '--- match_teams ---' AS table_name;
SELECT * FROM match_teams LIMIT 5;

SELECT '--- match_umpire ---' AS table_name;
SELECT * FROM match_umpire LIMIT 5;

-- Ball-by-ball Tables
SELECT '--- delivery ---' AS table_name;
SELECT * FROM delivery LIMIT 5;

SELECT '--- dismissal ---' AS table_name;
SELECT * FROM dismissal LIMIT 5;