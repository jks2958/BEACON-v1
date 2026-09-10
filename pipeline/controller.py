"""DashboardController — the Presentation-layer object that orchestrates
a single upload -> preprocess -> classify -> explain request, shared by
every Streamlit page so each page stays thin UI code.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from pipeline.artifacts import ArtifactStore
from pipeline.common import DERIVATIONS
from pipeline.explain import Explainer

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


class StreamUnavailable(Exception):
    """Raised when a stream's model artifacts haven't been trained/saved
    yet — the caller (a Streamlit page) is expected to show this as a
    clear status message, not a stack trace."""


class DashboardController:
    def __init__(self, stream: str):
        """stream: 'network' or 'memory'."""
        self.stream = stream
        model_path = os.path.join(MODEL_DIR, f"{stream}_classifier.joblib")
        artifacts_path = os.path.join(MODEL_DIR, f"{stream}_preprocessing_artifacts.joblib")

        if not (os.path.exists(model_path) and os.path.exists(artifacts_path)):
            raise StreamUnavailable(
                f"No trained {stream} model found at {model_path}. "
                f"Run scripts/train_{stream}.py first."
            )

        self.classifier = ArtifactStore.load_model(model_path)
        bundle = ArtifactStore.load_artifacts(artifacts_path)
        self.preprocessor = bundle["preprocessor"]
        self.feature_cols = bundle["feature_cols"]
        # Derived-feature steps run before the Preprocessor and create
        # columns it was fitted on. Training records them by name, so a
        # model can never be fed data that skipped a step it needs.
        self.derivations = [DERIVATIONS[name] for name in bundle.get("derivations", [])]
        self.explainer = Explainer(self.classifier)

    def handle_upload(self, file) -> pd.DataFrame:
        """Read an uploaded CSV and validate it carries every column the
        model was trained on. Raises ValueError with a readable message
        on a schema mismatch, per FR-2 (reject before predicting)."""
        df = pd.read_csv(file)
        # Apply the same derivations training did, before validating: a raw
        # capture carries `delta_start` as the string "not a complete
        # handshake", and the derived `*_incomplete` indicators the model
        # needs simply don't exist in the file yet.
        for derive in self.derivations:
            df = derive(df)
        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Uploaded file is missing {len(missing)} required column(s) for the "
                f"{self.stream} model, e.g.: {missing[:8]}"
            )

        # Column presence alone isn't enough: a non-numeric value in a
        # required feature would otherwise reach the model as an object
        # column. Coerce first so a garbage value becomes NaN and is
        # treated exactly like a missing one.
        df[self.feature_cols] = df[self.feature_cols].apply(pd.to_numeric, errors="coerce")

        # Only NaNs the preprocessor was NOT fitted to fill are fatal.
        # Statistical features like `payload_bytes_skewness` are genuinely
        # undefined for a single-packet flow, and Step 4 learned a fill for
        # them at training time -- rejecting those would reject almost every
        # real capture.
        handled = self.preprocessor.missingness_handled_cols
        bad_cols = [c for c in self.feature_cols
                    if c not in handled and df[c].isnull().any()]
        if bad_cols:
            raise ValueError(
                f"Uploaded file has missing or non-numeric value(s) in {len(bad_cols)} "
                f"required column(s) the {self.stream} model has no fill rule for, "
                f"e.g.: {bad_cols[:8]}"
            )
        return df

    def run_pipeline(self, df: pd.DataFrame) -> dict:
        """Preprocess, classify, and explain an uploaded capture.

        An uploaded file may hold many rows (a network capture is hundreds
        of flows from ONE sample). The verdict is therefore the mean of the
        per-row class probabilities, not row 0's prediction -- that is both
        the operationally correct unit and far more accurate, since
        individual row errors cancel out. Measured on the Network stream:
        69.7% per flow vs 99.1% per capture.
        """
        transformed = self.preprocessor.transform(df)
        X = transformed[self.feature_cols]

        row_predictions = self.classifier.predict(X)
        probabilities = self.classifier.predict_proba(X)

        aggregate_proba = probabilities.mean(axis=0)
        verdict = aggregate_proba.idxmax()
        confidence = float(aggregate_proba.max())

        # Explain a row the model actually assigned to the verdict class,
        # so the explanation corresponds to the reported answer rather than
        # to whichever row happened to be first.
        verdict_idx = list(self.classifier.label_encoder.classes_).index(verdict)
        matching = np.flatnonzero(row_predictions == verdict)
        explain_pos = int(matching[0]) if len(matching) else 0
        top_features = self.explainer.top_features(X.iloc[[explain_pos]], verdict_idx, n=8)

        return {
            "verdict": verdict,
            "confidence": confidence,
            "aggregate_probabilities": aggregate_proba,
            "n_rows": int(len(X)),
            "row_predictions": row_predictions,
            "probabilities": probabilities,
            "top_features": top_features,
        }


RISK_BY_CATEGORY = {
    "Benign": "Low",
    "Hoax": "Low",
    "HackTool": "Medium",
    "Backdoor": "High",
    "Exploit": "High",
    "Rootkit": "Critical",
    "Trojan": "High",
    "Virus": "High",
    "Worm": "High",
}


def risk_level(predicted_label: str, confidence: float) -> str:
    """FR-6: qualitative risk level from predicted category + confidence.
    A low-confidence prediction is downgraded one notch since a shaky
    call on a dangerous-sounding label shouldn't read as equally urgent
    as a confident one."""
    base = RISK_BY_CATEGORY.get(predicted_label, "Medium")
    if confidence < 0.5:
        downgrade = {"Critical": "High", "High": "Medium", "Medium": "Low", "Low": "Low"}
        return downgrade[base]
    return base
