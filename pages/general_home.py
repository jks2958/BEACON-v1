"""Approachable landing page for BEACON's non-technical audience."""
import streamlit as st

from pipeline.app_state import ANALYST_MODE, set_mode
from pipeline.ui import page_header, render, section_header


render(page_header(
    "Explainable Cyber Threat Analysis",
    "Understand suspicious activity with evidence-based AI analysis.",
    eyebrow="BEACON",
))

primary, secondary, spacer = st.columns([1, 1.15, 2])
with primary:
    if st.button("Analyze Evidence", type="primary", use_container_width=True):
        st.switch_page("pages/general_analyze.py")
with secondary:
    if st.button("Switch to Analyst Mode", use_container_width=True):
        set_mode(st.session_state, ANALYST_MODE)
        st.rerun()

render(section_header("Available now", "Supported production inputs in this version"))
c1, c2 = st.columns(2)
c1.success("**Prepared Network CSV**\n\nNetwork-flow telemetry exported in BEACON's expected schema.",
           icon=":material/hub:")
c2.success("**Prepared Memory CSV**\n\nMemory-analysis telemetry exported in BEACON's expected schema.",
           icon=":material/memory:")

render(section_header("How it works"))
steps = [
    ("01", "Upload prepared telemetry", "Choose Network or Memory and select a CSV."),
    ("02", "BEACON analyzes evidence", "The existing validated model processes the telemetry."),
    ("03", "Review an explainable result", "See the classification, confidence, and grounded reasons."),
    ("04", "Open technical details", "Inspect probabilities and SHAP evidence when needed."),
]
cols = st.columns(4)
for column, (number, title, description) in zip(cols, steps):
    with column:
        render(f'<div class="bx-step"><div class="num">{number}</div><strong>{title}</strong>'
               f'<span>{description}</span></div>')

render(section_header("Future evidence workflows", "Roadmap only — not production classification"))
st.info(
    "PCAP/PCAPNG parsing is currently diagnostic-only because exact compatibility with the "
    "trained Network feature representation is not validated. Raw-memory ingestion is planned.",
    icon=":material/science:",
)
