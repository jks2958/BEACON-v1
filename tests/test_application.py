"""Parity checks for the application wrapper around validated inference."""
import io

import numpy as np
import pandas as pd
import pytest

from conftest import requires_memory, requires_network, synth_upload, to_csv_upload
from pipeline.application import analyze_csv, get_controller, validate_stream
from pipeline.controller import DashboardController


def _bytes_upload(frame: pd.DataFrame):
    payload = frame.to_csv(index=False).encode()
    direct, wrapped = io.BytesIO(payload), io.BytesIO(payload)
    direct.name = wrapped.name = "parity.csv"
    return direct, wrapped


def _full_shap(controller, validated):
    transformed = controller.preprocessor.transform(validated)
    X = transformed[controller.feature_cols]
    return np.asarray(controller.explainer.explain(X.iloc[[0]]))


@pytest.mark.parametrize("invalid", ["", "disk", "malmem_specialist"])
def test_only_product_streams_are_accepted(invalid):
    with pytest.raises(ValueError, match="Unsupported analysis stream"):
        validate_stream(invalid)


@pytest.mark.parametrize("stream", ["network", "memory"])
def test_controller_cache_returns_one_instance_per_stream(stream):
    assert get_controller(stream) is get_controller(stream)


def test_stream_controllers_remain_distinct():
    assert get_controller("network") is not get_controller("memory")


@pytest.mark.parametrize("stream", ["network", "memory"])
def test_wrapper_matches_direct_pipeline_in_every_returned_value(stream):
    cached = get_controller(stream)
    direct_controller = DashboardController(stream)
    source = synth_upload(cached, n_rows=3, seed=81)
    direct_file, wrapped_file = _bytes_upload(source)

    direct_frame = direct_controller.handle_upload(direct_file)
    direct = direct_controller.run_pipeline(direct_frame)
    wrapped = analyze_csv(stream, wrapped_file)

    assert wrapped.stream == stream == cached.stream == direct_controller.stream
    assert list(cached.classifier.label_encoder.classes_) == \
        list(direct_controller.classifier.label_encoder.classes_)
    pd.testing.assert_frame_equal(wrapped.validated_frame, direct_frame)
    assert wrapped.result["verdict"] == direct["verdict"]
    assert wrapped.result["n_rows"] == direct["n_rows"]
    np.testing.assert_allclose(wrapped.result["confidence"], direct["confidence"], rtol=0, atol=0)
    np.testing.assert_array_equal(wrapped.result["row_predictions"], direct["row_predictions"])
    pd.testing.assert_series_equal(
        wrapped.result["aggregate_probabilities"], direct["aggregate_probabilities"],
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        wrapped.result["probabilities"], direct["probabilities"], check_exact=True,
    )
    pd.testing.assert_frame_equal(
        wrapped.result["top_features"].reset_index(drop=True),
        direct["top_features"].reset_index(drop=True), check_exact=True,
    )
    np.testing.assert_allclose(
        _full_shap(cached, wrapped.validated_frame),
        _full_shap(direct_controller, direct_frame), rtol=0, atol=0,
    )


@requires_network
def test_wrapper_preserves_missing_column_error_exactly(network_controller):
    malformed = synth_upload(network_controller).drop(columns=network_controller.feature_cols[:2])
    direct_file, wrapped_file = _bytes_upload(malformed)
    with pytest.raises(ValueError) as direct_error:
        network_controller.handle_upload(direct_file)
    with pytest.raises(ValueError) as wrapped_error:
        analyze_csv("network", wrapped_file)
    assert str(wrapped_error.value) == str(direct_error.value)


@requires_memory
def test_wrapper_preserves_non_numeric_error_exactly(memory_controller):
    malformed = synth_upload(memory_controller)
    malformed[memory_controller.feature_cols[0]] = "not numeric"
    direct_file, wrapped_file = _bytes_upload(malformed)
    with pytest.raises(ValueError) as direct_error:
        memory_controller.handle_upload(direct_file)
    with pytest.raises(ValueError) as wrapped_error:
        analyze_csv("memory", wrapped_file)
    assert str(wrapped_error.value) == str(direct_error.value)
