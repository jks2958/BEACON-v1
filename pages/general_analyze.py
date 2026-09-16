"""Guided CSV analysis workflow backed by the unchanged shared core."""
import streamlit as st

from pipeline.application import analyze_upload
from pipeline.app_state import save_analysis
from pipeline.ui import page_header, render, section_header


render(page_header(
    "Analyze evidence",
    "Three simple steps take prepared telemetry to an explainable result.",
    eyebrow="GENERAL MODE",
))

render(section_header("Step 1 · Choose evidence type"))
evidence = st.radio(
    "Evidence type",
    ["Network telemetry", "Memory telemetry"],
    horizontal=True,
    help="Network means network-flow telemetry. Memory means memory-analysis telemetry.",
)
stream = "network" if evidence == "Network telemetry" else "memory"
helper = ("Network telemetry summarizes communication flows."
          if stream == "network" else "Memory telemetry summarizes memory-analysis observations.")
st.caption(helper)

render(section_header("Step 2 · Upload CSV", "Supported file type: prepared .csv telemetry"))
uploaded = st.file_uploader(
    f"Upload prepared {stream} telemetry",
    type="csv",
    key="general_csv_upload",
    help="Choose a prepared CSV that matches the selected evidence type.",
)
if uploaded is None:
    st.info(f"Selected evidence: **{stream.title()} telemetry**. Choose a CSV to continue.",
            icon=":material/upload_file:")
else:
    st.success(f"Ready to analyze **{uploaded.name}** as {stream} telemetry.",
               icon=":material/check_circle:")

render(section_header("Step 3 · Run analysis"))
if st.button("Analyze Evidence", type="primary", disabled=uploaded is None):
    try:
        with st.spinner("Validating evidence and running the model…"):
            output = analyze_upload(stream, uploaded)
        save_analysis(st.session_state, output)
        st.success("Analysis complete. Preparing your result.")
        st.switch_page("pages/general_results.py")
    except ValueError as exc:
        st.error("BEACON could not analyze this file. Check that it is a valid prepared "
                 f"{stream} CSV and try again.")
        with st.expander("Error details"):
            st.code(str(exc))
