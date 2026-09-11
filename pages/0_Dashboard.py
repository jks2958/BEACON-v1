"""Dashboard — the single "analyse anything" screen.

BEACON has two models expecting different CSV schemas (342 Network
columns vs 94 Memory columns), so there is no reliable way to auto-detect
which one an upload is for. Rather than guess, this page asks the analyst
to pick the evidence type first via a segmented control, then behaves
exactly like the pinned Network/Memory Detection pages underneath.
"""
import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable, risk_level
from pipeline.ui import (detections_table, probability_bars, record_detection, render,
                         sidebar_footer, stat_strip, stream_status_card, verdict_card)
from pipeline.viz import headline, load_metrics, shap_contribution_chart

net_metrics, mem_metrics = load_metrics("network"), load_metrics("memory")


@st.cache_resource
def _load_controller(stream: str) -> DashboardController | None:
    try:
        return DashboardController(stream)
    except StreamUnavailable:
        return None


st.markdown("# Analyse. Explain. Decide.")
st.caption("Upload network-flow or memory-forensic telemetry. BEACON classifies the sample "
           "into one of nine malware categories or benign, and shows exactly which "
           "behaviours drove the call.")

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
                   f"automatically once `models/{stream}_classifier.joblib` exists.", icon="🚧")
        uploaded = None
    else:
        label = ("Network flow CSV · 342 columns expected" if stream == "network"
                 else "Memory-dump feature CSV · 94 columns expected")
        uploaded = st.file_uploader(label, type="csv")
        st.caption(f"Any file from `data/raw/{'NetCSVs' if stream == 'network' else 'MemoryCSVs'}"
                   "/<Category>/` works as a test sample.")

result = None
error = None
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
        render(verdict_card(
            verdict, severity, confidence,
            f"{uploaded.name} · {result['n_rows']:,} {unit} · {stream}_classifier.joblib"))

st.markdown("")
render(stat_strip([
    {"icon": "▦", "title": "9 malware families", "desc":
        "Backdoor, Exploit, HackTool, Hoax, Rootkit, Trojan, Virus, Worm + Benign"},
    {"icon": "⇄", "title": "2 evidence streams", "desc":
        "Network flow (342 features) & memory forensics (94 features)"},
    {"icon": "◈", "title": "XGBoost + SHAP", "desc": "Explained predictions, not black-box labels"},
    {"icon": "⌂", "title": "Local processing", "desc": "Runs on your machine — nothing leaves it"},
]))

st.markdown("")
c1, c2, c3 = st.columns([1, 1.15, 0.95], gap="medium")

with c1:
    render('<div class="bx-card" style="height:100%"><h2>Class probabilities</h2>'
           '<div class="sub">Mean across the capture\'s rows</div></div>')
    if result is not None:
        st.markdown("")
        render(probability_bars(result["aggregate_probabilities"], result["verdict"]))

with c2:
    render('<div class="bx-card" style="height:100%"><h2>SHAP explanation</h2>'
           '<div class="sub">Top features that contributed to this prediction</div></div>')
    if result is not None:
        st.markdown("")
        st.altair_chart(shap_contribution_chart(result["top_features"], "light"),
                        use_container_width=True)

with c3:
    render('<div class="bx-card" style="height:100%"><h2>Model status</h2>'
           '<div class="sub">Both detection streams</div></div>')
    st.markdown("")
    net_head = headline(net_metrics, "sample") if net_metrics and "sample_level" in net_metrics else None
    mem_head = headline(mem_metrics) if mem_metrics else None
    render(stream_status_card(
        "Network stream", "🌐", bool(net_head),
        f"{net_head['accuracy']:.1%} per capture (n={net_head['n']:,})" if net_head
        else "not trained yet"))
    render(stream_status_card(
        "Memory stream", "🧠", bool(mem_head),
        f"{mem_head['accuracy']:.1%} accuracy (n={mem_head['n']:,})" if mem_head
        else "not trained yet"))

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
