# Statistical-Insights-from-IPL-Matches

This Python program performs a wide range of analyses on IPL (Indian Premier League) data from 2008 to 2024. It uses CSV datasets for matches, players, deliveries, teams, venues, umpires, and match results, allowing users to query and explore IPL statistics interactively.

---

## Features

The program allows you to perform the following queries:

1. List all IPL teams.
2. List all IPL players.
3. List all IPL umpires.
4. List all IPL venues.
5. Show all matches with full details including teams, venue, umpires, winner, and player of the match.
6. Player statistics (runs, wickets, catches, matches played).
7. Player of the Match statistics for a specific player.
8. Head-to-head stats between two teams (matches played, wins, toss wins).
9. Individual team stats (matches played, won, lost, abandoned).
10. Player team history per season.
11. Venue-based stats: wins while batting first or chasing.
12. Average first innings score per venue.
13. Total number of 4s and 6s per season.
14. Average powerplay score for a team per season.
15. Average wickets taken in powerplay by a team per season.
16. Season-wise stats: Orange Cap, Purple Cap, most 4s and 6s, dots, winner, runner-up.
17. Number of matches judged by an umpire.
18. Most hundreds and fifties per season.
19. Most 5-wicket hauls per match per season.
20. Bowler vs batter comparison.
21. Toss winning probability and chi-square hypothesis test.
22. Player run distribution and normality test.
23. Venue advantage hypothesis test (bat first vs chase).
24. Player boundary probability with 95% confidence interval.
25. Correlation between toss result and match result.
26. Update team name in the dataset.
27. Update venue name in the dataset.
28. Exit the program.

---

## Key Python Libraries Used

- **pandas**: For data manipulation and analysis.
- **numpy**: For numerical calculations like mean, variance, standard deviation.
- **scipy**: For statistical tests (chi-square, Shapiro-Wilk, binomial tests).
- **time**: For calculating execution time.
- **collections.defaultdict**: For storing nested statistics easily.
- **warnings**: To suppress unnecessary warnings.

---

## Data Requirements

The program requires the following normalized CSV files (stored in `normalized csvs/` folder):

- `delivery.csv`
- `dismissals.csv`
- `match_result.csv`
- `match_teams.csv`
- `match.csv`
- `player_of_the_match.csv`
- `players.csv`
- `teams.csv`
- `toss.csv`
- `umpire.csv`
- `umpire_match.csv`
- `venue.csv`

---

## How to Run

1. Clone the repository.
2. Make sure the `normalized csvs/` folder contains all required CSV files.
3. Run the Python program:

```bash
python <filename>.py

