#!/usr/bin/env python3
"""Generate the SVG cards embedded in the profile README.

Everything under profile/ is produced by this script, so the README never
hot-links a shared rendering service that can rate-limit or go down.

Usage:
    GH_TOKEN=$(gh auth token) python3 scripts/generate_readme_cards.py

Only the standard library is used, so there is nothing to install.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = os.environ.get("PROFILE_LOGIN", "GoDiao")
DISPLAY_NAME = "DIAO Shengjia"
TAGLINE = "AI Engineer @ Garena (Sea) · AI/ML Researcher"
CHIPS = ["Agentic AI", "AI Infrastructure", "Computer Vision", "Embodied AI"]

API = "https://api.github.com/graphql"
OUT_DIR = Path(__file__).resolve().parent.parent / "profile"

# One palette for every card and every badge in the README: Garena red on black.
BG = "#050505"        # near-black card ground
PANEL = "#151515"     # tiles and empty heatmap cells
BORDER = "#242424"
TEXT = "#f2f2f2"
MUTED = "#8c8c8c"
ACCENT = "#e51d2a"    # Garena red
ACCENT_DEEP = "#7a0d14"

# Heatmap ramp, low to high, readable on the black ground.
HEAT = ["#161616", "#4a0f14", "#8c141d", "#cc1a26", "#ff3b45"]

FONT = (
    "ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
    "Roboto,'Helvetica Neue',Arial,sans-serif"
)

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: OWNER
      isFork: false
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 12, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(token, cursor=None):
    payload = json.dumps(
        {"query": QUERY, "variables": {"login": LOGIN, "cursor": cursor}}
    ).encode()
    req = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "profile-card-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    if "errors" in body:
        raise RuntimeError(json.dumps(body["errors"], indent=2))
    return body["data"]["user"]


def fetch():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("set GH_TOKEN (locally: GH_TOKEN=$(gh auth token))")

    user = graphql(token)
    repos = list(user["repositories"]["nodes"])
    page = user["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        more = graphql(token, page["endCursor"])
        repos.extend(more["repositories"]["nodes"])
        page = more["repositories"]["pageInfo"]

    contrib = user["contributionsCollection"]
    # GitHub's own per-language colors are ignored: blue/orange/green swatches
    # fight the red-on-black theme, and the language name is already spelled
    # out next to every swatch, so the hue carries no information here.
    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            langs[name] = langs.get(name, 0) + edge["size"]

    days = []
    for week in contrib["contributionCalendar"]["weeks"]:
        days.append(week["contributionDays"])

    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "commits": contrib["totalCommitContributions"]
        + contrib["restrictedContributionsCount"],
        "prs": contrib["totalPullRequestContributions"],
        "reviews": contrib["totalPullRequestReviewContributions"],
        "issues": contrib["totalIssueContributions"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "contributions": contrib["contributionCalendar"]["totalContributions"],
        "languages": langs,
        "weeks": days,
    }


def human(n):
    if n >= 10000:
        return "{:.1f}k".format(n / 1000).replace(".0k", "k")
    return str(n)


def write(name, body):
    path = OUT_DIR / name
    path.write_text(body, encoding="utf-8")
    print("wrote", path.relative_to(OUT_DIR.parent))


def frame(width, height, title=None):
    """Card background plus optional title; returns (svg_open, y_after_title)."""
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" role="img" font-family="{f}">'
        '<rect width="{w}" height="{h}" rx="10" fill="{bg}" '
        'stroke="{br}" stroke-width="1"/>'
    ).format(w=width, h=height, f=FONT, bg=BG, br=BORDER)
    y = 20
    if title:
        head += (
            '<text x="22" y="34" fill="{a}" font-size="15" '
            'font-weight="700">{t}</text>'
        ).format(a=ACCENT, t=escape(title))
        y = 58
    return head, y


# --------------------------------------------------------------------------
# banner.svg
# --------------------------------------------------------------------------
def banner():
    w, h = 1200, 260
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" role="img" font-family="{f}">'.format(
            w=w, h=h, f=FONT
        ),
        "<defs>",
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0%" stop-color="#000000"/>',
        '<stop offset="60%" stop-color="#140406"/>',
        '<stop offset="100%" stop-color="#26060a"/>',
        "</linearGradient>",
        '<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">',
        '<stop offset="0%" stop-color="{}"/>'.format(ACCENT),
        '<stop offset="100%" stop-color="{}" stop-opacity="0"/>'.format(
            ACCENT_DEEP
        ),
        "</linearGradient>",
        "</defs>",
        '<rect width="{w}" height="{h}" rx="14" fill="url(#g)"/>'.format(w=w, h=h),
    ]

    # Faint dot grid, denser toward the right edge.
    for col in range(20, w, 26):
        for row in range(20, h, 26):
            opacity = 0.05 + 0.22 * (col / w)
            parts.append(
                '<circle cx="{x}" cy="{y}" r="1.4" fill="{c}" opacity="{o:.3f}"/>'.format(
                    x=col, y=row, c=ACCENT, o=opacity
                )
            )

    parts.append(
        '<rect x="56" y="62" width="4" height="96" rx="2" fill="{}"/>'.format(ACCENT)
    )
    parts.append(
        '<text x="82" y="106" fill="#ffffff" font-size="44" '
        'font-weight="700" letter-spacing="0.5">{}</text>'.format(
            escape(DISPLAY_NAME)
        )
    )
    parts.append(
        '<text x="84" y="140" fill="{c}" font-size="18" '
        'font-weight="500">{t}</text>'.format(c=ACCENT, t=escape(TAGLINE))
    )

    x = 84
    for chip in CHIPS:
        width = 16 + int(len(chip) * 7.6)
        parts.append(
            '<rect x="{x}" y="176" width="{w}" height="30" rx="15" '
            'fill="#131313" stroke="{s}" stroke-opacity="0.55"/>'.format(
                x=x, w=width, s=ACCENT
            )
        )
        parts.append(
            '<text x="{x}" y="196" fill="{c}" font-size="13" '
            'font-weight="500">{t}</text>'.format(
                x=x + 12, c=TEXT, t=escape(chip)
            )
        )
        x += width + 10

    parts.append(
        '<rect x="82" y="224" width="520" height="2" fill="url(#rule)"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# stats.svg
# --------------------------------------------------------------------------
def stats_card(data):
    w, h = 460, 200
    tiles = [
        ("Total stars", human(data["stars"])),
        ("Contributions", human(data["contributions"])),
        ("Commits (1y)", human(data["commits"])),
        ("Pull requests", human(data["prs"])),
        ("Code reviews", human(data["reviews"])),
        ("Contributed to", human(data["contributed_to"])),
    ]
    parts = [frame(w, h, "{} · GitHub".format(LOGIN))[0]]

    tile_w, tile_h, gap = 138, 40, 8
    left, top = 22, 54
    for index, (label, value) in enumerate(tiles):
        col, row = index % 3, index // 3
        x = left + col * (tile_w + gap)
        y = top + row * (tile_h + gap + 14)
        parts.append(
            '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
            'fill="{p}"/>'.format(x=x, y=y, w=tile_w, h=tile_h + 14, p=PANEL)
        )
        parts.append(
            '<text x="{x}" y="{y}" fill="#ffffff" font-size="20" '
            'font-weight="700">{v}</text>'.format(x=x + 12, y=y + 26, v=value)
        )
        parts.append(
            '<text x="{x}" y="{y}" fill="{m}" font-size="11">{l}</text>'.format(
                x=x + 12, y=y + 44, m=MUTED, l=escape(label)
            )
        )

    parts.append(
        '<text x="22" y="{y}" fill="{m}" font-size="10">'
        "{r} public repos · {f} followers · updated {d}</text>".format(
            y=h - 14,
            m=MUTED,
            r=data["repos"],
            f=data["followers"],
            d=datetime.utcnow().strftime("%Y-%m-%d"),
        )
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# top-langs.svg
# --------------------------------------------------------------------------
def langs_card(data):
    w, h = 400, 200
    ranked = sorted(
        data["languages"].items(), key=lambda kv: kv[1], reverse=True
    )[:6]
    total = sum(size for _, size in ranked) or 1
    # Brightest red for the largest share, fading to maroon down the ranking.
    ramp = ["#ff3b45", "#e51d2a", "#bf1620", "#8f1017", "#630b10", "#3d070a"]

    parts = [frame(w, h, "Most used languages")[0]]

    bar_x, bar_w, bar_y = 22, w - 44, 54
    parts.append(
        '<rect x="{x}" y="{y}" width="{w}" height="10" rx="5" '
        'fill="{p}"/>'.format(x=bar_x, y=bar_y, w=bar_w, p=PANEL)
    )
    parts.append(
        '<clipPath id="barclip"><rect x="{x}" y="{y}" width="{w}" '
        'height="10" rx="5"/></clipPath>'.format(x=bar_x, y=bar_y, w=bar_w)
    )
    offset = 0.0
    for index, (name, size) in enumerate(ranked):
        seg = bar_w * size / total
        parts.append(
            '<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="10" '
            'fill="{c}" clip-path="url(#barclip)"/>'.format(
                x=bar_x + offset, y=bar_y, w=seg, c=ramp[index]
            )
        )
        offset += seg

    row_y = 92
    for index, (name, size) in enumerate(ranked):
        col, row = index % 2, index // 2
        x = 22 + col * 186
        y = row_y + row * 28
        pct = 100.0 * size / total
        parts.append(
            '<circle cx="{x}" cy="{y}" r="5" fill="{c}"/>'.format(
                x=x + 5, y=y - 4, c=ramp[index]
            )
        )
        parts.append(
            '<text x="{x}" y="{y}" fill="{t}" font-size="12.5">{n}</text>'.format(
                x=x + 18, y=y, t=TEXT, n=escape(name)
            )
        )
        parts.append(
            '<text x="{x}" y="{y}" fill="{m}" font-size="12.5" '
            'text-anchor="end">{p:.1f}%</text>'.format(
                x=x + 168, y=y, m=MUTED, p=pct
            )
        )

    parts.append(
        '<text x="22" y="{y}" fill="{m}" font-size="10">'
        "by bytes across owned, non-fork repositories</text>".format(
            y=h - 14, m=MUTED
        )
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# activity.svg
# --------------------------------------------------------------------------
def activity_card(data):
    weeks = data["weeks"]
    cell, gap = 11, 3
    step = cell + gap
    left, top = 34, 52
    w = left + len(weeks) * step + 30
    h = top + 7 * step + 38

    # Quartile thresholds over active days. A linear ramp to the peak would
    # flatten almost every day into the lowest bucket whenever one day spikes.
    active = sorted(
        day["contributionCount"]
        for week in weeks
        for day in week
        if day["contributionCount"] > 0
    )

    def quantile(fraction):
        if not active:
            return 1
        return active[min(len(active) - 1, int(len(active) * fraction))]

    cuts = [quantile(0.25), quantile(0.55), quantile(0.85)]

    def level(count):
        if count == 0:
            return 0
        for index, cut in enumerate(cuts):
            if count <= cut:
                return index + 1
        return 4

    parts = [
        frame(w, h, "Contribution activity · last 12 months")[0],
        '<text x="{x}" y="34" fill="{m}" font-size="11" '
        'text-anchor="end">{n} contributions</text>'.format(
            x=w - 22, m=MUTED, n=data["contributions"]
        ),
    ]

    seen_month = None
    for wi, week in enumerate(weeks):
        first = week[0]["date"]
        month = datetime.strptime(first, "%Y-%m-%d").strftime("%b")
        if month != seen_month and wi < len(weeks) - 2:
            parts.append(
                '<text x="{x}" y="{y}" fill="{m}" font-size="10">{t}</text>'.format(
                    x=left + wi * step, y=top - 8, m=MUTED, t=month
                )
            )
            seen_month = month
        for day in week:
            y = top + day["weekday"] * step
            parts.append(
                '<rect x="{x}" y="{y}" width="{c}" height="{c}" rx="2.5" '
                'fill="{f}"><title>{d}: {n}</title></rect>'.format(
                    x=left + wi * step,
                    y=y,
                    c=cell,
                    f=HEAT[level(day["contributionCount"])],
                    d=day["date"],
                    n=day["contributionCount"],
                )
            )

    for label, weekday in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        parts.append(
            '<text x="6" y="{y}" fill="{m}" font-size="9">{t}</text>'.format(
                y=top + weekday * step + 9, m=MUTED, t=label
            )
        )

    legend_y = top + 7 * step + 18
    swatch_x = w - 24 - 30 - len(HEAT) * step
    parts.append(
        '<text x="{x}" y="{y}" fill="{m}" font-size="10" '
        'text-anchor="end">Less</text>'.format(
            x=swatch_x - 6, y=legend_y + 9, m=MUTED
        )
    )
    for index, color in enumerate(HEAT):
        parts.append(
            '<rect x="{x}" y="{y}" width="{c}" height="{c}" rx="2.5" '
            'fill="{f}"/>'.format(
                x=swatch_x + index * step, y=legend_y, c=cell, f=color
            )
        )
    parts.append(
        '<text x="{x}" y="{y}" fill="{m}" font-size="10">More</text>'.format(
            x=swatch_x + len(HEAT) * step + 4, y=legend_y + 9, m=MUTED
        )
    )
    parts.append("</svg>")
    return "".join(parts)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = fetch()
    except urllib.error.HTTPError as err:
        sys.exit("GitHub API {}: {}".format(err.code, err.read().decode()[:400]))

    write("banner.svg", banner())
    write("stats.svg", stats_card(data))
    write("top-langs.svg", langs_card(data))
    write("activity.svg", activity_card(data))


if __name__ == "__main__":
    main()
