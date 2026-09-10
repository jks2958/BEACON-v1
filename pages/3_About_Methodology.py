"""About / Methodology page."""
import json
import os

import streamlit as st

st.set_page_config(page_title="BEACON — About", page_icon="📖", layout="wide")
st.title("📖 About BEACON")

st.markdown("## The Problem")
st.write(
    "Malware classifiers are typically accurate but opaque, and most are trained "
    "on a single behavioral data source (usually network traffic), missing "
    "whatever signal only shows up in memory. BEACON targets both gaps at once: "
    "a per-prediction SHAP explanation, and independent classifiers over both "
    "network-flow and memory-forensic evidence."
)

st.markdown("## The Approach")
st.write(
    "Two structurally identical pipelines — one per data stream — share the same "
    "preprocessing code (`pipeline/common.py`), differ only in their resampling "
    "strategy (light class-weighting vs. cluster-based SMOTE for a severely "
    "underrepresented class), and both train an XGBoost multiclass classifier "
    "explained via a SHAP `TreeExplainer`."
)

st.markdown("## Current Status")

metrics_path = os.path.join("models", "memory_metrics.json")
if os.path.exists(metrics_path):
    with open(metrics_path) as fh:
        metrics = json.load(fh)
    st.success("Memory-stream model: trained and evaluated on real data.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Test macro F1", f"{metrics['test_macro_f1']:.3f}")
    c2.metric("Train rows (post-resampling)", metrics["train_rows_after_resampling"])
    c3.metric("Test rows", metrics["test_rows"])
    st.caption(
        f"Exploit class training data is "
        f"{metrics['exploit_synthetic_fraction_in_training']:.0%} synthetic "
        "(cluster-based SMOTE) — treat its results as lower-confidence than the "
        "other 8 categories."
    )
else:
    st.warning("Memory-stream model metrics not found — run scripts/train_memory.py.")

st.warning(
    "Network-stream model: **not trained.** This repository has no raw NetCSVs "
    "data; only the Memory-dump dataset is present. See the Network Detection "
    "page for what's needed to complete it."
)

st.markdown("## Built With")
st.write(", ".join(["Python", "XGBoost", "Optuna", "SHAP", "scikit-learn",
                     "imbalanced-learn", "pandas", "Streamlit"]))
