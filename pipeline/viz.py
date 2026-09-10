"""Chart and palette layer for the BEACON dashboard.

Colours live here rather than in the pages so light/dark swap in one
place and every chart is written against roles, not raw hex.

Form choices (decided before colour, per the data's job):
  * Class probabilities -- one class IS the answer and the other eight are
    context, so this is the EMPHASIS form (accent + de-emphasis gray), not
    nine categorical hues. Nine competing colours would bury the one bar
    that matters.
  * SHAP contributions -- polarity (toward vs away from the verdict), so a
    DIVERGING bar: two hues with a neutral gray midpoint.
  * Verdict / confidence / risk -- single headline values, so stat tiles,
    not one-bar charts.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

# Validated reference palette. Light/dark are selected steps of the same
# hues, not an automatic flip.
LIGHT = {
    "surface": "#fcfcfb",
    "text_primary": "#0b0b0b",
    "text_secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    "accent": "#2a78d6",      # sequential/emphasis hue
    # Muted step, not the lighter baseline gray: the baseline sits at
    # 1.75:1 on this surface and the de-emphasis bars would be nearly
    # invisible. Validated at >=3:1 with CVD dE 15.9 against the accent.
    "deemphasis": "#898781",
    "diverge_pos": "#2a78d6",  # pushes toward the verdict
    "diverge_neg": "#e34948",  # pushes away
}

DARK = {
    "surface": "#1a1a19",
    "text_primary": "#ffffff",
    "text_secondary": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "baseline": "#383835",
    "accent": "#3987e5",
    "deemphasis": "#898781",
    "diverge_pos": "#3987e5",
    "diverge_neg": "#e66767",
}

# Reserved status palette -- never reused for a data series. Always shipped
# with an icon + label so colour never carries the meaning alone.
STATUS = {
    "Low": ("#0ca30c", "🟢"),
    "Medium": ("#fab219", "🟡"),
    "High": ("#ec835a", "🟠"),
    "Critical": ("#d03b3b", "🔴"),
}


def palette(theme: str = "light") -> dict:
    return DARK if theme == "dark" else LIGHT


def load_metrics(stream: str) -> dict | None:
    """Read models/<stream>_metrics.json, or None if not trained yet."""
    import json
    import os

    # Anchored to this file, not the process CWD. A relative "models/..."
    # silently returned None whenever the app was launched from anywhere
    # but the repo root, which drops every accuracy figure from the UI
    # rather than raising -- the failure mode is a missing number, not an
    # error message.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "models", f"{stream}_metrics.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def headline(metrics: dict | None, unit: str | None = None) -> dict | None:
    """Pull (accuracy, macro_f1, n) out of a metrics file.

    The two streams' files are shaped differently -- Network nests
    flow_level/sample_level, Memory is flat -- and Memory records accuracy
    only inside its classification report. Reading defensively here keeps
    that difference out of every page.

    unit: "flow" or "sample" to select a Network block; None picks the
    best available (sample level, else flat).
    """
    if not metrics:
        return None

    block = metrics
    if unit == "flow" and "flow_level" in metrics:
        block = metrics["flow_level"]
    elif unit == "sample" and "sample_level" in metrics:
        block = metrics["sample_level"]
    elif "sample_level" in metrics:
        block = metrics["sample_level"]
    elif "flow_level" in metrics:
        block = metrics["flow_level"]

    report = block.get("classification_report") or block.get("test_classification_report") or {}
    accuracy = block.get("test_accuracy", report.get("accuracy"))
    n = (block.get("n_test_samples") or block.get("n_test_flows")
         or block.get("test_rows") or metrics.get("test_rows"))
    if accuracy is None:
        return None
    return {"accuracy": float(accuracy),
            "macro_f1": float(block.get("test_macro_f1", 0.0)),
            "n": int(n) if n else 0}


def detect_theme() -> str:
    """Streamlit exposes the viewer's theme; fall back to light."""
    try:
        import streamlit as st

        return "dark" if getattr(st.context.theme, "type", "light") == "dark" else "light"
    except Exception:
        return "light"


def _base(chart: alt.Chart, p: dict) -> alt.Chart:
    """Recessive chrome: hairline grid, muted axis ink, transparent surface
    so the chart sits on the page plane rather than a competing panel."""
    # configure(background=...) rather than configure_background(): the
    # latter doesn't exist on a LayerChart, and both charts here are layered.
    return chart.configure_view(stroke=None).configure_axis(
        grid=False,
        domainColor=p["baseline"],
        tickColor=p["baseline"],
        labelColor=p["text_secondary"],
        titleColor=p["muted"],
        labelFontSize=12,
        titleFontSize=11,
    ).configure(background="transparent")


def class_probability_chart(proba: pd.Series, verdict: str, theme: str = "light"):
    """Horizontal emphasis bar: the predicted class in the accent hue, the
    rest in de-emphasis gray, sorted by magnitude and directly labelled."""
    p = palette(theme)
    df = (
        proba.rename("probability")
        .rename_axis("category")
        .reset_index()
        .sort_values("probability", ascending=False)
    )
    df["is_verdict"] = df["category"] == verdict
    df["label"] = (df["probability"] * 100).map(lambda v: f"{v:.1f}%")

    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, height=18)  # 4px rounded data-end
        .encode(
            # labelOverlap=False: Altair silently drops axis labels when
            # bands are tight, which here hid 4 of the 9 categories.
            y=alt.Y("category:N", sort="-x", title=None,
                    axis=alt.Axis(labelFontSize=13, labelOverlap=False,
                                  labelPadding=6)),
            x=alt.X("probability:Q", title="Mean probability",
                    axis=alt.Axis(format="%", values=[0, 0.25, 0.5, 0.75, 1.0]),
                    scale=alt.Scale(domain=[0, 1])),
            color=alt.condition(
                alt.datum.is_verdict,
                alt.value(p["accent"]),
                alt.value(p["deemphasis"]),
            ),
            tooltip=[alt.Tooltip("category:N", title="Category"),
                     alt.Tooltip("probability:Q", title="Probability", format=".2%")],
        )
    )
    # Selective direct labels -- values sit in text ink, never the series colour.
    labels = (
        alt.Chart(df)
        .mark_text(align="left", dx=6, fontSize=12, color=p["text_secondary"])
        .encode(y=alt.Y("category:N", sort="-x"), x="probability:Q", text="label:N")
    )
    # ~34px per band: enough vertical room that every category keeps its label.
    return _base((bars + labels).properties(height=34 * len(df) + 20), p)


def shap_contribution_chart(top_features: pd.DataFrame, theme: str = "light"):
    """Diverging bar around a zero baseline: blue pushes toward the verdict,
    red pushes away, neutral gray midpoint at zero."""
    p = palette(theme)
    df = top_features.copy()
    df["direction"] = df["shap_value"].map(
        lambda v: "Pushes toward" if v >= 0 else "Pushes away")
    df["magnitude"] = df["shap_value"].abs()

    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, height=16)
        .encode(
            y=alt.Y("feature:N", sort=alt.EncodingSortField("magnitude", order="descending"),
                    title=None, axis=alt.Axis(labelFontSize=12, labelLimit=300,
                                              labelOverlap=False, labelPadding=6)),
            x=alt.X("shap_value:Q", title="SHAP contribution"),
            color=alt.Color(
                "direction:N",
                scale=alt.Scale(domain=["Pushes toward", "Pushes away"],
                                range=[p["diverge_pos"], p["diverge_neg"]]),
                legend=alt.Legend(title=None, orient="top", labelColor=p["text_secondary"]),
            ),
            tooltip=[alt.Tooltip("feature:N", title="Feature"),
                     alt.Tooltip("value:Q", title="Scaled value", format=".4f"),
                     alt.Tooltip("shap_value:Q", title="SHAP", format="+.4f")],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"x": [0]}))
        .mark_rule(color=p["baseline"], strokeWidth=1)
        .encode(x="x:Q")
    )
    return _base((zero + bars).properties(height=34 * len(df) + 20), p)


def stat_tile_css(theme: str = "light") -> str:
    """Hairline-ringed tiles; hero value in the system sans, proportional
    figures (tabular is reserved for columns that must align)."""
    p = palette(theme)
    ring = "rgba(255,255,255,0.10)" if theme == "dark" else "rgba(11,11,11,0.10)"
    return f"""
<style>
.beacon-kpi {{ display:flex; gap:12px; flex-wrap:wrap; margin:4px 0 18px; }}
.beacon-tile {{
  flex:1 1 150px; min-width:150px; padding:14px 16px;
  border:1px solid {ring}; border-radius:10px; background:transparent;
}}
.beacon-tile .k {{
  font-size:11px; letter-spacing:.06em; text-transform:uppercase;
  color:{p['muted']}; margin-bottom:6px;
}}
.beacon-tile .v {{
  font-size:26px; line-height:1.15; font-weight:650; color:{p['text_primary']};
}}
.beacon-tile .v.hero {{ font-size:34px; }}
.beacon-tile .s {{ font-size:12px; color:{p['text_secondary']}; margin-top:4px; }}
</style>
"""


def stat_tiles(tiles: list[dict], theme: str = "light") -> str:
    """tiles: [{label, value, sub (optional), color (optional), hero (bool)}]"""
    p = palette(theme)
    out = ['<div class="beacon-kpi">']
    for t in tiles:
        color = t.get("color") or p["text_primary"]
        hero = " hero" if t.get("hero") else ""
        sub = f'<div class="s">{t["sub"]}</div>' if t.get("sub") else ""
        out.append(
            f'<div class="beacon-tile"><div class="k">{t["label"]}</div>'
            f'<div class="v{hero}" style="color:{color}">{t["value"]}</div>{sub}</div>'
        )
    out.append("</div>")
    return "".join(out)
