"""Resamplers. Only the training scripts use these, but a resampler that
inflates the majority class, or that loses track of which rows are
synthetic, would inflate every metric the report quotes -- Exploit's
Memory-stream training data is ~90% synthetic, so that flag is what
keeps its per-class numbers honestly caveated.
"""
import numpy as np
import pandas as pd
import pytest

from pipeline.resampling import ClusterBasedResampler, SmoteResampler


@pytest.fixture
def imbalanced():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((120, 4)), columns=list("abcd"))
    y = pd.Series(["Major"] * 100 + ["Minor"] * 20)
    return X, y


def test_smote_balances_the_minority_up(imbalanced):
    X, y = imbalanced
    Xr, yr = SmoteResampler(random_state=0).resample(X, y)
    counts = pd.Series(yr).value_counts()
    assert counts["Minor"] > 20
    assert len(Xr) == len(yr)
    assert list(Xr.columns) == list(X.columns)


def test_cluster_based_targets_only_the_named_minority(imbalanced):
    X, y = imbalanced
    Xr, yr, is_synth = ClusterBasedResampler(random_state=0).resample(X, y, "Minor")
    counts = pd.Series(yr).value_counts()
    assert counts["Major"] == 100, "majority class must be left untouched"
    assert counts["Minor"] == 100, "minority is raised to the majority count"
    assert len(Xr) == len(yr) == len(is_synth)


def test_synthetic_flag_marks_exactly_the_invented_rows(imbalanced):
    X, y = imbalanced
    Xr, yr, is_synth = ClusterBasedResampler(random_state=0).resample(X, y, "Minor")
    flags = np.asarray(is_synth).astype(bool)
    assert flags.sum() == 80, "100 target - 20 real = 80 synthetic"
    # Every synthetic row belongs to the minority class, never the majority.
    assert set(pd.Series(yr)[flags]) == {"Minor"}


def test_explicit_target_total_is_honoured(imbalanced):
    X, y = imbalanced
    _, yr, _ = ClusterBasedResampler(random_state=0).resample(
        X, y, "Minor", target_total=50)
    assert pd.Series(yr).value_counts()["Minor"] == 50


def test_minority_already_at_target_adds_nothing(imbalanced):
    X, y = imbalanced
    Xr, yr, is_synth = ClusterBasedResampler(random_state=0).resample(
        X, y, "Minor", target_total=20)
    assert np.asarray(is_synth).astype(bool).sum() == 0
    assert len(Xr) == len(X)


def test_synthetic_rows_stay_within_the_feature_range(imbalanced):
    # SMOTE interpolates between real points, so it can never produce a
    # value outside the minority class's own observed range.
    X, y = imbalanced
    Xr, yr, is_synth = ClusterBasedResampler(random_state=0).resample(X, y, "Minor")
    flags = np.asarray(is_synth).astype(bool)
    real_min = X[y == "Minor"].min()
    real_max = X[y == "Minor"].max()
    synthetic = Xr[flags]
    for col in X.columns:
        assert synthetic[col].min() >= real_min[col] - 1e-9
        assert synthetic[col].max() <= real_max[col] + 1e-9


def test_best_k_by_silhouette_stays_in_range():
    rng = np.random.default_rng(2)
    X = np.vstack([rng.normal(0, 0.3, (30, 3)), rng.normal(5, 0.3, (30, 3))])
    k = ClusterBasedResampler(k_range=range(2, 5), random_state=0).best_k_by_silhouette(X)
    assert k in range(2, 5)
