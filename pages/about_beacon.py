"""Scope and audience information shared by both application modes."""
import streamlit as st
from pipeline.ui import page_header, render, section_header


render(page_header("About BEACON", "One explainable analysis core, tailored for two audiences."))
st.write(
    "BEACON is an explainable malware-classification platform that analyzes "
    "prepared Network and Memory telemetry using two independent machine-learning streams."
)

render(section_header("User modes"))
st.markdown("### General Mode")
st.write("For non-technical users who need a simple workflow and an understandable result structure.")
st.markdown("### Analyst Mode")
st.write("For cybersecurity professionals who need probabilities, feature evidence, SHAP explanations, and model details.")

render(section_header("Current input support"))
st.success("Prepared CSV telemetry for Network and Memory analysis.")

render(section_header("Roadmap — not implemented"))
st.write("Future planned evidence sources include:")
st.markdown("- PCAP / PCAPNG\n- Raw memory telemetry")
st.caption("These formats are not accepted by the current application.")
