#!/usr/bin/env python3
"""Multi-turn conversation evaluation JSON -> HTML analytics report.
Standalone: needs only the Python standard library.

Usage
  python multiturn_report_generator.py path/to/multiturn_evaluation_report_*.json
  python multiturn_report_generator.py report.json -o out.html --open
"""
import argparse
import html
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime

ETYPE = "MULTI_TURN"


TITLE = "Multi-turn"


BLURB = "Does the assistant stay in role, remember context, and finish the user's goal across turns?"


def esc(x):
    return html.escape("" if x is None else str(x))


def f2(x):
    return "–" if x is None else f"{x:.2f}"


def pct(x):
    return "–" if x is None else f"{x * 100:.0f}%"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def pctl(xs, p):
    s = sorted(xs)
    if not s:
        return 0
    return s[max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip(" []")


def sec(s):
    return f"{s:.1f}s"


def fmt_ts(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return ts or "–"


def short_id(i):
    return i.split("_", 1)[1] if "_" in i else i


def prep(raw):
    cases = raw["case_results"]
    names = list((raw.get("metric_averages") or {}).keys())
    for c in cases:
        for m in c.get("metrics", []):
            if m["metric_name"] not in names:
                names.append(m["metric_name"])
    for c in cases:
        c["_m"] = {m["metric_name"]: m for m in c.get("metrics", [])}
        c["_mean"] = mean([m.get("score") for m in c.get("metrics", [])])
        c["_lat"] = (c.get("latency_ms") or 0) / 1000
        c["_failed"] = [m["metric_name"] for m in c.get("metrics", []) if not m.get("passed")]
        c["_ok"] = bool(c.get("all_passed", not c["_failed"]))
    stats = {}
    for n in names:
        ms = [c["_m"][n] for c in cases if n in c["_m"]]
        thr = Counter(m["threshold"] for m in ms).most_common(1)[0][0] if ms else 0.5
        stats[n] = dict(
            avg=mean([m.get("score") for m in ms]),
            n=len(ms),
            pass_rate=(sum(1 for m in ms if m.get("passed")) / len(ms)) if ms else None,
            thr=thr,
            fails=[c for c in cases if n in c["_failed"]],
        )
    S = dict(raw=raw, kind="mt", cases=cases, names=names, stats=stats)
    S["title"] = TITLE
    S["n"] = len(cases)
    S["passed"] = sum(c["_ok"] for c in cases)
    S["thr"] = Counter(s["thr"] for s in stats.values()).most_common(1)[0][0] if stats else 0.5
    S["lat"] = [c["_lat"] for c in cases]
    S["mean"] = mean([c["_mean"] for c in cases])
    S["weakest"] = min((n for n in names if stats[n]["avg"] is not None), key=lambda n: stats[n]["avg"], default=None)
    S["id"] = "s-" + S["kind"]
    return S


def judge_flag(m):
    """Score contradicts the judge's own explanation."""
    r = (m.get("reason") or "").lower()
    s, t = m.get("score"), m.get("threshold", 0.5)
    if s is None:
        return None
    if s < 1 and "no contradiction" in r:
        return "score < 1.0, but the judge's reason says there were no contradictions"
    if s < t and "no irrelevant" in r:
        return "score is below threshold, but the judge's reason says there were no irrelevant statements"
    return None


def pass_rate_at(S, t):
    ok = 0
    for c in S["cases"]:
        sc = [m["score"] for m in c["metrics"] if m.get("score") is not None]
        ok += all(s >= t for s in sc)
    return ok / S["n"] if S["n"] else 0


def doc_of(chunk):
    m = re.match(r"--- Document: (.+?) \(Section: (.+?)\) ---", chunk or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def parse_transcript(text):
    parts = re.split(r"(?m)^(USER|ASSISTANT):\s?", text or "")
    turns = []
    for i in range(1, len(parts) - 1, 2):
        turns.append((parts[i].lower(), parts[i + 1].strip()))
    return turns


def tool_key(t):
    return json.dumps([t.get("name"), t.get("input_parameters")], sort_keys=True)


def heat_style(sc, thr):
    if sc >= thr:
        a = 26 + min(1, (sc - thr) / max(1e-9, 1 - thr)) * 34
        return f"background:color-mix(in srgb,var(--success) {a:.0f}%,transparent)"
    a = 18 + min(1, (thr - sc) / max(1e-9, thr)) * 48
    return f"background:color-mix(in srgb,var(--danger) {a:.0f}%,transparent)"


def heatmap(S):
    names, st = S["names"], S["stats"]
    maxlat = max(S["lat"] + [1e-9])
    head = "".join(f"<th title='threshold {st[n]['thr']}'>{esc(n)}</th>" for n in names)
    rows = []
    for c in S["cases"]:
        tds = []
        for n in names:
            m = c["_m"].get(n)
            if not m or m.get("score") is None:
                tds.append('<td class="na" title="Metric not applicable to this case">·</td>')
            else:
                tds.append(f'<td style="{heat_style(m["score"], m["threshold"])}" title="{esc(n)} (threshold {m["threshold"]})"><b>{m["score"]:.2f}</b></td>')
        cls = "ok" if c["_ok"] else "bad"
        rows.append(
            f'<tr><th class="rowh {cls}"><a class="jump" href="#c-{esc(c["test_case_id"])}">{esc(c["test_case_id"])}</a>'
            f'<small>{esc(c.get("category"))}</small></th>{"".join(tds)}'
            f'<td class="mean">{f2(c["_mean"])}</td>'
            f'<td class="lat"><span class="lbar" style="width:{c["_lat"]/maxlat*100:.0f}%"></span>{sec(c["_lat"])}</td></tr>'
        )
    foot_avg = "".join(
        f'<td><b>{f2(st[n]["avg"])}</b></td>' for n in names
    )
    foot_pr = "".join(
        f'<td>{pct(st[n]["pass_rate"])}<small>{sum(1 for c in S["cases"] if n in c["_m"] and c["_m"][n].get("passed"))}/{st[n]["n"]}</small></td>' for n in names
    )
    return (
        '<div class="scroll"><table class="heat"><thead><tr><th class="c0">Case</th>' + head +
        '<th>Case mean</th><th>Latency</th></tr></thead><tbody>' + "".join(rows) +
        f'</tbody><tfoot><tr><th class="rowh">Metric mean</th>{foot_avg}<td></td><td></td></tr>'
        f'<tr><th class="rowh">Pass rate</th>{foot_pr}<td></td><td></td></tr></tfoot></table></div>'
        '<p class="note">Left border = case verdict (green passed, red failed). Dots mark metrics that were not applicable. '
        'Click a case id to jump to its details.</p>'
    )


def segbar(k, n):
    return f'<div class="seg"><i class="p" style="flex:{k}"></i><i class="f" style="flex:{n - k}"></i></div>'


def svg_axes(W, H, L, R, T, B, xlab, ylab, xticks, yticks, xmap, ymap, yfmt=lambda v: f"{v:.2f}", xfmt=lambda v: f"{v:.2f}"):
    g = []
    for v in yticks:
        y = ymap(v)
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="gl"/><text x="{L - 6}" y="{y + 3:.1f}" text-anchor="end" class="tick">{yfmt(v)}</text>')
    for v in xticks:
        x = xmap(v)
        g.append(f'<line y1="{T}" y2="{H - B}" x1="{x:.1f}" x2="{x:.1f}" class="gl"/><text x="{x:.1f}" y="{H - B + 14}" text-anchor="middle" class="tick">{xfmt(v)}</text>')
    g.append(f'<text x="{(L + W - R) / 2}" y="{H - 6}" text-anchor="middle" class="axl">{esc(xlab)}</text>')
    g.append(f'<text transform="translate(12 {(T + H - B) / 2}) rotate(-90)" text-anchor="middle" class="axl">{esc(ylab)}</text>')
    return "".join(g)


def sensitivity_chart(S):
    W, H, L, R, T, B = 520, 260, 46, 16, 14, 42
    xm = lambda v: L + v * (W - L - R)
    ym = lambda v: H - B - v * (H - T - B)
    xs = [i / 20 for i in range(0, 21)]
    ys = [pass_rate_at(S, x) for x in xs]
    path = " ".join(f"{xm(x):.1f},{ym(y):.1f}" for x, y in zip(xs, ys))
    area = f"{xm(0):.1f},{ym(0):.1f} " + path + f" {xm(1):.1f},{ym(0):.1f}"
    t = S["thr"]
    cur = pass_rate_at(S, t)
    marks = ""
    for v in (0.7, 0.8):
        if abs(v - t) > 1e-9:
            marks += f'<circle cx="{xm(v):.1f}" cy="{ym(pass_rate_at(S, v)):.1f}" r="4" class="dot warn"><title>threshold {v}: {pct(pass_rate_at(S, v))}</title></circle>'
    svg = (
        f'<svg viewBox="0 0 {W} {H}" class="plot">{svg_axes(W, H, L, R, T, B, "Uniform pass threshold applied to every metric", "Cases passing all metrics", [0, .25, .5, .75, 1], [0, .25, .5, .75, 1], xm, ym, yfmt=lambda v: f"{v * 100:.0f}%")}'
        f'<polygon points="{area}" class="area"/><polyline points="{path}" class="line"/>'
        f'<line x1="{xm(t):.1f}" x2="{xm(t):.1f}" y1="{T}" y2="{H - B}" class="thr"/>'
        f'<circle cx="{xm(t):.1f}" cy="{ym(cur):.1f}" r="5" class="dot ok"><title>configured threshold {t}: {pct(cur)}</title></circle>{marks}</svg>'
    )
    a7, a8 = pass_rate_at(S, 0.7), pass_rate_at(S, 0.8)
    cap = (f'<p class="note">Configured threshold <b>{t}</b> → <b>{pct(cur)}</b> pass. At 0.70 → <b>{pct(a7)}</b>, at 0.80 → <b>{pct(a8)}</b>. '
           'A steep drop means passes are marginal rather than solid.</p>')
    return svg + cap


def mt_tool_panel(S):
    rows, tot, dup = [], 0, 0
    mx = max([len(c.get("tools_called") or []) for c in S["cases"]] + [1])
    for c in S["cases"]:
        calls = c.get("tools_called") or []
        keys = [tool_key(t) for t in calls]
        distinct = len(set(keys))
        rep = len(keys) - distinct
        tot += len(keys)
        dup += rep
        c["_calls"], c["_rep"] = len(keys), rep
        turns = (c.get("metadata") or {}).get("turns_count") or len(parse_transcript(c.get("actual_output"))) // 2
        rows.append(
            f'<div class="brow"><div class="bl"><a class="jump" href="#c-{esc(c["test_case_id"])}">{esc(short_id(c["test_case_id"]))}</a><small>{turns} user turns</small></div>'
            f'<div class="seg2"><i class="u" style="width:{distinct / mx * 100:.0f}%"></i><i class="r" style="width:{rep / mx * 100:.0f}%"></i></div>'
            f'<div class="bv">{len(keys)} <small>({rep} repeat)</small></div></div>'
        )
    S["_tot_calls"], S["_dup_calls"] = tot, dup
    return ('<div class="brows">' + "".join(rows) + "</div>"
            f'<p class="note"><span class="lg u"></span>distinct lookup <span class="lg r"></span>identical repeat of an earlier call. '
            f'<b>{dup}</b> of <b>{tot}</b> tool calls repeated an earlier call with identical parameters.</p>')


def finding(kind, title, text):
    icon = {"ok": "&#10003;", "bad": "!", "warn": "&#9650;", "info": "i"}[kind]
    return f'<div class="finding {kind}"><div class="ic">{icon}</div><div><b>{title}</b><p>{text}</p></div></div>'


def ids(cs, n=6):
    s = ", ".join(short_id(c["test_case_id"]) for c in cs[:n])
    return s + (f" +{len(cs) - n} more" if len(cs) > n else "")


def findings(S):
    F = []
    n, st, names = S["n"], S["stats"], S["names"]
    failed = [c for c in S["cases"] if not c["_ok"]]
    if failed:
        # counterfactual: which single metric, if ignored, lifts pass rate the most
        best, bl = None, 0
        for m in names:
            ok = sum(1 for c in S["cases"] if not (set(c["_failed"]) - {m}))
            if ok - S["passed"] > bl:
                best, bl = m, ok - S["passed"]
        if best:
            only = [c for c in failed if c["_failed"] == [best]]
            F.append((2, finding("bad", f"Biggest lever: {esc(best)}",
                f"{len(only)} case(s) fail <i>only</i> on this metric ({esc(ids(only))}). Excluding it would lift the pass rate from {pct(S['passed'] / n)} to {pct((S['passed'] + bl) / n)}.")))
        sysf = [c for c in failed if len(c["_failed"]) >= 3]
        if sysf:
            F.append((3, finding("warn", f"{len(sysf)} case(s) fail on 3+ metrics",
                f"{esc(ids(sysf))}: multi-metric failures usually indicate a systemic cause (wrong context, off-script answer) rather than a borderline score.")))
    lenient = [m for m in names if st[m]["pass_rate"] is not None and st[m]["pass_rate"] >= 0.75 and st[m]["avg"] is not None and st[m]["avg"] < 0.75]
    if lenient:
        F.append((4, finding("warn", "Threshold is hiding weak averages",
            ", ".join(f"{esc(m)} (pass {pct(st[m]['pass_rate'])}, mean {f2(st[m]['avg'])})" for m in lenient) + f". Passing at {S['thr']} while averaging below 0.75 means many passes are marginal.")))
    flags = [(c, m) for c in S["cases"] for m in c["metrics"] if judge_flag(m)]
    if flags:
        F.append((5, finding("warn", f"{len(flags)} judge score/explanation mismatch(es)",
            "; ".join(f"{esc(short_id(c['test_case_id']))} / {esc(m['metric_name'])}" for c, m in flags[:5]) +
            ". The LLM judge's score disagrees with its own reasoning, so treat those scores with caution (flagged inside the case details).")))
    if S.get("_tot_calls") and S.get("_dup_calls"):
        F.append((3, finding("warn", "Redundant repeated lookups",
            f"{S['_dup_calls']} of {S['_tot_calls']} tool calls re-fetched the same order with identical parameters. Cache the order after the first call per conversation.")))
    F.sort(key=lambda x: x[0])
    if not F:
        F.append((9, finding("ok", "No notable issues", "All cases passed and nothing stood out.")))
    return "".join(f for _, f in F)


def metric_row(m):
    fl = judge_flag(m)
    w = f'<div class="warnbox">&#9650; Judge inconsistency: {esc(fl)}.</div>' if fl else ""
    return (f'<tr><td>{esc(m["metric_name"])}</td><td class="sc {"ok" if m.get("passed") else "bad"}">{f2(m.get("score"))}<small>/ {m.get("threshold")}</small></td>'
            f'<td>{esc(clean(m.get("reason")))}{w}</td></tr>')


def case_card(S, c):
    fails = [m for m in c["metrics"] if not m.get("passed")]
    passes = [m for m in c["metrics"] if m.get("passed")]
    tbl = lambda ms: '<div class="scroll"><table class="mt"><thead><tr><th>Metric</th><th>Score</th><th>Judge reasoning</th></tr></thead><tbody>' + "".join(metric_row(m) for m in ms) + "</tbody></table></div>"
    body = ""
    turns = parse_transcript(c.get("actual_output"))
    chat = "".join(f'<div class="turn {r}"><div class="who">{r.upper()}</div><div class="bubble">{esc(t)}</div></div>' for r, t in turns)
    body += f'<div><div class="dl">Scenario goal</div><p class="txt">{esc(c.get("expected_output"))}</p></div><div><div class="dl">Transcript</div><div class="chat">{chat}</div></div>'
    calls = c.get("tools_called") or []
    if calls:
        chips = "".join(f'<span class="chip">{esc(t["name"])}({esc(", ".join(f"{a}={b}" for a, b in (t.get("input_parameters") or {}).items()))})</span>' for t in calls)
        body += f'<div><div class="dl">Tool calls ({len(calls)})</div><div>{chips}</div></div>'
    ctx = c.get("retrieval_context") or []
    if ctx:
        items = ""
        for i, x in enumerate(ctx):
            d, s = doc_of(x)
            label = f"{d} › {s}" if d else "no document header"
            items += f'<div class="ctx"><span class="ci">chunk {i + 1} · {esc(label)}</span>{esc(x if len(x) < 900 else x[:900] + " …")}</div>'
        body += f'<details class="sub"><summary>Retrieval context ({len(ctx)})</summary>{items}</details>'
    if fails:
        body += f'<div><div class="dl bad">Failed metrics ({len(fails)})</div>{tbl(fails)}</div>'
    if passes:
        body += f'<details class="sub"><summary>Passed metrics ({len(passes)}): ' + " · ".join(f'{esc(m["metric_name"])} {f2(m.get("score"))}' for m in passes) + f'</summary>{tbl(passes)}</details>'
    md = c.get("metadata") or {}
    tags = ""
    if md.get("difficulty"):
        tags += f'<span class="tag">{esc(md["difficulty"])}</span>'
    title = md.get("scenario") or c.get("input")
    return (f'<details class="case" id="c-{esc(c["test_case_id"])}" data-s="{"pass" if c["_ok"] else "fail"}"><summary>'
            f'<span class="num">{esc(c["test_case_id"])}<small>{esc(c.get("category"))}</small></span><span class="q">{esc(title)}</span>'
            f'<span class="mini hide-s">{f2(c["_mean"])} · {sec(c["_lat"])}</span>{tags}'
            f'<span class="tag {"ok" if c["_ok"] else "bad"}">{"PASSED" if c["_ok"] else "FAILED"}</span><span class="chev">&#9656;</span></summary>'
            f'<div class="detail">{body}</div></details>')


def explorer(S):
    return ('<section class="panel explorer"><div class="ptitle"><h2>Case details</h2></div>'
            '<div class="filters"><button class="on" data-f="all">All</button><button data-f="fail">Failed</button><button data-f="pass">Passed</button>'
            '<button class="expand" style="margin-left:auto">Expand all</button></div>' + "".join(case_card(S, c) for c in S["cases"]) + "</section>")


def kpi(label, value, sub="", cls=""):
    return f'<div class="kpi {cls}"><small>{esc(label)}</small><strong>{value}</strong><em>{sub}</em></div>'


def panel(title, inner, sub="", cls=""):
    s = f'<p class="psub">{sub}</p>' if sub else ""
    return f'<section class="panel {cls}"><div class="ptitle"><h2>{esc(title)}</h2></div>{s}{inner}</section>'


def suite_html(S):
    st = S["stats"]
    # pre-compute audits (they annotate cases / S for findings)
    diag = []
    diag.append(panel("Tool calls per conversation", mt_tool_panel(S)))
    diag.append(panel("Threshold sensitivity", sensitivity_chart(S)))
    diag = [d for d in diag if d]

    kp = []
    kp.append(kpi("Pass rate", pct(S["passed"] / S["n"]), f"{S['passed']} of {S['n']} cases", "ok" if S["passed"] == S["n"] else "bad"))
    kp.append(segkpi(S))
    kp.append(kpi("Mean score", f2(S["mean"]), "average of case means"))
    w = S["weakest"]
    if w:
        kp.append(kpi("Weakest metric", f2(st[w]["avg"]), esc(w), "bad" if st[w]["avg"] < S["thr"] + .2 else ""))
    kp.append(kpi("Latency p50 / p95", f'{sec(pctl(S["lat"], 50))} <span class="sl">/ {sec(pctl(S["lat"], 95))}</span>', "per case"))
    fl = sum(1 for c in S["cases"] for m in c["metrics"] if judge_flag(m))
    kp.append(kpi("Judge flags", str(fl), "score contradicts explanation", "warn" if fl else "ok"))

    find_html = findings(S)  # after audits so annotations exist
    out = f'<section class="suite" id="{S["id"]}">'
    out += f'<div class="suite-head"><p>{esc(BLURB)}</p></div>'
    out += f'<div class="kpis">{"".join(kp)}</div>'
    out += panel("Key findings", find_html, "Derived from the data; chart details are not repeated here.")
    out += panel("Case × metric scores", heatmap(S))
    out += '<div class="grid">' + "".join(diag) + "</div>"
    out += explorer(S)
    return out + "</section>"


def segkpi(S):
    return (f'<div class="kpi seg-kpi"><small>Passed / failed</small>{segbar(S["passed"], S["n"])}'
            f'<em><b class="g">{S["passed"]}</b> passed · <b class="r">{S["n"] - S["passed"]}</b> failed</em></div>')


CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{font-family:Manrope,system-ui,sans-serif;--gold:#d9a441;--gold-bright:#f4c95d;--gold-pale:#fff0b8;--gold-dark:#9b6a16;--ink:#11100c;--bg:#0d0d0b;--surface:#14130f;--surface-2:#191711;--surface-3:#211d14;--line:#302a1d;--line-soft:#242119;--text:#f4f0e5;--muted:#aaa396;--dim:#8a8476;--success:#b8d978;--danger:#e4a09a;--warn:#f4c95d;color:var(--text);background:var(--bg);color-scheme:dark}
:root[data-theme="light"]{--gold:#b87909;--gold-bright:#d69a18;--gold-pale:#fff4ca;--gold-dark:#875a05;--ink:#201807;--bg:#faf8f2;--surface:#fff;--surface-2:#fffdf7;--surface-3:#fff7df;--line:#e7dfca;--line-soft:#eee8da;--text:#242117;--muted:#686255;--dim:#938a78;--success:#63842a;--danger:#a34d45;--warn:#b87909;color-scheme:light}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;background:radial-gradient(circle at 78% 0%,color-mix(in srgb,var(--gold) 12%,transparent),transparent 32%),radial-gradient(circle at 15% 28%,color-mix(in srgb,var(--gold) 5%,transparent),transparent 30%),var(--bg);color:var(--text)}
button{font:inherit;cursor:pointer}a{color:inherit}
code{font:11px "DM Mono",monospace;color:var(--gold)}
.topbar{height:72px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 5vw;background:color-mix(in srgb,var(--surface) 88%,transparent);backdrop-filter:blur(18px);position:sticky;top:0;z-index:20}
.brand{display:flex;gap:11px;align-items:center}.brand b{display:block;font-size:16px;letter-spacing:-.02em}.brand span{display:block;font-size:10px;color:var(--dim);margin-top:2px}
.logo{width:35px;height:35px;display:grid;place-items:center;background:linear-gradient(145deg,var(--gold-bright),var(--gold));color:var(--ink);border-radius:10px;box-shadow:0 5px 24px color-mix(in srgb,var(--gold) 18%,transparent)}
.top-actions{display:flex;gap:10px}
.btn{border:1px solid var(--line);color:var(--muted);background:var(--surface-2);border-radius:999px;padding:7px 12px;font-size:10px}
.btn:hover{color:var(--gold-bright);border-color:var(--gold)}
main{max-width:1440px;margin:auto;padding:56px 5vw 80px}
.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:34px;gap:30px}
.eyebrow{font:10px "DM Mono",monospace;letter-spacing:.14em;color:var(--gold)}
.hero h1{font-size:clamp(36px,4.6vw,62px);line-height:.98;letter-spacing:-.06em;margin:14px 0 0}
.hero h1 em{font-family:Georgia,serif;color:var(--gold-bright);font-weight:400}
.hero-card{border:1px solid var(--line);background:linear-gradient(145deg,color-mix(in srgb,var(--gold) 9%,var(--surface)),var(--surface));padding:16px 20px;border-radius:11px;min-width:300px;display:grid;gap:7px}
.hero-card div{display:flex;justify-content:space-between;gap:18px;font-size:11px}.hero-card span{color:var(--dim);font:10px "DM Mono",monospace}.hero-card b{font-weight:600;text-align:right}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px;border-bottom:1px solid var(--line);padding-bottom:14px}
.tabs button{background:var(--surface-2);border:1px solid var(--line);color:var(--muted);border-radius:8px;padding:9px 16px;font:600 12px Manrope,sans-serif}
.tabs button.on,.tabs button:hover{color:var(--ink);background:linear-gradient(135deg,var(--gold-bright),var(--gold));border-color:var(--gold)}
.suite[hidden]{display:none}
.suite-head h2{font-size:22px;margin:0 0 4px;letter-spacing:-.02em}.suite-head p{margin:0 0 20px;color:var(--muted);font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:18px}
.kpi{background:var(--surface-2);border:1px solid var(--line);padding:14px 16px;border-radius:10px}
.kpi small{display:block;font:9px "DM Mono",monospace;color:var(--dim);letter-spacing:.08em;text-transform:uppercase}
.kpi strong{display:block;white-space:nowrap;font-size:26px;margin-top:8px;color:var(--gold-bright);letter-spacing:-.03em}.kpi strong .sl{font-size:14px;color:var(--dim)}
.kpi em{display:block;font-style:normal;font-size:10px;color:var(--dim);margin-top:4px}
.kpi.ok strong{color:var(--success)}.kpi.bad strong{color:var(--danger)}.kpi.warn strong{color:var(--warn)}
.seg-kpi .seg{margin:14px 0 8px;height:14px}.g{color:var(--success)}.r{color:var(--danger)}
.grid{display:grid;gap:18px;grid-template-columns:1fr 1fr;margin-bottom:18px;align-items:start}
.panel{border:1px solid var(--line);background:color-mix(in srgb,var(--surface) 94%,transparent);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.08);padding:22px;min-width:0;margin-bottom:18px}
.grid .panel{margin-bottom:0}.panel.wide{margin-top:0}
.ptitle h2{font-size:14px;margin:0 0 6px}.psub{font-size:11px;color:var(--dim);line-height:1.6;margin:0 0 14px}
.note{font-size:10.5px;color:var(--dim);line-height:1.65;margin:10px 0 0}.note b{color:var(--muted)}
.dim{color:var(--dim)}
.scroll{overflow-x:auto}
table.heat{border-collapse:separate;border-spacing:3px;width:100%;font-size:11px}
table.heat th{font:9px "DM Mono",monospace;color:var(--dim);font-weight:500;padding:6px 4px;text-align:center;vertical-align:bottom;line-height:1.35}
table.heat th.c0{text-align:left}
table.heat th.rowh{text-align:left;font:600 11px "DM Mono",monospace;color:var(--text);padding:7px 10px;border-left:3px solid var(--line);white-space:nowrap}
table.heat th.rowh.ok{border-left-color:var(--success)}table.heat th.rowh.bad{border-left-color:var(--danger)}
table.heat th.rowh small{display:block;font-weight:400;color:var(--dim);font-size:9px;margin-top:2px}
table.heat th.rowh a{text-decoration:none}table.heat th.rowh a:hover{color:var(--gold)}
table.heat td{text-align:center;padding:10px 4px;border-radius:6px;font-family:"DM Mono",monospace;min-width:74px}
table.heat td.na{color:var(--dim);border:1px dashed var(--line-soft)}
table.heat td.mean{color:var(--muted);background:var(--surface-2)}
table.heat td.lat{position:relative;text-align:left;padding-left:8px;min-width:96px;color:var(--muted);font-size:10px;background:var(--surface-2);overflow:hidden}
.lbar{position:absolute;left:0;top:0;bottom:0;background:color-mix(in srgb,var(--gold) 20%,transparent);z-index:0}
table.heat td.lat{z-index:0}
table.heat tfoot th.rowh{border-left-color:transparent;color:var(--dim)}
table.heat tfoot td{background:none;border-top:1px solid var(--line);border-radius:0;color:var(--muted)}table.heat tfoot td small{display:block;font-size:8.5px;color:var(--dim)}
.seg{display:flex;height:12px;border-radius:99px;overflow:hidden;background:var(--surface-3);gap:2px}
.seg i{display:block;min-width:0}.seg .p{background:var(--success)}.seg .f{background:var(--danger)}
.brows{display:grid;gap:12px}.brow{display:grid;grid-template-columns:150px 1fr 70px;gap:12px;align-items:center}
.bl{font-size:11.5px;font-weight:600}.bl small{display:block;font:9px "DM Mono",monospace;color:var(--dim);font-weight:400;margin-top:2px}.bl a{text-decoration:none}
.bv{font:11px "DM Mono",monospace;color:var(--muted);text-align:right}.bv small{color:var(--dim)}
.seg2{display:flex;height:12px;background:var(--surface-3);border-radius:99px;overflow:hidden}
.seg2 .u,.lg.u{background:var(--gold)}.seg2 .r,.lg.r{background:var(--danger)}
.stack{display:flex;height:16px;border-radius:6px;overflow:hidden;gap:2px}.stack i{display:block}
.s-hit{background:var(--success)}.s-partial{background:var(--warn)}.s-miss{background:var(--danger)}.s-unlabelled{background:var(--dim)}
.lg{display:inline-block;width:9px;height:9px;border-radius:3px;margin:0 5px 0 8px;vertical-align:baseline}
svg.plot{width:100%;height:auto;display:block}
.plot .gl{stroke:var(--line-soft);stroke-width:1}.plot .tick{font:8.5px "DM Mono",monospace;fill:var(--dim)}.plot .axl{font:9px "DM Mono",monospace;fill:var(--muted)}
.plot .thr{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1;opacity:.7}.plot .quad{font:8px "DM Mono",monospace;fill:var(--dim);letter-spacing:.08em;opacity:.8}
.plot .dot{stroke:var(--surface);stroke-width:1.5}.plot .dot.ok{fill:var(--success)}.plot .dot.bad{fill:var(--danger)}.plot .dot.warn{fill:var(--warn)}
.plot .plbl{font:8.5px "DM Mono",monospace;fill:var(--muted)}
.plot .line{fill:none;stroke:var(--gold-bright);stroke-width:2.2;stroke-linejoin:round}.plot .area{fill:color-mix(in srgb,var(--gold) 14%,transparent)}
.finding{display:grid;grid-template-columns:30px 1fr;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);margin-bottom:8px}
.finding .ic{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;font:700 12px "DM Mono",monospace;color:var(--ink)}
.finding.ok .ic{background:var(--success)}.finding.bad .ic{background:var(--danger)}.finding.warn .ic{background:var(--gold-bright)}.finding.info .ic{background:#7fb4d8}
.finding b{font-size:12px;display:block;margin-bottom:3px}.finding p{margin:0;font-size:11px;line-height:1.65;color:var(--muted)}.finding p b{display:inline;font-size:inherit;margin:0;color:var(--text)}.finding i{color:var(--text)}
.tag{font:8.5px "DM Mono",monospace;padding:4px 7px;border-radius:4px;border:1px solid color-mix(in srgb,var(--gold) 35%,var(--line));background:color-mix(in srgb,var(--gold) 12%,var(--surface));color:var(--gold);white-space:nowrap}
.tag.ok{color:var(--success);border-color:color-mix(in srgb,var(--success) 40%,var(--line));background:color-mix(in srgb,var(--success) 10%,var(--surface))}
.tag.bad{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 40%,var(--line));background:color-mix(in srgb,var(--danger) 10%,var(--surface))}
.tag.warn{color:var(--warn)}
.chip{display:inline-block;font:10px "DM Mono",monospace;padding:3px 7px;border-radius:5px;border:1px solid var(--line);background:var(--surface);color:var(--muted);margin:0 5px 4px 0}
.chip.bad{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 50%,var(--line))}.chip.warn{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 50%,var(--line))}
.filters{display:flex;gap:7px;margin:8px 0 14px}.filters button{background:var(--surface-2);border:1px solid var(--line);color:var(--muted);border-radius:7px;padding:7px 12px;font:10px "DM Mono",monospace}.filters button.on,.filters button:hover{color:var(--gold);border-color:var(--gold)}
details.case{border:1px solid var(--line);border-radius:10px;margin-bottom:9px;background:var(--surface-2);overflow:hidden;scroll-margin-top:90px}
details.case[open]{border-color:color-mix(in srgb,var(--gold) 40%,var(--line))}
details.case>summary{list-style:none;display:grid;grid-template-columns:200px 1fr auto auto auto 18px;gap:14px;align-items:center;padding:14px;cursor:pointer}
details>summary::-webkit-details-marker{display:none}
details.case>summary:hover{background:color-mix(in srgb,var(--gold) 3%,var(--surface))}
.num{font:10px "DM Mono",monospace;color:var(--gold)}.num small{display:block;color:var(--dim);font-size:9px;margin-top:3px}
.q{font-size:12px;line-height:1.5}.chev{color:var(--dim);transition:.2s}details[open]>summary .chev{transform:rotate(90deg)}
.mini{font:10px "DM Mono",monospace;color:var(--muted)}
.detail{border-top:1px solid var(--line);padding:18px 22px;display:grid;gap:16px}
.dl{font:9px "DM Mono",monospace;letter-spacing:.1em;color:var(--gold);text-transform:uppercase;margin-bottom:6px}.dl.bad{color:var(--danger)}
.txt{font-size:12px;line-height:1.7;color:var(--muted);margin:0;white-space:pre-wrap}
.ctx{padding:10px 12px;background:var(--surface);border-radius:6px;border:1px solid var(--line-soft);font-size:10.5px;line-height:1.65;color:var(--muted);margin-top:7px;white-space:pre-wrap;word-break:break-word}
.ctx .ci{display:block;font:9px "DM Mono",monospace;color:var(--gold);margin-bottom:4px}
details.sub{border:1px solid var(--line-soft);border-radius:8px;padding:9px 12px;background:var(--surface)}
details.sub>summary{cursor:pointer;font:10px "DM Mono",monospace;color:var(--muted);line-height:1.6}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table.mt{width:100%;border-collapse:collapse;font-size:11px}table.mt th{font:9px "DM Mono",monospace;color:var(--dim);text-align:left;padding:8px;border-bottom:1px solid var(--line);font-weight:500}
table.mt td{padding:9px 8px;border-bottom:1px solid var(--line-soft);vertical-align:top;color:var(--muted);line-height:1.6}table.mt td:first-child{color:var(--text);font-weight:600}
table.mt td.sc{font-family:"DM Mono",monospace;white-space:nowrap;font-weight:600}table.mt td.sc small{color:var(--dim);font-weight:400;margin-left:3px}.sc.ok{color:var(--success)}.sc.bad{color:var(--danger)}
table.ov td{vertical-align:middle}table.ov .sn small,table.ov .pp{display:block;font:9px "DM Mono",monospace;color:var(--dim);margin-top:4px;font-weight:400}table.ov .sn a{text-decoration:none;color:var(--gold-bright)}
.warnbox{margin-top:6px;padding:6px 9px;border:1px solid color-mix(in srgb,var(--gold) 40%,var(--line));background:color-mix(in srgb,var(--gold) 8%,var(--surface));border-radius:6px;font-size:10px;color:var(--warn)}
.chat{display:grid;gap:10px}.turn{max-width:82%}.turn.user{justify-self:end}.turn.assistant{justify-self:start}
.bubble{padding:11px 14px;border-radius:12px;font-size:11.5px;line-height:1.65;border:1px solid var(--line);white-space:pre-wrap}
.turn.user .bubble{background:linear-gradient(135deg,color-mix(in srgb,var(--gold) 22%,var(--surface)),color-mix(in srgb,var(--gold) 10%,var(--surface)));border-top-right-radius:3px}
.turn.assistant .bubble{background:var(--surface);color:var(--muted);border-top-left-radius:3px}
.who{font:9px "DM Mono",monospace;color:var(--dim);margin-bottom:3px}.turn.user .who{text-align:right}
.mrow{display:grid;grid-template-columns:130px 1fr;gap:14px;align-items:center;margin:8px 0}.mlabel{font-size:11.5px;font-weight:600}
.sbar{display:flex;align-items:center;gap:10px}.track{position:relative;flex:1;height:9px;border-radius:99px;background:var(--surface-3);border:1px solid var(--line-soft)}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:99px}.fill.ok{background:var(--success)}.fill.bad{background:var(--danger)}
.tick{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--text);opacity:.7}.val{font:11px "DM Mono",monospace;min-width:34px;text-align:right}
footer{margin-top:36px;text-align:center;font:10px "DM Mono",monospace;color:var(--dim)}
@media(max-width:1000px){.grid,.two{grid-template-columns:1fr}.hero{display:block}.hero-card{margin-top:22px}details.case>summary{grid-template-columns:1fr auto 18px}.hide-s,details.case>summary .tag:not(.ok):not(.bad){display:none}.turn{max-width:96%}.brow{grid-template-columns:110px 1fr 56px}}
@media print{.topbar,.filters,.tabs{display:none}.suite[hidden]{display:block!important}body{background:#fff}details.case{break-inside:avoid}}
"""


JS = r"""
(function(){
 var root=document.documentElement;
 try{var s=localStorage.getItem('rep-theme');if(s)root.setAttribute('data-theme',s)}catch(e){}
 function tab(id){var any=false;document.querySelectorAll('section.suite').forEach(function(x){var on=x.id===id;x.hidden=!on;if(on)any=true});
  document.querySelectorAll('.tabs button').forEach(function(b){b.classList.toggle('on',b.dataset.tab===id)});return any}
 var first=document.querySelector('.tabs button');
 if(first){var h=location.hash.slice(1);if(!(h&&tab(h)))tab(first.dataset.tab)}
 document.addEventListener('click',function(e){
  var t=e.target.closest('[data-tab]');if(t){e.preventDefault();tab(t.dataset.tab);window.scrollTo({top:0});return}
  if(e.target.closest('#theme')){var n=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',n);try{localStorage.setItem('rep-theme',n)}catch(x){}return}
  var b=e.target.closest('button[data-f]');
  if(b){var p=b.closest('.explorer');p.querySelectorAll('button[data-f]').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
   p.querySelectorAll('details.case').forEach(function(d){d.style.display=(b.dataset.f==='all'||d.dataset.s===b.dataset.f)?'':'none'});return}
  var x=e.target.closest('button.expand');
  if(x){var q=x.closest('.explorer'),o=x.dataset.o!=='1';q.querySelectorAll('details.case').forEach(function(d){if(d.style.display!=='none')d.open=o});x.dataset.o=o?'1':'0';x.textContent=o?'Collapse all':'Expand all';return}
  var j=e.target.closest('a.jump');
  if(j){e.preventDefault();var d=document.getElementById(j.getAttribute('href').slice(1));if(d){d.style.display='';d.open=true;d.scrollIntoView({behavior:'smooth',block:'start'})}}
 });
})();
"""


GEM = '<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6"/><path d="M2 9h20"/></svg>'


def save(out, text):
    """Write the report; fall back to the current directory if the target folder isn't writable."""
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        out = os.path.basename(out)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    return out


def build(S, meta):
    sections = suite_html(S)
    mrows = "".join(f"<div><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in meta)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(S['title'])} evaluation</title><style>{CSS}</style></head><body>
<header class="topbar"><div class="brand"><div class="logo">{GEM}</div><div><b>EvalData Level II</b><span>Evaluation of AI systems</span></div></div>
<div class="top-actions"><button class="btn" onclick="window.print()">Print / PDF</button><button class="btn" id="theme">Toggle theme</button></div></header>
<main><section class="hero"><div><div class="eyebrow">&#9670; EVALUATION ANALYTICS</div><h1>{esc(S['title'])}, <em>measured</em></h1></div><div class="hero-card">{mrows}</div></section>
{sections}
<footer>Generated {datetime.now().strftime('%d %b %Y %H:%M')} &middot; static report</footer></main><script>{JS}</script></body></html>"""


def load_suite(path):
    """Accepts the suite's own JSON, or a full report that contains it."""
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    cands = [data] if isinstance(data, dict) and "case_results" in data else [
        v for v in (data.values() if isinstance(data, dict) else []) if isinstance(v, dict) and "case_results" in v]
    for c in cands:
        if c.get("evaluation_type") == ETYPE:
            return data, c
    sys.exit(f"{path}: no '{ETYPE}' suite with 'case_results' found. Wrong report type for this script?")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("json_path", nargs="?", help="Path to the report JSON")
    ap.add_argument("-o", "--output", help="Output HTML path (default: <json name>_analytics.html)")
    ap.add_argument("--open", action="store_true", help="Open the report in a browser")
    a = ap.parse_args()
    path = a.json_path or input("Path to JSON report: ").strip().strip('"').strip("'")
    if not os.path.isfile(path):
        sys.exit(f"File not found: {path}")
    try:
        top, raw = load_suite(path)
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON: {e}")
    S = prep(raw)
    meta = [("Run", fmt_ts(raw.get("timestamp"))), ("Model", str(raw.get("model_name") or "not recorded")),
            ("Cases", str(S["n"])), ("Source", os.path.basename(path))]
    out = a.output or (os.path.splitext(path)[0] + "_analytics.html")
    out = save(out, build(S, meta))
    print(f"Report written to: {os.path.abspath(out)}")
    if a.open:
        import webbrowser
        webbrowser.open("file://" + os.path.abspath(out))


if __name__ == "__main__":
    main()
