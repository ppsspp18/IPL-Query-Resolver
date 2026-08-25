USE ipl_normalized;

-- --------------------------------------------------
-- 10. Create delivery table
-- --------------------------------------------------
CREATE TABLE delivery AS
SELECT 
    i.match_id,
    i.innings,
    i.`over`,
    i.ball,
    bt.team_id AS batting_team_id,
    bot.team_id AS bowling_team_id,
    btr.player_id AS batter_id,
    blr.player_id AS bowler_id,
    nst.player_id AS non_striker_id,
    i.runs_batter,
    i.runs_extras,
    i.runs_total
FROM ipl_raw i
LEFT JOIN teams bt ON i.batting_team = bt.team_name
LEFT JOIN teams bot ON i.bowling_team = bot.team_name
LEFT JOIN players btr ON i.batter = btr.player_name
LEFT JOIN players blr ON i.bowler = blr.player_name
LEFT JOIN players nst ON i.non_striker = nst.player_name;

-- --------------------------------------------------
-- 11. Create dismissal table
-- --------------------------------------------------
-- Extract first fielder from tuple format e.g. "('BB McCullum', 'SC Ganguly')"
CREATE TABLE dismissal AS
SELECT 
    i.match_id,
    i.innings,
    i.`over`,
    i.ball,
    po.player_id AS player_out_id,
    i.wicket_kind,
    f.player_id AS fielder_id
FROM ipl_raw i
LEFT JOIN players po ON i.player_out = po.player_name
LEFT JOIN players f ON TRIM(REPLACE(REPLACE(REPLACE(
    SUBSTRING_INDEX(i.fielders, ',', 1), 
    '(', ''), ')', ''), '''', '')) = f.player_name
WHERE i.wicket_kind IS NOT NULL 
  AND TRIM(i.wicket_kind) != ''
  AND i.wicket_kind != 'NA';
