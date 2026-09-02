"""Schema awareness for the Text-to-SQL pipeline.

Introspects the live MySQL database (INFORMATION_SCHEMA) to build:
  * a structured schema model (tables, columns, foreign keys),
  * a natural-language prompt context for an LLM,
  * an in-memory entity index (teams / players / venues / umpires / seasons)
    used for deterministic intent resolution.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from db import run_query

# Tables ignored when building the schema model.
SKIP_TABLES = {"ipl_raw"}

TABLES_PREFIX = {
    "teams": "Master tables",
    "venues": "Master tables",
    "umpires": "Master tables",
    "players": "Master tables",
    "match_details": "Match metadata",
    "match_result": "Match metadata",
    "match_toss": "Match metadata",
    "match_teams": "Match metadata",
    "match_umpire": "Match metadata",
    "delivery": "Ball-by-ball",
    "dismissal": "Ball-by-ball",
}

_ORDER = {name: i for i, name in enumerate(TABLES_PREFIX)}


def normalize(text: str) -> str:
    """Lowercase, strip diacritics and punctuation for fuzzy matching."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def initials_key(name: str) -> str:
    """'Virat Kohli' -> 'v kohli'; used to match 'v kohli' style questions."""
    parts = normalize(name).split()
    if len(parts) < 2:
        return normalize(name)
    return f"{parts[0][0]} {parts[-1]}".strip()


# --------------------------------------------------------------------------- #
# Schema model
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_table_columns() -> dict[str, list[dict]]:
    rows = run_query(
        """
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c, DATA_TYPE AS dtype, COLUMN_KEY AS ckey
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
    )
    out: dict[str, list[dict]] = {}
    for r in rows:
        if r["t"] in SKIP_TABLES:
            continue
        out.setdefault(r["t"], []).append(
            {"name": r["c"], "type": r["dtype"], "key": r["ckey"] or ""}
        )
    return out


@lru_cache(maxsize=1)
def get_foreign_keys() -> list[dict]:
    rows = run_query(
        """
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c, REFERENCED_TABLE_NAME AS ref_t,
               REFERENCED_COLUMN_NAME AS ref_c
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND REFERENCED_TABLE_NAME IS NOT NULL
        """
    )
    return [
        {"table": r["t"], "column": r["c"],
         "references": f'{r["ref_t"]}.{r["ref_c"]}'}
        for r in rows
        if r["t"] not in SKIP_TABLES
    ]


@lru_cache(maxsize=1)
def get_schema_context() -> dict:
    """Full structured schema model used by the resolver and the LLM prompt."""
    columns = get_table_columns()
    fks = get_foreign_keys()
    tables = {}
    for tname in sorted(columns, key=lambda t: _ORDER.get(t, 99)):
        tables[tname] = {
            "description": _describe_table(tname),
            "columns": columns[tname],
            "sample_rows": _sample_rows(tname, 3),
        }
    return {"tables": tables, "foreign_keys": fks}


def _describe_table(table: str) -> str:
    desc = {
        "teams": "every franchise that has played in the IPL",
        "venues": "every stadium that hosted a match, with its city",
        "umpires": "every umpire who officiated a match",
        "players": "every player who featured in a match",
        "match_details": "one row per match (season, date, venue, stage/type)",
        "match_result": "one row per match (winner, player of the match, margin, target)",
        "match_toss": "one row per match (toss winner and decision)",
        "match_teams": "one row per match linking the two competing teams",
        "match_umpire": "one row per (match, umpire) pair",
        "delivery": "one row per ball bowled (batting/bowling team, batter/bowler, runs)",
        "dismissal": "one row per wicket (batter out, kind of dismissal, fielder)",
    }
    return desc.get(table, "")


def _sample_rows(table: str, limit: int) -> list[dict]:
    try:
        cols = get_table_columns().get(table, [])
        if not cols:
            return []
        names = ", ".join(f"`{c['name']}`" for c in cols[:5])
        return run_query(f"SELECT {names} FROM `{table}` ORDER BY 1 LIMIT {limit}")
    except Exception:
        return []


# --------------------------------------------------------------------------- #
# Entity index
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_entities() -> dict[str, dict[str, str]]:
    """Return {entity_type: {normalized_key: canonical_name}} for resolution."""
    teams = {
        normalize(t["team_name"]): t["team_name"]
        for t in run_query("SELECT team_name FROM teams")
    }
    venues = {
        normalize(v["venue_name"]): v["venue_name"]
        for v in run_query("SELECT venue_name FROM venues")
    }
    umpires = {
        normalize(u["umpire_name"]): u["umpire_name"]
        for u in run_query("SELECT umpire_name FROM umpires")
    }
    seasons = {
        normalize(s["season"]): s["season"]
        for s in run_query("SELECT DISTINCT season FROM match_details ORDER BY season")
    }
    players = {
        normalize(p["player_name"]): p["player_name"]
        for p in run_query("SELECT player_name FROM players")
    }
    return {
        "teams": teams,
        "players": players,
        "venues": venues,
        "umpires": umpires,
        "seasons": seasons,
    }


# --------------------------------------------------------------------------- #
# Entity resolution
# --------------------------------------------------------------------------- #
SEASON_RE = re.compile(r"(19|20)\d{2}(/\d{2})?")


def resolve_entities(question: str) -> dict[str, str]:
    """Find known entity mentions in a natural-language question.

    Returns a dict mapping entity type -> canonical name, e.g.
    {"teams": "Mumbai Indians", "players": "Virat Kohli"}.

    Player names in the dataset are abbreviated ("V Kohli"), so full names
    ("Virat Kohli") are resolved via an initial + surname signature match.
    """
    idx = get_entities()
    q = normalize(question)
    found: dict[str, str] = {}

    # 1. Substring match for teams / venues / seasons (full names).
    for etype in ("teams", "venues"):
        candidates = sorted(idx[etype].items(), key=lambda kv: len(kv[0]), reverse=True)
        for key, name in candidates:
            if key and key in q:
                found.setdefault(etype, name)

    for m in SEASON_RE.finditer(q):
        found.setdefault("seasons", m.group(0))

    # 2. Player / umpire resolution via surname + first-letter signature,
    #    since the dataset stores abbreviated names ("V Kohli", "S Ravi").
    player = _resolve_abbrev_name(q, idx["players"], prefer=get_player_prominence())
    if player:
        found["players"] = player
    umpire = _resolve_abbrev_name(q, idx["umpires"])
    if umpire:
        found["umpires"] = umpire
    return found


@lru_cache(maxsize=1)
def get_player_prominence() -> dict[str, int]:
    """Map player_name -> career deliveries, used to disambiguate short names."""
    rows = run_query(
        """
        SELECT p.player_name AS name, COUNT(*) AS n
        FROM delivery d
        JOIN players p ON d.batter_id = p.player_id OR d.bowler_id = p.player_id
        GROUP BY p.player_id
        """
    )
    return {r["name"]: r["n"] for r in rows}


# Common English words that collide with player surnames and must not be
# treated as a player mention on their own (e.g. "head to head").
COMMON_WORDS = {"head"}

# Words that can never act as a player initial (preceding token).
_INITIAL_STOPWORDS = {
    "to", "of", "in", "at", "the", "a", "an", "for", "on", "vs", "and",
    "with", "by", "did", "do", "is", "was", "who", "when", "how", "against",
    "from", "or", "as", "total", "most", "best",
}


def _resolve_abbrev_name(
    q: str,
    entity_dict: dict[str, str],
    prefer: dict[str, int] | None = None,
) -> str | None:
    """Resolve an abbreviated multi-token name ("V Kohli") in normalized text.

    "Virat Kohli" is matched via a first-initial + surname signature, while
    "MS Dhoni" is matched by the stored full-initial form. When several stored
    names share a signature, `prefer` (e.g. career prominence) breaks the tie.
    """
    tokens = q.split()
    if not tokens:
        return None

    # surname -> {"letter": [names], "full": [names]} for lookup.
    surname_map: dict[str, dict[str, list[str]]] = {}
    for key, name in entity_dict.items():
        parts = key.split()
        if len(parts) < 2:
            continue
        surname, initial = parts[-1], parts[0]
        node = surname_map.setdefault(surname, {"letter": [], "full": []})
        node["letter"].append(name)
        node["full"].append(name)

    for i, tok in enumerate(tokens):
        if tok not in surname_map or tok in COMMON_WORDS:
            continue
        node = surname_map[tok]
        if i == 0:
            # Standalone surname: accept only when the word is a surname-only
            # player token (unique in the index) and the sentence looks like a
            # player question is unlikely to be ambiguous.
            if len(node["letter"]) == 1:
                return node["letter"][0]
            continue
        prev = tokens[i - 1]
        if prev in _INITIAL_STOPWORDS:
            continue
        # Match the stored abbreviation as typed ("ms dhoni", "ch gayle").
        exact = [n for n in node["full"] if n.split()[0].lower() == prev]
        if exact:
            return exact[0]
        # Match by first-initial signature ("virat" -> "v kohli").
        if prev[0].isalpha():
            letter = prev[0]
            matches = [n for n in node["letter"] if n.split()[0].lower().startswith(letter)]
            if matches:
                if len(matches) == 1:
                    return matches[0]
                # Ambiguous short names ("R Sharma" vs "RG Sharma"): prefer the
                # more prominent player by career deliveries.
                return max(matches, key=lambda n: (prefer or {}).get(n, 0))
    return None


def season_exists(season: str) -> bool:
    n = normalize(season)
    for key, name in get_entities()["seasons"].items():
        if n in key or key in n:
            return True
    return False


def resolve_season(text: str) -> str | None:
    """Map a season mention ('2020', '2020/21', '2009') to its canonical value."""
    idx = get_entities()["seasons"]
    # Prefer the explicit slash form when typed ("2009/10").
    m = re.search(r"(19|20)\d{2}/\d{2}", text)
    if m:
        return idx.get(normalize(m.group(0)))
    n = normalize(text)
    for m in re.finditer(r"(19|20)\d{2}", n):
        cand = m.group(0)
        if cand in idx:
            return idx[cand]
        for key, name in idx.items():
            if key.startswith(cand):
                return name
    return None


