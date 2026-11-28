"""Build the GitHub activity card (light and dark) from the public contribution calendar.

Usage: GH_TOKEN=... python scripts/activity_card.py <login> <out_dir>
Only reads the contribution calendar (daily counts). No repository names are fetched.
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request

QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}"""

THEMES = {
    "dark": dict(
        bg="#131209", border="#313131", text="#F2F2EE", muted="#A3A39C", dim="#76766F", accent="#CAFF45",
        levels=["#1E1D14", "#3B4813", "#6A8A1E", "#9DC92C", "#CAFF45"], shade=(0.62, 0.45),
    ),
    "light": dict(
        bg="#FFFFFF", border="#E3E3DE", text="#0A0A0A", muted="#5C5C58", dim="#8A8A85", accent="#2F6A3A",
        levels=["#EDEDE7", "#CFE2B6", "#93BE74", "#558F48", "#2F6A3A"], shade=(0.86, 0.72),
    ),
}
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
SANS = "Geist, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
EASE = "cubic-bezier(0.22,1,0.36,1)"


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def stats(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if counts[i] == 0:  # today may still be empty
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    best = max(days, key=lambda d: d["contributionCount"])
    active = sum(1 for c in counts if c)
    return dict(current=current, longest=longest, best=best, active=active)


def shade(hex_color, f):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % (round(r * f), round(g * f), round(b * f))


def fmt_date(s):
    d = dt.date.fromisoformat(s)
    return d.strftime("%b ") + str(d.day)


def build(cal, theme):
    t = THEMES[theme]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    st = stats(days)
    peak = max(1, max(d["contributionCount"] for d in days))

    W, H = 1200, 440
    # dimetric axes: weeks run right and slightly down, weekdays run left and down
    wx, wy = 11.6, 4.0
    dx, dy = -6.4, 5.0
    gap = 0.80
    ox, oy = 96, 134
    max_h = 64

    def P(w, d, h=0.0):
        return (ox + w * wx + d * dx, oy + w * wy + d * dy - h)

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
      f'aria-label="GitHub activity for the last 12 months: {cal["totalContributions"]} contributions, '
      f'longest streak {st["longest"]} days.">')
    a("<style>"
      f".u{{opacity:0;transform:translateY(12px);animation:up 900ms {EASE} forwards}}"
      f".c{{opacity:0;transform:translateY(8px);animation:up 700ms {EASE} forwards}}"
      "@keyframes up{to{opacity:1;transform:none}}"
      "@media (prefers-reduced-motion: reduce){*{animation:none!important;opacity:1!important;transform:none!important}}"
      "</style>")
    a(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}"/>')

    # header
    a(f'<g class="u" style="animation-delay:40ms"><circle cx="60" cy="58" r="4" fill="{t["accent"]}"/>'
      f'<text x="74" y="62" font-family="{MONO}" font-size="12" fill="{t["muted"]}" letter-spacing="1.6">'
      f'GITHUB ACTIVITY · LAST 12 MONTHS</text></g>')

    # month labels along the front edge
    seen = set()
    for wi, w in enumerate(weeks):
        first = w["contributionDays"][0]["date"]
        m = first[:7]
        if m in seen or wi > len(weeks) - 3:
            continue
        seen.add(m)
        if wi == 0 and dt.date.fromisoformat(first).day > 7:
            continue
        x, y = P(wi, 7.9)
        a(f'<text class="c" style="animation-delay:{200 + wi * 10}ms" x="{x:.1f}" y="{y + 12:.1f}" '
          f'font-family="{MONO}" font-size="10" fill="{t["dim"]}">{dt.date.fromisoformat(first).strftime("%b")}</text>')

    # prisms, back to front
    cells = []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = dt.date.fromisoformat(d["date"]).isoweekday() % 7  # Sunday=0
            cells.append((wi, wd, d))
    cells.sort(key=lambda c: (c[0] + c[1], c[1]))

    by_week = {}
    for wi, wd, d in cells:
        c = d["contributionCount"]
        lvl = LEVEL.get(d["contributionLevel"], 0)
        h = 1.6 if c == 0 else 4 + math.sqrt(c / peak) * max_h
        top = t["levels"][lvl]
        left, right = shade(top, t["shade"][0]), shade(top, t["shade"][1])
        g0, g1 = (1 - gap) / 2, (1 + gap) / 2
        A = (wi + g0, wd + g0)
        B = (wi + g1, wd + g0)
        C = (wi + g1, wd + g1)
        D = (wi + g0, wd + g1)
        pt = lambda p, hh: "%.1f,%.1f" % P(p[0], p[1], hh)
        poly = []
        # front face (weekday + 1 edge) and right face (week + 1 edge)
        poly.append(f'<polygon points="{pt(D,0)} {pt(C,0)} {pt(C,h)} {pt(D,h)}" fill="{left}"/>')
        poly.append(f'<polygon points="{pt(B,0)} {pt(C,0)} {pt(C,h)} {pt(B,h)}" fill="{right}"/>')
        poly.append(f'<polygon points="{pt(A,h)} {pt(B,h)} {pt(C,h)} {pt(D,h)}" fill="{top}"/>')
        by_week.setdefault(wi + wd, []).append("".join(poly))
    for k in sorted(by_week):
        a(f'<g class="c" style="animation-delay:{120 + k * 14}ms">{"".join(by_week[k])}</g>')

    # stats column
    sx = 812
    a(f'<line x1="{sx - 36}" y1="96" x2="{sx - 36}" y2="{H - 48}" stroke="{t["border"]}"/>')
    unit = lambda n, u: f'{n}<tspan font-size="20" font-weight="500" fill="{t["muted"]}" letter-spacing="0"> {u}</tspan>'
    items = [
        (f'{cal["totalContributions"]:,}', "contributions"),
        (f'{st["active"]}', "active days"),
        (unit(st["longest"], "days"), "longest streak"),
        (f'{st["best"]["contributionCount"]}', f'best day, {fmt_date(st["best"]["date"])}'),
    ]
    for i, (num, label) in enumerate(items):
        col, row = i % 2, i // 2
        x = sx + col * 176
        y = 158 + row * 112
        a(f'<g class="u" style="animation-delay:{260 + i * 90}ms">'
          f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="44" font-weight="600" fill="{t["text"]}" '
          f'letter-spacing="-1.2">{num}</text>'
          f'<text x="{x}" y="{y + 26}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{label}</text></g>')

    # current streak note and legend
    note = f'{st["current"]} day current streak' if st["current"] else "no streak today yet"
    a(f'<g class="u" style="animation-delay:700ms"><circle cx="{sx + 4}" cy="{H - 96}" r="3" fill="{t["accent"]}"/>'
      f'<text x="{sx + 14}" y="{H - 92}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{note}</text></g>')
    lx, ly = sx, H - 60
    a(f'<g class="u" style="animation-delay:760ms"><text x="{lx}" y="{ly + 9}" font-family="{MONO}" font-size="10" '
      f'fill="{t["dim"]}">less</text>')
    for i, col in enumerate(t["levels"]):
        a(f'<rect x="{lx + 34 + i * 15}" y="{ly}" width="11" height="11" rx="2.5" fill="{col}"/>')
    a(f'<text x="{lx + 34 + 5 * 15 + 4}" y="{ly + 9}" font-family="{MONO}" font-size="10" fill="{t["dim"]}">more</text></g>')

    a("</svg>")
    return "\n".join(out)


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    cal = fetch(login, os.environ["GH_TOKEN"])
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(out_dir, f"activity-{theme}.svg"), "w") as f:
            f.write(build(cal, theme))


if __name__ == "__main__":
    main()
