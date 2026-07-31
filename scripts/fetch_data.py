#!/usr/bin/env python3
"""Pull league data from the Sleeper API and cache it as JSON under data/."""
import json
import urllib.request
from pathlib import Path

LEAGUE_ID = "1312135999710572544"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BASE = "https://api.sleeper.app/v1"

# how many prior seasons to pull for trend context (not a full history rebuild)
PRIOR_SEASONS = 2


def get(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def save(name, obj):
    path = DATA_DIR / name
    path.write_text(json.dumps(obj, indent=2))
    print(f"wrote {path} ({len(json.dumps(obj))} bytes)")


def main():
    DATA_DIR.mkdir(exist_ok=True)

    league = get(f"{BASE}/league/{LEAGUE_ID}")
    save("league.json", league)

    users = get(f"{BASE}/league/{LEAGUE_ID}/users")
    save("users.json", users)

    rosters = get(f"{BASE}/league/{LEAGUE_ID}/rosters")
    save("rosters.json", rosters)

    traded_picks = get(f"{BASE}/league/{LEAGUE_ID}/traded_picks")
    save("traded_picks.json", traded_picks)

    draft_id = league["draft_id"]
    draft = get(f"{BASE}/draft/{draft_id}")
    save("draft.json", draft)
    draft_picks = get(f"{BASE}/draft/{draft_id}/picks")
    save("draft_picks.json", draft_picks)

    # recent history for trend context only
    history = []
    prev_id = league.get("previous_league_id")
    for _ in range(PRIOR_SEASONS):
        if not prev_id:
            break
        prev_league = get(f"{BASE}/league/{prev_id}")
        prev_rosters = get(f"{BASE}/league/{prev_id}/rosters")
        prev_users = get(f"{BASE}/league/{prev_id}/users")
        history.append(
            {
                "season": prev_league.get("season"),
                "league": prev_league,
                "rosters": prev_rosters,
                "users": prev_users,
            }
        )
        prev_id = prev_league.get("previous_league_id")
    save("history.json", history)

    # full player dump is ~10MB; filter down to only rostered players
    print("fetching full player dump...")
    all_players = get(f"{BASE}/players/nfl")
    rostered_ids = set()
    for r in rosters:
        rostered_ids.update(r.get("players") or [])
    for h in history:
        for r in h["rosters"]:
            rostered_ids.update(r.get("players") or [])

    filtered_players = {pid: all_players[pid] for pid in rostered_ids if pid in all_players}
    save("players.json", filtered_players)

    print(f"done. {len(filtered_players)} players cached out of {len(all_players)} total.")


if __name__ == "__main__":
    main()
