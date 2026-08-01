#!/usr/bin/env python3
"""Compute season summaries and all-time head-to-head records from data/history/*.json.

See CLAUDE.md for the league-specific rules this implements: exclude the
phantom "Any Boul FFC" team, exclude week 14 of the 2022-2025 seasons from
head-to-head (those were "vs. league median" weeks with no real opponent),
and exclude playoff/consolation-bracket weeks (Sleeper still returns
matchup data for those, but they aren't part of the regular-season
head-to-head history this matrix represents).
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"

PHANTOM_OWNER_ID = "480904402215890944"
# Shane's 2019-2023 account (BeHated/Nick Gives Me A Chubb/Sexy Wentzy) locked
# him out in 2023, so he made a new Sleeper account, which became The Choo
# Choo Crew in 2024. Same person; alias the old id to the new one so his
# 2019-2023 history joins correctly with his current team.
OWNER_ALIASES = {"394252838206713856": "1065778674277945344"}
MEDIAN_WEEK_SEASONS = {2022, 2023, 2024, 2025}
MEDIAN_WEEK = 14

SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]


def load(path):
    return json.loads(path.read_text())


def current_team_lookup():
    teams = load(DATA_DIR / "teams.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    current_owner_ids = set(owner_to_name.keys())
    return owner_to_name, current_owner_ids


def build_placements(winners_bracket):
    """Map roster_id -> finishing place, from the 'p' (placement) matches."""
    placements = {}
    for m in winners_bracket:
        p = m.get("p")
        if not p:
            continue
        if "w" in m:
            placements[m["w"]] = p
        if "l" in m:
            placements[m["l"]] = p + 1
    return placements


def season_summary(season, data, owner_to_name):
    rosters = data["rosters"]
    roster_owner = {r["roster_id"]: OWNER_ALIASES.get(r["owner_id"], r["owner_id"]) for r in rosters}
    placements = build_placements(data["winners_bracket"])
    season_name_by_owner = {
        u["user_id"]: (u.get("metadata") or {}).get("team_name") or u["display_name"] for u in data["users"]
    }

    standings = []
    for r in rosters:
        owner_id = OWNER_ALIASES.get(r["owner_id"], r["owner_id"])
        if owner_id == PHANTOM_OWNER_ID:
            continue
        settings = r["settings"]
        fpts = settings.get("fpts", 0) + settings.get("fpts_decimal", 0) / 100
        fpts_against = settings.get("fpts_against", 0) + settings.get("fpts_against_decimal", 0) / 100
        name = owner_to_name.get(owner_id) or season_name_by_owner.get(owner_id) or "(unknown team)"
        standings.append(
            {
                "owner_id": owner_id,
                "team_name": name,
                "wins": settings.get("wins", 0),
                "losses": settings.get("losses", 0),
                "ties": settings.get("ties", 0),
                "points_for": round(fpts, 2),
                "points_against": round(fpts_against, 2),
                "place": placements.get(r["roster_id"]),
            }
        )

    # sort by regular-season record first (what a "standings" table means),
    # not by final playoff finish -- upsets in the bracket are shown as a
    # separate place/badge rather than reordering the table
    standings.sort(key=lambda s: (-s["wins"], -s["points_for"]))
    champion = next((s for s in standings if s["place"] == 1), None)
    runner_up = next((s for s in standings if s["place"] == 2), None)
    third = next((s for s in standings if s["place"] == 3), None)

    return {
        "season": season,
        "champion": champion["team_name"] if champion else None,
        "champion_owner_id": champion["owner_id"] if champion else None,
        "runner_up": runner_up["team_name"] if runner_up else None,
        "runner_up_owner_id": runner_up["owner_id"] if runner_up else None,
        "third": third["team_name"] if third else None,
        "standings": standings,
    }


def head_to_head(all_season_data, current_owner_ids):
    matrix = {}  # owner_id -> owner_id -> {wins, losses, ties, pf, pa, games}

    def cell(a, b):
        matrix.setdefault(a, {}).setdefault(
            b, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0, "games": 0}
        )
        return matrix[a][b]

    for season, data in all_season_data.items():
        roster_owner = {r["roster_id"]: OWNER_ALIASES.get(r["owner_id"], r["owner_id"]) for r in data["rosters"]}
        playoff_week_start = data["league"]["settings"]["playoff_week_start"]
        for week_str, matchups in data["matchups_by_week"].items():
            week = int(week_str)
            if week >= playoff_week_start:
                continue
            if season in MEDIAN_WEEK_SEASONS and week == MEDIAN_WEEK:
                continue
            by_matchup_id = {}
            for m in matchups:
                if m.get("matchup_id") is None:
                    continue
                by_matchup_id.setdefault(m["matchup_id"], []).append(m)
            for pair in by_matchup_id.values():
                if len(pair) != 2:
                    continue
                m1, m2 = pair
                owner1 = roster_owner.get(m1["roster_id"])
                owner2 = roster_owner.get(m2["roster_id"])
                if not owner1 or not owner2:
                    continue
                if owner1 == PHANTOM_OWNER_ID or owner2 == PHANTOM_OWNER_ID:
                    continue
                if owner1 not in current_owner_ids or owner2 not in current_owner_ids:
                    continue
                p1, p2 = m1.get("points", 0) or 0, m2.get("points", 0) or 0

                c1, c2 = cell(owner1, owner2), cell(owner2, owner1)
                c1["games"] += 1
                c2["games"] += 1
                c1["points_for"] += p1
                c1["points_against"] += p2
                c2["points_for"] += p2
                c2["points_against"] += p1
                if p1 > p2:
                    c1["wins"] += 1
                    c2["losses"] += 1
                elif p2 > p1:
                    c2["wins"] += 1
                    c1["losses"] += 1
                else:
                    c1["ties"] += 1
                    c2["ties"] += 1

    return matrix


def rivalry_games(all_season_data, current_owner_ids, owner_to_name):
    """Per-pair chronological game log, for the rivalries page. Same filtering
    rules as head_to_head() (regular season only, week 14 excluded, phantom and
    departed franchises excluded), but keeps every individual game rather than
    just the aggregate record.
    """
    pair_games = {}  # frozenset({a, b}) -> list of games

    for season in sorted(all_season_data):
        data = all_season_data[season]
        roster_owner = {r["roster_id"]: OWNER_ALIASES.get(r["owner_id"], r["owner_id"]) for r in data["rosters"]}
        playoff_week_start = data["league"]["settings"]["playoff_week_start"]
        for week_str, matchups in sorted(data["matchups_by_week"].items(), key=lambda kv: int(kv[0])):
            week = int(week_str)
            if week >= playoff_week_start:
                continue
            if season in MEDIAN_WEEK_SEASONS and week == MEDIAN_WEEK:
                continue
            by_matchup_id = {}
            for m in matchups:
                if m.get("matchup_id") is None:
                    continue
                by_matchup_id.setdefault(m["matchup_id"], []).append(m)
            for pair in by_matchup_id.values():
                if len(pair) != 2:
                    continue
                m1, m2 = pair
                owner1 = roster_owner.get(m1["roster_id"])
                owner2 = roster_owner.get(m2["roster_id"])
                if not owner1 or not owner2:
                    continue
                if owner1 == PHANTOM_OWNER_ID or owner2 == PHANTOM_OWNER_ID:
                    continue
                if owner1 not in current_owner_ids or owner2 not in current_owner_ids:
                    continue
                p1, p2 = m1.get("points", 0) or 0, m2.get("points", 0) or 0
                a, b = sorted((owner1, owner2))
                a_score, b_score = (p1, p2) if owner1 == a else (p2, p1)
                pair_games.setdefault(frozenset((a, b)), []).append(
                    {
                        "season": season,
                        "week": week,
                        "a_score": round(a_score, 2),
                        "b_score": round(b_score, 2),
                    }
                )

    pairs = []
    for key, games in pair_games.items():
        a, b = sorted(key)
        a_wins = sum(1 for g in games if g["a_score"] > g["b_score"])
        b_wins = sum(1 for g in games if g["b_score"] > g["a_score"])
        ties = len(games) - a_wins - b_wins
        pairs.append(
            {
                "a": a,
                "b": b,
                "a_name": owner_to_name.get(a, "(unknown team)"),
                "b_name": owner_to_name.get(b, "(unknown team)"),
                "a_wins": a_wins,
                "b_wins": b_wins,
                "ties": ties,
                "a_points": round(sum(g["a_score"] for g in games), 2),
                "b_points": round(sum(g["b_score"] for g in games), 2),
                "games": games,
            }
        )
    pairs.sort(key=lambda p: (p["a_name"], p["b_name"]))
    return pairs


def main():
    owner_to_name, current_owner_ids = current_team_lookup()

    all_season_data = {}
    summaries = []
    for season in SEASONS:
        path = HISTORY_DIR / f"{season}.json"
        if not path.exists():
            continue
        data = load(path)
        all_season_data[season] = data
        summaries.append(season_summary(season, data, owner_to_name))

    # 2018 predates Sleeper entirely; add as a manual entry (see CLAUDE.md)
    summaries.insert(
        0,
        {
            "season": 2018,
            "champion": "Fuck Michael Thomas",
            "champion_owner_id": None,
            "runner_up": "Brock Hard",
            "runner_up_owner_id": None,
            "third": None,
            "standings": [],
            "note": "Pre-Sleeper season, played on a different platform. Only the championship result is known.",
        },
    )

    (DATA_DIR / "season_summaries.json").write_text(json.dumps(summaries, indent=2))
    print(f"wrote season_summaries.json ({len(summaries)} seasons)")

    matrix = head_to_head(all_season_data, current_owner_ids)
    (DATA_DIR / "head_to_head.json").write_text(json.dumps(matrix, indent=2))
    print(f"wrote head_to_head.json ({len(matrix)} teams)")

    pairs = rivalry_games(all_season_data, current_owner_ids, owner_to_name)
    (DATA_DIR / "rivalries.json").write_text(json.dumps(pairs, indent=2))
    print(f"wrote rivalries.json ({len(pairs)} pairs)")


if __name__ == "__main__":
    main()
