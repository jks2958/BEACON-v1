"""The shipped Network model's explicit feature contract and validator."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import os

import numpy as np
import pandas as pd


CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "network_feature_contract.json")


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    PARTIALLY_COMPATIBLE = "partially_compatible"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class FeatureCompatibility:
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


class NetworkFeatureContract:
    def __init__(self, entries: list[dict]):
        self.entries = tuple(entries)
        self.feature_names = tuple(entry["name"] for entry in entries)

    @classmethod
    def load(cls, path: str = CONTRACT_PATH) -> "NetworkFeatureContract":
        with open(path) as handle:
            payload = json.load(handle)
        return cls(payload["features"])

    def validate(self, frame: pd.DataFrame) -> FeatureCompatibility:
        required = list(self.feature_names)
        missing = tuple(column for column in required if column not in frame.columns)
        extra = tuple(column for column in frame.columns if column not in self.feature_names)
        present = [column for column in required if column in frame.columns]
        non_numeric = tuple(column for column in present
                            if not pd.api.types.is_numeric_dtype(frame[column]))
        non_finite = tuple(column for column in present
                           if pd.api.types.is_numeric_dtype(frame[column])
                           and not np.isfinite(frame[column].to_numpy(dtype=float)).all())
        exact_order = list(frame.columns) == required
        structurally_complete = not (missing or extra or non_numeric or non_finite) and exact_order
        # No paired raw capture/prepared CSV exists in this repository, so the
        # generated contract deliberately records every extraction semantic as
        # empirically unverified. Structural completeness alone is not enough.
        empirically_reproduced = all(
            entry.get("reproduction_status") == "exact" for entry in self.entries
        )
        if structurally_complete and empirically_reproduced:
            status = CompatibilityStatus.COMPATIBLE
        elif present:
            status = CompatibilityStatus.PARTIALLY_COMPATIBLE
        else:
            status = CompatibilityStatus.INCOMPATIBLE
        return FeatureCompatibility(
            status=status,
            required_count=len(required), present_count=len(present),
            missing_features=missing, extra_features=extra,
            non_numeric_features=non_numeric, non_finite_features=non_finite,
            exact_order=exact_order, empirically_reproduced=empirically_reproduced,
        )


NETWORK_FEATURE_CONTRACT = NetworkFeatureContract.load()
