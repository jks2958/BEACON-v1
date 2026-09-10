"""The metrics files are what the report and the dashboard quote, so the
numbers in them have to describe the models that are actually shipped.
"""
import json
import os

import pytest

from conftest import MODEL_DIR, requires_memory, requires_network
from pipeline.artifacts import ArtifactStore

CATEGORIES = {"Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"}


def _metrics(stream):
    path = os.path.join(MODEL_DIR, f"{stream}_metrics.json")
    if not os.path.exists(path):
        pytest.skip(f"{stream} metrics not present")
    with open(path) as fh:
        return json.load(fh)


@pytest.mark.parametrize("stream", ["memory", "network"])
def test_recorded_n_estimators_matches_the_booster(stream):
    # Regression: the memory file recorded Optuna's SUGGESTED 450 while the
    # shipped booster carried 400 rounds, because early stopping overrode
    # the suggestion before the final fit.
    metrics = _metrics(stream)
    model_path = os.path.join(MODEL_DIR, f"{stream}_classifier.joblib")
    if not os.path.exists(model_path):
        pytest.skip(f"{stream} model not present")
    actual = ArtifactStore.load_model(model_path).model.get_booster().num_boosted_rounds()
    assert metrics["best_params"]["n_estimators"] == actual, (
        f"{stream}_metrics.json claims {metrics['best_params']['n_estimators']} "
        f"trees; the shipped model has {actual}")


@pytest.mark.parametrize("stream", ["memory", "network"])
def test_categories_recorded_match_the_label_encoder(stream):
    metrics = _metrics(stream)
    model_path = os.path.join(MODEL_DIR, f"{stream}_classifier.joblib")
    if not os.path.exists(model_path):
        pytest.skip(f"{stream} model not present")
    classes = set(ArtifactStore.load_model(model_path).label_encoder.classes_)
    assert classes == CATEGORIES
    if "categories_present" in metrics:
        assert set(metrics["categories_present"]) == classes


def test_fusion_metrics_record_their_own_caveats():
    path = os.path.join(MODEL_DIR, "fusion_metrics.json")
    if not os.path.exists(path):
        pytest.skip("fusion experiment not run")
    with open(path) as fh:
        d = json.load(fh)
    # The fusion numbers are only interpretable alongside the fact that the
    # models are evaluation-only and the hyperparameters were reused.
    assert "note" in d and "evaluation-only" in d["note"].lower()
    assert d["scored_by_both"] == d["holdout_samples"], \
        "every held-out dual-stream sample should be scored by both streams"

    r = d["results"]
    for arm in ("network_only", "memory_only", "fusion_mean"):
        assert 0.0 <= r[arm]["accuracy"] <= 1.0
        assert r[arm]["n"] == d["scored_by_both"]


def test_fusion_conclusion_is_recorded_not_just_the_numbers():
    path = os.path.join(MODEL_DIR, "fusion_metrics.json")
    if not os.path.exists(path):
        pytest.skip("fusion experiment not run")
    with open(path) as fh:
        d = json.load(fh)
    ab = d.get("batch_effect_ablation")
    if ab is None:
        pytest.skip("ablation not run")
    # The ablation is what makes the memory arm's low score interpretable.
    assert ab["arms"]["neighbours_in_training"]["n"] == ab["arms"]["neighbours_held_out"]["n"], \
        "both ablation arms must be scored on the same samples"
