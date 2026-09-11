"""UI layer for the BEACON dashboard — a command-console analyst UI with
a real dark/light theme toggle (not just an OS-preference read), Material
Symbols instead of emoji for every icon, and the BEACON mark as the brand
mark instead of a generic glyph.

Colour roles are duplicated per theme (LIGHT_TOKENS / DARK_TOKENS) rather
than computed from one set, because a computed flip reliably produces bad
contrast somewhere -- both palettes are hand-picked and internally
consistent with pipeline/viz.py's chart palettes. Every component reads
the ACTIVE theme via tokens()/severity_colors(), never the module-level
dicts directly, so flipping the toggle re-themes every page in one place.
Severity/risk always ships with an icon or dot alongside the label, so
colour never carries the meaning alone.
"""
from __future__ import annotations

import base64
import html
import os

import pandas as pd

_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

LIGHT_TOKENS = {
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
    "badge_bg": "#0a0e1a",  # the logo mark keeps its native dark badge in both themes
}

DARK_TOKENS = {
    "bg": "#080b14",
    "panel": "#111827",
    "panel2": "#0b1120",
    "line": "#1f2a44",
    "ink": "#f3f6ff",
    "ink2": "#a9b4d0",
    "muted": "#6b7793",
    "accent": "#22d3ee",
    "accent_ink": "#67e8f9",
    "accent_soft": "rgba(34,211,238,.14)",
    "bar_mute": "#233048",
    "badge_bg": "#0a0e1a",
}

# Reserved status palette -- never reused for a data series. Dark gets its
# own brighter steps rather than the light palette's values, which read as
# muddy/low-contrast against a near-black panel.
SEVERITY = {
    "light": {"Low": "#1f9d6f", "Medium": "#c98a1c", "High": "#d9642e", "Critical": "#d1454b"},
    "dark": {"Low": "#34d399", "Medium": "#fbbf24", "High": "#fb923c", "Critical": "#f87171"},
}
SEVERITY_SOFT = {
    "light": {"Low": "#e3f6ee", "Medium": "#fbf1de", "High": "#fceee4", "Critical": "#fbe8e8"},
    "dark": {"Low": "rgba(52,211,153,.14)", "Medium": "rgba(251,191,36,.14)",
             "High": "rgba(251,146,60,.14)", "Critical": "rgba(248,113,113,.14)"},
}

# One Material Symbol per category so the verdict card always carries an
# icon, not colour alone -- same rule the severity chip follows.
CATEGORY_ICON = {
    "Benign": "check_circle", "Backdoor": "sensor_door", "Exploit": "bolt",
    "HackTool": "build", "Hoax": "help", "Rootkit": "bug_report",
    "Trojan": "warning", "Virus": "coronavirus", "Worm": "pest_control",
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


def current_theme_name() -> str:
    """'dark' or 'light' -- the single source of truth every page and
    chart call reads, so the toggle and every themed surface agree."""
    import streamlit as st

    # `.get(..., "dark")` alone isn't enough: st.segmented_control lets a
    # single-select pill be clicked again to DESELECT it, which sets
    # session_state["beacon_theme"] to None (a present key, not a missing
    # one) rather than leaving the old choice in place -- `or` catches
    # that explicit-None case the same as a never-set key.
    return st.session_state.get("beacon_theme") or "dark"


def tokens() -> dict:
    return DARK_TOKENS if current_theme_name() == "dark" else LIGHT_TOKENS


def severity_colors() -> dict:
    return SEVERITY[current_theme_name()]


def severity_soft() -> dict:
    return SEVERITY_SOFT[current_theme_name()]


def theme_toggle() -> None:
    """Sidebar dark/light switch. Bound directly to session_state via
    `key` so every other themed call in this same rerun (tokens(),
    inject_theme(), the Altair charts) already sees the new choice --
    Streamlit applies a widget's pending value before the script reruns,
    not after this line executes."""
    import streamlit as st

    st.session_state.setdefault("beacon_theme", "dark")
    render(nav_label("Appearance"))
    st.segmented_control(
        "Theme", options=["dark", "light"], format_func=str.capitalize,
        key="beacon_theme", label_visibility="collapsed",
    )


def _logo_data_uri() -> str:
    path = os.path.join(_ASSET_DIR, "logo-mark.png")
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def icon(name: str, size: int = 18, color: str | None = None) -> str:
    """A Material Symbol as an inline span, for use inside render()'d HTML
    (raw st.html() output bypasses Streamlit's own `:material/x:` markdown
    shorthand, so components need this instead).

    Deliberately reuses Streamlit's OWN self-hosted "Material Symbols
    Rounded" font -- the one its native `:material/x:` icons already load
    -- rather than importing a second icon font (Outlined) from Google
    Fonts: that import loaded as CSS but Chromium never actually fetched
    the variable-font file, leaving every custom icon rendering as literal
    ligature text ("grid_view") instead of a glyph. Reusing Streamlit's
    font sidesteps that and keeps every icon visually consistent besides."""
    style = f"font-size:{size}px;line-height:1;vertical-align:middle"
    if color:
        style += f";color:{color}"
    return f'<span class="bx-icon" style="{style}">{_esc(name)}</span>'


def inject_theme() -> str:
    t = tokens()
    dark = current_theme_name() == "dark"
    shadow = "0 1px 2px rgba(0,0,0,.35)" if dark else "0 1px 2px rgba(21,27,44,.04)"
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Orbitron:wght@700;800;900&display=swap">
<style>
  /* [data-testid*="Icon"] (not just stIconMaterial) is load-bearing --
     Streamlit uses several icon testids (stIconMaterial for nav/buttons,
     stAlertDynamicIcon for st.info/warning/error, more elsewhere), all
     rendered as Material Symbols ligatures. Missing any of them forces
     Inter onto that span, which has no such ligature, so the icon shows
     as literal text ("upload_file") instead of a glyph. */
  html, body, [class*="st-"]:not([data-testid*="Icon"]):not(.bx-icon),
  .stMarkdown, button, input, textarea {{
    font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
  }}
  /* Reuses Streamlit's own self-hosted "Material Symbols Rounded" font --
     the one its native `:material/x:` icons already load -- so custom
     icon() spans need no font import of their own and always match. */
  .bx-icon {{
    font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal;
    display: inline-block; white-space: nowrap; word-wrap: normal; direction: ltr;
    -webkit-font-feature-settings: "liga"; font-feature-settings: "liga";
  }}
  .stApp {{ background: {t['bg']}; }}
  /* Safety net: Streamlit's static config.toml theme (fixed at "dark")
     sets the page's root text colour, so any custom element rendered via
     st.html() that doesn't set its OWN colour explicitly inherits that
     static value -- fine while the in-app toggle is also dark, invisible
     once toggled to light. Give st.html() output a sane themed default;
     every component that already sets its own colour is unaffected. */
  .stHtml {{ color: {t['ink2']}; }}
  .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }}
  h1 {{ font-size: 1.7rem !important; font-weight: 800 !important; letter-spacing: -.02em; color: {t['ink']} !important; }}
  h2 {{ font-size: 1rem !important; font-weight: 700 !important; color: {t['ink']} !important; }}
  h3 {{ font-size: .92rem !important; font-weight: 700 !important; color: {t['ink']} !important; }}
  p, .stCaption, .stMarkdown p {{ color: {t['ink2']} !important; }}
  hr {{ border-color: {t['line']}; margin: 1.1rem 0; }}
  /* Inline code spans default to Streamlit's static config theme's code
     styling (always dark), which clashed once toggled away from dark. */
  code {{ background: {t['panel2']} !important; color: {t['accent_ink']} !important;
    border-radius: 4px; }}
  /* Global, not scoped to .bx-card: a "sub" caption appears standalone
     inside st.container(border=True) panels too (no .bx-card ancestor
     there), and without !important it silently fell back to Streamlit's
     own base-theme text colour instead of the active toggle's palette. */
  .sub {{ font-size: 12px; color: {t['muted']} !important; margin: 0 0 14px; }}

  /* ---- sidebar: native page nav + status footer ---- */
  [data-testid="stSidebar"] {{ background: {t['panel']}; border-right: 1px solid {t['line']}; }}
  /* padding-top clears the fixed sidebar_brand_bar() overlay (see below) --
     it needs to be taller than that bar so the nav's first item doesn't
     render underneath it. */
  /* This padding-top is NOT measured from the viewport (where the fixed
     brand bar sits) -- stSidebarNav's own box already starts 76px down
     (Streamlit's native offset, unrelated to anything here) before this
     padding is even added, and the first link then sits ~3px inside
     that. So: bar height + a tight 6px visible gap - 76px native offset
     - 3px inner offset = padding-top. This constant tracks the current
     logo image's aspect ratio and needs re-measuring in a live browser,
     not recomputing on paper, whenever that image changes. */
  [data-testid="stSidebarNav"] {{ padding-top: 102px; }}
  [data-testid="stSidebarNav"] a {{ border-radius: 8px; margin: 1px 8px; padding: 2px 4px; }}
  [data-testid="stSidebarNav"] a p {{ font-size: .87rem; font-weight: 500; color: {t['ink2']}; }}
  [data-testid="stSidebarNav"] a span[data-testid="stIconMaterial"] {{ color: {t['muted']}; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {t['accent_soft']}; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] p {{ color: {t['accent_ink']}; font-weight: 600; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] span[data-testid="stIconMaterial"] {{ color: {t['accent_ink']}; }}
  [data-testid="stSidebarNav"] a:hover {{ background: {t['panel2']}; }}

  .bx-navlabel {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .12em;
    text-transform: uppercase; color: {t['muted']}; margin: 16px 10px 4px; }}
  .bx-label {{ font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
    color: {t['muted']}; margin: 2px 0 8px; }}
  .bx-mono {{ font-family: "IBM Plex Mono", ui-monospace, monospace; }}

  /* ---- sidebar theme toggle ---- */
  [data-testid="stSidebar"] div[data-testid="stSegmentedControl"] {{ padding: 0 8px; }}

  /* ---- cards ---- */
  .bx-card {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 12px;
    padding: 20px; box-shadow: {shadow}; }}
  .bx-card h2 {{ margin: 0 0 3px; }}

  /* Streamlit's own bordered container (st.container(border=True)), re-skinned
     to match .bx-card so a chart/table can sit INSIDE a themed panel border --
     raw HTML cards can't wrap native widgets, this can. */
  [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]) {{
    background: {t['panel']}; border: 1px solid {t['line']} !important; border-radius: 12px !important;
    box-shadow: {shadow};
  }}
  [data-testid="stVerticalBlockBorderWrapper"] {{ background: {t['panel']}; border-color: {t['line']} !important;
    border-radius: 12px !important; box-shadow: {shadow}; }}

  /* ---- file-upload drop zone reskin ---- */
  [data-testid="stFileUploaderDropzone"] {{
    background: {t['panel2']} !important; border: 1.5px dashed {t['line']} !important;
    border-radius: 10px !important;
  }}
  [data-testid="stFileUploaderDropzoneInstructions"] svg {{ display:none; }}
  [data-testid="stFileUploaderDropzoneInstructions"] span,
  [data-testid="stFileUploaderDropzoneInstructions"] small {{ color: {t['ink2']}; }}
  /* the uploaded-file chip that appears after a file is picked -- also
     unthemed by default, so it stayed dark-config-styled against a
     light dropzone once toggled to light. */
  [data-testid="stFileChip"] {{ background: {t['panel']} !important; border-radius: 8px; }}
  [data-testid="stFileChip"] * {{ color: {t['ink2']} !important; }}
  [data-testid="stFileChip"] svg {{ fill: {t['ink2']} !important; }}

  /* ---- verdict card ---- */
  .bx-verdict {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }}
  .bx-vicon {{ width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center;
    justify-content: center; flex: none; }}
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
  .bx-chip {{ display: inline-flex; align-items: center; gap: 6px;
    font-family: "IBM Plex Mono", monospace; font-size: 10.5px; font-weight: 700;
    padding: 3px 9px; border-radius: 99px; }}

  .bx-note {{ border: 1px solid {t['line']}; border-radius: 9px; padding: 12px 14px;
    background: {t['panel2']}; font-size: 12px; color: {t['ink2']}; line-height: 1.55; }}
  .bx-note strong {{ color: {t['ink']}; font-weight: 700; }}

  /* ---- feature / stat strip (icon tiles) ---- */
  .bx-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px; margin-bottom: 4px; }}
  .bx-stat {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 12px;
    padding: 15px 16px; display: flex; gap: 12px; align-items: flex-start; }}
  .bx-stat .ic {{ width: 36px; height: 36px; border-radius: 9px; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center; flex: none; }}
  .bx-stat .t {{ font-weight: 700; font-size: 13.5px; color: {t['ink']}; margin-bottom: 2px; }}
  .bx-stat .d {{ font-size: 11.5px; color: {t['muted']}; line-height: 1.4; }}

  /* ---- numeric run-stats (KPI grid), optionally with a leading icon ---- */
  .bx-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 1px; background: {t['line']}; border: 1px solid {t['line']};
    border-radius: 10px; overflow: hidden; margin-bottom: 4px; }}
  .bx-kpi {{ background: {t['panel']}; padding: 14px 16px; }}
  .bx-kpi .ic {{ width: 30px; height: 30px; border-radius: 8px; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }}
  .bx-kpi .k {{ font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; color: {t['muted']}; margin-bottom: 4px; }}
  .bx-kpi .v {{ font-size: 19px; font-weight: 700; font-variant-numeric: tabular-nums; color: {t['ink']}; letter-spacing: -.01em; }}
  .bx-kpi .s {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; color: {t['muted']}; margin-top: 3px; }}
  .bx-kpi .s.ok {{ color: {SEVERITY[current_theme_name()]['Low']}; }}

  /* ---- ranked probability bars ---- */
  .bx-prob {{ display: grid; grid-template-columns: 76px minmax(0,1fr) 44px; align-items: center; gap: 10px; padding: 3px 0; }}
  .bx-prob .n {{ font-size: 12px; color: {t['ink2']}; text-align: right; font-weight: 500; }}
  .bx-prob.top .n {{ color: {t['accent_ink']}; font-weight: 700; }}
  .bx-prob .ptrack {{ display: block; height: 10px; background: {t['panel2']}; border: 1px solid {t['line']};
    border-radius: 5px; overflow: hidden; }}
  .bx-prob .pfill {{ display: block; height: 100%; min-width: 3px; background: {t['bar_mute']}; border-radius: 0 4px 4px 0; }}
  .bx-prob.top .pfill {{ background: {t['accent']}; }}
  .bx-prob .p {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['muted']};
    font-variant-numeric: tabular-nums; text-align: right; }}
  .bx-prob.top .p {{ color: {t['ink']}; font-weight: 600; }}

  /* ---- model status cards ---- */
  .bx-streamcard {{ display: flex; align-items: flex-start; gap: 11px; padding: 13px;
    border-radius: 10px; border: 1px solid {t['line']}; margin-bottom: 10px; }}
  .bx-streamcard .ic {{ width: 34px; height: 34px; border-radius: 8px; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center; flex: none; }}
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
  table.bx-log thead th {{ text-align: left; font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase;
    color: {t['muted']}; font-weight: 600; padding: 9px 13px; white-space: nowrap;
    border-bottom: 1px solid {t['line']}; background: {t['panel2']}; }}
  table.bx-log td {{ padding: 9px 13px; border-bottom: 1px solid {t['line']}; font-size: 12px; color: {t['ink2']}; }}
  table.bx-log tr:last-child td {{ border-bottom: 0; }}
  table.bx-log td.m {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; color: {t['muted']}; font-variant-numeric: tabular-nums; }}
  table.bx-log td.h {{ font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: {t['ink2']}; }}
  .bx-sev {{ display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 600; }}
  .bx-sev i {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }}

  /* ---- confidence ring ---- */
  .bx-ring-wrap {{ display: flex; flex-direction: column; align-items: center; gap: 6px; }}
  .bx-ring {{ width: 108px; height: 108px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; position: relative; }}
  .bx-ring::before {{ content: ""; position: absolute; inset: 10px; border-radius: 50%; background: {t['panel']}; }}
  .bx-ring .v {{ position: relative; font-size: 21px; font-weight: 800; color: {t['ink']}; letter-spacing: -.01em; }}
  .bx-ring-label {{ font-size: 10.5px; color: {t['muted']}; font-weight: 600; }}

  /* ---- SHAP ranked table ---- */
  .bx-shaptable {{ width: 100%; border-collapse: collapse; }}
  .bx-shaptable th {{ text-align: left; font-size: 9.5px; letter-spacing: .08em; text-transform: uppercase;
    color: {t['muted']}; font-weight: 600; padding: 0 0 8px; }}
  .bx-shaptable td {{ padding: 7px 0; border-top: 1px solid {t['line']}; font-size: 12.5px; color: {t['ink2']}; vertical-align: middle; }}
  .bx-shaptable td.rank {{ color: {t['muted']}; font-family: "IBM Plex Mono", monospace; width: 22px; }}
  .bx-shaptable td.feat {{ color: {t['ink']}; font-weight: 600; }}
  .bx-shaptable td.bar {{ width: 42%; }}
  .bx-shapbar-track {{ height: 8px; border-radius: 4px; background: {t['panel2']}; overflow: hidden; display: flex; }}
  .bx-shapbar-fill {{ display: block; height: 100%; border-radius: 4px; }}
  .bx-shaptable td.val {{ font-family: "IBM Plex Mono", monospace; text-align: right; white-space: nowrap; }}

  /* ---- analysis workflow stepper ---- */
  .bx-steps {{ display: flex; align-items: flex-start; gap: 4px; }}
  .bx-step {{ flex: 1; display: flex; flex-direction: column; align-items: center; text-align: center;
    position: relative; padding-top: 4px; }}
  .bx-step .num {{ width: 30px; height: 30px; border-radius: 50%; background: {t['accent_soft']};
    color: {t['accent_ink']}; display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; margin-bottom: 8px; }}
  .bx-step .t {{ font-size: 12.5px; font-weight: 700; color: {t['ink']}; }}
  .bx-step .d {{ font-size: 10.5px; color: {t['muted']}; margin-top: 2px; }}
  .bx-step::before {{ content: ""; position: absolute; top: 19px; left: -50%; width: 100%; height: 1px;
    background: {t['line']}; z-index: 0; }}
  .bx-step:first-child::before {{ display: none; }}

  /* ---- sidebar brand bar: fixed, overlays the top-left corner ----
     st.navigation()'s menu always renders at the very top of the sidebar
     regardless of where a brand block is placed in the script, so normal
     document flow can't put anything above it -- position:fixed escapes
     that entirely (verified empirically: content is rendered where this
     CSS puts it, not where Streamlit would have placed a static block).
     A transformed ancestor becomes the containing block for a fixed
     descendant, so this still slides away with the sidebar's own
     collapse animation rather than staying stranded on screen. */
  /* Fixed dark background, like the hero banner -- the logo image's own
     glow assumes a dark ground and would look wrong against a white
     sidebar panel the moment the toggle switched to light. Padding is
     tight on purpose: this bar's own height sets how far the nav below
     has to be pushed down (see stSidebarNav padding-top), so slack here
     directly becomes dead space there. */
  .bx-sidebar-brand {{ position: fixed; top: 0; left: 0; z-index: 1000; width: 300px;
    padding: 10px 14px 6px; background: #0a0e1a; border-bottom: 1px solid #1c2740;
    border-right: 1px solid #1c2740; line-height: 0; text-align: center; }}
  .bx-sidebar-brand img {{ width: 220px; height: auto; display: inline-block; border-radius: 8px; }}

  /* ---- hero banner: full-width, always dark regardless of the toggle
     (a brand splash, not page body content) -- the cover photo assumes a
     dark ground and would look wrong recoloured. ---- */
  .bx-hero {{ position: relative; overflow: hidden; border-radius: 14px;
    background: #080b14; padding: 20px 24px; margin-bottom: 20px;
    display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap; }}
  /* An IMG element, not an inline SVG element -- st.html() strips raw SVG
     tags (a sanitizer default), silently dropping content with no error.
     Even mentioning the angle-bracket spelling of these tag names in a
     CSS comment is enough to trigger the same stripping mid-stylesheet
     and silently drop unrelated rules after it -- found by bisecting this
     exact file, not by reasoning about it -- so this comment spells them
     out as plain words instead.
     object-fit:cover (not the default fill from width/height:100%) is
     load-bearing too -- without it the source photo stretches to match
     the banner's actual aspect ratio, distorting it. */
  .bx-hero-bg {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0;
    object-fit: cover; object-position: center; }}
  /* Dark-to-transparent scrim over the photo so the title text (which
     sits on the left) stays legible regardless of how bright that
     region of the source photo is. */
  .bx-hero-scrim {{ position: absolute; inset: 0; z-index: 0;
    background: linear-gradient(90deg, #050810 0%, rgba(5,8,16,.88) 32%, rgba(5,8,16,.35) 60%, rgba(5,8,16,.15) 100%); }}
  /* A named class, not a bare `> *` or `> div` -- either would also match
     the background IMG and the scrim (both also direct children) and,
     being later in source order at equal specificity, silently override
     their position:absolute back to relative, collapsing them into
     normal flex flow and making them invisible. Learned that the hard
     way once already with `> *`; naming the two real content blocks
     explicitly instead of matching "whatever's left" avoids repeating it
     with the scrim div. */
  .bx-hero-content {{ position: relative; z-index: 1; }}
  .bx-eyebrow {{ font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .16em;
    color: #67e8f9; text-transform: uppercase; margin-bottom: 2px; }}

  @media (max-width: 720px) {{ .bx-verdict {{ flex-wrap: wrap; }} .bx-sidebar-brand {{ position: static; width: auto; }} }}
</style>
"""


def _hero_cover_data_uri() -> str:
    path = os.path.join(_ASSET_DIR, "hero-cover.jpg")
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def sidebar_brand_bar() -> str:
    """Fixed brand bar overlaying the sidebar's top-left corner -- see the
    .bx-sidebar-brand CSS comment for why position:fixed is what makes
    this actually render above st.navigation()'s menu.

    Renders the supplied logo image as-is (it already carries the
    "BEACON" wordmark and tagline baked in) rather than cropping out just
    the icon and re-setting the name in a separate custom wordmark --
    one image, no extraction, no duplicated text."""
    return f'<div class="bx-sidebar-brand"><img src="{_logo_data_uri()}" alt="BEACON"></div>'


def _acronym_line() -> str:
    """"BEACON" spelled out, with the letters that form the name picked
    out in the accent colour -- stands in for repeating the wordmark
    itself, which already sits one tab away in the sidebar."""
    letters = [("B", "ehavioral"), ("E", "xplainable"), ("A", "I for"),
               ("C", "yber"), ("O", "perations"), ("N", "etwork")]
    words = " ".join(
        f'<span style="color:#67e8f9">{i}</span>{rest}' for i, rest in letters
    )
    return (f'<div style="font-size:18px;font-weight:700;letter-spacing:.01em;'
            f'color:#e2e8f0">{words}</div>')


def header_band(intro: str, eyebrow: str = "CYBER COMMAND CENTER",
                tags: str = "OBSERVE &middot; ANALYZE &middot; EXPLAIN &middot; DEFEND") -> str:
    """Full-width hero banner above the page content: eyebrow + the
    "BEACON" acronym spelled out + a one-line intro, over the cover
    photo, with live status tags on the right. The brand mark and
    wordmark themselves live in the sidebar (see sidebar_brand_bar()) --
    repeating the "BEACON" title here as well read as redundant, so this
    banner carries the acronym expansion instead."""
    import datetime

    now = datetime.datetime.now().strftime("%b %d, %Y &middot; %H:%M")
    return f"""
<div class="bx-hero">
  <img class="bx-hero-bg" src="{_hero_cover_data_uri()}" alt="">
  <div class="bx-hero-scrim"></div>
  <div class="bx-hero-content">
    <div class="bx-eyebrow">{_esc(eyebrow)}</div>
    {_acronym_line()}
    <div style="font-size:12.5px;color:#94a3b8;margin-top:5px;max-width:440px">{_esc(intro)}</div>
  </div>
  <div class="bx-hero-content" style="text-align:right;background:rgba(5,8,16,.55);
       padding:8px 14px;border-radius:9px;backdrop-filter:blur(2px)">
    <div class="bx-mono" style="font-size:10px;letter-spacing:.14em;color:#64748b;
         text-transform:uppercase;white-space:nowrap;margin-bottom:6px">{tags}</div>
    <div style="display:flex;align-items:center;justify-content:flex-end;gap:14px">
      <span class="bx-mono" style="font-size:11.5px;color:#cbd5e1">{now}</span>
      <span style="display:inline-flex;align-items:center;gap:6px;font-size:11.5px;
            font-weight:600;color:#34d399">
        <i style="width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block"></i>
        System Online
      </span>
    </div>
  </div>
</div>
"""


def top_bar() -> str:
    """Deprecated alias for header_band(), kept so any remaining call site
    doesn't break; new code should call header_band() directly."""
    return header_band("Explainable malware detection from network-flow "
                        "and memory-forensic telemetry")


def nav_label(text: str) -> str:
    return f'<div class="bx-navlabel">{_esc(text)}</div>'


def severity_chip(severity: str) -> str:
    colour = severity_colors().get(severity, tokens()["muted"])
    soft = severity_soft().get(severity, tokens()["panel2"])
    return (f'<span class="bx-chip" style="color:{colour};background:{soft}">'
            f'● {_esc(severity)}</span>')


def verdict_card(verdict: str, severity: str, confidence: float, meta: str,
                 threshold: float = 0.60, example: bool = False) -> str:
    t = tokens()
    colour = severity_colors().get(severity, t["accent"])
    soft = severity_soft().get(severity, t["accent_soft"])
    ic = icon(CATEGORY_ICON.get(verdict, "help"), size=21, color=colour)
    badge = (f'<span class="bx-chip" style="background:{t["accent_soft"]};color:{t["accent_ink"]}">'
             f'LABELLED EXAMPLE</span>') if example else ""
    return f"""
<div class="bx-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
    <h2 style="margin:0">Result</h2>{badge}
  </div>
  <div style="height:10px"></div>
  <div class="bx-verdict">
    <div class="bx-vicon" style="background:{soft}">{ic}</div>
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


def confidence_ring(confidence: float, colour: str | None = None, label: str = "CONFIDENCE") -> str:
    """A circular gauge (CSS conic-gradient) for the Dashboard's results
    panel -- confidence is the single headline number there, so it gets a
    stat-tile treatment rather than competing for space with a bar chart."""
    t = tokens()
    c = colour or t["accent"]
    pct = max(0.0, min(1.0, confidence)) * 360
    return f"""
<div class="bx-ring-wrap">
  <div class="bx-ring" style="background:conic-gradient({c} {pct}deg, {t['panel2']} {pct}deg)">
    <span class="v">{confidence:.0%}</span>
  </div>
  <div class="bx-ring-label">{_esc(label)}</div>
</div>
"""


def data_preview_table(df: pd.DataFrame, max_rows: int = 5, max_cols: int = 10) -> str:
    """A themed preview table -- native st.dataframe renders via a canvas
    widget that follows Streamlit's static config theme, not this app's
    in-app dark/light toggle, so it looked wrong (a dark grid inside a
    light card) as soon as the toggle left its default. Truncated to
    max_cols since a Network capture carries 342 raw columns."""
    t = tokens()
    cols = list(df.columns[:max_cols])
    truncated_cols = len(df.columns) > max_cols
    rows = df[cols].head(max_rows)
    head = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    if truncated_cols:
        head += f'<th style="color:{t["muted"]}">&hellip; +{len(df.columns) - max_cols} more</th>'
    body_rows = []
    for _, row in rows.iterrows():
        cells = "".join(f"<td>{_esc(row[c])}</td>" for c in cols)
        if truncated_cols:
            cells += "<td></td>"
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="bx-tablewrap"><table class="bx-log">'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    )


def metrics_table(rows: list[dict], columns: list[str]) -> str:
    """A themed table for a small results grid (e.g. the Methodology page's
    measured-results table) -- native st.dataframe renders via a canvas
    widget that follows Streamlit's static config theme, not this app's
    in-app dark/light toggle, so it looked wrong there too."""
    head = "".join(f"<th>{_esc(c)}</th>" for c in columns)
    body = []
    for r in rows:
        cells = "".join(f"<td>{_esc(r[c])}</td>" for c in columns)
        body.append(f"<tr>{cells}</tr>")
    return (f'<div class="bx-tablewrap"><table class="bx-log">'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def stat_strip(items: list[dict]) -> str:
    """items: [{icon, title, desc}] -- icon is a Material Symbol name."""
    cells = "".join(
        f'<div class="bx-stat"><div class="ic">{icon(i["icon"], size=18)}</div>'
        f'<div><div class="t">{_esc(i["title"])}</div><div class="d">{_esc(i["desc"])}</div></div></div>'
        for i in items
    )
    return f'<div class="bx-strip">{cells}</div>'


def kpi_strip(items: list[dict]) -> str:
    """items: [{label, value, sub, icon (optional), ok (optional bool)}]"""
    cells = []
    for i in items:
        ic = f'<div class="ic">{icon(i["icon"], size=16)}</div>' if i.get("icon") else ""
        sub_cls = " ok" if i.get("ok") else ""
        sub = f'<div class="s{sub_cls}">{_esc(i["sub"])}</div>' if i.get("sub") else ""
        cells.append(f'<div class="bx-kpi">{ic}<div class="k">{_esc(i["label"])}</div>'
                     f'<div class="v">{_esc(i["value"])}</div>{sub}</div>')
    return f'<div class="bx-kpis">{"".join(cells)}</div>'


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


def shap_table(top_features: pd.DataFrame) -> str:
    """Ranked #/feature/bar/value table -- an alternative to the diverging
    Altair chart for panels that want a compact list-with-inline-bar look."""
    t = tokens()
    sev = severity_colors()
    max_abs = top_features["shap_value"].abs().max() or 1.0
    rows = []
    for rank, row in enumerate(top_features.itertuples(), start=1):
        toward = row.shap_value >= 0
        colour = t["accent"] if toward else sev["Critical"]
        width = abs(row.shap_value) / max_abs * 100
        rows.append(f"""
<tr>
  <td class="rank">{rank}</td>
  <td class="feat">{_esc(row.feature)}</td>
  <td class="bar"><div class="bx-shapbar-track">
    <span class="bx-shapbar-fill" style="width:{width:.0f}%;background:{colour}"></span>
  </div></td>
  <td class="val" style="color:{colour}">{row.shap_value:+.3f}</td>
</tr>""")
    return (f'<table class="bx-shaptable"><thead><tr><th>#</th><th>Feature</th>'
            f'<th>Contribution</th><th>SHAP value</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def workflow_stepper(steps: list[dict]) -> str:
    """steps: [{icon, title, desc}] -- a static 4-stage process strip
    (Upload -> Classify -> Explain -> Export)."""
    cells = "".join(
        f'<div class="bx-step"><div class="num">{icon(s["icon"], size=16)}</div>'
        f'<div class="t">{_esc(s["title"])}</div><div class="d">{_esc(s["desc"])}</div></div>'
        for s in steps
    )
    return f'<div class="bx-steps">{cells}</div>'


def stream_status_card(name: str, icon_name: str, ok: bool, detail: str) -> str:
    t = tokens()
    sev = severity_colors()
    chip = (f'<span class="bx-chip" style="background:{severity_soft()["Low"]};color:{sev["Low"]}">LIVE</span>' if ok
            else f'<span class="bx-chip" style="background:{severity_soft()["Medium"]};color:{sev["Medium"]}">NOT TRAINED</span>')
    return (f'<div class="bx-streamcard"><div class="ic">{icon(icon_name, size=16)}</div>'
            f'<div style="flex:1"><div class="top"><span class="t">{_esc(name)}</span>{chip}</div>'
            f'<div class="d">{_esc(detail)}</div></div></div>')


def engine_status(name: str, detail: str, ok: bool = True) -> str:
    colour = severity_colors()["Low"] if ok else tokens()["muted"]
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
    sev = severity_colors()
    body = []
    for r in rows:
        colour = sev.get(r["severity"], tokens()["muted"])
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
