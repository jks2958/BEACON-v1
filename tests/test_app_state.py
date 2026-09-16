import pytest

from pipeline.app_state import (ACTIVE_STREAM_KEY, ANALYST_MODE, GENERAL_MODE, MODE_KEY,
                                RESULTS_KEY, current_mode, latest_analysis, save_analysis,
                                set_mode)
from pipeline.application import AnalysisOutput


def _output(stream="network"):
    return AnalysisOutput(stream=stream, validated_frame="validated", result={"verdict": "Benign"})


def test_general_mode_is_the_default_and_invalid_stored_values_recover():
    assert current_mode({}) == GENERAL_MODE
    assert current_mode({MODE_KEY: "unknown"}) == GENERAL_MODE


def test_mode_switch_preserves_analysis_state():
    state = {}
    saved = _output()
    save_analysis(state, saved)
    set_mode(state, ANALYST_MODE)
    assert current_mode(state) == ANALYST_MODE
    assert latest_analysis(state) is saved
    set_mode(state, GENERAL_MODE)
    assert latest_analysis(state) is saved


def test_invalid_mode_is_rejected_without_mutating_state():
    state = {MODE_KEY: GENERAL_MODE}
    with pytest.raises(ValueError, match="Unsupported BEACON mode"):
        set_mode(state, "expert")
    assert state[MODE_KEY] == GENERAL_MODE


def test_results_are_retained_per_stream_and_active_stream_tracks_latest():
    state = {}
    network, memory = _output("network"), _output("memory")
    save_analysis(state, network)
    save_analysis(state, memory)
    assert latest_analysis(state, "network") is network
    assert latest_analysis(state, "memory") is memory
    assert latest_analysis(state) is memory
    assert state[ACTIVE_STREAM_KEY] == "memory"


def test_state_contains_outputs_but_never_controller_or_model_keys():
    state = {}
    save_analysis(state, _output())
    assert set(state) == {RESULTS_KEY, ACTIVE_STREAM_KEY}
    assert "controller" not in repr(state).lower()
    assert "classifier" not in repr(state).lower()
