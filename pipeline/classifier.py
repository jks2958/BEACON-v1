"""XGBoost-based classifiers for BEACON's two behavioral streams.

NetworkClassifier and MemoryClassifier are structurally identical — same
training interface, same underlying algorithm — and differ only in which
data and resampling strategy trained them, not in how they're used. That
distinction lives in the training scripts (scripts/train_memory.py,
scripts/train_network.py), not in these classes.
"""
from __future__ import annotations

from abc import ABC

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder


class MalwareClassifier(ABC):
    stream_name: str = "base"

    def __init__(self):
        self.model: xgb.XGBClassifier | None = None
        self.label_encoder: LabelEncoder = LabelEncoder()
        self.feature_order: list[str] = []

    def train(self, X: pd.DataFrame, y, sample_weight=None, **xgb_params) -> None:
        self.feature_order = list(X.columns)
        y_encoded = self.label_encoder.fit_transform(y)
        params = {
            "objective": "multi:softprob",
            "num_class": len(self.label_encoder.classes_),
            "eval_metric": "mlogloss",
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": -1,
        }
        params.update(xgb_params)
        self.model = xgb.XGBClassifier(**params)
        self.model.fit(X[self.feature_order], y_encoded, sample_weight=sample_weight)

    def _align(self, X: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in self.feature_order if c not in X.columns]
        if missing:
            raise ValueError(
                f"{self.stream_name} classifier: input is missing required feature(s): {missing}"
            )
        return X[self.feature_order]

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self.model.predict(self._align(X))
        return self.label_encoder.inverse_transform(preds)

    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        proba = self.model.predict_proba(self._align(X))
        return pd.DataFrame(proba, columns=self.label_encoder.classes_, index=X.index)


class NetworkClassifier(MalwareClassifier):
    stream_name = "network"


class MemoryClassifier(MalwareClassifier):
    stream_name = "memory"
