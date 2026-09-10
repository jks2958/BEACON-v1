"""Persists trained classifiers bundled with the exact preprocessing
state that produced them, so inference can never silently drift from
how a model was actually trained.
"""
from __future__ import annotations

import os

import joblib


class ArtifactStore:
    @staticmethod
    def save_model(model, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(model, path)

    @staticmethod
    def load_model(path: str):
        return joblib.load(path)

    @staticmethod
    def save_artifacts(artifacts: dict, path: str) -> None:
        """Persist a preprocessing artifact bundle: the fitted
        Preprocessor (Min-Max ranges, correlation drop-list, label
        fixes, missingness state) plus anything else inference needs
        that isn't part of the classifier itself."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(artifacts, path)

    @staticmethod
    def load_artifacts(path: str) -> dict:
        return joblib.load(path)
