"""UI layer for the BEACON dashboard — a light, product-style analyst
console (sidebar navigation, rounded cards, icon strip), replacing the
earlier dark SOC-console skin at the user's direction.

Colour roles match pipeline/viz.py's LIGHT palette so the HTML components
here and the Altair charts read as one system, not two competing palettes.
Severity/risk always ships with an icon or dot alongside the label, so
colour never carries the meaning alone.
"""
from __future__ import annotations

import html

import pandas as pd

TOKENS = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "panel2": "#f8fafc",
    "line": "#e4e9f2",
    "ink": "#151b2c",
    "ink2": "#4b5675",
    "muted": "#8993ab",
    "accent": "#3d63e0",
    "accent_ink": "#2947b3",
    "accent_soft": "#e9eefd",
    "bar_mute": "#c7cee0",
}

# Reserved status palette -- never reused for a data series.
SEVERITY = {
    "Low": "#1f9d6f",
    "Medium": "#c98a1c",
    "High": "#d9642e",
    "Critical": "#d1454b",
}
SEVERITY_SOFT = {
    "Low": "#e3f6ee",
    "Medium": "#fbf1de",
    "High": "#fceee4",
    "Critical": "#fbe8e8",
}


def _esc(value) -> str:
    return html.escape(str(value))


def render(markup: str) -> None:
    """Emit raw HTML.

    st.markdown(unsafe_allow_html=True) runs the string through the Markdown
    parser first, which mangles a <style> block into visible page text.
    st.html() bypasses Markdown entirely, which is what CSS and these
    components need.
    """
    import streamlit as st

    st.html(markup)


def inject_theme() -> str:
    t = TOKENS
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
  /* :not(stIconMaterial) is load-bearing -- Streamlit draws its icons as
     Material Symbols LIGATURES, so a span reading "keyboard_double_arrow_left"
     is an arrow only while it keeps the icon font. [class*="st-"] otherwise
     matches those spans and reflows them as that literal text. */
  html, body, [class*="st-"]:not([data-testid="stIconMaterial"]),
  .stMarkdown, button, input, textarea {{
    font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
  }}
  .stApp {{ background: {t['bg']}; }}
  .block-container {{ padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1400px; }}
  h1 {{ font-size: 1.7rem !important; font-weight: 800 !important; letter-spacing: -.02em; }}
  h2 {{ font-size: 1rem !important; font-weight: 700 !important; }}
  h3 {{ font-size: .92rem !important; font-weight: 700 !important; }}
  p, .stCaption {{ color: {t['ink2']}; }}
  hr {{ border-color: {t['line']}; margin: 1.1rem 0; }}

  /* ---- sidebar: brand block + native page nav + status footer ---- */
  [data-testid="stSidebar"] {{ background: {t['panel']}; border-right: 1px solid {t['line']}; }}
  [data-testid="stSidebarNav"] {{ padding-top: 4px; }}
  [data-testid="stSidebarNav"] a {{
    border-radius: 8px; margin: 1px 8px; padding: 2px 4px;
  }}
  [data-testid="stSidebarNav"] a p {{ font-size: .87rem; font-weight: 500; color: {t['ink2']}; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {t['accent_soft']}; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] p {{ color: {t['accent_ink']}; font-weight: 600; }}
  [data-testid="stSidebarNav"] a:hover {{ background: {t['panel2']}; }}

  .bx-brand {{ display: flex; align-items: center; gap: 10px; padding: 6px 4px 16px;
    border-bottom: 1px solid {t['line']}; margin-bottom: 6px; }}
  .bx-brand .name {{ font-weight: 800; font-size: 17px; letter-spacing: -.01em; color: {t['ink']}; }}
  .bx-brand .tag {{ font-size: 10.5px; color: {t['muted']}; line-height: 1.3; margin-top: 1px; }}
  .bx-navlabel {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .12em;
    text-transform: uppercase; color: {t['muted']}; margin: 14px 10px 2px; }}

  .bx-label {{
    font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
    color: {t['muted']}; margin: 2px 0 8px;
  }}
  .bx-mono {{ font-family: "IBM Plex Mono", ui-monospace, monospace; }}

  /* ---- cards ---- */
  .bx-card {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 12px;
    padding: 20px; box-shadow: 0 1px 2px rgba(21,27,44,.04); }}
  .bx-card h2 {{ margin: 0 0 3px; }}
  .bx-card .sub {{ font-size: 12px; color: {t['muted']}; margin: 0 0 14px; }}

  /* ---- file-upload drop zone reskin ---- */
  [data-testid="stFileUploaderDropzone"] {{
    background: {t['panel2']} !important; border: 1.5px dashed {t['line']} !important;
    border-radius: 10px !important;
  }}
  [data-testid="stFileUploaderDropzoneInstructions"] svg {{ display:none; }}

  /* ---- verdict card ---- */
  .bx-verdict {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }}
  .bx-vicon {{ width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center;
    justify-content: center; flex: none; font-size: 21px; }}
  .bx-verdict .lbl {{ font-size: 10.5px; color: {t['muted']}; font-weight: 700; letter-spacing: .04em; }}
  .bx-verdict .cat {{ font-size: 21px; font-weight: 800; letter-spacing: -.01em; color: {t['ink']}; }}
  .bx-meta {{ font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: {t['muted']};
    margin: -8px 0 16px; overflow-wrap: anywhere; }}

  .bx-metric {{ margin-bottom: 13px; }}
  .bx-metric .row {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
  .bx-metric .k {{ font-size: 12.5px; color: {t['ink2']}; font-weight: 600; }}
  .bx-metric .v {{ font-family: "IBM Plex Mono", monospace; font-weight: 700; font-size: 13.5px; color: {t['ink']}; }}
  .bx-track {{ position: relative; height: 7px; border-radius: 4px; background: {t['panel2']};
    border: 1px solid {t['line']}; overflow: hidden; }}
  .bx-fill {{ display: block; height: 100%; border-radius: 4px; background: {t['accent']}; }}
  .bx-mark {{ position: absolute; top: -4px; bottom: -4px; width: 2px; background: {t['muted']}; opacity: .6; }}

  .bx-riskrow {{ display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: {t['ink2']};
    font-weight: 600; margin-bottom: 14px; }}
  .bx-chip {{
    display: inline-flex; align-items: center; gap: 6px;
    font-family: "IBM Plex Mono", monospace; font-size: 10.5px; font-weight: 700;
    padding: 3px 9px; border-radius: 99px;
  }}

  .bx-note {{
    border: 1px solid {t['line']}; border-radius: 9px; padding: 12px 14px;
    background: {t['panel2']}; font-size: 12px; color: {t['ink2']}; line-height: 1.55;
  }}
  .bx-note strong {{ color: {t['ink']}; font-weight: 700; }}

  /* ---- feature / stat strip (icon tiles) ---- */
  .bx-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px; margin-bottom: 4px; }}
  .bx-stat {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 12px;
    padding: 15px 16px; display: flex; gap: 12px; align-items: flex-start; }}
  .bx-stat .ic {{ width: 36px; height: 36px; border-radius: 9px; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center;
    flex: none; font-size: 17px; }}
  .bx-stat .t {{ font-weight: 700; font-size: 13.5px; color: {t['ink']}; margin-bottom: 2px; }}
  .bx-stat .d {{ font-size: 11.5px; color: {t['muted']}; line-height: 1.4; }}

  /* ---- numeric run-stats (small KPI grid) ---- */
  .bx-kpis {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1px; background: {t['line']}; border: 1px solid {t['line']};
    border-radius: 10px; overflow: hidden; margin-bottom: 4px;
  }}
  .bx-kpi {{ background: {t['panel']}; padding: 12px 14px; }}
  .bx-kpi .k {{ font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; color: {t['muted']}; margin-bottom: 4px; }}
  .bx-kpi .v {{ font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; color: {t['ink']}; letter-spacing: -.01em; }}
  .bx-kpi .s {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['muted']}; margin-top: 3px; }}

  /* ---- ranked probability bars ---- */
  .bx-prob {{ display: grid; grid-template-columns: 76px minmax(0,1fr) 44px; align-items: center; gap: 10px; padding: 3px 0; }}
  .bx-prob .n {{ font-size: 12px; color: {t['ink2']}; text-align: right; font-weight: 500; }}
  .bx-prob.top .n {{ color: {t['accent_ink']}; font-weight: 700; }}
  .bx-prob .ptrack {{ display: block; height: 10px; background: {t['panel2']}; border: 1px solid {t['line']};
    border-radius: 5px; overflow: hidden; }}
  /* display:block is load-bearing -- these are spans, and an inline element
     ignores width/height outright (the bar renders 0x0 without it). */
  .bx-prob .pfill {{ display: block; height: 100%; min-width: 3px; background: {t['bar_mute']}; border-radius: 0 4px 4px 0; }}
  .bx-prob.top .pfill {{ background: {t['accent']}; }}
  .bx-prob .p {{
    font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['muted']};
    font-variant-numeric: tabular-nums; text-align: right;
  }}
  .bx-prob.top .p {{ color: {t['ink']}; font-weight: 600; }}

  /* ---- model status cards ---- */
  .bx-streamcard {{ display: flex; align-items: flex-start; gap: 11px; padding: 13px;
    border-radius: 10px; border: 1px solid {t['line']}; margin-bottom: 10px; }}
  .bx-streamcard .ic {{ width: 34px; height: 34px; border-radius: 8px; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center;
    flex: none; font-size: 16px; }}
  .bx-streamcard .top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
  .bx-streamcard .t {{ font-weight: 700; font-size: 13px; color: {t['ink']}; }}
  .bx-streamcard .d {{ font-size: 11.3px; color: {t['muted']}; margin-top: 2px; line-height: 1.4; }}

  /* ---- engine status (compact dot rows, sidebar footer) ---- */
  .bx-status {{ display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }}
  .bx-status .dot {{ width: 7px; height: 7px; border-radius: 50%; margin-top: 5px; flex: none; }}
  .bx-status .nm {{ font-size: 11.5px; color: {t['ink2']}; line-height: 1.35; }}
  .bx-status .mt {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['muted']}; }}

  /* ---- detections log ---- */
  .bx-tablewrap {{ overflow-x: auto; border: 1px solid {t['line']}; border-radius: 10px; }}
  table.bx-log {{ width: 100%; border-collapse: collapse; min-width: 680px; background: {t['panel']}; }}
  table.bx-log thead th {{
    text-align: left; font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase;
    color: {t['muted']}; font-weight: 600; padding: 9px 13px; white-space: nowrap;
    border-bottom: 1px solid {t['line']}; background: {t['panel2']};
  }}
  table.bx-log td {{ padding: 9px 13px; border-bottom: 1px solid {t['line']}; font-size: 12px; color: {t['ink2']}; }}
  table.bx-log tr:last-child td {{ border-bottom: 0; }}
  table.bx-log td.m {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['muted']}; font-variant-numeric: tabular-nums; }}
  table.bx-log td.h {{ font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: {t['ink2']}; }}
  .bx-sev {{ display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 600; }}
  .bx-sev i {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }}

  @media (max-width: 720px) {{
    .bx-verdict {{ flex-wrap: wrap; }}
  }}
</style>
"""


LIGHTHOUSE_SVG = """<svg width="30" height="30" viewBox="0 0 24 24" fill="none">
  <path d="M9 21V9.5L12 3l3 6.5V21" stroke="#3d63e0" stroke-width="1.6" stroke-linejoin="round"/>
  <path d="M6 21h12M10 13h4M9.5 17h5" stroke="#3d63e0" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="12" cy="6.4" r="1.15" fill="#3d63e0"/>
</svg>"""


def sidebar_brand() -> str:
    return (f'<div class="bx-brand">{LIGHTHOUSE_SVG}<div>'
            f'<div class="name">BEACON</div>'
            f'<div class="tag">Explainable malware<br>detection</div></div></div>')


def top_bar() -> str:
    """Full-width brand bar above the page content.

    st.navigation()'s sidebar menu renders at a fixed position -- the very
    top of the sidebar -- no matter where in the script st.navigation() or
    surrounding st.sidebar blocks are called, so a brand block placed in
    the sidebar always ends up BELOW the nav rather than above it. Putting
    the brand here instead sidesteps that constraint entirely, and is
    closer to the reference layout anyway: brand and section nav were two
    separate stacked bars there, not one nested inside the other."""
    return f"""
<div style="display:flex;align-items:center;justify-content:space-between;
     padding:2px 2px 18px;border-bottom:1px solid {TOKENS['line']};margin-bottom:18px">
  <div style="display:flex;align-items:center;gap:11px">
    {LIGHTHOUSE_SVG}
    <div>
      <div style="font-weight:800;font-size:19px;letter-spacing:-.01em;color:{TOKENS['ink']}">BEACON</div>
      <div style="font-size:11px;color:{TOKENS['muted']}">Explainable malware detection from
        network-flow and memory-forensic telemetry</div>
    </div>
  </div>
  <div class="bx-mono" style="font-size:10.5px;letter-spacing:.14em;color:{TOKENS['muted']};
       text-transform:uppercase;white-space:nowrap">DETECT &middot; EXPLAIN &middot; SAFER SYSTEMS</div>
</div>
"""


def nav_label(text: str) -> str:
    return f'<div class="bx-navlabel">{_esc(text)}</div>'


def severity_chip(severity: str) -> str:
    colour = SEVERITY.get(severity, TOKENS["muted"])
    soft = SEVERITY_SOFT.get(severity, TOKENS["panel2"])
    return (f'<span class="bx-chip" style="color:{colour};background:{soft}">'
            f'● {_esc(severity)}</span>')


# One glyph per category so the verdict card always carries an icon, not
# colour alone -- same rule the severity chip follows.
CATEGORY_ICON = {
    "Benign": "✓", "Backdoor": "🛡", "Exploit": "⚡", "HackTool": "🔧",
    "Hoax": "◐", "Rootkit": "☠", "Trojan": "🐴", "Virus": "🦠", "Worm": "➰",
}


def verdict_card(verdict: str, severity: str, confidence: float, meta: str,
                 threshold: float = 0.60, example: bool = False) -> str:
    colour = SEVERITY.get(severity, TOKENS["accent"])
    soft = SEVERITY_SOFT.get(severity, TOKENS["accent_soft"])
    icon = CATEGORY_ICON.get(verdict, "●")
    badge = ('<span class="bx-chip" style="background:{s};color:{c}">LABELLED EXAMPLE</span>'
             .format(s=TOKENS["accent_soft"], c=TOKENS["accent_ink"])) if example else ""
    return f"""
<div class="bx-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
    <h2 style="margin:0">Result</h2>{badge}
  </div>
  <div style="height:10px"></div>
  <div class="bx-verdict">
    <div class="bx-vicon" style="background:{soft};color:{colour}">{icon}</div>
    <div><div class="lbl">PREDICTED CATEGORY</div><div class="cat">{_esc(verdict)}</div></div>
  </div>
  <div class="bx-meta">{_esc(meta)}</div>
  <div class="bx-metric">
    <div class="row"><span class="k">Confidence</span><span class="v">{confidence:.1%}</span></div>
    <div class="bx-track">
      <div class="bx-fill" style="width:{min(confidence, 1.0) * 100:.1f}%"></div>
      <div class="bx-mark" style="left:{threshold * 100:.0f}%"></div>
    </div>
  </div>
  <div class="bx-riskrow">Risk level: {severity_chip(severity)}</div>
</div>
"""


def stat_strip(items: list[dict]) -> str:
    """items: [{icon, title, desc}] -- the four feature tiles."""
    cells = "".join(
        f'<div class="bx-stat"><div class="ic">{i["icon"]}</div>'
        f'<div><div class="t">{_esc(i["title"])}</div><div class="d">{_esc(i["desc"])}</div></div></div>'
        for i in items
    )
    return f'<div class="bx-strip">{cells}</div>'


def kpi_strip(items: list[dict]) -> str:
    cells = "".join(
        f'<div class="bx-kpi"><div class="k">{_esc(i["label"])}</div>'
        f'<div class="v">{_esc(i["value"])}</div>'
        + (f'<div class="s">{_esc(i["sub"])}</div>' if i.get("sub") else "")
        + "</div>"
        for i in items
    )
    return f'<div class="bx-kpis">{cells}</div>'


def probability_bars(proba: pd.Series, verdict: str) -> str:
    ordered = proba.sort_values(ascending=False)
    rows = []
    for name, value in ordered.items():
        top = " top" if name == verdict else ""
        rows.append(
            f'<div class="bx-prob{top}"><span class="n">{_esc(name)}</span>'
            f'<span class="ptrack"><span class="pfill" style="width:{value * 100:.1f}%"></span></span>'
            f'<span class="p">{value * 100:.1f}%</span></div>'
        )
    return "".join(rows)


def stream_status_card(name: str, icon: str, ok: bool, detail: str) -> str:
    chip = ('<span class="bx-chip" style="background:#e3f6ee;color:#1f9d6f">LIVE</span>' if ok
            else '<span class="bx-chip" style="background:#fbf1de;color:#c98a1c">NOT TRAINED</span>')
    return (f'<div class="bx-streamcard"><div class="ic">{icon}</div>'
            f'<div style="flex:1"><div class="top"><span class="t">{_esc(name)}</span>{chip}</div>'
            f'<div class="d">{_esc(detail)}</div></div></div>')


def engine_status(name: str, detail: str, ok: bool = True) -> str:
    colour = SEVERITY["Low"] if ok else TOKENS["muted"]
    return (f'<div class="bx-status"><span class="dot" style="background:{colour}"></span>'
            f'<div><div class="nm">{_esc(name)}</div><div class="mt">{_esc(detail)}</div></div></div>')


def sidebar_footer(net_ok: bool, mem_ok: bool) -> str:
    """Shared status block every page renders at the bottom of the
    sidebar, after the native nav menu -- one definition so the five
    pages can't drift into five slightly different status footers."""
    return (
        nav_label("Engine status")
        + engine_status("Network model", "loaded" if net_ok else "not trained", ok=net_ok)
        + engine_status("Memory model", "loaded" if mem_ok else "not trained", ok=mem_ok)
        + nav_label("Dataset")
        + '<div class="bx-status"><div><div class="mt">BCCC-Mal-NetMem-2025<br>'
          '9 categories · local inference only</div></div></div>'
    )


def detections_table(rows: list[dict]) -> str:
    if not rows:
        return ('<div class="bx-note">No detections yet this session. '
                "Classify a capture and it will be listed here.</div>")
    body = []
    for r in rows:
        colour = SEVERITY.get(r["severity"], TOKENS["muted"])
        body.append(
            f'<tr><td class="m">{_esc(r["time"])}</td>'
            f'<td class="h">{_esc(r["sample"])}</td>'
            f'<td class="m">{_esc(r["stream"])}</td>'
            f'<td>{_esc(r["verdict"])}</td>'
            f'<td class="m">{r["confidence"]:.1%}</td>'
            f'<td><span class="bx-sev" style="color:{colour}"><i style="background:{colour}"></i>'
            f'{_esc(r["severity"])}</span></td>'
            f'<td class="m">{r["rows"]:,}</td></tr>'
        )
    return (
        '<div class="bx-tablewrap"><table class="bx-log"><thead><tr>'
        "<th>Time</th><th>Sample</th><th>Stream</th><th>Verdict</th>"
        "<th>Confidence</th><th>Severity</th><th>Rows</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def record_detection(session_state, *, sample: str, stream: str, verdict: str,
                     confidence: float, severity: str, rows: int) -> None:
    """Append to the in-session detections log. Deliberately in-memory only:
    the pages promise nothing is written to disk, and a session log that
    silently persisted uploaded sample names would break that promise."""
    from datetime import datetime, timezone

    log = session_state.setdefault("detections", [])
    entry = {"time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
             "sample": sample, "stream": stream, "verdict": verdict,
             "confidence": float(confidence), "severity": severity, "rows": int(rows)}
    # Guard against Streamlit's rerun-on-interaction duplicating the same
    # classification every time an unrelated widget changes.
    if log and {k: log[0][k] for k in ("sample", "stream", "verdict", "rows")} == \
            {k: entry[k] for k in ("sample", "stream", "verdict", "rows")}:
        return
    log.insert(0, entry)
    del log[25:]
