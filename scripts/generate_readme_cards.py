#!/usr/bin/env python3
"""Generate the SVG cards embedded in the profile README.

Everything under profile/ is produced by this script, so the README never
hot-links a shared rendering service that can rate-limit or go down. The star
counts in the README's Open Source Contributions section are rewritten here
too, for the same reason: a number in the text cannot be rate-limited, and
this keeps it from going stale.

Usage:
    GH_TOKEN=$(gh auth token) python3 scripts/generate_readme_cards.py

Only the standard library is used, so there is nothing to install.
"""

import json
import os
import re
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
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "profile"
README = ROOT / "README.md"

# One palette for every card in the README, built to sit on GitHub's light
# canvas and its dark one without a second set of files.
#
# Nothing here is an opaque ground. Cards, tiles and rules are a neutral grey
# at low alpha, so each tone is a relation to whatever is behind it rather
# than a fixed colour: NEUTRAL at 0.10 lands on #f0f0f0 over white and
# #1b1e24 over #0d1117, the same slight lift either way.
#
# The text tones are the compromise. No single colour clears 4.5:1 against
# #ffffff and #0d1117 at once -- the best any colour manages on both is
# 4.35:1, at a luminance near 0.19 -- so these sit in the band that clears
# 3:1 on white, on dark, and on dark dimmed, and hierarchy comes from size
# and weight instead of from brightness.
NEUTRAL = "#808080"   # panels and rules, never without one of the alphas
CARD_OP = "0.05"      # the card's own lift off the page
PANEL_OP = "0.10"     # tiles, bar tracks, empty heatmap cells
BORDER_OP = "0.30"
TEXT = "#747474"      # 4.67:1 on white, 4.05:1 on dark, 3.18:1 on dimmed
MUTED = "#929292"     # 3.11:1 on white, 6.08:1 on dark, 4.78:1 on dimmed
ACCENT = "#e51d2a"    # Garena red, already 4.62:1 and 4.09:1 unchanged
ACCENT_DEEP = "#b3202b"

# Heatmap and language ramps are one red at rising alpha rather than a ladder
# of fixed colours. A ladder can only be built toward one ground: the old one
# ran #161616 to #ff3b45, which was a ramp on black and a row of near-blacks
# on white. As alpha it reads pink-to-red on the light canvas and dark-red-to
# -red on the dark one.
HEAT_OP = [None, 0.28, 0.48, 0.72, 1.0]   # None: the empty-day neutral
LANG_OP = [1.0, 0.82, 0.66, 0.52, 0.42, 0.34]

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
      privacy: PUBLIC
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
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


def post(token, query, variables=None):
    """Raw GraphQL response, errors included; the caller decides how strict."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
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
        return json.loads(resp.read().decode())


def graphql(token, cursor=None):
    body = post(token, QUERY, {"login": LOGIN, "cursor": cursor})
    if "errors" in body:
        raise RuntimeError(json.dumps(body["errors"], indent=2))
    return body["data"]["user"]


def auth_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("set GH_TOKEN (locally: GH_TOKEN=$(gh auth token))")
    return token


def fetch():
    # The repositories query is pinned to privacy: PUBLIC on purpose. Without
    # it the card depends on who ran it: a PAT carrying the `repo` scope folds
    # private repositories into the star total and the language breakdown,
    # while the Actions GITHUB_TOKEN sees only public ones, so the same script
    # produced two different cards. Public-only is also the honest figure for
    # a page whose whole audience can see exactly those repositories.
    token = auth_token()
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
        # Private contributions are counted because this profile publishes
        # them: both a PAT and the Actions token report the same figure, and
        # it is what GitHub's own contribution graph shows for this user.
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


# --------------------------------------------------------------------------
# Open Source Contributions star counts
# --------------------------------------------------------------------------
HEADING = "## Open Source Contributions"

# One entry of that section: the repository link, then the star count this
# function keeps current. Anchoring on the backticked count is what stops the
# pattern from touching any other link in the README, including the pull
# request link that sits on the same line as one of the entries.
ENTRY = re.compile(
    r"\(https://github\.com/([\w.-]+)/([\w.-]+)\) `[\d.]+k?\u2605`"
)


def compact(n):
    """Stars the way the section writes them: 940, 1.4k, 12.6k, 73.3k.

    Not human(), which keeps counts under 10k exact. A list of ten
    repositories reads better with every line in the same k-form.
    """
    if n < 1000:
        return str(n)
    return "{:.1f}k".format(n / 1000).replace(".0k", "k")


def repo_stars(token, repos):
    """Current stargazer counts for every repository named in the section.

    One request with an alias per repository. A repository that was renamed,
    deleted or made private answers null, and GraphQL reports that alongside
    the data for the others; those are skipped so one dead link cannot fail
    the daily run. Their count simply stays as last written.
    """
    fields = " ".join(
        'r{i}: repository(owner: "{o}", name: "{n}") {{ stargazerCount }}'.format(
            i=index, o=owner, n=name
        )
        for index, (owner, name) in enumerate(repos)
    )
    data = post(token, "query {" + fields + "}").get("data") or {}
    counts = {}
    for index, (owner, name) in enumerate(repos):
        node = data.get("r{}".format(index))
        if node:
            counts["{}/{}".format(owner, name)] = node["stargazerCount"]
    return counts


def refresh_readme_stars(token):
    """Rewrite the star counts in the Open Source Contributions section."""
    text = README.read_text(encoding="utf-8")
    start = text.find(HEADING)
    if start < 0:
        print("skipped README stars:", HEADING, "is gone")
        return
    end = text.find("\n## ", start + len(HEADING))
    section = text[start:end if end > 0 else len(text)]

    repos = [(m.group(1), m.group(2)) for m in ENTRY.finditer(section)]
    if not repos:
        print("skipped README stars: no entries matched")
        return
    counts = repo_stars(token, repos)

    def replace(match):
        owner, name = match.group(1), match.group(2)
        stars = counts.get("{}/{}".format(owner, name))
        if stars is None:
            return match.group(0)
        return "(https://github.com/{}/{}) `{}\u2605`".format(
            owner, name, compact(stars)
        )

    updated = ENTRY.sub(replace, section)
    if updated == section:
        print("README stars unchanged")
        return
    README.write_text(text[:start] + updated + text[start + len(section):],
                      encoding="utf-8")
    print("wrote README.md ({} entries)".format(len(repos)))


def wash(opacity, color=NEUTRAL):
    """A fill that reads the same on either canvas: one colour, low alpha."""
    return 'fill="{c}" fill-opacity="{o}"'.format(c=color, o=opacity)


def heat(level):
    """Fill for one heatmap cell; level 0 is a day with no contributions."""
    if level == 0:
        return wash(PANEL_OP)
    return wash("{:g}".format(HEAT_OP[level]), ACCENT)


def frame(width, height, title=None):
    """Card background plus optional title; returns (svg_open, y_after_title)."""
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" role="img" font-family="{f}">'
        '<rect width="{w}" height="{h}" rx="10" {bg} '
        'stroke="{n}" stroke-opacity="{bo}" stroke-width="1"/>'
    ).format(w=width, h=height, f=FONT, bg=wash(CARD_OP), n=NEUTRAL,
             bo=BORDER_OP)
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
        '<stop offset="0%" stop-color="{}" stop-opacity="0.05"/>'.format(NEUTRAL),
        '<stop offset="60%" stop-color="{}" stop-opacity="0.07"/>'.format(ACCENT),
        '<stop offset="100%" stop-color="{}" stop-opacity="0.14"/>'.format(ACCENT),
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
        '<text x="82" y="106" fill="{c}" font-size="44" '
        'font-weight="700" letter-spacing="0.5">{t}</text>'.format(
            c=ACCENT, t=escape(DISPLAY_NAME)
        )
    )
    parts.append(
        '<text x="84" y="140" fill="{c}" font-size="18" '
        'font-weight="500">{t}</text>'.format(c=TEXT, t=escape(TAGLINE))
    )

    x = 84
    for chip in CHIPS:
        width = 16 + int(len(chip) * 7.6)
        parts.append(
            '<rect x="{x}" y="176" width="{w}" height="30" rx="15" '
            '{bg} stroke="{s}" stroke-opacity="0.55"/>'.format(
                x=x, w=width, bg=wash(PANEL_OP), s=ACCENT
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
# badge-stars.svg
# --------------------------------------------------------------------------
# The header badge row is shields.io, and shields has no endpoint for a user's
# star total, so this one is drawn here to match its neighbours exactly rather
# than approximately. Geometry is copied from a real flat-square badge:
# height 20, square corners, 5px padding each side of a segment, a 14px logo
# at x=5 with a 3px gap, and Verdana 11 text pinned with textLength so the
# result does not drift with whatever font the viewer actually has. Verdana
# digits are uniform at 7.0px; "total stars" measures 55.0px.
LABEL = "total stars"
LABEL_W = 55.0
DIGIT_W = 7.0

# Simple Icons' star glyph, on their 24x24 grid, scaled to the 14px logo box.
STAR = (
    "M12 .587l3.668 7.431 8.332 1.151-6.064 5.828 1.48 8.279L12 18.897"
    "l-7.416 4.379 1.48-8.279L0 9.169l8.332-1.151z"
)


def stars_badge(data):
    value = str(data["stars"])
    left = 5 + 14 + 3 + LABEL_W + 5
    value_w = DIGIT_W * len(value)
    right = 5 + value_w + 5
    width = left + right

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="20" '
        'role="img" aria-label="total stars: {v}">'
        "<title>total stars: {v}</title>"
        '<g shape-rendering="crispEdges">'
        '<rect width="{l:g}" height="20" fill="#0a0a0a"/>'
        '<rect x="{l:g}" width="{r:g}" height="20" fill="{a}"/>'
        "</g>"
        '<g transform="translate(5,3) scale(0.58333)" fill="#ffffff">'
        '<path d="{star}"/></g>'
        '<g fill="#fff" text-anchor="middle" '
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'text-rendering="geometricPrecision" font-size="110">'
        '<text x="{lx:g}" y="140" textLength="{lw:g}" '
        'transform="scale(.1)">{label}</text>'
        '<text x="{vx:g}" y="140" textLength="{vw:g}" '
        'transform="scale(.1)">{v}</text>'
        "</g></svg>"
    ).format(
        w=width,
        l=left,
        r=right,
        a=ACCENT,
        star=STAR,
        v=value,
        label=escape(LABEL),
        lx=(5 + 14 + 3 + LABEL_W / 2.0) * 10,
        lw=LABEL_W * 10,
        vx=(left + right / 2.0) * 10,
        vw=value_w * 10,
    )


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
            '{p}/>'.format(x=x, y=y, w=tile_w, h=tile_h + 14,
                           p=wash(PANEL_OP))
        )
        parts.append(
            '<text x="{x}" y="{y}" fill="{c}" font-size="20" '
            'font-weight="700">{v}</text>'.format(
                x=x + 12, y=y + 26, c=TEXT, v=value
            )
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
    # One red fading down the ranking by alpha. The maroons this replaced
    # were only a fade against black; on white they read as six solid reds.
    ramp = [wash("{:g}".format(a), ACCENT) for a in LANG_OP]

    parts = [frame(w, h, "Most used languages")[0]]

    bar_x, bar_w, bar_y = 22, w - 44, 54
    parts.append(
        '<rect x="{x}" y="{y}" width="{w}" height="10" rx="5" '
        '{p}/>'.format(x=bar_x, y=bar_y, w=bar_w, p=wash(PANEL_OP))
    )
    parts.append(
        '<clipPath id="barclip"><rect x="{x}" y="{y}" width="{w}" '
        'height="10" rx="5"/></clipPath>'.format(x=bar_x, y=bar_y, w=bar_w)
    )
    # Segment edges come from a cumulative integer sum rounded once, not from
    # `offset += seg` in a loop: accumulated float error made byte-identical
    # input render to different coordinates, which committed a "changed" card
    # every day.
    cumulative = 0
    edge = 0.0
    for index, (name, size) in enumerate(ranked):
        cumulative += size
        next_edge = round(bar_w * cumulative / total, 1)
        parts.append(
            '<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="10" '
            '{c} clip-path="url(#barclip)"/>'.format(
                x=bar_x + edge, y=bar_y, w=next_edge - edge, c=ramp[index]
            )
        )
        edge = next_edge

    row_y = 92
    for index, (name, size) in enumerate(ranked):
        col, row = index % 2, index // 2
        x = 22 + col * 186
        y = row_y + row * 28
        pct = 100.0 * size / total
        parts.append(
            '<circle cx="{x}" cy="{y}" r="5" {c}/>'.format(
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
                '{f}><title>{d}: {n}</title></rect>'.format(
                    x=left + wi * step,
                    y=y,
                    c=cell,
                    f=heat(level(day["contributionCount"])),
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
    swatch_x = w - 24 - 30 - len(HEAT_OP) * step
    parts.append(
        '<text x="{x}" y="{y}" fill="{m}" font-size="10" '
        'text-anchor="end">Less</text>'.format(
            x=swatch_x - 6, y=legend_y + 9, m=MUTED
        )
    )
    for index in range(len(HEAT_OP)):
        parts.append(
            '<rect x="{x}" y="{y}" width="{c}" height="{c}" rx="2.5" '
            '{f}/>'.format(
                x=swatch_x + index * step, y=legend_y, c=cell, f=heat(index)
            )
        )
    parts.append(
        '<text x="{x}" y="{y}" fill="{m}" font-size="10">More</text>'.format(
            x=swatch_x + len(HEAT_OP) * step + 4, y=legend_y + 9, m=MUTED
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
    write("badge-stars.svg", stars_badge(data))
    write("stats.svg", stats_card(data))
    write("top-langs.svg", langs_card(data))
    write("activity.svg", activity_card(data))

    # The cards are on disk by now. A hiccup on this one extra query should
    # not cost the day's refresh, so it never takes the run down with it.
    try:
        refresh_readme_stars(auth_token())
    # OSError covers urllib's URLError and HTTPError as well as the write.
    except (OSError, RuntimeError, KeyError) as err:
        print("README stars skipped:", err)


if __name__ == "__main__":
    main()
