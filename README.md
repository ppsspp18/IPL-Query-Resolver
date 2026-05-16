# 🏏 IPL Query Resolver

> A relational database system for Indian Premier League (IPL) data — engineered for high integrity, fast querying, and deep statistical insight across 17 seasons (2008–2024).

---

## 📌 Overview

IPL Query Resolver is a self-built analytical database project that transforms raw IPL CSV data into a fully normalized relational schema (BCNF), enabling fast, accurate, and meaningful querying across 25,000+ ball-by-ball records.

The project demonstrates core database engineering principles — normalization, relational algebra, indexing, and statistical analysis — through an interactive command-line interface with 25+ pre-built analytical queries.

---

## 🎯 Motivation

Raw IPL datasets are typically flat, denormalized CSVs riddled with redundancy and integrity issues. This project was built to:

- Apply **Boyce-Codd Normal Form (BCNF)** normalization to eliminate data anomalies
- Simulate relational algebra operations (selection, projection, joins, set difference) using pandas
- Extract meaningful cricket analytics efficiently using indexed, structured data
- Demonstrate how proper schema design directly impacts query performance

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.x |
| Data Manipulation | pandas, numpy |
| Statistical Analysis | scipy |
| Data Format | CSV (normalized) |
| Interface | Command-Line (Interactive Menu) |

---

## 🗃️ Database Design

### Normalization

The raw IPL data was decomposed from flat CSVs into **12 normalized tables** conforming to **BCNF**, eliminating partial and transitive dependencies:

| Table | Description |
|---|---|
| `match.csv` | Core match metadata (date, season, match_id) |
| `match_teams.csv` | Teams participating in each match |
| `match_result.csv` | Winner, margin, and result type per match |
| `toss.csv` | Toss winner and decision per match |
| `delivery.csv` | Ball-by-ball delivery data (25k+ records) |
| `dismissals.csv` | Wicket type, bowler, and fielder per dismissal |
| `players.csv` | Player master data |
| `teams.csv` | Team master data |
| `venue.csv` | Venue master data |
| `umpire.csv` | Umpire master data |
| `umpire_match.csv` | Umpire-to-match assignments |
| `player_of_the_match.csv` | POTM awards per match |

### Relational Algebra Operations Used

- **Selection (σ)** — Filter rows by condition (e.g., deliveries in powerplay overs)
- **Projection (π)** — Extract specific columns (e.g., player names, scores)
- **Natural Joins (⋈)** — Combine tables on shared keys (e.g., match + result + teams)
- **Set Difference (−)** — Find players who never won POTM, venues with no wins while batting first
- **Indexing** — Logical indexing via pandas `.loc` and `.iloc` for millisecond-level queries on large datasets

All normalized CSVs are stored in the `normalized csvs/` folder.

---

## 📊 Analytical Queries (25+)

The program provides an interactive menu with the following query categories:

### 📋 Master Data Lookups
1. List all IPL teams
2. List all IPL players
3. List all IPL umpires
4. List all IPL venues
5. Show all matches with full details (teams, venue, umpires, winner, POTM)

### 👤 Player Analytics
6. Player statistics — runs, wickets, catches, matches played
7. Player of the Match award history
8. Head-to-head stats between two teams (matches, wins, toss wins)
9. Individual team stats — played, won, lost, abandoned
10. Player team history per season
18. Most hundreds and fifties per season
19. Most 5-wicket hauls per season
20. Bowler vs batter head-to-head comparison

### 🏟️ Venue Analytics
11. Venue-based win stats — batting first vs chasing
12. Average first innings score per venue
24. Venue advantage hypothesis test

### 📅 Season-wise Analytics
13. Total 4s and 6s per season
14. Average powerplay score per team per season
15. Average wickets taken in powerplay per team per season
16. Season summary — Orange Cap, Purple Cap, most boundaries, most dots, winner, runner-up
17. Number of matches officiated per umpire

### 📐 Statistical Tests & Probability
21. Toss win probability with chi-square hypothesis test
22. Player run distribution with Shapiro-Wilk normality test
23. Venue advantage hypothesis test (bat first vs chase)
24. Player boundary probability with 95% confidence interval
25. Correlation between toss result and match result

### 🛠️ Data Management
26. Update team name in the dataset
27. Update venue name in the dataset

---

## 🚀 Getting Started

### Prerequisites

```bash
pip install pandas numpy scipy
```

### Installation

```bash
# Clone the repository
git clone https://github.com/ppsspp18/IPL-Query-Resolver.git
cd IPL-Query-Resolver
```

### Running the Program

```bash
python main_code.py
```

The program will present an interactive numbered menu. Enter the query number to run any analysis.

### Directory Structure

```
IPL-Query-Resolver/
│
├── main_code.py               # Main program with all queries
├── README.md                  # Project documentation
│
└── normalized csvs/           # BCNF-normalized data tables
    ├── delivery.csv
    ├── dismissals.csv
    ├── match.csv
    ├── match_result.csv
    ├── match_teams.csv
    ├── player_of_the_match.csv
    ├── players.csv
    ├── teams.csv
    ├── toss.csv
    ├── umpire.csv
    ├── umpire_match.csv
    └── venue.csv
```

---

## 📈 Performance

- **25,000+ ball-by-ball records** processed across 17 IPL seasons (2008–2024)
- Queries execute in **milliseconds** due to indexed data access via pandas
- BCNF normalization ensures **zero redundancy** and **full referential integrity** across all tables

---

## 🧠 Key Concepts Demonstrated

- **Database Normalization** — 1NF → 2NF → 3NF → BCNF decomposition
- **Relational Algebra** — Selection, projection, join, set difference applied programmatically
- **Indexing** — Efficient lookups on large datasets using pandas indexing
- **Statistical Hypothesis Testing** — Chi-square, Shapiro-Wilk, binomial tests on cricket data
- **Confidence Intervals** — Boundary probability estimation using scipy
- **Data Integrity** — Eliminating update, insertion, and deletion anomalies through normalization

---

## 📬 Author

**Prakhar Pathak**
Self Project | Jul 2025 – Aug 2025

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
