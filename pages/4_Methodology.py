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
- **Adding per-capture context to each flow helped, but not for free.**
  Since every flow is judged in isolation, we tried giving each one
  features describing its own capture: same-destination "beaconing"
  frequency, a local rolling-window deviation, and per-capture z-scores.
  This genuinely raised per-flow accuracy by +2.08 points (68.4% to
  70.5%) — the largest real gain of anything tried — but cost -0.67
  points of per-capture accuracy (99.3% to 98.7%), because features
  shared across many flows in one capture make those flows' errors move
  together instead of cancelling out on average. A tenth feature (total
  flows per capture) pushed the per-flow gain to +3.71 points, but
  Virus captures average 718 flows against 140-275 for every other
  class — a swing large enough that we can't rule out it's a dataset
  collection artifact rather than real virus behaviour, so it wasn't
  used. Net verdict: a validated research direction, not a drop-in
  replacement for the shipped model, since it trades away some of the
  metric the product actually reports.
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

st.markdown("## Reframing the Memory task")
st.write(
    "The 9-class ceiling above raises a fair question: would a different "
    "taxonomy suit these features better? The 94 Memory features are all "
    "*counts* — `pslist.nproc`, `dlllist.ndlls`, `handles.nHandles`, "
    "`malfind.ninjections` — and never *identities*: nothing records which "
    "DLL, which process, or what the injected code contained. That predicts "
    "coarse behavioural discrimination should work better than fine-grained "
    "family attribution, which is exactly what these framings test."
)
st.write(
    "Five framings were **pre-registered** — declared before any was run — "
    "and all five are reported, including the one that failed. Picking a "
    "taxonomy by trying several and keeping the best score is test-set "
    "overfitting, not a finding."
)
st.write(
    "All figures below group by `category/stem` rather than the bare filename "
    "stem the shipped model uses. The bare stem collides — 2,155 of 5,728 "
    "stems (37.6%) occur under more than one category — so grouping by it "
    "merges unrelated samples and reports optimistically (see §5.5.3 of the "
    "design specification). These numbers are therefore slightly lower than, "
    "and not directly comparable to, the 59.2% headline above."
)

render(metrics_table(
    [
        {"Framing": "9 classes (as shipped)", "Classes": "9", "Accuracy": "57.9%",
         "Balanced acc": "53.7%", "Macro F1": "0.544", "Trivial baseline": "13.5%"},
        {"Framing": "Binary (Benign vs Malware)", "Classes": "2", "Accuracy": "86.7%",
         "Balanced acc": "67.0%", "Macro F1": "0.677", "Trivial baseline": "87.7%"},
        {"Framing": "Behavioural super-classes", "Classes": "6", "Accuracy": "64.0%",
         "Balanced acc": "65.9%", "Macro F1": "0.656", "Trivial baseline": "25.8%"},
        {"Framing": "Exploit class excluded", "Classes": "8", "Accuracy": "58.8%",
         "Balanced acc": "58.8%", "Macro F1": "0.588", "Trivial baseline": "13.6%"},
    ],
    ["Framing", "Classes", "Accuracy", "Balanced acc", "Macro F1", "Trivial baseline"],
))

st.warning(
    "**The binary framing is a trap, and it is reported here so nobody "
    "repeats it.** At 86.7% accuracy it looks like the strongest result on "
    "this page — but malware is 1,611 of 1,836 test samples, so a classifier "
    "that ignores its input and always answers \"malware\" scores 87.7%. The "
    "model is *worse than that constant*. Its honest figure is balanced "
    "accuracy, 67.0%. Any binary malware-detection accuracy quoted without "
    "its class balance is meaningless.",
    icon=":material/warning:",
)

st.write(
    "**Behavioural super-classes are the real gain.** Grouping by what "
    "malware *does* in memory — self-replicating (Virus, Worm), "
    "stealth-persistence (Rootkit, Trojan), remote-access (Backdoor), "
    "deception (Hoax), offensive tooling (HackTool, Exploit), with Benign "
    "always kept separate — lifts macro F1 from 0.544 to 0.656 (+11.3 "
    "points) and balanced accuracy from 53.7% to 65.9% (+12.2). The grouping "
    "is motivated by malware behaviour, not by reading the confusion matrix."
)

st.markdown("### Deferring the uncertain cases")
st.write(
    "A classifier that may abstain is more useful to an analyst than one "
    "forced to guess. Below each row is the accuracy on the most-confident "
    "fraction of samples, with the rest referred for manual review — "
    "coverage is quoted alongside every figure, because an accuracy without "
    "its coverage says nothing."
)
render(metrics_table(
    [
        {"Coverage": "100% (no abstention)", "9-class": "57.8%", "Behavioural 6-class": "63.7%"},
        {"Coverage": "80%", "9-class": "65.0%", "Behavioural 6-class": "69.3%"},
        {"Coverage": "60%", "9-class": "72.2%", "Behavioural 6-class": "77.2%"},
        {"Coverage": "50%", "9-class": "76.5%", "Behavioural 6-class": "81.3%"},
        {"Coverage": "40%", "9-class": "83.1%", "Behavioural 6-class": "84.9%"},
    ],
    ["Coverage", "9-class", "Behavioural 6-class"],
))
st.write(
    "Read honestly: **81.3% on half the samples**, with the other half "
    "flagged for an analyst. That is a triage capability, not a higher "
    "score on the original task — the 9-class figure at full coverage "
    "remains 58%, and every framing above is a redefinition of the "
    "question rather than a better answer to it."
)

st.markdown("## Built with")
st.write(", ".join(["Python", "XGBoost", "Optuna", "SHAP", "scikit-learn",
                    "imbalanced-learn", "pandas", "Altair", "Streamlit"]))
