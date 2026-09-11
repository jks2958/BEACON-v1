"""End-to-end test of scripts/train_malmem_specialist.py against a
FABRICATED CSV shaped like CIC-MalMem-2022's publicly documented schema
(Category/Class columns, VolMemLyzer-style feature names) -- not the real
dataset, which this repo does not ship and this sandbox cannot download
(kaggle.com, unb.ca, and ieee-dataport.org are all blocked by the egress
proxy here).

This exists because the script was written without ever seeing the real
file. Faking a plausible file and running the whole script against it as
a subprocess is what actually proves detect_schema(), derive_family_group(),
the binary/multiclass objective switch, and the artifact-saving path work
mechanically -- rather than just "the code parses."

If the real dataset's columns differ from what's faked here, this test
still passes (it only proves the MECHANICS), but scripts/train_malmem_
specialist.py's own detect_schema() will say so loudly on the real run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def fake_malmem_csv(tmp_path):
    """A small CSV in the documented CIC-MalMem-2022 shape: a Category
    column with 'Family-Variant' style malware labels and plain 'Benign',
    a binary Class column, an identifier column, and numeric
    VolMemLyzer-style feature columns -- plus a few missing values and one
    duplicate row, since real capture data always has both."""
    rng = np.random.default_rng(0)
    families = {
        "Benign": 60, "Ransomware-Ako": 15, "Ransomware-Maze": 15,
        "Spyware-Gator": 15, "Trojan-Zeus": 15, "Trojan-Emotet": 15,
    }
    feat_names = ["pslist.nproc", "pslist.nppid", "dlllist.ndlls",
                  "handles.nhandles", "handles.avg_handlers_per_proc",
                  "ldrmodules.not_in_load", "malfind.ninjections",
                  "svcscan.nservices", "callbacks.ncallbacks"]
    rows = []
    for fam, n in families.items():
        is_benign = fam == "Benign"
        base = rng.normal(5 if is_benign else 9, 1.5, size=(n, len(feat_names)))
        d = pd.DataFrame(np.clip(base, 0, None), columns=feat_names)
        d["Category"] = fam
        d["Class"] = "Benign" if is_benign else "Malware"
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    df.insert(0, "Unnamed: 0", range(len(df)))
    df.loc[rng.choice(len(df), 4, replace=False), "handles.nhandles"] = np.nan
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # one duplicate row

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    path = raw_dir / "synthetic_CIC-MalMem-2022.csv"
    df.to_csv(path, index=False)
    return path, df


def test_script_runs_end_to_end_on_documented_schema(fake_malmem_csv, tmp_path):
    path, df = fake_malmem_csv
    model_dir = tmp_path / "models"

    env = {**os.environ,
           "BEACON_MALMEM_RAW_GLOB": str(path.parent / "*.csv"),
           "BEACON_MODEL_DIR": str(model_dir),
           "BEACON_OPTUNA_TRIALS": "2"}
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "train_malmem_specialist.py")],
        env=env, capture_output=True, text=True, timeout=180)

    assert result.returncode == 0, (
        f"script exited {result.returncode}\n--- stdout ---\n{result.stdout[-3000:]}"
        f"\n--- stderr ---\n{result.stderr[-3000:]}")

    # Schema detection found the right columns and said so.
    assert "Family label column: 'Category'" in result.stdout
    assert "Binary class column: 'Class'" in result.stdout
    assert "After dedup: (135" in result.stdout  # 136 rows in -> 1 exact duplicate removed

    metrics_path = model_dir / "malmem_specialist_metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text())

    # Fine-grained "Family-Variant" values collapsed to the four
    # supercategories, not left as 5 distinct raw family strings.
    assert sorted(metrics["categories"]) == ["Benign", "Ransomware", "Spyware", "Trojan"]
    assert metrics["family_label_column_used"] == "Category"
    assert metrics["class_label_column_used"] == "Class"
    assert 0.0 <= metrics["test_accuracy"] <= 1.0
    assert 0.0 <= metrics["test_macro_f1"] <= 1.0
    assert metrics["test_rows"] + metrics["train_rows"] == 135

    # The binary diagnostic against the dataset's own Class column ran too.
    assert metrics["binary_diagnostic_vs_dataset_class_column"] is not None

    assert (model_dir / "malmem_specialist_classifier.joblib").exists()
    assert (model_dir / "malmem_specialist_preprocessing_artifacts.joblib").exists()

    # This model must never silently touch the shipped memory artifacts.
    assert not (model_dir / "memory_classifier.joblib").exists()
    assert not (model_dir / "memory_metrics.json").exists()


def test_missing_label_column_fails_loudly_not_silently(tmp_path):
    """If the real file's columns don't match what's expected, the script
    must say so and stop -- not guess and train on garbage."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.DataFrame({"totally_unexpected_col": [1, 2, 3], "x": [0.1, 0.2, 0.3]}).to_csv(
        raw_dir / "weird.csv", index=False)

    env = {**os.environ,
           "BEACON_MALMEM_RAW_GLOB": str(raw_dir / "*.csv"),
           "BEACON_MODEL_DIR": str(tmp_path / "models"),
           "BEACON_OPTUNA_TRIALS": "2"}
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "train_malmem_specialist.py")],
        env=env, capture_output=True, text=True, timeout=60)

    assert result.returncode != 0
    assert "None of the expected label columns" in result.stderr


def test_derive_family_group_collapses_variant_suffixes():
    from scripts.train_malmem_specialist import derive_family_group
    s = pd.Series(["Benign", "Ransomware-Ako", "Ransomware-Maze", "Trojan-Zeus"])
    out = derive_family_group(s)
    assert list(out) == ["Benign", "Ransomware", "Ransomware", "Trojan"]


def test_derive_family_group_is_a_noop_without_hyphens():
    from scripts.train_malmem_specialist import derive_family_group
    s = pd.Series(["Benign", "Ransomware", "Trojan"])
    assert list(derive_family_group(s)) == ["Benign", "Ransomware", "Trojan"]


def test_malmem_specialist_classifier_is_registered_separately():
    # Guards against ever merging this stream into MemoryClassifier by
    # accident -- it must remain its own class with its own stream_name.
    from pipeline.classifier import MalMemSpecialistClassifier, MemoryClassifier
    assert MalMemSpecialistClassifier.stream_name == "malmem_specialist"
    assert MalMemSpecialistClassifier.stream_name != MemoryClassifier.stream_name
    assert issubclass(MalMemSpecialistClassifier, MemoryClassifier.__bases__[0])
