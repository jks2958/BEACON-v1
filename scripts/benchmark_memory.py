"""Leakage-aware Memory-stream benchmark and snapshot-family experiment.

This script does not overwrite the shipped model.  It measures alternative
group definitions and an optional family-summary representation, writing a
machine-readable report to ``models/memory_experiments.json``.

Usage:
    unzip MemoryCSVs.zip -d data/raw/
    python scripts/benchmark_memory.py --representation both
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.memory_groups import aggregate_snapshot_features, memory_group_id


CATEGORIES = ["Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"]


def load_raw(raw_dir: str, group_mode: str) -> pd.DataFrame:
    frames = []
    for category in CATEGORIES:
        for path in sorted(glob.glob(os.path.join(raw_dir, category, "*.csv"))):
            stem = os.path.splitext(os.path.basename(path))[0]
            frame = pd.read_csv(path)
            frame["label"] = category
            frame["stem"] = stem
            frame["group_id"] = memory_group_id(category, stem, group_mode)
            frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No Memory CSVs found under {raw_dir!r}")
    return pd.concat(frames, ignore_index=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    excluded = {"label", "stem", "group_id"}
    return [column for column in frame.select_dtypes(include=np.number)
            if column not in excluded and not frame[column].isna().all()]


def make_model(name: str):
    if name == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=500, max_features="sqrt", class_weight="balanced",
            n_jobs=-1, random_state=42,
        )
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=300, l2_regularization=1.0, class_weight="balanced", random_state=42,
        )
    if name == "xgboost":
        # Reuse the shipped run's measured optimum as a strong, inexpensive
        # baseline. Hyperparameter search belongs outside this diagnostic
        # until the grouping/provenance question is settled.
        return XGBClassifier(
            n_estimators=400, max_depth=7, learning_rate=0.05549542126546421,
            subsample=0.8251401651626141, colsample_bytree=0.8092060458816955,
            objective="multi:softprob", num_class=len(CATEGORIES),
            eval_metric="mlogloss", tree_method="hist", n_jobs=-1, random_state=42,
        )
    raise ValueError(f"Unknown model: {name}")


def evaluate(frame: pd.DataFrame, features: list[str], model_name: str) -> dict:
    X = frame[features].replace([np.inf, -np.inf], np.nan).fillna(-1)
    y, groups = frame["label"], frame["group_id"]
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    if set(groups.iloc[train_idx]) & set(groups.iloc[test_idx]):
        raise RuntimeError("Group leakage detected")

    model = make_model(model_name)
    weights = compute_sample_weight("balanced", y.iloc[train_idx])
    started = time.monotonic()
    if model_name == "xgboost":
        encoder = LabelEncoder().fit(y)
        model.fit(X.iloc[train_idx], encoder.transform(y.iloc[train_idx]), sample_weight=weights)
        predictions = encoder.inverse_transform(model.predict(X.iloc[test_idx]).astype(int))
    else:
        model.fit(X.iloc[train_idx], y.iloc[train_idx], sample_weight=weights)
        predictions = model.predict(X.iloc[test_idx])
    return {
        "model": model_name,
        "accuracy": float(accuracy_score(y.iloc[test_idx], predictions)),
        "macro_f1": float(f1_score(y.iloc[test_idx], predictions, average="macro")),
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "n_features": len(features),
        "seconds": round(time.monotonic() - started, 3),
        "classification_report": classification_report(
            y.iloc[test_idx], predictions, output_dict=True, zero_division=0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=os.path.join("data", "raw", "MemoryCSVs"))
    parser.add_argument("--group-mode", choices=["stem", "category_stem", "snapshot_family"],
                        default="snapshot_family")
    parser.add_argument("--representation", choices=["rows", "summary", "both"], default="both")
    parser.add_argument("--models", nargs="+",
                        choices=["extra_trees", "hist_gradient_boosting", "xgboost"],
                        default=["extra_trees", "hist_gradient_boosting", "xgboost"])
    parser.add_argument("--output", default=os.path.join("models", "memory_experiments.json"))
    args = parser.parse_args()

    raw = load_raw(args.raw_dir, args.group_mode)
    features = feature_columns(raw)
    representations = {}
    if args.representation in {"rows", "both"}:
        representations["rows"] = (raw, features)
    if args.representation in {"summary", "both"}:
        summary = aggregate_snapshot_features(raw, features)
        representations["snapshot_summary"] = (
            summary, [column for column in summary if column not in {"label", "group_id"}]
        )

    results = []
    for representation, (frame, columns) in representations.items():
        for model_name in args.models:
            print(f"[RUN] {representation} / {model_name}", flush=True)
            result = evaluate(frame, columns, model_name)
            result["representation"] = representation
            results.append(result)
            print(f"      accuracy={result['accuracy']:.4f}, macro_f1={result['macro_f1']:.4f}")

    report = {
        "experiment": "memory leakage-safe alternatives",
        "group_mode": args.group_mode,
        "grouping_note": (
            "snapshot_family strips a terminal numeric suffix and is intentionally "
            "conservative until the dataset publisher confirms whether _1 ... _5 are "
            "repeated observations of one subject"
        ),
        "raw_rows": int(len(raw)),
        "groups": int(raw["group_id"].nunique()),
        "results": results,
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
