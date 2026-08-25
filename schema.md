# IPL Normalized Database Schema

The IPL dataset (`IPL.csv`) is loaded into a raw table (`ipl_raw`) and then
normalized into **4 master tables**, **5 match-metadata tables**, and **2
ball-by-ball tables** in the MySQL database `ipl_normalized`.

## Table Relationships

```
                            ipl_raw  (raw denormalized source)
                                 |
        +------------+------------+------------+--------------+
        |            |            |            |              |
   master tables  match metadata          ball-by-ball
        |            |            |            |              |
  teams          match_details    match_result   delivery
  venues         match_toss       match_teams    dismissal
  umpires        match_umpire
  players
```

- **Master tables** hold a single row per unique entity (team, venue, umpire,
  player). Other tables reference them by foreign-key id.
- **Match metadata** has one row per match (`match_id`); only `match_umpire`
  has one row per (match, umpire) pair.
- **Ball-by-ball** tables have one row per delivery (and per dismissal).

## 1. Raw Table

**`ipl_raw`** — one row per ball as it appears in the CSV. Used only as the
source for building the normalized tables.

| Column | Type |
|---|---|
| `match_id` | INT |
| `season` | VARCHAR(10) |
| `date` | DATE |
| `venue`, `city` | VARCHAR |
| `stage` | VARCHAR(50) |
| `toss_winner`, `toss_decision` | VARCHAR |
| `match_won_by`, `superover_winner`, `win_outcome` | VARCHAR |
| `runs_target`, `overs`, `method` | INT / VARCHAR |
| `player_of_match`, `umpire` | VARCHAR |
| `innings`, `` `over` ``, `ball` | INT |
| `batting_team`, `bowling_team`, `batter`, `bowler`, `non_striker` | VARCHAR |
| `runs_batter`, `runs_extras`, `runs_total` | INT |
| `player_out`, `wicket_kind`, `fielders` | VARCHAR |

## 2. Master Tables

### `teams`
| Column | Type |
|---|---|
| `team_id` | INT PRIMARY KEY AUTO_INCREMENT |
| `team_name` | VARCHAR(100) NOT NULL UNIQUE |

```sql
mysql> SELECT * FROM teams LIMIT 5;
+---------+---------------------+
| team_id | team_name           |
+---------+---------------------+
|       3 | Chennai Super Kings |
|       8 | Deccan Chargers     |
|      15 | Delhi Capitals      |
|       6 | Delhi Daredevils    |
|      13 | Gujarat Lions       |
+---------+---------------------+
```

### `venues`
| Column | Type |
|---|---|
| `venue_id` | INT PRIMARY KEY AUTO_INCREMENT |
| `venue_name` | VARCHAR(255) NOT NULL |
| `venue_city` | VARCHAR(100) |

```sql
mysql> SELECT * FROM venues LIMIT 5;
+----------+--------------------------------------------+------------+
| venue_id | venue_name                                 | venue_city |
+----------+--------------------------------------------+------------+
|        1 | M Chinnaswamy Stadium                      | Bangalore  |
|        2 | Punjab Cricket Association Stadium, Mohali | Chandigarh |
|        3 | Feroz Shah Kotla                           | Delhi      |
|        4 | Wankhede Stadium                           | Mumbai     |
|        5 | Eden Gardens                               | Kolkata    |
+----------+--------------------------------------------+------------+
```

### `umpires`
| Column | Type |
|---|---|
| `umpire_id` | INT PRIMARY KEY AUTO_INCREMENT |
| `umpire_name` | VARCHAR(150) NOT NULL UNIQUE |

```sql
mysql> SELECT * FROM umpires LIMIT 5;
+-----------+----------------------+
| umpire_id | umpire_name          |
+-----------+----------------------+
|        40 | A Bengeri            |
|         4 | A Deshmukh           |
|        12 | A Nand Kishore       |
|        36 | A Totre              |
|        39 | Abhijit Bhattacharya |
+-----------+----------------------+
```

### `players`
| Column | Type |
|---|---|
| `player_id` | INT PRIMARY KEY AUTO_INCREMENT |
| `player_name` | VARCHAR(150) NOT NULL UNIQUE |

```sql
mysql> SELECT * FROM players LIMIT 5;
+-----------+----------------+
| player_id | player_name    |
+-----------+----------------+
|       326 | A Ashish Reddy |
|       568 | A Badoni       |
|       336 | A Chandila     |
|       127 | A Chopra       |
|       437 | A Choudhary    |
+-----------+----------------+
```

## 3. Match Metadata Tables

One row per match, except `match_umpire` (one row per match+umpire pair).

### `match_details`
| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | references `ipl_raw` |
| `season` | VARCHAR(10) | e.g. `2007/08` |
| `date` | DATE | |
| `venue_id` | INT | FK → `venues.venue_id` |
| `match_type` | VARCHAR | `League`, `Qualifier 1`, `Final`, ... |

```sql
mysql> SELECT * FROM match_details LIMIT 5;
+----------+---------+------------+----------+------------+
| match_id | season  | date       | venue_id | match_type |
+----------+---------+------------+----------+------------+
|   335982 | 2007/08 | 2008-04-18 |        1 | League     |
|   335983 | 2007/08 | 2008-04-19 |        2 | League     |
|   335984 | 2007/08 | 2008-04-19 |        3 | League     |
|   335985 | 2007/08 | 2008-04-20 |        4 | League     |
|   335986 | 2007/08 | 2008-04-20 |        5 | League     |
+----------+---------+------------+----------+------------+
```

### `match_result`
| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `winner_id` | INT | FK → `teams.team_id`; NULL if no result |
| `player_of_match_id` | INT | FK → `players.player_id` |
| `result` | VARCHAR | `run` \| `wicket` \| `super` |
| `result_margin` | INT | runs/wickets won by |
| `target_run` | INT | target set for chaser |
| `target_over` | INT | overs in target |
| `super_over` | CHAR(1) | `Y` / `N` |
| `method` | VARCHAR | `D/L` or NULL |

```sql
mysql> SELECT * FROM match_result LIMIT 5;
+----------+-----------+--------------------+--------+---------------+------------+-------------+------------+--------+
| match_id | winner_id | player_of_match_id | result | result_margin | target_run | target_over | super_over | method |
+----------+-----------+--------------------+--------+---------------+------------+-------------+------------+--------+
|   335982 |         1 |                  2 | run    |           140 |       NULL |          20 | N          | NULL   |
|   335983 |         3 |                 19 | run    |            33 |       NULL |          20 | N          | NULL   |
|   335984 |         6 |                 91 | wicket |             9 |       NULL |          20 | N          | NULL   |
|   335985 |         2 |                 11 | wicket |             5 |       NULL |          20 | N          | NULL   |
|   335986 |         1 |                  4 | wicket |             5 |       NULL |          20 | N          | NULL   |
+----------+-----------+--------------------+--------+---------------+------------+-------------+------------+--------+
```

### `match_toss`
| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `toss_winner_id` | INT | FK → `teams.team_id` |
| `toss_decision` | VARCHAR | `bat` \| `field` |

```sql
mysql> SELECT * FROM match_toss LIMIT 5;
+----------+----------------+---------------+
| match_id | toss_winner_id | toss_decision |
+----------+----------------+---------------+
|   335982 |              2 | field         |
|   335983 |              3 | bat           |
|   335984 |              5 | bat           |
|   335985 |              7 | bat           |
|   335986 |              8 | bat           |
+----------+----------------+---------------+
```

### `match_teams`
| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `team1_id` | INT | FK → `teams.team_id` |
| `team2_id` | INT | FK → `teams.team_id` |

```sql
mysql> SELECT * FROM match_teams LIMIT 5;
+----------+----------+----------+
| match_id | team1_id | team2_id |
+----------+----------+----------+
|   335982 |        1 |        2 |
|   335983 |        3 |        4 |
|   335984 |        6 |        5 |
|   335985 |        7 |        2 |
|   335986 |        8 |        1 |
+----------+----------+----------+
```

### `match_umpire`
| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `umpire_id` | INT | FK → `umpires.umpire_id` |

```sql
mysql> SELECT * FROM match_umpire LIMIT 5;
+----------+-----------+
| match_id | umpire_id |
+----------+-----------+
|  1136561 |         1 |
|  1136562 |         2 |
|  1136563 |         3 |
|  1136563 |         4 |
|  1136564 |         5 |
+----------+-----------+
```

## 4. Ball-by-Ball Tables

### `delivery`
One row per ball bowled. All ids are foreign keys to the master tables.

| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `innings` | INT | |
| `` `over` `` | INT | |
| `ball` | INT | |
| `batting_team_id` | INT | FK → `teams` |
| `bowling_team_id` | INT | FK → `teams` |
| `batter_id` | INT | FK → `players` |
| `bowler_id` | INT | FK → `players` |
| `non_striker_id` | INT | FK → `players` (nullable) |
| `runs_batter` | INT | runs off the bat |
| `runs_extras` | INT | runs from extras |
| `runs_total` | INT | total runs on the ball |

```sql
mysql> SELECT * FROM delivery LIMIT 5;
+----------+---------+------+------+-----------------+-----------------+-----------+-----------+----------------+-------------+-------------+------------+
| match_id | innings | over | ball | batting_team_id | bowling_team_id | batter_id | bowler_id | non_striker_id | runs_batter | runs_extras | runs_total |
+----------+---------+------+------+-----------------+-----------------+-----------+-----------+----------------+-------------+-------------+------------+
|   335982 |       1 |    0 |    1 |               1 |               2 |         1 |        14 |              2 |           0 |           1 |          1 |
|   335982 |       1 |    0 |    2 |               1 |               2 |         2 |        14 |              1 |           0 |           0 |          0 |
|   335982 |       1 |    0 |    3 |               1 |               2 |         2 |        14 |              1 |           0 |           1 |          1 |
|   335982 |       1 |    0 |    3 |               1 |               2 |         2 |        14 |              1 |           0 |           0 |          0 |
|   335982 |       1 |    0 |    4 |               1 |               2 |         2 |        14 |              1 |           0 |           0 |          0 |
+----------+---------+------+------+-----------------+-----------------+-----------+-----------+----------------+-------------+-------------+------------+
```

### `dismissal`
One row per wicket. `fielders` from the raw tuple is collapsed to the first
fielder only.

| Column | Type | Notes |
|---|---|---|
| `match_id` | INT | |
| `innings` | INT | |
| `` `over` `` | INT | |
| `ball` | INT | |
| `player_out_id` | INT | FK → `players.player_id` |
| `wicket_kind` | VARCHAR | `bowled`, `caught`, `lbw`, ... |
| `fielder_id` | INT | FK → `players.player_id` (nullable) |

```sql
mysql> SELECT * FROM dismissal LIMIT 5;
+----------+---------+------+------+---------------+-------------+------------+
| match_id | innings | over | ball | player_out_id | wicket_kind | fielder_id |
+----------+---------+------+------+---------------+-------------+------------+
|   335982 |       1 |    5 |    2 |             1 | caught      |          9 |
|   335982 |       1 |   12 |    1 |             3 | caught      |         14 |
|   335982 |       1 |   17 |    1 |             4 | caught      |         10 |
|   335982 |       2 |    1 |    1 |             6 | bowled      |       NULL |
|   335982 |       2 |    2 |    2 |             8 | bowled      |       NULL |
+----------+---------+------+------+---------------+-------------+------------+
```

## Loading Order

Run the `.sql` files in order:

1. `00_setup_raw_data.sql` — create DB, load `IPL.csv` into `ipl_raw`
2. `01_create_master_tables.sql` — `teams`, `venues`, `umpires`, `players`
3. `02_create_match_metadata.sql` — `match_details`, `match_result`, `match_toss`,
   `match_teams`, `match_umpire`
4. `03_create_ball_by_ball.sql` — `delivery`, `dismissal`
5. `04_top5_rows.sql` — sample verification queries
