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
| Test suite (`tests/`) | ✅ 96 tests, no raw dataset required |
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

## Dual-stream fusion — a negative result

`scripts/train_fusion.py` tests whether combining both streams into one
verdict beats either alone. **It does not.** Measured on the 214 samples
that carry both a network capture and a memory dump, with both models
trained excluding all 214 (`models/fusion_metrics.json`):

| Decision rule | Accuracy | Macro F1 |
|---|---|---|
| Network only | **99.07%** | 0.987 |
| Memory only | 34.58% | 0.205 |
| Fusion (mean) | 78.50% | 0.730 |
| Fusion (confidence-weighted) | 78.97% | 0.660 |

Fusion costs 20 points against the network stream alone. The memory
stream is the only correct voice in 1 case out of 214 (network alone 139,
both 73, neither 1), so averaging it in mostly corrupts verdicts the
network stream already had right. The streams therefore stay independent
in the dashboard; memory is a fallback for samples with no network
capture, not a vote alongside one.

Caveats, all recorded in the metrics file: these 214 cover 8 of the 9
categories (no sample has both streams for Exploit) and are skewed
(HackTool 69, Backdoor 3), and hyperparameters were reused from the
shipped runs rather than re-searched.

### The finding underneath it

The memory arm scores 34.6% here against its own 59.2% headline. That gap
is not a bug — given the shipped hold-out, this same pipeline reproduces
58.82% vs the shipped 59.15%. It is a **near-neighbour effect**, and the
ablation isolates it. Holding the evaluation set fixed at the 41 dual
samples the shipped model also never saw, and varying only whether the
*other* 173 dual samples are in training:

| Training set | Accuracy on the same 41 |
|---|---|
| 173 neighbours in | **68.29%** |
| 173 neighbours out | **31.71%** |

**36.6 points from 173 samples out of ~5,700.** The dual-stream samples
are a tightly-related cluster that a split grouped by `sample_id` does not
separate. No exact-duplicate feature vector crosses the shipped split, so
the 59.2% is not inflated *that* way — what is demonstrated is a strong
near-neighbour effect for one identifiable cluster, not that the dataset
has this structure throughout. Testing that properly would mean clustering
the memory features and splitting by cluster rather than by sample.

```bash
.venv/bin/python scripts/train_fusion.py      # needs both raw datasets
```

It writes only `models/fusion_metrics.json`; the shipped models are left
untouched.

## An external-dataset specialist — CIC-MalMem-2022

The Memory stream's 59.2% is a measured ceiling, not a tuning gap (see
above), so the honest way to push it further is more or different
*information*, not more tuning. The one real candidate for that is a
completely external memory-forensics dataset — but it turns out none of
the public ones actually plug into BCCC's model. `scripts/train_
malmem_specialist.py` trains a **separate third model** on
[CIC-MalMem-2022](https://www.unb.ca/cic/datasets/malmem-2022.html) (UNB)
to make that concrete, rather than leave it as an assumption.

**Why separate, not merged:**

- **Different taxonomy.** This dataset's malware side is Ransomware /
  Spyware / Trojan Horse (15 families). BEACON's Memory stream classifies
  Backdoor / Exploit / HackTool / Hoax / Rootkit / Trojan / Virus / Worm.
  Only "Trojan" overlaps by name, and even that names a different set of
  specific families. There is **no Exploit category here at all** — the
  one class this project is weakest on — so this dataset cannot patch
  that gap even in principle.
- **Different features.** This dataset's ~55 columns come from
  VolMemLyzer; BCCC's ~98 come straight out of raw Volatility plugin
  output. Different tool, different column names. Concatenating the two
  CSVs would silently train on nonsense (columns aligned by position, not
  by meaning).
- **No sample-grouping column.** BCCC's memory rows carry a `sample_id`
  used for a grouped split (and even that has a real caveat — see
  §5.5.3 of the design doc). This dataset is one row per sample with no
  such column, so a plain stratified split is used instead.

So this is a genuinely new, third model — its own taxonomy, its own
features, its own split strategy, its own metrics file — not a way to
raise the 59.2%.

```bash
mkdir -p data/raw/CIC-MalMem-2022
# download the CSV yourself -- this sandbox's egress proxy blocks
# kaggle.com, unb.ca, and ieee-dataport.org alike:
#   https://www.kaggle.com/datasets/luccagodoy/obfuscated-malware-memory-2022-cic
#   https://www.unb.ca/cic/datasets/malmem-2022.html
# place the CSV under data/raw/CIC-MalMem-2022/, then:
.venv/bin/python scripts/train_malmem_specialist.py
```

The script was written and tested against a fabricated CSV before the
real file was available — this sandbox cannot download it — so it
auto-detects the label/feature columns and prints the full schema before
training rather than assuming public documentation matches the actual
CSV byte-for-byte. `tests/test_malmem_specialist.py` proves the
mechanics (schema detection, family-label collapsing, the binary/
multiclass objective switch, artifact saving) against that fabricated
file, since a real-data test can't ship in the repo.

### Real results (user-supplied CSV, 58,596 rows)

The real file matched the documented schema exactly — `Category` and
`Class` columns, 55 VolMemLyzer features, no surprises. Two things
checked before trusting the run: the `Category` → supercategory
collapsing was verified against the independent `Class` column (every
non-Benign group maps to `Malware`, with zero exceptions) before the
real training run, and 534 exact-duplicate rows were found and removed
by dedup — asymmetric (467 malware, 67 benign), consistent with
obfuscated-malware runs producing more near-identical memory snapshots
than varied benign workloads, not a bug.

| Metric | Value |
|---|---|
| Test accuracy | **88.1%** |
| Test macro F1 (blended) | **0.820** |
| Test macro F1, **malware families only** | **0.760** |
| n (test) | 11,613 (train 46,449) |

**The blended 0.820 overstates the hard part of the task, and the
malware-only 0.760 is the fairer number to quote.** The confusion matrix
(`models/malmem_specialist_confusion_matrix.png`) shows why: Benign is a
perfect wall — F1 1.000, zero confusion in or out of it — while every
single error is a Ransomware/Spyware/Trojan family confused with another
family. Benign-vs-malware separability on this dataset is a
well-documented property in the published literature (the script's own
binary diagnostic against the `Class` column also hits 100%), not
something this run discovered. The genuinely hard part — family
attribution — sits at 0.760, meaningfully above BCCC's 9-class 0.558
(more real samples per class, only 3 malware families instead of 8, and
a cleaner lab-collection methodology), but the two numbers are still
**not directly comparable**: different taxonomy, different features,
different dataset difficulty.

This does not change `models/memory_metrics.json` or the dashboard.
`data/raw/CIC-MalMem-2022/` stays gitignored, same as every other raw
dataset in this project — only the trained artifacts, metrics, and
confusion matrix under `models/malmem_specialist_*` are committed.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

96 tests, ~40 seconds, and they need no raw data: the trained artifacts are
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
  classifier.py      MalwareClassifier, NetworkClassifier, MemoryClassifier,
                     MalMemSpecialistClassifier
  explain.py         SHAP TreeExplainer wrapper
  artifacts.py       ArtifactStore (save/load model + preprocessing bundle)
  controller.py       DashboardController used by the Streamlit pages
  ui.py              SOC-console components (theme, verdict band, KPI strip)
  viz.py             Altair charts + palette
scripts/
  train_memory.py     End-to-end training run (Memory stream)
  train_network.py    End-to-end training run (Network stream)
  train_fusion.py     Dual-stream fusion experiment (negative result)
  train_malmem_specialist.py  Separate 3rd model, external dataset
tests/                pytest suite (96 tests, no raw data required)
app.py                Streamlit landing page
pages/                Network Detection / Memory Detection / About pages
models/               Trained models + preprocessing artifacts + metrics (both streams)
data/raw/             Extracted raw CSVs (gitignored — re-extract from the zips)
*.ipynb               Original exploratory notebooks (kept for the record)
```
