# BEACON

Behavioral Explainable AI for Cyber Operations Network — a multiclass malware
classifier (9 categories + benign) over network-flow and memory-forensic
telemetry, with SHAP explanations and a Streamlit dashboard. Background,
literature review, and requirements are in `P1 Report.pdf`.

## Status (honest, as of this branch)

| Component | Status |
|---|---|
| Preprocessing pipeline (`pipeline/common.py`) | ✅ Built, reused by training and inference |
| Resampling (`pipeline/resampling.py`) | ✅ Built (class weights + cluster-based SMOTE) |
| **Memory-stream model** | ✅ **Trained on the real dataset**, macro F1 ≈ 0.48 — see `models/memory_metrics.json` |
| SHAP explainability | ✅ Working, wired into the dashboard |
| Streamlit dashboard | ✅ Functional for the Memory stream |
| **Network-stream model** | ❌ **Not trained** — this repo has no raw `NetCSVs` data, only `MemoryCSVs.zip` |
| Original `.ipynb` notebooks | Kept as-is except two bug fixes (see below); they're exploratory, not the pipeline this app runs on |

The Memory-stream numbers are real, not illustrative: macro F1 ≈ 0.48,
accuracy ≈ 52% on a held-out, sample-grouped test split, trained on the
full 9,177-row real dataset in `MemoryCSVs.zip`. Exploit's training data is
~90% synthetic (cluster-based SMOTE, only 80 real samples exist) — treat its
per-class numbers as lower-confidence than the other 8 categories, per the
report's own caveat.

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

Try the Memory Detection page with any single CSV from
`data/raw/MemoryCSVs/<Category>/*.csv` — that's exactly the data the model
was trained and tested on.

## Completing the Network stream

1. Obtain the dataset's `NetCSVs/<Category>/*.csv` files (not included here —
   see `Conversion_Code.ipynb`'s original `NET_ROOT` path for where they lived
   locally) and place them under `data/raw/NetCSVs/`.
2. Write `scripts/train_network.py`, mirroring `scripts/train_memory.py`
   (load → dedup → drop empty columns → fix labels → split → log-transform →
   scale → correlation-prune → light SMOTE/class-weighting → Optuna + XGBoost
   → evaluate → save via `ArtifactStore`).
3. Run it — `pages/1_Network_Detection.py` picks up
   `models/network_classifier.joblib` automatically once it exists.

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
scripts/
  train_memory.py     Real, working end-to-end training run (Memory stream)
app.py                Streamlit landing page
pages/                Network Detection / Memory Detection / About pages
models/               Trained model + preprocessing artifacts + metrics
data/raw/             Extracted raw CSVs (gitignored — re-extract from the zips)
*.ipynb               Original exploratory notebooks (kept for the record)
```
