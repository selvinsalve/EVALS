#!/usr/bin/env python3
"""Conversational evaluation JSON -> HTML analytics report.  Usage: python conversational_report_generator.py path/to/conv_report.json [-o out.html] [--open]"""
# ---------------------------------------------------------------------------
# Shared helpers: formatting, inline-SVG charts, theme (matches reference UI)
# No third-party dependencies, output is a single offline-friendly HTML file.
# ---------------------------------------------------------------------------
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime

PALETTE = ["var(--gold-bright)", "#7fb4d8", "#b8d978", "#e4a09a", "#c9a0e4"]


def esc(x):
    return html.escape("" if x is None else str(x))


def rich(x):
    """Escape, then turn **bold** into <b>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(x))


def short(name):
    n = re.sub(r"Metric$", "", name or "")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)


def f2(x, d=2):
    return "-" if x is None else f"{x:.{d}f}"


def fmt_secs(s):
    s = float(s or 0)
    return f"{s/60:.1f} min" if s >= 120 else f"{s:.0f} s"


def fmt_ts(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return ts or "-"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def status_cls(passed):
    return "ok" if passed else "bad"


def cell_style(score, passed):
    if score is None:
        return ""
    if passed:
        a = 14 + score * 34
        return f"background:color-mix(in srgb,var(--success) {a:.0f}%,transparent)"
    a = 16 + (1 - score) * 36
    return f"background:color-mix(in srgb,var(--danger) {a:.0f}%,transparent)"


# ---------------------------------------------------------------- charts ---
def donut(passed, failed, center_label="pass rate"):
    total = passed + failed
    r, c = 62, 2 * 3.14159265 * 62
    frac = passed / total if total else 0
    dash_ok = c * frac
    return f"""
<svg viewBox="0 0 180 180" class="donut" role="img" aria-label="{passed} passed, {failed} failed">
  <circle cx="90" cy="90" r="{r}" fill="none" stroke="var(--danger)" stroke-width="18" opacity=".85"/>
  <circle cx="90" cy="90" r="{r}" fill="none" stroke="var(--success)" stroke-width="18"
          stroke-dasharray="{dash_ok:.1f} {c:.1f}" transform="rotate(-90 90 90)" stroke-linecap="butt"/>
  <text x="90" y="88" text-anchor="middle" class="donut-n">{frac*100:.0f}%</text>
  <text x="90" y="108" text-anchor="middle" class="donut-l">{esc(center_label)}</text>
</svg>
<div class="legend"><span><i style="background:var(--success)"></i>Passed <b>{passed}</b></span>
<span><i style="background:var(--danger)"></i>Failed <b>{failed}</b></span></div>"""


def score_bar(score, thr=None, show_val=True):
    if score is None:
        return '<span class="dim">n/a</span>'
    w = max(0, min(1, score)) * 100
    cls = "ok" if (thr is None or score >= thr) else "bad"
    tick = f'<i class="tick" style="left:{thr*100:.0f}%" title="threshold {thr}"></i>' if thr is not None else ""
    val = f'<b class="val {cls}">{score:.2f}</b>' if show_val else ""
    return f'<div class="sbar"><div class="track"><span class="fill {cls}" style="width:{w:.0f}%"></span>{tick}</div>{val}</div>'


def metric_bars(rows):
    """rows = [(label, value, threshold, sublabel)]"""
    out = []
    for label, val, thr, sub in rows:
        out.append(
            f'<div class="mrow"><div class="mlabel"><span>{esc(label)}</span><small>{esc(sub)}</small></div>'
            f"{score_bar(val, thr)}</div>"
        )
    return '<div class="mbars">' + "".join(out) + "</div>"


def radar(labels, series, size=340):
    """series = [(name, [values 0..1], color)]"""
    import math

    n = len(labels)
    cx = cy = size / 2
    R = size / 2 - 62
    def pt(i, v):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + R * v * math.cos(a), cy + R * v * math.sin(a)
    g = []
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{pt(i, ring)[0]:.1f},{pt(i, ring)[1]:.1f}" for i in range(n))
        g.append(f'<polygon points="{pts}" fill="none" stroke="var(--line)" stroke-width="1"/>')
        x, y = pt(0, ring)
        g.append(f'<text x="{x+4:.1f}" y="{y:.1f}" class="rtick">{ring:.2f}</text>')
    for i in range(n):
        x, y = pt(i, 1)
        g.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="var(--line)"/>')
        lx, ly = pt(i, 1.2)
        anchor = "middle" if abs(lx - cx) < 12 else ("start" if lx > cx else "end")
        words = labels[i].split(" ")
        half = max(1, len(words) // 2 + len(words) % 2) if len(words) > 2 else len(words)
        lines = [" ".join(words[:half]), " ".join(words[half:])] if len(words) > 1 and len(labels[i]) > 14 else [labels[i]]
        tspans = "".join(
            f'<tspan x="{lx:.1f}" dy="{0 if k == 0 else 12}">{esc(t)}</tspan>' for k, t in enumerate(lines) if t
        )
        g.append(f'<text x="{lx:.1f}" y="{ly - (6 if len(lines)>1 else 0):.1f}" text-anchor="{anchor}" class="rlabel">{tspans}</text>')
    for name, vals, color in series:
        pts = " ".join(f"{pt(i, v or 0)[0]:.1f},{pt(i, v or 0)[1]:.1f}" for i, v in enumerate(vals))
        g.append(f'<polygon points="{pts}" fill="{color}" fill-opacity=".16" stroke="{color}" stroke-width="2"/>')
        for i, v in enumerate(vals):
            x, y = pt(i, v or 0)
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"><title>{esc(name)} / {esc(labels[i])}: {f2(v)}</title></circle>')
    leg = "".join(f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, _, c in series)
    return f'<svg viewBox="-85 0 {size+170} {size}" class="radar">{"".join(g)}</svg><div class="legend">{leg}</div>'


def heatmap(row_labels, col_labels, cells, row_title=""):
    """cells[r][c] = (score, passed, threshold) or None"""
    head = "".join(f"<th>{esc(c)}</th>" for c in col_labels)
    body = []
    for r, lab in enumerate(row_labels):
        tds = []
        for c in range(len(col_labels)):
            cell = cells[r][c]
            if cell is None:
                tds.append('<td class="na">-</td>')
            else:
                s, p, t = cell
                tds.append(f'<td style="{cell_style(s, p)}" title="threshold {t}"><b>{s:.2f}</b></td>')
        body.append(f"<tr><th class='rowh'>{lab}</th>{''.join(tds)}</tr>")
    return f'<div class="scroll"><table class="heat"><thead><tr><th>{esc(row_title)}</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def hbar_simple(items, unit="s", color="var(--gold)"):
    """items = [(label, value)]"""
    mx = max([v for _, v in items] + [1e-9])
    rows = []
    for lab, v in items:
        rows.append(
            f'<div class="mrow"><div class="mlabel"><span>{esc(lab)}</span></div>'
            f'<div class="sbar"><div class="track"><span class="fill" style="width:{v/mx*100:.0f}%;background:{color}"></span></div>'
            f'<b class="val">{v:.0f}{unit}</b></div></div>'
        )
    return '<div class="mbars">' + "".join(rows) + "</div>"


def kpi(label, value, sub="", cls=""):
    return f'<div class="kpi {cls}"><small>{esc(label)}</small><strong>{value}</strong><em>{esc(sub)}</em></div>'


def panel(title, num, inner, cls="", sub=""):
    s = f"<p class='psub'>{sub}</p>" if sub else ""
    return f'<section class="panel {cls}"><div class="panel-title"><span>{num}</span><h2>{esc(title)}</h2></div>{s}{inner}</section>'


def reason_mismatch(score, thr, reason):
    """Flag LLM-judge outputs whose score contradicts their own explanation."""
    if score is None or not reason:
        return None
    r = reason.lower()
    if score < 1 and ("no contradiction" in r):
        return "score < 1.0 but the judge's reason states there were no contradictions"
    if score < (thr or 0.7) and ("no irrelevant" in r):
        return "score is below threshold but the judge's reason says there were no irrelevant statements"
    return None


# Rule-based remediation hints keyed by metric name
RECS = {
    "FaithfulnessMetric": "Constrain the generator to retrieved context (stricter system prompt, citations); manually audit the judge's flagged claims, as small local judges often mis-flag supported claims.",
    "AnswerRelevancyMetric": "Check that answers address every part of the question; review judge reasoning for consistency, since low scores with 'no irrelevant statements' usually signal a judge issue.",
    "ContextualRelevancyMetric": "Reduce retrieval noise: lower top-k, add a reranker or metadata filters, and re-chunk documents so each chunk answers one question.",
    "ContextualPrecisionMetric": "Improve ranking: put the most relevant chunks first with a cross-encoder reranker.",
    "ContextualRecallMetric": "Ensure the knowledge base actually contains the facts in the expected answers, then increase top-k or add hybrid (BM25 + vector) retrieval.",
    "RoleAdherenceMetric": "Tighten the system prompt on role boundaries and add refusal examples for out-of-scope requests.",
    "ConversationCompletenessMetric": "The bot should address every user intent, so add an intent checklist/tool for actions it can't perform (e.g. explain cancellation outcome explicitly) before moving on.",
    "TurnRelevancyMetric": "Keep each reply anchored to the latest user message; trim boilerplate.",
    "TurnFaithfulnessMetric": "Ground each reply in that turn's retrieval context; avoid adding unsupported policy details.",
    "ConversationalGEval": "Review the custom G-Eval criteria and the judge's reasoning, and answer the user's literal request first, then explain policy.",
    "KnowledgeRetentionMetric": "Persist key entities (order IDs, dates) in conversation state / memory.",
}


# ------------------------------------------------------------------- CSS ---
CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{font-family:Manrope,system-ui,sans-serif;--gold:#d9a441;--gold-bright:#f4c95d;--gold-pale:#fff0b8;--gold-dark:#9b6a16;--ink:#11100c;--bg:#0d0d0b;--surface:#14130f;--surface-2:#191711;--surface-3:#211d14;--line:#302a1d;--line-soft:#242119;--text:#f4f0e5;--muted:#aaa396;--dim:#706a5d;--success:#b8d978;--danger:#e4a09a;--warn:#f4c95d;color:var(--text);background:var(--bg);color-scheme:dark}
:root[data-theme="light"]{--gold:#b87909;--gold-bright:#d69a18;--gold-pale:#fff4ca;--gold-dark:#875a05;--ink:#201807;--bg:#faf8f2;--surface:#fff;--surface-2:#fffdf7;--surface-3:#fff7df;--line:#e7dfca;--line-soft:#eee8da;--text:#242117;--muted:#686255;--dim:#938a78;--success:#63842a;--danger:#a34d45;--warn:#b87909;color-scheme:light}
*{box-sizing:border-box}html{min-height:100%;scroll-behavior:smooth}
body{margin:0;min-height:100vh;background:radial-gradient(circle at 78% 0%,color-mix(in srgb,var(--gold) 12%,transparent),transparent 32%),radial-gradient(circle at 15% 28%,color-mix(in srgb,var(--gold) 5%,transparent),transparent 30%),var(--bg);color:var(--text)}
button{font:inherit;cursor:pointer}
.topbar{height:72px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 5vw;background:color-mix(in srgb,var(--surface) 88%,transparent);backdrop-filter:blur(18px);position:sticky;top:0;z-index:20}
.brand{display:flex;gap:11px;align-items:center}.brand b{display:block;font-size:16px;letter-spacing:-.02em}.brand span{display:block;font-size:10px;color:var(--dim);margin-top:2px}
.logo{width:35px;height:35px;display:grid;place-items:center;background:linear-gradient(145deg,var(--gold-bright),var(--gold));color:var(--ink);border-radius:10px;box-shadow:0 5px 24px color-mix(in srgb,var(--gold) 18%,transparent)}
.top-actions{display:flex;align-items:center;gap:12px}
.status{font:10px "DM Mono",monospace;color:var(--dim)}.status span{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--success);margin-right:7px;box-shadow:0 0 8px color-mix(in srgb,var(--success) 55%,transparent)}
.btn{border:1px solid var(--line);color:var(--muted);background:var(--surface-2);border-radius:999px;padding:7px 12px;font-size:10px;display:flex;align-items:center;gap:6px}
.btn:hover{color:var(--gold-bright);border-color:color-mix(in srgb,var(--gold) 55%,var(--line))}
nav.toc{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:26px}
nav.toc a{font:10px "DM Mono",monospace;color:var(--muted);text-decoration:none;border:1px solid var(--line);padding:6px 10px;border-radius:999px;background:var(--surface-2)}
nav.toc a:hover{color:var(--gold);border-color:var(--gold)}
main{max-width:1440px;margin:auto;padding:60px 5vw 90px}
.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:40px;gap:30px}
.eyebrow{font:10px "DM Mono",monospace;letter-spacing:.14em;color:var(--gold);display:flex;gap:7px;align-items:center}
.hero h1{font-size:clamp(38px,5vw,66px);line-height:.98;letter-spacing:-.06em;margin:14px 0 18px}
.hero h1 em{font-family:Georgia,serif;color:var(--gold-bright);font-weight:400;text-shadow:0 0 35px color-mix(in srgb,var(--gold) 20%,transparent)}
.hero p{max-width:670px;color:var(--muted);line-height:1.7;font-size:14px;margin:0}
.hero-card{border:1px solid var(--line);background:linear-gradient(145deg,color-mix(in srgb,var(--gold) 9%,var(--surface)),var(--surface));padding:17px 20px;border-radius:11px;box-shadow:0 16px 40px rgba(0,0,0,.08);min-width:300px;display:grid;gap:7px}
.hero-card div{display:flex;justify-content:space-between;gap:18px;font-size:11px}.hero-card span{color:var(--dim);font-family:"DM Mono",monospace;font-size:10px}.hero-card b{font-weight:600;text-align:right;word-break:break-all}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:20px}
.kpi{background:var(--surface-2);border:1px solid var(--line);padding:15px 16px;border-radius:10px}
.kpi small{display:block;font:9px "DM Mono",monospace;color:var(--dim);letter-spacing:.08em;text-transform:uppercase}
.kpi strong{display:block;white-space:nowrap;font-size:26px;margin-top:8px;color:var(--gold-bright);letter-spacing:-.03em}
.kpi em{display:block;font-style:normal;font-size:10px;color:var(--dim);margin-top:4px}
.kpi.ok strong{color:var(--success)}.kpi.bad strong{color:var(--danger)}
.grid{display:grid;gap:20px;margin-bottom:20px}.g-3{grid-template-columns:260px 1fr 1fr}.g-2{grid-template-columns:1fr 1fr}.g-21{grid-template-columns:1.25fr 1fr}
.panel{border:1px solid var(--line);background:color-mix(in srgb,var(--surface) 94%,transparent);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.08);padding:24px;min-width:0;margin-bottom:20px}
.grid .panel{margin-bottom:0}
.panel-title{display:flex;align-items:center;gap:10px;margin-bottom:6px}.panel-title>span{font:10px "DM Mono",monospace;color:var(--gold)}.panel-title h2{font-size:14px;margin:0}
.psub{font-size:11px;color:var(--dim);line-height:1.6;margin:4px 0 16px}
.donut{width:100%;max-width:200px;display:block;margin:6px auto}.donut-n{font-size:30px;font-weight:800;fill:var(--text)}.donut-l{font:9px "DM Mono",monospace;fill:var(--dim)}
.legend{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;font-size:10px;color:var(--muted);margin-top:8px}.legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px}.legend b{font-family:"DM Mono",monospace;color:var(--text);margin-left:3px}
.radar{width:100%;max-width:460px;display:block;margin:0 auto}.rlabel{font-size:9.5px;fill:var(--muted)}.rtick{font:8px "DM Mono",monospace;fill:var(--dim)}
.mbars{display:grid;gap:13px}.mrow{display:grid;grid-template-columns:minmax(120px,210px) 1fr;gap:14px;align-items:center}
.mlabel span{font-size:11.5px;font-weight:600;display:block}.mlabel small{font-size:9px;color:var(--dim);font-family:"DM Mono",monospace}
.sbar{display:flex;align-items:center;gap:10px}.track{position:relative;flex:1;height:9px;border-radius:99px;background:var(--surface-3);border:1px solid var(--line-soft)}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:99px;background:var(--gold)}.fill.ok{background:linear-gradient(90deg,color-mix(in srgb,var(--success) 70%,transparent),var(--success))}.fill.bad{background:linear-gradient(90deg,color-mix(in srgb,var(--danger) 70%,transparent),var(--danger))}
.tick{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--text);opacity:.7;border-radius:2px}
.val{font:11px "DM Mono",monospace;min-width:34px;text-align:right}.val.ok{color:var(--success)}.val.bad{color:var(--danger)}
.dim{color:var(--dim)}
.scroll{overflow-x:auto}table.heat{border-collapse:separate;border-spacing:4px;width:100%;font-size:11px}
table.heat th{font:9px "DM Mono",monospace;color:var(--dim);font-weight:500;padding:6px;text-align:center}
table.heat th.rowh{text-align:left;color:var(--muted);font:500 11px Manrope,sans-serif;max-width:260px;padding-right:10px}
table.heat td{text-align:center;padding:12px 6px;border-radius:7px;font-family:"DM Mono",monospace;border:1px solid var(--line-soft)}.heat td.na{color:var(--dim)}
.finding{display:grid;grid-template-columns:30px 1fr;gap:12px;padding:13px 14px;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);margin-bottom:9px}
.finding .ic{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;font:700 12px "DM Mono",monospace;color:var(--ink)}
.finding.ok .ic{background:var(--success)}.finding.bad .ic{background:var(--danger)}.finding.warn .ic{background:var(--gold-bright)}.finding.info .ic{background:#7fb4d8}
.finding b{font-size:12px;display:block;margin-bottom:3px}.finding p{margin:0;font-size:11px;line-height:1.65;color:var(--muted)}
.tag{font:8.5px "DM Mono",monospace;padding:4px 7px;border-radius:4px;border:1px solid color-mix(in srgb,var(--gold) 35%,var(--line));background:color-mix(in srgb,var(--gold) 12%,var(--surface));color:var(--gold)}
.tag.ok{color:var(--success);border-color:color-mix(in srgb,var(--success) 40%,var(--line));background:color-mix(in srgb,var(--success) 10%,var(--surface))}
.tag.bad{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 40%,var(--line));background:color-mix(in srgb,var(--danger) 10%,var(--surface))}
.filters{display:flex;gap:7px;margin:12px 0 16px}.filters button{background:var(--surface-2);border:1px solid var(--line);color:var(--muted);border-radius:7px;padding:7px 12px;font:10px "DM Mono",monospace}.filters button.on,.filters button:hover{color:var(--gold);border-color:var(--gold)}
details.case{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;background:var(--surface-2);overflow:hidden}
details.case[open]{border-color:color-mix(in srgb,var(--gold) 40%,var(--line))}
details.case>summary{list-style:none;display:grid;grid-template-columns:90px 1fr auto auto 20px;gap:14px;align-items:center;padding:15px;cursor:pointer}
details.case>summary::-webkit-details-marker{display:none}
details.case>summary:hover{background:color-mix(in srgb,var(--gold) 3%,var(--surface))}
.num{font:10px "DM Mono",monospace;color:var(--gold)}.q{font-size:12px;line-height:1.5}.chev{color:var(--dim);transition:.2s}details[open]>summary .chev{transform:rotate(90deg)}
.mini{font:10px "DM Mono",monospace;color:var(--muted)}
.detail{border-top:1px solid var(--line);padding:20px 24px;display:grid;gap:18px}
.dl{font:9px "DM Mono",monospace;letter-spacing:.1em;color:var(--gold-dark);text-transform:uppercase;margin-bottom:6px}
:root[data-theme=dark] .dl{color:var(--gold)}
.txt{font-size:12px;line-height:1.7;color:var(--muted);margin:0}.ctx{padding:10px 12px;background:var(--surface);border-radius:6px;border:1px solid var(--line-soft);font-size:11px;line-height:1.65;color:var(--muted);margin-bottom:7px}
.ctx .ci{font:9px "DM Mono",monospace;color:var(--gold);margin-right:6px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table.mt{width:100%;border-collapse:collapse;font-size:11px}table.mt th{font:9px "DM Mono",monospace;color:var(--dim);text-align:left;padding:8px;border-bottom:1px solid var(--line);font-weight:500}
table.mt td{padding:10px 8px;border-bottom:1px solid var(--line-soft);vertical-align:top;color:var(--muted);line-height:1.6}table.mt td:first-child{color:var(--text);font-weight:600;white-space:nowrap}
.warnbox{margin-top:8px;padding:7px 9px;border:1px solid color-mix(in srgb,var(--gold) 40%,var(--line));background:color-mix(in srgb,var(--gold) 8%,var(--surface));border-radius:6px;font-size:10px;color:var(--gold)}
.chat{display:grid;gap:12px}.turn{display:grid;gap:6px;max-width:82%}.turn.user{justify-self:end}.turn.assistant{justify-self:start}
.bubble{padding:12px 15px;border-radius:12px;font-size:12px;line-height:1.65;border:1px solid var(--line)}
.turn.user .bubble{background:linear-gradient(135deg,color-mix(in srgb,var(--gold) 22%,var(--surface)),color-mix(in srgb,var(--gold) 10%,var(--surface)));border-top-right-radius:3px}
.turn.assistant .bubble{background:var(--surface);border-top-left-radius:3px;color:var(--muted)}
.who{font:9px "DM Mono",monospace;color:var(--dim)}.turn.user .who{text-align:right}
.turn .ctx{margin:0;font-size:10px;border-style:dashed}
.recs li{font-size:11.5px;color:var(--muted);line-height:1.7;margin-bottom:8px}.recs b{color:var(--text)}
.recs{padding-left:18px;margin:0}
.reason-list{display:grid;gap:8px}.reason{padding:11px 13px;border-left:3px solid var(--danger);background:var(--surface-2);border-radius:0 7px 7px 0;font-size:11px;line-height:1.65;color:var(--muted)}.reason b{color:var(--text)}
footer{margin-top:40px;text-align:center;font:10px "DM Mono",monospace;color:var(--dim)}
@media(max-width:1000px){.g-3,.g-2,.g-21,.two{grid-template-columns:1fr}.hero{display:block}.hero-card{margin-top:24px}details.case>summary{grid-template-columns:70px 1fr 20px}.hide-s{display:none}.turn{max-width:96%}}
@media print{.topbar,.filters,nav.toc{display:none}details.case{break-inside:avoid}body{background:#fff}}
"""

JS = r"""
(function(){
 var root=document.documentElement;
 try{var s=localStorage.getItem('rep-theme');if(s)root.setAttribute('data-theme',s)}catch(e){}
 document.getElementById('theme').addEventListener('click',function(){
  var n=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',n);
  try{localStorage.setItem('rep-theme',n)}catch(e){}
 });
 var bs=document.querySelectorAll('.filters button[data-f]');
 bs.forEach(function(b){b.addEventListener('click',function(){
  bs.forEach(function(x){x.classList.remove('on')});b.classList.add('on');
  var f=b.dataset.f;document.querySelectorAll('details.case').forEach(function(d){
   d.style.display=(f==='all'||d.dataset.s===f)?'':'none';});
 })});
 var ex=document.getElementById('expand');
 if(ex)ex.addEventListener('click',function(){
  var ds=document.querySelectorAll('details.case');var open=ex.dataset.o!=='1';
  ds.forEach(function(d){d.open=open});ex.dataset.o=open?'1':'0';ex.textContent=open?'Collapse all':'Expand all';});
})();
"""

GEM = '<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6"/><path d="M2 9h20"/></svg>'


def page(title, eyebrow, h1, lede, meta, toc, body, subtitle="Evaluation of AI systems"):
    meta_html = "".join(f"<div><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in meta)
    toc_html = "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t in toc)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body>
<header class="topbar"><div class="brand"><div class="logo">{GEM}</div><div><b>EvalData Level II</b><span>{esc(subtitle)}</span></div></div>
<div class="top-actions"><div class="status"><span></span>Report generated</div>
<button class="btn" onclick="window.print()">Print / PDF</button>
<button class="btn" id="theme" aria-label="Toggle theme">Toggle theme</button></div></header>
<main>
<section class="hero"><div><div class="eyebrow">&#9670; {esc(eyebrow)}</div><h1>{h1}</h1><p>{lede}</p></div>
<div class="hero-card">{meta_html}</div></section>
<nav class="toc">{toc_html}</nav>
{body}
<footer>Generated {datetime.now().strftime('%d %b %Y %H:%M')} &middot; static report, no external data calls</footer>
</main><script>{JS}</script></body></html>"""


def finding(kind, title, text):
    icon = {"ok": "&#10003;", "bad": "!", "warn": "&#9650;", "info": "i"}[kind]
    return f'<div class="finding {kind}"><div class="ic">{icon}</div><div><b>{title}</b><p>{text}</p></div></div>'


def cli(description, default_suffix, build, expected_type):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("json_path", nargs="?", help="Path to the evaluation report JSON")
    ap.add_argument("-o", "--output", help=f"Output HTML path (default: <json name>{default_suffix})")
    ap.add_argument("--open", action="store_true", help="Open the report in your browser when done")
    a = ap.parse_args()
    path = a.json_path or input("Path to JSON report: ").strip().strip('"').strip("'")
    if not os.path.isfile(path):
        sys.exit(f"File not found: {path}")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON: {e}")
    got = str(data.get("evaluation_type", "")).lower()
    if got and expected_type.lower() not in got:
        print(f"[warn] evaluation_type is '{data.get('evaluation_type')}', this script expects '{expected_type}'.")
    if not isinstance(data.get("results"), list):
        sys.exit("JSON has no 'results' list, so this doesn't look like an evaluation report.")
    out = a.output or os.path.splitext(path)[0] + default_suffix
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build(data, os.path.basename(path)))
    print(f"Report written to: {os.path.abspath(out)}")
    if a.open:
        import webbrowser
        webbrowser.open("file://" + os.path.abspath(out))


# ====================== Conversational-specific report ======================
def build(d, fname):
    results = d["results"]
    n = len(results)
    passed = sum(1 for r in results if r.get("overall_passed"))
    failed = n - passed
    order, thr = [], {}
    for r in results:
        for m, v in (r.get("metrics") or {}).items():
            if m not in order:
                order.append(m)
            thr.setdefault(m, v.get("threshold"))
    avgs = {m: mean([(r["metrics"].get(m) or {}).get("score") for r in results]) for m in order}
    fails = {m: [r for r in results if m in r["metrics"] and not r["metrics"][m].get("passed")] for m in order}
    labels = [short(m) for m in order]
    sess_avg = [r.get("average_score") if r.get("average_score") is not None else mean([v.get("score") for v in r["metrics"].values()]) for r in results]
    overall = mean(sess_avg)
    tot_turns = sum(r.get("total_turns") or len(r.get("turn_details") or []) for r in results)
    tot_time = d.get("total_execution_time_seconds") or sum(r.get("execution_time_seconds") or 0 for r in results)
    a_turns = [t for r in results for t in (r.get("turn_details") or []) if t.get("role") == "assistant"]
    grounded = [t for t in a_turns if t.get("retrieval_context")]
    cov = len(grounded) / len(a_turns) * 100 if a_turns else 0
    sid = [r.get("session_id", f"session_{i+1}") for i, r in enumerate(results)]

    kp = "".join([
        kpi("Sessions", n, "simulated conversations"),
        kpi("Passed", passed, "all metrics >= threshold", "ok"),
        kpi("Failed", failed, "at least one metric below", "bad" if failed else ""),
        kpi("Pass rate", f"{d.get('pass_rate', passed/n*100 if n else 0):.0f}%", "strict, all-metric rule", "ok" if passed == n else "bad"),
        kpi("Mean score", f2(overall), "across sessions"),
        kpi("Total turns", tot_turns, f"{len(a_turns)} assistant replies"),
        kpi("Grounded replies", f"{cov:.0f}%", f"{len(grounded)}/{len(a_turns)} have retrieval context"),
        kpi("Run time", fmt_secs(tot_time), f"{fmt_secs(tot_time/n if n else 0)} per session"),
    ])

    series = [(sid[i], [(r["metrics"].get(m) or {}).get("score") or 0 for m in order], PALETTE[(i + 1) % len(PALETTE)]) for i, r in enumerate(results)]
    series.insert(0, ("Average", [avgs[m] or 0 for m in order], PALETTE[0]))
    overview = '<div class="grid g-3">' + \
        panel("Outcome", "01", donut(passed, failed)) + \
        panel("Metric averages", "02", metric_bars([(short(m), avgs[m], thr[m], f"threshold {thr[m]} | {len(fails[m])} failing") for m in order]),
              sub="Vertical tick = pass threshold. Averages are taken over all sessions.") + \
        panel("Session profiles", "03", radar(labels, series)) + "</div>"

    cells = [[(None if not r["metrics"].get(m) else (r["metrics"][m]["score"] or 0, r["metrics"][m]["passed"], r["metrics"][m]["threshold"])) for m in order] for r in results]
    rl = [f"<span class='num'>{esc(sid[i])}</span><br>{esc((r.get('scenario') or '')[:80])}{'...' if len(r.get('scenario') or '')>80 else ''}" for i, r in enumerate(results)]
    heat = panel("Session x metric heatmap", "04", heatmap(rl, labels, cells, "Session"), sub="Green = passed, red = failed; intensity follows the score. Hover for threshold.")

    # compare sessions bars
    comp = []
    for m in order:
        inner = "".join(f'<div style="display:grid;grid-template-columns:70px 1fr;gap:8px;align-items:center;margin-bottom:4px"><small class="mini">{esc(sid[i][-3:])}</small>{score_bar((r["metrics"].get(m) or {}).get("score"), thr[m])}</div>' for i, r in enumerate(results))
        comp.append(f'<div><div class="dl" style="margin-top:10px">{esc(short(m))}</div>{inner}</div>')
    cmp_panel = panel("Session comparison", "05", "".join(comp), sub="Per-metric score for each session against the shared threshold.")
    turn_panel = panel("Turn-level grounding", "06",
                       metric_bars([(f"{sid[i]}", mean([1 if t.get('retrieval_context') else 0 for t in r['turn_details'] if t['role'] == 'assistant']), None,
                                     f"{sum(1 for t in r['turn_details'] if t['role']=='assistant' and t.get('retrieval_context'))}/{sum(1 for t in r['turn_details'] if t['role']=='assistant')} assistant turns grounded") for i, r in enumerate(results)]) +
                       "<p class='psub' style='margin-top:16px'>Share of assistant turns that were backed by retrieved policy text. Ungrounded turns can't be checked by Turn Faithfulness.</p>" +
                       "<div class='dl' style='margin-top:14px'>Execution time per session</div>" + hbar_simple([(sid[i], r.get("execution_time_seconds") or 0) for i, r in enumerate(results)]))
    grid2 = f'<div class="grid g-2">{cmp_panel}{turn_panel}</div>'

    # findings
    F = []
    F.append(finding("bad" if passed / n < .5 else ("warn" if passed < n else "ok"), "Overall result",
                     f"{passed} of {n} sessions passed ({passed/n*100:.0f}%). A session passes only if every metric meets its threshold."))
    ranked = sorted([m for m in order if avgs[m] is not None], key=lambda m: avgs[m])
    if ranked:
        F.append(finding("warn" if avgs[ranked[0]] < 0.9 else "ok", f"Weakest metric: {short(ranked[0])}",
                         f"Average {f2(avgs[ranked[0]])} (threshold {thr[ranked[0]]}); failing in {len(fails[ranked[0]])} session(s). Strongest: {short(ranked[-1])} at {f2(avgs[ranked[-1]])}."))
    perfect = [short(m) for m in order if avgs[m] == 1.0]
    if perfect:
        F.append(finding("ok", "Perfect on", ", ".join(perfect) + ": role discipline, relevance and memory are solid across the sessions."))
    for r, i in zip(results, range(n)):
        bad = [(m, v) for m, v in r["metrics"].items() if not v.get("passed")]
        if bad:
            F.append(finding("bad", f"{sid[i]} failed", f"Scenario: {esc(r.get('scenario'))}<br>Failing: " + "; ".join(f"{short(m)} {v['score']:.2f} (thr {v['threshold']})" for m, v in bad)))
    edge = [(sid[i], m, v["score"]) for i, r in enumerate(results) for m, v in r["metrics"].items() if v.get("passed") and v.get("score") is not None and v["score"] - v["threshold"] <= .02]
    if edge:
        F.append(finding("warn", "Passing right on the line", "; ".join(f"{a}: {short(b)} = {c:.2f}" for a, b, c in edge) + ". A tiny change in judge output would flip these to fail."))
    if a_turns and cov < 100:
        un = [(sid[i], t["turn_index"]) for i, r in enumerate(results) for t in r["turn_details"] if t["role"] == "assistant" and not t.get("retrieval_context")]
        F.append(finding("info", "Ungrounded assistant turns", f"{len(a_turns)-len(grounded)} reply(ies) had no retrieval context: " + ", ".join(f"{a} turn {b}" for a, b in un) + ". These are typically pleasantries, but any factual claim there can't be verified."))
    findings_html = panel("Key findings", "07", "".join(F))
    recs = "".join(f"<li><b>{short(m)}</b> ({len(fails[m])} failing): {esc(RECS.get(m, 'Review judge reasons.'))}</li>" for m in order if fails[m])
    near_m = [m for m in order if not fails[m] and avgs[m] is not None and avgs[m] < .9]
    recs += "".join(f"<li><b>{short(m)}</b> (watch, avg {f2(avgs[m])}): {esc(RECS.get(m, ''))}</li>" for m in near_m)
    rec_html = panel("Suggested actions", "08", f'<ul class="recs">{recs}</ul>' if recs else "<p class='txt'>No failing metrics.</p>")

    # failure reasoning
    blocks = []
    for m in order:
        if not fails[m]:
            continue
        items = "".join(f'<div class="reason"><b>{esc(r.get("session_id"))} &middot; {r["metrics"][m]["score"]:.2f} / {thr[m]}</b><br>{esc(r["metrics"][m].get("reason"))}</div>' for r in fails[m])
        blocks.append(f'<div style="margin-bottom:20px"><div class="dl">{esc(short(m))}: judge reasoning</div><div class="reason-list">{items}</div></div>')
    fail_html = panel("Failure reasoning", "09", "".join(blocks) or "<p class='txt'>Nothing failed.</p>", sub="Verbatim explanations from the LLM judge for every metric that missed its threshold.")

    # session explorer
    cards = []
    for i, r in enumerate(results):
        turns = []
        for t in r.get("turn_details") or []:
            role = t.get("role", "user")
            ctx = ""
            if role == "assistant":
                rc = t.get("retrieval_context")
                ctx = "".join(f'<div class="ctx"><span class="ci">context #{k+1}</span>{esc(c)}</div>' for k, c in enumerate(rc)) if rc else '<div class="ctx"><span class="ci">no retrieval context</span></div>'
            turns.append(f'<div class="turn {role}"><div class="who">TURN {t.get("turn_index")} &middot; {role.upper()}</div><div class="bubble">{rich(t.get("content"))}</div>{ctx}</div>')
        rows = []
        for m in order:
            v = r["metrics"].get(m)
            if not v:
                continue
            mm = reason_mismatch(v.get("score"), v.get("threshold"), v.get("reason"))
            warn = f'<div class="warnbox">&#9650; Judge inconsistency: {esc(mm)}.</div>' if mm else ""
            err = f'<div class="warnbox">Error: {esc(v["error"])}</div>' if v.get("error") else ""
            rows.append(f"<tr><td>{esc(short(m))}</td><td style='min-width:150px'>{score_bar(v.get('score'), v.get('threshold'))}</td><td class='mini'>{v.get('threshold')}</td>"
                        f"<td><span class='tag {status_cls(v.get('passed'))}'>{'PASS' if v.get('passed') else 'FAIL'}</span></td><td>{esc(v.get('reason'))}{warn}{err}</td></tr>")
        cards.append(f"""
<details class="case" data-s="{'pass' if r.get('overall_passed') else 'fail'}"><summary>
<span class="num">{esc(sid[i])}</span><span class="q">{esc(r.get('scenario'))}</span>
<span class="mini hide-s">avg {f2(r.get('average_score'))} &middot; {r.get('total_turns')} turns &middot; {fmt_secs(r.get('execution_time_seconds'))}</span>
<span class="tag {status_cls(r.get('overall_passed'))}">{'PASSED' if r.get('overall_passed') else 'FAILED'}</span><span class="chev">&#9656;</span></summary>
<div class="detail">
<div><div class="dl">Chatbot role</div><p class="txt">{esc(r.get('chatbot_role'))}</p></div>
<div><div class="dl">Transcript</div><div class="chat">{''.join(turns)}</div></div>
<div class="scroll"><table class="mt"><thead><tr><th>Metric</th><th>Score</th><th>Thr.</th><th>Status</th><th>Judge reasoning</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
</div></details>""")
    explorer = panel("Session explorer", "10",
                     '<div class="filters"><button class="on" data-f="all">All</button><button data-f="fail">Failed</button><button data-f="pass">Passed</button>'
                     '<button id="expand" data-o="0" style="margin-left:auto">Expand all</button></div>' + "".join(cards))

    # data quality
    Q = []
    mm_all = [(sid[i], m, reason_mismatch(v.get("score"), v.get("threshold"), v.get("reason"))) for i, r in enumerate(results) for m, v in r["metrics"].items()]
    mm_all = [x for x in mm_all if x[2]]
    if mm_all:
        Q.append(finding("warn", f"{len(mm_all)} judge score/reason inconsistenc{'y' if len(mm_all)==1 else 'ies'}", "; ".join(f"{a} / {short(b)}: {c}" for a, b, c in mm_all) + ". Consider a stronger judge model or re-running."))
    # file-level avg vs recomputed
    for m, v in (d.get("metric_averages") or {}).items():
        if m in avgs and avgs[m] is not None and abs(avgs[m] - v) > .01:
            Q.append(finding("warn", f"Average mismatch: {short(m)}", f"Reported {v} but recomputed {avgs[m]:.3f} from sessions."))
    for i, r in enumerate(results):
        if r.get("total_turns") and r["total_turns"] != len(r.get("turn_details") or []):
            Q.append(finding("warn", f"{sid[i]} turn count mismatch", f"total_turns={r['total_turns']} but {len(r['turn_details'])} turn records."))
    mu = str(d.get("model_used", ""))
    if "object at 0x" in mu:
        Q.append(finding("info", "Model name not recorded", "<code>model_used</code> holds a Python object repr instead of a model name. Log the model string for run-to-run comparability."))
    if n < 10:
        Q.append(finding("info", "Small sample", f"Only {n} sessions: each one moves the pass rate by {100/n:.0f} points. Add more scenarios (multi-intent, adversarial, off-topic) before drawing conclusions."))
    qa_html = panel("Data quality & evaluation caveats", "11", "".join(Q) or "<p class='txt'>No issues detected.</p>")

    body = (f'<div class="kpis" id="summary">{kp}</div><div id="overview">{overview}</div><div id="heatmap">{heat}</div>{grid2}'
            f'<div class="grid g-21" id="insights">{findings_html}{rec_html}</div><div id="failures">{fail_html}</div>'
            f'<div id="cases">{explorer}</div><div id="quality">{qa_html}</div>')
    ts = [("summary", "Summary"), ("overview", "Overview"), ("heatmap", "Heatmap"), ("insights", "Insights"), ("failures", "Failures"), ("cases", "Sessions"), ("quality", "Data quality")]
    return page(f"Conversational Evaluation: {d.get('run_id')}", "CONVERSATIONAL EVALUATION REPORT",
                "Conversation quality, <em>measured</em>",
                "Role adherence, completeness, turn relevancy, faithfulness and knowledge retention across multi-turn chatbot sessions, with full transcripts and the judge's reasoning.",
                [("Run ID", d.get("run_id")), ("Timestamp", fmt_ts(d.get("timestamp"))), ("Source file", fname),
                 ("Judge model", "not recorded" if "object at 0x" in mu else mu), ("Duration", fmt_secs(tot_time))], ts, body, "Conversational evaluation")


if __name__ == "__main__":
    cli("Generate an HTML analytics report from a Conversational evaluation JSON.", "_analytics.html", build, "Conversational")
