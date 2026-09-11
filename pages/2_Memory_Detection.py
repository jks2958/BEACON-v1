"""Memory Detection — a pinned, Memory-only version of the Dashboard."""
import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable, risk_level
from pipeline.ui import (current_theme_name, detections_table, kpi_strip, probability_bars,
                         record_detection, render, sidebar_footer, verdict_card)
from pipeline.viz import headline, load_metrics, shap_contribution_chart


@st.cache_resource
def _load_controller(stream: str) -> DashboardController:
    # Streamlit reruns the script on every interaction; cache_resource keeps
    # the model and SHAP explainer loaded once instead of re-reading them.
    return DashboardController(stream)


net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net_metrics), mem_ok=bool(mem_metrics)))

try:
    controller = _load_controller("memory")
except StreamUnavailable as exc:
    st.error(str(exc))
    st.stop()

head = headline(mem_metrics)

st.markdown("# Analyse memory capture")
st.caption("Memory-forensic telemetry classified locally into one of nine categories, "
           "with a SHAP explanation of what drove the verdict.")

uploaded = st.file_uploader("Memory-dump feature CSV", type="csv",
                            label_visibility="collapsed")

if uploaded is None:
    st.info("Upload a memory-dump feature CSV to run a classification. Any file from "
            "`data/raw/MemoryCSVs/<Category>/` works as a test sample.",
            icon=":material/upload_file:")
    render('<div class="bx-label" style="margin-top:22px">Detections this session</div>')
    render(detections_table(st.session_state.get("detections", [])))
    st.stop()

try:
    df = controller.handle_upload(uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

with st.spinner("Classifying and computing SHAP explanation…"):
    result = controller.run_pipeline(df)

verdict = result["verdict"]
confidence = result["confidence"]
severity = risk_level(verdict, confidence)
proba = result["aggregate_probabilities"].sort_values(ascending=False)
runner_up = proba.index[1] if len(proba) > 1 else "—"
margin = (proba.iloc[0] - proba.iloc[1]) * 100 if len(proba) > 1 else 0.0

record_detection(st.session_state, sample=uploaded.name, stream="memory",
                 verdict=verdict, confidence=confidence, severity=severity,
                 rows=result["n_rows"])

left, right = st.columns([1, 1], gap="medium")
with left:
    render(verdict_card(verdict, severity, confidence,
                        f"{uploaded.name} · {result['n_rows']} row(s) · memory_classifier.joblib"))
with right:
    kpis = [
        {"label": "Rows analysed", "value": f"{result['n_rows']:,}", "sub": "memory sample"},
        {"label": "Features used", "value": f"{len(controller.feature_cols)}",
         "sub": "post-preprocessing"},
        {"label": "Second choice", "value": runner_up, "sub": f"margin {margin:.1f} pt"},
    ]
    if head:
        kpis += [
            {"label": "Model accuracy", "value": f"{head['accuracy']:.1%}",
             "sub": f"per sample · n={head['n']:,}"},
            {"label": "Macro F1", "value": f"{head['macro_f1']:.3f}", "sub": "9-class"},
        ]
    render(kpi_strip(kpis))

st.markdown("")
summary_tab, explain_tab, raw_tab = st.tabs(["Summary", "Explanation", "Raw features"])

with summary_tab:
    left, right = st.columns([1, 1], gap="medium")
    with left:
        render('<div class="bx-label">Class probabilities</div>')
        render(probability_bars(result["aggregate_probabilities"], verdict))
    with right:
        render('<div class="bx-label">Top contributing features</div>')
        st.altair_chart(shap_contribution_chart(result["top_features"], current_theme_name()),
                        use_container_width=True)

with explain_tab:
    st.markdown("Blue pushes the verdict toward **{}**; red pushes away. Values are "
                "SHAP contributions relative to the model's base rate."
                .format(verdict))
    st.altair_chart(shap_contribution_chart(result["top_features"], current_theme_name()),
                    use_container_width=True)

with raw_tab:
    st.dataframe(result["top_features"], use_container_width=True, hide_index=True)

render('<div class="bx-label" style="margin-top:20px">Detections this session</div>')
render(detections_table(st.session_state.get("detections", [])))

st.download_button(
    "Export verdict (CSV)",
    pd.DataFrame([{"sample": uploaded.name, "stream": "memory",
                   "predicted_category": verdict, "confidence": confidence,
                   "severity": severity, "rows_analysed": result["n_rows"]}]
                 ).to_csv(index=False),
    file_name="beacon_memory_verdict.csv", mime="text/csv",
)
