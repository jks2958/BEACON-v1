"""BEACON — MalMem specialist: a deliberately SEPARATE third model, trained
on an external memory-forensics dataset (CIC-MalMem-2022 / "Obfuscated
Malware Memory 2022", University of New Brunswick) rather than BCCC's.

WHY THIS IS A SEPARATE MODEL, NOT MORE MEMORY-STREAM DATA
-----------------------------------------------------------
CIC-MalMem-2022 does not share BCCC-Mal-NetMem-2025's category taxonomy or
its feature schema:

  - Categories don't line up. This dataset's malware side is Ransomware /
    Spyware / Trojan Horse (15 families). BEACON's Memory stream classifies
    Backdoor / Exploit / HackTool / Hoax / Rootkit / Trojan / Virus / Worm.
    Only "Trojan" overlaps by name, and even that names a different set of
    specific families. There is no "Exploit" category here at all -- the
    one class this project is weakest on -- so this dataset cannot patch
    that gap even in principle.
  - Features don't line up. This dataset's 55-ish columns come from
    VolMemLyzer; BCCC's ~98 columns come straight out of raw Volatility
    plugin output. Different tool, different column names, different
    aggregation choices. Concatenating the two CSVs would silently train
    on nonsense (columns aligned by position, not by meaning).
  - No sample-grouping column. BCCC's memory rows carry a sample_id used
    for a StratifiedGroupKFold split (Section 5.5.3 of the project's
    design doc found even that has real caveats). This dataset is one row
    per sample with no such column, so a plain stratified split is used
    here instead -- documented, not hidden.

So this script trains its own model on its own taxonomy, saves it under
its own model_* / metrics filenames, and is evaluated on its own terms.
Nothing here touches models/memory_*.

SCHEMA IS AUTO-DETECTED, NOT HARDCODED
-----------------------------------------------------------
This script has never been run against the real file in this repo -- the
CSV has to be downloaded by hand (see README) because this environment's
egress proxy blocks kaggle.com, the UNB CIC site, and IEEE DataPort alike.
Column names below are taken from the dataset's public documentation, not
from inspecting the actual file, so detect_schema() prints every column
name/dtype and the full label distribution before touching anything else,
and fails loudly with a clear message rather than guessing if the columns
it expects aren't there. If the real file's column names differ, fix
CANDIDATE_LABEL_COLS / CANDIDATE_CLASS_COLS below and re-run -- don't
patch around a mismatch downstream.

Usage:
    1. Download the dataset yourself (this sandbox cannot reach the host):
       https://www.kaggle.com/datasets/luccagodoy/obfuscated-malware-memory-2022-cic
       or https://www.unb.ca/cic/datasets/malmem-2022.html
    2. Place the CSV(s) under data/raw/CIC-MalMem-2022/
    3. python scripts/train_malmem_specialist.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.artifacts import ArtifactStore
from pipeline.classifier import MalMemSpecialistClassifier
from pipeline.common import Preprocessor

RAW_GLOB = os.environ.get("BEACON_MALMEM_RAW_GLOB",
                          os.path.join("data", "raw", "CIC-MalMem-2022", "*.csv"))
MODEL_DIR = os.environ.get("BEACON_MODEL_DIR", "models")
N_OPTUNA_TRIALS = int(os.environ.get("BEACON_OPTUNA_TRIALS", "20"))
RANDOM_STATE = 42

# Priority-ordered candidate column names for the fine-grained family label
# and the coarse binary label, per the dataset's public documentation.
# detect_schema() tries these in order and reports which one it used.
CANDIDATE_LABEL_COLS = ["Category", "category", "label", "Label"]
CANDIDATE_CLASS_COLS = ["Class", "class"]
# Columns that are identifiers/metadata, never model features, if present.
NON_FEATURE_HINTS = ["unnamed: 0", "unnamed:0", "index", "id", "filename", "file_name"]


def load_raw() -> pd.DataFrame:
    files = sorted(glob.glob(RAW_GLOB))
    if not files:
        raise FileNotFoundError(
            f"No CSV found at {RAW_GLOB}. Download CIC-MalMem-2022 yourself "
            "(this sandbox cannot reach kaggle.com or unb.ca) and place the "
            "CSV under data/raw/CIC-MalMem-2022/ -- see this file's docstring "
            "for the two source URLs."
        )
    frames = [pd.read_csv(f) for f in files]
    for f, d in zip(files, frames):
        print(f"[LOAD] {f}: {d.shape}")
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def detect_schema(df: pd.DataFrame) -> tuple[str, str | None, list[str]]:
    """Find the label column(s) and the non-feature columns, printing full
    diagnostics first. Returns (family_label_col, class_label_col_or_None,
    non_feature_cols). Raises with a clear message if nothing usable is
    found, rather than guessing.
    """
    print("=" * 70)
    print("SCHEMA DETECTION (this file has not been verified against the "
          "real dataset -- read this block on first run)")
    print("=" * 70)
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print(df.dtypes.value_counts())

    family_col = next((c for c in CANDIDATE_LABEL_COLS if c in df.columns), None)
    class_col = next((c for c in CANDIDATE_CLASS_COLS if c in df.columns), None)
    if family_col is None:
        raise ValueError(
            f"None of the expected label columns {CANDIDATE_LABEL_COLS} were "
            f"found. Actual columns: {list(df.columns)}. Update "
            "CANDIDATE_LABEL_COLS in this script to match the real file."
        )
    print(f"\nFamily label column: '{family_col}'")
    print(df[family_col].value_counts())
    if class_col:
        print(f"\nBinary class column: '{class_col}'")
        print(df[class_col].value_counts())
    else:
        print("\nNo separate binary class column found (not required).")

    non_feature = [c for c in df.columns
                   if c.strip().lower() in NON_FEATURE_HINTS or c in (family_col, class_col)]
    print(f"\nNon-feature columns excluded: {non_feature}")
    return family_col, class_col, non_feature


def derive_family_group(series: pd.Series) -> pd.Series:
    """CIC-MalMem-2022's Category column is documented as fine-grained
    (e.g. 'Trojan-Reconyc', 'Ransomware-Ako', 'Spyware-180solutions', plain
    'Benign'). This collapses to the coarse supercategory this specialist
    actually classifies -- taking the text before the first '-' where one
    exists, and the raw value otherwise. If the real column turns out to
    already BE the coarse label (no '-' in any value), this is a no-op."""
    return series.astype(str).str.split("-", n=1).str[0]


def main():
    df = load_raw()
    print(f"\nRaw combined: {df.shape}")

    pre = Preprocessor(label_col="label")
    df = pre.remove_duplicates(df)
    print(f"After dedup: {df.shape}")

    family_col, class_col, non_feature_raw = detect_schema(df)
    df["label"] = derive_family_group(df[family_col])
    print("\nDerived family-group label distribution (what this model predicts):")
    print(df["label"].value_counts())
    n_classes_found = df["label"].nunique()
    if n_classes_found < 2:
        raise ValueError(
            f"Only {n_classes_found} distinct label(s) after grouping -- "
            "derive_family_group() likely mis-parsed the real column. Fix "
            "it before continuing rather than training on a degenerate split."
        )

    before_cols = set(df.columns)
    df = pre.drop_empty_columns(df)
    if before_cols - set(df.columns):
        print(f"Dropped fully-empty columns: {sorted(before_cols - set(df.columns))}")

    non_feature = ["label"] + [c for c in non_feature_raw if c in df.columns]

    print("\n" + "=" * 70)
    print("SPLIT -- plain stratified 80/20 (no sample-grouping column exists "
          "in this dataset; see this file's docstring)")
    print("=" * 70)
    class_counts = df["label"].value_counts()
    rare = class_counts[class_counts < 10]
    if len(rare):
        print(f"[WARN] very small classes, treat their test-set numbers as "
              f"low-confidence: {dict(rare)}")
    train_df, test_df = train_test_split(
        df, test_size=0.2, stratify=df["label"], random_state=RANDOM_STATE)
    train_df = train_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)
    print(f"Train: {train_df.shape}, Test: {test_df.shape}")

    print("\n" + "=" * 70)
    print("Missingness -- fit on train only")
    print("=" * 70)
    numeric_cols = [c for c in train_df.columns
                    if c not in non_feature and pd.api.types.is_numeric_dtype(train_df[c])]
    missing_cols = [c for c in numeric_cols if train_df[c].isnull().any()]
    if missing_cols:
        decisions = pre.analyze_missingness(train_df, missing_cols)
        print("Missingness decisions:", decisions)
        train_df = pre.fit_handle_missingness(train_df, decisions)
        test_df = pre.apply_handle_missingness(test_df)
    else:
        print("No missing values in numeric columns.")

    print("\n" + "=" * 70)
    print("Min-Max scale -- fit on train only")
    print("=" * 70)
    numeric_cols = [c for c in train_df.columns
                    if c not in non_feature and pd.api.types.is_numeric_dtype(train_df[c])]
    train_df = pre.fit_minmax(train_df, numeric_cols)
    test_df = pre.apply_minmax(test_df)
    print(f"Scaled {len(pre.minmax_ranges)} numeric columns")

    print("\n" + "=" * 70)
    print("Correlation pruning -- disabled by default")
    print("=" * 70)
    # Disabled by default on the same evidence basis as the BCCC Memory
    # stream (pruning cost real signal there: 52.7% -> 58.7% when turned
    # off). This is a DIFFERENT feature set (VolMemLyzer, not raw
    # Volatility), so that specific number doesn't transfer -- but the
    # underlying reason does: XGBoost's tree splits aren't harmed by
    # correlated inputs, so there's no correctness reason to prune, only
    # an unproven assumption that fewer columns helps. Set
    # BEACON_MALMEM_CORR_THRESHOLD to A/B this once real data is in.
    corr_threshold = float(os.environ.get("BEACON_MALMEM_CORR_THRESHOLD", "1.0"))
    train_df = pre.fit_correlation_prune(train_df, numeric_cols, threshold=corr_threshold)
    test_df = pre.apply_correlation_prune(test_df)
    feature_cols = [c for c in numeric_cols if c not in pre.corr_drop_cols]
    print(f"threshold={corr_threshold}; dropped {len(pre.corr_drop_cols)}; "
          f"{len(feature_cols)} features remain")

    print("\n" + "=" * 70)
    print("Class weighting -- balanced (no synthetic oversampling)")
    print("=" * 70)
    # Unlike BCCC Memory's Exploit class (80 real samples against ~200 for
    # every other category), this dataset's public documentation doesn't
    # report anywhere near that severe an imbalance, so cluster-based SMOTE
    # is not applied speculatively -- balanced class weights, plus the
    # [WARN] above if any class turns out to be small in the real file.
    X_train, y_train = train_df[feature_cols], train_df["label"]
    X_test, y_test = test_df[feature_cols], test_df["label"]
    sample_weights = compute_sample_weight("balanced", y_train)

    print("\n" + "=" * 70)
    print("Optuna hyperparameter search + final XGBoost training")
    print("=" * 70)
    sgkf_inner = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    inner_train_idx, inner_val_idx = next(sgkf_inner.split(X_train, y_train))
    X_tr, X_val = X_train.iloc[inner_train_idx], X_train.iloc[inner_val_idx]
    y_tr, y_val = y_train.iloc[inner_train_idx], y_train.iloc[inner_val_idx]
    w_tr = compute_sample_weight("balanced", y_tr)
    w_val = compute_sample_weight("balanced", y_val)

    le_inner = LabelEncoder()
    y_tr_enc = le_inner.fit_transform(y_tr)
    y_val_enc = le_inner.transform(y_val)
    n_classes = len(le_inner.classes_)

    def objective(trial):
        import xgboost as xgb

        base = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 9),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "tree_method": "hist", "random_state": RANDOM_STATE, "n_jobs": -1,
            "early_stopping_rounds": 30,
        }
        # Mirrors the binary-vs-multiclass objective fix in
        # pipeline/classifier.py: num_class=2 under multi:softprob returns
        # a 2-column matrix from predict(), breaking every sklearn metric.
        if n_classes == 2:
            params = {**base, "objective": "binary:logistic", "eval_metric": "logloss"}
        else:
            params = {**base, "objective": "multi:softprob", "num_class": n_classes,
                      "eval_metric": "mlogloss"}
        model = xgb.XGBClassifier(**params)
        model.fit(X_tr, y_tr_enc, sample_weight=w_tr,
                  eval_set=[(X_val, y_val_enc)], sample_weight_eval_set=[w_val], verbose=False)
        trial.set_user_attr("best_iteration", model.best_iteration)
        return f1_score(y_val_enc, model.predict(X_val), average="macro")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name="beacon_malmem_specialist")
    study.optimize(objective, n_trials=N_OPTUNA_TRIALS, show_progress_bar=False)
    print(f"Best inner-validation macro F1: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")

    classifier = MalMemSpecialistClassifier()
    best_params = study.best_params.copy()
    best_iteration = study.best_trial.user_attrs.get("best_iteration")
    if best_iteration is not None:
        best_params["n_estimators"] = best_iteration + 1
    classifier.train(X_train, y_train, sample_weight=sample_weights, **best_params)

    print("\n" + "=" * 70)
    print("EVALUATION on held-out test set")
    print("=" * 70)
    y_pred = classifier.predict(X_test)
    print(classification_report(y_test, y_pred, digits=3))
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    acc = (y_pred == y_test.values).mean()
    print(f"Test accuracy: {acc:.4f}  macro F1: {macro_f1:.4f}")

    # Secondary diagnostic: how this maps onto the dataset's own binary
    # Class column, purely for comparing against literature-reported
    # binary numbers on this same dataset. Not the model this script ships.
    binary_report = None
    if class_col and class_col in test_df.columns:
        binary_pred = np.where(y_pred == "Benign", "Benign", "Malware")
        binary_truth = test_df[class_col].astype(str)
        binary_report = classification_report(binary_truth, binary_pred, digits=3, output_dict=True)
        print("\nSecondary diagnostic -- collapsed to the dataset's own binary "
              "Benign/Malware label (not what this model was trained to predict):")
        print(classification_report(binary_truth, binary_pred, digits=3))

    cm = confusion_matrix(y_test, y_pred, labels=classifier.label_encoder.classes_)
    cm_path = os.path.join(MODEL_DIR, "malmem_specialist_confusion_matrix.png")
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(7, 5.5))
        sns.heatmap(cm, annot=True, fmt="d", xticklabels=classifier.label_encoder.classes_,
                    yticklabels=classifier.label_encoder.classes_, cmap="Blues")
        plt.xlabel("Predicted"); plt.ylabel("Actual")
        plt.title("MalMem Specialist (CIC-MalMem-2022) -- Confusion Matrix")
        plt.tight_layout()
        os.makedirs(MODEL_DIR, exist_ok=True)
        plt.savefig(cm_path, dpi=150)
        plt.close()
        print(f"Saved confusion matrix -> {cm_path}")
    except ImportError:
        print("matplotlib/seaborn not installed -- skipped confusion matrix image")

    print("\n" + "=" * 70)
    print("Saving artifacts (separate from memory_*/network_* on purpose)")
    print("=" * 70)
    os.makedirs(MODEL_DIR, exist_ok=True)
    ArtifactStore.save_model(classifier, os.path.join(MODEL_DIR, "malmem_specialist_classifier.joblib"))
    ArtifactStore.save_artifacts(
        {"preprocessor": pre, "feature_cols": feature_cols,
         "categories": sorted(df["label"].unique().tolist())},
        os.path.join(MODEL_DIR, "malmem_specialist_preprocessing_artifacts.joblib"),
    )

    metrics = {
        "stream": "malmem_specialist",
        "source": "CIC-MalMem-2022 (University of New Brunswick) -- NOT the "
                  "BCCC-Mal-NetMem-2025 dataset the rest of BEACON is trained on",
        "family_label_column_used": family_col,
        "class_label_column_used": class_col,
        "categories": sorted(df["label"].unique().tolist()),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "n_features": len(feature_cols),
        "corr_threshold": corr_threshold,
        "optuna_trials": N_OPTUNA_TRIALS,
        "best_inner_val_macro_f1": float(study.best_value),
        "best_params": best_params,
        "best_params_suggested": study.best_params,
        "test_accuracy": float(acc),
        "test_macro_f1": float(macro_f1),
        "test_classification_report": classification_report(y_test, y_pred, digits=3, output_dict=True),
        "small_class_warning": {k: int(v) for k, v in rare.items()} if len(rare) else None,
        "binary_diagnostic_vs_dataset_class_column": binary_report,
    }
    metrics_path = os.path.join(MODEL_DIR, "malmem_specialist_metrics.json")
    with open(metrics_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"Saved model, preprocessing artifacts, and metrics to {MODEL_DIR}/")
    print("\nThis model is NOT wired into the Streamlit dashboard and does "
          "NOT change models/memory_metrics.json. Reported as its own "
          "result on its own taxonomy.")


if __name__ == "__main__":
    main()
