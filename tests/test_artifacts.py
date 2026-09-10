"""ArtifactStore round-trip, and the shape of the committed bundles.

A model and the preprocessing state that produced it must travel
together; a bundle that loses its fitted parameters would silently
predict on differently-scaled inputs.
"""
import numpy as np
import pandas as pd
import pytest

from conftest import requires_memory, requires_network
from pipeline.artifacts import ArtifactStore
from pipeline.classifier import NetworkClassifier
from pipeline.common import Preprocessor


def test_preprocessor_survives_a_round_trip(tmp_path):
    pre = Preprocessor(label_col="label")
    train = pd.DataFrame({"label": ["A"] * 4, "x": [1.0, 2.0, np.nan, 4.0]})
    pre.fit_handle_missingness(train, {"x": "random"})
    pre.fit_minmax(train, ["x"])

    path = str(tmp_path / "artifacts.joblib")
    ArtifactStore.save_artifacts({"preprocessor": pre, "feature_cols": ["x"]}, path)
    loaded = ArtifactStore.load_artifacts(path)["preprocessor"]

    assert loaded.minmax_ranges == pre.minmax_ranges
    assert loaded.missingness_medians == pre.missingness_medians
    assert loaded.missingness_handled_cols == pre.missingness_handled_cols


def test_model_survives_a_round_trip_and_predicts_identically(tmp_path):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((40, 3)), columns=list("abc"))
    y = pd.Series([f"C{i % 3}" for i in range(40)])
    clf = NetworkClassifier()
    clf.train(X, y, n_estimators=5, max_depth=2)

    path = str(tmp_path / "model.joblib")
    ArtifactStore.save_model(clf, path)
    reloaded = ArtifactStore.load_model(path)

    assert list(reloaded.predict(X)) == list(clf.predict(X))
    assert list(reloaded.label_encoder.classes_) == list(clf.label_encoder.classes_)


@requires_network
def test_committed_network_bundle_records_its_derivations(network_controller):
    # Without this key, inference has no way to know the model was trained
    # on encoded handshake columns.
    assert network_controller.derivations, "network bundle lost its derivations"


@requires_network
def test_feature_cols_match_what_the_model_expects(network_controller):
    assert set(network_controller.feature_cols) == \
        set(network_controller.classifier.feature_order)


@requires_memory
def test_memory_feature_cols_match_the_model(memory_controller):
    assert set(memory_controller.feature_cols) == \
        set(memory_controller.classifier.feature_order)


@requires_network
def test_both_streams_cover_the_nine_categories(network_controller, memory_controller):
    expected = {"Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
                "Rootkit", "Trojan", "Virus", "Worm"}
    assert set(network_controller.classifier.label_encoder.classes_) == expected
    assert set(memory_controller.classifier.label_encoder.classes_) == expected
