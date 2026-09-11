"""Dashboard — the single "analyse anything" screen, laid out as a command
console: KPI strip, an analyse/result panel pair, then class-probability
and SHAP panels, a raw-data preview, and the upload-classify-explain-export
workflow strip.

BEACON has two models expecting different CSV schemas (342 Network
columns vs 94 Memory columns), so there is no reliable way to auto-detect
which one an upload is for. Rather than guess, this page asks the analyst
to pick the evidence type first via a segmented control, then behaves
exactly like the pinned Network/Memory Detection pages underneath.
"""
import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable, risk_level
from pipeline.ui import (confidence_ring, data_preview_table, detections_table, kpi_strip,
                         probability_bars, record_detection, render, severity_chip,
                         severity_colors, shap_table, sidebar_footer, tokens, workflow_stepper)
from pipeline.viz import headline, load_metrics

net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")


@st.cache_resource
def _load_controller(stream: str) -> DashboardController | None:
    try:
        return DashboardController(stream)
    except StreamUnavailable:
        return None


net_head = headline(net_metrics, "sample") if net_metrics and "sample_level" in net_metrics else None
mem_head = headline(mem_metrics) if mem_metrics else None
models_ready = sum(1 for h in (net_head, mem_head) if h)

st.markdown("# Analyse. Explain. Decide.")
st.caption("Upload network-flow or memory-forensic telemetry. BEACON classifies the sample "
           "into one of nine malware categories or benign, and shows exactly which "
           "behaviours drove the call.")

render(kpi_strip([
    {"icon": "grid_view", "label": "Malware categories", "value": "9",
     "sub": "Known malware families"},
    {"icon": "swap_horiz", "label": "Behavioral streams", "value": "2",
     "sub": "Memory + Network"},
    {"icon": "layers", "label": "Model stack", "value": "XGBoost + SHAP",
     "sub": "Tree-based ML with explainability"},
    {"icon": "verified", "label": "Models ready", "value": f"{models_ready}/2",
     "sub": "Ready for inference" if models_ready == 2 else "Awaiting training data",
     "ok": models_ready == 2},
]))

st.markdown("")
left, right = st.columns([1.35, 1], gap="medium")

with left:
    render('<div class="bx-card"><h2>Analyse a capture</h2>'
           '<div class="sub">Choose the evidence type, then upload its feature CSV</div></div>')
    st.markdown("")
    choice = st.segmented_control("Evidence type", options=["Memory dump", "Network capture"],
                                  default="Network capture", label_visibility="collapsed")
    stream = "network" if choice == "Network capture" else "memory"
    controller = _load_controller(stream)

    if controller is None:
        st.warning(f"No trained {stream} model is available. Run "
                   f"`python scripts/train_{stream}.py` first — this page picks it up "
                   f"automatically once `models/{stream}_classifier.joblib` exists.",
                   icon=":material/construction:")
        uploaded = None
    else:
        label = ("Network flow CSV · 342 columns expected" if stream == "network"
                 else "Memory-dump feature CSV · 94 columns expected")
        uploaded = st.file_uploader(label, type="csv")
        st.caption(f"Any file from `data/raw/{'NetCSVs' if stream == 'network' else 'MemoryCSVs'}"
                   "/<Category>/` works as a test sample.")

result = None
error = None
df = None
if controller is not None and uploaded is not None:
    try:
        df = controller.handle_upload(uploaded)
        with st.spinner("Classifying and computing SHAP explanation…"):
            result = controller.run_pipeline(df)
    except ValueError as exc:
        error = str(exc)

with right:
    if error:
        render('<div class="bx-card"><h2>Result</h2></div>')
        st.error(error)
    elif result is None:
        render(
            '<div class="bx-card"><h2>Result</h2>'
            '<div class="sub">Waiting for an upload</div>'
            '<div class="bx-note">Pick an evidence type and upload a CSV on the left — '
            "the verdict, confidence, risk level and SHAP explanation will appear here.</div>"
            "</div>"
        )
    else:
        verdict = result["verdict"]
        confidence = result["confidence"]
        severity = risk_level(verdict, confidence)
        unit = "flows" if stream == "network" else "row(s)"
        record_detection(st.session_state, sample=uploaded.name, stream=stream,
                         verdict=verdict, confidence=confidence, severity=severity,
                         rows=result["n_rows"])
        sev_colour = severity_colors().get(severity)
        render(f"""
<div class="bx-card">
  <h2 style="margin-bottom:2px">Result</h2>
  <div class="sub">{uploaded.name} · {result['n_rows']:,} {unit} · {stream}_classifier.joblib</div>
  <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">
    {confidence_ring(confidence, colour=sev_colour)}
    <div style="flex:1;min-width:140px">
      <div class="bx-label" style="margin-bottom:2px">Predicted malware category</div>
      <div style="font-size:22px;font-weight:800;color:{tokens()['ink']}">{verdict}</div>
      <div class="bx-riskrow" style="margin-top:10px">Risk level: {severity_chip(severity)}</div>
    </div>
  </div>
</div>
""")

st.markdown("")
c1, c2 = st.columns([1, 1.1], gap="medium")

with c1:
    with st.container(border=True):
        render('<h2>Class probabilities</h2><div class="sub">Mean across the capture\'s rows</div>')
        if result is not None:
            render(probability_bars(result["aggregate_probabilities"], result["verdict"]))
        else:
            st.caption("Results appear here once a capture is classified.")

with c2:
    with st.container(border=True):
        render('<h2>Top contributing features (SHAP)</h2>'
               '<div class="sub">Ranked by absolute contribution to the verdict</div>')
        if result is not None:
            render(shap_table(result["top_features"]))
        else:
            st.caption("The SHAP breakdown appears here once a capture is classified.")

st.markdown("")
c3, c4 = st.columns([1.3, 1], gap="medium")

with c3:
    with st.container(border=True):
        render('<h2>Data preview (first 5 rows)</h2>'
               '<div class="sub">Post-validation upload, before preprocessing</div>')
        if df is not None:
            render(data_preview_table(df))
        else:
            st.caption("The uploaded capture's raw rows appear here.")

with c4:
    with st.container(border=True):
        render('<h2>Analysis workflow</h2><div class="sub">From raw behaviour to actionable insight</div>')
        render(workflow_stepper([
            {"icon": "upload_file", "title": "Upload", "desc": "Feature CSV"},
            {"icon": "bolt", "title": "Classify", "desc": "XGBoost inference"},
            {"icon": "insights", "title": "Explain", "desc": "SHAP analysis"},
            {"icon": "download", "title": "Export", "desc": "Results & report"},
        ]))

if result is not None:
    st.markdown("")
    st.download_button(
        "Export verdict (CSV)",
        pd.DataFrame([{"sample": uploaded.name, "stream": stream,
                       "predicted_category": result["verdict"], "confidence": result["confidence"],
                       "rows_analysed": result["n_rows"]}]).to_csv(index=False),
        file_name=f"beacon_{stream}_verdict.csv", mime="text/csv",
    )

render('<div class="bx-label" style="margin-top:20px">Detections this session</div>')
render(detections_table(st.session_state.get("detections", [])))

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net_metrics), mem_ok=bool(mem_metrics)))
