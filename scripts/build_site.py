#!/usr/bin/env python3
"""Generate the static GitHub Pages site into docs/ from data/teams.json + data/content.json."""
import json
import re
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


def page_shell(title, body, description=""):
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
    )


def build_index(teams, content_all, league_content, rings, runner_ups):
    verdict_order = ["Win-Now Contender", "Contender", "Retool", "Rebuild"]
    teams_by_verdict = {v: [] for v in verdict_order}
    team_by_id = {t["roster_id"]: t for t in teams}
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

    history_rows = []
    for c in sorted(league_content.get("championships", []), key=lambda c: -c["year"]):
        winner = team_by_id[c["winner"]]
        loser = team_by_id[c["runner_up"]]
        history_rows.append(f"""<tr>
<td class="hist-year">{c['year']}</td>
<td><a href="team-{winner['roster_id']}.html">🏆 {esc(winner['team_name'])}</a></td>
<td><a href="team-{loser['roster_id']}.html">{esc(loser['team_name'])}</a></td>
</tr>""")
    history_table = f"""
<section class="history-section">
  <h2>League History</h2>
  <table class="history-table">
    <thead><tr><th>Year</th><th>Champion</th><th>Runner-up</th></tr></thead>
    <tbody>{"".join(history_rows)}</tbody>
  </table>
</section>""" if history_rows else ""

    body = f"""
<header class="league-header">
  <h1>{esc(league_content['league_headline'])}</h1>
  <p class="league-summary">{esc(league_content['league_summary'])}</p>
</header>
{"".join(sections)}
{history_table}
<footer class="site-footer">
  <p>Built from live Sleeper league data. Analysis and grades are opinion, not projections.</p>
</footer>
"""
    return page_shell(
        league_content["league_headline"],
        body,
        description=league_content["league_summary"],
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

    print(f"Built {len(teams)} team pages + index into {DOCS_DIR}")


if __name__ == "__main__":
    main()
