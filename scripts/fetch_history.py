#!/usr/bin/env python3
"""Pull full historical league data (2019-2025) from Sleeper.

See CLAUDE.md for the league-specific quirks this accounts for:
the phantom "Any Boul FFC" bye team, the removed "Allah's Army" team,
and the 2022 schedule mess (playoff bracket is overridden separately
in compute_history.py, not here).
"""
import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
BASE = "https://api.sleeper.app/v1"

SEASON_LEAGUE_IDS = {
    2019: "394148223893188608",
    2020: "515624360016109568",
    2021: "650040105834221568",
    2022: "787506053142216704",
    2023: "915838243437330432",
    2024: "1048295810074656768",
    2025: "1182746000653811712",
    2026: "1312135999710572544",
}

PHANTOM_OWNER_ID = "480904402215890944"  # Any Boul FFC, bye-week placeholder


def get(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def fetch_season(season, league_id):
    league = get(f"{BASE}/league/{league_id}")
    users = get(f"{BASE}/league/{league_id}/users")
    rosters = get(f"{BASE}/league/{league_id}/rosters")

    num_weeks = league["settings"].get("playoff_week_start", 15) + 4
    matchups_by_week = {}
    for week in range(1, num_weeks):
        m = get(f"{BASE}/league/{league_id}/matchups/{week}")
        if not m:
            break
        matchups_by_week[week] = m

    try:
        winners_bracket = get(f"{BASE}/league/{league_id}/winners_bracket")
    except Exception:
        winners_bracket = []

    transactions_by_week = {}
    for week in range(1, num_weeks):
        t = get(f"{BASE}/league/{league_id}/transactions/{week}")
        if t:
            transactions_by_week[week] = t

    traded_picks = get(f"{BASE}/league/{league_id}/traded_picks")
    draft_picks = get(f"{BASE}/draft/{league['draft_id']}/picks")

    return {
        "season": season,
        "league_id": league_id,
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups_by_week": matchups_by_week,
        "winners_bracket": winners_bracket,
        "transactions_by_week": transactions_by_week,
        "traded_picks": traded_picks,
        "draft_picks": draft_picks,
    }


def expand_player_cache():
    """The players.json cache (built by fetch_data.py) only covers currently
    rostered players. Trades going back to 2019 reference players who have
    since retired or been dropped, so widen the cache to every player_id that
    ever appears in a trade's adds/drops across all fetched history."""
    players_path = DATA_DIR / "players.json"
    known = json.loads(players_path.read_text()) if players_path.exists() else {}
    traded_ids = set(known.keys())
    for season in SEASON_LEAGUE_IDS:
        path = HISTORY_DIR / f"{season}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for txs in data.get("transactions_by_week", {}).values():
            for t in txs:
                if t.get("type") != "trade":
                    continue
                for side in (t.get("adds"), t.get("drops")):
                    if side:
                        traded_ids.update(side.keys())

    missing = traded_ids - known.keys()
    if not missing:
        return
    print(f"fetching {len(missing)} additional players seen in historical trades...")
    all_players = get(f"{BASE}/players/nfl")
    for pid in missing:
        if pid in all_players:
            known[pid] = all_players[pid]
    players_path.write_text(json.dumps(known, indent=2))
    print(f"  players.json now has {len(known)} players")


def main():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    for season, league_id in SEASON_LEAGUE_IDS.items():
        print(f"fetching {season}...")
        data = fetch_season(season, league_id)
        out_path = HISTORY_DIR / f"{season}.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"  wrote {out_path} ({len(data['matchups_by_week'])} weeks)")

    expand_player_cache()


if __name__ == "__main__":
    main()
