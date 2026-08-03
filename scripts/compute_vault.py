#!/usr/bin/env python3
"""Compute The Vault: all-time (2019-2026) records and streaks from
data/history/*.json. Writes data/vault.json.

Game-level records (highest/lowest team score) use every real matchup
entry regardless of week, since a team's own score that week is real no
matter what. Margin-based records (biggest blowout, closest game) need a
*real* opponent, so they reuse the same "discard week 14, every season"
rule as compute_analytics.py's regular_season_weeks() -- some seasons
played week 14 against the league median instead of a real opponent, and
Sleeper's raw data still pairs everyone against a fictional matchup_id
that week, so a "blowout" or "closest game" computed from that pairing
would be meaningless. See CLAUDE.md's "Week 14" section.

Player-level records (best individual game, worst started player) only
look at players in a team's starting lineup that week -- a bench player's
raw point total isn't a meaningful record on its own.

A team's whole game is dropped from every score/player record (not just
"lowest score") if most of its starters scored exactly 0.0 that week --
see neglected_lineup(). That's the signature of a manager starting known-
bye/inactive players on purpose (e.g. already clinched a playoff seed and
tanking a meaningless week), not just an honest bad week: a lineup that
actually played, even badly, comes back with small positive scores across
the board, not a wall of zeros. Tried a hindsight "hypothetical optimal
lineup vs. actual" gap check first, but that flagged perfectly legitimate
games too -- a deep bench that happens to outscore the starters in
hindsight is just normal variance, not neglect, and start/sit calls are
made before kickoff without hindsight anyway.

Streaks (win/loss, and weekly top-scorer) are restricted to real regular-
season games (regular_season_weeks(), imported from compute_analytics.py)
for the same reason compute_luck() is: toilet-bowl/consolation-bracket
games and the week-14 median-week fiction would muddy what a "streak"
even means.
"""
import json
from pathlib import Path

import compute_analytics as ca

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
PHANTOM_OWNER_ID = "480904402215890944"
OWNER_ALIASES = {"394252838206713856": "1065778674277945344"}
SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
DISCARD_WEEK = 14
# a lineup where at least this fraction of starters scored exactly 0.0 is
# treated as "didn't set a lineup" and dropped from records entirely.
NEGLECTED_ZERO_FRACTION = 0.5


def load(path):
    return json.loads(path.read_text())


def neglected_lineup(starters, starters_points):
    """True if most of a team's starting lineup scored exactly 0.0 that
    week -- the signature of starting known-bye/inactive players on
    purpose rather than an honest (if unlucky) week."""
    valid = [pts for pid, pts in zip(starters or [], starters_points or []) if pid != "0" and pts is not None]
    if not valid:
        return False
    zero_count = sum(1 for pts in valid if pts == 0)
    return zero_count / len(valid) >= NEGLECTED_ZERO_FRACTION


def main():
    teams = load(DATA_DIR / "teams.json")
    players = load(DATA_DIR / "players.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    last_known_name = {}

    def display_name(owner_id):
        return owner_to_name.get(owner_id) or last_known_name.get(owner_id) or "(departed team)"

    all_season_data = {}
    for season in SEASONS:
        path = HISTORY_DIR / f"{season}.json"
        if path.exists():
            all_season_data[season] = load(path)

    highest_score = None
    lowest_score = None
    biggest_blowout = None
    closest_game = None
    best_individual = None
    worst_started = None

    # owner_id -> list of (season, week, result) in chronological order, result in {"W","L","T"}
    results_by_owner = {}
    # (season, week) -> [(owner_id, points), ...] for the weekly-top-scorer streak
    weekly_scores = []

    for season in SEASONS:
        data = all_season_data.get(season)
        if not data:
            continue
        roster_owner = {r["roster_id"]: OWNER_ALIASES.get(r["owner_id"], r["owner_id"]) for r in data["rosters"]}
        for u in data["users"]:
            name = (u.get("metadata") or {}).get("team_name") or u["display_name"]
            last_known_name[u["user_id"]] = name
        playoff_week_start = data["league"]["settings"]["playoff_week_start"]

        for week_str, matchups in data.get("matchups_by_week", {}).items():
            week = int(week_str)

            # a real team's bye week against the phantom "Any Boul FFC" isn't a
            # meaningful score (lineups often aren't optimized for a guaranteed
            # win against a 0-point opponent) -- exclude whoever was paired
            # with the phantom's matchup_id that week from score records too,
            # not just from the blowout/closest-game pairing below.
            bye_matchup_ids = {
                m["matchup_id"]
                for m in matchups
                if roster_owner.get(m["roster_id"]) == PHANTOM_OWNER_ID and m.get("matchup_id") is not None
            }

            # --- game/player score records: every real matchup entry, any week ---
            by_matchup_id = {}
            for m in matchups:
                owner = roster_owner.get(m["roster_id"])
                if not owner or owner == PHANTOM_OWNER_ID:
                    continue
                if m.get("matchup_id") in bye_matchup_ids:
                    continue
                pts = m.get("points") or 0.0

                # a lineup that's mostly known-inactive/bye players wasn't
                # really "played" that week -- e.g. a team already locked
                # into a playoff seed benching every real starter -- so it
                # shouldn't be eligible for score/player records at all,
                # not just "lowest score."
                if neglected_lineup(m.get("starters"), m.get("starters_points")):
                    continue

                if highest_score is None or pts > highest_score["points"]:
                    highest_score = {"owner_id": owner, "team_name": display_name(owner), "points": round(pts, 2), "season": season, "week": week}
                if lowest_score is None or pts < lowest_score["points"]:
                    lowest_score = {"owner_id": owner, "team_name": display_name(owner), "points": round(pts, 2), "season": season, "week": week}

                for player_id, ppts in zip(m.get("starters") or [], m.get("starters_points") or []):
                    if player_id == "0" or ppts is None:
                        continue
                    p = players.get(player_id)
                    entry = {
                        "player_id": player_id,
                        "name": p.get("full_name") if p else f"Player {player_id}",
                        "position": p.get("position") if p else None,
                        "owner_id": owner,
                        "team_name": display_name(owner),
                        "points": round(ppts, 2),
                        "season": season,
                        "week": week,
                    }
                    if best_individual is None or ppts > best_individual["points"]:
                        best_individual = entry
                    if worst_started is None or ppts < worst_started["points"]:
                        worst_started = entry

                if m.get("matchup_id") is not None:
                    by_matchup_id.setdefault(m["matchup_id"], []).append((owner, pts))

            # --- margin-based records: real opponents only (discard week 14) ---
            if week != DISCARD_WEEK:
                for pair in by_matchup_id.values():
                    if len(pair) != 2:
                        continue
                    (oa, pa), (ob, pb) = pair
                    margin = round(abs(pa - pb), 2)
                    game = {
                        "team_a": {"owner_id": oa, "team_name": display_name(oa), "points": round(pa, 2)},
                        "team_b": {"owner_id": ob, "team_name": display_name(ob), "points": round(pb, 2)},
                        "margin": margin,
                        "season": season,
                        "week": week,
                    }
                    if biggest_blowout is None or margin > biggest_blowout["margin"]:
                        biggest_blowout = game
                    if margin > 0 and (closest_game is None or margin < closest_game["margin"]):
                        closest_game = game

        # --- streaks: real regular-season games only ---
        for week, pairs in sorted(ca.regular_season_weeks(data.get("matchups_by_week", {}), playoff_week_start), key=lambda x: x[0]):
            pool = {}
            for pair in pairs:
                for m in pair:
                    owner = roster_owner.get(m["roster_id"])
                    if owner and owner != PHANTOM_OWNER_ID:
                        pool[owner] = m.get("points", 0) or 0
            if pool:
                top_owner = max(pool, key=pool.get)
                weekly_scores.append((season, week, top_owner))

            for m1, m2 in pairs:
                o1, o2 = roster_owner.get(m1["roster_id"]), roster_owner.get(m2["roster_id"])
                if not o1 or not o2 or o1 == PHANTOM_OWNER_ID or o2 == PHANTOM_OWNER_ID:
                    continue
                p1, p2 = m1.get("points", 0) or 0, m2.get("points", 0) or 0
                r1 = "W" if p1 > p2 else ("L" if p2 > p1 else "T")
                r2 = "W" if p2 > p1 else ("L" if p1 > p2 else "T")
                results_by_owner.setdefault(o1, []).append((season, week, r1))
                results_by_owner.setdefault(o2, []).append((season, week, r2))

    def find_streaks(results, wanted):
        """Longest run of `wanted` ("W" or "L") in a chronological result
        list, returned as every maximal run (so a team's history can show
        more than one streak if it wants to compare its best runs)."""
        runs = []
        current = None
        for season, week, result in sorted(results, key=lambda x: (x[0], x[1])):
            if result == wanted:
                if current is None:
                    current = {"start_season": season, "start_week": week, "end_season": season, "end_week": week, "length": 1}
                else:
                    current["end_season"], current["end_week"] = season, week
                    current["length"] += 1
            else:
                if current:
                    runs.append(current)
                current = None
        if current:
            runs.append(current)
        return runs

    def top_streaks(wanted, limit=10):
        leaderboard = []
        for owner, results in results_by_owner.items():
            for run in find_streaks(results, wanted):
                leaderboard.append({**run, "owner_id": owner, "team_name": display_name(owner)})
        leaderboard.sort(key=lambda r: -r["length"])
        return leaderboard[:limit]

    # weekly top-scorer streaks: consecutive weeks (chronological, across all history)
    # where the same owner had the week's single highest regular-season score
    weekly_scores.sort(key=lambda x: (x[0], x[1]))
    scorer_runs = []
    current = None
    for season, week, owner in weekly_scores:
        if current and current["owner_id"] == owner:
            current["end_season"], current["end_week"] = season, week
            current["length"] += 1
        else:
            if current:
                scorer_runs.append(current)
            current = {"owner_id": owner, "start_season": season, "start_week": week, "end_season": season, "end_week": week, "length": 1}
    if current:
        scorer_runs.append(current)
    for r in scorer_runs:
        r["team_name"] = display_name(r["owner_id"])
    scorer_runs.sort(key=lambda r: -r["length"])

    vault = {
        "game_records": {
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "biggest_blowout": biggest_blowout,
            "closest_game": closest_game,
        },
        "player_records": {
            "best_individual": best_individual,
            "worst_started": worst_started,
        },
        "streaks": {
            "win_streaks": top_streaks("W"),
            "loss_streaks": top_streaks("L"),
            "top_scorer_streaks": scorer_runs[:10],
        },
    }
    (DATA_DIR / "vault.json").write_text(json.dumps(vault, indent=2))
    print("wrote vault.json")


if __name__ == "__main__":
    main()
