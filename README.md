# BEACON

Behavioral Explainable AI for Cyber Operations Network — a multiclass malware
classifier (9 categories + benign) over network-flow and memory-forensic
telemetry, with SHAP explanations and a Streamlit dashboard. Background,
literature review, and requirements are in `P1 Report.pdf`.

## Status

| Component | Status |
|---|---|
| Preprocessing pipeline (`pipeline/common.py`) | ✅ Built, reused by training and inference |
| Resampling (`pipeline/resampling.py`) | ✅ Built (class weights + cluster-based SMOTE) |
| **Memory-stream model** | ✅ **Trained on the real dataset** — 59.2% accuracy, macro F1 0.558 |
| **Network-stream model** | ✅ **Trained on the real dataset** — 99.1% per capture, 68.2% per flow |
| SHAP explainability | ✅ Working, wired into both streams |
| Streamlit dashboard | ✅ Functional for both streams |
| Test suite (`tests/`) | ✅ 82 tests, no raw dataset required |
| Original `.ipynb` notebooks | Kept as-is except two bug fixes (see below); they're exploratory, not the pipeline this app runs on |

Both streams' numbers are real, not illustrative — measured on held-out,
sample-grouped splits (no capture appears in both train and test).

### Network stream: two units, two questions

| Unit | Accuracy | Macro F1 | n |
|---|---|---|---|
| Per capture | 99.1% | 0.991 | 447 |
| Per flow | 68.2% | 0.645 | 129,118 |

A capture is hundreds of flows from ONE sample. Combining them into a
single verdict is how the system is actually used, and it lets individual
flow errors cancel out; judging a lone flow in isolation is the harder
underlying task. **Quoting the per-capture number without its unit would
overstate what the model does**, so both appear together everywhere —
in the dashboard, here, and in `models/network_metrics.json`, which nests
`flow_level` and `sample_level` blocks rather than one flat set.

Per-class at capture level: F1 ≥ 0.98 for all nine categories. Identifier
columns (`flow_id`, `timestamp`, `src_ip`, `dst_ip`, `protocol`, `src_port`)
are dropped so the model learns behaviour rather than the lab's addressing;
`dst_port` is kept, since 443/80/4444 genuinely encode service behaviour.

### Memory stream

Macro F1 ≈ 0.56, accuracy ≈ 59% on a held-out, sample-grouped test split,
trained on the full 9,177-row real dataset in `MemoryCSVs.zip`. Exploit's training data is
~90% synthetic (cluster-based SMOTE, only 80 real samples exist) — treat its
per-class numbers as lower-confidence than the other 8 categories, per the
report's own caveat.

**Why not higher, and why 90%+ isn't a realistic target for this task:**
per-class results (`models/memory_metrics.json`) and the confusion matrix
(`models/memory_confusion_matrix.png`) show Backdoor, Hoax, and HackTool
separating cleanly (65-86% recall), while Benign, Rootkit, Trojan, Virus,
and Worm are heavily confused with *each other* — a real behavioral-overlap
ceiling in memory-forensic features (process/handle/DLL counts) rather
than a tuning gap: several of these families simply don't leave
distinguishable memory footprints from each other or from benign processes.
Widening the hyperparameter search (60 trials, added regularization terms)
did not beat the narrower 20-trial search — confirming the ceiling is in
the feature set's discriminative power for these specific classes, not in
search coverage. The one change that produced a real, measured gain was
disabling correlation-based feature pruning (Step 8), which had been
discarding genuinely useful signal for this stream specifically (52.7% ->
58.7% accuracy) -- see the comment in `scripts/train_memory.py`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Reproducing the Memory-stream model

```bash
mkdir -p data/raw
unzip "MemoryCSVs.zip" -d data/raw/
.venv/bin/python scripts/train_memory.py
```

Writes `models/memory_classifier.joblib`, `models/memory_preprocessing_artifacts.joblib`,
`models/memory_confusion_matrix.png`, and `models/memory_metrics.json`.

## Running the dashboard

```bash
.venv/bin/streamlit run app.py
```

Both detection pages are live. Try Memory Detection with any single CSV
from `data/raw/MemoryCSVs/<Category>/*.csv`, or Network Detection with any
capture from `data/raw/NetCSVs/<Category>/*.csv` — that's exactly the data
the models were trained and tested on. Each page reports a verdict, a
confidence against an action threshold, a severity, the SHAP features that
drove the call, and a CSV export.

## Reproducing the Network-stream model

The raw `NetCSVs` are 1.4 GB and are NOT in this repo (same as `data/raw/`
generally). Obtain the dataset's `NetCSVs/<Category>/*.csv` files, then:

```bash
mkdir -p data/raw/NetCSVs      # then place <Category>/*.csv underneath
.venv/bin/python scripts/train_network.py
```

Writes the four `models/network_*` files. `pages/1_Network_Detection.py`
picks them up automatically; without them it shows a "not trained yet"
notice rather than failing.

Two Network-specific details, both absent from the Memory stream:

- `NetCSVs` carry their own `label` column, and the Benign captures label
  themselves `Zbenign` — normalised in `LABEL_FIXES`.
- `delta_start` and `handshake_duration` hold the literal string
  `"not a complete handshake"` in ~39% of rows. That is a behavioural
  signal, not corrupt data, so `encode_handshake` turns it into an
  indicator column plus a `-1` sentinel. **That step runs at inference
  too** — the artifact bundle records it under `derivations`, so a raw
  capture is encoded before validation rather than rejected.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

82 tests, ~13 seconds, and they need no raw data: the trained artifacts are
committed, so model-backed tests synthesise inputs from each model's own
recorded feature list. Tests that need an artifact skip cleanly if it is
absent rather than failing.

Covered: the preprocessor's fit/apply split (Steps 1-8), the handshake
derivation, binary-vs-multiclass objective selection, upload validation
and schema rejection (FR-2), probability aggregation across a capture's
flows, risk-level assignment (FR-6), resampling's synthetic-row flag, and
metrics reporting for both file shapes.

## What changed in this branch vs. the original notebooks

- **Root-cause fix**: `Preprocessing_Step5_to_Step10.ipynb`'s Step 7 excluded
  identifier columns (`flow_id`, `timestamp`, `src_ip`, `dst_ip`, `protocol`)
  from *scaling* but never actually dropped them from the saved Parquet, so
  they reached training as raw strings.
- **Consequence fix**: `Training_XGBoost.ipynb` now filters `feature_cols` to
  numeric dtypes only, so it no longer crashes on Optuna's first trial the
  way its committed output shows.
- Both notebooks' stale/crashed outputs were cleared rather than left
  misleading readers about what the code currently does.
- A second, previously-uncaught 100%-null column (`pslist.avg_handlers`, in
  addition to the known `info.winBuild`) was found in the real Memory data
  and is now auto-detected and dropped, instead of relying on a hardcoded
  column name.

## Repository layout

```
pipeline/           Shared, reusable pipeline code (training + inference)
  common.py         Preprocessor (Steps 1-8)
  resampling.py      SmoteResampler, ClusterBasedResampler
  classifier.py      MalwareClassifier, NetworkClassifier, MemoryClassifier
  explain.py         SHAP TreeExplainer wrapper
  artifacts.py       ArtifactStore (save/load model + preprocessing bundle)
  controller.py       DashboardController used by the Streamlit pages
  ui.py              SOC-console components (theme, verdict band, KPI strip)
  viz.py             Altair charts + palette
scripts/
  train_memory.py     End-to-end training run (Memory stream)
  train_network.py    End-to-end training run (Network stream)
tests/                pytest suite (82 tests, no raw data required)
app.py                Streamlit landing page
pages/                Network Detection / Memory Detection / About pages
models/               Trained models + preprocessing artifacts + metrics (both streams)
data/raw/             Extracted raw CSVs (gitignored — re-extract from the zips)
*.ipynb               Original exploratory notebooks (kept for the record)
```
