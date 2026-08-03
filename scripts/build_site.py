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
    ("link", "index.html", "Home"),
    ("link", "power-rankings.html", "Power Rankings"),
    ("link", "history.html", "League History"),
    ("link", "head-to-head.html", "Head-to-Head"),
    ("link", "rivalries.html", "Rivalries"),
    ("link", "analytics.html", "Analytics"),
    ("link", "trades.html", "Trades"),
]

POSITION_COLORS = {"QB": "#e5484d", "RB": "#3fb97d", "WR": "#4f7fe0", "TE": "#d9a635"}


def nav_html(active):
    """Renders NAV_ITEMS. Each item is either ("link", href, label) for a
    plain top-bar link, or ("group", label, [(href, label), ...]) for a
    dropdown holding multiple pages under one header (e.g. Weekly Recap,
    one page per week) -- a <details>/<summary> disclosure so it works
    without JS: native click-to-toggle for touch, plus a CSS :hover
    override for desktop mouse users.
    """
    parts = []
    for item in NAV_ITEMS:
        if item[0] == "link":
            _, href, label = item
            cls = "nav-link active" if href == active else "nav-link"
            parts.append(f'<a class="{cls}" href="{href}">{esc(label)}</a>')
        else:
            _, label, children = item
            group_active = any(href == active for href, _ in children)
            open_attr = " open" if group_active else ""
            summary_cls = "nav-link nav-group-summary active" if group_active else "nav-link nav-group-summary"
            child_links = "".join(
                f'<a class="nav-dropdown-link{" active" if href == active else ""}" href="{href}">{esc(clabel)}</a>'
                for href, clabel in children
            )
            parts.append(
                f'<details class="nav-group"{open_attr}><summary class="{summary_cls}">{esc(label)}</summary>'
                f'<div class="nav-dropdown">{child_links}</div></details>'
            )
    return f'<nav class="site-nav"><span class="nav-brand">Ethel\'s Dynasty</span><div class="nav-links">{"".join(parts)}</div></nav>'


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


def build_team_page(team, content, rings, runner_ups, season_summaries, transaction_count):
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

    season_rows = []
    for s in sorted(season_summaries, key=lambda s: -s["season"]):
        st = next((x for x in s.get("standings", []) if x["owner_id"] == team["owner_id"]), None)
        if not st:
            continue
        season_rows.append(f"""<tr>
<td>{s['season']}</td>
<td>{st['wins']}-{st['losses']}{'-' + str(st['ties']) if st['ties'] else ''}</td>
<td>{st['points_for']:.1f}</td>
<td>{st['points_against']:.1f}</td>
<td>{playoff_badge(st['place'])}</td>
</tr>""")
    season_history_table = (
        f"""<table class="roster-table season-standings">
<thead><tr><th>Season</th><th>Record</th><th>PF</th><th>PA</th><th>Finish</th></tr></thead>
<tbody>{"".join(season_rows)}</tbody>
</table>"""
        if season_rows
        else '<p class="stat-label">No prior seasons on record</p>'
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
<a class="back-link" href="power-rankings.html">&larr; All Teams</a>
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

<section class="season-history-section">
  <h2>Season History</h2>
  {season_history_table}
  <p class="section-note"><a href="team-{team['roster_id']}-transactions.html">See all {transaction_count} transactions across every season &rarr;</a></p>
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


HUB_SECTIONS = [
    ("power-rankings.html", "Power Rankings", "Every team's 2026 outlook: verdict, strengths, weaknesses, and draft recommendations."),
    ("history.html", "League History", "Season-by-season standings and champions, back to the league's 2018 founding."),
    ("head-to-head.html", "Head-to-Head", "All-time records between every team currently in the league."),
    ("analytics.html", "Analytics", "All-play luck, positional scoring mix, and roster-management activity."),
    ("trades.html", "Trades", "Every trade ever made, dynasty value grades, the Hall of Bad Trades, and the draft pick capital ledger."),
    ("weekly-recaps.html", "Weekly Recap", "Scores, transactions, and a recap of how each week's matchups went."),
]


def build_home_page(league_content, teams, rings, season_summaries, current_owner_ids):
    hub_cards = "".join(
        f"""<a class="hub-card" href="{href}">
  <h3>{esc(label)}</h3>
  <p>{esc(desc)}</p>
</a>"""
        for href, label, desc in HUB_SECTIONS
    )

    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}
    real_seasons = sorted((s for s in season_summaries if s["season"] != 2018), key=lambda s: -s["season"])
    latest = real_seasons[0] if real_seasons else None
    champ_roster = owner_to_roster.get(latest["champion_owner_id"]) if latest else None
    champ_link = (
        f'<a href="team-{champ_roster}.html">{esc(latest["champion"])}</a>'
        if latest and champ_roster
        else esc(latest["champion"]) if latest else "&mdash;"
    )
    total_rings = sum(rings.values())

    facts = f"""
<div class="snapshot-card">
  <h3>Founded</h3>
  <p class="big-stat">2018</p>
  <p class="stat-label">on a different platform, pre-Sleeper</p>
</div>
<div class="snapshot-card">
  <h3>Teams</h3>
  <p class="big-stat">{len(current_owner_ids)}</p>
  <p class="stat-label">half-PPR, one QB, four-round rookie draft</p>
</div>
<div class="snapshot-card">
  <h3>Reigning Champion</h3>
  <p class="big-stat">{champ_link}</p>
  <p class="stat-label">{latest['season'] if latest else ''} season</p>
</div>
<div class="snapshot-card">
  <h3>Championships Awarded</h3>
  <p class="big-stat">{total_rings}</p>
  <p class="stat-label">since 2018, including the pre-Sleeper era</p>
</div>
"""

    body = f"""
<header class="league-header">
  <h1>Ethel's Dynasty</h1>
  <p class="league-summary">{esc(league_content['league_summary'])}</p>
</header>

<section class="snapshot-grid">
  {facts}
</section>

<section class="hub-section">
  <h2>Explore the League</h2>
  <div class="hub-grid">
    {hub_cards}
  </div>
</section>

<footer class="site-footer">
  <p>Built from live Sleeper league data. Analysis and grades are opinion, not projections.</p>
</footer>
"""
    return page_shell(
        "Ethel's Dynasty",
        body,
        active="index.html",
        description=league_content["league_summary"],
    )


def build_power_rankings_page(teams, content_all, league_content, rings, runner_ups):
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
        active="power-rankings.html",
        description=league_content["league_summary"],
    )


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
            lo, hi = sorted((row_owner, col_owner))
            href = f"rivalries.html#pair-{lo}-{hi}"
            cells.append(f'<td class="{cls}"><a href="{href}" title="{esc(name_by_owner[row_owner])} vs {esc(name_by_owner[col_owner])}: {label} &mdash; see every game">{label}</a></td>')
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


def build_rivalries_page(rivalries, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}
    teams_sorted = sorted(teams, key=lambda t: t["team_name"])

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    def pair_anchor(a, b):
        lo, hi = sorted((a, b))
        return f"pair-{lo}-{hi}"

    def options_html(selected_owner_id):
        opts = []
        for t in teams_sorted:
            sel = " selected" if t["owner_id"] == selected_owner_id else ""
            opts.append(f'<option value="{esc(t["owner_id"])}"{sel}>{esc(t["team_name"])}</option>')
        return "".join(opts)

    default_a = teams_sorted[0]["owner_id"] if teams_sorted else ""
    default_b = teams_sorted[1]["owner_id"] if len(teams_sorted) > 1 else ""

    def game_row(g, a_name, b_name):
        if g["a_score"] > g["b_score"]:
            result = f"{esc(a_name)} won"
        elif g["b_score"] > g["a_score"]:
            result = f"{esc(b_name)} won"
        else:
            result = "Tied"
        return f"""<tr>
<td>{g['season']}</td>
<td>Week {g['week']}</td>
<td>{g['a_score']:.2f} &ndash; {g['b_score']:.2f}</td>
<td>{result}</td>
</tr>"""

    sections = []
    for p in rivalries:
        rows = "".join(game_row(g, p["a_name"], p["b_name"]) for g in p["games"])
        record = f"{p['a_wins']}-{p['b_wins']}" + (f"-{p['ties']}" if p["ties"] else "")
        sections.append(f"""
<div class="pair-section" id="{pair_anchor(p['a'], p['b'])}">
  <h3>{team_link(p['a'], p['a_name'])} &harr; {team_link(p['b'], p['b_name'])}</h3>
  <p class="section-note">All-time: {esc(p['a_name'])} {record} {esc(p['b_name'])} ({p['a_points']:.2f} &ndash; {p['b_points']:.2f} combined points) across {len(p['games'])} game{'s' if len(p['games']) != 1 else ''}.</p>
  <table class="roster-table">
    <thead><tr><th>Season</th><th>Week</th><th>Score ({esc(p['a_name'])} &ndash; {esc(p['b_name'])})</th><th>Result</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="4" class="trade-empty">No games on record</td></tr>'}</tbody>
  </table>
</div>""")

    body = f"""
<header class="league-header">
  <h1>Rivalries</h1>
  <p class="league-summary">Pick any two teams to see their complete head-to-head history, game by game, back to 2019. Regular-season games only; 2022&ndash;2025 week 14 "vs. league median" games are excluded since there was no real opponent that week.</p>
</header>

<section class="analytics-section">
  <div class="rivalry-picker">
    <select id="rivalry-team-a">{options_html(default_a)}</select>
    <span class="rivalry-vs">vs</span>
    <select id="rivalry-team-b">{options_html(default_b)}</select>
    <button type="button" onclick="(function(){{
      var a=document.getElementById('rivalry-team-a').value;
      var b=document.getElementById('rivalry-team-b').value;
      if(a===b){{return;}}
      var pair=[a,b].sort();
      window.location.hash='pair-'+pair[0]+'-'+pair[1];
    }})()">View history</button>
  </div>
</section>

<section class="analytics-section">
  {"".join(sections)}
</section>
"""
    return page_shell(
        "Rivalries — Ethel's Dynasty",
        body,
        description="Full head-to-head game log between any two teams in league history.",
        active="rivalries.html",
    )


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


def draft_flow_sections_html(draft_flow, team_link):
    """Net draft capital leaderboard + pick trade ledgers, as a chunk of
    <section> HTML to embed in the Trades page (not a standalone page --
    draft pick trades are just another flavor of trade)."""
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

    return f"""
<section class="analytics-section" id="draft-capital">
  <h2>Draft Capital Flow</h2>
  <p class="section-note">Every draft pick trade in league history, 2019 through the 2028 class. "Net capital" is picks acquired minus picks given away across the team's whole history &mdash; positive means a team has consistently traded for future equity, negative means it's been spending picks to win now.</p>
  <div class="net-chart">{"".join(net_rows)}</div>
</section>

<section class="analytics-section" id="future-picks">
  <h2>Future Pick Trades (2026-2028)</h2>
  <div class="history-list">{trade_ledger(draft_flow["future_trades"], seasons_desc=False)}</div>
</section>

<section class="analytics-section" id="historical-picks">
  <h2>Historical Pick Trades (2019-2025)</h2>
  <div class="history-list">{trade_ledger(draft_flow["historical_trades"])}</div>
</section>
"""


def tx_date(t):
    if not t.get("created"):
        return f"{t['season']} season"
    dt = datetime.fromtimestamp(t["created"] / 1000, tz=timezone.utc)
    return dt.strftime("%b %-d, %Y")


def build_trades_page(trades_data, teams, trade_grades, draft_flow):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    def pair_anchor(a, b):
        return f"pair-{a}-{b}"

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

    def grade_html(t):
        g = trade_grades.get(t["transaction_id"])
        if not g:
            return '<p class="trade-grade-note">Not graded &mdash; either too recent (needs a year to pass) or predates available dynasty value data (before May 2020).</p>'

        aged_vals = {o: g["sides"][o]["aged_value"] for o in t["teams"]}
        best = max(aged_vals.values())
        any_incomplete = any(not g["sides"][o]["hist_complete"] or not g["sides"][o]["aged_complete"] for o in t["teams"])
        rows = []
        for o in t["teams"]:
            s = g["sides"][o]
            won_cls = " trade-grade-won" if s["aged_value"] == best and len(set(aged_vals.values())) > 1 else ""
            rows.append(
                f'<tr class="{won_cls.strip()}"><td>{team_link(o, t["team_names"][o])}</td>'
                f'<td>{s["hist_value"]:.0f}</td><td>{s["aged_value"]:.0f}</td></tr>'
            )
        horizon_label = f"{g['horizon_years']}-yr avg" if g["horizon_years"] > 1 else "1-yr"
        incomplete_note = (
            '<p class="trade-grade-note">* one or more assets couldn\'t be fully valued (missing from a snapshot); totals are a lower bound.</p>'
            if any_incomplete
            else ""
        )
        return f"""<div class="trade-grade">
  <table class="trade-grade-table">
    <thead><tr><th>Team</th><th>At Trade</th><th>{esc(horizon_label)} Later</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  {incomplete_note}
</div>"""

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
  <div class="trade-meta">{esc(tx_date(t))}</div>
  <div class="trade-sides">{sides_html}</div>
  {grade_html(t)}
</div>"""

    # --- hall of bad trades: the most lopsided deals in hindsight ---
    def bad_trade_entries(limit=10):
        """For every graded trade, find the side that came out worst against
        the best-off side in that same trade (by the aged-value checkpoint),
        and rank across all trades by how big that gap was. Only meaningful
        for 2+ side trades that actually got graded (see grade_html).

        Requires every side to be aged_complete (the gap is computed purely
        from aged_value, so that's the only completeness that matters here).
        Otherwise a side whose only asset couldn't be priced at all (e.g. a
        same-year pick that already resolved by the time the 1-year
        checkpoint rolled around, so it dropped out of DynastyProcess's data
        entirely) totals to a literal $0 and would rank as "lost everything"
        -- indistinguishable from an actually bad trade -- when the honest
        answer is just "unknown." hist_complete doesn't gate ranking (a side
        can have an under-counted at-trade value and still have a fully
        known aged value), but bad_trade_card still surfaces it visually.
        """
        entries = []
        for t in trades_data["trades"]:
            g = trade_grades.get(t["transaction_id"])
            if not g or len(t["teams"]) < 2:
                continue
            if any(not g["sides"][o]["aged_complete"] for o in t["teams"]):
                continue
            aged = {o: g["sides"][o]["aged_value"] for o in t["teams"]}
            for o in t["teams"]:
                others_best = max(v for oo, v in aged.items() if oo != o)
                gap = others_best - aged[o]
                if gap > 0:
                    entries.append({"trade": t, "loser": o, "gap": gap})
        entries.sort(key=lambda e: -e["gap"])
        return entries[:limit]

    def value_bar(value, scale_max, cls):
        pct = min(100, value / scale_max * 100) if scale_max else 0
        return f'<span class="badtrade-bar-track"><span class="badtrade-bar-fill {cls}" style="width:{pct:.0f}%"></span></span><span class="badtrade-bar-val">{value:,.0f}</span>'

    def bad_trade_card(rank, entry):
        t = entry["trade"]
        g = trade_grades[t["transaction_id"]]
        horizon_label = f"{g['horizon_years']}-yr avg" if g["horizon_years"] > 1 else "1-yr"
        scale_max = max(
            (g["sides"][o]["hist_value"] for o in t["teams"]),
            default=1,
        )
        scale_max = max(scale_max, max((g["sides"][o]["aged_value"] for o in t["teams"]), default=1), 1)

        def side_block(o):
            s = g["sides"][o]
            aged_cls = "badtrade-bar-pos" if s["aged_value"] >= s["hist_value"] else "badtrade-bar-neg"
            hist_note = (
                '<p class="trade-grade-note">* at-trade value is a lower bound, not every asset was priceable then.</p>'
                if not s["hist_complete"]
                else ""
            )
            return f"""<div class="trade-side">
  <h4>{team_link(o, t['team_names'][o])}</h4>
  <ul>{side_items(t['sides'][o])}</ul>
  <div class="badtrade-bars">
    <div class="badtrade-bar-row"><span class="badtrade-bar-label">At Trade</span>{value_bar(s['hist_value'], scale_max, 'badtrade-bar-neutral')}</div>
    <div class="badtrade-bar-row"><span class="badtrade-bar-label">{esc(horizon_label)}</span>{value_bar(s['aged_value'], scale_max, aged_cls)}</div>
  </div>
  {hist_note}
</div>"""

        sides_html = "".join(side_block(o) for o in t["teams"])
        loser_name = t["team_names"][entry["loser"]]
        return f"""
<div class="trade-card bad-trade-card" id="bad-trade-{rank}">
  <div class="trade-meta">#{rank} &middot; {esc(tx_date(t))} <span class="bad-trade-badge">&#128315; {team_link(entry['loser'], loser_name)} lost by {entry['gap']:,.0f}</span></div>
  <div class="trade-sides">{sides_html}</div>
</div>"""

    bad_trades = bad_trade_entries()

    def bad_trades_leaderboard(entries):
        max_gap = max((e["gap"] for e in entries), default=1) or 1
        rows = []
        for i, e in enumerate(entries, 1):
            pct = e["gap"] / max_gap * 100
            loser_name = e["trade"]["team_names"][e["loser"]]
            rows.append(f"""<a class="badtrade-lb-row" href="#bad-trade-{i}">
  <span class="badtrade-lb-rank">#{i}</span>
  <span class="badtrade-lb-team">{esc(loser_name)}</span>
  <span class="badtrade-lb-track"><span class="badtrade-lb-fill" style="width:{pct:.0f}%"></span></span>
  <span class="badtrade-lb-val">-{e['gap']:,.0f}</span>
</a>""")
        return f'<div class="badtrade-leaderboard">{"".join(rows)}</div>'

    bad_trades_html = (
        bad_trades_leaderboard(bad_trades) + "".join(bad_trade_card(i, e) for i, e in enumerate(bad_trades, 1))
        if bad_trades
        else '<p class="section-note">Not enough graded trades yet to rank.</p>'
    )

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

    draft_flow_html = draft_flow_sections_html(draft_flow, team_link)

    body = f"""
<header class="league-header">
  <h1>Trades</h1>
  <p class="league-summary">Every trade in league history, 2019 through today &mdash; players and draft picks both &mdash; plus the draft pick capital ledger. Click a pair below to jump straight to every deal those two teams have made with each other.</p>
  <p class="section-note">Each trade with a Dynasty Value grade shows what each side was worth at the moment of the trade versus the average of its value 1, 2, and 3 years later (whichever have elapsed) &mdash; not "value today," which would unfairly zero out old trades just from players aging out of relevance. Values come from <a href="https://github.com/dynastyprocess/data" target="_blank" rel="noopener">DynastyProcess's open-data project</a>; trades before May 2020 predate their value history and aren't graded, and trades under a year old haven't aged long enough yet.</p>
  <nav class="subnav">
    <a href="#hall-of-bad-trades">Hall of Bad Trades</a>
    <a href="#trade-partners">Trade Partners</a>
    <a href="#all-trades">All Trades</a>
    <a href="#by-pair">By Team Pair</a>
    <a href="#draft-capital">Draft Capital Flow</a>
  </nav>
</header>

<section class="analytics-section" id="hall-of-bad-trades">
  <h2>Hall of Bad Trades</h2>
  <p class="section-note">The most lopsided deals in hindsight &mdash; ranked by how far the losing side's aged Dynasty Value fell behind the other side's, at the same checkpoint.</p>
  <div class="trade-list">{bad_trades_html}</div>
</section>

<section class="analytics-section" id="trade-partners">
  <h2>Most Active Trade Partners</h2>
  <table class="roster-table">
    <thead><tr><th>Pair</th><th>Trades</th></tr></thead>
    <tbody>{partner_rows}</tbody>
  </table>
</section>

<section class="analytics-section" id="all-trades">
  <h2>All Trades</h2>
  <p class="section-note">Newest first, {len(trades_data['trades'])} trades total.</p>
  <div class="trade-list">{all_trades_html}</div>
</section>

<section class="analytics-section" id="by-pair">
  <h2>By Team Pair</h2>
  {"".join(pair_sections)}
</section>

{draft_flow_html}
"""
    return page_shell("Trades — Ethel's Dynasty", body, description="Every trade in league history, dynasty value grades, the Hall of Bad Trades, and the draft pick capital ledger.", active="trades.html")


def weekly_nav_children(weekly_data):
    """The (href, label) pairs for the Weekly Recap dropdown -- the hub
    plus one entry per played week, newest first (weekly_data["weeks"] is
    already sorted that way by compute_weekly.py)."""
    children = [("weekly-recaps.html", "Overview")]
    for w in weekly_data["weeks"]:
        children.append((f"week-{w['week']}-recap.html", f"Week {w['week']}"))
    return children


def build_weekly_recap_hub_page(weekly_data, prose_data, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    weeks = weekly_data["weeks"]
    if not weeks:
        cards_html = '<p class="section-note">The 2026 season hasn\'t kicked off yet &mdash; check back after Week 1 for scores, transactions, and recaps.</p>'
    else:
        cards = []
        for w in weeks:
            headline = prose_data.get("weeks", {}).get(str(w["week"]), {}).get("headline")
            top = w["highlights"]["top_scorer"]
            summary = esc(headline) if headline else f"Top score: {team_link(top['owner_id'], top['name'])} with {top['points']:.1f}"
            cards.append(f"""<a class="hub-card" href="week-{w['week']}-recap.html">
  <h3>Week {w['week']}</h3>
  <p>{summary}</p>
</a>""")
        cards_html = f'<div class="hub-grid">{"".join(cards)}</div>'

    body = f"""
<header class="league-header">
  <h1>Weekly Recap</h1>
  <p class="league-summary">Every week of the {weekly_data['season']} season &mdash; scores, transactions, and a recap of how each matchup went.</p>
</header>

<section class="hub-section">
  {cards_html}
</section>
"""
    return page_shell("Weekly Recap — Ethel's Dynasty", body, description="Weekly scores, transactions, and recaps for the current season.", active="weekly-recaps.html")


def build_weekly_recap_page(week_data, weekly_data, prose_data, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    week_prose = prose_data.get("weeks", {}).get(str(week_data["week"]), {})

    def asset_items(items):
        rendered = []
        for a in items:
            pos = a["position"] or ""
            nfl = a["team"] or "FA"
            rendered.append(f'<li><span class="trade-pos pos-{pos}">{esc(pos)}</span> {esc(a["name"])} <span class="trade-nfl">{esc(nfl)}</span></li>')
        if not rendered:
            return '<li class="trade-empty">(nothing)</li>'
        return "".join(rendered)

    def pick_items(picks):
        return "".join(f'<li><span class="trade-pos trade-pick">PICK</span> {esc(pk["season"])} Round {pk["round"]}</li>' for pk in picks)

    def tx_card(tx):
        if tx["type"] == "trade":
            sides_html = "".join(
                f"""<div class="trade-side">
  <h4>{team_link(o, tx['team_names'][o])}</h4>
  <ul>{asset_items(tx['sides'][o]['players']) + pick_items(tx['sides'][o]['picks'])}</ul>
</div>"""
                for o in tx["teams"]
            )
            return f"""
<div class="trade-card">
  <div class="trade-meta">{esc(tx_date(tx))} &middot; Trade</div>
  <div class="trade-sides">{sides_html}</div>
</div>"""
        label = TX_TYPE_LABEL.get(tx["type"], tx["type"])
        return f"""
<div class="trade-card">
  <div class="trade-meta">{esc(tx_date(tx))} &middot; {esc(label)} &middot; {team_link(tx['owner_id'], tx['name'])}</div>
  <div class="trade-sides">
    <div class="trade-side"><h4>Dropped</h4><ul>{asset_items(tx['gave'])}</ul></div>
    <div class="trade-side"><h4>Added</h4><ul>{asset_items(tx['received'])}</ul></div>
  </div>
</div>"""

    def game_card(g):
        a, b = g["team_a"], g["team_b"]
        a_win = g["winner_owner_id"] == a["owner_id"]
        b_win = g["winner_owner_id"] == b["owner_id"]
        blurb = week_prose.get("games", {}).get(g["game_key"])
        blurb_html = f'<p class="week-game-blurb">{esc(blurb)}</p>' if blurb else ""
        return f"""<div class="week-game-card">
  <div class="week-game-row{' week-game-winner' if a_win else ''}">
    <span class="week-game-team">{team_link(a['owner_id'], a['name'])}</span>
    <span class="week-game-score">{a['points']:.1f}</span>
  </div>
  <div class="week-game-row{' week-game-winner' if b_win else ''}">
    <span class="week-game-team">{team_link(b['owner_id'], b['name'])}</span>
    <span class="week-game-score">{b['points']:.1f}</span>
  </div>
  <p class="section-note">Margin: {g['margin']:.1f}</p>
  {blurb_html}
</div>"""

    h = week_data["highlights"]
    highlight_cards = f"""
<div class="snapshot-card">
  <h3>Top Score</h3>
  <p class="big-stat">{team_link(h['top_scorer']['owner_id'], h['top_scorer']['name'])}</p>
  <p class="stat-label">{h['top_scorer']['points']:.1f} points</p>
</div>
<div class="snapshot-card">
  <h3>Low Score</h3>
  <p class="big-stat">{team_link(h['low_scorer']['owner_id'], h['low_scorer']['name'])}</p>
  <p class="stat-label">{h['low_scorer']['points']:.1f} points</p>
</div>
<div class="snapshot-card">
  <h3>Closest Game</h3>
  {f"<p class='big-stat'>{h['closest_game']['margin']:.1f} pts</p><p class='stat-label'>{team_link(h['closest_game']['team_a']['owner_id'], h['closest_game']['team_a']['name'])} vs {team_link(h['closest_game']['team_b']['owner_id'], h['closest_game']['team_b']['name'])}</p>" if h['closest_game'] else "<p class='big-stat'>&mdash;</p>"}
</div>
<div class="snapshot-card">
  <h3>Biggest Blowout</h3>
  <p class="big-stat">{h['biggest_blowout']['margin']:.1f} pts</p>
  <p class="stat-label">{team_link(h['biggest_blowout']['team_a']['owner_id'], h['biggest_blowout']['team_a']['name'])} vs {team_link(h['biggest_blowout']['team_b']['owner_id'], h['biggest_blowout']['team_b']['name'])}</p>
</div>
"""

    intro = f'<p class="league-summary">{esc(week_prose["intro"])}</p>' if week_prose.get("intro") else ""
    title_suffix = f": {week_prose['headline']}" if week_prose.get("headline") else ""

    weeks_nav = weekly_nav_children(weekly_data)
    idx = next(i for i, (href, _) in enumerate(weeks_nav) if href == f"week-{week_data['week']}-recap.html")
    prev_link = f'<a href="{weeks_nav[idx + 1][0]}">&larr; {esc(weeks_nav[idx + 1][1])}</a>' if idx + 1 < len(weeks_nav) else ""
    next_link = f'<a href="{weeks_nav[idx - 1][0]}">{esc(weeks_nav[idx - 1][1])} &rarr;</a>' if idx > 0 else ""

    body = f"""
<a class="back-link" href="weekly-recaps.html">&larr; Weekly Recap</a>
<header class="league-header">
  <h1>Week {week_data['week']}{esc(title_suffix)}</h1>
  {intro}
</header>

<section class="snapshot-grid">
  {highlight_cards}
</section>

<section class="analytics-section">
  <h2>Scores</h2>
  <div class="week-game-list">{"".join(game_card(g) for g in week_data['games'])}</div>
</section>

<section class="analytics-section">
  <h2>Transactions</h2>
  <div class="trade-list">{"".join(tx_card(t) for t in week_data['transactions']) or '<p class="stat-label">No transactions this week.</p>'}</div>
</section>

<div class="week-pager">{prev_link}{next_link}</div>
"""
    return page_shell(
        f"Week {week_data['week']} Recap — Ethel's Dynasty",
        body,
        description=f"Scores, transactions, and recap for Week {week_data['week']} of the {weekly_data['season']} season.",
        active=f"week-{week_data['week']}-recap.html",
    )


TX_TYPE_LABEL = {"trade": "Trade", "waiver": "Waiver Claim", "free_agent": "Free Agent Move"}


def build_team_transactions_page(team, tx_list, teams):
    owner_to_roster = {t["owner_id"]: t["roster_id"] for t in teams}

    def team_link(owner_id, name):
        roster_id = owner_to_roster.get(owner_id)
        if roster_id:
            return f'<a href="team-{roster_id}.html">{esc(name)}</a>'
        return esc(name)

    def asset_items(items):
        rendered = []
        for a in items:
            if a.get("pick"):
                rendered.append(f'<li><span class="trade-pos trade-pick">PICK</span> {esc(a["season"])} Round {a["round"]}</li>')
            else:
                pos = a["position"] or ""
                nfl = a["team"] or "FA"
                rendered.append(f'<li><span class="trade-pos pos-{pos}">{esc(pos)}</span> {esc(a["name"])} <span class="trade-nfl">{esc(nfl)}</span></li>')
        if not rendered:
            return '<li class="trade-empty">(nothing)</li>'
        return "".join(rendered)

    def tx_card(tx):
        label = TX_TYPE_LABEL.get(tx["type"], tx["type"])
        if tx["type"] == "trade":
            opp = " &amp; ".join(team_link(o["owner_id"], o["name"]) for o in tx["opponents"])
            heading = f'<p class="trade-heading">Trade with {opp}</p>'
            gave_label, received_label = "Gave", "Received"
        else:
            heading = ""
            gave_label, received_label = "Dropped", "Added"
        return f"""
<div class="trade-card">
  <div class="trade-meta">{esc(tx_date(tx))} &middot; {esc(label)}</div>
  {heading}
  <div class="trade-sides">
    <div class="trade-side">
      <h4>{gave_label}</h4>
      <ul>{asset_items(tx["gave"])}</ul>
    </div>
    <div class="trade-side">
      <h4>{received_label}</h4>
      <ul>{asset_items(tx["received"])}</ul>
    </div>
  </div>
</div>"""

    cards_html = "".join(tx_card(tx) for tx in tx_list)
    counts = {}
    for tx in tx_list:
        counts[tx["type"]] = counts.get(tx["type"], 0) + 1
    count_summary = " &middot; ".join(
        f"{counts.get(k, 0)} {TX_TYPE_LABEL[k].lower()}{'s' if counts.get(k, 0) != 1 else ''}"
        for k in ("trade", "waiver", "free_agent")
        if counts.get(k)
    )

    body = f"""
<a class="back-link" href="team-{team['roster_id']}.html">&larr; {esc(team['team_name'])}</a>
<header class="league-header">
  <h1>{esc(team['team_name'])} &mdash; All Transactions</h1>
  <p class="league-summary">Every trade, waiver claim, and free agent move this team has made across every season on record. {len(tx_list)} total: {count_summary}</p>
</header>

<section class="analytics-section">
  <div class="trade-list">{cards_html or '<p class="stat-label">No transactions on record</p>'}</div>
</section>
"""
    return page_shell(
        f"{team['team_name']} Transactions — Ethel's Dynasty",
        body,
        description=f"Every trade, waiver claim, and free agent move made by {team['team_name']}.",
        active="",
    )


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

.nav-group { position: relative; }
.nav-group-summary { cursor: pointer; list-style: none; }
.nav-group-summary::-webkit-details-marker { display: none; }
.nav-group-summary::after { content: "\25be"; margin-left: 4px; font-size: 0.7em; }
.nav-dropdown {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  flex-direction: column;
  min-width: 150px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
  z-index: 30;
}
.nav-group[open] > .nav-dropdown,
.nav-group:hover > .nav-dropdown { display: flex; }
.nav-dropdown-link {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 5px;
  white-space: nowrap;
}
.nav-dropdown-link:hover { text-decoration: none; background: var(--bg); color: var(--text); }
.nav-dropdown-link.active { color: var(--text); background: var(--bg); }

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
.h2h-table td a { color: inherit; text-decoration: none; }
.h2h-table td a:hover { text-decoration: underline; }

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

.hub-section { margin-top: 8px; }
.hub-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.hub-card {
  display: block;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
  color: var(--text);
}
.hub-card:hover { border-color: var(--accent); text-decoration: none; }
.hub-card h3 { margin: 0 0 8px; font-size: 1.05rem; }
.hub-card p { margin: 0; font-size: 0.88rem; color: var(--text-muted); }

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

.week-game-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.week-game-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; }
.week-game-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 0.92rem; }
.week-game-team { font-weight: 600; }
.week-game-score { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text-muted); }
.week-game-winner .week-game-team, .week-game-winner .week-game-score { color: var(--contender); }
.week-game-blurb { margin: 8px 0 0; font-size: 0.88rem; }
.week-pager { display: flex; justify-content: space-between; margin-top: 24px; font-size: 0.9rem; }
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

.season-history-section { margin-bottom: 32px; }

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
.trade-heading { font-weight: 600; margin: 0 0 10px; font-size: 0.95rem; }
.trade-sides { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
.trade-side h4 { margin: 0 0 8px; font-size: 0.95rem; }
.trade-side ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.trade-side li { font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
.trade-empty { color: var(--text-muted); font-style: italic; }
.trade-nfl { color: var(--text-muted); font-size: 0.78rem; }
.trade-pos { font-size: 0.68rem; font-weight: 700; width: 30px; text-align: center; border-radius: 3px; padding: 1px 0; color: #fff; flex-shrink: 0; }
.trade-pos.pos-QB { background: #e5484d; }
.trade-pos.pos-RB { background: #3fb97d; }
.trade-pos.pos-WR { background: #4f7fe0; }
.trade-pos.pos-TE { background: #d9a635; }
.trade-pos.pos- { background: var(--text-muted); }
.trade-pos.trade-pick { background: var(--text-muted); width: auto; padding: 1px 6px; }

.pair-section { margin-bottom: 32px; }
.pair-section h3 { margin-bottom: 10px; }
.pair-section .trade-list { margin-bottom: 4px; }

.trade-grade { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border); }
.trade-grade-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.trade-grade-table th { text-align: left; color: var(--text-muted); font-weight: 600; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.03em; padding: 2px 8px 4px 0; }
.trade-grade-table td { padding: 3px 8px 3px 0; }
.trade-grade-table tr.trade-grade-won td { font-weight: 700; color: var(--contender); }
.trade-grade-note { color: var(--text-muted); font-size: 0.76rem; font-style: italic; margin: 10px 0 0; }

.subnav { display: flex; gap: 14px; flex-wrap: wrap; margin: 10px 0 4px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 0.85rem; }
.subnav a { color: var(--text-muted); font-weight: 600; }
.subnav a:hover { color: var(--text); }

.badtrade-leaderboard { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
.badtrade-lb-row { display: grid; grid-template-columns: 30px 150px 1fr 70px; align-items: center; gap: 10px; font-size: 0.85rem; padding: 4px 0; color: var(--text); }
.badtrade-lb-row:hover { text-decoration: none; }
.badtrade-lb-row:hover .badtrade-lb-team { text-decoration: underline; }
.badtrade-lb-rank { color: var(--text-muted); font-weight: 700; font-variant-numeric: tabular-nums; }
.badtrade-lb-team { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.badtrade-lb-track { height: 12px; border-radius: 3px; background: var(--border); overflow: hidden; }
.badtrade-lb-fill { display: block; height: 100%; background: var(--winnow); border-radius: 3px; }
.badtrade-lb-val { text-align: right; font-weight: 700; color: var(--winnow); font-variant-numeric: tabular-nums; }
@media (max-width: 560px) {
  .badtrade-lb-row { grid-template-columns: 24px 90px 1fr 55px; font-size: 0.78rem; }
}

.bad-trade-card { border-color: var(--winnow); }
.bad-trade-badge { float: right; color: var(--winnow); font-weight: 700; letter-spacing: normal; text-transform: none; }

.badtrade-bars { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
.badtrade-bar-row { display: grid; grid-template-columns: 62px 1fr 55px; align-items: center; gap: 6px; font-size: 0.76rem; }
.badtrade-bar-label { color: var(--text-muted); }
.badtrade-bar-track { height: 10px; border-radius: 3px; background: var(--border); overflow: hidden; }
.badtrade-bar-fill { display: block; height: 100%; border-radius: 3px; }
.badtrade-bar-neutral { background: var(--text-muted); }
.badtrade-bar-pos { background: var(--contender); }
.badtrade-bar-neg { background: var(--winnow); }
.badtrade-bar-val { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }

.rivalry-picker { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rivalry-picker select { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface); color: var(--text); min-width: 200px; }
.rivalry-picker .rivalry-vs { color: var(--text-muted); font-weight: 600; }
.rivalry-picker button { font: inherit; font-weight: 600; padding: 8px 16px; border-radius: 8px; border: none; background: var(--accent); color: #fff; cursor: pointer; }
.rivalry-picker button:hover { opacity: 0.9; }

.site-footer { margin-top: 60px; color: var(--text-muted); font-size: 0.8rem; border-top: 1px solid var(--border); padding-top: 16px; }
"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    teams = load("teams.json")
    content = load("content.json")
    rings, runner_ups = compute_rings(content.get("championships", []))

    weekly_data = load("weekly.json") if (DATA_DIR / "weekly.json").exists() else {"season": 2026, "weeks": []}
    weekly_prose = load("weekly_recap_prose.json") if (DATA_DIR / "weekly_recap_prose.json").exists() else {"weeks": {}}
    NAV_ITEMS.append(("group", "Weekly Recap", weekly_nav_children(weekly_data)))

    (DOCS_DIR / "style.css").write_text(CSS)

    season_summaries = load("season_summaries.json")
    team_transactions = load("team_transactions.json")

    for t in teams:
        c = content["teams"][str(t["roster_id"])]
        tx_list = team_transactions.get(t["owner_id"], [])
        html = build_team_page(t, c, rings, runner_ups, season_summaries, len(tx_list))
        (DOCS_DIR / f"team-{t['roster_id']}.html").write_text(html)

        tx_html = build_team_transactions_page(t, tx_list, teams)
        (DOCS_DIR / f"team-{t['roster_id']}-transactions.html").write_text(tx_html)

    current_owner_ids = {t["owner_id"] for t in teams}
    home_html = build_home_page(content, teams, rings, season_summaries, current_owner_ids)
    (DOCS_DIR / "index.html").write_text(home_html)

    power_rankings_html = build_power_rankings_page(teams, content["teams"], content, rings, runner_ups)
    (DOCS_DIR / "power-rankings.html").write_text(power_rankings_html)

    history_html = build_history_page(season_summaries, teams)
    (DOCS_DIR / "history.html").write_text(history_html)

    h2h_matrix = load("head_to_head.json")
    h2h_html = build_head_to_head_page(h2h_matrix, teams)
    (DOCS_DIR / "head-to-head.html").write_text(h2h_html)

    rivalries = load("rivalries.json")
    rivalries_html = build_rivalries_page(rivalries, teams)
    (DOCS_DIR / "rivalries.html").write_text(rivalries_html)

    analytics = load("analytics.json")
    analytics_html = build_analytics_page(analytics, teams)
    (DOCS_DIR / "analytics.html").write_text(analytics_html)

    draft_flow = load("draft_flow.json")

    trades_data = load("trades.json")
    trade_grades = load("trade_grades.json")
    trades_html = build_trades_page(trades_data, teams, trade_grades, draft_flow)
    (DOCS_DIR / "trades.html").write_text(trades_html)

    stale_draft_flow_page = DOCS_DIR / "draft-flow.html"
    if stale_draft_flow_page.exists():
        stale_draft_flow_page.unlink()

    weekly_hub_html = build_weekly_recap_hub_page(weekly_data, weekly_prose, teams)
    (DOCS_DIR / "weekly-recaps.html").write_text(weekly_hub_html)
    current_week_pages = set()
    for w in weekly_data["weeks"]:
        week_html = build_weekly_recap_page(w, weekly_data, weekly_prose, teams)
        filename = f"week-{w['week']}-recap.html"
        (DOCS_DIR / filename).write_text(week_html)
        current_week_pages.add(filename)
    for stale in DOCS_DIR.glob("week-*-recap.html"):
        if stale.name not in current_week_pages:
            stale.unlink()

    print(
        f"Built {len(teams)} team pages + home + power-rankings + history + head-to-head + rivalries + "
        f"analytics + trades (incl. draft capital flow) + weekly recap ({len(weekly_data['weeks'])} weeks) into {DOCS_DIR}"
    )


if __name__ == "__main__":
    main()
