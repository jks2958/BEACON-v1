"""Explainability — what SHAP is, and how BEACON uses it.

The example chart on this page is illustrative, not a live prediction —
it uses real feature names pulled from the trained models' own recorded
feature lists, with made-up contribution values, so a reader sees the
actual vocabulary the model reasons over without this page implying an
inference ran. Analyse a real capture on the Dashboard or a Detection
page to see a genuine SHAP explanation.
"""
import pandas as pd
import streamlit as st

from pipeline.ui import render, sidebar_footer
from pipeline.viz import load_metrics, shap_contribution_chart

net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net_metrics), mem_ok=bool(mem_metrics)))

st.markdown("# Explainability")
st.caption("Every verdict ships with the reasons behind it — not just a category and a number.")

left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown("## Why not just a label?")
    st.write(
        "A classifier that says “Backdoor, 91% confidence” and stops there gives an "
        "analyst nothing to act on — they still have to manually dig through the file "
        "to check whether that call is even right. BEACON pairs every prediction with "
        "**SHAP** (SHapley Additive exPlanations), which scores how much each feature "
        "pushed the verdict toward — or away from — the category shown."
    )
    st.markdown("## Why TreeExplainer")
    st.write(
        "`pipeline/explain.py` wraps SHAP's `TreeExplainer` rather than a model-agnostic "
        "explainer, because it computes exact Shapley values for tree ensembles in "
        "polynomial rather than exponential time — the only practical choice at the row "
        "counts BEACON processes (a single network capture can be hundreds of flows)."
    )
    st.markdown("## Reading the chart")
    st.write(
        "Blue bars **push toward** the predicted category; red bars **push away** from "
        "it. Bars are sorted by magnitude, and the explanation is always computed for a "
        "row the model actually assigned to the shown verdict — so the reasoning matches "
        "the answer it's explaining, not whichever row happened to load first."
    )

with right:
    render('<div class="bx-card"><h2>Illustrative example</h2>'
           '<div class="sub">Real feature names, made-up contribution values — '
           "not a live prediction</div></div>")
    st.markdown("")

    example = pd.DataFrame([
        {"feature": "packets_IAT_mode", "value": 0.82, "shap_value": 0.85},
        {"feature": "median_fwd_packets_delta_time", "value": 0.61, "shap_value": 0.62},
        {"feature": "dst_port", "value": 0.44, "shap_value": 0.41},
        {"feature": "handshake_duration", "value": 0.30, "shap_value": 0.30},
        {"feature": "total_header_bytes", "value": 0.71, "shap_value": -0.34},
        {"feature": "packets_count", "value": 0.55, "shap_value": -0.48},
    ])
    st.altair_chart(shap_contribution_chart(example, "light"), use_container_width=True)
    st.caption("These are real Network-stream feature names (verified against "
               "`models/network_preprocessing_artifacts.joblib`), shown here with "
               "illustrative numbers to explain how to read the chart.")

st.markdown("---")
st.markdown("## Where this shows up")
c1, c2 = st.columns(2, gap="medium")
with c1:
    render('<div class="bx-card"><h2>🌐 Network stream</h2>'
           '<div class="sub">342 features, identifier columns excluded</div>'
           "<p style='margin:0;font-size:13px;color:#4b5675'>Explains a representative "
           "flow the model assigned to the verdict category, since a capture is hundreds "
           "of flows and no single one is privileged.</p></div>")
with c2:
    render('<div class="bx-card"><h2>🧠 Memory stream</h2>'
           '<div class="sub">94 features from raw Volatility plugin output</div>'
           "<p style='margin:0;font-size:13px;color:#4b5675'>A memory sample is usually "
           "one row, so the explanation is computed directly for it — no aggregation "
           "needed.</p></div>")
