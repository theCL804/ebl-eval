# Ethel's Dynasty — league quirks and data caveats

This repo builds a static analysis/history site for a Sleeper dynasty fantasy
football league ("Ethel's Dynasty", league_id `1312135999710572544` for 2026).
The raw Sleeper API data does not tell the full story for several seasons.
The following corrections are known from the league's actual history and
MUST be applied when building history, standings, or head-to-head pages —
do not trust the raw API output alone for these cases.

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

## General rule

When in doubt about a specific season's historical results, prefer the
league's own record of events (as given by the commissioner/user) over
whatever the raw Sleeper API returns, and note the discrepancy rather than
silently picking one source.
