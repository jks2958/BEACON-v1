# Chapter 5 — Software Design Specification (revised draft)

> **Status of this draft.** The Chapter 5 currently in `P1 Report.pdf` was written
> before the system was built. This revision describes BEACON as implemented and
> measured. Section 0 lists every substantive correction; Sections 5.1–5.6 are the
> replacement text. Figure numbering is preserved so existing diagrams can be
> reused where they remain accurate — Section 0 marks the ones that must be redrawn.

---

## 0. Corrections to the existing chapter

| # | Existing claim | Corrected | Consequence |
|---|---|---|---|
| 1 | "0% match rate joining on `sample_id` across all 9 categories" | **214 samples (9.6% of the 2,235 network samples) carry both a network capture and a memory dump** | The stated justification for two independent pipelines was factually wrong. The conclusion survives — but now on measured evidence (correction 2), not on a false premise. **Must be rewritten.** |
| 2 | Fusion is "impossible" | Fusion is possible and was **measured**. It is worse: 99.07% network-only vs 78.50% fused, on the 214 dual-stream samples | Replaces an assumption with an experiment. New Section 5.2.2. |
| 3 | Network model uses "light multiclass SMOTE (~5:1 imbalance)" | Network uses **balanced class weights, no SMOTE** | Figure 5.6 (Activity) decision point is wrong; redraw. |
| 4 | "Correlation pruning removes redundant columns before the vector reaches the model" | Correlation pruning is **disabled on both streams** (threshold 1.0). Measured on Memory: enabling it cost 6 points of accuracy (52.7% → 58.7%) | Step 8 is retained in code as a no-op with a recorded justification. |
| 5 | Memory: "98 features, after dropping `info.winBuild`" | **94 features.** A second 100%-null column, `pslist.avg_handlers`, was found in the real data and is auto-detected | Data dictionary must be updated. |
| 6 | Network: "348 features" | **342 features** reach the model, after dropping 6 identifier columns and adding 2 handshake indicators | Data dictionary must be updated. |
| 7 | "`src_port`/`dst_port` (bimodal but not treated as a data issue)" | **`src_port` is dropped** as an identifier; `dst_port` is kept | See 5.5 for the measured justification. |
| 8 | `delta_start`/`handshake_duration` are "structural-missingness candidates (Step 4)" | They are handled by a dedicated **derivation step that runs before Step 1**, not by Step 4 | New pipeline stage; Figure 5.6 must show it. |
| 9 | Artifacts persisted as `models/*.pkl` | `models/*.joblib` | Cosmetic. |
| 10 | `DashboardController ... via apply_preprocessing` | Methods are `handle_upload()` and `run_pipeline()` | Figure 5.3 / 5.4 labels. |
| 11 | Activity diagram "reflects the full Steps 1–13 pipeline" | Implemented pipeline is Steps 1–8 preprocessing, then resampling, then training | Figure 5.6 must be redrawn. |
| 12a | *(absent)* | **The Memory split's group key is not unique** — 37.6% of stems occur under multiple categories; the reported 59.2% is ~1.9 points optimistic | New Section 5.5.3. |
| 12 | *(absent)* | **Per-flow vs per-capture evaluation** — the central evaluation concept of the finished system | New Section 5.2.3. Nothing in the current chapter describes it. |

---

## 5.1 Design Methodology and Software Process Model

### Design Methodology: Object-Oriented

*(Retained from the existing draft — this section proved correct in implementation.)*

BEACON follows an object-oriented design methodology. Three characteristics of the
system justify it:

- **Encapsulation of pipeline stages.** Cleaning, missing-value handling, scaling,
  resampling, model training and explanation each carry their own fitted state —
  Min-Max ranges, a correlation drop-list, a trained model's feature order. Modelling
  each as a class keeps that state bundled with the logic that uses it.

- **Reuse through inheritance and polymorphism.** The Network and Memory pipelines
  share the same eight preprocessing steps but differ in imbalance ratio and
  resampling strategy. `MalwareClassifier` is an abstract base with
  `NetworkClassifier`/`MemoryClassifier` subclasses; `Resampler` is an abstract base
  with `SmoteResampler`/`ClusterBasedResampler`.

- **Consistency with the underlying libraries.** XGBoost, scikit-learn and SHAP all
  expose fit/predict/transform-style objects.

**One implementation note worth recording.** The two classifier subclasses ended up
differing in *nothing* — same interface, same algorithm, same parameters. What
actually differs is which data and which resampling strategy trained them, and that
lives in the training scripts. The subclasses are retained because they make the
stream a type-level distinction rather than a string passed around at runtime, but
the honest description is that the polymorphism buys clarity, not behaviour.

### Software Process Model: Iterative and Incremental

*(Retained, and strengthened by what implementation produced.)*

The original justification was that EDA after the initial design uncovered findings
requiring earlier decisions to be revisited. Implementation produced four more of
exactly this kind, each of which changed a design decision after it had been made:

1. **Correlation pruning was harmful.** Inherited from the Network-stream design and
   never validated against Memory's smaller feature space. Disabling it raised Memory
   accuracy from 52.7% to 58.7%.
2. **The evaluation unit was wrong.** Scoring the Network stream per flow answers a
   question the system never asks; scoring per capture answers the one it does
   (Section 5.2.3).
3. **A second fully-null column existed.** `pslist.avg_handlers` was 100% null in the
   real data alongside the known `info.winBuild`. The fix was to stop hardcoding
   column names and detect emptiness.
4. **Fusion was assumed impossible, then measured and found harmful** (Section 5.2.2).

A waterfall model freezes design before implementation and would have shipped all
four errors.

---

## 5.2 System Overview

BEACON ingests a malware sample's telemetry — either network-flow records or
memory-dump records — and returns a predicted category (one of nine: Backdoor,
Benign, Exploit, HackTool, Hoax, Rootkit, Trojan, Virus, Worm), a confidence, a
qualitative risk level, and a SHAP-based explanation, through a Streamlit dashboard.

It is built on the BCCC-Mal-NetMem-2025 dataset (York University), which profiles
samples from two angles: network-flow captures and memory-dump captures.

### 5.2.1 Architectural Design

**Layered architecture**, chosen for a one-directional dependency chain: presentation
depends on application/service, which depends on model/intelligence, which depends on
the data layer, with no layer depending upward.

| Layer | Modules | Responsibility |
|---|---|---|
| Presentation | `app.py`; `pages/1_Network_Detection.py`; `pages/2_Memory_Detection.py`; `pages/3_About_Methodology.py`; `pipeline/ui.py`; `pipeline/viz.py` | Upload, results display, SHAP charts, navigation, theming |
| Application / Service | `Preprocessor`, `encode_handshake` (`pipeline/common.py`); `Resampler` subclasses; `Explainer`; `DashboardController` | Transformation shared by training and inference; imbalance correction; SHAP; request orchestration |
| Model / Intelligence | `NetworkClassifier`, `MemoryClassifier` | Learned mapping from features to one of nine categories |
| Data | Raw CSV captures (`data/raw/`, not distributed); `ArtifactStore` over `models/*.joblib` | Persistent storage of inputs, models and preprocessing artifacts |

Two additions since the original draft: `pipeline/ui.py` and `pipeline/viz.py` were
extracted from the pages so that presentation concerns (theme tokens, chart palettes,
component markup) do not live inside page scripts.

**The load-bearing relationship** remains as originally stated: the Preprocessing
Module is *shared*, not duplicated, between training and inference. Training fits the
transformation parameters; inference applies them. This is what prevents the dashboard
from silently drifting from how the model was trained.

Implementation hardened this in a way the original design did not anticipate. A model's
input contract is not only the fitted parameters but also **which derivation steps ran
before them**. The artifact bundle therefore records derivations by name:

```
{preprocessor, feature_cols, categories, derivations: ["encode_handshake"]}
```

Inference replays exactly what training recorded. Before this, the Network page
rejected every real capture — the model had been trained on encoded handshake columns
that no raw capture contains.

### 5.2.2 Why two independent pipelines (revised justification)

The existing chapter states the two feature spaces "do not correspond row-for-row (0%
match rate joining on `sample_id` across all 9 categories)" and concludes a fused
model is impossible. **The 0% figure is incorrect.** Matching network capture
filenames against memory dump filenames yields **214 samples carrying both streams**,
9.6% of the 2,235 network samples.

Fusion was therefore built and measured (`scripts/train_fusion.py`). Because a fusion
score is only meaningful on samples neither model trained on — and only 41 of the 214
were unseen by the shipped memory model — evaluation-only models were trained holding
out all 214 from both streams.

| Decision rule | Accuracy | Macro F1 |
|---|---|---|
| **Network only** | **99.07%** | 0.987 |
| Memory only | 34.58% | 0.205 |
| Fusion (mean of class probabilities) | 78.50% | 0.730 |
| Fusion (confidence-weighted) | 78.97% | 0.660 |

Fusion costs 20 points against the network stream alone. The agreement breakdown
explains why: of 214 samples, the network stream alone was correct on 139, both
streams on 73, **the memory stream alone on 1**, and neither on 1. The memory stream
contributes almost no independent signal, so averaging it in corrupts verdicts the
network stream already had right.

**The architecture is unchanged — but the justification is now evidential rather than
assumed.** The streams remain independent; the memory stream serves samples that have
no network capture.

*Limitations, stated in `models/fusion_metrics.json`:* the 214 cover 8 of 9 categories
(no sample carries both streams for Exploit) and are skewed (HackTool 69, Backdoor 3);
hyperparameters were reused from the shipped runs rather than re-searched.

**A methodological finding.** The memory arm scores 34.6% here against its own 59.2%
headline. This is not a defect — given the shipped hold-out, the same pipeline
reproduces 58.82% against the shipped 59.15%. It is a near-neighbour effect, isolated
by ablation. Holding the evaluation set fixed at the 41 dual samples and varying only
whether the other 173 are in training:

| Training set | Accuracy on the same 41 |
|---|---|
| 173 neighbours in training | **68.29%** |
| 173 neighbours held out | **31.71%** |

**36.6 points from 173 samples out of roughly 5,700.** The dual-stream samples form a
tightly-related cluster that a split grouped by `sample_id` does not separate. No
exact-duplicate feature vector crosses the shipped split, so the 59.2% is not inflated
in that manner; what is demonstrated is a strong near-neighbour effect for one
identifiable cluster, not that the dataset carries this structure throughout.
Establishing the latter would require clustering the memory feature space and
splitting by cluster rather than by sample — recorded here as future work.

### 5.2.3 Evaluation unit: per flow and per capture

Nothing in the existing chapter describes this, and it is the single most important
evaluation decision in the finished system.

A network capture is not one record. It is **hundreds of flows produced by one
sample**. This creates two distinct questions:

- **Per flow** — can the model classify a single flow in isolation? 68.25% accuracy,
  macro F1 0.645, n = 129,118.
- **Per capture** — can it classify the sample the flows came from? Flow probabilities
  are averaged into one verdict, so individual flow errors cancel. 99.11% accuracy,
  macro F1 0.991, n = 447.

Per capture is how the system is used. Per flow is the harder underlying task.
**Reporting the per-capture figure without its unit would materially overstate what
the model does**, so both are reported together, each with its `n`, in the dashboard,
the README and this chapter. The Memory stream has no such distinction — a memory
sample is a single record.

---

## 5.4 Design Models

*(Section 5.3 is absent from the existing chapter's numbering; retained as-is.)*

All diagrams follow UML 2.5 notation. **Figures 5.3, 5.4 and 5.6 require redrawing**
against the corrections below; Figures 5.1, 5.2, 5.5, 5.7 and 5.8 remain accurate.

### 5.4.1 Class Diagram — Figure 5.3 *(redraw)*

Changes from the drawn version:

- `DashboardController` exposes `handle_upload(file)` and `run_pipeline(df)` — not
  `apply_preprocessing`. It also holds `derivations`, resolved from the artifact bundle.
- `Preprocessor` gains `missingness_handled_cols` (a property naming the columns Step 4
  was fitted to fill) and `transform()` as the single inference entry point.
- Module-level `encode_handshake` and the `DERIVATIONS` registry are new, and sit
  *outside* `Preprocessor` because they run before it.
- `ClusterBasedResampler.resample()` returns a **three-tuple** `(X, y, is_synthetic)`.
  The synthetic flag is not incidental: 89.7% of the Memory model's Exploit training
  rows are synthetic, and the flag is what keeps that caveat attached to the number.
- Two presentation modules exist that the diagram does not show: `pipeline/ui.py` and
  `pipeline/viz.py`.

### 5.4.2 Sequence Diagram — Figure 5.4 *(redraw)*

The sequence gains one step at the front and one at the end:

1. `handle_upload()` applies each recorded **derivation**, *then* validates the schema.
   Order matters: the derived columns do not exist in a raw capture, so validating
   first rejects every real file.
2. `run_pipeline()` calls `Preprocessor.transform()`, then the classifier for per-row
   probabilities, then **aggregates them by mean into one verdict**, then calls
   `Explainer` for a row the model assigned to *that verdict class* — so the
   explanation describes the answer being shown rather than whichever row came first.

### 5.4.3 State Transition Diagram — Figure 5.5 *(accurate)*

Five states from upload to display, with a `Rejected` state for schema failure. One
refinement to the rejection rule: a missing value is fatal **only** in a column the
preprocessor has no fitted fill rule for. Statistics such as `payload_bytes_skewness`
are genuinely undefined for a single-packet flow, and Step 4 learned fills for 43 such
columns on the Network stream; rejecting those would reject almost every real capture.

### 5.4.4 Activity Diagram — Figure 5.6 *(redraw)*

The drawn version shows a "Steps 1–13" pipeline with two decision points. The
implemented pipeline is:

```
derive (encode_handshake, network only)
  → Step 1 deduplicate
  → Step 2 drop fully-null columns (auto-detected)
  → Step 3 normalise labels (Zbenign → Benign, network only)
  → Step 5 grouped stratified split by sample_id
  → Step 4 missingness: structural (sentinel + indicator) vs random (median)
  → Step 6 log-transform heavy-tailed features (network only)
  → Step 7 Min-Max scale (fit on train only)
  → Step 8 correlation prune (DISABLED, threshold 1.0, both streams)
  → resample (memory Exploit only) / balanced class weights
  → Optuna search → XGBoost fit → evaluate → persist
```

Both original decision points are wrong as drawn. The dataset branch is not "light
SMOTE vs cluster-based oversampling" — the Network stream uses **balanced class
weights and no SMOTE at all**. The missingness branch is real and retained.

Note that Step 5 (split) precedes Step 4 (missingness) deliberately: medians must be
fitted on training data only, or the test set leaks into the imputation.

### 5.4.5 Data Flow Diagrams — Figures 5.7, 5.8 *(accurate)*

D4 (Prediction & Explanation Log) remains the extension point: results are still
session-scoped. The dashboard now keeps an in-session detections table, which is the
shape D4 would persist, but it does not survive a page reload.

---

## 5.5 Data Design

BEACON's information domain begins as heterogeneous CSV rows and is transformed into
fixed-length numeric feature vectors. Entities are held in memory as pandas
DataFrames and persisted via `joblib` rather than a relational database. Predictions
are not yet logged persistently (D4).

### 5.5.1 Data Dictionary *(corrected)*

**Network-flow features — 342 reach the model.**

| Group | Detail |
|---|---|
| Dropped as identifiers | `flow_id`, `timestamp`, `src_ip`, `dst_ip`, `protocol`, `src_port` |
| Log-transformed (Step 6) | `duration`, `packets_count`, `total_payload_bytes`, `bytes_rate`, `packets_rate` |
| Median-imputed (Step 4) | 43 columns, mostly higher-order statistics undefined for short flows |
| Derived | `delta_start_incomplete`, `handshake_duration_incomplete` |
| Min-Max scaled | all 342 |
| Correlation-pruned | none (disabled) |

`src_port` deserves its own note, because the measured result contradicts the
intuition. It was tested for leakage and **was not leaking** — global gain rank 76 of
343, and removing it cost 1.3 points at flow level while slightly *improving*
sample-level accuracy. It is dropped anyway: an OS-assigned ephemeral port carries no
behavioural meaning, so a feature that costs nothing and invites a "why is that a
feature?" objection is a poor trade. `dst_port` is kept — 443, 80 and 4444 genuinely
encode service behaviour.

**The handshake columns.** `delta_start` and `handshake_duration` contain the literal
string `"not a complete handshake"` in **38.6%** of rows. This is behaviour, not
corrupt data: a flow that never completed a TCP handshake is different from one that
completed in 0.03 s. Each becomes a binary indicator plus a `-1` sentinel in the
original column, distinguishable from any real duration (all ≥ 0). Nulling these
rows — the original notebook's behaviour — discarded a signal present in over a third
of the data.

**Memory-dump features — 94 reach the model.**

| Group | Detail |
|---|---|
| Dropped as 100% null | `info.winBuild`, `pslist.avg_handlers` |
| Log-transformed | none — no heavy-tail transform was warranted |
| Missingness handling | none required after the null-column drop |
| Min-Max scaled | all 94 |
| Correlation-pruned | none (disabled — measured to cost 6 points) |

**Label field.** Normalised to exactly nine values. The `Zbenign` → `Benign` fix
applies to the Network stream only, where labels are read from a column inside each
CSV; Memory labels come from the directory name and need no normalisation.

### 5.5.2 Class balance and its treatment

| Stream | Imbalance | Treatment |
|---|---|---|
| Network | moderate | balanced class weights; no synthetic data |
| Memory | severe for Exploit (20 test samples against ~200 for every other class) | cluster-based SMOTE (K-means by silhouette, then per-cluster interpolation) raising Exploit to the smallest other class, plus balanced weights |

**89.7% of the Memory model's Exploit training rows are synthetic.** Exploit's
per-class Memory result (F1 0.296) must be read as lower-confidence than the other
eight categories, and the training pipeline carries an `is_synthetic` flag through
resampling specifically so this caveat cannot be detached from the number.

---

### 5.5.3 Data-integrity finding: the split's group key

Both streams split with `StratifiedGroupKFold` grouped by `sample_id` so that no
sample appears in both train and test. On the Memory stream, `sample_id` is the CSV
filename stem — and that identifier is not unique.

Of 8,625 memory files there are only 5,731 distinct stems, and **2,155 of those stems
(37.6%) occur under more than one category directory**. Names such as `7968_1`,
`7968_2` and `7968_3` appear under HackTool, Rootkit *and* Worm: they are per-run
indices, not sample hashes. Grouping by stem therefore collapses unrelated samples
from different categories into a single group carrying three different labels.

The effect was measured by re-training with a `category/stem` key, which cannot
collide, holding everything else constant:

| Group key | Test accuracy | Macro F1 |
|---|---|---|
| `stem` (as shipped) | 59.31% | 0.569 |
| `category/stem` | 57.46% | 0.549 |

**The reported 59.2% is therefore roughly 1.9 points optimistic** — a real but modest
overstatement, not a structural failure of the evaluation. It is recorded here rather
than silently corrected because retraining the shipped model to close a two-point gap
is a decision for the project supervisor, not an implementation detail.

Two properties of this dataset consequently limit what the Memory-stream number can
be claimed to mean, and both should be stated wherever it is quoted: the identifier
collisions described here, and the near-neighbour clustering demonstrated in
Section 5.2.2. Neither affects the Network stream, whose filenames are 64-character
sample hashes and are unique.

## 5.6 User Interface Design

The dashboard is a four-page Streamlit application presented as a security-operations
console: a dark analyst theme, monospaced figures, and severity encoded in form as
well as colour.

### 5.6.1 Screen Images

| Page | Purpose |
|---|---|
| Triage Console (landing) | Engine status per stream, headline accuracy tiles with explicit units, navigation |
| Network Detection | Upload a capture; verdict, confidence, severity, class probabilities, SHAP explanation, export |
| Memory Detection | The same for a memory dump |
| About / Methodology | Model card: data, features, measured results, caveats |

### 5.6.2 Screen Objects and Actions

| Object | Action |
|---|---|
| File uploader | Accepts a CSV; rejects on schema failure with a message naming the offending columns |
| Verdict band | Predicted category, severity chip, confidence meter against a 60% action threshold |
| KPI strip | Rows analysed, features used, second-choice category and margin, model accuracy **with its unit and n** |
| Class probability bars | All nine categories, verdict emphasised rather than nine competing hues |
| SHAP contribution chart | Diverging bars — toward the verdict versus away from it |
| Detections table | Session log of every verdict produced |
| Export button | Downloads the verdict, confidence, severity and row count as CSV |

**Two interface rules follow from the evaluation design rather than from aesthetics.**
First, any accuracy figure is rendered with its unit and sample count attached, and
the Network page carries a note explaining why the two figures differ — the per-capture
number alone would mislead. Second, severity is downgraded one level when confidence
falls below 50%, so a shaky call on a dangerous-sounding label does not read as
urgently as a confident one.

---

## Verification status

Every figure in this chapter is drawn from a committed metrics file or from repository
code, not from recollection. The system carries 88 automated tests covering the
preprocessing fit/apply split, the derivation contract, upload validation, verdict
aggregation, risk levels, resampling's synthetic flag, and the consistency of the
metrics files with the shipped models. They require no raw dataset and run in about
13 seconds.
