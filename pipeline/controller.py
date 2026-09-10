"""DashboardController — the Presentation-layer object that orchestrates
a single upload -> preprocess -> classify -> explain request, shared by
every Streamlit page so each page stays thin UI code.
"""
from __future__ import annotations

import os

import pandas as pd

from pipeline.artifacts import ArtifactStore
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
        self.explainer = Explainer(self.classifier)

    def handle_upload(self, file) -> pd.DataFrame:
        """Read an uploaded CSV and validate it carries every column the
        model was trained on. Raises ValueError with a readable message
        on a schema mismatch, per FR-2 (reject before predicting)."""
        df = pd.read_csv(file)
        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Uploaded file is missing {len(missing)} required column(s) for the "
                f"{self.stream} model, e.g.: {missing[:8]}"
            )

        # Column presence alone isn't enough: a NaN or non-numeric value
        # in a required feature reaches the model silently otherwise,
        # since none of these columns were flagged as expecting missing
        # values at training time.
        coerced = df[self.feature_cols].apply(pd.to_numeric, errors="coerce")
        bad_cols = [c for c in self.feature_cols if coerced[c].isnull().any()]
        if bad_cols:
            raise ValueError(
                f"Uploaded file has missing or non-numeric value(s) in {len(bad_cols)} "
                f"required column(s) for the {self.stream} model, e.g.: {bad_cols[:8]}"
            )
        return df

    def run_pipeline(self, df: pd.DataFrame) -> dict:
        """Preprocess, classify, and explain every row of df. Returns a
        dict with predictions, per-class probabilities, and (for the
        first row only, to keep this cheap) a SHAP top-features table."""
        transformed = self.preprocessor.transform(df)
        X = transformed[self.feature_cols]

        predictions = self.classifier.predict(X)
        probabilities = self.classifier.predict_proba(X)

        first_row = X.iloc[[0]]
        pred_label = predictions[0]
        pred_idx = list(self.classifier.label_encoder.classes_).index(pred_label)
        top_features = self.explainer.top_features(first_row, pred_idx, n=8)

        return {
            "predictions": predictions,
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
