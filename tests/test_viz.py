"""viz.headline(): pulling (accuracy, macro_f1, n) out of metrics files.

The two streams' files are shaped differently, and getting this wrong is
not cosmetic -- the landing page once labelled a flow-level figure as
"per capture", which overstates what the model does.
"""
import json

import pytest

from pipeline.viz import headline, load_metrics, palette, STATUS

NETWORK_SHAPED = {
    "flow_level": {"test_accuracy": 0.6825, "test_macro_f1": 0.6454,
                   "n_test_flows": 129118},
    "sample_level": {"test_accuracy": 0.9911, "test_macro_f1": 0.9910,
                     "n_test_samples": 447},
}

MEMORY_SHAPED = {
    "test_macro_f1": 0.5583, "test_rows": 1836,
    "test_classification_report": {"accuracy": 0.5915},
}


def test_none_metrics_yields_none():
    assert headline(None) is None
    assert headline({}) is None


def test_flow_unit_selects_the_flow_block():
    head = headline(NETWORK_SHAPED, "flow")
    assert head["accuracy"] == pytest.approx(0.6825)
    assert head["n"] == 129118


def test_sample_unit_selects_the_sample_block():
    head = headline(NETWORK_SHAPED, "sample")
    assert head["accuracy"] == pytest.approx(0.9911)
    assert head["n"] == 447


def test_the_two_units_are_not_interchangeable():
    # If these ever collapse to one number, a page is quoting the wrong
    # unit somewhere.
    assert headline(NETWORK_SHAPED, "flow")["accuracy"] != \
        headline(NETWORK_SHAPED, "sample")["accuracy"]


def test_flat_memory_shape_reads_accuracy_out_of_the_report():
    head = headline(MEMORY_SHAPED)
    assert head["accuracy"] == pytest.approx(0.5915)
    assert head["macro_f1"] == pytest.approx(0.5583)
    assert head["n"] == 1836


def test_missing_accuracy_yields_none_rather_than_a_zero():
    # Reporting 0.0% would look like a measurement; None lets the caller
    # omit the tile entirely.
    assert headline({"test_macro_f1": 0.5, "test_rows": 10}) is None


def test_committed_network_metrics_carry_both_units():
    # Guards the real file, not a fixture: a retrain that wrote only one
    # block would silently change what the pages report.
    metrics = load_metrics("network")
    if metrics is None:
        pytest.skip("network metrics not present")
    assert "flow_level" in metrics and "sample_level" in metrics
    flow, sample = headline(metrics, "flow"), headline(metrics, "sample")
    assert flow["n"] > sample["n"], "flows should outnumber captures"
    assert 0.0 < flow["accuracy"] <= 1.0
    assert 0.0 < sample["accuracy"] <= 1.0


def test_committed_memory_metrics_are_readable():
    metrics = load_metrics("memory")
    if metrics is None:
        pytest.skip("memory metrics not present")
    head = headline(metrics)
    assert 0.0 < head["accuracy"] <= 1.0
    assert head["n"] > 0


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_palette_defines_every_token_charts_use(theme):
    p = palette(theme)
    for token in ("baseline", "text_secondary", "muted", "accent"):
        assert token in p, f"{theme} palette missing {token}"


def test_status_colours_are_distinct():
    assert len(set(STATUS.values())) == len(STATUS)
