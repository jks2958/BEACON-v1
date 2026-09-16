"""Application service shared by BEACON's General and Analyst views.

This module is intentionally a thin wrapper. It owns Streamlit resource
caching and delegates CSV validation, preprocessing, prediction, probability
aggregation, and SHAP to the existing DashboardController without changing
their semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd
import streamlit as st

from pipeline.controller import DashboardController
from pipeline.ingestion import (DEFAULT_INGESTION_SERVICE, EvidenceUpload,
                                EvidenceType, IncompatibleEvidenceError, ParsedEvidence)


SUPPORTED_STREAMS = ("network", "memory")


@dataclass(frozen=True)
class AnalysisOutput:
    """The existing pipeline output plus its validated, pre-transform frame."""

    stream: str
    validated_frame: pd.DataFrame
    result: dict
    evidence: ParsedEvidence | None = None


def validate_stream(stream: str) -> str:
    if stream not in SUPPORTED_STREAMS:
        raise ValueError(f"Unsupported analysis stream: {stream}")
    return stream


@st.cache_resource(show_spinner=False)
def get_controller(stream: str) -> DashboardController:
    """Return one process-cached controller for a supported evidence stream."""
    return DashboardController(validate_stream(stream))


def analyze_evidence(evidence: ParsedEvidence) -> AnalysisOutput:
    """Analyze normalized evidence through the unchanged controller path."""
    if not evidence.compatibility_status.value == "compatible":
        contract = evidence.metadata.get("feature_contract")
        missing = len(contract.missing_features) if contract else "unknown"
        source = ("Memory" if evidence.stream == "memory" else "Network")
        raise IncompatibleEvidenceError(
            f"{source} diagnostic inference is disabled: exact reproduction of the "
            f"{source} feature contract is unproven ({missing} required features missing)."
        )
    controller = get_controller(validate_stream(evidence.stream))
    # CSV evidence retains the byte-for-byte validated path. A future
    # empirically proven structured adapter hands its normalized contract frame
    # to that same controller as CSV rather than asking the controller to know
    # about JSON. The shipped structured contract is currently fail-closed
    # above, so this branch cannot run until reproduction is proven.
    controller_bytes = (evidence.dataframe.to_csv(index=False).encode("utf-8")
                        if evidence.evidence_type is EvidenceType.MEMORY_VOLATILITY
                        else evidence.source_bytes)
    controller_input = BytesIO(controller_bytes)
    controller_input.name = evidence.original_filename
    frame = controller.handle_upload(controller_input)
    result = controller.run_pipeline(frame)
    return AnalysisOutput(
        stream=evidence.stream, validated_frame=frame, result=result, evidence=evidence,
    )


def ingest_and_analyze(upload: EvidenceUpload) -> AnalysisOutput:
    """Normalize an upload, then route it to the existing inference service."""
    return analyze_evidence(DEFAULT_INGESTION_SERVICE.ingest(upload))


def analyze_upload(stream: str, uploaded_file: BinaryIO) -> AnalysisOutput:
    """Framework boundary used by every BEACON upload page."""
    return ingest_and_analyze(EvidenceUpload.from_file(uploaded_file, validate_stream(stream)))


def analyze_csv(stream: str, uploaded_file: BinaryIO) -> AnalysisOutput:
    """Backward-compatible name for callers predating unified ingestion."""
    return analyze_upload(stream, uploaded_file)
