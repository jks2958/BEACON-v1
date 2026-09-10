"""BEACON — dual-stream fusion: one verdict per sample from both streams.

WHY THIS RETRAINS BOTH MODELS
-----------------------------
2,235 samples have a network capture and 5,731 have a memory dump, but
only 214 have BOTH -- and a fusion score is only meaningful on samples
neither model was trained on. Of those 214, just 41 are unseen by the
shipped memory model, and intersecting with the shipped network model's
held-out captures leaves single digits, with two categories at zero.

So this script trains EVALUATION-ONLY models that hold out all 214
dual-stream samples from both streams, and measures fusion on all 214.
It does not touch models/*.joblib -- the shipped models keep their own
(larger) training sets and their own reported numbers. The comparison
that matters is fusion vs each stream alone measured on the SAME samples
with the SAME models, which is exactly what this produces.

ONE DISCLOSED SHORTCUT
----------------------
Hyperparameters are reused from the shipped runs rather than re-searched,
which saves hours of Optuna. Those parameters were selected on splits that
included some of the 214, so they carry a weak second-order optimism. It
is disclosed in the output and in the metrics file rather than hidden.

Usage: python scripts/train_fusion.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.classifier import MemoryClassifier, NetworkClassifier
from pipeline.common import Preprocessor, encode_handshake
from pipeline.resampling import ClusterBasedResampler
from sklearn.utils.class_weight import compute_sample_weight

CATEGORIES = ["Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"]
NET_DIR = os.path.join("data", "raw", "NetCSVs")
MEM_DIR = os.path.join("data", "raw", "MemoryCSVs")
MODEL_DIR = os.environ.get("BEACON_MODEL_DIR", "models")
NET_SUFFIX = "_traffic_cleaned.pcap.csv"

IDENTIFIER_COLS = ["flow_id", "timestamp", "src_ip", "dst_ip", "protocol", "src_port"]
LABEL_FIXES = {"Zbenign": "Benign"}
LOG_TRANSFORM_COLS = ["duration", "packets_count", "total_payload_bytes",
                      "bytes_rate", "packets_rate"]
NON_FEATURE = ["label", "sample_id"]
RANDOM_STATE = 42

NET_PARAMS = {"n_estimators": 200, "max_depth": 10,
              "learning_rate": 0.04153498507513123,
              "subsample": 0.7148598656309413, "colsample_bytree": 0.6055887974495078}
MEM_PARAMS = {"n_estimators": 450, "max_depth": 7,
              "learning_rate": 0.05549542126546421,
              "subsample": 0.8251401651626141, "colsample_bytree": 0.8092060458816955}


def net_id(path: str) -> str:
    return os.path.basename(path).replace(NET_SUFFIX, "")


def mem_id(path: str) -> str:
    return re.sub(r"_timeout$", "", os.path.splitext(os.path.basename(path))[0])


def dual_stream_ids() -> dict[str, str]:
    """Samples carrying BOTH a network capture and a memory dump."""
    net = {net_id(f): cat for cat in CATEGORIES
           for f in glob.glob(os.path.join(NET_DIR, cat, "*.csv"))}
    mem = {mem_id(f) for cat in CATEGORIES
           for f in glob.glob(os.path.join(MEM_DIR, cat, "*.csv"))}
    return {s: c for s, c in net.items() if s in mem}


# ----------------------------------------------------------------------
# Network stream
# ----------------------------------------------------------------------

def load_network() -> pd.DataFrame:
    frames, ids, labels, lengths = [], [], [], []
    for cat in CATEGORIES:
        files = sorted(glob.glob(os.path.join(NET_DIR, cat, "*.csv")))
        for f in files:
            d = pd.read_csv(f, low_memory=False)
            frames.append(d)
            ids.append(net_id(f))
            labels.append(cat)
            lengths.append(len(d))
        print(f"[NET LOAD] {cat}: {len(files)} files", flush=True)
    combined = pd.concat(frames, ignore_index=True)
    combined["sample_id"] = np.repeat(ids, lengths)
    if "label" not in combined.columns:
        combined["label"] = np.repeat(labels, lengths)
    return combined


def build_network(holdout: set[str]):
    df = load_network()
    pre = Preprocessor(label_col="label")
    df = pre.remove_duplicates(df)
    df = encode_handshake(df)
    df = df.drop(columns=[c for c in IDENTIFIER_COLS if c in df.columns])
    df = pre.drop_empty_columns(df)
    df = pre.fix_labels(df, LABEL_FIXES)

    is_held = df["sample_id"].isin(holdout)
    train_df = df[~is_held].reset_index(drop=True)
    test_df = df[is_held].reset_index(drop=True)
    del df
    print(f"[NET] train rows={len(train_df):,}  holdout rows={len(test_df):,} "
          f"({test_df['sample_id'].nunique()} samples)", flush=True)
    assert not (set(train_df["sample_id"]) & set(test_df["sample_id"]))

    numeric = [c for c in train_df.columns
               if c not in NON_FEATURE and pd.api.types.is_numeric_dtype(train_df[c])]
    missing = [c for c in numeric if train_df[c].isnull().any()]
    if missing:
        train_df = pre.fit_handle_missingness(train_df, pre.analyze_missingness(train_df, missing))
        test_df = pre.apply_handle_missingness(test_df)
    train_df = pre.fit_log_transform(train_df, LOG_TRANSFORM_COLS)
    test_df = pre.apply_log_transform(test_df)
    numeric = [c for c in train_df.columns
               if c not in NON_FEATURE and pd.api.types.is_numeric_dtype(train_df[c])]
    train_df = pre.fit_minmax(train_df, numeric)
    test_df = pre.apply_minmax(test_df)
    train_df = pre.fit_correlation_prune(train_df, numeric, threshold=1.0)
    test_df = pre.apply_correlation_prune(test_df)
    feature_cols = [c for c in numeric if c not in pre.corr_drop_cols]

    clf = NetworkClassifier()
    weights = compute_sample_weight("balanced", train_df["label"])
    print(f"[NET] fitting on {len(train_df):,} rows x {len(feature_cols)} features…", flush=True)
    clf.train(train_df[feature_cols], train_df["label"], sample_weight=weights, **NET_PARAMS)
    return clf, test_df, feature_cols


# ----------------------------------------------------------------------
# Memory stream
# ----------------------------------------------------------------------

def load_memory() -> pd.DataFrame:
    frames = []
    for cat in CATEGORIES:
        files = sorted(glob.glob(os.path.join(MEM_DIR, cat, "*.csv")))
        for f in files:
            d = pd.read_csv(f)
            d["sample_id"] = mem_id(f)
            d["label"] = cat
            frames.append(d)
        print(f"[MEM LOAD] {cat}: {len(files)} files", flush=True)
    return pd.concat(frames, ignore_index=True)


def build_memory(holdout: set[str]):
    df = load_memory()
    pre = Preprocessor(label_col="label")
    df = pre.remove_duplicates(df)
    df = pre.drop_empty_columns(df)

    is_held = df["sample_id"].isin(holdout)
    train_df = df[~is_held].reset_index(drop=True)
    test_df = df[is_held].reset_index(drop=True)
    print(f"[MEM] train rows={len(train_df):,}  holdout rows={len(test_df):,} "
          f"({test_df['sample_id'].nunique()} samples)", flush=True)
    assert not (set(train_df["sample_id"]) & set(test_df["sample_id"]))

    numeric = [c for c in train_df.columns
               if c not in NON_FEATURE and pd.api.types.is_numeric_dtype(train_df[c])]
    missing = [c for c in numeric if train_df[c].isnull().any()]
    if missing:
        train_df = pre.fit_handle_missingness(train_df, pre.analyze_missingness(train_df, missing))
        test_df = pre.apply_handle_missingness(test_df)
    numeric = [c for c in train_df.columns
               if c not in NON_FEATURE and pd.api.types.is_numeric_dtype(train_df[c])]
    train_df = pre.fit_minmax(train_df, numeric)
    test_df = pre.apply_minmax(test_df)
    # threshold 1.0 == pruning disabled, matching the shipped memory model.
    train_df = pre.fit_correlation_prune(train_df, numeric, threshold=1.0)
    test_df = pre.apply_correlation_prune(test_df)
    feature_cols = [c for c in numeric if c not in pre.corr_drop_cols]

    # Exploit augmentation, as the shipped memory pipeline does.
    other = train_df.loc[train_df["label"] != "Exploit", "label"].value_counts()
    X_res, y_res, _ = ClusterBasedResampler(
        k_range=range(2, 5), k_neighbors=3, random_state=RANDOM_STATE
    ).resample(train_df[feature_cols], train_df["label"], "Exploit", int(other.min()))

    clf = MemoryClassifier()
    weights = compute_sample_weight("balanced", y_res)
    print(f"[MEM] fitting on {len(X_res):,} rows x {len(feature_cols)} features…", flush=True)
    clf.train(X_res, y_res, sample_weight=weights, **MEM_PARAMS)
    return clf, test_df, feature_cols


# ----------------------------------------------------------------------
# Fusion
# ----------------------------------------------------------------------

def per_sample_proba(clf, df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Mean class probability per sample -- a capture's flows (or a dump's
    rows) are evidence about ONE sample, so they combine into one vector."""
    proba = clf.predict_proba(df[feature_cols])
    proba["sample_id"] = df["sample_id"].values
    return proba.groupby("sample_id").mean()


def evaluate(name: str, proba: pd.DataFrame, truth: pd.Series) -> dict:
    pred = proba.idxmax(axis=1)
    y = truth.loc[pred.index]
    acc, f1 = accuracy_score(y, pred), f1_score(y, pred, average="macro")
    print(f"  {name:28s} acc={acc*100:6.2f}%  macroF1={f1:.4f}  n={len(y)}")
    return {"accuracy": float(acc), "macro_f1": float(f1), "n": int(len(y)),
            "classification_report": classification_report(
                y, pred, output_dict=True, zero_division=0)}


def batch_effect_ablation(dual: dict[str, str], shipped_test: set[str]) -> dict:
    """Why the memory stream scores so much lower here than its headline.

    Holds the evaluation set fixed (the dual-stream samples the SHIPPED
    memory model also never saw) and varies only whether the OTHER dual
    samples are in training. If they are worth a large jump, the 214 are a
    tightly-related cluster that a split grouped by sample_id does not
    separate -- which is exactly why this experiment holds out all of them.
    """
    eval_ids = set(dual) & shipped_test
    others = set(dual) - eval_ids
    out = {"eval_samples": len(eval_ids), "varied_samples": len(others), "arms": {}}
    for arm, holdout in [("neighbours_in_training", eval_ids),
                         ("neighbours_held_out", eval_ids | others)]:
        clf, test_df, cols = build_memory(holdout)
        proba = per_sample_proba(clf, test_df, cols)
        keep = sorted(set(proba.index) & eval_ids)
        pred = proba.loc[keep].idxmax(axis=1)
        y = pd.Series({s: dual[s] for s in keep})
        acc = accuracy_score(y, pred)
        f1 = f1_score(y, pred, average="macro", zero_division=0)
        print(f"  {arm:24s} acc={acc*100:6.2f}%  macroF1={f1:.4f}  n={len(keep)}")
        out["arms"][arm] = {"accuracy": float(acc), "macro_f1": float(f1), "n": len(keep)}
    a, b = out["arms"]["neighbours_in_training"], out["arms"]["neighbours_held_out"]
    out["accuracy_delta"] = round(a["accuracy"] - b["accuracy"], 4)
    return out


def main():
    dual = dual_stream_ids()
    holdout = set(dual)
    print("=" * 70)
    print(f"Dual-stream samples held out of BOTH streams: {len(holdout)}")
    print(pd.Series(list(dual.values())).value_counts().to_string())
    print("=" * 70)

    net_clf, net_test, net_cols = build_network(holdout)
    mem_clf, mem_test, mem_cols = build_memory(holdout)

    assert list(net_clf.label_encoder.classes_) == list(mem_clf.label_encoder.classes_), \
        "streams disagree on class order -- probabilities are not comparable"
    classes = list(net_clf.label_encoder.classes_)

    net_p = per_sample_proba(net_clf, net_test, net_cols)
    mem_p = per_sample_proba(mem_clf, mem_test, mem_cols)
    common = sorted(set(net_p.index) & set(mem_p.index))
    print(f"\nSamples scored by BOTH streams: {len(common)}")

    net_p, mem_p = net_p.loc[common, classes], mem_p.loc[common, classes]
    truth = pd.Series({s: dual[s] for s in common})

    print("\n" + "=" * 70)
    print("RESULTS -- same samples, same models, three decision rules")
    print("=" * 70)
    results = {
        "network_only": evaluate("network only", net_p, truth),
        "memory_only": evaluate("memory only", mem_p, truth),
        "fusion_mean": evaluate("fusion (mean)", (net_p + mem_p) / 2, truth),
        "fusion_confidence_weighted": evaluate(
            "fusion (confidence-weighted)",
            net_p.mul(net_p.max(axis=1), axis=0).add(
                mem_p.mul(mem_p.max(axis=1), axis=0)), truth),
    }
    # A stream that is simply better everywhere would make fusion pointless;
    # record how often each stream alone was right to show what fusion fixes.
    net_ok = net_p.idxmax(axis=1) == truth
    mem_ok = mem_p.idxmax(axis=1) == truth
    fus_ok = ((net_p + mem_p) / 2).idxmax(axis=1) == truth
    print(f"\n  both streams wrong        : {int((~net_ok & ~mem_ok).sum())}")
    print(f"  only network right        : {int((net_ok & ~mem_ok).sum())}")
    print(f"  only memory right         : {int((~net_ok & mem_ok).sum())}")
    print(f"  both right                : {int((net_ok & mem_ok).sum())}")
    print(f"  fusion right where exactly one stream was: "
          f"{int((fus_ok & (net_ok ^ mem_ok)).sum())} / {int((net_ok ^ mem_ok).sum())}")

    out = {
        "experiment": "dual-stream fusion",
        "holdout_samples": len(holdout),
        "scored_by_both": len(common),
        "class_order": classes,
        "note": ("Evaluation-only models: all dual-stream samples were held out of "
                 "BOTH training sets. Hyperparameters were reused from the shipped "
                 "runs rather than re-searched, so they carry a weak second-order "
                 "optimism (they were tuned on splits that included some of these "
                 "samples). Shipped models in models/*.joblib are unchanged."),
        "results": results,
        "agreement": {"both_wrong": int((~net_ok & ~mem_ok).sum()),
                      "only_network": int((net_ok & ~mem_ok).sum()),
                      "only_memory": int((~net_ok & mem_ok).sum()),
                      "both_right": int((net_ok & mem_ok).sum())},
    }
    if os.environ.get("BEACON_SKIP_ABLATION") != "1":
        print("\n" + "=" * 70)
        print("ABLATION -- is the memory stream's low score a cluster effect?")
        print("=" * 70)
        from sklearn.model_selection import StratifiedGroupKFold
        mem = load_memory()
        pre_m = Preprocessor(label_col="label")
        mem = pre_m.drop_empty_columns(pre_m.remove_duplicates(mem))
        _, t_idx = next(StratifiedGroupKFold(n_splits=5, shuffle=True,
                                             random_state=RANDOM_STATE)
                        .split(mem, mem["label"], groups=mem["sample_id"]))
        shipped_test = set(mem.iloc[t_idx]["sample_id"])
        del mem
        out["batch_effect_ablation"] = batch_effect_ablation(dual, shipped_test)

    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, "fusion_metrics.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
