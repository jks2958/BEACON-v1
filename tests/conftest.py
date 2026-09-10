"""Shared fixtures.

The trained artifacts ARE committed, so the model-backed tests run on a
fresh clone with no dataset present. The raw CSVs are not committed, so
nothing here may read from data/raw/ -- inputs are synthesised from each
model's own recorded feature list instead.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

MODEL_DIR = os.path.join(REPO_ROOT, "models")


def _trained(stream: str) -> bool:
    return all(os.path.exists(os.path.join(MODEL_DIR, f"{stream}_{part}"))
               for part in ("classifier.joblib", "preprocessing_artifacts.joblib"))


requires_network = pytest.mark.skipif(
    not _trained("network"), reason="network model artifacts not present")
requires_memory = pytest.mark.skipif(
    not _trained("memory"), reason="memory model artifacts not present")


@pytest.fixture(scope="session")
def network_controller():
    """Session-scoped: loading a 29MB booster and building its SHAP
    explainer costs seconds, and every test here treats it as read-only."""
    from pipeline.controller import DashboardController
    return DashboardController("network")


@pytest.fixture(scope="session")
def memory_controller():
    from pipeline.controller import DashboardController
    return DashboardController("memory")


def synth_upload(controller, n_rows: int = 5, seed: int = 0) -> pd.DataFrame:
    """Build an upload-shaped frame carrying every RAW column the model
    needs. Values are arbitrary -- these tests assert on plumbing
    (validation, aggregation, alignment), never on what verdict comes out
    of made-up numbers.
    """
    rng = np.random.default_rng(seed)
    cols = [c for c in controller.feature_cols
            if not c.endswith("_incomplete") and not c.startswith("has_")]
    df = pd.DataFrame(rng.random((n_rows, len(cols))), columns=cols)
    # Derived columns are produced from raw ones, so hand back the raw
    # form the derivation expects rather than the encoded output.
    for base in ("delta_start", "handshake_duration"):
        if f"{base}_incomplete" in controller.feature_cols:
            df[base] = 0.05
    return df


def to_csv_upload(df: pd.DataFrame, name: str = "capture.csv"):
    """Mimic a Streamlit UploadedFile closely enough for handle_upload."""
    import io
    buf = io.BytesIO(df.to_csv(index=False).encode())
    buf.name = name
    return buf
