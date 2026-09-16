"""Memory Detection — a pinned, Memory-only version of the Dashboard."""
import pandas as pd
import streamlit as st

from pipeline.application import analyze_upload, get_controller
from pipeline.app_state import save_analysis
from pipeline.controller import StreamUnavailable, risk_level
from pipeline.interpretation import interpret_analysis
from pipeline.ingestion import (DEFAULT_INGESTION_SERVICE, EvidenceIngestionError,
                                EvidenceUpload)
from pipeline.ui import (current_theme_name, detections_table, kpi_strip, probability_bars,
                         interpretation_summary, page_header, record_detection, render,
                         section_header, sidebar_footer, verdict_card)
from pipeline.viz import headline, load_metrics, shap_contribution_chart


net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net_metrics), mem_ok=bool(mem_metrics)))

try:
    controller = get_controller("memory")
except StreamUnavailable as exc:
    st.error(str(exc))
    st.stop()

head = headline(mem_metrics)

render(page_header("Memory detection",
                   "Classify prepared memory-analysis telemetry and inspect feature-level evidence.",
                   eyebrow="ANALYST MODE"))
st.warning("Memory family classification remains less reliable than Network capture-level "
           "classification. Treat the result as review evidence, not proof of compromise.",
           icon=":material/info:")
with st.expander("Structured Volatility compatibility diagnostics"):
    st.caption("Diagnostic only — this does not produce a malware verdict or call the model. "
               "Upload a JSON object with `records` and optional `metadata` fields.")
    diagnostic_upload = st.file_uploader(
        "Upload structured Volatility JSON",
        type="json",
        key="memory_volatility_diagnostic",
    )
    if diagnostic_upload is not None:
        try:
            diagnostic = DEFAULT_INGESTION_SERVICE.ingest(
                EvidenceUpload.from_file(diagnostic_upload, "memory")
            )
            contract = diagnostic.metadata["feature_contract"]
            st.warning(f"Compatibility: **{contract.status.value.replace('_', ' ').title()}** — "
                       "production inference is blocked because empirical feature equivalence "
                       "has not been proven.")
            d1, d2, d3 = st.columns(3)
            d1.metric("Expected features", contract.required_count)
            d2.metric("Recognized features", contract.present_count)
            d3.metric("Missing features", len(contract.missing_features))
            st.write("Source format: **Structured Volatility JSON**")
            st.write("Declared plugins:", diagnostic.metadata.get("declared_plugins") or "Not supplied")
            if contract.missing_features:
                st.caption("Missing contract fields")
                st.code("\n".join(contract.missing_features))
            if contract.extra_features:
                st.caption("Extra fields (not passed to the model)")
                st.code("\n".join(contract.extra_features))
        except EvidenceIngestionError as exc:
            st.error(f"Compatibility diagnostics could not read this evidence: {exc}")
render(section_header("Input", "Upload prepared Memory CSV telemetry"))

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
    with st.spinner("Classifying and computing SHAP explanation…"):
        output = analyze_upload("memory", uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

df, result = output.validated_frame, output.result
save_analysis(st.session_state, output)

verdict = result["verdict"]
confidence = result["confidence"]
severity = risk_level(verdict, confidence)
interpretation = interpret_analysis(result, "memory")
proba = result["aggregate_probabilities"].sort_values(ascending=False)
runner_up = proba.index[1] if len(proba) > 1 else "—"
margin = (proba.iloc[0] - proba.iloc[1]) * 100 if len(proba) > 1 else 0.0

record_detection(st.session_state, sample=uploaded.name, stream="memory",
                 verdict=verdict, confidence=confidence, severity=severity,
                 rows=result["n_rows"])

left, right = st.columns([1, 1], gap="medium")
render(section_header("Result summary"))
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

render(interpretation_summary(interpretation))

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
