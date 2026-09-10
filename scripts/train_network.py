"""BEACON — Network stream: end-to-end training on the real NetCSVs data.

Mirrors scripts/train_memory.py, but handles three things that are
specific to the Network stream and absent from Memory:

  1. NetCSVs carry their OWN `label` column (Memory's label came from the
     folder name). That makes the "Zbenign" -> "Benign" normalization
     live here -- it is a real inconsistency in this data, not the dead
     code it was on the Memory side.
  2. `delta_start` and `handshake_duration` contain the literal string
     "not a complete handshake" in ~44% of rows. That is a behavioral
     signal (the TCP handshake never completed), not corrupt data, so it
     becomes an explicit indicator feature instead of being nulled away.
  3. Identifier columns (flow_id, timestamp, src_ip, dst_ip, protocol)
     must be dropped outright. Leaving them in is exactly what crashed
     the original Training_XGBoost.ipynb at Optuna trial 0.

Usage: python scripts/train_network.py
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
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.artifacts import ArtifactStore
from pipeline.classifier import NetworkClassifier
from pipeline.common import Preprocessor
from pipeline.explain import Explainer

RAW_DIR = os.path.join("data", "raw", "NetCSVs")
# Overridable so a partial-data smoke test can't overwrite the real
# committed artifacts with a model trained on a subset of categories.
MODEL_DIR = os.environ.get("BEACON_MODEL_DIR", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

CATEGORIES = ["Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"]

# Live on this stream: the Benign network captures label themselves
# "Zbenign" internally, which would otherwise become a spurious 10th class.
LABEL_FIXES = {"Zbenign": "Benign"}

# Pure identifiers -- never model features. src_ip/dst_ip in particular
# would let the model memorise the lab's addressing rather than learn
# behaviour.
IDENTIFIER_COLS = ["flow_id", "timestamp", "src_ip", "dst_ip", "protocol"]

HANDSHAKE_COLS = ["delta_start", "handshake_duration"]
INCOMPLETE_HANDSHAKE = "not a complete handshake"

LOG_TRANSFORM_COLS = ["duration", "packets_count", "total_payload_bytes",
                      "bytes_rate", "packets_rate"]

NON_FEATURE_COLS = ["label", "sample_id"]
N_OPTUNA_TRIALS = int(os.environ.get("BEACON_OPTUNA_TRIALS", "15"))
# Memory-stream evidence said pruning cost real signal there; this stream
# has 347 raw columns with genuine near-duplicates, so it is worth A/B
# testing rather than assuming. 1.0 disables it (nothing exceeds |r|>1.0).
CORR_THRESHOLD = float(os.environ.get("BEACON_CORR_THRESHOLD", "1.0"))
RANDOM_STATE = 42


def load_raw() -> pd.DataFrame:
    """Load per-sample flow CSVs, downcasting to float32 on the way in --
    at ~646k rows x 347 columns, float64 would cost ~1.8GB before XGBoost
    takes its own copies."""
    frames, sample_ids, labels, lengths = [], [], [], []
    for cat in CATEGORIES:
        files = glob.glob(os.path.join(RAW_DIR, cat, "*.csv"))
        if not files:
            print(f"[WARN] no files found for {cat} -- skipping")
            continue
        for f in files:
            df = pd.read_csv(f, low_memory=False)
            for c in df.select_dtypes(include=["float64"]).columns:
                df[c] = df[c].astype("float32")
            frames.append(df)
            # sample_id identifies the capture this flow came from, so the
            # grouped split can keep whole captures on one side. Collected
            # here and assigned after the concat -- assigning per-file to a
            # 347-column frame fragments it badly.
            sample_ids.append(os.path.basename(f).replace("_traffic_cleaned.pcap.csv", ""))
            labels.append(cat)
            lengths.append(len(df))
        print(f"[LOAD] {cat}: {len(files)} files", flush=True)

    combined = pd.concat(frames, ignore_index=True)
    combined["sample_id"] = np.repeat(sample_ids, lengths)
    if "label" not in combined.columns:
        combined["label"] = np.repeat(labels, lengths)
    return combined


def encode_handshake(df: pd.DataFrame) -> pd.DataFrame:
    """Turn 'not a complete handshake' into an explicit binary feature,
    then make the underlying columns genuinely numeric.

    Nulling these out (what ignore_errors=True did originally) throws away
    a real signal: a flow that never completed a handshake is behaviourally
    different from one that completed in 0.03s, and ~44% of rows are in
    that state."""
    df = df.copy()
    for col in HANDSHAKE_COLS:
        if col not in df.columns:
            continue
        incomplete = df[col].astype(str).str.strip() == INCOMPLETE_HANDSHAKE
        df[f"{col}_incomplete"] = incomplete.astype("int8")
        # -1 sentinel: distinguishable from any real duration (>= 0)
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
        df.loc[incomplete, col] = -1.0
    return df


def main():
    print("=" * 70)
    print("STEP 1-3: load, dedup, drop identifiers/empty columns, fix labels")
    print("=" * 70)
    df = load_raw()
    print(f"Raw combined: {df.shape}")
    print(f"Memory footprint: {df.memory_usage(deep=True).sum() / 1e9:.2f} GB")

    pre = Preprocessor(label_col="label")
    df = pre.remove_duplicates(df)
    print(f"After dedup: {df.shape}")

    df = encode_handshake(df)
    n_incomplete = int(df.get("delta_start_incomplete", pd.Series(dtype="int8")).sum())
    print(f"Flows with an incomplete handshake: {n_incomplete} "
          f"({n_incomplete / len(df) * 100:.1f}%) -- kept as an indicator feature")

    present_ids = [c for c in IDENTIFIER_COLS if c in df.columns]
    df = df.drop(columns=present_ids)
    print(f"Dropped identifier columns: {present_ids}")

    before_cols = set(df.columns)
    df = pre.drop_empty_columns(df)
    dropped_empty = sorted(before_cols - set(df.columns))
    print(f"Dropped fully-empty columns {dropped_empty}: {df.shape}")

    labels_before = sorted(df["label"].unique())
    df = pre.fix_labels(df, LABEL_FIXES)
    print(f"Labels {labels_before} -> {sorted(df['label'].unique())}")
    print("\nLabel distribution:")
    print(df["label"].value_counts())

    print("\n" + "=" * 70)
    print("STEP 5: grouped stratified split (by sample_id, before resampling)")
    print("=" * 70)
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    train_idx, test_idx = next(sgkf.split(df, df["label"], groups=df["sample_id"]))
    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    overlap = set(train_df["sample_id"]) & set(test_df["sample_id"])
    print(f"Train: {train_df.shape}, Test: {test_df.shape}, "
          f"sample_id overlap: {len(overlap)} (must be 0)")
    assert len(overlap) == 0, "sample_id leaked across the train/test split"
    del df

    print("\n" + "=" * 70)
    print("STEP 4: missingness handling (fit on train only)")
    print("=" * 70)
    numeric_cols = [c for c in train_df.columns
                    if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(train_df[c])]
    missing_cols = [c for c in numeric_cols if train_df[c].isnull().any()]
    if missing_cols:
        decisions = pre.analyze_missingness(train_df, missing_cols)
        structural = [c for c, d in decisions.items() if d == "structural"]
        print(f"{len(missing_cols)} column(s) with missing values; "
              f"{len(structural)} judged structural (sentinel+flag), rest median-imputed")
        train_df = pre.fit_handle_missingness(train_df, decisions)
        test_df = pre.apply_handle_missingness(test_df)
    else:
        print("No missing values in numeric columns.")

    print("\n" + "=" * 70)
    print("STEP 6: log-transform heavy-tailed features")
    print("=" * 70)
    train_df = pre.fit_log_transform(train_df, LOG_TRANSFORM_COLS)
    test_df = pre.apply_log_transform(test_df)
    print(f"Log-transformed: {pre.log_cols}")

    print("\n" + "=" * 70)
    print("STEP 7: Min-Max scale (fit on train only)")
    print("=" * 70)
    numeric_cols = [c for c in train_df.columns
                    if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(train_df[c])]
    train_df = pre.fit_minmax(train_df, numeric_cols)
    test_df = pre.apply_minmax(test_df)
    print(f"Scaled {len(pre.minmax_ranges)} numeric columns")

    print("\n" + "=" * 70)
    print(f"STEP 8: correlation pruning (threshold={CORR_THRESHOLD})")
    print("=" * 70)
    train_df = pre.fit_correlation_prune(train_df, numeric_cols, threshold=CORR_THRESHOLD)
    test_df = pre.apply_correlation_prune(test_df)
    feature_cols = [c for c in numeric_cols if c not in pre.corr_drop_cols]
    print(f"Dropped {len(pre.corr_drop_cols)} correlated columns; "
          f"{len(feature_cols)} features remain")

    print("\n" + "=" * 70)
    print("STEP 9: class weighting (moderate imbalance -- no SMOTE needed)")
    print("=" * 70)
    X_train, y_train = train_df[feature_cols], train_df["label"]
    X_test, y_test = test_df[feature_cols], test_df["label"]
    sample_weights = compute_sample_weight("balanced", y_train)
    ratio = y_train.value_counts().max() / y_train.value_counts().min()
    print(f"Imbalance ratio (max/min class): {ratio:.1f}:1 -- balanced weights applied")

    print("\n" + "=" * 70)
    print("STEP 11: Optuna hyperparameter search + final XGBoost training")
    print("=" * 70)
    from sklearn.preprocessing import LabelEncoder
    import xgboost as xgb

    le_inner = LabelEncoder()
    y_enc = le_inner.fit_transform(y_train)
    n_classes = len(le_inner.classes_)

    inner = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    i_tr, i_val = next(inner.split(X_train, y_enc))
    X_tr, X_val = X_train.iloc[i_tr], X_train.iloc[i_val]
    y_tr, y_val = y_enc[i_tr], y_enc[i_val]
    w_tr = compute_sample_weight("balanced", y_tr)
    w_val = compute_sample_weight("balanced", y_val)
    print(f"Inner train: {X_tr.shape}, inner val: {X_val.shape}")

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "tree_method": "hist",
            "random_state": RANDOM_STATE, "n_jobs": -1,
            "early_stopping_rounds": 30,
        }
        if n_classes == 2:
            params |= {"objective": "binary:logistic", "eval_metric": "logloss"}
        else:
            params |= {"objective": "multi:softprob", "num_class": n_classes,
                       "eval_metric": "mlogloss"}
        model = xgb.XGBClassifier(**params)
        model.fit(X_tr, y_tr, sample_weight=w_tr, eval_set=[(X_val, y_val)],
                  sample_weight_eval_set=[w_val], verbose=False)
        trial.set_user_attr("best_iteration", model.best_iteration)
        return f1_score(y_val, model.predict(X_val), average="macro")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name="beacon_network")
    study.optimize(objective, n_trials=N_OPTUNA_TRIALS, show_progress_bar=False)
    print(f"Best inner-validation macro F1: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")

    best_params = study.best_params.copy()
    best_iteration = study.best_trial.user_attrs.get("best_iteration")
    if best_iteration is not None:
        best_params["n_estimators"] = best_iteration + 1
        print(f"Final fit uses {best_params['n_estimators']} trees (early-stopped count)")

    classifier = NetworkClassifier()
    classifier.train(X_train, y_train, sample_weight=sample_weights, **best_params)

    print("\n" + "=" * 70)
    print("EVALUATION on held-out test set")
    print("=" * 70)
    y_pred = classifier.predict(X_test)
    print(classification_report(y_test, y_pred, digits=3))
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    accuracy = float((y_pred == y_test.values).mean())
    print(f"Test accuracy: {accuracy:.4f}   Test macro F1: {macro_f1:.4f}")

    cm = confusion_matrix(y_test, y_pred, labels=classifier.label_encoder.classes_)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(9, 7))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                    xticklabels=classifier.label_encoder.classes_,
                    yticklabels=classifier.label_encoder.classes_)
        plt.xlabel("Predicted"); plt.ylabel("Actual")
        plt.title("Network Stream -- Confusion Matrix")
        plt.tight_layout()
        plt.savefig(os.path.join(MODEL_DIR, "network_confusion_matrix.png"), dpi=150)
        plt.close()
        print(f"Saved confusion matrix -> {MODEL_DIR}/network_confusion_matrix.png")
    except ImportError:
        print("matplotlib/seaborn missing -- skipped confusion matrix image")

    print("\n" + "=" * 70)
    print("SHAP sanity check")
    print("=" * 70)
    explainer = Explainer(classifier)
    row = X_test.iloc[[0]]
    pred_label = classifier.predict(row)[0]
    pred_idx = list(classifier.label_encoder.classes_).index(pred_label)
    print(f"Top 5 SHAP features for test row 0 (predicted: {pred_label}):")
    print(explainer.top_features(row, pred_idx, n=5).to_string(index=False))

    print("\n" + "=" * 70)
    print("Saving artifacts")
    print("=" * 70)
    ArtifactStore.save_model(classifier, os.path.join(MODEL_DIR, "network_classifier.joblib"))
    ArtifactStore.save_artifacts(
        {"preprocessor": pre, "feature_cols": feature_cols, "categories": CATEGORIES},
        os.path.join(MODEL_DIR, "network_preprocessing_artifacts.joblib"))

    metrics = {
        "stream": "network",
        "categories_present": sorted(y_train.unique().tolist()),
        "train_rows": int(len(X_train)), "test_rows": int(len(X_test)),
        "n_features": len(feature_cols),
        "corr_threshold": CORR_THRESHOLD,
        "optuna_trials": N_OPTUNA_TRIALS,
        "best_inner_val_macro_f1": float(study.best_value),
        "best_params": study.best_params,
        "test_accuracy": accuracy,
        "test_macro_f1": float(macro_f1),
        "test_classification_report": classification_report(y_test, y_pred, digits=3,
                                                            output_dict=True),
        "incomplete_handshake_fraction": float(n_incomplete / (len(train_df) + len(test_df))),
    }
    with open(os.path.join(MODEL_DIR, "network_metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"Saved model, preprocessing artifacts, and metrics to {MODEL_DIR}/")


if __name__ == "__main__":
    main()
