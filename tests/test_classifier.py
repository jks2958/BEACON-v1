"""MalwareClassifier objective selection and prediction alignment."""
import numpy as np
import pandas as pd
import pytest

from pipeline.classifier import MemoryClassifier, NetworkClassifier


def _toy(n_classes: int, n: int = 60, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.random((n, 4)), columns=list("abcd"))
    y = pd.Series([f"C{i % n_classes}" for i in range(n)])
    return X, y


def test_binary_uses_the_binary_objective():
    # Regression: multi:softprob with num_class=2 makes predict() return a
    # 2-column matrix instead of 1-D labels, which breaks every sklearn
    # metric downstream.
    clf = NetworkClassifier()
    X, y = _toy(2)
    clf.train(X, y, n_estimators=5, max_depth=2)
    assert clf.model.get_params()["objective"] == "binary:logistic"

    preds = clf.predict(X)
    assert preds.ndim == 1
    assert len(preds) == len(X)
    assert set(preds) <= {"C0", "C1"}


def test_multiclass_uses_softprob_with_num_class():
    clf = NetworkClassifier()
    X, y = _toy(3)
    clf.train(X, y, n_estimators=5, max_depth=2)
    params = clf.model.get_params()
    assert params["objective"] == "multi:softprob"
    assert clf.predict(X).ndim == 1


@pytest.mark.parametrize("n_classes", [2, 3, 9])
def test_predict_proba_columns_are_labels_and_rows_sum_to_one(n_classes):
    clf = MemoryClassifier()
    X, y = _toy(n_classes, n=90)
    clf.train(X, y, n_estimators=5, max_depth=2)
    proba = clf.predict_proba(X)

    assert list(proba.columns) == sorted(set(y))
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert proba.index.equals(X.index)


def test_predict_realigns_shuffled_columns():
    # An upload's column ORDER must not change the answer.
    clf = NetworkClassifier()
    X, y = _toy(3)
    clf.train(X, y, n_estimators=5, max_depth=2)
    shuffled = X[["d", "b", "a", "c"]]
    assert list(clf.predict(shuffled)) == list(clf.predict(X))


def test_missing_feature_raises_a_named_error():
    clf = NetworkClassifier()
    X, y = _toy(3)
    clf.train(X, y, n_estimators=5, max_depth=2)
    with pytest.raises(ValueError, match="missing required feature"):
        clf.predict(X.drop(columns=["b"]))


def test_stream_name_appears_in_the_error():
    clf = MemoryClassifier()
    X, y = _toy(3)
    clf.train(X, y, n_estimators=5, max_depth=2)
    with pytest.raises(ValueError, match="memory classifier"):
        clf.predict(X.drop(columns=["a"]))
