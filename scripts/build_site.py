#!/usr/bin/env python3
"""Generate the static GitHub Pages site into docs/ from data/teams.json + data/content.json."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

VERDICT_CLASS = {
    "Win-Now Contender": "verdict-winnow",
    "Contender": "verdict-contender",
    "Retool": "verdict-retool",
    "Rebuild": "verdict-rebuild",
}


def load(name):
    return json.loads((DATA_DIR / name).read_text())


def compute_rings(championships):
    rings = {}
    runner_ups = {}
    for c in championships:
        rings[c["winner"]] = rings.get(c["winner"], 0) + 1
        runner_ups[c["runner_up"]] = runner_ups.get(c["runner_up"], 0) + 1
    return rings, runner_ups


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return s.strip("-")


def esc(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


NAV_ITEMS = [
    ("index.html", "Power Rankings"),
    ("history.html", "League History"),
    ("head-to-head.html", "Head-to-Head"),
    ("analytics.html", "Analytics"),
    ("draft-flow.html", "Draft Capital Flow"),
    ("trades.html", "Trades Hub"),
]

POSITION_COLORS = {"QB": "#7c93f0", "RB": "#3fb97d", "WR": "#d9a635", "TE": "#e0664a"}


def nav_html(active):
    links = []
    for href, label in NAV_ITEMS:
        cls = "nav-link active" if href == active else "nav-link"
        links.append(f'<a class="{cls}" href="{href}">{esc(label)}</a>')
    return f'<nav class="site-nav"><span class="nav-brand">Ethel\'s Dynasty</span><div class="nav-links">{"".join(links)}</div></nav>'


def page_shell(title, body, description="", active=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="stylesheet" href="style.css">
</head>
<body>
{nav_html(active)}
<div class="page">
{body}
</div>
</body>
</html>
"""


def draft_picks_summary(picks):
    by_season = {}
    for p in picks:
        by_season.setdefault(p["season"], []).append(p["round"])
    parts = []
    for season in sorted(by_season):
        rounds = sorted(by_season[season])
        rounds_list = ", ".join(f"Rd {r}" for r in rounds)
        parts.append(f'<div class="picks-season"><span class="picks-year">{season}</span><span class="picks-list">{rounds_list} <span class="picks-count">({len(rounds)} picks)</span></span></div>')
    return "\n".join(parts)


def player_row(p):
    inj = f'<span class="tag tag-injury">{esc(p["injury_status"])}</span>' if p.get("injury_status") else ""
    age = p["age"] if p["age"] is not None else "-"
    nfl_team = p["team"] or "FA"
    return f"""<tr>
<td class="pos"><span class="tag tag-pos-{esc((p['position'] or '').lower())}">{esc(p['position'])}</span></td>
<td class="name">{esc(p['name'])}</td>
<td class="nfl-team">{esc(nfl_team)}</td>
<td class="age">{age}</td>
<td class="exp">{p.get('years_exp', '-')}</td>
<td class="inj">{inj}</td>
</tr>"""


def build_team_page(team, content, rings, runner_ups):
    verdict = content["verdict"]
    vclass = VERDICT_CLASS.get(verdict, "")
    ring_count = rings.get(team["roster_id"], 0)
    runner_up_count = runner_ups.get(team["roster_id"], 0)
    trophies = "🏆" * ring_count
    trophy_line = ""
    if ring_count or runner_up_count:
        bits = []
        if ring_count:
            bits.append(f"{ring_count}x champion")
        if runner_up_count:
            bits.append(f"{runner_up_count}x runner-up")
        trophy_line = f'<p class="trophy-line">{trophies} {esc(" · ".join(bits))}</p>'
    starters = [p for p in team["roster"] if p["is_starter"]]
    bench = [p for p in team["roster"] if not p["is_starter"]]

    history_items = "".join(
        f'<div class="history-item"><span class="history-season">{h["season"]}</span><span class="history-record">{h["wins"]}-{h["losses"]}{"-" + str(h["ties"]) if h["ties"] else ""}</span><span class="history-pts">{h["fpts"]:.1f} pts</span></div>'
        for h in team["recent_history"]
    )

    strengths = "".join(f"<li>{esc(s)}</li>" for s in content["strengths"])
    weaknesses = "".join(f"<li>{esc(w)}</li>" for w in content["weaknesses"])
    standing_paras = "".join(f"<p>{esc(p)}</p>" for p in content.get("standing", []))
    outlook_paras = "".join(f"<p>{esc(p)}</p>" for p in content.get("future_outlook", []))

    pos_counts = team["position_counts"]
    pos_ages = team["position_avg_age"]
    comp_rows = "".join(
        f'<div class="comp-row"><span class="comp-pos">{pos}</span><span class="comp-count">{pos_counts.get(pos,0)} rostered</span><span class="comp-age">avg age {pos_ages.get(pos) or "-"}</span></div>'
        for pos in ["QB", "RB", "WR", "TE"]
    )

    body = f"""
<a class="back-link" href="index.html">&larr; All Teams</a>
<header class="team-header">
  <div class="verdict-badge {vclass}">{esc(verdict)}</div>
  <h1>{esc(team['team_name'])} {trophies}</h1>
  <p class="owner">Managed by {esc(team['display_name'])}</p>
  {trophy_line}
  <p class="tagline">{esc(content['tagline'])}</p>
</header>

<section class="snapshot-grid">
  <div class="snapshot-card">
    <h3>Roster Age</h3>
    <p class="big-stat">{team['avg_age']}</p>
    <p class="stat-label">average age, full roster</p>
  </div>
  <div class="snapshot-card">
    <h3>Recent Record</h3>
    {history_items or '<p class="stat-label">No prior seasons on record</p>'}
  </div>
  <div class="snapshot-card">
    <h3>Position Composition</h3>
    {comp_rows}
  </div>
</section>

<section class="standing-section">
  <h2>Where They Stand</h2>
  <div class="standing">{standing_paras}</div>
</section>

<section class="outlook-section">
  <h2>Future Outlook</h2>
  <div class="outlook">{outlook_paras}</div>
</section>

<section class="narrative-section">
  <h2>Scouting Report</h2>
  <p class="narrative">{esc(content['narrative'])}</p>
  <div class="sw-grid">
    <div class="strengths">
      <h3>Strengths</h3>
      <ul>{strengths}</ul>
    </div>
    <div class="weaknesses">
      <h3>Weaknesses</h3>
      <ul>{weaknesses}</ul>
    </div>
  </div>
</section>

<section class="picks-section">
  <h2>Draft Capital</h2>
  <div class="picks-grid">
    {draft_picks_summary(team['draft_picks'])}
  </div>
</section>

<section class="roster-section">
  <h2>Starters</h2>
  <table class="roster-table">
    <thead><tr><th>Pos</th><th>Player</th><th>Team</th><th>Age</th><th>Exp</th><th></th></tr></thead>
    <tbody>
    {"".join(player_row(p) for p in starters)}
    </tbody>
  </table>

  <h2>Bench</h2>
  <table class="roster-table">
    <thead><tr><th>Pos</th><th>Player</th><th>Team</th><th>Age</th><th>Exp</th><th></th></tr></thead>
    <tbody>
    {"".join(player_row(p) for p in bench)}
    </tbody>
  </table>
</section>
"""
    return page_shell(
        f"{team['team_name']} — Ethel's Dynasty 2026 Draft Preview",
        body,
        description=content["tagline"],
        active="",
    )


def build_index(teams, content_all, league_content, rings, runner_ups):
    verdict_order = ["Win-Now Contender", "Contender", "Retool", "Rebuild"]
    teams_by_verdict = {v: [] for v in verdict_order}
    for t in teams:
        c = content_all[str(t["roster_id"])]
        teams_by_verdict[c["verdict"]].append((t, c))

    sections = []
    for verdict in verdict_order:
        group = teams_by_verdict[verdict]
        if not group:
            continue
        vclass = VERDICT_CLASS.get(verdict, "")
        cards = []
        for t, c in group:
            slug = f"team-{t['roster_id']}.html"
            record = t["recent_history"][-1] if t["recent_history"] else None
            record_str = f"{record['wins']}-{record['losses']} in {record['season']}" if record else "No history"
            trophies = "🏆" * rings.get(t["roster_id"], 0)
            cards.append(f"""
<a class="team-card" href="{slug}">
  <div class="team-card-top">
    <span class="verdict-badge small {vclass}">{esc(verdict)}</span>
  </div>
  <h3>{esc(t['team_name'])} {trophies}</h3>
  <p class="card-owner">{esc(t['display_name'])}</p>
  <p class="card-tagline">{esc(c['tagline'])}</p>
  <div class="card-stats">
    <span>{record_str}</span>
    <span>avg age {t['avg_age']}</span>
  </div>
</a>""")
        sections.append(f"""
<section class="verdict-section">
  <h2 class="verdict-heading {vclass}">{esc(verdict)}</h2>
  <div class="team-grid">
    {"".join(cards)}
  </div>
</section>""")

    body = f"""
<header class="league-header">
  <h1>{esc(league_content['league_headline'])}</h1>
  <p class="league-summary">{esc(league_content['league_summary'])}</p>
  <p class="header-links"><a href="history.html">See full League History &rarr;</a> &nbsp;&middot;&nbsp; <a href="head-to-head.html">Head-to-Head records &rarr;</a></p>
</header>
{"".join(sections)}
<footer class="site-footer">
  <p>Built from live Sleeper league data. Analysis and grades are opinion, not projections.</p>
</footer>
"""
    return page_shell(
        league_content["league_headline"],
        body,
        active="index.html",
        description=league_content["league_summary"],
    )


def build_history_page(season_summaries, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(name, owner_id):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name) if name else "&mdash;"

    cards = []
    for s in sorted(season_summaries, key=lambda s: -s["season"]):
        if s["season"] == 2018:
            cards.append(f"""
<div class="season-card">
  <h3>2018 <span class="season-note">(pre-Sleeper)</span></h3>
  <p class="season-champ">🏆 {team_link(s['champion'], s['champion_owner_id'])} beat {team_link(s['runner_up'], s['runner_up_owner_id'])}</p>
  <p class="season-note">{esc(s.get('note', ''))}</p>
</div>""")
            continue

        def playoff_badge(place):
            if place == 1:
                return '<span class="badge-finish badge-1">🏆 Champion</span>'
            if place == 2:
                return '<span class="badge-finish badge-2">🥈 Runner-up</span>'
            if place == 3:
                return '<span class="badge-finish badge-3">🥉 3rd</span>'
            if place:
                return f'<span class="badge-finish">{place}th</span>'
            return '<span class="badge-finish badge-none">&mdash;</span>'

        rows = "".join(
            f"""<tr>
<td class="rank">{i}</td>
<td>{team_link(st['team_name'], st['owner_id'])}</td>
<td>{st['wins']}-{st['losses']}{'-' + str(st['ties']) if st['ties'] else ''}</td>
<td>{st['points_for']:.1f}</td>
<td>{st['points_against']:.1f}</td>
<td>{playoff_badge(st['place'])}</td>
</tr>"""
            for i, st in enumerate(s["standings"], start=1)
        )
        cards.append(f"""
<div class="season-card">
  <h3>{s['season']}</h3>
  <p class="season-champ">🏆 {team_link(s['champion'], s['champion_owner_id'])} beat {team_link(s['runner_up'], s['runner_up_owner_id'])}{f" (3rd: {team_link(s['third'], None)})" if s.get('third') else ''}</p>
  <table class="roster-table season-standings">
    <thead><tr><th>#</th><th>Team</th><th>Regular Season</th><th>PF</th><th>PA</th><th>Playoff Finish</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>""")

    body = f"""
<header class="league-header">
  <h1>League History</h1>
  <p class="league-summary">Every season since the league's founding in 2018. 2019 onward is sourced live from Sleeper; 2018 predates the platform and is recorded from league history. See the 2022 note below for a schedule quirk that year.</p>
</header>
<section class="history-list">
  {"".join(cards)}
</section>
<footer class="site-footer">
  <p>2022 note: a schedule mixup pushed the playoffs back a week and results were tracked manually that year; the numbers above have since been corrected to match.</p>
</footer>
"""
    return page_shell("League History — Ethel's Dynasty", body, description="Season-by-season standings and champions since 2018.", active="history.html")


def build_head_to_head_page(matrix, teams):
    teams_sorted = sorted(teams, key=lambda t: t["team_name"])
    owner_ids = [t["owner_id"] for t in teams_sorted]
    name_by_owner = {t["owner_id"]: t["team_name"] for t in teams_sorted}

    header_cells = "".join(f'<th class="h2h-col-label"><span>{esc(name_by_owner[o])}</span></th>' for o in owner_ids)
    rows = []
    for row_owner in owner_ids:
        cells = []
        for col_owner in owner_ids:
            if row_owner == col_owner:
                cells.append('<td class="h2h-self">&mdash;</td>')
                continue
            rec = matrix.get(row_owner, {}).get(col_owner)
            if not rec:
                cells.append('<td class="h2h-none">-</td>')
                continue
            label = f"{rec['wins']}-{rec['losses']}"
            if rec["ties"]:
                label += f"-{rec['ties']}"
            cls = "h2h-winning" if rec["wins"] > rec["losses"] else ("h2h-losing" if rec["losses"] > rec["wins"] else "")
            cells.append(f'<td class="{cls}" title="{esc(name_by_owner[row_owner])} vs {esc(name_by_owner[col_owner])}: {label}">{label}</td>')
        rows.append(f'<tr><th class="h2h-row-label">{esc(name_by_owner[row_owner])}</th>{"".join(cells)}</tr>')

    body = f"""
<header class="league-header">
  <h1>Head-to-Head Records</h1>
  <p class="league-summary">All-time regular-season and playoff record between every pair of current teams, aggregated across every season 2019-2025 (2022-2025 week 14 "vs. league median" games excluded, since those weren't real matchups). Read each row as that team's record against the column opponent.</p>
</header>
<section class="h2h-section">
  <div class="h2h-scroll">
    <table class="h2h-table">
      <thead><tr><th></th>{header_cells}</tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</section>
<footer class="site-footer">
  <p>Only games between two teams still active in 2026 are counted. Matchups against departed franchises (Allah's Army, Los Diablos, and others) aren't shown here.</p>
</footer>
"""
    return page_shell("Head-to-Head — Ethel's Dynasty", body, description="All-time head-to-head records between every team in the league.", active="head-to-head.html")


def build_analytics_page(analytics, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    # --- luck table ---
    luck_rows_data = sorted(analytics["luck"]["all_time"].items(), key=lambda x: -x[1]["luck"])
    luck_rows = "".join(
        f"""<tr>
<td>{team_link(o, v['team_name'])}</td>
<td>{v['actual_wins']:g}</td>
<td>{v['expected_wins']:.1f}</td>
<td class="{'luck-pos' if v['luck'] > 0 else ('luck-neg' if v['luck'] < 0 else '')}">{v['luck']:+.1f}</td>
</tr>"""
        for o, v in luck_rows_data
    )

    # --- positional mix stacked bars ---
    pos_rows = []
    for o, v in sorted(analytics["positional"]["all_time"].items(), key=lambda x: x[1]["team_name"] or ""):
        total = sum(v[p] for p in ["QB", "RB", "WR", "TE"]) or 1
        segments = "".join(
            f'<span class="pos-seg" style="width:{v[p]/total*100:.1f}%;background:{POSITION_COLORS[p]}" title="{p}: {v[p]:.0f} pts ({v[p]/total*100:.0f}%)"></span>'
            for p in ["QB", "RB", "WR", "TE"]
        )
        pos_rows.append(f"""
<div class="pos-row">
  <div class="pos-team">{team_link(o, v['team_name'])}</div>
  <div class="pos-bar">{segments}</div>
</div>""")

    pos_legend = "".join(
        f'<span class="pos-legend-item"><span class="pos-swatch" style="background:{POSITION_COLORS[p]}"></span>{p}</span>'
        for p in ["QB", "RB", "WR", "TE"]
    )

    # --- transaction activity ---
    tx_rows_data = sorted(analytics["transactions"]["all_time"].items(), key=lambda x: -x[1]["total"])
    tx_rows = "".join(
        f"""<tr>
<td>{team_link(o, v['team_name'])}</td>
<td>{v['trade']}</td>
<td>{v['waiver']}</td>
<td>{v['free_agent']}</td>
<td class="tx-total">{v['total']}</td>
</tr>"""
        for o, v in tx_rows_data
    )

    partner_rows = "".join(
        f"""<tr>
<td>{team_link(p['a'], p['a_name'])} &harr; {team_link(p['b'], p['b_name'])}</td>
<td>{p['trades']}</td>
</tr>"""
        for p in analytics["transactions"]["trade_partners"][:10]
    )

    body = f"""
<header class="league-header">
  <h1>Analytics</h1>
  <p class="league-summary">Advanced stats computed from every game played since 2019: all-play luck, positional scoring mix, and roster-management activity. Games against the phantom bye team and 2022-2025 week-14 median games are excluded, same as Head-to-Head.</p>
</header>

<section class="analytics-section">
  <h2>Luck: Record vs. All-Play Expectation</h2>
  <p class="section-note">"Expected wins" is how many games a team's weekly score would have beaten if it had played every other team that week, summed across every real matchup week since 2019. Positive luck means the team has won more than its scoring would predict; negative means the opposite &mdash; often true of high-scoring teams that still run into a big week from an opponent.</p>
  <table class="roster-table">
    <thead><tr><th>Team</th><th>Actual Wins</th><th>Expected Wins</th><th>Luck</th></tr></thead>
    <tbody>{luck_rows}</tbody>
  </table>
</section>

<section class="analytics-section">
  <h2>Career Positional Scoring Mix</h2>
  <p class="section-note">Share of each team's all-time starter points that has come from each position, since 2019.</p>
  <div class="pos-legend">{pos_legend}</div>
  <div class="pos-chart">{"".join(pos_rows)}</div>
</section>

<section class="analytics-section">
  <h2>Roster Management Activity</h2>
  <p class="section-note">All-time transaction counts by type, since 2019.</p>
  <table class="roster-table">
    <thead><tr><th>Team</th><th>Trades</th><th>Waiver Claims</th><th>Free Agent Adds</th><th>Total</th></tr></thead>
    <tbody>{tx_rows}</tbody>
  </table>
</section>

<section class="analytics-section">
  <h2>Top Trade Partners</h2>
  <p class="section-note">The pairs of teams that have traded with each other the most, all-time.</p>
  <table class="roster-table">
    <thead><tr><th>Pair</th><th>Trades</th></tr></thead>
    <tbody>{partner_rows}</tbody>
  </table>
</section>
"""
    return page_shell("Analytics — Ethel's Dynasty", body, description="All-play luck, positional scoring trends, and trade/transaction activity.", active="analytics.html")


def build_draft_flow_page(draft_flow, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    # --- net capital leaderboard ---
    nc_sorted = sorted(draft_flow["net_capital"].items(), key=lambda x: -x[1]["net"])
    max_abs = max((abs(v["net"]) for _, v in nc_sorted), default=1) or 1
    net_rows = []
    for o, v in nc_sorted:
        pct = abs(v["net"]) / max_abs * 50
        bar = (
            f'<div class="net-bar-neg" style="width:{pct if v["net"] < 0 else 0:.0f}%"></div>'
            f'<div class="net-bar-mid"></div>'
            f'<div class="net-bar-pos" style="width:{pct if v["net"] > 0 else 0:.0f}%"></div>'
        )
        net_rows.append(f"""
<div class="net-row">
  <div class="net-team">{team_link(o, v['team_name'])}</div>
  <div class="net-bar-track">{bar}</div>
  <div class="net-value {'luck-pos' if v['net']>0 else ('luck-neg' if v['net']<0 else '')}">{v['net']:+d}</div>
</div>""")

    # --- trade ledgers, grouped by season ---
    def trade_ledger(trades, seasons_desc=True):
        by_season = {}
        for t in trades:
            by_season.setdefault(t["season"], []).append(t)
        seasons = sorted(by_season.keys(), key=lambda s: -int(s) if seasons_desc else int(s))
        cards = []
        for season in seasons:
            rows = "".join(
                f"""<tr>
<td class="rd">Rd {t['round']}</td>
<td>{team_link(t['from_owner'], t['from_name'])}</td>
<td class="arrow">&rarr;</td>
<td>{team_link(t['to_owner'], t['to_name'])}</td>
</tr>"""
                for t in sorted(by_season[season], key=lambda t: t["round"])
            )
            cards.append(f"""
<div class="season-card">
  <h3>{season}</h3>
  <table class="roster-table trade-ledger">
    <tbody>{rows}</tbody>
  </table>
</div>""")
        return "".join(cards)

    body = f"""
<header class="league-header">
  <h1>Draft Capital Flow</h1>
  <p class="league-summary">Every draft pick trade in league history, 2019 through the 2028 class. "Net capital" is picks acquired minus picks given away across the team's whole history &mdash; positive means a team has consistently traded for future equity, negative means it's been spending picks to win now.</p>
</header>

<section class="analytics-section">
  <h2>All-Time Net Draft Capital</h2>
  <div class="net-chart">{"".join(net_rows)}</div>
</section>

<section class="analytics-section">
  <h2>Future Pick Trades (2026-2028)</h2>
  <div class="history-list">{trade_ledger(draft_flow["future_trades"], seasons_desc=False)}</div>
</section>

<section class="analytics-section">
  <h2>Historical Pick Trades (2019-2025)</h2>
  <div class="history-list">{trade_ledger(draft_flow["historical_trades"])}</div>
</section>
"""
    return page_shell("Draft Capital Flow — Ethel's Dynasty", body, description="Every draft pick trade in league history, and who's accumulated the most future capital.", active="draft-flow.html")


def build_trades_page(trades_data, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    def pair_anchor(a, b):
        return f"pair-{a}-{b}"

    def trade_date(t):
        if not t.get("created"):
            return f"{t['season']} season"
        dt = datetime.fromtimestamp(t["created"] / 1000, tz=timezone.utc)
        return dt.strftime("%b %-d, %Y")

    def side_items(side):
        items = []
        for p in side["players"]:
            pos = p["position"] or ""
            team = p["team"] or "FA"
            items.append(f'<li><span class="trade-pos pos-{pos}">{esc(pos)}</span> {esc(p["name"])} <span class="trade-nfl">{esc(team)}</span></li>')
        for pk in side["picks"]:
            items.append(f'<li><span class="trade-pos trade-pick">PICK</span> {esc(pk["season"])} Round {pk["round"]}</li>')
        if not items:
            return '<li class="trade-empty">(nothing)</li>'
        return "".join(items)

    def trade_card(t):
        sides_html = "".join(
            f"""<div class="trade-side">
  <h4>{team_link(o, t['team_names'][o])}</h4>
  <ul>{side_items(t['sides'][o])}</ul>
</div>"""
            for o in t["teams"]
        )
        return f"""
<div class="trade-card">
  <div class="trade-meta">{esc(trade_date(t))}</div>
  <div class="trade-sides">{sides_html}</div>
</div>"""

    # --- top trade partners leaderboard ---
    partner_rows = "".join(
        f"""<tr>
<td><a href="#{pair_anchor(p['a'], p['b'])}">{team_link(p['a'], p['a_name'])} &harr; {team_link(p['b'], p['b_name'])}</a></td>
<td>{p['count']}</td>
</tr>"""
        for p in trades_data["partners"]
    )

    # --- all trades, newest first ---
    all_trades_html = "".join(trade_card(t) for t in trades_data["trades"])

    # --- per-pair sections, sorted by most active first ---
    pair_sections = []
    for p in trades_data["partners"]:
        cards = "".join(trade_card(t) for t in p["trades"])
        pair_sections.append(f"""
<div class="pair-section" id="{pair_anchor(p['a'], p['b'])}">
  <h3>{team_link(p['a'], p['a_name'])} &harr; {team_link(p['b'], p['b_name'])} <span class="section-note">({p['count']} trade{'s' if p['count'] != 1 else ''})</span></h3>
  {cards}
</div>""")

    body = f"""
<header class="league-header">
  <h1>Trades Hub</h1>
  <p class="league-summary">Every trade in league history, 2019 through today &mdash; players and draft picks both, not just picks. Click a pair below to jump straight to every deal those two teams have made with each other.</p>
</header>

<section class="analytics-section">
  <h2>Most Active Trade Partners</h2>
  <table class="roster-table">
    <thead><tr><th>Pair</th><th>Trades</th></tr></thead>
    <tbody>{partner_rows}</tbody>
  </table>
</section>

<section class="analytics-section">
  <h2>All Trades</h2>
  <p class="section-note">Newest first, {len(trades_data['trades'])} trades total.</p>
  <div class="trade-list">{all_trades_html}</div>
</section>

<section class="analytics-section">
  <h2>By Team Pair</h2>
  {"".join(pair_sections)}
</section>
"""
    return page_shell("Trades Hub — Ethel's Dynasty", body, description="Every trade in league history, players and picks, with a breakdown of who trades with whom.", active="trades.html")


CSS = """
:root {
  --bg: #f7f7f8;
  --surface: #ffffff;
  --border: #e2e2e6;
  --text: #17171a;
  --text-muted: #63636c;
  --accent: #3454d1;
  --winnow: #c4432b;
  --contender: #1f8a55;
  --retool: #b8860b;
  --rebuild: #3454d1;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121214;
    --surface: #1b1b1f;
    --border: #2c2c32;
    --text: #eeeef0;
    --text-muted: #9a9aa2;
    --accent: #7c93f0;
    --winnow: #e0664a;
    --contender: #3fb97d;
    --retool: #d9a635;
    --rebuild: #7c93f0;
  }
}
:root[data-theme="dark"] {
  --bg: #121214; --surface: #1b1b1f; --border: #2c2c32; --text: #eeeef0;
  --text-muted: #9a9aa2; --accent: #7c93f0; --winnow: #e0664a; --contender: #3fb97d;
  --retool: #d9a635; --rebuild: #7c93f0;
}
:root[data-theme="light"] {
  --bg: #f7f7f8; --surface: #ffffff; --border: #e2e2e6; --text: #17171a;
  --text-muted: #63636c; --accent: #3454d1; --winnow: #c4432b; --contender: #1f8a55;
  --retool: #b8860b; --rebuild: #3454d1;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
.page { max-width: 920px; margin: 0 auto; padding: 32px 20px 80px; }
h1, h2, h3 { line-height: 1.2; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.site-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  max-width: 920px;
  margin: 0 auto;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.nav-brand { font-weight: 700; font-size: 1rem; }
.nav-links { display: flex; gap: 4px; flex-wrap: wrap; }
.nav-link {
  color: var(--text-muted);
  font-size: 0.88rem;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 6px;
}
.nav-link:hover { text-decoration: none; background: var(--surface); color: var(--text); }
.nav-link.active { color: var(--text); background: var(--surface); border: 1px solid var(--border); }

.header-links { font-size: 0.9rem; margin-top: 12px; }

.season-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; }
.season-card h3 { margin: 0 0 6px; }
.season-note { color: var(--text-muted); font-size: 0.85rem; font-weight: 400; }
.season-champ { margin: 0 0 10px; font-size: 0.95rem; }
.season-standings { font-size: 0.85rem; }
.season-standings .rank { color: var(--text-muted); font-weight: 700; }
.badge-finish { font-size: 0.78rem; font-weight: 600; white-space: nowrap; }
.badge-finish.badge-1 { color: var(--retool); }
.badge-finish.badge-2, .badge-finish.badge-3 { color: var(--text-muted); }
.badge-finish.badge-none { color: var(--text-muted); opacity: 0.5; }

.h2h-section { margin-top: 8px; }
.h2h-scroll { overflow-x: auto; }
.h2h-table { border-collapse: collapse; font-size: 0.78rem; white-space: nowrap; }
.h2h-table th, .h2h-table td { padding: 7px 9px; text-align: center; border: 1px solid var(--border); }
.h2h-row-label { text-align: left !important; font-weight: 600; position: sticky; left: 0; background: var(--bg); }
.h2h-col-label { vertical-align: bottom; padding: 8px 4px !important; height: 150px; }
.h2h-col-label span {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  white-space: nowrap;
  font-weight: 600;
  font-size: 0.8rem;
  display: inline-block;
}
.h2h-self { background: var(--border); }
.h2h-none { color: var(--text-muted); }
.h2h-winning { color: var(--contender); font-weight: 700; }
.h2h-losing { color: var(--winnow); font-weight: 700; }

.league-header h1 { font-size: 2rem; margin-bottom: 8px; }
.league-summary { color: var(--text-muted); max-width: 68ch; font-size: 1.05rem; }

.verdict-section { margin-top: 40px; }
.verdict-heading { font-size: 1.3rem; padding-bottom: 8px; border-bottom: 2px solid var(--border); margin-bottom: 16px; }
.verdict-heading.verdict-winnow { color: var(--winnow); }
.verdict-heading.verdict-contender { color: var(--contender); }
.verdict-heading.verdict-retool { color: var(--retool); }
.verdict-heading.verdict-rebuild { color: var(--rebuild); }

.team-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.team-card {
  display: block;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  color: var(--text);
}
.team-card:hover { border-color: var(--accent); text-decoration: none; }
.team-card h3 { margin: 8px 0 2px; font-size: 1.1rem; }
.card-owner { color: var(--text-muted); font-size: 0.85rem; margin: 0 0 8px; }
.card-tagline { font-size: 0.9rem; margin: 0 0 12px; }
.card-stats { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); border-top: 1px solid var(--border); padding-top: 8px; }

.verdict-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  color: #fff;
  background: var(--accent);
}
.verdict-badge.verdict-winnow { background: var(--winnow); }
.verdict-badge.verdict-contender { background: var(--contender); }
.verdict-badge.verdict-retool { background: var(--retool); }
.verdict-badge.verdict-rebuild { background: var(--rebuild); }
.verdict-badge.small { font-size: 0.7rem; }

.back-link { display: inline-block; margin-bottom: 16px; font-size: 0.9rem; }
.team-header { margin-bottom: 28px; }
.team-header h1 { font-size: 1.9rem; margin: 10px 0 2px; }
.owner { color: var(--text-muted); margin: 0 0 4px; }
.trophy-line { color: var(--text-muted); font-size: 0.85rem; margin: 0 0 12px; }
.tagline { font-size: 1.1rem; max-width: 60ch; }

.snapshot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }
.snapshot-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.snapshot-card h3 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin: 0 0 10px; }
.big-stat { font-size: 2rem; font-weight: 700; margin: 0; }
.stat-label { color: var(--text-muted); font-size: 0.85rem; margin: 4px 0 0; }
.history-item, .comp-row { display: flex; justify-content: space-between; font-size: 0.88rem; padding: 3px 0; }
.history-season, .comp-pos { font-weight: 600; }
.history-pts, .comp-age { color: var(--text-muted); }

.standing-section { margin-bottom: 32px; }
.standing { max-width: 72ch; }
.standing p { margin: 0 0 14px; }

.outlook-section { margin-bottom: 32px; }
.outlook { max-width: 72ch; }
.outlook p { margin: 0 0 14px; }

.narrative-section { margin-bottom: 32px; }
.narrative { max-width: 72ch; }
.sw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 16px; }
.sw-grid h3 { font-size: 0.95rem; margin-bottom: 8px; }
.sw-grid ul { margin: 0; padding-left: 20px; }
.sw-grid li { margin-bottom: 8px; font-size: 0.92rem; }
.strengths h3 { color: var(--contender); }
.weaknesses h3 { color: var(--winnow); }

.picks-section { margin-bottom: 32px; }
.picks-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.picks-season { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; gap: 2px; }
.picks-year { font-weight: 700; font-size: 0.95rem; }
.picks-list { font-size: 0.85rem; color: var(--text-muted); }
.picks-count { opacity: 0.8; }

.roster-section h2 { margin-top: 32px; }
.roster-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-bottom: 8px; }
.roster-table th { text-align: left; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.roster-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
.roster-table tr:hover { background: var(--surface); }
.name { font-weight: 600; }
.nfl-team, .age, .exp { color: var(--text-muted); }

.tag { display: inline-block; font-size: 0.7rem; font-weight: 700; padding: 1px 7px; border-radius: 5px; background: var(--border); }
.tag-injury { background: var(--winnow); color: #fff; }

.roster-table { overflow-x: auto; display: block; }
@media (min-width: 640px) { .roster-table { display: table; } }
@media (max-width: 600px) {
  .sw-grid { grid-template-columns: 1fr; }
}

.history-section { margin-top: 48px; }
.history-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.history-table th { text-align: left; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.history-table td { padding: 7px 8px; border-bottom: 1px solid var(--border); }
.hist-year { color: var(--text-muted); font-weight: 600; }

.analytics-section { margin-bottom: 40px; }
.section-note { color: var(--text-muted); font-size: 0.88rem; max-width: 68ch; margin: 4px 0 16px; }
.luck-pos { color: var(--contender); font-weight: 700; }
.luck-neg { color: var(--winnow); font-weight: 700; }
.tx-total { font-weight: 700; }

.pos-legend { display: flex; gap: 16px; margin-bottom: 12px; font-size: 0.8rem; color: var(--text-muted); }
.pos-legend-item { display: flex; align-items: center; gap: 5px; }
.pos-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.pos-chart { display: flex; flex-direction: column; gap: 10px; }
.pos-row { display: grid; grid-template-columns: 150px 1fr; align-items: center; gap: 10px; }
.pos-team { font-size: 0.85rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pos-bar { display: flex; height: 18px; border-radius: 4px; overflow: hidden; background: var(--border); }
.pos-seg { height: 100%; }
@media (max-width: 560px) {
  .pos-row { grid-template-columns: 1fr; }
}

.net-chart { display: flex; flex-direction: column; gap: 8px; }
.net-row { display: grid; grid-template-columns: 150px 1fr 40px; align-items: center; gap: 10px; font-size: 0.85rem; }
.net-team { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.net-bar-track { display: flex; align-items: center; height: 14px; }
.net-bar-neg { height: 100%; background: var(--winnow); border-radius: 3px 0 0 3px; margin-left: auto; }
.net-bar-mid { width: 2px; height: 100%; background: var(--border); }
.net-bar-pos { height: 100%; background: var(--contender); border-radius: 0 3px 3px 0; }
.net-value { font-weight: 700; text-align: right; }

.trade-ledger td { font-size: 0.85rem; padding: 5px 8px; }
.trade-ledger .rd { color: var(--text-muted); font-weight: 600; width: 55px; }
.trade-ledger .arrow { color: var(--text-muted); width: 20px; text-align: center; }

.trade-list { display: flex; flex-direction: column; gap: 12px; }
.trade-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; }
.trade-meta { color: var(--text-muted); font-size: 0.78rem; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.03em; }
.trade-sides { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
.trade-side h4 { margin: 0 0 8px; font-size: 0.95rem; }
.trade-side ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.trade-side li { font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
.trade-empty { color: var(--text-muted); font-style: italic; }
.trade-nfl { color: var(--text-muted); font-size: 0.78rem; }
.trade-pos { font-size: 0.68rem; font-weight: 700; width: 30px; text-align: center; border-radius: 3px; padding: 1px 0; color: #fff; flex-shrink: 0; }
.trade-pos.pos-QB { background: #7c93f0; }
.trade-pos.pos-RB { background: #3fb97d; }
.trade-pos.pos-WR { background: #d9a635; }
.trade-pos.pos-TE { background: #e0664a; }
.trade-pos.pos- { background: var(--text-muted); }
.trade-pos.trade-pick { background: var(--text-muted); width: auto; padding: 1px 6px; }

.pair-section { margin-bottom: 32px; }
.pair-section h3 { margin-bottom: 10px; }
.pair-section .trade-list { margin-bottom: 4px; }

.site-footer { margin-top: 60px; color: var(--text-muted); font-size: 0.8rem; border-top: 1px solid var(--border); padding-top: 16px; }
"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    teams = load("teams.json")
    content = load("content.json")
    rings, runner_ups = compute_rings(content.get("championships", []))

    (DOCS_DIR / "style.css").write_text(CSS)

    for t in teams:
        c = content["teams"][str(t["roster_id"])]
        html = build_team_page(t, c, rings, runner_ups)
        (DOCS_DIR / f"team-{t['roster_id']}.html").write_text(html)

    index_html = build_index(teams, content["teams"], content, rings, runner_ups)
    (DOCS_DIR / "index.html").write_text(index_html)

    season_summaries = load("season_summaries.json")
    history_html = build_history_page(season_summaries, teams)
    (DOCS_DIR / "history.html").write_text(history_html)

    h2h_matrix = load("head_to_head.json")
    h2h_html = build_head_to_head_page(h2h_matrix, teams)
    (DOCS_DIR / "head-to-head.html").write_text(h2h_html)

    analytics = load("analytics.json")
    analytics_html = build_analytics_page(analytics, teams)
    (DOCS_DIR / "analytics.html").write_text(analytics_html)

    draft_flow = load("draft_flow.json")
    draft_flow_html = build_draft_flow_page(draft_flow, teams)
    (DOCS_DIR / "draft-flow.html").write_text(draft_flow_html)

    trades_data = load("trades.json")
    trades_html = build_trades_page(trades_data, teams)
    (DOCS_DIR / "trades.html").write_text(trades_html)

    print(f"Built {len(teams)} team pages + index + history + head-to-head + analytics + draft-flow + trades into {DOCS_DIR}")


if __name__ == "__main__":
    main()
