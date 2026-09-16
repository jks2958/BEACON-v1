"""Safe adapter for already-structured Volatility-derived JSON evidence.

This module never executes Volatility or uploaded content. It only reads a
small, explicit JSON envelope and reports compatibility with the shipped
94-feature Memory contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
from types import MappingProxyType
from typing import Mapping

import pandas as pd

from pipeline.memory_feature_contract import MEMORY_FEATURE_CONTRACT, MemoryCompatibility

MAX_STRUCTURED_EVIDENCE_BYTES = 10 * 1024 * 1024


class VolatilityEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class AdaptedMemoryEvidence:
    dataframe: pd.DataFrame
    metadata: Mapping[str, object]
    compatibility: MemoryCompatibility


def adapt_volatility_json(content: bytes) -> AdaptedMemoryEvidence:
    if not content or not content.strip():
        raise VolatilityEvidenceError("The structured Volatility evidence is empty.")
    if len(content) > MAX_STRUCTURED_EVIDENCE_BYTES:
        raise VolatilityEvidenceError("Structured Volatility evidence exceeds the 10 MiB limit.")
    try:
        payload = json.load(BytesIO(content))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VolatilityEvidenceError(f"Structured Volatility JSON could not be read: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise VolatilityEvidenceError("Expected a JSON object containing a 'records' list.")
    if not payload["records"]:
        raise VolatilityEvidenceError("Structured Volatility evidence contains no records.")
    if not all(isinstance(record, dict) for record in payload["records"]):
        raise VolatilityEvidenceError("Every Volatility record must be a JSON object.")

    # DataFrame construction preserves supplied field names and record order;
    # it performs no filling, mapping, derivation, or scientific preprocessing.
    frame = pd.DataFrame(payload["records"])
    compatibility = MEMORY_FEATURE_CONTRACT.validate(frame)
    supplied_metadata = payload.get("metadata", {})
    if not isinstance(supplied_metadata, dict):
        raise VolatilityEvidenceError("Volatility metadata must be a JSON object when supplied.")
    plugins = supplied_metadata.get("plugins", [])
    if not isinstance(plugins, list) or not all(isinstance(item, str) for item in plugins):
        raise VolatilityEvidenceError("Volatility metadata 'plugins' must be a list of names.")
    metadata = MappingProxyType({
        "source_format": "structured_volatility_json",
        "declared_tool": supplied_metadata.get("tool"),
        "declared_plugins": tuple(plugins),
        "record_count": len(frame),
        "expected_features": compatibility.required_count,
        "reproduced_features": compatibility.present_count,
        "missing_features": compatibility.missing_features,
        "extra_fields": compatibility.extra_features,
        "incompatible_fields": compatibility.non_numeric_features + compatibility.non_finite_features,
        "empirically_reproduced": compatibility.empirically_reproduced,
    })
    return AdaptedMemoryEvidence(frame, metadata, compatibility)
