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


def main():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    for season, league_id in SEASON_LEAGUE_IDS.items():
        print(f"fetching {season}...")
        data = fetch_season(season, league_id)
        out_path = HISTORY_DIR / f"{season}.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"  wrote {out_path} ({len(data['matchups_by_week'])} weeks)")


if __name__ == "__main__":
    main()
