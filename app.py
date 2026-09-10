"""BEACON — Behavioral Explainable AI for Cyber Operations Network.

Landing page for the Streamlit dashboard. Run with:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="BEACON", page_icon="🛰️", layout="wide")

st.title("🛰️ BEACON")
st.subheader("Behavioral Explainable AI for Cyber Operations Network")

st.markdown(
    """
BEACON classifies a piece of software's behavior — captured either as
**network-flow** telemetry or **memory-dump** telemetry — into one of nine
malware categories or benign, and explains every prediction with SHAP so an
analyst can see exactly which behavioral features drove the call.
"""
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Malware categories", "9")
col2.metric("Behavioral data streams", "2")
col3.metric("Model + explainability", "XGBoost + SHAP")
col4.metric("Memory model status", "Trained ✅")

st.divider()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("### 🧬 Multiclass Classification")
    st.write("Predicts one of nine malware families, or benign — not just malicious/not.")
with c2:
    st.markdown("### 🔀 Dual-Source Evidence")
    st.write("Independent classifiers for network-flow and memory-forensic behavior.")
with c3:
    st.markdown("### 🔍 Per-Prediction Explanation")
    st.write("Every prediction ships with the SHAP-ranked features that drove it.")
with c4:
    st.markdown("### 📊 Analyst Dashboard")
    st.write("Upload a CSV, get a category, a confidence score, a risk level, and why.")

st.divider()
st.info(
    "**Status:** the Memory-stream classifier is trained on the real BCCC "
    "Mal-NetMemLog dataset and live in this dashboard. The Network-stream "
    "classifier has not been trained yet — see the Network Detection page "
    "for what's blocking it.",
    icon="ℹ️",
)

st.page_link("pages/2_Memory_Detection.py", label="Try the Memory Detection demo →", icon="🧠")
st.page_link("pages/3_About_Methodology.py", label="Learn about the project →", icon="📖")
