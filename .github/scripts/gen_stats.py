#!/usr/bin/env python3
"""Generate self-hosted GitHub stats cards (SVG) for the profile README.

Uses only the GitHub API + the Actions GITHUB_TOKEN, so it never depends on a
third-party hosted service. Output: dist/stats.svg and dist/top-langs.svg.
"""
import json
import os
import sys
import urllib.request
from html import escape
from math import cos, pi, sin

LOGIN = os.environ.get("GH_USER", "shuhan-wang1")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "dist")

BG = "#0d1117"
TITLE = "#00ADB5"
ICON = "#00ADB5"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
TRACK = "#21262d"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def api(url, data=None):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    res = api("https://api.github.com/graphql", body)
    user = (res.get("data") or {}).get("user")
    if res.get("errors"):
        # GITHUB_TOKEN can't read every field; keep going if we still got the user.
        print("GraphQL warnings:", json.dumps(res["errors"])[:2000], file=sys.stderr)
    if not user:
        raise RuntimeError(f"GraphQL returned no user: {res}")

    # All-time commit count (same approach as github-readme-stats' include_all_commits)
    try:
        commits = api(f"https://api.github.com/search/commits?q=author:{LOGIN}&per_page=1")["total_count"]
    except Exception as e:  # noqa: BLE001
        print(f"search/commits failed ({e}); falling back to last-year contributions", file=sys.stderr)
        cc = user["contributionsCollection"]
        commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]

    repos = [r for r in user["repositories"]["nodes"] if r]
    if all(r.get("stargazerCount") is not None for r in repos):
        stars = sum(r["stargazerCount"] for r in repos)
    else:
        # Fallback: public REST listing works with any token
        rest = api(f"https://api.github.com/users/{LOGIN}/repos?per_page=100&type=owner")
        stars = sum(r["stargazers_count"] for r in rest if not r["fork"])

    langs = {}
    colors = {}
    for r in repos:
        for e in ((r.get("languages") or {}).get("edges") or []):
            n = e["node"]["name"]
            langs[n] = langs.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or TITLE

    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    active_days = sum(1 for d in days if d > 0)

    return {
        "name": os.environ.get("DISPLAY_NAME") or user["name"] or LOGIN,
        "stars": stars,
        "commits": commits,
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "contributions": cal["totalContributions"],
        "active_days": active_days,
        "total_days": max(len(days), 1),
        "langs": sorted(langs.items(), key=lambda kv: kv[1], reverse=True),
        "colors": colors,
    }


# Octicons (16px) - MIT licensed, from primer/octicons
ICONS = {
    "star": "M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z",
    "commit": "M10.5 7.75a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zm1.43.75a4.002 4.002 0 01-7.86 0H.75a.75.75 0 110-1.5h3.32a4.001 4.001 0 017.86 0h3.32a.75.75 0 110 1.5h-3.32z",
    "pr": "M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z",
    "people": "M5.5 3.5a2 2 0 100 4 2 2 0 000-4zM2 5.5a3.5 3.5 0 115.898 2.549 5.507 5.507 0 013.034 4.084.75.75 0 11-1.482.235 4.001 4.001 0 00-7.9 0 .75.75 0 01-1.482-.236A5.507 5.507 0 013.102 8.05 3.49 3.49 0 012 5.5zM11 4a.75.75 0 100 1.5 1.5 1.5 0 01.666 2.844.75.75 0 00-.416.672v.352a.75.75 0 00.574.73c1.2.289 2.162 1.2 2.522 2.372a.75.75 0 101.434-.44 5.01 5.01 0 00-2.56-3.012A3 3 0 0011 4z",
}


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else str(n)


def stats_card(d):
    w, h = 495, 165
    rows = [
        ("star", "Total Stars Earned:", d["stars"]),
        ("commit", "Total Commits:", d["commits"]),
        ("pr", "Total PRs:", d["prs"]),
        ("people", "Contributed to (last year):", d["contributed_to"]),
    ]
    row_svg = []
    for i, (icon, label, val) in enumerate(rows):
        y = 60 + i * 25
        row_svg.append(
            f'<g transform="translate(25,{y - 12})">'
            f'<svg width="16" height="16" viewBox="0 0 16 16" fill="{ICON}"><path fill-rule="evenodd" d="{ICONS[icon]}"/></svg>'
            f'<text x="25" y="12.5" class="stat">{escape(label)}</text>'
            f'<text x="225" y="12.5" class="stat">{fmt(val)}</text>'
            f"</g>"
        )

    # Ring: total contributions in the last year; arc = share of active days
    cx, cy, r = 415, 88, 40
    frac = d["active_days"] / d["total_days"]
    frac = max(0.02, min(frac, 0.999))
    ang = 2 * pi * frac
    x1, y1 = cx, cy - r
    x2, y2 = cx + r * sin(ang), cy - r * cos(ang)
    large = 1 if ang > pi else 0
    arc = f"M {x1} {y1} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}"
    name = escape(d["name"])

    return f"""<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t">
<title id="t">{name}'s GitHub Stats</title>
<style>
.header {{ font: 600 18px {FONT}; fill: {TITLE}; }}
.stat {{ font: 600 14px {FONT}; fill: {TEXT}; }}
.big {{ font: 700 20px {FONT}; fill: {TEXT}; }}
.small {{ font: 400 10px {FONT}; fill: {MUTED}; }}
</style>
<rect width="{w}" height="{h}" rx="4.5" fill="{BG}"/>
<text x="25" y="35" class="header">{name}'s GitHub Stats</text>
{''.join(row_svg)}
<g>
<title>{d['active_days']} active days in the last year</title>
<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{TRACK}" stroke-width="6"/>
<path d="{arc}" stroke="{ICON}" stroke-width="6" stroke-linecap="round"/>
<text x="{cx}" y="{cy + 2}" text-anchor="middle" dominant-baseline="middle" class="big">{fmt(d['contributions'])}</text>
<text x="{cx}" y="{cy + 22}" text-anchor="middle" class="small">contributions / year</text>
</g>
</svg>
"""


def langs_card(d, count=8):
    w, h = 300, 165
    top = d["langs"][:count]
    total = sum(s for _, s in top) or 1
    items = [(n, s / total * 100, d["colors"][n]) for n, s in top]

    bar_x, bar_w = 25, w - 50
    x = bar_x
    segs = []
    for n, pct, c in items:
        sw = bar_w * pct / 100
        segs.append(f'<rect x="{x:.2f}" y="0" width="{sw:.2f}" height="8" fill="{c}"/>')
        x += sw

    rows = []
    for i, (n, pct, c) in enumerate(items):
        col, row = i % 2, i // 2
        rx = bar_x + col * 130
        ry = 85 + row * 19
        rows.append(
            f'<g transform="translate({rx},{ry})">'
            f'<circle cx="5" cy="-4" r="5" fill="{c}"/>'
            f'<text x="16" y="0" class="lang">{escape(n)} <tspan class="pct">{pct:.1f}%</tspan></text>'
            f"</g>"
        )

    return f"""<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t">
<title id="t">Most Used Languages</title>
<style>
.header {{ font: 600 18px {FONT}; fill: {TITLE}; }}
.lang {{ font: 400 11px {FONT}; fill: {TEXT}; }}
.pct {{ fill: {MUTED}; }}
</style>
<rect width="{w}" height="{h}" rx="4.5" fill="{BG}"/>
<text x="25" y="35" class="header">Most Used Languages</text>
<g transform="translate(0,55)">
<mask id="m"><rect x="{bar_x}" y="0" width="{bar_w}" height="8" rx="4" fill="white"/></mask>
<g mask="url(#m)">{''.join(segs)}</g>
</g>
{''.join(rows)}
</svg>
"""


def main():
    d = fetch()
    print(json.dumps({k: v for k, v in d.items() if k not in ("langs", "colors")}, indent=2))
    print("langs:", [(n, s) for n, s in d["langs"][:8]])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_card(d))
    with open(os.path.join(OUT, "top-langs.svg"), "w", encoding="utf-8") as f:
        f.write(langs_card(d))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
