"""DashboardController: upload validation, aggregation, and risk levels.

The upload tests run against the REAL committed network model, because
both bugs they cover were invisible to a synthetic stand-in: they came
from the gap between what training produced and what inference expected.
"""
import numpy as np
import pandas as pd
import pytest

from conftest import requires_memory, requires_network, synth_upload, to_csv_upload
from pipeline.controller import (DashboardController, StreamUnavailable,
                                 RISK_BY_CATEGORY, risk_level)


def test_unknown_stream_raises_stream_unavailable():
    with pytest.raises(StreamUnavailable):
        DashboardController("no_such_stream")


# --------------------------------------------------------------------
# FR-2: validate an upload against the schema, reject before predicting
# --------------------------------------------------------------------

@requires_network
def test_valid_upload_is_accepted(network_controller):
    df = synth_upload(network_controller)
    out = network_controller.handle_upload(to_csv_upload(df))
    assert len(out) == len(df)
    for col in network_controller.feature_cols:
        assert col in out.columns


@requires_network
def test_missing_columns_are_rejected_with_a_readable_message(network_controller):
    df = synth_upload(network_controller)
    dropped = [c for c in network_controller.feature_cols
               if not c.endswith("_incomplete")][:3]
    with pytest.raises(ValueError, match="missing 3 required column"):
        network_controller.handle_upload(to_csv_upload(df.drop(columns=dropped)))


@requires_network
def test_derivations_run_before_validation(network_controller):
    # Regression: the *_incomplete columns exist only AFTER
    # encode_handshake, and no raw capture carries them. Validating first
    # rejected every real file.
    assert [f.__name__ for f in network_controller.derivations] == ["encode_handshake"]
    df = synth_upload(network_controller)
    df["delta_start"] = "not a complete handshake"

    out = network_controller.handle_upload(to_csv_upload(df))
    assert (out["delta_start_incomplete"] == 1).all()
    assert (out["delta_start"] == -1.0).all()


@requires_network
def test_nan_is_allowed_where_a_fill_rule_was_fitted(network_controller):
    # Regression: statistics like payload_bytes_skewness are undefined for
    # a single-packet flow. Step 4 learned fills for 40+ such columns, so
    # rejecting them rejected almost every real capture.
    handled = network_controller.preprocessor.missingness_handled_cols
    fillable = [c for c in network_controller.feature_cols if c in handled]
    assert fillable, "expected the network model to carry fitted fill rules"

    df = synth_upload(network_controller)
    df[fillable[0]] = np.nan
    out = network_controller.handle_upload(to_csv_upload(df))
    assert out[fillable[0]].isna().all()  # left for transform() to fill

    result = network_controller.run_pipeline(out)
    assert result["verdict"] in list(network_controller.classifier.label_encoder.classes_)


@requires_network
def test_nan_without_a_fill_rule_is_rejected(network_controller):
    handled = network_controller.preprocessor.missingness_handled_cols
    unhandled = [c for c in network_controller.feature_cols
                 if c not in handled and not c.endswith("_incomplete")]
    df = synth_upload(network_controller)
    df[unhandled[0]] = np.nan
    with pytest.raises(ValueError, match="no fill rule for"):
        network_controller.handle_upload(to_csv_upload(df))


@requires_network
def test_non_numeric_garbage_is_treated_as_missing(network_controller):
    handled = network_controller.preprocessor.missingness_handled_cols
    unhandled = [c for c in network_controller.feature_cols
                 if c not in handled and not c.endswith("_incomplete")]
    df = synth_upload(network_controller)
    df[unhandled[0]] = "not a number"
    with pytest.raises(ValueError, match="no fill rule for"):
        network_controller.handle_upload(to_csv_upload(df))


# --------------------------------------------------------------------
# FR-3/4/5: aggregate to one verdict, with a matching explanation
# --------------------------------------------------------------------

@requires_network
def test_verdict_is_the_mean_of_flow_probabilities(network_controller):
    # A capture is many flows from ONE sample, so the verdict is the mean
    # of their probabilities -- not row 0's call.
    df = network_controller.handle_upload(to_csv_upload(synth_upload(network_controller, 12)))
    result = network_controller.run_pipeline(df)

    expected = result["probabilities"].mean(axis=0)
    pd.testing.assert_series_equal(result["aggregate_probabilities"], expected)
    assert result["verdict"] == expected.idxmax()
    assert result["confidence"] == pytest.approx(float(expected.max()))
    assert result["n_rows"] == 12


@requires_network
def test_aggregate_probabilities_are_a_distribution(network_controller):
    df = network_controller.handle_upload(to_csv_upload(synth_upload(network_controller, 7)))
    proba = network_controller.run_pipeline(df)["aggregate_probabilities"]
    assert proba.sum() == pytest.approx(1.0)
    assert (proba >= 0).all()


@requires_network
def test_explanation_describes_a_row_assigned_to_the_verdict(network_controller):
    # Otherwise the SHAP chart explains a different category than the one
    # shown as the answer.
    df = network_controller.handle_upload(to_csv_upload(synth_upload(network_controller, 10)))
    result = network_controller.run_pipeline(df)

    if (result["row_predictions"] == result["verdict"]).any():
        top = result["top_features"]
        assert list(top.columns) == ["feature", "value", "shap_value"]
        assert len(top) == 8
        assert set(top["feature"]) <= set(network_controller.feature_cols)


@requires_memory
def test_single_row_memory_upload_works(memory_controller):
    # A memory sample is usually ONE row; aggregation must degenerate
    # cleanly rather than assuming many.
    df = memory_controller.handle_upload(to_csv_upload(synth_upload(memory_controller, 1)))
    result = memory_controller.run_pipeline(df)
    assert result["n_rows"] == 1
    assert result["confidence"] == pytest.approx(
        float(result["aggregate_probabilities"].max()))


@requires_memory
def test_memory_bundle_predating_derivations_still_loads(memory_controller):
    # The memory artifacts were pickled before `derivations` existed.
    # bundle.get(..., []) is what keeps them loadable.
    assert memory_controller.derivations == []


# --------------------------------------------------------------------
# FR-6: qualitative risk level
# --------------------------------------------------------------------

def test_confident_prediction_keeps_its_category_risk():
    assert risk_level("Rootkit", 0.9) == "Critical"
    assert risk_level("Benign", 0.9) == "Low"


@pytest.mark.parametrize("category,expected", [
    ("Rootkit", "High"), ("Trojan", "Medium"), ("HackTool", "Low"), ("Benign", "Low")])
def test_low_confidence_downgrades_one_notch(category, expected):
    # A shaky call on a dangerous-sounding label shouldn't read as
    # urgently as a confident one.
    assert risk_level(category, 0.49) == expected


def test_threshold_is_at_half():
    assert risk_level("Rootkit", 0.5) == "Critical"
    assert risk_level("Rootkit", 0.4999) == "High"


def test_unknown_category_defaults_to_medium():
    assert risk_level("Something New", 0.9) == "Medium"


def test_every_trained_category_has_a_risk_mapping():
    expected = {"Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
                "Rootkit", "Trojan", "Virus", "Worm"}
    assert set(RISK_BY_CATEGORY) == expected
