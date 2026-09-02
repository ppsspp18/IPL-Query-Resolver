"""Benchmark harness for the Text-to-SQL pipeline.

Runs a curated suite of 33 complex natural-language queries against the
schema-aware Text-to-SQL engine and reports system accuracy by comparing the
generated query's result set against a hand-written canonical SQL answer.

Usage:
    python benchmark.py            # full report + JSON export
    python benchmark.py --json     # JSON only (report.json)
    python benchmark.py --case 5   # run a single case
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

from text2sql import INTENT_META, execute_sql, process_question

# --------------------------------------------------------------------------- #
# Benchmark cases: natural-language question -> canonical SQL answer.
# --------------------------------------------------------------------------- #
CASES: list[dict] = [
    {
        "id": 1,
        "category": "player",
        "intent": "player_career_batting",
        "question": "What are the career batting stats of Virat Kohli?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches,
                   SUM(d.runs_batter) AS Runs, COUNT(d.batter_id) AS Balls_Faced,
                   SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS Fours,
                   SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS Sixes,
                   ROUND(SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(d.batter_id), 0), 2) AS Strike_Rate
            FROM players p
            LEFT JOIN delivery d ON p.player_id = d.batter_id
            WHERE p.player_name = 'V Kohli'
            GROUP BY p.player_id, p.player_name
        """,
    },
    {
        "id": 2,
        "category": "player",
        "intent": "player_career_bowling",
        "question": "How many wickets has Jasprit Bumrah taken in his career?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches,
                   COUNT(d.bowler_id) AS Balls_Bowled,
                   ROUND(COUNT(d.bowler_id) / 6.0, 1) AS Overs,
                   SUM(d.runs_total) AS Runs_Conceded,
                   SUM(CASE WHEN ds.player_out_id IS NOT NULL
                             AND ds.wicket_kind NOT IN ('run out', 'retired hurt')
                            THEN 1 ELSE 0 END) AS Wickets,
                   ROUND(SUM(d.runs_total) * 1.0 / NULLIF(SUM(CASE WHEN ds.player_out_id IS NOT NULL
                               AND ds.wicket_kind NOT IN ('run out', 'retired hurt')
                               THEN 1 ELSE 0 END), 0), 2) AS Bowling_Average,
                   ROUND(SUM(d.runs_total) * 6.0 / NULLIF(COUNT(d.bowler_id), 0), 2) AS Economy
            FROM players p
            LEFT JOIN delivery d ON p.player_id = d.bowler_id
            LEFT JOIN dismissal ds ON d.match_id = ds.match_id AND d.innings = ds.innings
                AND d.`over` = ds.`over` AND d.ball = ds.ball
            WHERE p.player_name = 'JJ Bumrah'
            GROUP BY p.player_id, p.player_name
        """,
    },
    {
        "id": 3,
        "category": "player",
        "intent": "player_motm",
        "question": "How many times was MS Dhoni the Man of the Match?",
        "expected_sql": """
            SELECT COUNT(*) AS Man_of_the_Match_Awards
            FROM match_result mr
            JOIN players p ON mr.player_of_match_id = p.player_id
            WHERE p.player_name = 'MS Dhoni'
        """,
    },
    {
        "id": 4,
        "category": "player",
        "intent": "player_team_history",
        "question": "Which team did Rohit Sharma play for in each season?",
        "expected_sql": """
            SELECT md.season AS Season, bt.team_name AS Team, COUNT(DISTINCT d.match_id) AS Matches_Played
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            JOIN teams bt ON d.batting_team_id = bt.team_id
            JOIN players p ON d.batter_id = p.player_id
            WHERE p.player_name = 'RG Sharma'
            GROUP BY md.season, bt.team_name
            ORDER BY md.season, bt.team_name
        """,
    },
    {
        "id": 5,
        "category": "player",
        "intent": "player_boundaries",
        "question": "How many sixes did Virat Kohli hit against Mumbai Indians?",
        "expected_sql": """
            SELECT p.player_name AS Player, md.season AS Season, COUNT(*) AS Boundaries
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.batter_id = p.player_id
            WHERE p.player_name = 'V Kohli' AND d.runs_batter = 6
              AND d.bowling_team_id = (SELECT team_id FROM teams WHERE team_name = 'Mumbai Indians')
            GROUP BY p.player_name, md.season
            ORDER BY md.season
        """,
    },
    {
        "id": 6,
        "category": "player",
        "intent": "player_best_season",
        "question": "Which was Virat Kohli's best batting season?",
        "expected_sql": """
            SELECT md.season AS Season, SUM(d.runs_batter) AS Runs
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.batter_id = p.player_id
            WHERE p.player_name = 'V Kohli'
            GROUP BY md.season
            ORDER BY Runs DESC, Season
            LIMIT 1
        """,
    },
    {
        "id": 7,
        "category": "player",
        "intent": "player_sr_avg",
        "question": "What is Virat Kohli's strike rate and average in each season?",
        "expected_sql": """
            WITH bat AS (
                SELECT md.season, d.batter_id,
                       SUM(d.runs_batter) AS runs, COUNT(d.batter_id) AS balls,
                       SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS fours,
                       SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
                FROM delivery d JOIN match_details md ON d.match_id = md.match_id
                WHERE d.batter_id = (SELECT player_id FROM players WHERE player_name = 'V Kohli')
                GROUP BY md.season, d.batter_id
            ),
            outs AS (
                SELECT md.season, ds.player_out_id, COUNT(DISTINCT ds.key) AS dismissals
                FROM (SELECT match_id, innings, `over`, ball, player_out_id,
                             CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                      FROM dismissal) ds
                JOIN match_details md ON ds.match_id = md.match_id
                WHERE ds.player_out_id = (SELECT player_id FROM players WHERE player_name = 'V Kohli')
                GROUP BY md.season, ds.player_out_id
            )
            SELECT b.season AS Season, b.runs AS Runs, b.balls AS Balls,
                   b.fours AS Fours, b.sixes AS Sixes,
                   ROUND(b.runs * 100.0 / NULLIF(b.balls, 0), 2) AS Strike_Rate,
                   ROUND(b.runs * 1.0 / NULLIF(o.dismissals, 0), 2) AS Batting_Average,
                   COALESCE(o.dismissals, 0) AS Dismissals
            FROM bat b LEFT JOIN outs o ON b.season = o.season
            ORDER BY b.season
        """,
    },
    {
        "id": 8,
        "category": "team",
        "intent": "head_to_head",
        "question": "What is the head to head record between Chennai Super Kings and Mumbai Indians?",
        "expected_sql": """
            SELECT ta.team_name AS Team_A, tb.team_name AS Team_B,
                   COUNT(*) AS Matches_Played,
                   SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) AS Team_A_Wins,
                   SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) AS Team_B_Wins,
                   SUM(CASE WHEN mr.winner_id IS NULL OR mr.winner_id NOT IN (ta.team_id, tb.team_id)
                            THEN 1 ELSE 0 END) AS No_Result,
                   ROUND(SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS Team_A_Win_Pct,
                   ROUND(SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS Team_B_Win_Pct
            FROM match_teams mt
            CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = 'Chennai Super Kings') ta
            CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = 'Mumbai Indians') tb
            LEFT JOIN match_result mr ON mt.match_id = mr.match_id
            WHERE (mt.team1_id = ta.team_id AND mt.team2_id = tb.team_id)
               OR (mt.team1_id = tb.team_id AND mt.team2_id = ta.team_id)
        """,
    },
    {
        "id": 9,
        "category": "team",
        "intent": "team_most_titles",
        "question": "Which team has won the most IPL titles?",
        "expected_sql": """
            SELECT w.team_name AS Team, COUNT(*) AS Titles
            FROM match_details md
            JOIN match_result mr ON md.match_id = mr.match_id
            JOIN teams w ON mr.winner_id = w.team_id
            WHERE LOWER(TRIM(md.match_type)) = 'final'
            GROUP BY w.team_id, w.team_name
            ORDER BY Titles DESC, w.team_name
        """,
    },
    {
        "id": 10,
        "category": "team",
        "intent": "season_winner",
        "question": "Who won the 2013 season final?",
        "expected_sql": """
            SELECT w.team_name AS Champion,
                   (CASE WHEN mt.team1_id = mr.winner_id THEN t2.team_name ELSE t1.team_name END) AS Runner_Up
            FROM match_details md
            JOIN match_result mr ON md.match_id = mr.match_id
            JOIN match_teams mt ON md.match_id = mt.match_id
            JOIN teams w ON mr.winner_id = w.team_id
            JOIN teams t1 ON mt.team1_id = t1.team_id
            JOIN teams t2 ON mt.team2_id = t2.team_id
            WHERE md.season = '2013' AND LOWER(TRIM(md.match_type)) = 'final'
            ORDER BY md.date DESC
            LIMIT 1
        """,
    },
    {
        "id": 11,
        "category": "team",
        "intent": "toss_stats",
        "question": "Which team has won the most tosses in IPL history?",
        "expected_sql": """
            SELECT t.team_name AS Team, COUNT(*) AS Tosses_Won
            FROM match_toss mt JOIN teams t ON mt.toss_winner_id = t.team_id
            GROUP BY t.team_id, t.team_name
            ORDER BY Tosses_Won DESC, t.team_name
        """,
    },
    {
        "id": 12,
        "category": "venue",
        "intent": "venue_avg_first_innings",
        "question": "What is the average first innings score at Wankhede Stadium?",
        "expected_sql": """
            SELECT v.venue_name AS Venue, v.venue_city AS City,
                   COUNT(DISTINCT inn1.match_id) AS Matches,
                   ROUND(AVG(inn1.runs), 2) AS Avg_First_Innings_Score
            FROM venues v
            JOIN match_details md ON v.venue_id = md.venue_id
            JOIN (SELECT match_id, SUM(runs_total) AS runs FROM delivery WHERE innings = 1 GROUP BY match_id) inn1
                 ON md.match_id = inn1.match_id
            WHERE v.venue_name = 'Wankhede Stadium'
            GROUP BY v.venue_id, v.venue_name, v.venue_city
        """,
    },
    {
        "id": 13,
        "category": "venue",
        "intent": "list_venues",
        "question": "List all the venues with their cities",
        "expected_sql": "SELECT venue_name AS Venue, venue_city AS City FROM venues ORDER BY venue_name",
    },
    {
        "id": 14,
        "category": "season",
        "intent": "orange_cap",
        "question": "Who was the orange cap winner in 2016?",
        "expected_sql": """
            SELECT p.player_name AS Player, SUM(d.runs_batter) AS Runs
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = '2016'
            JOIN players p ON d.batter_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Runs DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 15,
        "category": "season",
        "intent": "purple_cap",
        "question": "Who took the most wickets (purple cap) in 2020?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT ds.key) AS Wickets
            FROM (SELECT match_id, innings, `over`, ball,
                         CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                  FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')) ds
            JOIN delivery d ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.`over` = d.`over` AND ds.ball = d.ball
            JOIN match_details md ON d.match_id = md.match_id AND md.season = '2020/21'
            JOIN players p ON d.bowler_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Wickets DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 16,
        "category": "season",
        "intent": "boundaries_per_season",
        "question": "How many sixes were hit per season?",
        "expected_sql": """
            SELECT md.season AS Season, COUNT(*) AS Total
            FROM delivery d JOIN match_details md ON d.match_id = md.match_id
            WHERE d.runs_batter = 6
            GROUP BY md.season ORDER BY md.season
        """,
    },
    {
        "id": 17,
        "category": "season",
        "intent": "powerplay_runs",
        "question": "What is the average powerplay score for each team per season?",
        "expected_sql": """
            SELECT md.season AS Season, t.team_name AS Team,
                   ROUND(AVG(pp.runs), 2) AS Avg_Powerplay_Score
            FROM match_details md
            JOIN (SELECT match_id, innings, batting_team_id, SUM(runs_total) AS runs
                  FROM delivery WHERE `over` < 6 GROUP BY match_id, innings, batting_team_id) pp
                 ON md.match_id = pp.match_id
            JOIN teams t ON pp.batting_team_id = t.team_id
            GROUP BY md.season, t.team_name
            ORDER BY md.season, t.team_name
        """,
    },
    {
        "id": 18,
        "category": "season",
        "intent": "powerplay_wickets",
        "question": "Average wickets taken in the powerplay per team and season?",
        "expected_sql": """
            SELECT md.season AS Season, t.team_name AS Team,
                   ROUND(AVG(pp.wkts), 2) AS Avg_Wickets_Powerplay
            FROM match_details md
            JOIN (
                SELECT d.match_id, d.innings, d.bowling_team_id, COUNT(DISTINCT ds.id) AS wkts
                FROM delivery d
                JOIN (SELECT match_id, innings, `over`, ball,
                             ROW_NUMBER() OVER (PARTITION BY match_id, innings, `over`, ball ORDER BY match_id) AS id
                      FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')) ds
                     ON d.match_id = ds.match_id AND d.innings = ds.innings
                        AND d.`over` = ds.`over` AND d.ball = ds.ball
                WHERE d.`over` < 6
                GROUP BY d.match_id, d.innings, d.bowling_team_id
            ) pp ON md.match_id = pp.match_id
            JOIN teams t ON pp.bowling_team_id = t.team_id
            GROUP BY md.season, t.team_name
            ORDER BY md.season, t.team_name
        """,
    },
    {
        "id": 19,
        "category": "season",
        "intent": "hundreds_fifties",
        "question": "Which player hit the most hundreds and fifties each season?",
        "expected_sql": """
            WITH innings AS (
                SELECT md.season, d.match_id, d.innings, d.batter_id, SUM(d.runs_batter) AS runs
                FROM delivery d JOIN match_details md ON d.match_id = md.match_id
                GROUP BY md.season, d.match_id, d.innings, d.batter_id
            ),
            agg AS (
                SELECT season, batter_id,
                       SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) AS hundreds,
                       SUM(CASE WHEN runs >= 50 THEN 1 ELSE 0 END) AS fifties
                FROM innings GROUP BY season, batter_id
            ),
            ranked AS (
                SELECT season, batter_id, hundreds, fifties,
                       RANK() OVER (PARTITION BY season ORDER BY hundreds DESC, fifties DESC, batter_id) AS hr,
                       RANK() OVER (PARTITION BY season ORDER BY fifties DESC, hundreds DESC, batter_id) AS fr
                FROM agg
            )
            SELECT s.season AS Season, ph.player_name AS Most_Hundreds, a.hundreds AS Hundreds,
                   pf.player_name AS Most_Fifties, a2.fifties AS Fifties
            FROM (SELECT DISTINCT season FROM ranked) s
            LEFT JOIN ranked a ON s.season = a.season AND a.hr = 1
            LEFT JOIN ranked a2 ON s.season = a2.season AND a2.fr = 1
            LEFT JOIN players ph ON a.batter_id = ph.player_id
            LEFT JOIN players pf ON a2.batter_id = pf.player_id
            ORDER BY s.season
        """,
    },
    {
        "id": 20,
        "category": "season",
        "intent": "five_wicket_hauls",
        "question": "Which bowlers took five or more wickets in a match, per season?",
        "expected_sql": """
            WITH match_wkts AS (
                SELECT md.season, d.match_id, d.bowler_id, COUNT(DISTINCT ds.key) AS wkts
                FROM (SELECT match_id, innings, `over`, ball,
                             CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                      FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')) ds
                JOIN delivery d ON ds.match_id = d.match_id AND ds.innings = d.innings
                    AND ds.`over` = d.`over` AND ds.ball = d.ball
                JOIN match_details md ON d.match_id = md.match_id
                GROUP BY md.season, d.match_id, d.bowler_id
            ),
            agg AS (
                SELECT season, bowler_id, COUNT(*) AS five_wicket_hauls
                FROM match_wkts WHERE wkts >= 5 GROUP BY season, bowler_id
            )
            SELECT a.season AS Season, p.player_name AS Bowler, a.five_wicket_hauls AS Five_Wicket_Hauls
            FROM agg a JOIN players p ON a.bowler_id = p.player_id
            ORDER BY a.season, a.five_wicket_hauls DESC
        """,
    },
    {
        "id": 21,
        "category": "season",
        "intent": "highest_partnership",
        "question": "What was the highest batting partnership in 2019?",
        "expected_sql": """
            WITH ordered AS (
                SELECT d.match_id, d.innings, d.`over`, d.ball, d.runs_total,
                       d.batter_id, d.non_striker_id,
                       ROW_NUMBER() OVER (PARTITION BY d.match_id, d.innings ORDER BY d.`over`, d.ball) AS rn,
                       CASE WHEN ds.key IS NOT NULL THEN 1 ELSE 0 END AS is_wicket
                FROM delivery d
                LEFT JOIN (SELECT match_id, innings, `over`, ball,
                                  CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                           FROM dismissal) ds
                    ON d.match_id = ds.match_id AND d.innings = ds.innings
                       AND d.`over` = ds.`over` AND d.ball = ds.ball
            ),
            part_groups AS (
                SELECT match_id, innings, runs_total, batter_id, non_striker_id,
                       COALESCE(SUM(is_wicket) OVER (
                           PARTITION BY match_id, innings ORDER BY rn
                           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS grp
                FROM ordered
            ),
            part_agg AS (
                SELECT match_id, innings, grp, SUM(runs_total) AS runs,
                       MIN(LEAST(COALESCE(batter_id, 0), COALESCE(non_striker_id, 0))) AS b1,
                       MAX(GREATEST(COALESCE(batter_id, 0), COALESCE(non_striker_id, 0))) AS b2
                FROM part_groups GROUP BY match_id, innings, grp
            ),
            with_season AS (
                SELECT md.season, md.date, pa.match_id, pa.runs, pa.b1, pa.b2
                FROM part_agg pa JOIN match_details md ON pa.match_id = md.match_id
            ),
            ranked AS (
                SELECT season, date, match_id, runs, b1, b2,
                       ROW_NUMBER() OVER (PARTITION BY season ORDER BY runs DESC, date, match_id) AS rk
                FROM with_season
            )
            SELECT r.season AS Season, r.date AS Date,
                   p1.player_name AS Batter_1, p2.player_name AS Batter_2,
                   r.runs AS Partnership_Runs
            FROM ranked r
            JOIN players p1 ON r.b1 = p1.player_id
            JOIN players p2 ON r.b2 = p2.player_id
            WHERE r.rk = 1 AND r.season = '2019'
            ORDER BY r.season
        """,
    },
    {
        "id": 22,
        "category": "bowler",
        "intent": "bowler_vs_batter",
        "question": "How has Jasprit Bumrah bowled to Virat Kohli?",
        "expected_sql": """
            SELECT bo.player_name AS Bowler, ba.player_name AS Batter,
                   COUNT(d.batter_id) AS Balls_Bowled,
                   SUM(d.runs_batter) AS Runs_Scored,
                   COUNT(DISTINCT CONCAT(ds.match_id, '-', ds.innings, '-', ds.`over`, '-', ds.ball)) AS Times_Dismissed,
                   ROUND(SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(d.batter_id), 0), 2) AS Batter_Strike_Rate,
                   ROUND(SUM(d.runs_batter) * 1.0 / NULLIF(COUNT(DISTINCT CONCAT(ds.match_id, '-', ds.innings, '-', ds.`over`, '-', ds.ball)), 0), 2) AS Batter_Average
            FROM delivery d
            JOIN players bo ON d.bowler_id = bo.player_id
            JOIN players ba ON d.batter_id = ba.player_id
            LEFT JOIN dismissal ds ON d.match_id = ds.match_id AND d.innings = ds.innings
                AND d.`over` = ds.`over` AND d.ball = ds.ball
            WHERE bo.player_name = 'JJ Bumrah' AND ba.player_name = 'V Kohli'
            GROUP BY bo.player_name, ba.player_name
        """,
    },
    {
        "id": 23,
        "category": "all-time",
        "intent": "top_run_scorer",
        "question": "Who is the highest run scorer in IPL history?",
        "expected_sql": """
            SELECT p.player_name AS Player, SUM(d.runs_batter) AS Runs
            FROM delivery d JOIN players p ON d.batter_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Runs DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 24,
        "category": "all-time",
        "intent": "top_wicket_taker",
        "question": "Who has taken the most wickets in IPL history?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT ds.key) AS Wickets
            FROM (SELECT match_id, innings, `over`, ball,
                         CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                  FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')) ds
            JOIN delivery d ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.`over` = d.`over` AND ds.ball = d.ball
            JOIN players p ON d.bowler_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Wickets DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 25,
        "category": "all-time",
        "intent": "most_sixes",
        "question": "Which player has hit the most sixes of all time?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(*) AS Sixes
            FROM delivery d JOIN players p ON d.batter_id = p.player_id
            WHERE d.runs_batter = 6
            GROUP BY p.player_id, p.player_name
            ORDER BY Sixes DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 26,
        "category": "all-time",
        "intent": "most_fours",
        "question": "Who has scored the most fours in IPL history?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(*) AS Fours
            FROM delivery d JOIN players p ON d.batter_id = p.player_id
            WHERE d.runs_batter = 4
            GROUP BY p.player_id, p.player_name
            ORDER BY Fours DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 27,
        "category": "all-time",
        "intent": "most_matches",
        "question": "Which player has played the most IPL matches?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches
            FROM delivery d JOIN players p ON d.batter_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Matches DESC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 28,
        "category": "umpire",
        "intent": "umpire_record",
        "question": "How many matches has Sundaram Ravi officiated?",
        "expected_sql": """
            SELECT u.umpire_name AS Umpire, COUNT(mu.match_id) AS Matches_Officiated
            FROM umpires u JOIN match_umpire mu ON u.umpire_id = mu.umpire_id
            WHERE u.umpire_name = 'S Ravi'
            GROUP BY u.umpire_id, u.umpire_name
        """,
    },
    {
        "id": 29,
        "category": "match",
        "intent": "list_matches",
        "question": "List all matches played in the 2023 season",
        "expected_sql": """
            SELECT md.season AS Season, md.date AS Date,
                   t1.team_name AS Team_1, t2.team_name AS Team_2,
                   v.venue_name AS Venue, md.match_type AS Match_Type,
                   COALESCE(CONCAT(w.team_name, ' won by ', mr.result_margin, ' ', mr.result),
                            'No Result') AS Result
            FROM match_details md
            JOIN match_teams mt ON md.match_id = mt.match_id
            JOIN teams t1 ON mt.team1_id = t1.team_id
            JOIN teams t2 ON mt.team2_id = t2.team_id
            JOIN venues v ON md.venue_id = v.venue_id
            LEFT JOIN match_result mr ON md.match_id = mr.match_id
            LEFT JOIN teams w ON mr.winner_id = w.team_id
            WHERE md.season = '2023'
            ORDER BY md.date, md.match_id
        """,
    },
    {
        "id": 30,
        "category": "match",
        "intent": "list_teams",
        "question": "List all the teams",
        "expected_sql": "SELECT team_name AS Team FROM teams ORDER BY team_name",
    },
    {
        "id": 31,
        "category": "player",
        "intent": "player_matches",
        "question": "How many matches has Jasprit Bumrah played?",
        "expected_sql": """
            SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches
            FROM players p LEFT JOIN delivery d ON p.player_id = d.batter_id
            WHERE p.player_name = 'JJ Bumrah'
            GROUP BY p.player_id, p.player_name
        """,
    },
    {
        "id": 32,
        "category": "all-time",
        "intent": "best_economy",
        "question": "Who has the best bowling economy rate in IPL history?",
        "expected_sql": """
            SELECT p.player_name AS Player,
                   ROUND(SUM(d.runs_total) * 6.0 / NULLIF(COUNT(d.bowler_id), 0), 2) AS Economy,
                   COUNT(d.bowler_id) AS Balls_Bowled
            FROM delivery d JOIN players p ON d.bowler_id = p.player_id
            GROUP BY p.player_id, p.player_name
            HAVING COUNT(d.bowler_id) >= 600
            ORDER BY Economy ASC, p.player_name
            LIMIT 1
        """,
    },
    {
        "id": 33,
        "category": "venue",
        "intent": "top_venue_first_innings",
        "question": "Which venue has the highest average first innings score?",
        "expected_sql": """
            SELECT v.venue_name AS Venue, v.venue_city AS City,
                   ROUND(AVG(inn1.runs), 2) AS Avg_First_Innings_Score
            FROM venues v
            JOIN match_details md ON v.venue_id = md.venue_id
            JOIN (SELECT match_id, SUM(runs_total) AS runs FROM delivery WHERE innings = 1 GROUP BY match_id) inn1
                 ON md.match_id = inn1.match_id
            GROUP BY v.venue_id, v.venue_name, v.venue_city
            ORDER BY Avg_First_Innings_Score DESC, v.venue_name
            LIMIT 1
        """,
    },
]


# --------------------------------------------------------------------------- #
# Result comparison helpers
# --------------------------------------------------------------------------- #
def _normalize_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 4)
    return str(value)


def _sort_key(row):
    return tuple(repr(_normalize_cell(v)) for v in row)


def results_match(expected: list[dict], actual: list[dict]) -> bool:
    """Execution-accuracy comparison: identical rows by VALUES, not aliases.

    Column names/order are cosmetic; two answers are considered equal when they
    return the same rows of data (Spider-style execution accuracy).
    """
    def cell_key(v):
        return repr(_normalize_cell(v))

    def row_values(rows):
        return sorted(
            [tuple(sorted((_normalize_cell(v) for v in r.values()), key=cell_key))
             for r in rows],
            key=lambda t: tuple(cell_key(v) for v in t),
        )
    return row_values(expected) == row_values(actual)


def sql_signature(sql: str) -> str:
    return " ".join(sql.lower().replace("`", "").split())


def _expected_rows(expected_sql: str) -> list[dict]:
    try:
        res = execute_sql(expected_sql)
        return res["rows"]
    except Exception as e:  # noqa: BLE001
        return [{"_error": str(e)}]


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
ENGINE = "auto"  # "auto" | "rule" | "llm"; set via the --engine CLI flag


async def run_case(case: dict) -> dict:
    question = case["question"]
    result = {
        "id": case["id"],
        "category": case["category"],
        "intent": case.get("intent", ""),
        "question": question,
        "status": "failed",
        "error": None,
        "sql_source": None,
        "generated_sql": None,
        "expected_sql": case["expected_sql"].strip(),
        "generated_rows": None,
        "expected_rows": None,
        "elapsed_ms": None,
        "sql_match": False,
        "result_match": False,
    }
    start = time.perf_counter()
    try:
        payload = await process_question(question, engine=ENGINE)
        result["generated_sql"] = payload["sql"]
        result["sql_source"] = payload["sql_source"]
        result["generated_rows"] = payload["rows"]
        result["elapsed_ms"] = payload["elapsed_ms"]
        result["status"] = "executed"
    except Exception as e:  # noqa: BLE001
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 1)
        return result

    exp_rows = _expected_rows(result["expected_sql"])
    result["expected_rows"] = exp_rows
    if any("_error" in (r or {}) for r in exp_rows):
        result["status"] = "failed"
        result["error"] = f"Expected SQL failed: {exp_rows[0].get('_error')}"
        return result

    result["sql_match"] = sql_signature(result["generated_sql"]) == sql_signature(case["expected_sql"])
    result["result_match"] = results_match(exp_rows, result["generated_rows"] or [])
    result["status"] = "passed" if result["result_match"] else "wrong"
    return result


async def run_benchmark(cases: list[dict] | None = None) -> dict:
    cases = cases or CASES
    results = []
    for case in cases:
        res = await run_case(case)
        results.append(res)
    return summarize(results)


def summarize(results: list[dict]) -> dict:
    total = len(results)
    executed = sum(1 for r in results if r["status"] in ("passed", "wrong"))
    passed = sum(1 for r in results if r["status"] == "passed")
    wrong = sum(1 for r in results if r["status"] == "wrong")
    failed = sum(1 for r in results if r["status"] == "failed")
    accuracy = round(100.0 * passed / total, 1) if total else 0.0
    avg_ms = round(sum(r["elapsed_ms"] or 0 for r in results) / total, 1) if total else 0.0

    by_source = {}
    for r in results:
        key = r["sql_source"] or "none"
        d = by_source.setdefault(key, {"count": 0, "passed": 0})
        d["count"] += 1
        d["passed"] += 1 if r["status"] == "passed" else 0

    return {
        "total": total,
        "executed": executed,
        "passed": passed,
        "wrong": wrong,
        "failed": failed,
        "accuracy": accuracy,
        "avg_query_ms": avg_ms,
        "by_sql_source": by_source,
        "cases": results,
    }


def print_report(report: dict) -> None:
    line = "=" * 100
    print(line)
    print("IPL QUERY RESOLVER - Text-to-SQL BENCHMARK REPORT")
    print(line)
    print(f"Total cases      : {report['total']}")
    print(f"Executed         : {report['executed']}")
    print(f"Passed (correct) : {report['passed']}")
    print(f"Wrong results    : {report['wrong']}")
    print(f"Failed to answer : {report['failed']}")
    print(f"System accuracy  : {report['accuracy']}%  ({report['passed']}/{report['total']})")
    print(f"Avg query time   : {report['avg_query_ms']} ms")
    if report["by_sql_source"]:
        print("By SQL source    : " + ", ".join(
            f"{k}={v['passed']}/{v['count']}" for k, v in report["by_sql_source"].items()))
    print(line)
    print(f"{'ID':>3} {'STATUS':<8} {'CATEGORY':<10} {'INTENT':<24} {'SQL MATCH':<9} {'MS':>8}  QUESTION")
    print("-" * 100)
    for r in report["cases"]:
        status = {"passed": "PASS", "wrong": "WRONG", "failed": "FAIL"}[r["status"]]
        sm = "yes" if r["sql_match"] else "-"
        ms = r["elapsed_ms"] or 0
        print(f"{r['id']:>3} {status:<8} {r['category']:<10} {r['intent']:<24} {sm:<9} {ms:>8.1f}  {r['question'][:60]}")
        if r["status"] == "failed" and r["error"]:
            print(f"      ! {r['error'][:120]}")
        elif r["status"] == "wrong":
            print(f"      generated: {str(r['generated_sql'])[:100]}")
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Text-to-SQL benchmark")
    parser.add_argument("--json", action="store_true", help="write report.json")
    parser.add_argument("--case", type=int, help="run a single case by id")
    parser.add_argument("--engine", choices=["auto", "rule", "llm"], default="auto",
                        help="SQL generator to benchmark (default: auto = LLM-first, rule fallback)")
    args = parser.parse_args()

    global ENGINE
    ENGINE = args.engine

    cases = CASES
    if args.case:
        cases = [c for c in CASES if c["id"] == args.case]
        if not cases:
            print(f"Unknown case id: {args.case}")
            return 1

    report = asyncio.run(run_benchmark(cases))
    print_report(report)
    if args.json:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json")
        with open(out, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
