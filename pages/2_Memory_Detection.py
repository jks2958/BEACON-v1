"""Memory Detection page — the one fully functional detection page.

Loads the real XGBoost model trained by scripts/train_memory.py on the
repo's actual MemoryCSVs data, applies the exact same fitted
Preprocessor used at training time (via DashboardController), and
explains the prediction with SHAP.
"""
import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController, StreamUnavailable, risk_level

st.set_page_config(page_title="BEACON — Memory Detection", page_icon="🧠", layout="wide")
st.title("🧠 Memory Detection")

try:
    controller = DashboardController("memory")
except StreamUnavailable as exc:
    st.error(str(exc))
    st.stop()

with st.expander("ℹ️ About this demo", expanded=False):
    st.write(
        "Uploaded files are parsed and classified **locally in this process** — "
        "nothing is sent anywhere else. Expected input: one row per sample, with "
        "the same memory-forensic feature columns (`pslist.*`, `dlllist.*`, "
        "`handles.*`, `malfind.*`, etc.) as the BCCC Mal-NetMemLog dataset's "
        "per-sample CSV exports."
    )

uploaded = st.file_uploader("Memory-dump feature CSV", type="csv")

sample_hint = st.checkbox("I don't have a file handy — where do I get one?")
if sample_hint:
    st.write(
        "Any single-row CSV from `data/raw/MemoryCSVs/<Category>/*.csv` in this "
        "repo works as a test upload (that's exactly what the model was "
        "trained/tested on)."
    )

if uploaded is not None:
    try:
        df = controller.handle_upload(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    with st.spinner("Classifying and computing SHAP explanation..."):
        result = controller.run_pipeline(df)

    pred_label = result["predictions"][0]
    proba_row = result["probabilities"].iloc[0]
    confidence = float(proba_row[pred_label])
    risk = risk_level(pred_label, confidence)

    risk_color = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}[risk]

    col1, col2, col3 = st.columns(3)
    col1.metric("Predicted category", pred_label)
    col2.metric("Confidence", f"{confidence:.1%}")
    col3.metric("Risk level", f"{risk_color} {risk}")

    st.subheader("Class probabilities")
    st.bar_chart(proba_row.sort_values(ascending=False))

    st.subheader("Top contributing features (SHAP)")
    st.caption(
        "Positive SHAP value pushes the prediction toward the predicted class; "
        "negative pushes away from it."
    )
    st.dataframe(result["top_features"], use_container_width=True)

    export_df = pd.DataFrame(
        {
            "predicted_category": [pred_label],
            "confidence": [confidence],
            "risk_level": [risk],
        }
    )
    st.download_button(
        "Download result as CSV",
        export_df.to_csv(index=False),
        file_name="beacon_memory_prediction.csv",
        mime="text/csv",
    )
