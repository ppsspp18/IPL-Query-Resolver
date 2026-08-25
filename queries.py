from db import run_query, run_many

INPUT_TEAM = {"name": "team", "label": "Team", "type": "select", "source": "teams"}
INPUT_TEAM1 = {"name": "team1", "label": "Team 1", "type": "select", "source": "teams"}
INPUT_TEAM2 = {"name": "team2", "label": "Team 2", "type": "select", "source": "teams"}
INPUT_PLAYER = {"name": "player", "label": "Player", "type": "select", "source": "players"}
INPUT_VENUE = {"name": "venue", "label": "Stadium", "type": "select", "source": "venues"}
INPUT_UMPIRE = {"name": "umpire", "label": "Umpire", "type": "select", "source": "umpires"}
INPUT_SEASON = {"name": "season", "label": "Season", "type": "select", "source": "seasons"}
INPUT_SEASON_OPT = {**INPUT_SEASON, "required": False}
INPUT_BOUNDARY = {
    "name": "boundary",
    "label": "Boundary",
    "type": "radio",
    "options": [{"value": "4", "label": "Fours (4s)"}, {"value": "6", "label": "Sixes (6s)"}],
    "default": "4",
}


def _table(title, columns, rows):
    return {"type": "table", "title": title, "columns": columns, "rows": rows}


def _cards(title, cards):
    return {"type": "cards", "title": title, "cards": cards}


def _note(text):
    return {"type": "note", "title": "", "text": text}


def result(title, sections):
    return {"title": title, "sections": sections}


# --------------------------------------------------------------------------- #
# 1. List of all IPL teams
# --------------------------------------------------------------------------- #
def q1(i):
    rows = run_query("SELECT team_name AS `Team` FROM teams ORDER BY team_name")
    return result(
        "List of all IPL teams",
        [_table("IPL Teams", ["Team"], rows)],
    )


# --------------------------------------------------------------------------- #
# 2. List of all players
# --------------------------------------------------------------------------- #
def q2(i):
    rows = run_query("SELECT player_name AS `Player` FROM players ORDER BY player_name")
    return result(
        "List of all players",
        [_table("IPL Players", ["Player"], rows)],
    )


# --------------------------------------------------------------------------- #
# 3. List of all umpires
# --------------------------------------------------------------------------- #
def q3(i):
    rows = run_query("SELECT umpire_name AS `Umpire` FROM umpires ORDER BY umpire_name")
    return result(
        "List of all umpires",
        [_table("IPL Umpires", ["Umpire"], rows)],
    )


# --------------------------------------------------------------------------- #
# 4. List of all venues
# --------------------------------------------------------------------------- #
def q4(i):
    rows = run_query(
        "SELECT venue_name AS `Venue`, venue_city AS `City` FROM venues ORDER BY venue_name"
    )
    return result(
        "List of all venues",
        [_table("IPL Venues", ["Venue", "City"], rows)],
    )


# --------------------------------------------------------------------------- #
# 5. List of all matches played in IPL
# --------------------------------------------------------------------------- #
def q5(i):
    season = (i.get("season") or "").strip()
    sql = """
        SELECT
            md.season AS `Season`,
            md.date AS `Date`,
            t1.team_name AS `Team 1`,
            t2.team_name AS `Team 2`,
            v.venue_name AS `Venue`,
            v.venue_city AS `City`,
            md.match_type AS `Match Type`,
            CASE
                WHEN mr.winner_id IS NULL THEN 'No Result'
                ELSE CONCAT(w.team_name, ' won by ', mr.result_margin, ' ', mr.result)
            END AS `Result`,
            COALESCE(pp.player_name, '') AS `Player of the Match`
        FROM match_details md
        JOIN match_teams mt ON md.match_id = mt.match_id
        JOIN teams t1 ON mt.team1_id = t1.team_id
        JOIN teams t2 ON mt.team2_id = t2.team_id
        JOIN venues v ON md.venue_id = v.venue_id
        LEFT JOIN match_result mr ON md.match_id = mr.match_id
        LEFT JOIN teams w ON mr.winner_id = w.team_id
        LEFT JOIN players pp ON mr.player_of_match_id = pp.player_id
    """
    params = []
    if season:
        sql += " WHERE md.season = %s"
        params.append(season)
    sql += " ORDER BY md.date, md.match_id"
    rows = run_query(sql, params)
    return result(
        "Matches played in IPL" + (f" - Season {season}" if season else " (All seasons)"),
        [_table("Matches", ["Season", "Date", "Team 1", "Team 2", "Venue", "City",
                            "Match Type", "Result", "Player of the Match"], rows)],
    )


# --------------------------------------------------------------------------- #
# 6. Particular player stats in IPL
# --------------------------------------------------------------------------- #
def q6(i):
    player = i["player"]
    bat, bowl = run_many([
        ("""
            SELECT
                p.player_name AS `Player`,
                COUNT(DISTINCT md.match_id) AS `Matches`,
                COUNT(DISTINCT CONCAT(d.match_id, '-', d.innings)) AS `Innings`,
                SUM(d.runs_batter) AS `Runs`,
                COUNT(d.batter_id) AS `Balls Faced`,
                SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS `Fours`,
                SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS `Sixes`,
                ROUND(SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(d.batter_id), 0), 2) AS `Strike Rate`
            FROM players p
            LEFT JOIN delivery d ON p.player_id = d.batter_id
            LEFT JOIN match_details md ON d.match_id = md.match_id
            WHERE p.player_name = %s
            GROUP BY p.player_id, p.player_name
        """, (player,)),
        ("""
            SELECT
                p.player_name AS `Player`,
                COUNT(DISTINCT md.match_id) AS `Matches`,
                COUNT(d.bowler_id) AS `Balls Bowled`,
                ROUND(COUNT(d.bowler_id) / 6.0, 1) AS `Overs`,
                SUM(d.runs_total) AS `Runs Conceded`,
                SUM(CASE WHEN ds.player_out_id IS NOT NULL
                          AND ds.wicket_kind NOT IN ('run out', 'retired hurt')
                         THEN 1 ELSE 0 END) AS `Wickets`,
                ROUND(SUM(d.runs_total) * 1.0 / NULLIF(SUM(CASE WHEN ds.player_out_id IS NOT NULL
                            AND ds.wicket_kind NOT IN ('run out', 'retired hurt')
                            THEN 1 ELSE 0 END), 0), 2) AS `Bowling Average`,
                ROUND(SUM(d.runs_total) * 6.0 / NULLIF(COUNT(d.bowler_id), 0), 2) AS `Economy`
            FROM players p
            LEFT JOIN delivery d ON p.player_id = d.bowler_id
            LEFT JOIN match_details md ON d.match_id = md.match_id
            LEFT JOIN dismissal ds
                ON d.match_id = ds.match_id AND d.innings = ds.innings
                   AND d.over = ds.over AND d.ball = ds.ball
            WHERE p.player_name = %s
            GROUP BY p.player_id, p.player_name
        """, (player,)),
    ])
    return result(
        f"Career stats - {player}",
        [
            _table("Batting Statistics", ["Player", "Matches", "Innings", "Runs",
                                          "Balls Faced", "Fours", "Sixes", "Strike Rate"], bat),
            _table("Bowling Statistics", ["Player", "Matches", "Balls Bowled", "Overs",
                                          "Runs Conceded", "Wickets", "Bowling Average", "Economy"], bowl),
        ],
    )


# --------------------------------------------------------------------------- #
# 7. How many times has a player won Man of the Match (and in which matches)
# --------------------------------------------------------------------------- #
def q7(i):
    player = i["player"]
    count, matches = run_many([
        ("""
            SELECT COUNT(*) AS `Man of the Match Awards`
            FROM match_result mr
            JOIN players p ON mr.player_of_match_id = p.player_id
            WHERE p.player_name = %s
        """, (player,)),
        ("""
            SELECT
                md.season AS `Season`,
                md.date AS `Date`,
                t1.team_name AS `Team 1`,
                t2.team_name AS `Team 2`,
                v.venue_name AS `Venue`,
                md.match_type AS `Match Type`,
                COALESCE(w.team_name, 'No Result') AS `Match Winner`
            FROM match_result mr
            JOIN players p ON mr.player_of_match_id = p.player_id
            JOIN match_details md ON mr.match_id = md.match_id
            JOIN match_teams mt ON md.match_id = mt.match_id
            JOIN teams t1 ON mt.team1_id = t1.team_id
            JOIN teams t2 ON mt.team2_id = t2.team_id
            JOIN venues v ON md.venue_id = v.venue_id
            LEFT JOIN teams w ON mr.winner_id = w.team_id
            WHERE p.player_name = %s
            ORDER BY md.date
        """, (player,)),
    ])
    sections = []
    if count:
        sections.append(_cards("Summary", [{"label": "Player", "value": player},
                                           {"label": "Man of the Match Awards", "value": count[0]["Man of the Match Awards"]}]))
    if matches:
        sections.append(_table("Matches where " + player + " was Man of the Match",
                               ["Season", "Date", "Team 1", "Team 2", "Venue",
                                "Match Type", "Match Winner"], matches))
    if not sections:
        sections.append(_note(f"No Man of the Match awards found for {player}."))
    return result(f"Man of the Match record - {player}", sections)


# --------------------------------------------------------------------------- #
# 8. Head to Head stats of any 2 teams
# --------------------------------------------------------------------------- #
def q8(i):
    team1, team2 = i["team1"], i["team2"]
    rows = run_query(
        """
        SELECT
            ta.team_name AS `Team A`,
            tb.team_name AS `Team B`,
            COUNT(*) AS `Matches Played`,
            SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) AS `Team A Wins`,
            SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) AS `Team B Wins`,
            SUM(CASE WHEN mr.winner_id IS NULL
                          OR mr.winner_id NOT IN (ta.team_id, tb.team_id)
                     THEN 1 ELSE 0 END) AS `No Result / Tied`,
            ROUND(SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS `Team A Win Pct`,
            ROUND(SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS `Team B Win Pct`
        FROM match_teams mt
        CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = %s) ta
        CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = %s) tb
        LEFT JOIN match_result mr ON mt.match_id = mr.match_id
        WHERE (mt.team1_id = ta.team_id AND mt.team2_id = tb.team_id)
           OR (mt.team1_id = tb.team_id AND mt.team2_id = ta.team_id)
        """,
        (team1, team2),
    )
    return result(
        f"Head to Head - {team1} vs {team2}",
        [_table("Head to Head Statistics",
                ["Team A", "Team B", "Matches Played", "Team A Wins", "Team B Wins",
                 "No Result / Tied", "Team A Win Pct", "Team B Win Pct"], rows)],
    )


# --------------------------------------------------------------------------- #
# 9. Player team history (which team in which season)
# --------------------------------------------------------------------------- #
def q9(i):
    player = i["player"]
    rows = run_query(
        """
        SELECT
            md.season AS `Season`,
            bt.team_name AS `Team`,
            COUNT(DISTINCT d.match_id) AS `Matches Played`
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        JOIN teams bt ON d.batting_team_id = bt.team_id
        JOIN players p ON d.batter_id = p.player_id
        WHERE p.player_name = %s
        GROUP BY md.season, bt.team_name
        ORDER BY md.season, bt.team_name
        """,
        (player,),
    )
    return result(
        f"Team history - {player}",
        [_table("Teams played for by season", ["Season", "Team", "Matches Played"], rows)],
    )


# --------------------------------------------------------------------------- #
# 10. For a given stadium, average first innings score
# --------------------------------------------------------------------------- #
def q10(i):
    venue = i["venue"]
    overall, per_season = run_many([
        ("""
            SELECT
                v.venue_name AS `Venue`,
                v.venue_city AS `City`,
                COUNT(DISTINCT inn1.match_id) AS `Matches`,
                ROUND(AVG(inn1.runs), 2) AS `Average First Innings Score`
            FROM venues v
            JOIN match_details md ON v.venue_id = md.venue_id
            JOIN (
                SELECT match_id, SUM(runs_total) AS runs
                FROM delivery WHERE innings = 1
                GROUP BY match_id
            ) inn1 ON md.match_id = inn1.match_id
            WHERE v.venue_name = %s
            GROUP BY v.venue_id, v.venue_name, v.venue_city
        """, (venue,)),
        ("""
            SELECT
                md.season AS `Season`,
                COUNT(DISTINCT inn1.match_id) AS `Matches`,
                ROUND(AVG(inn1.runs), 2) AS `Average First Innings Score`
            FROM venues v
            JOIN match_details md ON v.venue_id = md.venue_id
            JOIN (
                SELECT match_id, SUM(runs_total) AS runs
                FROM delivery WHERE innings = 1
                GROUP BY match_id
            ) inn1 ON md.match_id = inn1.match_id
            WHERE v.venue_name = %s
            GROUP BY md.season
            ORDER BY md.season
        """, (venue,)),
    ])
    sections = []
    if overall:
        o = overall[0]
        sections.append(_cards("Summary", [
            {"label": "Venue", "value": o["Venue"]},
            {"label": "City", "value": o["City"]},
            {"label": "Matches", "value": o["Matches"]},
            {"label": "Average 1st Innings Score", "value": o["Average First Innings Score"]},
        ]))
    if per_season:
        sections.append(_table("Season-wise breakdown", ["Season", "Matches",
                                                        "Average First Innings Score"], per_season))
    if not sections:
        sections.append(_note(f"No matches found at {venue}."))
    return result(f"Average first innings score - {venue}", sections)


# --------------------------------------------------------------------------- #
# 11. Total number of 4s or 6s per season
# --------------------------------------------------------------------------- #
def q11(i):
    boundary = int(i.get("boundary") or 4)
    label = "Fours (4s)" if boundary == 4 else "Sixes (6s)"
    rows = run_query(
        """
        SELECT
            md.season AS `Season`,
            COUNT(*) AS `Total`
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        WHERE d.runs_batter = %s
        GROUP BY md.season
        ORDER BY md.season
        """,
        (boundary,),
    )
    return result(
        f"Number of {label} per season",
        [_table(f"Boundary count - {label}", ["Season", "Total"], rows)],
    )


# --------------------------------------------------------------------------- #
# 12. Average powerplay score of a team for each season
# --------------------------------------------------------------------------- #
def q12(i):
    season = (i.get("season") or "").strip()
    sql = """
        SELECT
            md.season AS `Season`,
            t.team_name AS `Team`,
            ROUND(AVG(pp.runs), 2) AS `Average Powerplay Score`,
            COUNT(DISTINCT pp.match_id) AS `Innings`
        FROM match_details md
        JOIN (
            SELECT match_id, innings, batting_team_id, SUM(runs_total) AS runs
            FROM delivery
            WHERE `over` < 6
            GROUP BY match_id, innings, batting_team_id
        ) pp ON md.match_id = pp.match_id
        JOIN teams t ON pp.batting_team_id = t.team_id
    """
    params = []
    if season:
        sql += " WHERE md.season = %s"
        params.append(season)
    sql += """
        GROUP BY md.season, t.team_name
        ORDER BY md.season, t.team_name
    """
    rows = run_query(sql, params)
    return result(
        "Average powerplay score per team per season",
        [_table("Powerplay batting (first 6 overs)",
                ["Season", "Team", "Average Powerplay Score", "Innings"], rows)],
    )


# --------------------------------------------------------------------------- #
# 13. Average wickets taken in powerplay of a team for each season
# --------------------------------------------------------------------------- #
def q13(i):
    season = (i.get("season") or "").strip()
    sql = """
        SELECT
            md.season AS `Season`,
            t.team_name AS `Team`,
            ROUND(AVG(pp.wkts), 2) AS `Average Wickets in Powerplay`,
            COUNT(DISTINCT pp.match_id) AS `Innings Bowled`
        FROM match_details md
        JOIN (
            SELECT d.match_id, d.innings, d.bowling_team_id, COUNT(DISTINCT ds.id) AS wkts
            FROM delivery d
            JOIN (
                SELECT match_id, innings, `over`, ball,
                       ROW_NUMBER() OVER (
                           PARTITION BY match_id, innings, `over`, ball ORDER BY match_id
                       ) AS id
                FROM dismissal
                WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds ON d.match_id = ds.match_id AND d.innings = ds.innings
                AND d.over = ds.over AND d.ball = ds.ball
            WHERE d.`over` < 6
            GROUP BY d.match_id, d.innings, d.bowling_team_id
        ) pp ON md.match_id = pp.match_id
        JOIN teams t ON pp.bowling_team_id = t.team_id
    """
    params = []
    if season:
        sql += " WHERE md.season = %s"
        params.append(season)
    sql += """
        GROUP BY md.season, t.team_name
        ORDER BY md.season, t.team_name
    """
    rows = run_query(sql, params)
    return result(
        "Average wickets taken in powerplay per team per season",
        [_table("Powerplay bowling (first 6 overs)",
                ["Season", "Team", "Average Wickets in Powerplay", "Innings Bowled"], rows)],
    )


# --------------------------------------------------------------------------- #
# 14. Particular season stats - caps, most 4s/6s/dot balls, winner, runner up
# --------------------------------------------------------------------------- #
def q14(i):
    season = i["season"]
    rows = run_many([
        # Orange cap
        ("""
            SELECT p.player_name AS `name`, SUM(d.runs_batter) AS `runs`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.batter_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY runs DESC, p.player_name
            LIMIT 1
        """, (season,)),
        # Purple cap
        ("""
            SELECT p.player_name AS `name`, COUNT(DISTINCT ds.key) AS `wickets`
            FROM (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
                WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds
            JOIN delivery d
                ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.over = d.over AND ds.ball = d.ball
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.bowler_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY wickets DESC, p.player_name
            LIMIT 1
        """, (season,)),
        # Most fours
        ("""
            SELECT p.player_name AS `name`, COUNT(*) AS `count`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.batter_id = p.player_id
            WHERE d.runs_batter = 4
            GROUP BY p.player_id, p.player_name
            ORDER BY count DESC, p.player_name
            LIMIT 1
        """, (season,)),
        # Most sixes
        ("""
            SELECT p.player_name AS `name`, COUNT(*) AS `count`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.batter_id = p.player_id
            WHERE d.runs_batter = 6
            GROUP BY p.player_id, p.player_name
            ORDER BY count DESC, p.player_name
            LIMIT 1
        """, (season,)),
        # Most dot balls (faced)
        ("""
            SELECT p.player_name AS `name`, COUNT(*) AS `count`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.batter_id = p.player_id
            WHERE d.runs_total = 0
            GROUP BY p.player_id, p.player_name
            ORDER BY count DESC, p.player_name
            LIMIT 1
        """, (season,)),
        # Winner
        ("""
            SELECT w.team_name AS `name`
            FROM match_details md
            JOIN match_result mr ON md.match_id = mr.match_id
            JOIN teams w ON mr.winner_id = w.team_id
            WHERE md.season = %s AND LOWER(TRIM(md.match_type)) = 'final'
            ORDER BY md.date DESC
            LIMIT 1
        """, (season,)),
        # Runner up
        ("""
            SELECT
                CASE WHEN mt.team1_id = mr.winner_id THEN t2.team_name ELSE t1.team_name END AS `name`
            FROM match_details md
            JOIN match_result mr ON md.match_id = mr.match_id
            JOIN match_teams mt ON md.match_id = mt.match_id
            JOIN teams t1 ON mt.team1_id = t1.team_id
            JOIN teams t2 ON mt.team2_id = t2.team_id
            WHERE md.season = %s AND LOWER(TRIM(md.match_type)) = 'final'
            ORDER BY md.date DESC
            LIMIT 1
        """, (season,)),
    ])

    cards = []
    title_map = [
        ("Orange Cap", "runs", " runs"),
        ("Purple Cap", "wickets", " wickets"),
        ("Most Fours", "count", " fours"),
        ("Most Sixes", "count", " sixes"),
        ("Most Dot Balls", "count", " dot balls"),
    ]
    for (t, key, suffix), row in zip(title_map, rows):
        first = row[0] if row else None
        cards.append({"label": t, "value": (first["name"] if first else "N/A"),
                      "detail": (str(first[key]) + suffix) if first else ""})
    winner = rows[5][0]["name"] if rows[5] else "N/A"
    runner_up = rows[6][0]["name"] if rows[6] else "N/A"
    cards.append({"label": "Winner", "value": winner, "detail": f"Runner up: {runner_up}"})

    return result(
        f"Season highlights - {season}",
        [_cards("Season " + season, cards)],
    )


# --------------------------------------------------------------------------- #
# 15. Number of matches judged by a particular umpire
# --------------------------------------------------------------------------- #
def q15(i):
    umpire = i["umpire"]
    rows = run_query(
        """
        SELECT
            u.umpire_name AS `Umpire`,
            COUNT(mu.match_id) AS `Matches Officiated`
        FROM umpires u
        JOIN match_umpire mu ON u.umpire_id = mu.umpire_id
        WHERE u.umpire_name = %s
        GROUP BY u.umpire_id, u.umpire_name
        """,
        (umpire,),
    )
    return result(
        f"Matches officiated - {umpire}",
        [_table("Umpire record", ["Umpire", "Matches Officiated"], rows)],
    )


# --------------------------------------------------------------------------- #
# 16. Most hundreds and fifties per season
# --------------------------------------------------------------------------- #
def q16(i):
    rows = run_query(
        """
        WITH innings AS (
            SELECT md.season, d.match_id, d.innings, d.batter_id, SUM(d.runs_batter) AS runs
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            GROUP BY md.season, d.match_id, d.innings, d.batter_id
        ),
        agg AS (
            SELECT season, batter_id,
                   SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) AS hundreds,
                   SUM(CASE WHEN runs >= 50 THEN 1 ELSE 0 END) AS fifties
            FROM innings
            GROUP BY season, batter_id
        ),
        ranked AS (
            SELECT season, batter_id, hundreds, fifties,
                   RANK() OVER (PARTITION BY season ORDER BY hundreds DESC, fifties DESC, batter_id) AS hr,
                   RANK() OVER (PARTITION BY season ORDER BY fifties DESC, hundreds DESC, batter_id) AS fr
            FROM agg
        )
        SELECT
            s.season AS `Season`,
            ph.player_name AS `Most Hundreds`,
            a.hundreds AS `Hundreds`,
            pf.player_name AS `Most Fifties`,
            a2.fifties AS `Fifties`
        FROM (SELECT DISTINCT season FROM ranked) s
        LEFT JOIN ranked a ON s.season = a.season AND a.hr = 1
        LEFT JOIN ranked a2 ON s.season = a2.season AND a2.fr = 1
        LEFT JOIN players ph ON a.batter_id = ph.player_id
        LEFT JOIN players pf ON a2.batter_id = pf.player_id
        ORDER BY s.season
        """
    )
    return result(
        "Most hundreds and fifties per season",
        [_table("Hundreds & Fifties",
                ["Season", "Most Hundreds", "Hundreds", "Most Fifties", "Fifties"], rows)],
    )


# --------------------------------------------------------------------------- #
# 17. Most 5 wicket takers in a match per season
# --------------------------------------------------------------------------- #
def q17(i):
    rows = run_query(
        """
        WITH match_wkts AS (
            SELECT md.season, d.match_id, d.bowler_id,
                   COUNT(DISTINCT ds.key) AS wkts
            FROM (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
                WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds
            JOIN delivery d
                ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.over = d.over AND ds.ball = d.ball
            JOIN match_details md ON d.match_id = md.match_id
            GROUP BY md.season, d.match_id, d.bowler_id
        ),
        agg AS (
            SELECT season, bowler_id, COUNT(*) AS five_wicket_hauls
            FROM match_wkts
            WHERE wkts >= 5
            GROUP BY season, bowler_id
        )
        SELECT
            a.season AS `Season`,
            p.player_name AS `Bowler`,
            a.five_wicket_hauls AS `5-Wicket Hauls`
        FROM agg a
        JOIN players p ON a.bowler_id = p.player_id
        ORDER BY a.season, a.five_wicket_hauls DESC
        """
    )
    return result(
        "Bowlers with 5+ wickets in a match per season",
        [_table("Five-wicket hauls", ["Season", "Bowler", "5-Wicket Hauls"], rows)],
    )


# --------------------------------------------------------------------------- #
# 18. Bowler vs Batter comparison
# --------------------------------------------------------------------------- #
def q18(i):
    bowler, batter = i["bowler"], i["batter"]
    if bowler == batter:
        return result(
            f"Bowler vs Batter",
            [_note("Please choose two different players — a bowler and a batter.")],
        )
    rows = run_query(
        """
        SELECT
            bo.player_name AS `Bowler`,
            ba.player_name AS `Batter`,
            COUNT(d.batter_id) AS `Balls Bowled`,
            SUM(d.runs_batter) AS `Runs Scored`,
            COUNT(DISTINCT CONCAT(ds.match_id, '-', ds.innings, '-', ds.over, '-', ds.ball)) AS `Times Dismissed`,
            ROUND(SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(d.batter_id), 0), 2) AS `Batter Strike Rate`,
            ROUND(SUM(d.runs_batter) * 1.0 / NULLIF(COUNT(DISTINCT CONCAT(ds.match_id, '-', ds.innings, '-', ds.over, '-', ds.ball)), 0), 2) AS `Batter Average`
        FROM delivery d
        JOIN players bo ON d.bowler_id = bo.player_id
        JOIN players ba ON d.batter_id = ba.player_id
        LEFT JOIN dismissal ds
            ON d.match_id = ds.match_id AND d.innings = ds.innings
            AND d.over = ds.over AND d.ball = ds.ball
        WHERE bo.player_name = %s AND ba.player_name = %s
        GROUP BY bo.player_name, ba.player_name
        """,
        (bowler, batter),
    )
    if not rows:
        return result(
            f"Bowler vs Batter - {bowler} vs {batter}",
            [_note(f"No balls recorded between {bowler} (bowler) and {batter} (batter) in the dataset. Try another matchup.")],
        )
    return result(
        f"Bowler vs Batter - {bowler} vs {batter}",
        [_table("Head to head",
                ["Bowler", "Batter", "Balls Bowled", "Runs Scored", "Times Dismissed",
                 "Batter Strike Rate", "Batter Average"], rows)],
    )


# --------------------------------------------------------------------------- #
# 19. Player's best season (highest runs/wickets)
# --------------------------------------------------------------------------- #
def q19(i):
    player = i["player"]
    bat_season, bowl_season, bat_all, bowl_all = run_many([
        ("""
            SELECT md.season AS `season`, SUM(d.runs_batter) AS `runs`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.batter_id = p.player_id
            WHERE p.player_name = %s
            GROUP BY md.season
            ORDER BY runs DESC, season
            LIMIT 1
        """, (player,)),
        ("""
            SELECT md.season AS `season`, COUNT(DISTINCT ds.key) AS `wickets`
            FROM (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
                WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds
            JOIN delivery d
                ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.over = d.over AND ds.ball = d.ball
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.bowler_id = p.player_id
            WHERE p.player_name = %s
            GROUP BY md.season
            ORDER BY wickets DESC, season
            LIMIT 1
        """, (player,)),
        ("""
            SELECT md.season AS `Season`, SUM(d.runs_batter) AS `Runs`
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.batter_id = p.player_id
            WHERE p.player_name = %s
            GROUP BY md.season
            ORDER BY md.season
        """, (player,)),
        ("""
            SELECT md.season AS `Season`, COUNT(DISTINCT ds.key) AS `Wickets`
            FROM (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
                WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds
            JOIN delivery d
                ON ds.match_id = d.match_id AND ds.innings = d.innings
                AND ds.over = d.over AND ds.ball = d.ball
            JOIN match_details md ON d.match_id = md.match_id
            JOIN players p ON d.bowler_id = p.player_id
            WHERE p.player_name = %s
            GROUP BY md.season
            ORDER BY md.season
        """, (player,)),
    ])
    cards = []
    if bat_season:
        cards.append({"label": "Best Batting Season", "value": bat_season[0]["season"],
                      "detail": f"{bat_season[0]['runs']} runs"})
    else:
        cards.append({"label": "Best Batting Season", "value": "N/A"})
    if bowl_season:
        cards.append({"label": "Best Bowling Season", "value": bowl_season[0]["season"],
                      "detail": f"{bowl_season[0]['wickets']} wickets"})
    else:
        cards.append({"label": "Best Bowling Season", "value": "N/A"})
    sections = [_cards("Summary", cards)]
    if bat_all:
        sections.append(_table("Runs by season", ["Season", "Runs"], bat_all))
    if bowl_all:
        sections.append(_table("Wickets by season", ["Season", "Wickets"], bowl_all))
    return result(f"Best season - {player}", sections)


# --------------------------------------------------------------------------- #
# 20. Player strike rate & average per season
# --------------------------------------------------------------------------- #
def q20(i):
    player = i["player"]
    rows = run_query(
        """
        WITH bat AS (
            SELECT md.season, d.batter_id,
                   SUM(d.runs_batter) AS runs,
                   COUNT(d.batter_id) AS balls,
                   SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS fours,
                   SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id
            WHERE d.batter_id = (SELECT player_id FROM players WHERE player_name = %s)
            GROUP BY md.season, d.batter_id
        ),
        outs AS (
            SELECT md.season, ds.player_out_id, COUNT(DISTINCT ds.key) AS dismissals
            FROM (
                SELECT match_id, innings, `over`, ball, player_out_id,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
            ) ds
            JOIN match_details md ON ds.match_id = md.match_id
            WHERE ds.player_out_id = (SELECT player_id FROM players WHERE player_name = %s)
            GROUP BY md.season, ds.player_out_id
        )
        SELECT
            b.season AS `Season`,
            b.runs AS `Runs`,
            b.balls AS `Balls`,
            b.fours AS `Fours`,
            b.sixes AS `Sixes`,
            ROUND(b.runs * 100.0 / NULLIF(b.balls, 0), 2) AS `Strike Rate`,
            ROUND(b.runs * 1.0 / NULLIF(o.dismissals, 0), 2) AS `Batting Average`,
            COALESCE(o.dismissals, 0) AS `Dismissals`
        FROM bat b
        LEFT JOIN outs o ON b.season = o.season
        ORDER BY b.season
        """,
        (player, player),
    )
    return result(
        f"Strike rate & average by season - {player}",
        [_table("Per-season batting",
                ["Season", "Runs", "Balls", "Fours", "Sixes", "Strike Rate",
                 "Batting Average", "Dismissals"], rows)],
    )


# --------------------------------------------------------------------------- #
# 21. Highest partnerships per season
# --------------------------------------------------------------------------- #
def q21(i):
    season = (i.get("season") or "").strip()
    sql = """
        WITH ordered AS (
            SELECT d.match_id, d.innings, d.`over`, d.ball, d.runs_total,
                   d.batter_id, d.non_striker_id,
                   ROW_NUMBER() OVER (PARTITION BY d.match_id, d.innings ORDER BY d.`over`, d.ball) AS rn,
                   CASE WHEN ds.key IS NOT NULL THEN 1 ELSE 0 END AS is_wicket
            FROM delivery d
            LEFT JOIN (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal
            ) ds
                ON d.match_id = ds.match_id AND d.innings = ds.innings
                AND d.over = ds.over AND d.ball = ds.ball
        ),
        part_groups AS (
            SELECT match_id, innings, runs_total, batter_id, non_striker_id,
                   COALESCE(SUM(is_wicket) OVER (
                       PARTITION BY match_id, innings ORDER BY rn
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                   ), 0) AS grp
            FROM ordered
        ),
        part_agg AS (
            SELECT match_id, innings, grp, SUM(runs_total) AS runs,
                   MIN(LEAST(COALESCE(batter_id, 0), COALESCE(non_striker_id, 0))) AS b1,
                   MAX(GREATEST(COALESCE(batter_id, 0), COALESCE(non_striker_id, 0))) AS b2
            FROM part_groups
            GROUP BY match_id, innings, grp
        ),
        with_season AS (
            SELECT md.season, md.date, pa.match_id, pa.runs, pa.b1, pa.b2
            FROM part_agg pa
            JOIN match_details md ON pa.match_id = md.match_id
        ),
        ranked AS (
            SELECT season, date, match_id, runs, b1, b2,
                   ROW_NUMBER() OVER (PARTITION BY season ORDER BY runs DESC, date, match_id) AS rk
            FROM with_season
        )
        SELECT
            r.season AS `Season`,
            r.date AS `Date`,
            p1.player_name AS `Batter 1`,
            p2.player_name AS `Batter 2`,
            r.runs AS `Partnership Runs`
        FROM ranked r
        JOIN players p1 ON r.b1 = p1.player_id
        JOIN players p2 ON r.b2 = p2.player_id
        WHERE r.rk = 1
    """
    params = []
    if season:
        sql += " AND r.season = %s"
        params.append(season)
    sql += " ORDER BY r.season"
    rows = run_query(sql, params)
    return result(
        "Highest partnerships per season",
        [_table("Best partnership each season",
                ["Season", "Date", "Batter 1", "Batter 2", "Partnership Runs"], rows)],
    )


QUERIES = [
    {"id": 1, "title": "List of all IPL teams", "desc": "Every team that has ever played in the IPL.", "inputs": [], "handler": q1},
    {"id": 2, "title": "List of all players", "desc": "Every player that has appeared in an IPL match.", "inputs": [], "handler": q2},
    {"id": 3, "title": "List of all umpires", "desc": "Every umpire that has officiated an IPL match.", "inputs": [], "handler": q3},
    {"id": 4, "title": "List of all venues", "desc": "Every stadium that has hosted an IPL match.", "inputs": [], "handler": q4},
    {"id": 5, "title": "List of all matches played in IPL", "desc": "All matches with teams, venue and result. Optionally filter by season.", "inputs": [INPUT_SEASON_OPT], "handler": q5},
    {"id": 6, "title": "Particular player stats in IPL", "desc": "Career batting & bowling statistics for a chosen player.", "inputs": [INPUT_PLAYER], "handler": q6},
    {"id": 7, "title": "Man of the Match record of a player", "desc": "How many times a player was Man of the Match and in which matches.", "inputs": [INPUT_PLAYER], "handler": q7},
    {"id": 8, "title": "Head to Head stats of any 2 teams", "desc": "Overall record between two chosen teams.", "inputs": [INPUT_TEAM1, INPUT_TEAM2], "handler": q8},
    {"id": 9, "title": "Player team history", "desc": "Which team a player represented in which season.", "inputs": [INPUT_PLAYER], "handler": q9},
    {"id": 10, "title": "Average first innings score at a stadium", "desc": "Average first innings total at a chosen venue, overall and by season.", "inputs": [INPUT_VENUE], "handler": q10},
    {"id": 11, "title": "Total number of 4s or 6s per season", "desc": "Count of boundaries (fours or sixes) hit in each season.", "inputs": [INPUT_BOUNDARY], "handler": q11},
    {"id": 12, "title": "Average powerplay score of a team per season", "desc": "Average runs in the first 6 overs for each team and season.", "inputs": [INPUT_SEASON_OPT], "handler": q12},
    {"id": 13, "title": "Average powerplay wickets taken per season", "desc": "Average wickets taken in the first 6 overs for each team and season.", "inputs": [INPUT_SEASON_OPT], "handler": q13},
    {"id": 14, "title": "Particular season stats", "desc": "Orange cap, purple cap, most 4s, most 6s, most dot balls, winner and runner-up.", "inputs": [INPUT_SEASON], "handler": q14},
    {"id": 15, "title": "Number of matches judged by an umpire", "desc": "How many matches a chosen umpire has officiated.", "inputs": [INPUT_UMPIRE], "handler": q15},
    {"id": 16, "title": "Most hundreds and fifties per season", "desc": "The player with the most centuries and the most fifties in each season.", "inputs": [], "handler": q16},
    {"id": 17, "title": "Most 5-wicket hauls in a match per season", "desc": "Bowlers with 5+ wickets in a single match, per season.", "inputs": [], "handler": q17},
    {"id": 18, "title": "Bowler vs Batter comparison", "desc": "Head-to-head record between a chosen bowler and a chosen batter.", "inputs": [
        {"name": "bowler", "label": "Bowler", "type": "select", "source": "players"},
        {"name": "batter", "label": "Batter", "type": "select", "source": "players"},
    ], "handler": q18},
    {"id": 19, "title": "Player's best season", "desc": "The season in which a player scored the most runs and took the most wickets.", "inputs": [INPUT_PLAYER], "handler": q19},
    {"id": 20, "title": "Player strike rate & average per season", "desc": "Batting strike rate and average for a player in every season.", "inputs": [INPUT_PLAYER], "handler": q20},
    {"id": 21, "title": "Highest partnerships per season", "desc": "The best batting partnership of each season.", "inputs": [INPUT_SEASON_OPT], "handler": q21},
]


def get_query_meta():
    return [{"id": q["id"], "title": q["title"], "desc": q["desc"], "inputs": q["inputs"]} for q in QUERIES]


def run_query_by_id(query_id, inputs):
    for q in QUERIES:
        if q["id"] == query_id:
            return q["handler"](inputs)
    raise ValueError(f"Unknown query id: {query_id}")
