# §4.4 — Verification (revised draft)

> **Status of this draft.** The §4.4 currently in `P1 Report.pdf` was written
> before the automated test suite, the Network stream, the fusion experiment,
> and the MalMem specialist existed. This revision describes verification as
> it now actually happens. Section 0 lists every substantive correction;
> Section 4.4 (below it) is the replacement text, including an FR
> traceability table the current chapter doesn't have.

---

## 0. Corrections to the existing section

| # | Existing claim | Corrected | Consequence |
|---|---|---|---|
| 1 | "a dedicated validation script run before any model is trained" | **No such standalone script exists.** Verification is a committed **96-test pytest suite** (`tests/`) plus diagnostics printed inline by each training script | The claim described something that was never built as described. Replaced with what's actually there and runnable by anyone (`pytest`, no raw data required). |
| 2 | "a grouped, stratified split designed to prevent related records from appearing in both training and testing" | True for the Network stream. For Memory, **the grouping key has a real collision**: 37.6% of `sample_id` values occur under more than one category folder, so a "group" can span up to three labels (Chapter 5 §5.5.3). Re-splitting on a collision-free key measured the reported 59.2% as ~1.9 points optimistic | The split does what it's designed to do for Network; for Memory it does *mostly* what it's designed to do, measurably not perfectly. Stated with the number, not glossed over. |
| 3 | "SHAP output is additionally reviewed manually against domain expectations for each malware category" | **No systematic per-category audit was performed.** What actually happened: a per-run SHAP sanity check on one test row (printed by every `scripts/train_*.py`), the live per-prediction explanation every dashboard page renders, and one concrete targeted investigation — whether `src_port` was leaking lab-setup information into the Network model (it measurably wasn't: global gain rank 76 of 343) | The general claim overstated a systematic process into something closer to ad hoc review plus one worked example. The worked example is real and citable; the "for each category" framing isn't. |
| 4 | *(absent)* | **FR-7 is only partially satisfied.** "Export... the prediction result **and its accompanying explanation**" — the shipped CSV export contains the verdict, confidence, severity and row count; it does **not** contain the SHAP feature attributions shown on screen | Found while writing this section by reading `pages/1_Network_Detection.py` and `pages/2_Memory_Detection.py` directly, not assumed. A real, still-open gap against the FR as written. |
| 5 | *(absent)* | **FR-3 does not cover the MalMem specialist.** That model's taxonomy (Benign/Ransomware/Spyware/Trojan) is not "one of the nine supported malware categories," and the model is deliberately not wired into the dashboard | Stated explicitly so FR-3's verification isn't misread as covering three models when it covers two. |
| 6 | *(absent)* | **No FR traceability table existed.** Added one below, citing the actual test that exercises each requirement. | Closes a real gap in the original SRS: verification evidence was described in prose with no link back to which requirement it verifies. |
| 7 | *(absent)* | **Confusion matrices now exist for three models**, not the two referenced implicitly by the section (`network_confusion_matrix.png`, `memory_confusion_matrix.png`, `malmem_specialist_confusion_matrix.png`) | Reflects the MalMem specialist added since this section was last written. |

---

## 4.4 Verification

Verification of BEACON's requirements is carried out at three levels: an
automated test suite that runs without any dataset present, held-out
evaluation of each trained model, and targeted manual review where automated
checks can't substitute for domain judgment. The project supervisor reviews
this verification evidence as part of the standard project evaluation
process.

### 4.4.1 Automated test suite

`tests/` holds **96 tests across 10 files**, run with `pytest`; they require
no raw dataset and complete in well under a minute on a clean clone, so
anyone reviewing this project can verify the claims below themselves rather
than take them on trust. Coverage, by what each file actually checks:

| File | Verifies |
|---|---|
| `test_preprocessor.py` | The Steps 1–8 preprocessing pipeline's fit/apply split — that `apply_*` replays training-time parameters (Min-Max ranges, median fills, correlation drop-list) rather than recomputing them on new data, which is the specific failure mode that would let the dashboard silently drift from how a model was trained |
| `test_derivations.py` | The handshake-encoding derivation that runs before Step 1 on the Network stream, including that it is idempotent and that its registry entry matches what a trained model's artifact bundle records |
| `test_classifier.py` | Correct XGBoost objective selection for 2-class vs multiclass problems, and that prediction is invariant to input column order |
| `test_controller.py` | FR-2 (schema validation), FR-3/4/5 (verdict aggregation across a capture's rows, with an explanation that matches the verdict shown), and FR-6 (risk-level assignment) — detailed in §4.4.2 below |
| `test_resampling.py` | The synthetic-row flag from cluster-based oversampling, which is what keeps Exploit's ~90%-synthetic Memory training data honestly caveated everywhere its numbers are reported |
| `test_artifacts.py` | Save/load round-trips for both a model and its preprocessing bundle, and that each shipped model's recorded feature list matches what its classifier actually expects |
| `test_viz.py` | Metrics-file parsing across the different shapes the Network and Memory streams' files use, so a page can never silently show a `None` or a mismatched unit |
| `test_metrics_integrity.py` | That every shipped model's recorded hyperparameters match its actual saved booster (a real bug, caught this way: the Memory stream's file once claimed 450 trees against a 400-round booster because early stopping overrode Optuna's suggestion after the fact) and that the MalMem specialist's categories never silently include a BCCC-only category |
| `test_malmem_specialist.py` | The MalMem specialist's training script end-to-end, run as a subprocess against a fabricated CSV before the real dataset was available, proving schema detection, label derivation, and the binary/multiclass objective switch work mechanically |
| `test_docs.py` | That the numbers quoted in `README.md` match the committed metrics files, so documentation cannot silently drift from what was actually measured |

### 4.4.2 Functional requirement → verification evidence

| Requirement | Verification |
|---|---|
| **FR-1** — accept a CSV via the dashboard | Exercised as the precondition of every upload test in `test_controller.py`; confirmed against real files from both streams by running the live dashboard in a headless browser during development |
| **FR-2** — validate against the expected schema, reject before predicting | `test_controller.py::test_missing_columns_are_rejected_with_a_readable_message`, `test_nan_is_allowed_where_a_fill_rule_was_fitted`, `test_nan_without_a_fill_rule_is_rejected`, `test_non_numeric_garbage_is_treated_as_missing`. The rule is more precise than "reject files that do not match": a value is only fatal if the preprocessor has no fitted fill rule for that column — rejecting on any missing value would have rejected nearly every real Network capture, since 43 of its columns are legitimately undefined for a single-packet flow |
| **FR-3** — classify into one of nine categories or benign | Both the Network and Memory classifiers are trained and evaluated on the real 9-category taxonomy; `test_metrics_integrity.py::test_categories_recorded_match_the_label_encoder` pins this. **Does not cover the MalMem specialist**, whose 4-class taxonomy is a different, explicitly separate model (correction 5, above) |
| **FR-4** — report a numeric confidence score | `test_controller.py::test_aggregate_probabilities_are_a_distribution`; rendered as the confidence meter against a 60% action threshold on every verdict |
| **FR-5** — SHAP values with top contributing features, readable format | `test_controller.py::test_explanation_describes_a_row_assigned_to_the_verdict` (the explanation must describe the same class as the verdict shown, not whichever row was processed first); rendered as a diverging SHAP-contribution chart in every page's Explanation tab |
| **FR-6** — qualitative risk level from category + confidence | `test_controller.py::test_confident_prediction_keeps_its_category_risk`, `test_low_confidence_downgrades_one_notch`, `test_threshold_is_at_half`, `test_every_trained_category_has_a_risk_mapping` |
| **FR-7** — export the result and its explanation | The verdict, confidence, severity and row count are exported as CSV on every page. **The SHAP explanation itself is not included in the export** — a real gap against this requirement as written, found while drafting this section, not yet closed |
| **FR-8** — retraining independent of the dashboard | `scripts/train_network.py`, `train_memory.py`, `train_fusion.py`, and `train_malmem_specialist.py` are all standalone and were each actually run to produce their committed model; `test_malmem_specialist.py` additionally proves this mechanically via a real subprocess invocation, since the dataset itself can't ship in the test suite |

### 4.4.3 Model-level verification

Each trained model is assessed on a held-out test set, using per-class
precision, recall, F1-score, and a confusion matrix
(`models/network_confusion_matrix.png`, `models/memory_confusion_matrix.png`,
`models/malmem_specialist_confusion_matrix.png`), with particular attention
paid to categories known to be underrepresented in the source data —
Memory's Exploit class is flagged everywhere its numbers appear as ~90%
synthetic (cluster-based oversampling; only 80 real samples exist).

The Network stream's split is grouped by `sample_id` with zero overlap
between train and test, verified by an assertion in the training script
itself. The Memory stream's split uses the same mechanism, but Chapter 5
§5.5.3 found the grouping key is not fully collision-free for that dataset:
37.6% of `sample_id` values recur across more than one category folder,
because they are per-run indices rather than sample hashes. Re-splitting on
a key that cannot collide measured the shipped 59.2% as **~1.9 points
optimistic** (57.46% under the stricter key) — real, disclosed, and left
uncorrected in the shipped model pending a supervisor decision on whether a
two-point gap warrants a retrain.

Beyond routine train/test evaluation, three measured experiments serve as
additional, stronger verification of specific design decisions rather than
assumptions carried from the original proposal:

- **Dual-stream fusion** was built and measured, not assumed impossible.
  Combining both streams scores 78.50% against 99.07% for the Network
  stream alone (`models/fusion_metrics.json`) — the two-classifier
  architecture is justified by a result, not a limitation of the data.
- **The Memory stream's accuracy ceiling** was tested against five
  independent interventions — a wider hyperparameter search, more training
  data, an alternative model family, a hierarchical two-stage architecture,
  and feature engineering — none of which recovered meaningful accuracy,
  supporting that ~59% reflects the information available in these
  features rather than a tuning gap.
- **The MalMem specialist**, trained on an entirely external dataset
  (CIC-MalMem-2022), was verified against a fabricated file matching that
  dataset's public documentation before the real file was available, so its
  schema-detection logic was proven correct before ever touching real data.

### 4.4.4 SHAP output review

Every live prediction's explanation is generated by the same
`Explainer` (SHAP `TreeExplainer`) used during development, and each
training script prints a sanity check — the top contributing features for
one held-out row — as part of its own run. This was exercised as a targeted
investigation at least once: `src_port`'s SHAP attribution on a single
Network prediction initially suggested it might be leaking the lab
environment's addressing rather than genuine behaviour, which prompted
checking its *global* gain importance (rank 76 of 343) rather than trusting
the single-row reading. `src_port` was dropped from the Network stream's
features regardless — not because it was leaking, but because an
OS-assigned ephemeral port carries no behavioural meaning a reviewer should
have to explain away. No systematic, per-category SHAP audit was performed
beyond this (correction 3, above); doing so is recorded as future work
rather than claimed as complete.

---

**Verification status of this draft itself:** every fact above was checked
against the current repository — file contents, the actual `pytest`
collection count, and the exported CSV's real columns — rather than written
from recollection, per the same standard applied throughout Chapter 5.
