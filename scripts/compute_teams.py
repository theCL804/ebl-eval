#!/usr/bin/env python3
"""Combine raw Sleeper data into one consolidated data/teams.json per team."""
import json
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DRAFT_SEASONS = ["2026", "2027", "2028"]
NUM_TEAMS = 12
DRAFT_ROUNDS = 4

POSITION_GROUPS = ["QB", "RB", "WR", "TE"]


def load(name):
    return json.loads((DATA_DIR / name).read_text())


def main():
    league = load("league.json")
    users = load("users.json")
    rosters = load("rosters.json")
    traded_picks = load("traded_picks.json")
    players = load("players.json")
    history = load("history.json")

    user_by_id = {u["user_id"]: u for u in users}

    # roster_id -> owner_id map for translating traded pick "roster_id" (original owner)
    roster_owner = {r["roster_id"]: r["owner_id"] for r in rosters}

    # build draft pick ownership: default each roster owns its own picks each round/season
    # then apply overrides from traded_picks
    pick_owner = {}  # (season, round, original_roster_id) -> current owner roster_id
    for season in DRAFT_SEASONS:
        for rnd in range(1, DRAFT_ROUNDS + 1):
            for r in rosters:
                pick_owner[(season, rnd, r["roster_id"])] = r["roster_id"]
    for tp in traded_picks:
        key = (tp["season"], tp["round"], tp["roster_id"])
        if key in pick_owner:
            pick_owner[key] = tp["owner_id"]

    # invert: roster_id -> list of picks it currently holds
    picks_held = {r["roster_id"]: [] for r in rosters}
    for (season, rnd, orig_roster), owner_roster in pick_owner.items():
        picks_held[owner_roster].append({"season": season, "round": rnd, "original_roster_id": orig_roster})

    for v in picks_held.values():
        v.sort(key=lambda p: (p["season"], p["round"]))

    # recent history keyed by owner_id
    history_by_owner = {}
    for season_entry in history:
        season = season_entry["season"]
        for r in season_entry["rosters"]:
            history_by_owner.setdefault(r["owner_id"], []).append(
                {
                    "season": season,
                    "wins": r["settings"].get("wins", 0),
                    "losses": r["settings"].get("losses", 0),
                    "ties": r["settings"].get("ties", 0),
                    "fpts": r["settings"].get("fpts", 0) + r["settings"].get("fpts_decimal", 0) / 100,
                }
            )
    for v in history_by_owner.values():
        v.sort(key=lambda s: s["season"])

    teams = []
    for r in rosters:
        owner = user_by_id.get(r["owner_id"], {})
        raw_team_name = (owner.get("metadata") or {}).get("team_name")
        if raw_team_name in (None, "", "_"):
            raw_team_name = None
        team_name = raw_team_name or owner.get("display_name") or "Unknown"

        player_ids = r.get("players") or []
        starter_ids = set(r.get("starters") or [])

        roster_players = []
        for pid in player_ids:
            p = players.get(pid)
            if not p:
                continue
            roster_players.append(
                {
                    "player_id": pid,
                    "name": p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
                    "position": p.get("position"),
                    "team": p.get("team"),
                    "age": p.get("age"),
                    "years_exp": p.get("years_exp"),
                    "status": p.get("status"),
                    "injury_status": p.get("injury_status"),
                    "is_starter": pid in starter_ids,
                }
            )

        ages = [p["age"] for p in roster_players if p["age"] is not None]
        pos_counts = {}
        pos_avg_age = {}
        for pos in POSITION_GROUPS:
            pos_players = [p for p in roster_players if p["position"] == pos]
            pos_counts[pos] = len(pos_players)
            pos_ages = [p["age"] for p in pos_players if p["age"] is not None]
            pos_avg_age[pos] = round(mean(pos_ages), 1) if pos_ages else None

        teams.append(
            {
                "roster_id": r["roster_id"],
                "owner_id": r["owner_id"],
                "display_name": owner.get("display_name"),
                "team_name": team_name,
                "avatar": owner.get("avatar"),
                "record": r["settings"],
                "roster": sorted(roster_players, key=lambda p: (not p["is_starter"], p["position"] or "")),
                "avg_age": round(mean(ages), 1) if ages else None,
                "position_counts": pos_counts,
                "position_avg_age": pos_avg_age,
                "draft_picks": picks_held[r["roster_id"]],
                "recent_history": history_by_owner.get(r["owner_id"], []),
            }
        )

    teams.sort(key=lambda t: t["roster_id"])
    (DATA_DIR / "teams.json").write_text(json.dumps(teams, indent=2))
    print(f"wrote data/teams.json with {len(teams)} teams")


if __name__ == "__main__":
    main()
