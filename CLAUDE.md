# Ethel's Dynasty — project overview, architecture, and league quirks

## Purpose

This repo generates a static analysis and history site for "Ethel's
Dynasty," a 12-team half-PPR, one-QB, four-round-rookie-draft dynasty
league on Sleeper (current league_id `1312135999710572544`, 2026 season).
It started as a "vibe-written" scouting report for each team ahead of the
2026 rookie draft (roster construction, contention window, draft capital,
opinionated draft recommendations) and grew into a full league site:
season-by-season history back to the league's 2018 founding, an all-time
head-to-head matrix, advanced analytics (luck, positional scoring mix,
transaction activity), and a draft-pick trade flow ledger. The site is
published via GitHub Pages, serving the `docs/` folder on `main`
(`https://thecl804.github.io/ebl-eval/`), at the request of the repo owner
(a league member, not the commissioner) who wants to share it with the
league.

## Architecture

Everything is a static site generator, no frontend framework, no build
step beyond running Python scripts and committing the output:

1. **Fetch scripts** pull raw data from the public Sleeper API (no auth
   needed) into `data/*.json`:
   - `scripts/fetch_data.py` — current (2026) league: users, rosters,
     draft picks, traded picks, a player cache filtered to rostered
     players.
   - `scripts/fetch_history.py` — full historical data for every season
     2019–2026 (2026 included so in-season trades show up in the trades
     hub): rosters, weekly matchups, transactions, winners bracket, traded
     picks, and that season's draft results. Writes one file per season to
     `data/history/{season}.json`. Also widens `data/players.json` (which
     `fetch_data.py` filters to only currently-rostered players) to include
     every player who ever appears in any historical trade, waiver claim,
     or free agent move's adds/drops, since transactions reference players
     who have since retired or been dropped.
   - `scripts/fetch_dynasty_values.py` — point-in-time dynasty trade values
     from DynastyProcess's open-data repo (`github.com/dynastyprocess/data`)
     for every player/pick referenced in `data/trades.json`: the commit
     nearest each trade's date, plus the commits nearest 1/2/3 years after
     each trade (whichever have elapsed), joined to our Sleeper player ids
     via DynastyProcess's own id crosswalk. Writes `data/dynasty_values.json`.
     See "Dynasty trade grading" below for why KeepTradeCut isn't used here
     and why this doesn't grade against "value today."
2. **Compute scripts** turn raw data into the shapes the site templates
   consume:
   - `scripts/compute_teams.py` → `data/teams.json` (per-team roster
     composition, age, draft capital for the current league)
   - `scripts/compute_history.py` → `data/season_summaries.json` +
     `data/head_to_head.json` + `data/rivalries.json` (season
     standings/champions, all-time head-to-head matrix, and a full
     chronological game log per team pair for the Rivalries page — same
     filtering rules as the head-to-head matrix, just game-by-game instead
     of aggregated)
   - `scripts/compute_trade_grades.py` → `data/trade_grades.json` (per-trade
     dynasty value grade, from `data/trades.json` + `data/dynasty_values.json`)
   - `scripts/compute_analytics.py` → `data/analytics.json` (all-play
     luck, positional scoring mix, transaction activity)
   - `scripts/compute_draft_flow.py` → `data/draft_flow.json` (draft pick
     trade ledger and net-capital leaderboard, 2019–2028, derived from
     `traded_picks` ownership snapshots)
   - `scripts/compute_trades.py` → `data/trades.json` (the full trade
     ledger, players and picks both, read directly from each season's
     trade transactions rather than pick-ownership snapshots; also a
     pairwise team-partner breakdown for the trades hub's "click a pair,
     see every deal" view)
   - `scripts/compute_team_transactions.py` → `data/team_transactions.json`
     (every trade, waiver claim, and free agent move for each current team
     across all history, gave/received framed from that team's own
     perspective, for the per-team "Transactions" drill-down page)
3. **`data/content.json`** is hand-authored, not generated: the
   opinionated scouting-report prose per team (verdict, tagline,
   strengths/weaknesses, narrative, current standing, future outlook) and
   the league-wide summary. This is the one file in `data/` that isn't a
   mechanical transform of the Sleeper API and should be edited directly
   when the analysis needs to change.
4. **`scripts/build_site.py`** reads everything in `data/` and renders
   plain HTML/CSS into `docs/` (one file per team plus a per-team
   Transactions page, a Home landing page (`index.html`, added 2026-08 —
   a hub linking to every section plus a few league-wide facts, not the
   scouting-report grid), and Power Rankings, League History,
   Head-to-Head, Rivalries, Analytics, Draft Capital Flow, and Trades Hub
   pages, all sharing one `style.css` and a nav bar). **`index.html` is the home
   page, not Power Rankings** — the per-team scouting-report grid that
   used to live at `index.html` is now `power-rankings.html`; don't point
   new "back to all teams"-style links at `index.html`. Each team page
   also shows a full
   season-by-season record/finish table (from `season_summaries.json`,
   not just the last couple seasons) linking to that team's Transactions
   page. Re-run this after editing `content.json` or any compute script's
   output; it's the only script that touches `docs/`.

Run order for a full rebuild from scratch: `fetch_data.py` →
`fetch_history.py` → `compute_teams.py` → `compute_history.py` →
`compute_analytics.py` → `compute_draft_flow.py` → `compute_trades.py` →
`compute_team_transactions.py` → `fetch_dynasty_values.py` →
`compute_trade_grades.py` → `build_site.py`. `compute_trades.py` must run
before `fetch_dynasty_values.py`, since the latter only pulls values for
players/picks that actually appear in `data/trades.json`. In practice the
fetch scripts only need re-running when Sleeper data changes (new season,
new trades) or, for `fetch_dynasty_values.py`, when new trades are added or
enough time has passed for more trades to cross a 1/2/3-year aging
checkpoint; the compute + build scripts are cheap and safe to re-run
anytime.

## Key decisions

- **Always join across seasons by `owner_id`/`user_id`, never by team
  name or season-specific `roster_id`.** Team names get rebranded often
  (see below) and `roster_id` numbering isn't guaranteed stable across
  different league_ids/seasons.
- **Display every historical result under the owner's current (2026) team
  name**, not whatever they were called that season. This matches how the
  league itself talks about its history and is far less confusing for
  readers. See the team-name-churn note below for why this matters.
- **Season standings tables sort by regular-season record (wins, then
  points), not by final playoff finish.** Playoff results (including
  upsets) are shown as a separate "Playoff Finish" badge column instead of
  reordering the table — a team that went 8-6 and won the bracket
  shouldn't display above a 12-2 team that lost early.
- **Head-to-head matrix only includes the 12 teams currently in the
  league.** Games against departed franchises (Allah's Army, Los Diablos,
  Zshep27, etc.) are real and counted in that season's standings, but
  aren't shown in the head-to-head grid since there's no current team to
  attribute them to.
- **The scouting-report prose (`data/content.json`) is meant to be
  genuinely opinionated**, not a neutral data summary: verdicts
  (Win-Now Contender / Contender / Retool / Rebuild), explicit strengths
  and weaknesses, and specific draft recommendations. Ground it in current
  research (web search for that year's rookie class and dynasty rankings)
  rather than training-data knowledge alone, since the site is meant to
  reflect the current market, not a snapshot from months ago.
- **No em dashes in any written prose on the site or in responses in this
  repo** — an explicit, standing style preference from the repo owner.
- League history (standings trends, championship results) should be used
  as light narrative context, not over-engineered — the depth of
  historical data pulled (full 2019–2025 matchups/transactions) ended up
  being useful for the Analytics and Draft Capital Flow pages, but the
  original ask was for "a reference for where teams are going into this
  season," not an exhaustive archive for its own sake.
- The raw Sleeper API data does not tell the full story for several
  seasons. The following corrections are known from the league's actual
  history and MUST be applied when building history, standings, or
  head-to-head pages — do not trust the raw API output alone for these
  cases.

## Platform history

- The league existed before Sleeper. **2018 was played on a different
  platform** (pre-Sleeper). There is no Sleeper league_id or API data for
  2018. The 2018 champion (Fuck Michael Thomas, beat Brock Hard) is a known
  fact from league history but cannot be verified or expanded on via API
  (no rosters, matchups, etc. exist for it).
- Sleeper history starts at the 2019 season (`previous_league_id` chain
  terminates at league_id `394148223893188608` / 2019, which has
  `previous_league_id: 0`).
- Known league_ids by season:
  - 2019: 394148223893188608
  - 2020: 515624360016109568
  - 2021: 650040105834221568
  - 2022: 787506053142216704
  - 2023: 915838243437330432
  - 2024: 1048295810074656768
  - 2025: 1182746000653811712
  - 2026: 1312135999710572544 (current, pre_draft as of writing)

## Team count changes

- League expanded around 2020/2021 to add a 13th real team, **Nikki's
  Victims**.
- To keep an even number of teams for scheduling, a **phantom 14th team,
  "Any Boul FFC," was added purely as a bye-week placeholder** — it never
  had real players, just scoreless roster spots. Whoever was scheduled
  against Any Boul FFC that week effectively got a bye. This phantom team
  must be **excluded from all real team lists, standings, analytics, and
  head-to-head records** — it is not a competitor.
- The league has since dropped back to 12 real teams by removing **two**
  teams: Any Boul FFC (the phantom) and **"Team 12" / "Allah's Army"** (a
  real team that left the league). So during the 13-real-team era
  (roughly 2021–2025), Sleeper's `num_teams` setting shows 14 (13 real +
  1 phantom); current 2026 settings show 12 real teams.
- When building any per-season team list, cross-check team names against
  known real teams and drop "Any Boul FFC" explicitly.
- Confirmed Sleeper `user_id`s (stable across seasons, unlike team names
  which get rebranded often):
  - **Any Boul FFC (phantom)**: `480904402215890944` — first appears 2021,
    present every season 2021–2025, absent from the 2026 league. Exclude
    from all standings/analytics/head-to-head for every season it appears.
  - **Team 12 / Allah's Army (removed real team)**: `406674259818065920` —
    present 2019 ("LTeamCaptain") through 2025 (as "🏳️‍🌈ALLAS ARMY🏳️‍🌈",
    renamed multiple times: Team 12 → 👑Team 45👑 → LastChanceUniversity →
    ALLAS ARMY), absent from the 2026 league. Include this team normally
    in historical seasons 2019–2025 (it was a real competitor), just don't
    expect it in 2026+ pages.
- **Team names change often season to season for the same owner** (e.g.
  the "Chicken Boys" owner (`user_id 394248955468185600`) was "The Poo Poo
  Bunch" in 2019 and "Simply Charming Fellows" from 2020–2024, only
  becoming "The Chicken Boys" in 2025). When displaying historical
  results, **use each owner's current (2026) team name throughout**, not
  the name they had that season — this matches how the league itself
  refers to its own history (e.g. "the Chicken Boys' four-peat
  2020–2023") and is far less confusing for readers. Always join
  historical data by `owner_id`/`user_id`, never by team name or
  season-specific `roster_id`.

## One owner has two Sleeper accounts across history: Shane / The Choo Choo Crew

- Shane (Sleeper `display_name` `shanetrainor`, current team **The Choo Choo
  Crew**, `user_id 1065778674277945344`) is the same person as the owner of
  a since-abandoned account that played 2019–2023 under `user_id
  394252838206713856` (team names "Sexy Wentzy" in 2019, "Nick Gives Me A
  Chubb" in 2020, "BeHated" 2021–2023). Confirmed by the repo owner
  2026-08: Shane lost the password to the old account in 2023 and made a
  new one, which is why "The Choo Choo Crew" appears to start fresh in
  2024 with no prior history despite being one of the league's original
  2019 members.
- This is **not** a case like Team 12/Allah's Army below — it's the same
  person on two different Sleeper accounts, not two different owners.
  **All computation scripts that build a `roster_owner` map (`roster_id ->
  owner_id`) must alias the old id to the new one** via an
  `OWNER_ALIASES = {"394252838206713856": "1065778674277945344"}` dict
  applied at that lookup, so 2019–2023 results, trades, and transactions
  join correctly with the current team, the same way name-only rebrands
  already do. Applied in `compute_history.py`, `compute_analytics.py`,
  `compute_draft_flow.py`, `compute_trades.py`, and
  `compute_team_transactions.py` (2026-08). Before this fix,
  `compute_team_transactions.py` silently dropped all of the old
  account's transactions entirely, since its ledger only initializes
  entries for current owners.
- If another such case turns up (a league member who changed Sleeper
  accounts), extend the same `OWNER_ALIASES` dict in each of those five
  scripts rather than inventing a new mechanism.

## 2022 season: schedule was messed up, but the API bracket checks out

- In 2022 the league messed up the regular-season schedule and had to push
  the playoffs back a week, and results were tracked manually on a
  spreadsheet at the time rather than trusted from Sleeper's UI.
- **Verified 2025-08 (this repo): the raw `winners_bracket` endpoint for
  the 2022 league_id (`787506053142216704`) actually already shows the
  correct result** — roster_id 1 (owner `394248955468185600`, the
  "Chicken Boys" owner, named "Simply Charming Fellows" that season) beats
  roster_id 8 (owner `394253124748980224`, Long Live Wopo) in the m6/p1
  final. Full bracket: 1st Chicken Boys, 2nd Long Live Wopo, 3rd Zshep27
  (`394252975431766016`), 4th BeHated (`394252838206713856`). This matches
  the league's own spreadsheet record and the championship list the
  commissioner gave directly ("2022 - The Chicken Boys beat Long Live
  Wopo"). **No override of the API bracket data is needed for 2022** —
  use `winners_bracket` from the fetched data as-is.
- One unresolved minor discrepancy: the commissioner's hand-drawn bracket
  image labels one of the round-2 byes as "2. The Choo Choo Crew," but the
  Choo Choo Crew owner (`user_id 1065778674277945344`) didn't join the
  league until 2024 and wasn't a 2022 participant. The actual round-2 bye
  in that slot per the API was BeHated (`394252838206713856`). This
  doesn't affect the champion/runner-up and isn't worth resolving further
  — just don't be surprised if you notice the mismatch.
- Confirmed 2025-08: the commissioner manually corrected the 2022 bracket
  in Sleeper's UI after the fact, which is why the API data is already
  right. **All 8 seasons' champions/runners-up (2019-2025 via API, plus
  2018 from the pre-Sleeper era) have been cross-checked against the
  commissioner's own list and match exactly** — no per-season overrides
  are needed anywhere. Trust `winners_bracket` from the fetched data
  as-is for every season 2019-2025.

## Week 14 "vs. league median" games (2022–2025 seasons only)

- Seasons 2022, 2023, 2024, and 2025 had a 14-week regular season (later
  seasons moved playoffs to start week 15). To avoid any one team getting
  two byes in a season with an odd/phantom team count, **week 14 of the
  regular season in each of these four seasons (2022–2025 inclusive) was
  not a real head-to-head matchup** — every team instead played against
  the league median score that week.
- Week 14 games in 2022–2025 **still count normally for standings,
  wins/losses, and points-for/against** (that's how the league officially
  scored them), but they must be **excluded when computing all-time
  head-to-head records between specific team pairs**, since the "opponent"
  listed in the raw matchup data for that week is not a real opponent.
- This does not apply to 2019–2021 (no median week existed yet) or to
  2026+ once the playoff start moved to week 15 and the team count
  normalized back to 12.

## The Luck section's win/loss rules (`compute_analytics.py`)

`compute_luck()`'s `regular_season_weeks()` helper decides which weeks
count. Two rules, applied to every season 2019–2026:

- **Discard any week `>= playoff_week_start`** for that season (each
  season's value lives at `data["league"]["settings"]["playoff_week_start"]`
  in its history file). Sleeper still returns matchup data through the end
  of the playoffs, including for teams that missed the playoffs (they land
  in a "toilet bowl" consolation bracket instead), but none of that is
  part of the official regular-season record — a roster's
  `settings.wins`/`settings.losses` only ever sums to the regular-season
  week count.
- **Always discard week 14, in every season**, full stop — not
  conditionally by season. Some seasons (2023–2025) used week 14 as a
  "vs. league median" week with no real opponent; rather than track which
  seasons actually did that, week 14 is simply never counted, by explicit
  choice (2026-08). This is a deliberate simplification: for the seasons
  where week 14 was a real, opponent-based game (2019–2022, since 2022's
  `playoff_week_start` is 14, same as 2019–2021, meaning week 14 there was
  already a playoff week anyway), that one week's result is now discarded
  too, even though it was real. The tradeoff was accepted for simplicity
  over exactness — don't try to special-case it back in without asking.
- A real team's game against the phantom "Any Boul FFC" bye team still
  counts as a normal result for that team (it's a real win/loss in the
  official record) — only the phantom side itself is never credited a
  win. `compute_history.py`'s `head_to_head()` matrix uses its own,
  separate median/playoff-week exclusion (see above), since it has a
  stricter requirement: it needs a real opponent to attribute the result
  to, not just a real result.

## Dynasty trade grading (`fetch_dynasty_values.py`, `compute_trade_grades.py`)

The Trades Hub shows a Dynasty Value grade on each trade: what each side was
worth at the moment of the trade, versus the average of its value 1, 2, and 3
years later (whichever of those have elapsed so far).

- **KeepTradeCut was considered and rejected as the value source.** It's the
  most widely cited dynasty value site, but its Terms & Conditions
  explicitly prohibit "web scraping, data mining, data extraction... use of
  bots or crawlers" and redistributing its data, with no carve-out for
  non-commercial use (checked 2026-08). `robots.txt` alone would technically
  allow a crawler through, but that doesn't override the contractual
  prohibition in the ToS. **Don't scrape KeepTradeCut for this site.**
- **DynastyProcess (`github.com/dynastyprocess/data`) is used instead** — an
  open-data repo explicitly meant to be consumed programmatically. It
  doesn't publish a dated archive, but its git commit history for
  `files/values-players.csv` effectively is one: every commit is a dated
  snapshot of that day's values. `fetch_dynasty_values.py` fetches whichever
  commits are needed for each trade directly via
  `raw.githubusercontent.com/dynastyprocess/data/{commit_sha}/...`.
- **Grades are NOT "value at trade time" vs. "value today."** A trade from
  2019 graded against 2026 values would show both sides near zero just from
  players naturally aging out of dynasty relevance by now, regardless of
  whether the trade itself was any good — that would make every old trade
  look meaningless and bias grades toward whatever's recent. Instead the
  comparison point is fixed *relative to the trade date* (1/2/3 years later,
  averaged), so every trade is graded on the same relative clock. Don't
  change this back to a fixed "today" comparison without discussing the
  bias it reintroduces.
- **Two schema eras, handled explicitly, not smoothed over:** DynastyProcess
  switched from an ECR-rank-only schema (`mergename`, `dynoECR`, no dollar
  value, no `fp_id` to join on) to the modern one (`fp_id`, `value_1qb`)
  around commit `9f08039c` (2020-05-04). Snapshots older than that have no
  value data in a usable form at all, so trades from before ~May 2020 are
  simply left ungraded rather than approximated — don't try to reconstruct
  values for that era from the rank-only columns.
- **Draft picks don't have a `value_1qb` in DynastyProcess's data**, only an
  ECR rank (`values-picks.csv`). To put picks on the same value scale as
  players, `fetch_dynasty_values.py` converts a pick's ECR to a value by
  finding the player in that same snapshot with the closest ECR and using
  their `value_1qb` — a same-day nearest-rank bridge, not a fitted formula.
  Picks are matched by season + round only (our trade data doesn't track
  exact draft slot), using the round-average row DynastyProcess publishes
  when one exists, or averaging the exact-slot/tiered rows for that round
  otherwise.
- **Both `hist_complete`/`aged_complete` flags matter.** A side's total is
  marked incomplete if any asset in it couldn't be valued in a given
  snapshot (crosswalk miss, or the player/pick just isn't in that
  snapshot). Incomplete totals are still a *lower bound*, not garbage, and
  are shown as such in the UI rather than hidden — don't discard them.

## General rule

When in doubt about a specific season's historical results, prefer the
league's own record of events (as given by the commissioner/user) over
whatever the raw Sleeper API returns, and note the discrepancy rather than
silently picking one source.
