"""Methodology — model card and measured results.

Every figure here is read from models/*_metrics.json rather than typed in,
so the page cannot drift from what was actually measured.
"""
import streamlit as st

from pipeline.ui import metrics_table, render, sidebar_footer
from pipeline.viz import headline, load_metrics

net, mem = load_metrics("network"), load_metrics("memory")

with st.sidebar:
    render(sidebar_footer(net_ok=bool(net), mem_ok=bool(mem)))

st.markdown("# Methodology")
st.caption("Model card, measured results, and the limitations reported alongside them.")

st.markdown("## The problem")
st.write(
    "Malware classifiers are typically accurate but opaque, and most are trained "
    "on a single behavioural source — usually network traffic — missing whatever "
    "signal only appears in memory. BEACON targets both gaps: a per-prediction "
    "SHAP explanation (see the Explainability page), and independent classifiers "
    "over both evidence types."
)

st.markdown("## The approach")
st.write(
    "Two structurally identical pipelines share one preprocessing implementation "
    "(`pipeline/common.py`), so training and inference cannot drift apart. They "
    "differ only where the data demands it: the Memory stream needs cluster-based "
    "SMOTE for a severely underrepresented Exploit class, while the Network "
    "stream's imbalance is milder and needs only class weighting. Both train an "
    "XGBoost multiclass classifier explained via SHAP `TreeExplainer`."
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
                     "Accuracy": f"{h['accuracy']:.1%}", "Macro F1": f"{h['macro_f1']:.3f}",
                     "n": f"{h['n']:,}"})

if rows:
    render(metrics_table(rows, ["Stream", "Unit", "Accuracy", "Macro F1", "n"]))
else:
    st.warning("No metrics found — run the training scripts first.")

st.info(
    "**Read the units carefully.** The Network stream is reported twice because "
    "the two figures answer different questions. *Per capture* is how the system "
    "is actually used: a capture's hundreds of flows are combined into one "
    "verdict, so individual flow errors cancel out. *Per flow* is the harder "
    "underlying task — classifying a single flow in isolation. Quoting the "
    "per-capture number without its unit would overstate what the model does.",
    icon=":material/straighten:",
)

st.markdown("## Honest limitations")
st.markdown(
    """
- **Memory stream is the weaker one.** Backdoor, Hoax and HackTool separate
  cleanly, but Rootkit, Trojan, Virus, Worm and Benign overlap heavily in
  memory-forensic feature space. A learning curve confirmed this is an
  *information* ceiling, not a data-quantity one: accuracy gained only
  +0.27 points over the final 20% of training data.
- **Network's per-flow accuracy is an information ceiling too.** A matching
  learning curve found the same pattern: per-flow accuracy gained -0.02
  points and per-capture accuracy -0.30 points over the final 20% of
  training data (both within noise). More captures would not move either
  figure. The underlying cause: every flow in a capture inherits that
  capture's malware-family label, including the large share that's
  incidental traffic unrelated to the malware itself — no amount of
  additional data resolves a label that's wrong for the row it's on.
- **A per-flow noise filter was tried and made things worse.** Since the
  label-inheritance problem above suggested filtering out training flows
  that look Benign might help, we tested it: a separate classifier flagged
  malware-labeled training flows that statistically resemble real Benign
  traffic, and those were dropped before training. Accuracy improved on
  the flows the filter approved (78.4% to 81.3%), but Trojan and Worm lost
  40-43% of their training rows to the filter, and the net effect on the
  full test set was worse, not better (68.3% to 66.8% per-flow accuracy).
  The shipped model keeps the unfiltered training data.
- **Exploit on the Memory stream is ~90% synthetic.** Only 80 real training
  samples exist, so its per-class figures are lower-confidence than the
  other eight. The Network stream has no such problem (250 real captures).
- **The two streams are not fused.** Fusion was measured, not assumed
  impossible — combining both streams scores 78.5% against 99.1% for the
  Network stream alone, so BEACON runs two independent classifiers.
- **Effective sample size.** Per-capture accuracy rests on a few hundred
  held-out captures, not the flow count — the interval is correspondingly
  wider.
    """
)

st.markdown("## Built with")
st.write(", ".join(["Python", "XGBoost", "Optuna", "SHAP", "scikit-learn",
                    "imbalanced-learn", "pandas", "Altair", "Streamlit"]))
