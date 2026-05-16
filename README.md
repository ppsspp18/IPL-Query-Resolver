# 🏏 IPL Query Resolver

> A relational database system and interactive query engine for Indian Premier League (IPL) data spanning **2008 to 2024**, built with Python and normalized to Boyce-Codd Normal Form (BCNF).

---

## 📌 Table of Contents

- [What is this project?](#what-is-this-project)
- [Why was it built?](#why-was-it-built)
- [How does it work?](#how-does-it-work)
- [Database Design: Why BCNF?](#database-design-why-bcnf)
- [Schema Overview](#schema-overview)
- [Features & Queries](#features--queries)
- [Statistical Analysis Capabilities](#statistical-analysis-capabilities)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How to Run](#how-to-run)
- [Sample Usage](#sample-usage)
- [Design Decisions](#design-decisions)

---

## What is this project?

**IPL Query Resolver** is an interactive command-line application that lets users query, explore, and analyze IPL cricket data across 16 seasons. It is backed by a carefully designed relational database — originally sourced from raw CSV files — that has been decomposed and normalized into **BCNF (Boyce-Codd Normal Form)** to eliminate redundancy and ensure data integrity.

Think of it as a lightweight sports analytics engine: instead of writing SQL queries manually, users can pick from a menu of 22+ pre-built analytical queries covering everything from player stats and team performance to venue analysis and statistical hypothesis testing.

---

## Why was it built?

### The Problem with Raw IPL Data
Raw IPL datasets (commonly found on Kaggle or Cricsheet) come as a handful of flat, denormalized CSV files. These files:

- **Contain massive redundancy** — the same team name, venue name, or player name is repeated thousands of times across rows.
- **Are prone to update anomalies** — renaming a team or venue in one place doesn't automatically fix every other row that references it.
- **Mix concerns** — a single row might bundle match metadata, delivery details, toss information, dismissal types, and umpire names together.
- **Make complex queries slow and error-prone** — joining is harder when there are no proper foreign key relationships.

### The Goal
This project was built to:
1. **Design a proper relational schema** from scratch by decomposing raw data into normalized tables.
2. **Demonstrate database normalization principles** (1NF → 2NF → 3NF → BCNF) on real-world sports data.
3. **Enable rich analytical queries** on the cleaned data using Python's data science ecosystem.
4. **Apply statistical techniques** (chi-square tests, normality checks, confidence intervals) to derive insights beyond simple aggregations.

---

## How does it work?

The program follows a straightforward pipeline:

```
Raw CSVs  →  BCNF Normalization  →  Normalized CSVs  →  Python (pandas)  →  Interactive Query Menu
```

1. **Data Ingestion**: All 12 normalized CSV files are loaded into pandas DataFrames at startup.
2. **Interactive Menu**: The user is shown a numbered menu of 22+ query options.
3. **Query Execution**: Based on the user's choice, the program performs multi-table joins, aggregations, filtering, and (for statistical queries) hypothesis tests using `scipy`.
4. **Performance Reporting**: Every query reports its execution time, giving insight into query cost.
5. **Data Mutation**: Two update operations (rename team, rename venue) write changes back to the CSV files, simulating database UPDATE statements.

---

## Database Design: Why BCNF?

### What is BCNF?
A relation is in **Boyce-Codd Normal Form** if, for every non-trivial functional dependency `X → Y`, `X` is a superkey of the relation. BCNF is stricter than 3NF and eliminates all redundancy caused by functional dependencies.

### Why normalize to BCNF specifically?
- **Eliminates all anomalies**: Insert, update, and delete anomalies are removed when every fact is stored in exactly one place.
- **Reduces storage**: A team name like "Mumbai Indians" is stored once in `teams.csv` and referenced by ID everywhere else, rather than being repeated in thousands of delivery rows.
- **Enables clean joins**: With proper primary and foreign keys, joining tables is predictable and unambiguous.
- **Reflects real-world entities faithfully**: Each table represents one clear concept — a match, a delivery, a player, a venue — rather than a mixture of concerns.

### The Decomposition Process
The original raw data was analysed for all functional dependencies. For example:

- In a flat file, `match_id → venue_name` creates a dependency where `venue_name` is a non-key attribute. This was decomposed into a `venue` table (with `venue_id` as the key) and a `match` table that references `venue_id`.
- Similarly, `(match_id, over, ball) → batter, bowler, runs` was captured in the `delivery` table, and dismissal information (which only applies to certain deliveries) was split into a separate `dismissals` table.

---

## Schema Overview

The database consists of **12 normalized tables**:

| Table | Primary Key | Description |
|---|---|---|
| `teams.csv` | `team_id` | All IPL franchises |
| `players.csv` | `player_id` | All players who have featured in IPL |
| `venue.csv` | `venue_id` | All stadiums/grounds used |
| `umpire.csv` | `umpire_id` | All on-field umpires |
| `match.csv` | `match_id` | Core match metadata (season, date, venue, type) |
| `match_teams.csv` | `match_id` | Maps a match to its two competing teams |
| `toss.csv` | `match_id` | Toss winner and decision (bat/field) per match |
| `match_result.csv` | `match_id` | Winning team per match |
| `umpire_match.csv` | `match_id` | Maps a match to its two umpires |
| `player_of_the_match.csv` | `match_id` | Player of the Match per game |
| `delivery.csv` | `(match_id, inning, over, ball)` | Ball-by-ball delivery data |
| `dismissals.csv` | `delivery_id` | Wicket details for each delivery where a dismissal occurred |

### Entity Relationships (Simplified)

```
teams ────────────────────────── match_teams ── match ── venue
  │                                                │
  └─── match_result                               ├── toss
  └─── player_of_the_match ── players             ├── umpire_match ── umpire
                                                  └── delivery ── dismissals
```

---

## Features & Queries

The program exposes **22 query options** via an interactive menu:

### 📋 Lookup / Projection Queries
| # | Query |
|---|---|
| 1 | List all IPL teams |
| 2 | List all IPL players |
| 3 | List all IPL umpires |
| 4 | List all IPL venues |

### 🏏 Player Queries
| # | Query |
|---|---|
| 5 | Full details of all matches (multi-table join across 10 tables) |
| 6 | Player statistics — runs scored, wickets taken, catches, matches played |
| 7 | Player of the Match history — how many times and in which games |
| 10 | Player team history — which franchise a player represented in each season |
| 18 | Most fifties and hundreds per season |
| 19 | Most 5-wicket hauls per match per season |
| 20 | Bowler vs. batter head-to-head (balls faced, runs, wickets, dot balls) |

### 🏆 Team Queries
| # | Query |
|---|---|
| 8 | Head-to-head stats between any two teams (matches played, wins, toss wins) |
| 9 | Individual team stats (played, won, lost, abandoned) |
| 14 | Average powerplay (first 6 overs) score for a team per season |
| 15 | Average wickets taken in powerplay by a team per season |

### 🏟️ Venue Queries
| # | Query |
|---|---|
| 11 | Venue stats — wins batting first vs. wins chasing |
| 12 | Average first innings score at a given venue |

### 📅 Season-wise Aggregations
| # | Query |
|---|---|
| 13 | Total number of fours and sixes per season |
| 16 | Season awards — Orange Cap, Purple Cap, most sixes, most fours, winner, runner-up |
| 17 | Number of matches officiated by a particular umpire |

### ✏️ Data Mutation
| # | Operation |
|---|---|
| 21 | Update (rename) a team name — persists to `teams.csv` |
| 22 | Update (rename) a venue name — persists to `venue.csv` |

---

## Statistical Analysis Capabilities

Beyond aggregation, the project incorporates formal statistical methods:

### Hypothesis Testing
- **Chi-Square Test**: Tests whether winning the toss has a statistically significant correlation with winning the match. The null hypothesis is that toss outcome and match outcome are independent.
- **Shapiro-Wilk Normality Test**: Tests whether a player's run distribution across matches follows a normal distribution — useful to determine if parametric stats are appropriate.
- **Binomial Test**: Used to compute a player's boundary probability with a **95% confidence interval** — i.e., what fraction of deliveries does a player hit for a boundary, and how precise is that estimate?

### Venue Advantage
- Tests whether batting first or chasing is statistically advantageous at a specific venue, going beyond a simple win count to validate significance.

### Why include statistics?
Raw counts and averages can be misleading. For example, a team might appear to win more when they win the toss — but is that a real pattern or just noise? Hypothesis tests provide a principled answer, making this tool useful not just for casual fans but for analysts seeking data-backed conclusions.

---

## Tech Stack

| Library | Why it's used |
|---|---|
| `pandas` | DataFrame operations — loading CSVs, merging tables (simulating SQL JOINs), groupby aggregations |
| `numpy` | Numerical operations — mean, variance, standard deviation for statistical queries |
| `scipy` | Formal statistical tests — chi-square (`chi2_contingency`), Shapiro-Wilk (`shapiro`), binomial test (`binom_test`) |
| `collections.defaultdict` | Efficient nested statistics accumulation during season-wise aggregation without pre-initializing every key |
| `time` | Execution time measurement for every query — helps understand computational cost |
| `warnings` | Suppresses pandas deprecation warnings to keep output clean |

### Why pandas instead of a real SQL database?
This project is designed as a **learning exercise in relational database design**. Using pandas means the normalization and schema design is the focus — the joins and query logic are written explicitly in Python, making the relational reasoning visible. A production system would use PostgreSQL or SQLite, but pandas makes the project portable and dependency-light.

---

## Project Structure

```
IPL-Query-Resolver/
│
├── main_code.py               # Main program — query menu and all query logic
│
└── normalized csvs/           # Normalized database tables as CSV files
    ├── delivery.csv           # Ball-by-ball data
    ├── dismissals.csv         # Wicket details per delivery
    ├── match.csv              # Match metadata
    ├── match_result.csv       # Winner per match
    ├── match_teams.csv        # Teams per match
    ├── player_of_the_match.csv
    ├── players.csv
    ├── teams.csv
    ├── toss.csv
    ├── umpire.csv
    ├── umpire_match.csv
    └── venue.csv
```

---

## How to Run

### Prerequisites
Make sure you have Python 3.8+ and the required libraries installed:

```bash
pip install pandas numpy scipy
```

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/ppsspp18/IPL-Query-Resolver.git
   cd IPL-Query-Resolver
   ```

2. **Ensure the normalized CSVs are present** in the `normalized csvs/` folder. All 12 CSV files listed above must exist.

3. **Run the program**
   ```bash
   python main_code.py
   ```

4. **Follow the interactive menu** — enter a number (1–23) to choose a query.

---

## Sample Usage

```
Welcome to the IPL Data Analysis Program!
This program consists of the data of all IPL matches from 2008 to 2024

------------------------------------------------------
Please select any one of the below query
1  - List of all teams in IPL
6  - Particular player stats in IPL
8  - Input any 2 teams and find out the head to head stats
16 - Each season stats - purple cap, orange cap, most 4s, most 6s, winner, runner up
...

Enter your choice: 8

Enter the name of the first team: Mumbai Indians
Enter the name of the second team: Chennai Super Kings

Head to head stats between Mumbai Indians and Chennai Super Kings:
Total matches played: 36
Mumbai Indians wins: 20
Chennai Super Kings wins: 16
Mumbai Indians toss wins: 18
Chennai Super Kings toss wins: 18
Execution time: 0.0031 seconds
```

---

## Design Decisions

### Why split `dismissals` from `delivery`?
Not every delivery results in a wicket. Storing `is_wicket`, `dismissal_kind`, and `fielder_id` in the `delivery` table would leave these columns NULL for the vast majority of rows (~95%). Separating them into a `dismissals` table is more space-efficient and semantically cleaner — a dismissal is a distinct event, not a property of every ball.

### Why a separate `toss` table?
The toss is associated with a match but has its own attributes (`toss_winner`, `toss_decision`). Embedding it in `match.csv` would violate BCNF if toss attributes aren't determined solely by `match_id` in a different decomposition. Keeping it separate also makes toss-specific queries (e.g., chi-square test on toss vs. match result) cleaner to express.

### Why `match_teams` instead of columns in `match`?
A match always involves exactly two teams, so columns `team_id1` and `team_id2` in `match` could work — but labelling teams as "team 1" and "team 2" implies an ordering that doesn't exist in cricket. A separate `match_teams` table avoids this asymmetry and is more extensible (e.g., if the format ever changes).

### Why execution time on every query?
Displaying execution time after every result is intentional. It allows the user to understand which queries are expensive (e.g., ball-by-ball aggregations across 16 seasons) vs. cheap (simple projections on small lookup tables). It also demonstrates the performance trade-offs that motivate database indexing in production systems.

---

## Data Coverage

- **Seasons**: 2008 – 2024 (16 IPL seasons)
- **Entities tracked**: Teams, Players, Venues, Umpires, Matches, Deliveries, Dismissals, Tosses
- **Granularity**: Ball-by-ball (every single delivery across all matches)

---

*Built as a Database Management Systems project to demonstrate relational schema design, normalization to BCNF, and applied data analysis on real IPL cricket data.*
