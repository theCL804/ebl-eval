#!/usr/bin/env python3
"""Pull point-in-time dynasty trade values from DynastyProcess (open-data,
github.com/dynastyprocess/data) for every trade in data/trades.json.

DynastyProcess doesn't publish a dated archive, but its git commit history
for files/values-players.csv is effectively one: every commit is a snapshot
of that day's crowdsourced-plus-ECR-derived dynasty values. For each trade we
pull two snapshots: the commit closest to the trade date ("at trade"), and
the commit closest to one year after the trade date ("one year later"). See
CLAUDE.md for why KTC (the other common source) isn't used here: its Terms &
Conditions explicitly prohibit scraping and redistributing its data, while
DynastyProcess is an open-data repo meant to be consumed this way.

Deliberately NOT "value today" for every trade -- that would grade a 2019
trade against 2026 values, where both sides have often decayed to near zero
just from age/retirement regardless of whether the trade itself was any
good. Instead each trade's "how did it age" value is the average of its
value at 1, 2, and 3 years after the trade date (whichever of those have
actually elapsed so far -- a trade from last year only has a 1-year
checkpoint yet). Averaging over a few checkpoints smooths out noise from
whatever a single snapshot happened to catch (a bye week, an injury, a
hot streak) and grades every trade on the same relative clock instead of
penalizing older trades for the mere passage of time.

Only pulls values for players/picks actually referenced in data/trades.json,
not full snapshots, to keep the output small.
"""
import csv
import io
import json
import urllib.request
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_BASE = "https://raw.githubusercontent.com/dynastyprocess/data"
API_BASE = "https://api.github.com/repos/dynastyprocess/data"
VALUES_PATH = "files/values-players.csv"
UA = {"User-Agent": "ebl-eval (github.com/theCL804/ebl-eval)"}

ROUND_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def fetch_bytes(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def fetch_csv(url):
    text = fetch_bytes(url).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def fetch_commit_history():
    """Every commit that touched values-players.csv, oldest first. This repo
    updates values-players.csv and values-picks.csv together, so any commit's
    tree has both files in the state they were in on that date, even if a
    given commit only touched one of them.
    """
    commits = []
    page = 1
    while True:
        url = f"{API_BASE}/commits?path={VALUES_PATH}&per_page=100&page={page}"
        req = urllib.request.Request(url, headers=UA)
        batch = json.loads(urllib.request.urlopen(req).read())
        if not batch:
            break
        commits.extend({"sha": c["sha"], "date": c["commit"]["author"]["date"]} for c in batch)
        page += 1
    commits.sort(key=lambda c: c["date"])
    return commits


def nearest_commit(commits, target_iso_date):
    dates = [c["date"] for c in commits]
    i = bisect_left(dates, target_iso_date)
    candidates = [c for c in (commits[i - 1] if i > 0 else None, commits[i] if i < len(commits) else None) if c]
    target = datetime.fromisoformat(target_iso_date.replace("Z", "+00:00"))
    return min(candidates, key=lambda c: abs(datetime.fromisoformat(c["date"].replace("Z", "+00:00")) - target))


def load_crosswalk(sleeper_ids_needed):
    rows = fetch_csv(f"{RAW_BASE}/master/files/db_playerids.csv")
    crosswalk = {}
    for r in rows:
        if r["sleeper_id"] in sleeper_ids_needed and r["fantasypros_id"]:
            crosswalk[r["sleeper_id"]] = r["fantasypros_id"]
    return crosswalk


def pick_ecr_at_slot_avg(picks_rows, season, round_num):
    """Round-average dynasty ECR for a given season/round, from whichever row
    shape that snapshot happens to have for that season (exact draft slots
    for the current/imminent draft year, Early/Mid/Late tiers or a plain
    round-average row for further-out future years).
    """
    ordinal = ROUND_ORDINAL[round_num]
    exact = [r for r in picks_rows if r["player"] == f"{season} {ordinal}"]
    if exact:
        return float(exact[0]["ecr_1qb"])

    slots = [r for r in picks_rows if r["player"].startswith(f"{season} Pick {round_num}.")]
    if slots:
        return sum(float(r["ecr_1qb"]) for r in slots) / len(slots)

    tiers = [r for r in picks_rows if r["player"] in (f"{season} Early {ordinal}", f"{season} Mid {ordinal}", f"{season} Late {ordinal}")]
    if tiers:
        return sum(float(r["ecr_1qb"]) for r in tiers) / len(tiers)
    return None


def ecr_to_value(player_rows, ecr):
    """Convert a dynasty ECR (rank) to the value_1qb scale, by finding the
    player in this same snapshot with the closest ecr_1qb and using their
    value. Picks don't get their own value_1qb in DynastyProcess's data, only
    an ECR, so this is the bridge that puts pick values on the same scale as
    player values for trade totals.
    """
    if ecr is None:
        return None
    best = min(player_rows, key=lambda r: abs(float(r["ecr_1qb"]) - ecr) if r.get("ecr_1qb") else float("inf"))
    v = best.get("value_1qb")
    return float(v) if v not in (None, "", "NA") else None


def snapshot_values(sha, fp_ids_needed, pick_keys_needed):
    player_rows = fetch_csv(f"{RAW_BASE}/{sha}/files/values-players.csv")

    # DynastyProcess didn't publish a dollar-scale value_1qb (or an fp_id to
    # join on) before ~May 2020 -- only ECR-style rank columns under a
    # different schema entirely (mergename/dynoECR). No target value scale
    # exists in that era to convert anything onto, so snapshots from before
    # the schema change are unavailable rather than approximated.
    if not player_rows or "fp_id" not in player_rows[0]:
        return {}, {}, False

    picks_rows = fetch_csv(f"{RAW_BASE}/{sha}/files/values-picks.csv")

    player_values = {}
    for r in player_rows:
        if r["fp_id"] in fp_ids_needed:
            v = r.get("value_1qb")
            if v not in (None, "", "NA"):
                player_values[r["fp_id"]] = float(v)

    pick_values = {}
    for season, round_num in pick_keys_needed:
        ecr = pick_ecr_at_slot_avg(picks_rows, season, round_num)
        val = ecr_to_value(player_rows, ecr)
        if val is not None:
            pick_values[f"{season}-{round_num}"] = round(val, 1)

    return player_values, pick_values, True


def main():
    trades = json.loads((DATA_DIR / "trades.json").read_text())["trades"]

    sleeper_ids_needed = set()
    pick_keys_needed = set()
    for t in trades:
        for side in t["sides"].values():
            for p in side["players"]:
                sleeper_ids_needed.add(p["player_id"])
            for pk in side["picks"]:
                pick_keys_needed.add((pk["season"], pk["round"]))

    print(f"{len(trades)} trades, {len(sleeper_ids_needed)} unique players, {len(pick_keys_needed)} unique pick season/rounds")

    print("fetching commit history...")
    commits = fetch_commit_history()
    print(f"  {len(commits)} commits, {commits[0]['date'][:10]} to {commits[-1]['date'][:10]}")

    print("fetching player id crosswalk...")
    crosswalk = load_crosswalk(sleeper_ids_needed)
    fp_ids_needed = set(crosswalk.values())
    print(f"  matched {len(crosswalk)}/{len(sleeper_ids_needed)} players to DynastyProcess ids")

    latest_sha = commits[-1]["sha"]
    latest_date = datetime.fromisoformat(commits[-1]["date"].replace("Z", "+00:00"))

    def years_later(dt, n):
        try:
            return dt.replace(year=dt.year + n)
        except ValueError:  # Feb 29 on a target year that has no Feb 29
            return dt + timedelta(days=365 * n)

    trade_snapshot = {}
    needed_shas = {latest_sha}
    for t in trades:
        trade_dt = datetime.fromtimestamp(t["created"] / 1000, tz=timezone.utc)
        trade_date = trade_dt.isoformat().replace("+00:00", "Z")
        at_trade_sha = nearest_commit(commits, trade_date)["sha"]

        horizon_shas = []
        for n in (1, 2, 3):
            horizon_dt = years_later(trade_dt, n)
            if horizon_dt <= latest_date:
                horizon_date = horizon_dt.isoformat().replace("+00:00", "Z")
                horizon_shas.append(nearest_commit(commits, horizon_date)["sha"])

        trade_snapshot[t["transaction_id"]] = {"at_trade": at_trade_sha, "horizon_shas": horizon_shas}
        needed_shas.add(at_trade_sha)
        needed_shas.update(horizon_shas)
    print(f"fetching {len(needed_shas)} value snapshots...")

    snapshots = {}
    for i, sha in enumerate(sorted(needed_shas), 1):
        commit_date = next(c["date"] for c in commits if c["sha"] == sha)
        player_values, pick_values, available = snapshot_values(sha, fp_ids_needed, pick_keys_needed)
        snapshots[sha] = {
            "date": commit_date,
            "available": available,
            "player_values": player_values,
            "pick_values": pick_values,
        }
        note = f"{len(player_values)} players, {len(pick_values)} picks" if available else "no value data in this era's schema"
        print(f"  [{i}/{len(needed_shas)}] {sha[:8]} ({commit_date[:10]}): {note}")

    out = {
        "crosswalk": crosswalk,
        "snapshots": snapshots,
        "trade_snapshot": trade_snapshot,
        "latest_sha": latest_sha,
    }
    (DATA_DIR / "dynasty_values.json").write_text(json.dumps(out, indent=2))
    print(f"wrote dynasty_values.json ({len(snapshots)} snapshots)")


if __name__ == "__main__":
    main()
