"""Preprocessor, Steps 1-8.

The property under test throughout is that fit_* learns parameters from
training data and apply_* replays them UNCHANGED -- recomputing anything
at inference time is the silent-drift bug this class exists to prevent.
"""
import numpy as np
import pandas as pd
import pytest

from pipeline.common import Preprocessor


def test_remove_duplicates_keeps_first_and_reindexes():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    out = Preprocessor.remove_duplicates(df)
    assert len(out) == 2
    assert list(out.index) == [0, 1]


def test_drop_empty_columns_autodetects_all_null():
    # Regression: a hardcoded column list missed pslist.avg_handlers,
    # which was 100% null -> its median was NaN -> KMeans crashed.
    df = pd.DataFrame({"keep": [1.0, 2.0], "empty": [np.nan, np.nan],
                       "partial": [1.0, np.nan]})
    out = Preprocessor.drop_empty_columns(df)
    assert list(out.columns) == ["keep", "partial"]


def test_drop_empty_columns_respects_explicit_list():
    df = pd.DataFrame({"a": [np.nan, np.nan], "b": [np.nan, np.nan]})
    out = Preprocessor.drop_empty_columns(df, cols=["a"])
    assert list(out.columns) == ["b"]


def test_fix_labels_normalises_only_named_values():
    pre = Preprocessor(label_col="label")
    df = pd.DataFrame({"label": ["Zbenign", "Trojan"]})
    out = pre.fix_labels(df, {"Zbenign": "Benign"})
    assert list(out["label"]) == ["Benign", "Trojan"]


def test_fix_labels_is_a_noop_without_the_label_column():
    pre = Preprocessor(label_col="label")
    df = pd.DataFrame({"other": [1]})
    assert pre.fix_labels(df, {"a": "b"}).equals(df)


def test_analyze_missingness_splits_structural_from_random():
    # 'structural' is missingness concentrated in particular classes;
    # 'random' is roughly uniform, where a median fill is safe.
    df = pd.DataFrame({
        "label": ["A"] * 10 + ["B"] * 10,
        "structural": [np.nan] * 10 + list(range(10)),
        "random": [np.nan, 1] * 10,
    })
    pre = Preprocessor(label_col="label")
    decisions = pre.analyze_missingness(df, ["structural", "random"])
    assert decisions["structural"] == "structural"
    assert decisions["random"] == "random"


def test_missingness_replays_train_medians_not_test_medians():
    pre = Preprocessor(label_col="label")
    train = pd.DataFrame({"label": ["A"] * 4, "x": [1.0, 3.0, np.nan, 5.0]})
    pre.fit_handle_missingness(train, {"x": "random"})
    assert pre.missingness_medians["x"] == 3.0

    # A test frame whose own median is wildly different must still be
    # filled with the TRAIN median.
    test = pd.DataFrame({"label": ["A", "A"], "x": [np.nan, 1000.0]})
    assert pre.apply_handle_missingness(test)["x"].iloc[0] == 3.0


def test_structural_missingness_adds_flag_and_sentinel():
    pre = Preprocessor(label_col="label")
    train = pd.DataFrame({"label": ["A", "B"], "x": [np.nan, 2.0]})
    out = pre.fit_handle_missingness(train, {"x": "structural"})
    assert list(out["has_x"]) == [0, 1]
    assert out["x"].iloc[0] == -1


def test_missingness_handled_cols_reports_both_kinds():
    # The controller's upload validation keys off this: a NaN in one of
    # these is expected, a NaN anywhere else is fatal.
    pre = Preprocessor(label_col="label")
    train = pd.DataFrame({"label": ["A", "B"], "s": [np.nan, 1.0], "r": [np.nan, 2.0]})
    pre.fit_handle_missingness(train, {"s": "structural", "r": "random"})
    assert pre.missingness_handled_cols == {"s", "r"}


def test_missingness_handled_cols_empty_before_fitting():
    assert Preprocessor().missingness_handled_cols == set()


def test_log_transform_records_columns_and_clips_negatives():
    pre = Preprocessor()
    df = pd.DataFrame({"a": [0.0, np.e - 1], "absent": [1.0, 1.0]})
    out = pre.fit_log_transform(df, ["a", "not_a_column"])
    assert pre.log_cols == ["a"]
    assert out["a"].iloc[0] == 0.0
    assert out["a"].iloc[1] == pytest.approx(1.0)


def test_minmax_fits_on_train_and_can_exceed_range_on_test():
    # Deliberate: a test value beyond the training range SHOULD scale past
    # 1.0. Clipping it would hide distribution shift from the model.
    pre = Preprocessor()
    train = pd.DataFrame({"x": [0.0, 10.0]})
    pre.fit_minmax(train, ["x"])
    assert pre.minmax_ranges["x"] == (0.0, 10.0)
    out = pre.apply_minmax(pd.DataFrame({"x": [5.0, 20.0]}))
    assert out["x"].iloc[0] == 0.5
    assert out["x"].iloc[1] == 2.0


def test_minmax_constant_column_becomes_zero_not_nan():
    pre = Preprocessor()
    pre.fit_minmax(pd.DataFrame({"x": [7.0, 7.0]}), ["x"])
    assert (pre.apply_minmax(pd.DataFrame({"x": [7.0]}))["x"] == 0.0).all()


def test_correlation_prune_drops_and_replays_the_same_list():
    pre = Preprocessor()
    train = pd.DataFrame({"a": [1.0, 2, 3, 4], "dup": [2.0, 4, 6, 8],
                          "b": [4.0, 1, 3, 2]})
    out = pre.fit_correlation_prune(train, ["a", "dup", "b"], threshold=0.9)
    assert pre.corr_drop_cols == ["dup"]
    assert "dup" not in out.columns
    assert "dup" not in pre.apply_correlation_prune(
        pd.DataFrame({"a": [1.0], "dup": [2.0], "b": [1.0]})).columns


def test_correlation_prune_threshold_one_disables_it():
    # train_memory.py and train_network.py both pass 1.0 to turn Step 8
    # off, after measuring that it cost real signal.
    pre = Preprocessor()
    train = pd.DataFrame({"a": [1.0, 2, 3], "dup": [2.0, 4, 6]})
    out = pre.fit_correlation_prune(train, ["a", "dup"], threshold=1.0)
    assert pre.corr_drop_cols == []
    assert list(out.columns) == ["a", "dup"]


def test_apply_correlation_prune_tolerates_already_absent_columns():
    pre = Preprocessor()
    pre.corr_drop_cols = ["gone"]
    df = pd.DataFrame({"a": [1.0]})
    assert pre.apply_correlation_prune(df).equals(df)


def test_transform_runs_every_fitted_step():
    pre = Preprocessor(label_col="label")
    train = pd.DataFrame({"label": ["A"] * 4,
                          "big": [0.0, 10.0, 20.0, 30.0],
                          "gap": [1.0, 2.0, np.nan, 4.0],
                          "dup": [0.0, 10.0, 20.0, 30.0]})
    pre.fit_log_transform(train, ["big"])
    train = pre.apply_log_transform(train)
    train = pre.fit_handle_missingness(train, {"gap": "random"})
    pre.fit_minmax(train, ["big", "gap", "dup"])
    train = pre.apply_minmax(train)
    pre.fit_correlation_prune(train, ["big", "gap", "dup"], threshold=0.9)

    out = pre.transform(pd.DataFrame({"big": [10.0], "gap": [np.nan], "dup": [10.0]}))
    assert "dup" not in out.columns          # step 8 replayed
    assert out["gap"].notna().all()          # step 4 replayed
    assert 0.0 <= out["big"].iloc[0] <= 1.0  # steps 6+7 replayed
