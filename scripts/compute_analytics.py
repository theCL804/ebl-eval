#!/usr/bin/env python3
"""Compute points/luck, positional scoring, and transaction analytics from data/history/*.json.

See CLAUDE.md for the phantom-team exclusion rule applied here. Note that
the week-14 "vs. league median" weeks (2023-2025) are deliberately NOT
excluded here, unlike in compute_history.py's head-to-head matrix: the raw
matchup data still pairs each team against some roster that week, and
whatever the actual win/loss result was for that pairing matches the
official record (Sleeper's own win/loss determination for a median week
already resolves to a real win or loss in `settings.wins/losses`), so it's
correct to count it as a real result here. It's only excluded from
head-to-head because the specific *opponent* listed for that week is
fabricated, not because the result itself is fake.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"

PHANTOM_OWNER_ID = "480904402215890944"
SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
POSITIONS = ["QB", "RB", "WR", "TE"]


def load(path):
    return json.loads(path.read_text())


def real_matchup_weeks(matchups_by_week, playoff_week_start):
    """Yield (week, [(roster_id, points), ...]) for weeks that were part of
    the regular season (excludes playoffs/consolation bracket weeks, which
    Sleeper still returns matchups for but which don't count toward the
    official win/loss record)."""
    for week_str, matchups in matchups_by_week.items():
        week = int(week_str)
        if week >= playoff_week_start:
            continue
        by_matchup_id = {}
        for m in matchups:
            if m.get("matchup_id") is None:
                continue
            by_matchup_id.setdefault(m["matchup_id"], []).append(m)
        for pair in by_matchup_id.values():
            if len(pair) != 2:
                continue
            yield week, pair


def compute_luck(all_season_data, owner_to_name, current_owner_ids):
    per_season = {}
    all_time = {o: {"actual_wins": 0.0, "expected_wins": 0.0, "games": 0} for o in current_owner_ids}

    for season, data in all_season_data.items():
        roster_owner = {r["roster_id"]: r["owner_id"] for r in data["rosters"]}
        season_stats = {}

        # build the week's full score pool once per week for all-play calc
        week_pools = {}
        for week, pair in real_matchup_weeks(data["matchups_by_week"], data["league"]["settings"]["playoff_week_start"]):
            for m in pair:
                owner = roster_owner.get(m["roster_id"])
                if not owner or owner == PHANTOM_OWNER_ID:
                    continue
                week_pools.setdefault(week, {})[owner] = m.get("points", 0) or 0

        for week, pool in week_pools.items():
            for owner, pts in pool.items():
                others = [p for o, p in pool.items() if o != owner]
                if not others:
                    continue
                all_play_wins = sum(1 for p in others if pts > p)
                all_play_ties = sum(1 for p in others if pts == p)
                expected = (all_play_wins + 0.5 * all_play_ties) / len(others)
                s = season_stats.setdefault(owner, {"actual_wins": 0.0, "expected_wins": 0.0, "games": 0})
                s["expected_wins"] += expected
                s["games"] += 1

        for week, pair in real_matchup_weeks(data["matchups_by_week"], data["league"]["settings"]["playoff_week_start"]):
            m1, m2 = pair
            o1, o2 = roster_owner.get(m1["roster_id"]), roster_owner.get(m2["roster_id"])
            if not o1 or not o2:
                continue
            # a real team's game against the phantom bye team still counts
            # as a real result in the official record (they still "won" that
            # week); only the phantom side itself has no wins to credit
            p1, p2 = m1.get("points", 0) or 0, m2.get("points", 0) or 0
            if o1 in season_stats and o1 != PHANTOM_OWNER_ID:
                season_stats[o1]["actual_wins"] += 1 if p1 > p2 else (0.5 if p1 == p2 else 0)
            if o2 in season_stats and o2 != PHANTOM_OWNER_ID:
                season_stats[o2]["actual_wins"] += 1 if p2 > p1 else (0.5 if p1 == p2 else 0)

        season_result = {}
        for owner, s in season_stats.items():
            luck = round(s["actual_wins"] - s["expected_wins"], 2)
            season_result[owner] = {
                "team_name": owner_to_name.get(owner, "(departed team)"),
                "actual_wins": s["actual_wins"],
                "expected_wins": round(s["expected_wins"], 2),
                "luck": luck,
                "games": s["games"],
            }
            if owner in all_time:
                all_time[owner]["actual_wins"] += s["actual_wins"]
                all_time[owner]["expected_wins"] += s["expected_wins"]
                all_time[owner]["games"] += s["games"]
        per_season[season] = season_result

    all_time_result = {}
    for owner, s in all_time.items():
        all_time_result[owner] = {
            "team_name": owner_to_name.get(owner),
            "actual_wins": round(s["actual_wins"], 1),
            "expected_wins": round(s["expected_wins"], 2),
            "luck": round(s["actual_wins"] - s["expected_wins"], 2),
            "games": s["games"],
        }

    return per_season, all_time_result


def compute_positional(all_season_data, owner_to_name, current_owner_ids, players):
    def position_of(player_id):
        p = players.get(player_id)
        if not p:
            return None
        pos = p.get("position")
        return pos if pos in POSITIONS else None

    per_season = {}
    all_time = {o: {pos: 0.0 for pos in POSITIONS} for o in current_owner_ids}
    league_by_season = {}

    for season, data in all_season_data.items():
        roster_owner = {r["roster_id"]: r["owner_id"] for r in data["rosters"]}
        season_totals = {}
        league_totals = {pos: 0.0 for pos in POSITIONS}
        playoff_week_start = data["league"]["settings"]["playoff_week_start"]

        for week_str, matchups in data["matchups_by_week"].items():
            if int(week_str) >= playoff_week_start:
                continue
            for m in matchups:
                owner = roster_owner.get(m["roster_id"])
                if not owner or owner == PHANTOM_OWNER_ID:
                    continue
                starters = m.get("starters") or []
                starters_points = m.get("starters_points") or []
                team_totals = season_totals.setdefault(owner, {pos: 0.0 for pos in POSITIONS})
                for pid, pts in zip(starters, starters_points):
                    pos = position_of(pid)
                    if pos:
                        team_totals[pos] += pts
                        league_totals[pos] += pts

        per_season[season] = {
            owner: {"team_name": owner_to_name.get(owner, "(departed team)"), **{pos: round(v, 1) for pos, v in totals.items()}}
            for owner, totals in season_totals.items()
        }
        league_by_season[season] = {pos: round(v, 1) for pos, v in league_totals.items()}

        for owner, totals in season_totals.items():
            if owner in all_time:
                for pos in POSITIONS:
                    all_time[owner][pos] += totals[pos]

    all_time_result = {
        owner: {"team_name": owner_to_name.get(owner), **{pos: round(v, 1) for pos, v in totals.items()}}
        for owner, totals in all_time.items()
    }

    return per_season, all_time_result, league_by_season


def compute_transactions(all_season_data, owner_to_name, current_owner_ids):
    per_season = {}
    all_time = {o: {"trade": 0, "waiver": 0, "free_agent": 0, "total": 0} for o in current_owner_ids}
    trade_partners = {}  # frozenset({a,b}) -> count

    for season, data in all_season_data.items():
        roster_owner = {r["roster_id"]: r["owner_id"] for r in data["rosters"]}
        season_totals = {}

        for week_str, txs in data.get("transactions_by_week", {}).items():
            for t in txs:
                if t.get("status") != "complete":
                    continue
                ttype = t.get("type")
                if ttype not in ("trade", "waiver", "free_agent"):
                    continue
                roster_ids = t.get("roster_ids") or []
                owners = {roster_owner.get(rid) for rid in roster_ids}
                owners.discard(None)
                owners.discard(PHANTOM_OWNER_ID)
                for owner in owners:
                    s = season_totals.setdefault(owner, {"trade": 0, "waiver": 0, "free_agent": 0, "total": 0})
                    s[ttype] += 1
                    s["total"] += 1
                    if owner in all_time:
                        all_time[owner][ttype] += 1
                        all_time[owner]["total"] += 1
                if ttype == "trade" and len(owners) == 2:
                    a, b = sorted(owners)
                    if a in current_owner_ids and b in current_owner_ids:
                        key = f"{a}|{b}"
                        trade_partners[key] = trade_partners.get(key, 0) + 1

        per_season[season] = {
            owner: {"team_name": owner_to_name.get(owner, "(departed team)"), **totals}
            for owner, totals in season_totals.items()
        }

    partner_list = [
        {"a": k.split("|")[0], "b": k.split("|")[1], "a_name": owner_to_name.get(k.split("|")[0]), "b_name": owner_to_name.get(k.split("|")[1]), "trades": v}
        for k, v in trade_partners.items()
    ]
    partner_list.sort(key=lambda x: -x["trades"])

    all_time_result = {owner: {"team_name": owner_to_name.get(owner), **totals} for owner, totals in all_time.items()}

    return per_season, all_time_result, partner_list


def main():
    teams = load(DATA_DIR / "teams.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    current_owner_ids = set(owner_to_name.keys())
    players = load(DATA_DIR / "players.json")

    all_season_data = {}
    for season in SEASONS:
        path = HISTORY_DIR / f"{season}.json"
        if path.exists():
            all_season_data[season] = load(path)

    luck_by_season, luck_all_time = compute_luck(all_season_data, owner_to_name, current_owner_ids)
    positional_by_season, positional_all_time, league_positional_by_season = compute_positional(
        all_season_data, owner_to_name, current_owner_ids, players
    )
    tx_by_season, tx_all_time, trade_partners = compute_transactions(all_season_data, owner_to_name, current_owner_ids)

    analytics = {
        "luck": {"by_season": luck_by_season, "all_time": luck_all_time},
        "positional": {
            "by_season": positional_by_season,
            "all_time": positional_all_time,
            "league_by_season": league_positional_by_season,
        },
        "transactions": {"by_season": tx_by_season, "all_time": tx_all_time, "trade_partners": trade_partners},
    }
    (DATA_DIR / "analytics.json").write_text(json.dumps(analytics, indent=2))
    print("wrote data/analytics.json")


if __name__ == "__main__":
    main()
