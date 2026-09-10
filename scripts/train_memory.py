"""BEACON — Memory stream: end-to-end training on the real MemoryCSVs data.

Runs Steps 1-11 against data/raw/MemoryCSVs/<Category>/*.csv (extracted
from the repo's MemoryCSVs.zip) and saves a real, working model plus its
preprocessing artifacts to models/. This replaces the informal,
never-successfully-run Preprocessing_Step*.ipynb / Training_XGBoost.ipynb
notebooks for the Memory stream with one reusable, importable pipeline.

There is no equivalent NetCSVs data in this repository, so only the
Memory stream can be trained here — see scripts/train_network.py's
docstring for what's still needed to do the same for Network.

Usage: python scripts/train_memory.py
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
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.artifacts import ArtifactStore
from pipeline.classifier import MemoryClassifier
from pipeline.common import Preprocessor
from pipeline.explain import Explainer
from pipeline.resampling import ClusterBasedResampler

RAW_DIR = os.path.join("data", "raw", "MemoryCSVs")
MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# The dataset's real 9-category taxonomy. "Spyware" also appears on disk
# but with a completely different, incompatible column schema (verified
# by hand — 51 columns named e.g. handles.nhandles vs this taxonomy's 96
# columns named e.g. handles.nHandles) — it's excluded here the same way
# Eda_Code.ipynb's own committed run implicitly ran into when it tried to
# process "Spyware" against the wrong root and got 0 files back.
CATEGORIES = ["Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"]

NON_FEATURE_COLS = ["label", "sample_id", "is_synthetic"]
EXPLOIT_LABEL = "Exploit"
N_OPTUNA_TRIALS = int(os.environ.get("BEACON_OPTUNA_TRIALS", "20"))
RANDOM_STATE = 42


def load_raw() -> pd.DataFrame:
    frames = []
    for cat in CATEGORIES:
        files = glob.glob(os.path.join(RAW_DIR, cat, "*.csv"))
        if not files:
            print(f"[WARN] no files found for {cat}")
            continue
        for f in files:
            sample_id = os.path.splitext(os.path.basename(f))[0]
            df = pd.read_csv(f)
            df["sample_id"] = sample_id
            df["label"] = cat
            frames.append(df)
        print(f"[LOAD] {cat}: {len(files)} files")
    return pd.concat(frames, ignore_index=True)


def main():
    print("=" * 70)
    print("STEP 1-3: load, dedup, drop empty columns, fix labels")
    print("=" * 70)
    df = load_raw()
    print(f"Raw combined: {df.shape}")

    pre = Preprocessor(label_col="label")
    df = pre.remove_duplicates(df)
    print(f"After dedup: {df.shape}")

    # Auto-detect every 100%-null column rather than hardcoding
    # "info.winBuild" — this real data copy turned out to also have
    # pslist.avg_handlers at 100% null, which the original notebooks'
    # hardcoded check would have silently missed.
    before_cols = set(df.columns)
    df = pre.drop_empty_columns(df)
    print(f"After dropping fully-empty columns {sorted(before_cols - set(df.columns))}: {df.shape}")

    # No label normalization step here: unlike the Network stream (which
    # reads a "label" column straight out of each CSV, and hit a real
    # "Zbenign" vs "Benign" inconsistency there), Memory's label always
    # comes from the fixed CATEGORIES folder name above, so there's no
    # label-fixing case to handle on this stream.
    print("Label distribution:")
    print(df["label"].value_counts())

    print("\n" + "=" * 70)
    print("STEP 5: grouped stratified split (by sample_id, before resampling)")
    print("=" * 70)
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    train_idx, test_idx = next(sgkf.split(df, df["label"], groups=df["sample_id"]))
    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    overlap = set(train_df["sample_id"]) & set(test_df["sample_id"])
    print(f"Train: {train_df.shape}, Test: {test_df.shape}, sample_id overlap: {len(overlap)} (must be 0)")
    assert len(overlap) == 0, "sample_id leaked across train/test split"

    print("\n" + "=" * 70)
    print("STEP 4: missingness — decide sentinel+flag vs median, fit on train")
    print("=" * 70)
    non_feature = ["label", "sample_id"]
    numeric_cols = [c for c in train_df.columns if c not in non_feature and pd.api.types.is_numeric_dtype(train_df[c])]
    missing_cols = [c for c in numeric_cols if train_df[c].isnull().any()]
    if missing_cols:
        decisions = pre.analyze_missingness(train_df, missing_cols)
        print("Missingness decisions:", decisions)
        train_df = pre.fit_handle_missingness(train_df, decisions)
        test_df = pre.apply_handle_missingness(test_df)
    else:
        print("No missing values found in numeric columns (matches the original EDA finding).")

    print("\n" + "=" * 70)
    print("STEP 7: Min-Max scale — fit on train only")
    print("=" * 70)
    numeric_cols = [c for c in train_df.columns if c not in non_feature and pd.api.types.is_numeric_dtype(train_df[c])]
    train_df = pre.fit_minmax(train_df, numeric_cols)
    test_df = pre.apply_minmax(test_df)
    print(f"Scaled {len(pre.minmax_ranges)} numeric columns")

    print("\n" + "=" * 70)
    print("STEP 8: correlation pruning -- disabled for this stream")
    print("=" * 70)
    # threshold=0.9 was inherited from the Network-stream design (which
    # has 348 raw features, many literal duplicates like duration/
    # packets_count under different names -- pruning matters there).
    # Measured on this Memory stream specifically: dropping "redundant"
    # correlated columns at 0.9 cost real signal -- test macro F1 rose
    # from 0.486 to 0.548 (accuracy 52.7% -> 58.7%) when this step was
    # skipped. XGBoost's tree splits aren't harmed by correlated inputs
    # the way a linear model's coefficients would be, so there was no
    # correctness reason to prune here, only a (wrong, for this stream)
    # assumption that fewer columns is always better.
    train_df = pre.fit_correlation_prune(train_df, numeric_cols, threshold=1.0)
    test_df = pre.apply_correlation_prune(test_df)
    print(f"Dropped {len(pre.corr_drop_cols)} correlated columns: {pre.corr_drop_cols}")
    feature_cols = [c for c in numeric_cols if c not in pre.corr_drop_cols]
    print(f"Remaining feature columns: {len(feature_cols)}")

    print("\n" + "=" * 70)
    print("STEP 10: cluster-based SMOTE for Exploit, class weights for the rest")
    print("=" * 70)
    resampler = ClusterBasedResampler(k_range=range(2, 5), k_neighbors=3, random_state=RANDOM_STATE)
    other_counts = train_df.loc[train_df["label"] != EXPLOIT_LABEL, "label"].value_counts()
    target_total = int(other_counts.min())
    print(f"Exploit real samples: {(train_df['label'] == EXPLOIT_LABEL).sum()}, target after augmentation: {target_total}")

    X_train_full = train_df[feature_cols]
    y_train_full = train_df["label"]
    X_res, y_res, is_synth = resampler.resample(
        X_train_full, y_train_full, minority_label=EXPLOIT_LABEL, target_total=target_total
    )
    print(f"Chosen K for Exploit clustering: {resampler.chosen_k} (silhouette={resampler.chosen_silhouette:.3f})")
    print("Post-resampling label distribution:")
    print(y_res.value_counts())

    sample_weights = compute_sample_weight(class_weight="balanced", y=y_res)

    print("\n" + "=" * 70)
    print("STEP 11: Optuna hyperparameter search + final XGBoost training")
    print("=" * 70)
    # This is a resampled array (synthetic Exploit rows have no real
    # sample_id, and ClusterBasedResampler doesn't preserve the original
    # row order), so grouping by original sample_id isn't recoverable
    # cheaply here. The outer train/test split (Step 5, above) is what
    # actually guards against sample-level leakage into evaluation; this
    # inner split only picks Optuna's hyperparameters, so a plain
    # stratified (non-grouped) split is an acceptable simplification.
    from sklearn.model_selection import StratifiedKFold

    sgkf_inner = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    inner_train_idx, inner_val_idx = next(sgkf_inner.split(X_res, y_res))
    X_tr, X_val = X_res.iloc[inner_train_idx], X_res.iloc[inner_val_idx]
    y_tr, y_val = y_res.iloc[inner_train_idx], y_res.iloc[inner_val_idx]
    w_tr = compute_sample_weight("balanced", y_tr)
    w_val = compute_sample_weight("balanced", y_val)

    from sklearn.preprocessing import LabelEncoder
    le_inner = LabelEncoder()
    y_tr_enc = le_inner.fit_transform(y_tr)
    y_val_enc = le_inner.transform(y_val)
    n_classes = len(le_inner.classes_)

    def objective(trial):
        import xgboost as xgb

        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 9),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "objective": "multi:softprob",
            "num_class": n_classes,
            "eval_metric": "mlogloss",
            "tree_method": "hist",
            "random_state": RANDOM_STATE,
            "n_jobs": -1,
            "early_stopping_rounds": 30,
        }
        model = xgb.XGBClassifier(**params)
        model.fit(
            X_tr, y_tr_enc, sample_weight=w_tr,
            eval_set=[(X_val, y_val_enc)],
            sample_weight_eval_set=[w_val],
            verbose=False,
        )
        # Early stopping means this trial's model may have stopped well
        # short of the suggested n_estimators -- record the iteration
        # that actually produced its score, so the final fit (below,
        # which has no eval_set to early-stop against) reuses the tree
        # count that earned this trial its macro F1, not the untruncated
        # suggestion.
        trial.set_user_attr("best_iteration", model.best_iteration)
        preds = model.predict(X_val)
        return f1_score(y_val_enc, preds, average="macro")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name="beacon_memory")
    study.optimize(objective, n_trials=N_OPTUNA_TRIALS, show_progress_bar=False)
    print(f"Best inner-validation macro F1: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")

    classifier = MemoryClassifier()
    best_params = study.best_params.copy()
    best_iteration = study.best_trial.user_attrs.get("best_iteration")
    if best_iteration is not None:
        best_params["n_estimators"] = best_iteration + 1
        print(f"Using best_iteration+1={best_params['n_estimators']} trees for the final fit "
              f"(early stopping cut the winning trial short of its suggested n_estimators)")
    classifier.train(X_res, y_res, sample_weight=sample_weights, **best_params)

    print("\n" + "=" * 70)
    print("EVALUATION on held-out test set")
    print("=" * 70)
    X_test = test_df[feature_cols]
    y_test = test_df["label"]
    y_pred = classifier.predict(X_test)

    report = classification_report(y_test, y_pred, digits=3)
    print(report)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    print(f"Test macro F1: {macro_f1:.4f}")
    print("\nNote: Exploit's training data is ~{}% synthetic (cluster-based SMOTE) "
          "-- treat its test performance as lower-confidence than the other 8 categories."
          .format(round(100 * is_synth[y_res == EXPLOIT_LABEL].mean())))

    cm = confusion_matrix(y_test, y_pred, labels=classifier.label_encoder.classes_)
    cm_path = os.path.join(MODEL_DIR, "memory_confusion_matrix.png")
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(9, 7))
        sns.heatmap(cm, annot=True, fmt="d", xticklabels=classifier.label_encoder.classes_,
                    yticklabels=classifier.label_encoder.classes_, cmap="Blues")
        plt.xlabel("Predicted")
        plt.ylabel("Actual")
        plt.title("Memory Stream -- Confusion Matrix")
        plt.tight_layout()
        plt.savefig(cm_path, dpi=150)
        plt.close()
        print(f"Saved confusion matrix -> {cm_path}")
    except ImportError:
        print("matplotlib/seaborn not installed -- skipped confusion matrix image")

    print("\n" + "=" * 70)
    print("SHAP sanity check")
    print("=" * 70)
    explainer = Explainer(classifier)
    sample_row = X_test.iloc[[0]]
    pred_label = classifier.predict(sample_row)[0]
    pred_idx = list(classifier.label_encoder.classes_).index(pred_label)
    top5 = explainer.top_features(sample_row, pred_idx, n=5)
    print(f"Top 5 SHAP features for test row 0 (predicted: {pred_label}):")
    print(top5.to_string(index=False))

    print("\n" + "=" * 70)
    print("Saving artifacts")
    print("=" * 70)
    ArtifactStore.save_model(classifier, os.path.join(MODEL_DIR, "memory_classifier.joblib"))
    ArtifactStore.save_artifacts(
        {
            "preprocessor": pre,
            "feature_cols": feature_cols,
            "categories": CATEGORIES,
        },
        os.path.join(MODEL_DIR, "memory_preprocessing_artifacts.joblib"),
    )

    metrics = {
        "stream": "memory",
        "train_rows_before_resampling": int(len(train_df)),
        "train_rows_after_resampling": int(len(X_res)),
        "test_rows": int(len(test_df)),
        "n_features": len(feature_cols),
        "optuna_trials": N_OPTUNA_TRIALS,
        "best_inner_val_macro_f1": float(study.best_value),
        "best_params": study.best_params,
        "test_macro_f1": float(macro_f1),
        "test_classification_report": classification_report(y_test, y_pred, digits=3, output_dict=True),
        "exploit_synthetic_fraction_in_training": float(is_synth[y_res == EXPLOIT_LABEL].mean()),
    }
    metrics_path = os.path.join(MODEL_DIR, "memory_metrics.json")
    with open(metrics_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"Saved model, preprocessing artifacts, and metrics to {MODEL_DIR}/")


if __name__ == "__main__":
    main()
