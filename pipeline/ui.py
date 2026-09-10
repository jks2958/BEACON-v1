"""SOC-console UI layer for the BEACON dashboard.

Streamlit's defaults are airy and document-shaped; a triage console needs
density and state-at-a-glance. This module carries the token set, the CSS
that tightens Streamlit's chrome, and the small HTML components the pages
compose (severity band, KPI strip, ranked bars, detections log).

Colour roles match pipeline/viz.py so the UI and the charts are one system
rather than two palettes competing. Severity uses the reserved status
palette and always ships with an icon or dot alongside the label, so colour
never carries the meaning alone.
"""
from __future__ import annotations

import html

import pandas as pd

TOKENS = {
    "ground": "#10151a",
    "panel": "#171d23",
    "panel2": "#1c242c",
    "line": "#232c35",
    "line_soft": "#1b232b",
    "ink": "#e6edf3",
    "ink2": "#b3c0cc",
    "dim": "#8b9aa8",
    "accent": "#3987e5",
    "accent_dim": "#1e4f8a",
    "bar_emph": "#3987e5",
    "bar_mute": "#6b7683",
}

# Reserved status palette -- never reused for a data series.
SEVERITY = {
    "Low": "#0ca30c",
    "Medium": "#fab219",
    "High": "#ec835a",
    "Critical": "#d03b3b",
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
  /* :not(stIconMaterial) is load-bearing -- Streamlit draws its icons as
     Material Symbols LIGATURES, so a span reading "keyboard_double_arrow_left"
     is an arrow only while it keeps the icon font. [class*="st-"] otherwise
     matches those spans and reflows them as that literal text. */
  html, body, [class*="st-"]:not([data-testid="stIconMaterial"]),
  .stMarkdown, button, input, textarea {{
    font-family: "IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, sans-serif;
  }}
  /* Density: Streamlit's default block padding is document-sized. */
  .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }}
  h1 {{ font-size: 1.35rem !important; font-weight: 600 !important; letter-spacing: -.01em; }}
  h2 {{ font-size: 1rem !important; font-weight: 600 !important; }}
  h3 {{ font-size: .9rem !important; font-weight: 600 !important; }}
  [data-testid="stSidebar"] {{ background: {t['panel']}; border-right: 1px solid {t['line']}; }}
  [data-testid="stSidebarNav"] a p {{ font-size: .86rem; }}
  hr {{ border-color: {t['line']}; margin: 1.1rem 0; }}

  .bx-label {{
    font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
    color: {t['dim']}; margin: 2px 0 8px;
  }}
  .bx-mono {{ font-family: "IBM Plex Mono", ui-monospace, monospace; }}

  /* ---- severity band ---- */
  .bx-band {{
    display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 20px;
    align-items: center; border: 1px solid {t['line']}; border-radius: 4px;
    padding: 15px 18px; margin-bottom: 14px;
  }}
  .bx-band .name {{ font-size: 25px; font-weight: 700; letter-spacing: -.02em; line-height: 1.15; }}
  .bx-band .line1 {{ display: flex; align-items: center; gap: 11px; flex-wrap: wrap; }}
  .bx-band .meta {{
    font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['dim']};
    margin-top: 6px; overflow-wrap: anywhere;
  }}
  .bx-chip {{
    display: inline-flex; align-items: center; gap: 6px;
    font-family: "IBM Plex Mono", monospace; font-size: 10.5px; font-weight: 600;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 4px 9px; border-radius: 3px; border: 1px solid;
  }}
  .bx-meter {{ min-width: 200px; }}
  .bx-meter .head {{
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: {t['dim']};
  }}
  .bx-meter .val {{
    font-size: 21px; font-weight: 600; color: {t['ink']};
    font-variant-numeric: tabular-nums; letter-spacing: -.01em;
  }}
  .bx-meter .track {{
    position: relative; height: 7px; border-radius: 4px; margin-top: 6px;
    background: {t['panel2']}; border: 1px solid {t['line']};
  }}
  .bx-meter .fill {{ height: 100%; border-radius: 3px; background: {t['accent']}; }}
  .bx-meter .mark {{ position: absolute; top: -4px; bottom: -4px; width: 2px; background: {t['dim']}; opacity: .75; }}
  .bx-meter .foot {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['dim']}; margin-top: 5px; }}

  /* ---- KPI strip ---- */
  .bx-kpis {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
    gap: 1px; background: {t['line']}; border: 1px solid {t['line']};
    border-radius: 4px; overflow: hidden; margin-bottom: 4px;
  }}
  .bx-kpi {{ background: {t['panel']}; padding: 11px 13px; }}
  .bx-kpi .k {{ font-size: 9.5px; letter-spacing: .11em; text-transform: uppercase; color: {t['dim']}; margin-bottom: 4px; }}
  .bx-kpi .v {{ font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }}
  .bx-kpi .s {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['dim']}; margin-top: 3px; }}

  /* ---- ranked probability bars ---- */
  .bx-prob {{ display: grid; grid-template-columns: 78px minmax(0,1fr) 48px; align-items: center; gap: 10px; padding: 2px 0; }}
  .bx-prob .n {{ font-size: 12px; color: {t['ink2']}; text-align: right; }}
  .bx-prob.top .n {{ color: {t['ink']}; font-weight: 600; }}
  .bx-prob .track {{ display: block; height: 12px; background: {t['line']}; border-radius: 2px; overflow: hidden; }}
  /* display:block is load-bearing -- these are spans, and an inline element
     ignores width/height outright (the bar renders 0x0 without it). */
  .bx-prob .fill {{ display: block; height: 100%; min-width: 3px; background: {t['bar_mute']}; border-radius: 0 2px 2px 0; }}
  .bx-prob.top .fill {{ background: {t['bar_emph']}; }}
  .bx-prob .p {{
    font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['dim']};
    font-variant-numeric: tabular-nums; text-align: right;
  }}
  .bx-prob.top .p {{ color: {t['ink']}; }}

  /* ---- engine status ---- */
  .bx-status {{ display: flex; gap: 8px; align-items: flex-start; margin-bottom: 9px; }}
  .bx-status .dot {{ width: 7px; height: 7px; border-radius: 50%; margin-top: 6px; flex: none; }}
  .bx-status .nm {{ font-size: 12px; color: {t['ink2']}; line-height: 1.35; }}
  .bx-status .mt {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['dim']}; }}

  /* ---- detections log ---- */
  .bx-tablewrap {{ overflow-x: auto; border: 1px solid {t['line']}; border-radius: 4px; }}
  table.bx-log {{ width: 100%; border-collapse: collapse; min-width: 680px; background: {t['panel']}; }}
  table.bx-log thead th {{
    text-align: left; font-size: 9.5px; letter-spacing: .11em; text-transform: uppercase;
    color: {t['dim']}; font-weight: 500; padding: 8px 13px; white-space: nowrap;
    border-bottom: 1px solid {t['line']}; background: {t['panel2']};
  }}
  table.bx-log td {{ padding: 8px 13px; border-bottom: 1px solid {t['line_soft']}; font-size: 12px; }}
  table.bx-log tr:last-child td {{ border-bottom: 0; }}
  table.bx-log td.m {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['dim']}; font-variant-numeric: tabular-nums; }}
  table.bx-log td.h {{ font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: {t['ink2']}; }}
  .bx-sev {{ display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; }}
  .bx-sev i {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }}

  .bx-note {{
    border: 1px solid {t['line']}; border-left: 2px solid {t['accent_dim']};
    border-radius: 4px; padding: 12px 15px; background: {t['panel']};
    font-size: 12.5px; color: {t['ink2']}; line-height: 1.6;
  }}
  .bx-note strong {{ color: {t['ink']}; font-weight: 600; }}

  @media (max-width: 720px) {{
    .bx-band {{ grid-template-columns: 1fr; }}
  }}
</style>
"""


def severity_chip(severity: str) -> str:
    colour = SEVERITY.get(severity, TOKENS["dim"])
    return (f'<span class="bx-chip" style="color:{colour};border-color:{colour}66;'
            f'background:{colour}1a">● {_esc(severity)}</span>')


def verdict_band(verdict: str, severity: str, confidence: float, meta: str,
                 threshold: float = 0.60) -> str:
    colour = SEVERITY.get(severity, TOKENS["accent"])
    return f"""
<div class="bx-band" style="border-left:3px solid {colour};
     background:linear-gradient(90deg,{colour}1a,{colour}00 58%)">
  <div>
    <div class="line1"><span class="name">{_esc(verdict)}</span>{severity_chip(severity)}</div>
    <div class="meta">{_esc(meta)}</div>
  </div>
  <div class="bx-meter">
    <div class="head"><span>Confidence</span><span class="val">{confidence:.1%}</span></div>
    <div class="track">
      <div class="fill" style="width:{min(confidence, 1.0) * 100:.1f}%"></div>
      <div class="mark" style="left:{threshold * 100:.0f}%"></div>
    </div>
    <div class="foot">action threshold {threshold:.0%}</div>
  </div>
</div>
"""


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
            f'<span class="track"><span class="fill" style="width:{value * 100:.1f}%"></span></span>'
            f'<span class="p">{value * 100:.1f}%</span></div>'
        )
    return "".join(rows)


def engine_status(name: str, detail: str, ok: bool = True) -> str:
    colour = SEVERITY["Low"] if ok else TOKENS["dim"]
    shadow = f"box-shadow:0 0 0 3px {colour}26;" if ok else ""
    return (f'<div class="bx-status"><span class="dot" style="background:{colour};{shadow}"></span>'
            f'<div><div class="nm">{_esc(name)}</div><div class="mt">{_esc(detail)}</div></div></div>')


def detections_table(rows: list[dict]) -> str:
    if not rows:
        return ('<div class="bx-note">No detections yet this session. '
                "Classify a capture and it will be listed here.</div>")
    body = []
    for r in rows:
        colour = SEVERITY.get(r["severity"], TOKENS["dim"])
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
    the pages promise nothing is written to disk, and a SOC log that
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
