"""Exact Memory model feature contract and fail-closed compatibility checks."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os

import numpy as np
import pandas as pd

from pipeline.network_contract import CompatibilityStatus

CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "memory_feature_contract.json")


@dataclass(frozen=True)
class MemoryCompatibility:
    status: CompatibilityStatus
    required_count: int
    present_count: int
    missing_features: tuple[str, ...]
    extra_features: tuple[str, ...]
    non_numeric_features: tuple[str, ...]
    non_finite_features: tuple[str, ...]
    exact_order: bool
    empirically_reproduced: bool

    @property
    def safe_for_inference(self) -> bool:
        return self.status is CompatibilityStatus.COMPATIBLE and self.empirically_reproduced


class MemoryFeatureContract:
    def __init__(self, entries: list[dict]):
        self.entries = tuple(entries)
        self.feature_names = tuple(entry["name"] for entry in entries)

    @classmethod
    def load(cls, path: str = CONTRACT_PATH) -> "MemoryFeatureContract":
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls(payload["features"])

    def validate(self, frame: pd.DataFrame) -> MemoryCompatibility:
        required = list(self.feature_names)
        missing = tuple(name for name in required if name not in frame.columns)
        extra = tuple(name for name in frame.columns if name not in self.feature_names)
        present = [name for name in required if name in frame.columns]
        non_numeric = tuple(name for name in present
                            if not pd.api.types.is_numeric_dtype(frame[name]))
        non_finite = tuple(name for name in present
                           if pd.api.types.is_numeric_dtype(frame[name])
                           and not np.isfinite(frame[name].to_numpy(dtype=float)).all())
        exact_order = list(frame.columns) == required
        reproduced = all(item.get("reproduction_status") == "exact" for item in self.entries)
        structurally_complete = not (missing or extra or non_numeric or non_finite) and exact_order
        if structurally_complete and reproduced:
            status = CompatibilityStatus.COMPATIBLE
        elif present:
            status = CompatibilityStatus.PARTIALLY_COMPATIBLE
        else:
            status = CompatibilityStatus.INCOMPATIBLE
        return MemoryCompatibility(
            status, len(required), len(present), missing, extra, non_numeric,
            non_finite, exact_order, reproduced,
        )


MEMORY_FEATURE_CONTRACT = MemoryFeatureContract.load()
