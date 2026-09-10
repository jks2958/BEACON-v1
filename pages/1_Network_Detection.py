"""Network Detection page.

Honest by design: no NetCSVs data exists in this repository, so no
network-stream model has ever been trained here. This page says so
plainly instead of faking a prediction — matching the project's own UI
principle (see About page / SRS 5.6) of never presenting a
not-yet-functional part of the system as if it were live.
"""
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable

st.set_page_config(page_title="BEACON — Network Detection", page_icon="🌐", layout="wide")
st.title("🌐 Network Detection")


@st.cache_resource
def _load_controller(stream: str) -> DashboardController:
    return DashboardController(stream)


try:
    controller = _load_controller("network")
except StreamUnavailable:
    st.warning(
        "**No trained Network model is available yet.** This repository does not "
        "contain the raw NetCSVs network-flow data needed to train it — only the "
        "Memory-dump dataset is present. To enable this page:\n\n"
        "1. Place the raw `NetCSVs/<Category>/*.csv` data under `data/raw/NetCSVs/`.\n"
        "2. Write `scripts/train_network.py` (mirror `scripts/train_memory.py`) and run it.\n"
        "3. Reload this page — it will pick up `models/network_classifier.joblib` automatically.",
        icon="🚧",
    )
    st.stop()

st.write("Upload a CSV of network-flow features for a single captured sample.")
uploaded = st.file_uploader("Network flow CSV", type="csv")

if uploaded is not None:
    try:
        df = controller.handle_upload(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    if len(df) > 1:
        st.info(f"File has {len(df)} rows — showing the classification for row 1 only.")

    result = controller.run_pipeline(df)
    st.success(f"Predicted category: **{result['predictions'][0]}**")
    st.bar_chart(result["probabilities"].iloc[0])
    st.subheader("Top contributing features (SHAP)")
    st.dataframe(result["top_features"], use_container_width=True)
