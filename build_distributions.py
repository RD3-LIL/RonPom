"""Build a Distributions page for the College Ratings site (RonPom).

Reads data/players_2026_27.json (all 8,015 players) and
data/sharp_2026_27.json (1,411 qualified), writes
distributions.html at the repo root.

The page is static with vanilla JS only, no external libraries.
Pick a stat and it builds a histogram of every player with a
value for that stat, with a smooth Gaussian kernel density line
that follows the shape of the actual data, a mean line, hover
or tap a bar to see the players in that bin (linked to their
profile when one exists), and search a name to mark their spot
on the distribution.

Only the 354 players on top-25 teams have a profile page under
players/, so the bin lists link a player only when their slug
is in that set. The page says so.

No network, stdlib only.
"""

import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

STATS = [
    # key, label, decimals, is_percent, description
    ("rpr", "RPR", 2, False,
     "Our single-number rating for how much a player helps his team."),
    ("ppg", "PPG", 1, False, "Points scored per game."),
    ("rpg", "RPG", 1, False, "Rebounds grabbed per game."),
    ("apg", "APG", 1, False, "Assists per game."),
    ("ortg", "ORtg", 1, False,
     "Points the player produces per 100 possessions he uses."),
    ("ts", "TS%", 1, True,
     "Points scored per shooting attempt, counting twos, threes, and free throws together."),
    ("sharp", "SHARP", 2, False,
     "Extra points per game from threes and free throws above league average."),
    ("fg", "FG%", 1, True, "Share of all field goal attempts made."),
    ("fg3", "3P%", 1, True, "Share of three point attempts made."),
    ("ft", "FT%", 1, True, "Share of free throw attempts made."),
    ("efg", "eFG%", 1, True,
     "Field goal percentage adjusted so a three counts more than a two, since it is worth more points."),
    ("spg", "SPG", 1, False, "Steals per game."),
    ("bpg", "BPG", 1, False, "Blocks per game."),
    ("stlblk", "STL+BLK", 1, False, "Steals plus blocks per game."),
    ("dreb", "DREB", 1, False, "Defensive rebounds per game."),
]


def team_slug(name):
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_name.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def player_slug(name, athlete_id, team):
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_name.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"{s}-{athlete_id}-{team_slug(team)}"


def load_site_css():
    try:
        src = (HERE / "build_page.py").read_text()
        start = src.index('CSS = """') + len('CSS = """')
        end = src.index('"""', start)
        return src[start:end]
    except (OSError, ValueError):
        return ("body { font-family: sans-serif; max-width: 960px; "
                "margin: 0 auto; padding: 24px 16px 64px; "
                "line-height: 1.5; }")


def _round(v):
    if v is None:
        return None
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def main():
    players = json.loads((DATA / "players_2026_27.json").read_text())["players"]
    sharp = json.loads((DATA / "sharp_2026_27.json").read_text())["players"]
    sharp_by_key = {(p["athlete_id"], p["team"]): p["sharp"] for p in sharp}

    # Slugs of the profile pages that actually exist on disk.
    profile_slugs = {p.stem for p in (HERE / "players").glob("*.html")
                     if p.stem != "index"}

    rows = []
    for p in players:
        key = (p["athlete_id"], p["team"])
        slug = player_slug(p["name"], p["athlete_id"], p["team"])
        rows.append([
            p["name"],
            p["team"],
            slug if slug in profile_slugs else None,
            _round(p.get("ratings", {}).get("rpr")),
            _round(p.get("per_game", {}).get("pts")),
            _round(p.get("per_game", {}).get("reb")),
            _round(p.get("per_game", {}).get("ast")),
            _round(p.get("ratings", {}).get("ortg")),
            _round(100 * p["shooting"]["ts_pct"]) if p.get("shooting", {}).get("ts_pct") is not None else None,
            _round(sharp_by_key.get(key)),
            _round(100 * p["shooting"]["fg_pct"]) if p.get("shooting", {}).get("fg_pct") is not None else None,
            _round(100 * p["shooting"]["fg3_pct"]) if p.get("shooting", {}).get("fg3_pct") is not None else None,
            _round(100 * p["shooting"]["ft_pct"]) if p.get("shooting", {}).get("ft_pct") is not None else None,
            _round(100 * p["shooting"]["efg_pct"]) if p.get("shooting", {}).get("efg_pct") is not None else None,
            _round(p.get("per_game", {}).get("stl")),
            _round(p.get("per_game", {}).get("blk")),
            _round(p.get("per_game", {}).get("stl") + p.get("per_game", {}).get("blk")) if p.get("per_game", {}).get("stl") is not None and p.get("per_game", {}).get("blk") is not None else None,
            _round(p.get("per_game", {}).get("dreb")),
        ])

    counts = {}
    for i, (key, label, _, _, _) in enumerate(STATS):
        counts[label] = sum(1 for r in rows if r[3 + i] is not None)
    print("players:", len(rows), "counts:", counts)

    stats_js = json.dumps([
        {"key": key, "label": label, "dec": dec, "pct": pct, "desc": desc}
        for key, label, dec, pct, desc in STATS
    ])
    data_js = json.dumps(rows, separators=(",", ":"), ensure_ascii=False)

    css = load_site_css()
    extra_css = """
.stat-buttons { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.stat-buttons button { padding: 8px 14px; font-size: 15px; border: 1px solid #d0d7de; border-radius: 999px; background: #f6f8fa; cursor: pointer; }
.stat-buttons button.active { background: #0969da; color: #fff; border-color: #0969da; }
#chart { width: 100%; height: auto; display: block; }
#chart .bar { fill: #38bdf8; cursor: pointer; }
#chart .bar:hover, #chart .bar.sel { fill: #1d4ed8; }
#chart .kde { fill: none; stroke: #1d4ed8; stroke-width: 2; }
#chart .mean-line { stroke: #656d76; stroke-dasharray: 5 4; stroke-width: 1.5; }
#chart .marker-line { stroke: #f59e0b; stroke-width: 2; }
#chart .axis { font-size: 12px; fill: #656d76; }
#chart .axis-label { font-size: 13px; fill: #1f2328; }
.search-wrap { position: relative; max-width: 420px; margin: 12px 0; }
.search-wrap input { width: 100%; padding: 8px 10px; font-size: 15px; border: 1px solid #d0d7de; border-radius: 6px; box-sizing: border-box; }
.search-results { position: absolute; left: 0; right: 0; top: 100%; background: #fff; border: 1px solid #d0d7de; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.12); z-index: 10; max-height: 240px; overflow-y: auto; }
.search-results div { padding: 8px 10px; cursor: pointer; }
.search-results div:hover { background: #eaeef2; }
#bin-panel { margin-top: 16px; }
#bin-panel ul { list-style: none; padding: 0; }
#bin-panel li { padding: 4px 0; border-bottom: 1px solid #eaeef2; }
button.clear { margin-left: 8px; padding: 6px 12px; font-size: 14px; cursor: pointer; }
"""

    html = HTML_TEMPLATE.replace("__SITE_CSS__", css)
    html = html.replace("__EXTRA_CSS__", extra_css)
    html = html.replace("__STATS_JSON__", stats_js)
    html = html.replace("__DATA_JSON__", data_js)
    html = html.replace("__PLAYER_COUNT__", str(len(rows)))
    (HERE / "distributions.html").write_text(html)
    print(f"wrote distributions.html, {(HERE / 'distributions.html').stat().st_size} bytes")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Distributions | College Ratings</title>
<style>
__SITE_CSS__
__EXTRA_CSS__
</style>
</head>
<body>
<h1>College Ratings</h1>
<nav class="topnav">
<a href="index.html">&larr; College Ratings</a>
<a href="players/">Top-25 players</a>
</nav>

<h2>Distributions</h2>
<p>Pick a stat and see how all __PLAYER_COUNT__ players are spread across it.
The bars are a histogram of the real players, and the dark line is a smooth
curve that follows the shape of the data. The dashed grey line is the mean.</p>
<p>These distributions cover every player with a value for that stat, not just
the top-25 teams. Only players on top-25 teams have a profile page, so a
player without a profile shows as plain text in the bin lists.</p>

<div class="stat-buttons" id="stat-buttons"></div>
<p id="stat-desc"></p>

<div class="search-wrap">
<input id="search" type="text" placeholder="Search a player, then see where they sit" autocomplete="off">
<div class="search-results" id="search-results" style="display:none"></div>
</div>
<div id="marker-info"></div>

<svg id="chart" viewBox="0 0 900 400" role="img" aria-label="Distribution chart"></svg>

<div id="summary"></div>
<div id="bin-panel"><p>Hover or tap a bar to see the players in that range.</p></div>

<script>
var STATS = __STATS_JSON__;
var DATA = __DATA_JSON__;
var COLS = ["rpr","ppg","rpg","apg","ortg","ts","sharp","fg","fg3","ft","efg","spg","bpg","stlblk","dreb"];
var current = "ppg";
var selectedBin = -1;
var marker = null;

var W = 900, H = 400, ML = 56, MR = 24, MT = 24, MB = 44;
var PW = W - ML - MR, PH = H - MT - MB;

function fmt(v, stat) {
  if (v === null || v === undefined) return "-";
  return stat.pct ? v.toFixed(stat.dec) + "%" : v.toFixed(stat.dec);
}

function statIndex(key) { return COLS.indexOf(key); }

function valuesFor(key) {
  var i = 3 + statIndex(key);
  var out = [];
  for (var r = 0; r < DATA.length; r++) {
    var v = DATA[r][i];
    if (v !== null) out.push({name: DATA[r][0], team: DATA[r][1], slug: DATA[r][2], v: v});
  }
  return out;
}

function quantile(sorted, q) {
  if (!sorted.length) return 0;
  var pos = (sorted.length - 1) * q;
  var base = Math.floor(pos), rest = pos - base;
  return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base];
}

function kde(values, xs, h, lo, hi) {
  var n = values.length;
  var out = [];
  for (var j = 0; j < xs.length; j++) {
    var x = xs[j], s = 0;
    for (var i = 0; i < n; i++) {
      var u = (x - values[i]) / h;
      if (u > -4 && u < 4) s += Math.exp(-0.5 * u * u);
    }
    out.push(s / (n * h * Math.sqrt(2 * Math.PI)));
  }
  return out;
}

function svgEl(tag, attrs) {
  var el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (var k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function render() {
  var stat = STATS.filter(function (s) { return s.key === current; })[0];
  var vals = valuesFor(current);
  var nums = vals.map(function (d) { return d.v; }).sort(function (a, b) { return a - b; });
  var n = nums.length;
  // Chart range is capped at the 1st and 99th percentiles so a handful of
  // tiny-sample outliers (ORtg 300, TS% 150) do not squash the bulk of
  // players into a spike. Summary, top 5, and ranks still use all players.
  var pLo = quantile(nums, 0.01), pHi = quantile(nums, 0.99);
  var aboveHi = nums.filter(function (v) { return v > pHi; }).length;
  var belowLo = nums.filter(function (v) { return v < pLo; }).length;
  var lo = pLo, hi = pHi;
  var pad = (hi - lo) * 0.02 || 1;
  lo -= pad; hi += pad;
  if (nums[0] >= 0) lo = Math.max(0, lo);
  var mean = nums.reduce(function (a, b) { return a + b; }, 0) / n;
  var median = quantile(nums, 0.5);
  var sd = Math.sqrt(nums.reduce(function (a, b) { return a + (b - mean) * (b - mean); }, 0) / n);
  var iqr = quantile(nums, 0.75) - quantile(nums, 0.25);
  var h = 0.9 * Math.min(sd, iqr / 1.34 || sd) * Math.pow(n, -0.2);
  if (!h || h <= 0) h = (hi - lo) / 20;

  var NB = 20, bw = (hi - lo) / NB;
  var bins = [];
  for (var b = 0; b < NB; b++) bins.push({lo: lo + b * bw, hi: lo + (b + 1) * bw, items: []});
  vals.forEach(function (d) {
    var idx = Math.max(0, Math.min(NB - 1, Math.floor((d.v - lo) / bw)));
    bins[idx].items.push(d);
  });
  bins.forEach(function (bin) { bin.items.sort(function (a, b) { return b.v - a.v; }); });
  var maxCount = Math.max.apply(null, bins.map(function (bin) { return bin.items.length; }));

  var xs = [];
  for (var j = 0; j <= 100; j++) xs.push(lo + (hi - lo) * j / 100);
  var dens = kde(nums, xs, h, lo, hi);
  var kdeCounts = dens.map(function (d) { return d * n * bw; });
  var maxKde = Math.max.apply(null, kdeCounts);
  var yMax = Math.max(maxCount, maxKde) * 1.08;

  function X(v) { return ML + (v - lo) / (hi - lo) * PW; }
  function Y(c) { return MT + PH - c / yMax * PH; }

  var svg = document.getElementById("chart");
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  // Y axis ticks.
  var yStep = Math.pow(10, Math.floor(Math.log10(yMax / 4) || 0));
  if (yMax / yStep > 6) yStep *= 2;
  for (var yv = 0; yv <= yMax; yv += yStep) {
    svg.appendChild(svgEl("line", {x1: ML, y1: Y(yv), x2: ML + PW, y2: Y(yv), stroke: "#eaeef2"}));
    var t = svgEl("text", {x: ML - 8, y: Y(yv) + 4, "text-anchor": "end", "class": "axis"});
    t.textContent = yv;
    svg.appendChild(t);
  }
  var yLab = svgEl("text", {x: 14, y: MT + PH / 2, "class": "axis-label", transform: "rotate(-90 14 " + (MT + PH / 2) + ")", "text-anchor": "middle"});
  yLab.textContent = "Players";
  svg.appendChild(yLab);

  // X axis ticks.
  for (var tx = 0; tx <= 5; tx++) {
    var xv = lo + (hi - lo) * tx / 5;
    var tt = svgEl("text", {x: X(xv), y: MT + PH + 22, "text-anchor": "middle", "class": "axis"});
    tt.textContent = fmt(xv, stat);
    svg.appendChild(tt);
  }
  var xLab = svgEl("text", {x: ML + PW / 2, y: H - 4, "class": "axis-label", "text-anchor": "middle"});
  xLab.textContent = stat.label;
  svg.appendChild(xLab);

  // Bars.
  bins.forEach(function (bin, bi) {
    var rect = svgEl("rect", {
      x: X(bin.lo) + 1, y: Y(bin.items.length),
      width: Math.max(1, X(bin.hi) - X(bin.lo) - 2),
      height: MT + PH - Y(bin.items.length),
      "class": "bar" + (bi === selectedBin ? " sel" : "")
    });
    rect.addEventListener("mouseover", function () { showBin(bi, bins, stat); });
    rect.addEventListener("click", function () { selectedBin = bi; showBin(bi, bins, stat); render(); });
    svg.appendChild(rect);
  });

  // KDE line.
  var d = "";
  xs.forEach(function (x, j) {
    d += (j === 0 ? "M" : "L") + X(x).toFixed(1) + "," + Y(kdeCounts[j]).toFixed(1);
  });
  svg.appendChild(svgEl("path", {d: d, "class": "kde"}));

  // Mean line.
  svg.appendChild(svgEl("line", {x1: X(mean), y1: MT, x2: X(mean), y2: MT + PH, "class": "mean-line"}));
  var mt = svgEl("text", {x: Math.min(X(mean) + 6, ML + PW - 90), y: MT + 12, "class": "axis"});
  mt.textContent = "Mean " + fmt(mean, stat);
  svg.appendChild(mt);

  // Search marker. Recompute the value from the player's row on every
  // render, so switching stats after searching shows the new stat's value
  // instead of the stale value captured when the player was picked.
  var markerInfo = document.getElementById("marker-info");
  if (marker) {
    var mv = DATA[marker.rowIndex][3 + statIndex(current)];
    if (mv === null) {
      markerInfo.innerHTML = "<p><strong>" + esc(marker.name) + "</strong> has no value for " + stat.label + " (for example, SHARP needs 5 games and 20 minutes per game).</p><button class='clear' id='clear-marker'>Clear</button>";
    } else {
      var rank = 1 + nums.filter(function (v) { return v > mv; }).length;
      var kx = Math.min(Math.max(X(mv), ML), ML + PW), ky = Y(kdeAt(mv, nums, h) * n * bw);
      svg.appendChild(svgEl("line", {x1: kx, y1: MT, x2: kx, y2: MT + PH, "class": "marker-line"}));
      svg.appendChild(svgEl("circle", {cx: kx, cy: ky, r: 6, fill: "#f59e0b", stroke: "#fff", "stroke-width": 2}));
      var label = svgEl("text", {x: (kx > ML + PW - 220 ? kx - 8 : kx + 8), y: Math.max(ky - 10, MT + 12), "class": "axis-label", fill: "#b45309", "text-anchor": (kx > ML + PW - 220 ? "end" : "start")});
      label.textContent = marker.name + " " + fmt(mv, stat) + " (#" + rank + " of " + n + ")";
      svg.appendChild(label);
      markerInfo.innerHTML = "<p><strong>" + esc(marker.name) + "</strong> (" + esc(marker.team) + "): " + stat.label + " " + fmt(mv, stat) + ", rank #" + rank + " of " + n + ".</p><button class='clear' id='clear-marker'>Clear</button>";
    }
    var cb = document.getElementById("clear-marker");
    if (cb) cb.addEventListener("click", function () { marker = null; markerInfo.innerHTML = ""; document.getElementById("search").value = ""; render(); });
  } else {
    markerInfo.innerHTML = "";
  }

  // Summary.
  var top5 = vals.slice().sort(function (a, b) { return b.v - a.v; }).slice(0, 5);
  var topHtml = top5.map(function (d, i) {
    var nm = d.slug ? '<a href="players/' + d.slug + '.html">' + esc(d.name) + '</a>' : esc(d.name);
    return "<li>" + (i + 1) + ". " + nm + " (" + esc(d.team) + ") " + fmt(d.v, stat) + "</li>";
  }).join("");
  document.getElementById("summary").innerHTML =
    "<p><strong>" + stat.label + ":</strong> " + n + " players &middot; mean " + fmt(mean, stat) +
    " &middot; median " + fmt(median, stat) + " &middot; min " + fmt(nums[0], stat) +
    " &middot; max " + fmt(nums[n - 1], stat) + "</p>" +
    "<p>" + esc(stat.desc) + "</p>" +
    ((aboveHi || belowLo) ? "<p>Chart shows the 1st to 99th percentile (" + fmt(pLo, stat) + " to " + fmt(pHi, stat) + "); " + (belowLo + aboveHi) + " players outside that range are grouped in the end bins.</p>" : "") +
    "<ol>" + topHtml + "</ol>";

  document.getElementById("stat-desc").textContent = stat.label + ": " + stat.desc;
  document.querySelectorAll("#stat-buttons button").forEach(function (btn) {
    btn.classList.toggle("active", btn.dataset.key === current);
  });

  function kdeAt(x, values, hh) {
    var s = 0;
    for (var i = 0; i < values.length; i++) {
      var u = (x - values[i]) / hh;
      if (u > -4 && u < 4) s += Math.exp(-0.5 * u * u);
    }
    return s / (values.length * hh * Math.sqrt(2 * Math.PI));
  }

  function showBin(bi, binsArr, st) {
    selectedBin = bi;
    var bin = binsArr[bi];
    var shown = bin.items.slice(0, 100);
    var rows = shown.map(function (d) {
      var nm = d.slug ? '<a href="players/' + d.slug + '.html">' + esc(d.name) + '</a>' : esc(d.name);
      return "<li>" + nm + " (" + esc(d.team) + ") " + fmt(d.v, st) + "</li>";
    }).join("");
    var more = bin.items.length > 100 ? "<p>Showing the first 100 of " + bin.items.length + " players in this range.</p>" : "";
    document.getElementById("bin-panel").innerHTML =
      "<h3>" + st.label + " from " + fmt(bin.lo, st) + " to " + fmt(bin.hi, st) +
      " (" + bin.items.length + " players)</h3><ul>" + rows + "</ul>" + more;
  }
  // Keep showBin reachable for bar hover after render.
  window.__showBin = showBin;
  window.__bins = bins;
  window.__stat = stat;
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

(function init() {
  var btns = document.getElementById("stat-buttons");
  STATS.forEach(function (s) {
    var b = document.createElement("button");
    b.textContent = s.label;
    b.dataset.key = s.key;
    b.addEventListener("click", function () {
      current = s.key; selectedBin = -1;
      document.getElementById("bin-panel").innerHTML = "<p>Hover or tap a bar to see the players in that range.</p>";
      render();
    });
    btns.appendChild(b);
  });

  var input = document.getElementById("search");
  var results = document.getElementById("search-results");
  input.addEventListener("input", function () {
    var q = input.value.trim().toLowerCase();
    if (q.length < 2) { results.style.display = "none"; return; }
    var matches = [];
    for (var r = 0; r < DATA.length && matches.length < 10; r++) {
      if (DATA[r][0].toLowerCase().indexOf(q) !== -1) matches.push(DATA[r]);
    }
    if (!matches.length) { results.style.display = "none"; return; }
    results.innerHTML = "";
    matches.forEach(function (row) {
      var div = document.createElement("div");
      div.textContent = row[0] + " (" + row[1] + ")";
      div.addEventListener("click", function () {
        input.value = row[0];
        results.style.display = "none";
        marker = {name: row[0], team: row[1], rowIndex: DATA.indexOf(row)};
        render();
      });
      results.appendChild(div);
    });
    results.style.display = "block";
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-wrap")) results.style.display = "none";
  });

  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
