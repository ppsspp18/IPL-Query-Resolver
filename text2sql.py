"""Schema-aware Text-to-SQL pipeline.

Flow (with optional streaming events emitted between stages):

    1. validation       - basic question hygiene
    2. sql_generation   - intent detection + schema-aware SQL generation
                           (LLM first if configured, rule-based engine otherwise)
    3. query_execution  - read-only validation + execution against MySQL
    4. result           - structured answer

Every generated statement is guaranteed to be read-only: a whitelist blocks
mutation keywords, only tables present in the introspected schema are allowed,
and the SQL is pre-validated with EXPLAIN before it runs.
"""
from __future__ import annotations

import datetime
import decimal
import re
import time
from typing import Any, Callable, Optional

from starlette.concurrency import run_in_threadpool

from db import get_readonly_connection
from llm import chat_completion, is_configured
from schema import get_schema_context, normalize, resolve_entities, resolve_season

MAX_RESULT_ROWS = 500
MAX_QUESTION_LEN = 500

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class Text2SQLError(Exception):
    """Base error for the pipeline."""


class ValidationError(Text2SQLError):
    """Question failed input validation."""


class SQLGenerationError(Text2SQLError):
    """Could not produce SQL for the question."""


class ExecutionError(Text2SQLError):
    """Generated SQL was rejected or failed at execution time."""


# --------------------------------------------------------------------------- #
# Read-only guard
# --------------------------------------------------------------------------- #
_BANNED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|replace|"
    r"rename|call|lock|unlock|load|show|describe|analyze|optimize|kill|shutdown|"
    r"use|commit|rollback|savepoint)\b",
    re.IGNORECASE,
)
_MUTATION_HINTS = re.compile(r"\b(update|delete|insert)\b", re.IGNORECASE)


def enforce_read_only(sql: str) -> str:
    """Return a single read-only SELECT (or WITH..SELECT) statement.

    Raises ExecutionError if the statement could mutate the database.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ExecutionError("Empty SQL statement.")
    if ";" in cleaned:
        raise ExecutionError("Multiple statements are not allowed.")
    head = cleaned.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise ExecutionError("Only SELECT statements are allowed.")
    if _BANNED.search(cleaned):
        raise ExecutionError("Statement contains disallowed (mutating) keywords.")
    return cleaned


def _extract_tables(sql: str) -> set[str]:
    """Best-effort extraction of referenced table names (excluding CTEs)."""
    tables = set()
    for m in re.finditer(
        r"(?:from|join|into|update|table)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?",
        sql,
        re.IGNORECASE,
    ):
        tables.add(m.group(1).lower())
    # CTEs defined via WITH are not physical tables.
    for m in re.finditer(r"(?:with|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", sql, re.IGNORECASE):
        tables.discard(m.group(1).lower())
    return tables


def validate_sql(sql: str, params: Optional[list] = None) -> tuple[bool, str]:
    """Validate a SELECT against the live schema using EXPLAIN.

    Returns (ok, error_message).
    """
    try:
        sql = enforce_read_only(sql)
    except ExecutionError as e:
        return False, str(e)
    known = {t.lower() for t in get_schema_context()["tables"]}
    unknown = _extract_tables(sql) - known
    if unknown:
        return False, f"Unknown table(s): {', '.join(sorted(unknown))}."
    conn = get_readonly_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN {sql}", params or ())
            cur.fetchall()
        return True, ""
    except Exception as e:  # noqa: BLE001 - propagate as validation failure
        return False, str(e)
    finally:
        conn.close()


def _json_safe(value):
    """Convert DB types (Decimal, date, timedelta, bytes) to JSON-safe values."""
    if value is None:
        return None
    if isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, decimal.Decimal):
        f = float(value)
        return int(f) if f == int(f) else round(f, 6)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return value


def execute_sql(
    sql: str, params: Optional[list] = None, limit: int = MAX_RESULT_ROWS
) -> dict[str, Any]:
    """Execute read-only SQL and return rows plus execution metadata."""
    sql = enforce_read_only(sql)
    conn = get_readonly_connection()
    start = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    except Exception as e:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        raise ExecutionError(str(e)) from e
    finally:
        conn.close()
    rows = [
        {k: _json_safe(v) for k, v in row.items()}
        for row in rows
    ]
    truncated = len(rows) > limit
    return {
        "columns": cols,
        "rows": rows[:limit],
        "row_count": len(rows),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }


# --------------------------------------------------------------------------- #
# SQL templates (canonical read-only queries per intent)
# --------------------------------------------------------------------------- #
def _matches_sql(p: dict) -> tuple[str, list]:
    sql = """
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
    """
    params = []
    if p.get("season"):
        sql += " WHERE md.season = %s"
        params.append(p["season"])
    sql += " ORDER BY md.date, md.match_id"
    return sql, params


def _player_boundaries_sql(p: dict) -> tuple[str, list]:
    sql = """
        SELECT p.player_name AS Player, md.season AS Season, COUNT(*) AS Boundaries
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        JOIN players p ON d.batter_id = p.player_id
        WHERE p.player_name = %s AND d.runs_batter = %s
    """
    params = [p["player"], int(p["boundary"])]
    if p.get("team"):
        sql += " AND d.bowling_team_id = (SELECT team_id FROM teams WHERE team_name = %s)"
        params.append(p["team"])
    if p.get("season"):
        sql += " AND md.season = %s"
        params.append(p["season"])
    sql += " GROUP BY p.player_name, md.season ORDER BY md.season"
    return sql, params


def _boundaries_per_season_sql(p: dict) -> tuple[str, list]:
    return (
        """
        SELECT md.season AS Season, COUNT(*) AS Total
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        WHERE d.runs_batter = %s
        GROUP BY md.season
        ORDER BY md.season
        """,
        [int(p["boundary"])],
    )


def _powerplay_sql(p: dict, wickets: bool) -> tuple[str, list]:
    if wickets:
        metric = "ROUND(AVG(pp.wkts), 2) AS Avg_Wickets_Powerplay"
        sub = """
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
                    AND d.`over` = ds.`over` AND d.ball = ds.ball
            WHERE d.`over` < 6
            GROUP BY d.match_id, d.innings, d.bowling_team_id
        """
    else:
        metric = "ROUND(AVG(pp.runs), 2) AS Avg_Powerplay_Score"
        sub = """
            SELECT match_id, innings, batting_team_id, SUM(runs_total) AS runs
            FROM delivery
            WHERE `over` < 6
            GROUP BY match_id, innings, batting_team_id
        """
    sql = f"""
        SELECT md.season AS Season, t.team_name AS Team, {metric}
        FROM match_details md
        JOIN ( {sub} ) pp ON md.match_id = pp.match_id
        JOIN teams t ON pp.{'bowling_team_id' if wickets else 'batting_team_id'} = t.team_id
    """
    params = []
    if p.get("season"):
        sql += " WHERE md.season = %s"
        params.append(p["season"])
    sql += " GROUP BY md.season, t.team_name ORDER BY md.season, t.team_name"
    return sql, params


def _season_winner_sql(p: dict) -> tuple[str, list]:
    return (
        """
        SELECT w.team_name AS Champion,
               (CASE WHEN mt.team1_id = mr.winner_id THEN t2.team_name ELSE t1.team_name END) AS Runner_Up
        FROM match_details md
        JOIN match_result mr ON md.match_id = mr.match_id
        JOIN match_teams mt ON md.match_id = mt.match_id
        JOIN teams w ON mr.winner_id = w.team_id
        JOIN teams t1 ON mt.team1_id = t1.team_id
        JOIN teams t2 ON mt.team2_id = t2.team_id
        WHERE md.season = %s AND LOWER(TRIM(md.match_type)) = 'final'
        ORDER BY md.date DESC
        LIMIT 1
        """,
        [p["season"]],
    )


def _cap_sql(p: dict, kind: str) -> tuple[str, list]:
    if kind == "orange":
        return (
            """
            SELECT p.player_name AS Player, SUM(d.runs_batter) AS Runs
            FROM delivery d
            JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
            JOIN players p ON d.batter_id = p.player_id
            GROUP BY p.player_id, p.player_name
            ORDER BY Runs DESC, p.player_name
            LIMIT 1
            """,
            [p["season"]],
        )
    return (
        """
        SELECT p.player_name AS Player, COUNT(DISTINCT ds.key) AS Wickets
        FROM (
            SELECT match_id, innings, `over`, ball,
                   CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
            FROM dismissal
            WHERE wicket_kind NOT IN ('run out', 'retired hurt')
        ) ds
        JOIN delivery d ON ds.match_id = d.match_id AND ds.innings = d.innings
            AND ds.`over` = d.`over` AND ds.ball = d.ball
        JOIN match_details md ON d.match_id = md.match_id AND md.season = %s
        JOIN players p ON d.bowler_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Wickets DESC, p.player_name
        LIMIT 1
        """,
        [p["season"]],
    )


def _bowler_vs_batter_sql(p: dict) -> tuple[str, list]:
    bowler, batter = p["bowler"], p["batter"]
    # The dataset abbreviates names; if the resolved "bowler" has no bowling
    # deliveries but the "batter" does, swap so stats read correctly.
    if _balls_bowled(bowler) < _balls_bowled(batter):
        bowler, batter = batter, bowler
    return (
        """
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
        WHERE bo.player_name = %s AND ba.player_name = %s
        GROUP BY bo.player_name, ba.player_name
        """,
        [bowler, batter],
    )


def _balls_bowled(player: str) -> int:
    from db import run_query

    rows = run_query(
        """
        SELECT COUNT(*) AS n FROM delivery d
        JOIN players p ON d.bowler_id = p.player_id
        WHERE p.player_name = %s
        """,
        (player,),
    )
    return rows[0]["n"] if rows else 0


def _head_to_head_sql(p: dict) -> tuple[str, list]:
    return (
        """
        SELECT ta.team_name AS Team_A, tb.team_name AS Team_B,
               COUNT(*) AS Matches_Played,
               SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) AS Team_A_Wins,
               SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) AS Team_B_Wins,
               SUM(CASE WHEN mr.winner_id IS NULL OR mr.winner_id NOT IN (ta.team_id, tb.team_id)
                        THEN 1 ELSE 0 END) AS No_Result,
               ROUND(SUM(CASE WHEN mr.winner_id = ta.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS Team_A_Win_Pct,
               ROUND(SUM(CASE WHEN mr.winner_id = tb.team_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS Team_B_Win_Pct
        FROM match_teams mt
        CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = %s) ta
        CROSS JOIN (SELECT team_id, team_name FROM teams WHERE team_name = %s) tb
        LEFT JOIN match_result mr ON mt.match_id = mr.match_id
        WHERE (mt.team1_id = ta.team_id AND mt.team2_id = tb.team_id)
           OR (mt.team1_id = tb.team_id AND mt.team2_id = ta.team_id)
        """,
        [p["team1"], p["team2"]],
    )


def _highest_partnership_sql(p: dict) -> tuple[str, list]:
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
            ) ds ON d.match_id = ds.match_id AND d.innings = ds.innings
                AND d.`over` = ds.`over` AND d.ball = ds.ball
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
        WHERE r.rk = 1
    """
    params = []
    if p.get("season"):
        sql += " AND r.season = %s"
        params.append(p["season"])
    sql += " ORDER BY r.season"
    return sql, params


TEMPLATES: dict[str, Callable[[dict], tuple[str, list]]] = {
    "list_teams": lambda p: ("SELECT team_name AS Team FROM teams ORDER BY team_name", []),
    "list_players": lambda p: ("SELECT player_name AS Player FROM players ORDER BY player_name", []),
    "list_umpires": lambda p: ("SELECT umpire_name AS Umpire FROM umpires ORDER BY umpire_name", []),
    "list_venues": lambda p: ("SELECT venue_name AS Venue, venue_city AS City FROM venues ORDER BY venue_name", []),
    "list_matches": _matches_sql,
    "player_career_batting": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches,
               SUM(d.runs_batter) AS Runs,
               COUNT(d.batter_id) AS Balls_Faced,
               SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS Fours,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS Sixes,
               ROUND(SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(d.batter_id), 0), 2) AS Strike_Rate
        FROM players p
        LEFT JOIN delivery d ON p.player_id = d.batter_id
        WHERE p.player_name = %s
        GROUP BY p.player_id, p.player_name
        """,
        [p["player"]],
    ),
    "player_career_bowling": lambda p: (
        """
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
        WHERE p.player_name = %s
        GROUP BY p.player_id, p.player_name
        """,
        [p["player"]],
    ),
    "player_motm": lambda p: (
        """
        SELECT COUNT(*) AS Man_of_the_Match_Awards
        FROM match_result mr
        JOIN players p ON mr.player_of_match_id = p.player_id
        WHERE p.player_name = %s
        """,
        [p["player"]],
    ),
    "player_team_history": lambda p: (
        """
        SELECT md.season AS Season, bt.team_name AS Team, COUNT(DISTINCT d.match_id) AS Matches_Played
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        JOIN teams bt ON d.batting_team_id = bt.team_id
        JOIN players p ON d.batter_id = p.player_id
        WHERE p.player_name = %s
        GROUP BY md.season, bt.team_name
        ORDER BY md.season, bt.team_name
        """,
        [p["player"]],
    ),
    "player_best_season": lambda p: (
        """
        SELECT md.season AS Season, SUM(d.runs_batter) AS Runs
        FROM delivery d
        JOIN match_details md ON d.match_id = md.match_id
        JOIN players p ON d.batter_id = p.player_id
        WHERE p.player_name = %s
        GROUP BY md.season
        ORDER BY Runs DESC, Season
        LIMIT 1
        """,
        [p["player"]],
    ),
    "player_sr_avg": lambda p: (
        """
        WITH bat AS (
            SELECT md.season, d.batter_id,
                   SUM(d.runs_batter) AS runs, COUNT(d.batter_id) AS balls,
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
            ) ds JOIN match_details md ON ds.match_id = md.match_id
            WHERE ds.player_out_id = (SELECT player_id FROM players WHERE player_name = %s)
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
        [p["player"], p["player"]],
    ),
    "head_to_head": _head_to_head_sql,
    "venue_avg_first_innings": lambda p: (
        """
        SELECT v.venue_name AS Venue, v.venue_city AS City,
               COUNT(DISTINCT inn1.match_id) AS Matches,
               ROUND(AVG(inn1.runs), 2) AS Avg_First_Innings_Score
        FROM venues v
        JOIN match_details md ON v.venue_id = md.venue_id
        JOIN (SELECT match_id, SUM(runs_total) AS runs FROM delivery WHERE innings = 1 GROUP BY match_id) inn1
             ON md.match_id = inn1.match_id
        WHERE v.venue_name = %s
        GROUP BY v.venue_id, v.venue_name, v.venue_city
        """,
        [p["venue"]],
    ),
    "boundaries_per_season": _boundaries_per_season_sql,
    "player_boundaries": _player_boundaries_sql,
    "powerplay_runs": lambda p: _powerplay_sql(p, wickets=False),
    "powerplay_wickets": lambda p: _powerplay_sql(p, wickets=True),
    "season_winner": _season_winner_sql,
    "orange_cap": lambda p: _cap_sql(p, "orange"),
    "purple_cap": lambda p: _cap_sql(p, "purple"),
    "umpire_record": lambda p: (
        """
        SELECT u.umpire_name AS Umpire, COUNT(mu.match_id) AS Matches_Officiated
        FROM umpires u JOIN match_umpire mu ON u.umpire_id = mu.umpire_id
        WHERE u.umpire_name = %s
        GROUP BY u.umpire_id, u.umpire_name
        """,
        [p["umpire"]],
    ),
    "hundreds_fifties": lambda p: (
        """
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
        [],
    ),
    "five_wicket_hauls": lambda p: (
        """
        WITH match_wkts AS (
            SELECT md.season, d.match_id, d.bowler_id, COUNT(DISTINCT ds.key) AS wkts
            FROM (
                SELECT match_id, innings, `over`, ball,
                       CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
                FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')
            ) ds
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
        [],
    ),
    "bowler_vs_batter": _bowler_vs_batter_sql,
    "highest_partnership": _highest_partnership_sql,
    "top_run_scorer": lambda p: (
        """
        SELECT p.player_name AS Player, SUM(d.runs_batter) AS Runs
        FROM delivery d JOIN players p ON d.batter_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Runs DESC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "top_wicket_taker": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(DISTINCT ds.key) AS Wickets
        FROM (
            SELECT match_id, innings, `over`, ball,
                   CONCAT(match_id, '-', innings, '-', `over`, '-', ball) AS `key`
            FROM dismissal WHERE wicket_kind NOT IN ('run out', 'retired hurt')
        ) ds
        JOIN delivery d ON ds.match_id = d.match_id AND ds.innings = d.innings
            AND ds.`over` = d.`over` AND ds.ball = d.ball
        JOIN players p ON d.bowler_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Wickets DESC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "most_sixes": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(*) AS Sixes
        FROM delivery d JOIN players p ON d.batter_id = p.player_id
        WHERE d.runs_batter = 6
        GROUP BY p.player_id, p.player_name
        ORDER BY Sixes DESC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "most_fours": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(*) AS Fours
        FROM delivery d JOIN players p ON d.batter_id = p.player_id
        WHERE d.runs_batter = 4
        GROUP BY p.player_id, p.player_name
        ORDER BY Fours DESC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "most_matches": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches
        FROM delivery d JOIN players p ON d.batter_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Matches DESC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "team_most_titles": lambda p: (
        """
        SELECT w.team_name AS Team, COUNT(*) AS Titles
        FROM match_details md
        JOIN match_result mr ON md.match_id = mr.match_id
        JOIN teams w ON mr.winner_id = w.team_id
        WHERE LOWER(TRIM(md.match_type)) = 'final'
        GROUP BY w.team_id, w.team_name
        ORDER BY Titles DESC, w.team_name
        """,
        [],
    ),
    "toss_stats": lambda p: (
        """
        SELECT t.team_name AS Team, COUNT(*) AS Tosses_Won
        FROM match_toss mt JOIN teams t ON mt.toss_winner_id = t.team_id
        GROUP BY t.team_id, t.team_name
        ORDER BY Tosses_Won DESC, t.team_name
        """,
        [],
    ),
    "player_matches": lambda p: (
        """
        SELECT p.player_name AS Player, COUNT(DISTINCT d.match_id) AS Matches
        FROM players p LEFT JOIN delivery d ON p.player_id = d.batter_id
        WHERE p.player_name = %s
        GROUP BY p.player_id, p.player_name
        """,
        [p["player"]],
    ),
    "best_economy": lambda p: (
        """
        SELECT p.player_name AS Player,
               ROUND(SUM(d.runs_total) * 6.0 / NULLIF(COUNT(d.bowler_id), 0), 2) AS Economy,
               COUNT(d.bowler_id) AS Balls_Bowled
        FROM delivery d JOIN players p ON d.bowler_id = p.player_id
        GROUP BY p.player_id, p.player_name
        HAVING COUNT(d.bowler_id) >= 600
        ORDER BY Economy ASC, p.player_name
        LIMIT 1
        """,
        [],
    ),
    "top_venue_first_innings": lambda p: (
        """
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
        [],
    ),
}


INTENT_META: dict[str, dict] = {
    "list_teams": {"title": "List all IPL teams", "desc": "Every franchise that has played in the IPL."},
    "list_players": {"title": "List all players", "desc": "Every player who appeared in an IPL match."},
    "list_umpires": {"title": "List all umpires", "desc": "Every umpire who officiated a match."},
    "list_venues": {"title": "List all venues", "desc": "Every stadium with its host city."},
    "list_matches": {"title": "List matches", "desc": "Matches with teams, venue and result."},
    "player_career_batting": {"title": "Player batting career", "desc": "Career batting statistics for a player."},
    "player_career_bowling": {"title": "Player bowling career", "desc": "Career bowling statistics for a player."},
    "player_motm": {"title": "Man of the Match count", "desc": "How many times a player was Man of the Match."},
    "player_team_history": {"title": "Player team history", "desc": "Which team a player played for each season."},
    "player_best_season": {"title": "Player best season", "desc": "The season with the most runs for a player."},
    "player_sr_avg": {"title": "Player strike rate & average", "desc": "Per-season strike rate and average."},
    "head_to_head": {"title": "Head-to-head", "desc": "Overall record between two teams."},
    "venue_avg_first_innings": {"title": "Venue first-innings average", "desc": "Average first-innings score at a venue."},
    "boundaries_per_season": {"title": "Boundaries per season", "desc": "Fours or sixes hit in each season."},
    "player_boundaries": {"title": "Player boundaries", "desc": "Fours or sixes hit by a player."},
    "powerplay_runs": {"title": "Powerplay batting", "desc": "Average powerplay (first 6 overs) score."},
    "powerplay_wickets": {"title": "Powerplay bowling", "desc": "Average powerplay wickets taken."},
    "season_winner": {"title": "Season winner", "desc": "Champion and runner-up of a season."},
    "orange_cap": {"title": "Orange cap", "desc": "Highest run scorer of a season."},
    "purple_cap": {"title": "Purple cap", "desc": "Highest wicket taker of a season."},
    "umpire_record": {"title": "Umpire record", "desc": "Matches officiated by an umpire."},
    "hundreds_fifties": {"title": "Hundreds & fifties", "desc": "Most centuries and fifties each season."},
    "five_wicket_hauls": {"title": "Five-wicket hauls", "desc": "Bowlers with 5+ wickets in a match, per season."},
    "bowler_vs_batter": {"title": "Bowler vs batter", "desc": "Head-to-head between a bowler and a batter."},
    "highest_partnership": {"title": "Highest partnership", "desc": "Best batting partnership of a season."},
    "top_run_scorer": {"title": "Top run scorer", "desc": "Highest run scorer of all time."},
    "top_wicket_taker": {"title": "Top wicket taker", "desc": "Highest wicket taker of all time."},
    "most_sixes": {"title": "Most sixes", "desc": "Player with the most sixes all time."},
    "most_fours": {"title": "Most fours", "desc": "Player with the most fours all time."},
    "most_matches": {"title": "Most matches", "desc": "Player who played the most matches."},
    "team_most_titles": {"title": "Most titles", "desc": "Teams ranked by championship titles."},
    "toss_stats": {"title": "Toss statistics", "desc": "Tosses won by each team."},
    "player_matches": {"title": "Player match count", "desc": "How many matches a player has played."},
    "best_economy": {"title": "Best bowling economy", "desc": "Player with the best career economy rate."},
    "top_venue_first_innings": {"title": "Highest venue first-innings average", "desc": "Venue with the highest average first-innings score."},
}


# --------------------------------------------------------------------------- #
# Intent detection (rule-based classifier)
# --------------------------------------------------------------------------- #
_BOUNDARY_WORDS = (r"four|4\b|six|6\b|boundar")
_PLAYER_BOUNDARY = re.compile(
    r"(?=.*(four|six|4s|6s|boundar))(?=.*(hit|score|did|made|record))",
    re.IGNORECASE,
)


def _has(q: str, *phrases: str) -> bool:
    return any(ph in q for ph in phrases)


def _second_entity(q: str, first: str, etype: str) -> str | None:
    """Re-resolve after removing the first entity's tokens to find a 2nd one."""
    first_tokens = set(normalize(first).split())
    remaining = " ".join(t for t in q.split() if t not in first_tokens)
    return resolve_entities(remaining).get(etype)


def _detect_intent(q: str, ents: dict) -> tuple[str, dict, float]:
    """Return (intent_id, params, confidence) for a normalized question."""
    p = {}
    season = resolve_season(q)
    if season:
        p["season"] = season
    team = ents.get("teams")
    venue = ents.get("venues")
    umpire = ents.get("umpires")
    player = ents.get("players")

    # --- Player + boundary queries ("sixes V Kohli hit against MI") ---
    if player and re.search(r"four|six|4s|6s|boundar", q):
        boundary = 6 if re.search(r"six|6s", q) else 4
        team2 = team if team else None
        return "player_boundaries", {"player": player, "boundary": boundary, **p, **({"team": team2} if team2 else {})}, 0.95

    # --- Head to head (two teams) ---
    if _has(q, "head to head", "h2h", "record between", "versus") and team:
        team2 = _second_entity(q, team, "teams")
        if team2 and team2 != team:
            return "head_to_head", {"team1": team, "team2": team2}, 0.98

    # --- Bowler vs batter (two players) ---
    if player and _has(q, "bowler", "vs", "versus", "bowled to", "against"):
        batter = _second_entity(q, player, "players")
        if batter and batter != player:
            return "bowler_vs_batter", {"bowler": player, "batter": batter}, 0.95

    # --- Boundaries per season ---
    if re.search(_BOUNDARY_WORDS, q) and _has(q, "per season", "each season", "season"):
        boundary = 6 if re.search(r"six|6s", q) else 4
        return "boundaries_per_season", {"boundary": boundary}, 0.95

    # --- All-time leaders (skipped when a season narrows the scope) ---
    if not season:
        if _has(q, "most six", "highest six", "most number of sixes"):
            return "most_sixes", {}, 0.95
        if _has(q, "most four", "highest four", "most number of fours"):
            return "most_fours", {}, 0.95
        if _has(q, "most run", "highest run", "top run", "leading run", "most runs overall"):
            return "top_run_scorer", {}, 0.95
        if _has(q, "most wicket", "highest wicket", "top wicket"):
            return "top_wicket_taker", {}, 0.95
        if _has(q, "most match", "played the most", "most appearances", "most matches"):
            return "most_matches", {}, 0.9
        if _has(q, "most titles", "most championships", "most trophies", "most ipl titles") or ("most" in q and "titles" in q):
            return "team_most_titles", {}, 0.95
        if _has(q, "toss"):
            return "toss_stats", {}, 0.9
        if not player and _has(q, "economy") and _has(q, "best", "lowest", "top"):
            return "best_economy", {}, 0.9
        if not player and _has(q, "first innings") and _has(q, "highest", "best", "top"):
            return "top_venue_first_innings", {}, 0.9

    # --- List / catalogue questions ---
    if _has(q, "list all teams", "all the teams", "teams in the ipl", "which teams"):
        return "list_teams", {}, 0.99
    if _has(q, "list all players", "all the players"):
        return "list_players", {}, 0.99
    if _has(q, "list all umpires", "all the umpires"):
        return "list_umpires", {}, 0.99
    if _has(q, "list all venues", "all the venues", "list all stadiums"):
        return "list_venues", {}, 0.99
    if _has(q, "list matches", "all matches", "list the matches", "matches played in"):
        return "list_matches", p, 0.9

    # --- Player match count / career stats ---
    if player and _has(q, "how many matches", "matches has", "matches played by", "matches played"):
        return "player_matches", {"player": player}, 0.95
    if player and _has(q, "career", "stats", "batting stats", "bowling stats", "runs scored", "wickets", "took", "taken", "economy"):
        if _has(q, "bowl", "wicket", "economy", "took", "taken"):
            return "player_career_bowling", {"player": player}, 0.95
        return "player_career_batting", {"player": player}, 0.95

    # --- Man of the match ---
    if player and _has(q, "man of the match", "motm"):
        return "player_motm", {"player": player}, 0.95

    # --- Player team history ---
    if player and _has(q, "team history", "played for which", "which team"):
        return "player_team_history", {"player": player}, 0.9

    # --- Player best season / strike rate ---
    if player and ("best" in q and "season" in q):
        return "player_best_season", {"player": player}, 0.9
    if player and _has(q, "strike rate", "average per season", "sr"):
        return "player_sr_avg", {"player": player}, 0.95

    # --- Venue ---
    if venue and _has(q, "first innings", "average", "score at", "stadium"):
        return "venue_avg_first_innings", {"venue": venue}, 0.95

    # --- Powerplay ---
    if _has(q, "powerplay") and _has(q, "wicket", "bowl"):
        return "powerplay_wickets", p, 0.9
    if _has(q, "powerplay"):
        return "powerplay_runs", p, 0.9

    # --- Season caps / winner ---
    if season and _has(q, "orange cap", "highest run scorer", "top scorer", "most run"):
        return "orange_cap", {"season": season}, 0.95
    if season and _has(q, "purple cap", "highest wicket", "top wicket", "most wicket"):
        return "purple_cap", {"season": season}, 0.95
    if season and _has(q, "winner", "champion", "won the", "final"):
        return "season_winner", {"season": season}, 0.9

    # --- Umpire ---
    if umpire and _has(q, "umpire", "officiat", "judged"):
        return "umpire_record", {"umpire": umpire}, 0.95

    # --- Hundreds & fifties / five-wicket hauls ---
    if _has(q, "hundred", "century", "fifty"):
        return "hundreds_fifties", {}, 0.9
    if _has(q, "five wicket", "five-wicket", "5 wicket", "5-wicket",
            "five or more wickets", "5 or more wickets", "five-wicket haul"):
        return "five_wicket_hauls", {}, 0.9

    # --- Partnerships ---
    if _has(q, "partnership"):
        return "highest_partnership", p, 0.9

    return None, {}, 0.0


# --------------------------------------------------------------------------- #
# LLM prompt (schema-aware)
# --------------------------------------------------------------------------- #
def _schema_for_llm() -> str:
    ctx = get_schema_context()
    lines = ["Database: MySQL, schema `ipl_normalized`. Read-only (SELECT only).", ""]
    for tname, info in ctx["tables"].items():
        cols = ", ".join(
            f"{c['name']} ({c['type']}{', PK' if c['key'] == 'PRI' else ''})"
            for c in info["columns"]
        )
        lines.append(f"TABLE {tname} — {info['description']}")
        lines.append(f"  columns: {cols}")
        if info["sample_rows"]:
            sample = ", ".join(str(v) for v in list(info["sample_rows"][0].values())[:3])
            lines.append(f"  sample: {sample}")
        lines.append("")
    lines.append("Foreign keys:")
    for fk in ctx["foreign_keys"]:
        lines.append(f"  {fk['table']}.{fk['column']} -> {fk['references']}")
    lines.append("")
    lines.append("Rules:")
    lines.append("- Answer with ONLY a single MySQL SELECT statement, no semicolon, no markdown.")
    lines.append("- Player/umpire names are abbreviated in the data (e.g. 'V Kohli' for Virat Kohli).")
    lines.append("- Use EXACTLY the names provided in the 'Entities detected' list; never alter or 'fix' them.")
    lines.append("- Seasons look like '2007/08' or '2023'.")
    lines.append("- Wickets credited to a bowler must EXCLUDE wicket_kind IN ('run out', 'retired hurt').")
    lines.append("- For economy/average/rate stats, only consider players with a meaningful sample "
                 "(e.g. HAVING at least 500 deliveries bowled or faced).")
    lines.append("- Never invent columns or tables; join using the foreign keys above.")
    lines.append("- Return only the columns needed to answer the question.")
    return "\n".join(lines)


_LLM_SYSTEM_PROMPT = None


def get_llm_system_prompt() -> str:
    global _LLM_SYSTEM_PROMPT
    if _LLM_SYSTEM_PROMPT is None:
        _LLM_SYSTEM_PROMPT = _schema_for_llm()
    return _LLM_SYSTEM_PROMPT


def _clean_llm_sql(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return enforce_read_only(text)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
async def process_question(
    question: str,
    emit: Optional[Callable[[dict], Any]] = None,
    engine: str = "auto",
) -> dict:
    """Run the full Text-to-SQL pipeline for a question.

    `emit` receives lifecycle events (dicts) and may be sync or async.
    `engine` selects the SQL generator: "auto" (LLM-first, rule fallback),
    "rule" (deterministic), or "llm" (LLM only).
    """
    async def _emit(event: dict):
        if emit:
            result = emit(event)
            if hasattr(result, "__await__"):
                await result

    # 1. Validation ----------------------------------------------------------
    await _emit({"type": "validation", "status": "start", "message": "Validating question..."})
    question = (question or "").strip()
    if not question:
        raise ValidationError("Please ask a question.")
    if len(question) > MAX_QUESTION_LEN:
        raise ValidationError(f"Question too long (max {MAX_QUESTION_LEN} characters).")
    if _MUTATION_HINTS.search(question.lower()):
        raise ValidationError("Only read-only questions about the IPL dataset are supported.")
    await _emit({
        "type": "validation", "status": "done",
        "data": {"question": question, "normalized": question.lower()},
        "message": "Question validated.",
    })

    # 2. SQL generation ------------------------------------------------------
    await _emit({"type": "sql_generation", "status": "start", "message": "Interpreting intent and generating SQL..."})
    sql, meta = await run_in_threadpool(_generate_sql, question, engine)
    meta_title = INTENT_META.get(meta["intent"], {}).get("title", "Query result")
    await _emit({
        "type": "sql_generation", "status": "done",
        "data": {"intent": meta["intent"], "title": meta_title,
                 "parameters": meta["parameters"], "sql": sql,
                 "sql_source": meta["sql_source"], "confidence": meta["confidence"]},
        "message": "SQL generated.",
    })

    # 3. Query execution -----------------------------------------------------
    await _emit({"type": "query_execution", "status": "start", "message": "Executing query against MySQL..."})
    ok, err = await run_in_threadpool(validate_sql, sql, meta["sql_params"])
    if not ok:
        raise ExecutionError(f"Generated SQL failed validation: {err}")
    result = await run_in_threadpool(execute_sql, sql, meta["sql_params"])
    await _emit({
        "type": "query_execution", "status": "done",
        "data": {"row_count": result["row_count"], "elapsed_ms": result["elapsed_ms"]},
        "message": f"Query returned {result['row_count']} row(s) in {result['elapsed_ms']} ms.",
    })

    # 4. Result ---------------------------------------------------------------
    payload = {
        "question": question,
        "intent": meta["intent"],
        "title": meta_title,
        "parameters": meta["parameters"],
        "sql": sql,
        "sql_source": meta["sql_source"],
        "confidence": meta["confidence"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
        "elapsed_ms": result["elapsed_ms"],
    }
    await _emit({"type": "result", "data": payload, "message": "Done."})
    return payload


def _generate_sql(question: str, engine: str = "auto") -> tuple[str, dict]:
    """Generate read-only SQL.

    engine:
      "auto" - LLM first (if configured), schema-aware rule engine as fallback
      "rule" - deterministic rule engine only (offline, reproducible)
      "llm"  - LLM only (raises if not configured or SQL is invalid)
    """
    ents = resolve_entities(question)
    if engine in ("auto", "llm") and is_configured():
        try:
            raw = chat_completion(
                get_llm_system_prompt(),
                f"Question: {question}\nEntities detected: {ents or 'none'}\n"
                "Return only the SQL.",
            )
            sql = _clean_llm_sql(raw)
            ok, err = validate_sql(sql)
            if ok:
                return sql, {"intent": "llm", "parameters": ents, "sql_params": [], "sql_source": "llm", "confidence": 0.8}
            if engine == "llm":
                raise SQLGenerationError(f"LLM produced invalid SQL: {err}")
            # auto: fall through to rule engine on validation failure
        except SQLGenerationError:
            raise
        except Exception:
            if engine == "llm":
                raise SQLGenerationError("LLM could not produce valid SQL.")

    intent, params, confidence = _detect_intent(question.lower(), ents)
    if not intent:
        raise SQLGenerationError(
            "I couldn't map that question to a supported query. "
            "Try asking about player stats, team head-to-head, season winners, "
            "venues, umpires, boundaries, or partnerships."
        )
    template = TEMPLATES[intent]
    sql, sql_params = template(params)
    return sql, {
        "intent": intent,
        "parameters": params,
        "sql_params": sql_params,
        "sql_source": "rule",
        "confidence": round(confidence, 2),
    }
