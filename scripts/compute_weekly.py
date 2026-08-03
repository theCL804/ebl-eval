#!/usr/bin/env python3
"""Compute weekly recap data (scores + transactions) for the current
(2026) season only -- data/history/2026.json's matchups_by_week only ever
contains weeks that have actually been played (fetch_history.py stops
fetching the first week Sleeper returns empty), so every key present here
is real. Writes data/weekly.json: one entry per played week with every
game's score, the week's highlight stats, and that week's transactions.

The AI-written recap prose that goes with each week's scores lives in
data/weekly_recap_prose.json instead -- hand/AI-authored per week, same
spirit as data/content.json's scouting reports, edited directly rather
than generated here.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
SEASON = 2026
PHANTOM_OWNER_ID = "480904402215890944"
OWNER_ALIASES = {"394252838206713856": "1065778674277945344"}


def load(path):
    return json.loads(path.read_text())


def player_info(players, player_id):
    p = players.get(player_id)
    return {
        "player_id": player_id,
        "name": p.get("full_name") if p else f"Player {player_id}",
        "position": p.get("position") if p else None,
        "team": p.get("team") if p else None,
    }


def game_key(owner_a, owner_b):
    return "-".join(sorted([owner_a, owner_b]))


def main():
    teams = load(DATA_DIR / "teams.json")
    players = load(DATA_DIR / "players.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}

    path = HISTORY_DIR / f"{SEASON}.json"
    if not path.exists():
        (DATA_DIR / "weekly.json").write_text(json.dumps({"season": SEASON, "weeks": []}, indent=2))
        print("no history file for the current season yet; wrote empty weekly.json")
        return

    data = load(path)
    roster_owner = {r["roster_id"]: OWNER_ALIASES.get(r["owner_id"], r["owner_id"]) for r in data["rosters"]}

    def team(owner_id):
        return {"owner_id": owner_id, "name": owner_to_name.get(owner_id, "(unknown team)")}

    weeks = []
    for week_str, matchups in sorted(data.get("matchups_by_week", {}).items(), key=lambda kv: int(kv[0])):
        week = int(week_str)
        by_matchup = {}
        for m in matchups:
            owner = roster_owner.get(m["roster_id"])
            if not owner or owner == PHANTOM_OWNER_ID:
                continue
            by_matchup.setdefault(m["matchup_id"], []).append((owner, m.get("points") or 0.0))

        games = []
        for entries in by_matchup.values():
            if len(entries) != 2:
                continue  # not a real head-to-head game (e.g. a median week) -- skip
            (owner_a, pts_a), (owner_b, pts_b) = entries
            margin = round(abs(pts_a - pts_b), 2)
            winner = owner_a if pts_a > pts_b else (owner_b if pts_b > pts_a else None)
            games.append(
                {
                    "game_key": game_key(owner_a, owner_b),
                    "team_a": {**team(owner_a), "points": round(pts_a, 2)},
                    "team_b": {**team(owner_b), "points": round(pts_b, 2)},
                    "margin": margin,
                    "winner_owner_id": winner,
                }
            )
        if not games:
            continue

        all_scores = [(g["team_a"], g) for g in games] + [(g["team_b"], g) for g in games]
        top = max(all_scores, key=lambda x: x[0]["points"])[0]
        low = min(all_scores, key=lambda x: x[0]["points"])[0]
        decided = [g for g in games if g["margin"] > 0]
        closest = min(decided, key=lambda g: g["margin"]) if decided else None
        blowout = max(games, key=lambda g: g["margin"])

        transactions = []
        for t in data.get("transactions_by_week", {}).get(week_str, []):
            if t.get("status") != "complete":
                continue
            ttype = t.get("type")
            if ttype not in ("trade", "waiver", "free_agent"):
                continue
            roster_ids = t.get("roster_ids") or []
            owners = [roster_owner.get(rid) for rid in roster_ids]
            owners = [o for o in owners if o and o != PHANTOM_OWNER_ID]
            if not owners:
                continue
            adds = t.get("adds") or {}
            drops = t.get("drops") or {}

            if ttype == "trade":
                if len(set(owners)) < 2:
                    continue
                sides = {o: {"players": [], "picks": []} for o in set(owners)}
                for player_id, roster_id in adds.items():
                    owner = roster_owner.get(roster_id)
                    if owner in sides:
                        sides[owner]["players"].append(player_info(players, player_id))
                for dp in t.get("draft_picks") or []:
                    owner = roster_owner.get(dp["owner_id"])
                    if owner in sides:
                        sides[owner]["picks"].append({"season": dp["season"], "round": dp["round"]})
                transactions.append(
                    {
                        "type": "trade",
                        "transaction_id": t["transaction_id"],
                        "created": t.get("created"),
                        "teams": sorted(set(owners)),
                        "team_names": {o: owner_to_name.get(o, "(unknown team)") for o in set(owners)},
                        "sides": sides,
                    }
                )
            else:
                owner = owners[0]
                transactions.append(
                    {
                        "type": ttype,
                        "transaction_id": t["transaction_id"],
                        "created": t.get("created"),
                        "owner_id": owner,
                        "name": owner_to_name.get(owner, "(unknown team)"),
                        "gave": [player_info(players, pid) for pid, rid in drops.items() if roster_owner.get(rid) == owner],
                        "received": [player_info(players, pid) for pid, rid in adds.items() if roster_owner.get(rid) == owner],
                    }
                )
        transactions.sort(key=lambda x: x["created"] or 0, reverse=True)

        weeks.append(
            {
                "week": week,
                "games": games,
                "highlights": {
                    "top_scorer": top,
                    "low_scorer": low,
                    "closest_game": closest,
                    "biggest_blowout": blowout,
                },
                "transactions": transactions,
            }
        )

    weeks.sort(key=lambda w: w["week"], reverse=True)
    (DATA_DIR / "weekly.json").write_text(json.dumps({"season": SEASON, "weeks": weeks}, indent=2))
    print(f"wrote weekly.json: {len(weeks)} played week(s) for {SEASON}")


if __name__ == "__main__":
    main()
