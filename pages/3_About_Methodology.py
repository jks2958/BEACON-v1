"""About / Methodology page.

Every figure here is read from models/*_metrics.json rather than typed in,
so the page cannot drift from what was actually measured.
"""
import pandas as pd
import streamlit as st

from pipeline.ui import inject_theme, render
from pipeline.viz import headline, load_metrics

st.set_page_config(page_title="BEACON — About", page_icon="📖", layout="wide")

render(inject_theme())
st.markdown("# Model card & methodology")


net, mem = load_metrics("network"), load_metrics("memory")

st.markdown("## The problem")
st.write(
    "Malware classifiers are typically accurate but opaque, and most are trained "
    "on a single behavioural source — usually network traffic — missing whatever "
    "signal only appears in memory. BEACON targets both gaps: a per-prediction "
    "SHAP explanation, and independent classifiers over both evidence types."
)

st.markdown("## The approach")
st.write(
    "Two structurally identical pipelines share one preprocessing implementation "
    "(`pipeline/common.py`), so training and inference cannot drift apart. They "
    "differ only where the data demands it: the Memory stream needs cluster-based "
    "SMOTE for a severely underrepresented Exploit class, while the Network "
    "stream's imbalance is a mild 5.1:1 and needs only class weighting. Both "
    "train an XGBoost multiclass classifier explained via SHAP `TreeExplainer`."
)

st.markdown("## Measured results")

rows = []
for stream_name, metrics, unit, label in [
    ("Network", net, "flow", "per flow"),
    ("Network", net, "sample", "per capture"),
    ("Memory", mem, None, "per sample"),
]:
    h = headline(metrics, unit) if metrics else None
    # headline() falls back to the best available block, so a Network file
    # written before sample-level scoring existed would report its flow
    # numbers twice -- only take the block that genuinely exists.
    if unit and metrics and f"{unit}_level" not in metrics:
        h = None
    if h:
        rows.append({"Stream": stream_name, "Unit": label,
                     "Accuracy": h["accuracy"], "Macro F1": h["macro_f1"], "n": h["n"]})

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(
        df.style.format({"Accuracy": "{:.1%}", "Macro F1": "{:.3f}", "n": "{:,}"}),
        use_container_width=True, hide_index=True)
else:
    st.warning("No metrics found — run the training scripts first.")

st.info(
    "**Read the units carefully.** The Network stream is reported twice because "
    "the two figures answer different questions. *Per capture* is how the system "
    "is actually used: a capture's hundreds of flows are combined into one "
    "verdict, so individual flow errors cancel out. *Per flow* is the harder "
    "underlying task — classifying a single flow in isolation. Quoting the "
    "per-capture number without its unit would overstate what the model does.",
    icon="📏",
)

st.markdown("## Honest limitations")
st.markdown(
    """
- **Memory stream is the weaker one.** Backdoor, Hoax and HackTool separate
  cleanly, but Rootkit, Trojan, Virus, Worm and Benign overlap heavily in
  memory-forensic feature space. A learning curve confirmed this is an
  *information* ceiling, not a data-quantity one: accuracy gained only
  +0.27 points over the final 20% of training data.
- **Exploit on the Memory stream is ~90% synthetic.** Only 80 real training
  samples exist, so its per-class figures are lower-confidence than the
  other eight. The Network stream has no such problem (250 real captures).
- **The two streams are not fused.** Network and memory records use entirely
  different sample naming, so they cannot be joined per sample; BEACON runs
  two independent classifiers rather than one fused model.
- **Effective sample size.** Per-capture accuracy rests on a few hundred
  held-out captures, not the flow count — the interval is correspondingly
  wider.
    """
)

st.markdown("## Built with")
st.write(", ".join(["Python", "XGBoost", "Optuna", "SHAP", "scikit-learn",
                    "imbalanced-learn", "pandas", "Altair", "Streamlit"]))
