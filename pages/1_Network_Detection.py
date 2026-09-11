"""Network Detection — a pinned, Network-only version of the Dashboard.

A capture is hundreds of flows from ONE sample, so the verdict is the mean
of their class probabilities rather than any single flow's call: both the
operationally correct unit and far more accurate (measured 68.2% per flow
vs 99.1% per capture).
"""
import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable, risk_level
from pipeline.ui import (current_theme_name, detections_table, kpi_strip, probability_bars,
                         record_detection, render, sidebar_footer, verdict_card)
from pipeline.viz import headline, load_metrics, shap_contribution_chart


@st.cache_resource
def _load_controller(stream: str) -> DashboardController:
    return DashboardController(stream)


net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net_metrics), mem_ok=bool(mem_metrics)))

try:
    controller = _load_controller("network")
except StreamUnavailable:
    st.markdown("# Analyse network capture")
    st.warning(
        "**No trained Network model is available yet.** Place the raw "
        "`NetCSVs/<Category>/*.csv` data under `data/raw/NetCSVs/` and run "
        "`python scripts/train_network.py`. This page picks up "
        "`models/network_classifier.joblib` automatically once it exists.",
        icon=":material/construction:",
    )
    st.stop()

sample_head = headline(net_metrics, "sample") if net_metrics and "sample_level" in net_metrics else None
flow_head = headline(net_metrics, "flow") if net_metrics and "flow_level" in net_metrics else None

st.markdown("# Analyse network capture")
st.caption("Every flow in the capture is classified; the verdict combines them. "
           "Identifier columns (IPs, ports, timestamps, flow IDs) are excluded so the "
           "model learns behaviour rather than the capture environment.")

uploaded = st.file_uploader("Network flow CSV", type="csv", label_visibility="collapsed")

if uploaded is None:
    st.info("Upload a network capture CSV to run a classification. Any file from "
            "`data/raw/NetCSVs/<Category>/` works as a test sample.",
            icon=":material/upload_file:")
    render('<div class="bx-label" style="margin-top:22px">Detections this session</div>')
    render(detections_table(st.session_state.get("detections", [])))
    st.stop()

try:
    df = controller.handle_upload(uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

with st.spinner("Classifying flows and computing SHAP explanation…"):
    result = controller.run_pipeline(df)

verdict = result["verdict"]
confidence = result["confidence"]
severity = risk_level(verdict, confidence)
proba = result["aggregate_probabilities"].sort_values(ascending=False)
runner_up = proba.index[1] if len(proba) > 1 else "—"
margin = (proba.iloc[0] - proba.iloc[1]) * 100 if len(proba) > 1 else 0.0
agreeing = int((result["row_predictions"] == verdict).sum())
consensus = agreeing / result["n_rows"] if result["n_rows"] else 0.0

record_detection(st.session_state, sample=uploaded.name, stream="network",
                 verdict=verdict, confidence=confidence, severity=severity,
                 rows=result["n_rows"])

left, right = st.columns([1, 1], gap="medium")
with left:
    render(verdict_card(verdict, severity, confidence,
                        f"{uploaded.name} · {result['n_rows']:,} flows · network_classifier.joblib"))
with right:
    kpis = [
        {"label": "Flows analysed", "value": f"{result['n_rows']:,}",
         "sub": f"{consensus:.0%} individually agree"},
        {"label": "Features used", "value": f"{len(controller.feature_cols)}",
         "sub": "identifiers excluded"},
        {"label": "Second choice", "value": runner_up, "sub": f"margin {margin:.1f} pt"},
    ]
    if sample_head:
        kpis.append({"label": "Model accuracy", "value": f"{sample_head['accuracy']:.1%}",
                     "sub": f"per capture · n={sample_head['n']:,}"})
    if flow_head:
        kpis.append({"label": "Per-flow accuracy", "value": f"{flow_head['accuracy']:.1%}",
                     "sub": f"n={flow_head['n']:,} flows"})
    render(kpi_strip(kpis))

st.markdown("")
summary_tab, explain_tab, raw_tab = st.tabs(["Summary", "Explanation", "Raw features"])

with summary_tab:
    left, right = st.columns([1, 1], gap="medium")
    with left:
        render('<div class="bx-label">Class probabilities · mean across flows</div>')
        render(probability_bars(result["aggregate_probabilities"], verdict))
    with right:
        render('<div class="bx-label">Top contributing features</div>')
        st.altair_chart(shap_contribution_chart(result["top_features"], current_theme_name()),
                        use_container_width=True)

with explain_tab:
    st.markdown(f"Blue pushes the verdict toward **{verdict}**; red pushes away. "
                "Computed for a representative flow the model assigned to the verdict "
                "category, so the explanation matches the answer it explains.")
    st.altair_chart(shap_contribution_chart(result["top_features"], current_theme_name()),
                    use_container_width=True)

with raw_tab:
    st.dataframe(result["top_features"], use_container_width=True, hide_index=True)

if sample_head and flow_head:
    render(
        f'<div class="bx-note" style="margin-top:16px"><strong>Reading the accuracy '
        f'figures.</strong> <strong>{sample_head["accuracy"]:.1%} per capture</strong> '
        f'(n={sample_head["n"]:,}) is how this page works — a capture\'s flows are '
        f'combined into one verdict, so individual flow errors cancel out. '
        f'<strong>{flow_head["accuracy"]:.1%} per flow</strong> '
        f'(n={flow_head["n"]:,}) is the harder underlying task of judging a single flow '
        f'in isolation. Quoting the per-capture number without its unit would overstate '
        f'what the model does.</div>')

render('<div class="bx-label" style="margin-top:20px">Detections this session</div>')
render(detections_table(st.session_state.get("detections", [])))

st.download_button(
    "Export verdict (CSV)",
    pd.DataFrame([{"sample": uploaded.name, "stream": "network",
                   "predicted_category": verdict, "confidence": confidence,
                   "severity": severity, "flows_analysed": result["n_rows"],
                   "flow_consensus": round(consensus, 4)}]).to_csv(index=False),
    file_name="beacon_network_verdict.csv", mime="text/csv",
)
