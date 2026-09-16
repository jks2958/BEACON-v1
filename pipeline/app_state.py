"""Small, framework-agnostic state helpers for BEACON's two UI modes."""
from __future__ import annotations

from collections.abc import MutableMapping

from pipeline.application import AnalysisOutput


GENERAL_MODE = "General"
ANALYST_MODE = "Analyst"
USER_MODES = (GENERAL_MODE, ANALYST_MODE)
MODE_KEY = "beacon_mode"
RESULTS_KEY = "beacon_analysis_results"
ACTIVE_STREAM_KEY = "beacon_active_stream"


def current_mode(state: MutableMapping) -> str:
    mode = state.get(MODE_KEY, GENERAL_MODE)
    return mode if mode in USER_MODES else GENERAL_MODE


def set_mode(state: MutableMapping, mode: str) -> None:
    if mode not in USER_MODES:
        raise ValueError(f"Unsupported BEACON mode: {mode}")
    state[MODE_KEY] = mode


def save_analysis(state: MutableMapping, output: AnalysisOutput) -> None:
    """Keep result data—not controllers or models—available across pages."""
    results = state.setdefault(RESULTS_KEY, {})
    results[output.stream] = output
    state[ACTIVE_STREAM_KEY] = output.stream


def latest_analysis(state: MutableMapping, stream: str | None = None) -> AnalysisOutput | None:
    selected = stream or state.get(ACTIVE_STREAM_KEY)
    return state.get(RESULTS_KEY, {}).get(selected)
