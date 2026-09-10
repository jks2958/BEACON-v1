"""Shared preprocessing logic for BEACON's Network and Memory pipelines.

This module exists so training and inference apply the exact same
transformations. A Preprocessor instance is fit on training data (via the
fit_* / handle_* methods, which learn parameters like Min-Max ranges or a
correlation drop-list) and its fitted state is then reused unchanged on
test data or on a live inference request through ArtifactStore.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class Preprocessor:
    """Steps 1-8 of BEACON's preprocessing pipeline (dedup through
    correlation pruning), as one object so its fitted parameters
    (Min-Max ranges, correlation drop-list) travel with it rather than
    living in loose training-script globals.
    """

    def __init__(self, label_col: str = "label"):
        self.label_col = label_col
        self.log_cols: list[str] = []
        self.minmax_ranges: dict[str, tuple[float, float]] = {}
        self.corr_drop_cols: list[str] = []
        self.missingness_medians: dict[str, float] = {}
        self.structural_missing_cols: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: duplicate removal
    # ------------------------------------------------------------------
    @staticmethod
    def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(keep="first").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Step 2: drop fully-empty / non-informative columns
    # ------------------------------------------------------------------
    @staticmethod
    def drop_empty_columns(df: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
        """Drop columns that are 100% missing. If `cols` is given, only
        those are checked/dropped (matches training-time behavior where
        the empty-column list, e.g. ['info.winBuild'], is known ahead of
        time); otherwise every column is checked."""
        candidates = cols if cols is not None else list(df.columns)
        to_drop = [c for c in candidates if c in df.columns and df[c].isnull().all()]
        return df.drop(columns=to_drop) if to_drop else df

    # ------------------------------------------------------------------
    # Step 3: label normalization
    # ------------------------------------------------------------------
    def fix_labels(self, df: pd.DataFrame, label_fixes: dict[str, str]) -> pd.DataFrame:
        if self.label_col not in df.columns or not label_fixes:
            return df
        df = df.copy()
        df[self.label_col] = df[self.label_col].replace(label_fixes)
        return df

    # ------------------------------------------------------------------
    # Step 4: missingness — decide sentinel+flag (structural) vs median
    # (random), then apply. Fit on train, reuse fitted medians on test.
    # ------------------------------------------------------------------
    def analyze_missingness(
        self, df: pd.DataFrame, cols: list[str], spread_threshold: float = 50.0
    ) -> dict[str, str]:
        """For each column in `cols`, compute per-class missing rate and
        classify as 'structural' (missingness concentrated in specific
        classes -> spread > threshold) or 'random' (roughly uniform ->
        median imputation is safe)."""
        decisions: dict[str, str] = {}
        if self.label_col not in df.columns:
            return {c: "random" for c in cols if c in df.columns}

        for col in cols:
            if col not in df.columns:
                continue
            missing_pct = (
                df.groupby(self.label_col)[col]
                .apply(lambda s: s.isnull().mean() * 100)
            )
            spread = missing_pct.max() - missing_pct.min()
            decisions[col] = "structural" if spread > spread_threshold else "random"
        return decisions

    def fit_handle_missingness(
        self, df: pd.DataFrame, decisions: dict[str, str]
    ) -> pd.DataFrame:
        """Fit medians for 'random' columns on this (training) data, add
        has_<col> flags + sentinel fill for 'structural' columns, and
        remember both so apply_handle_missingness can replay them on
        unseen data."""
        df = df.copy()
        self.structural_missing_cols = [c for c, d in decisions.items() if d == "structural"]
        random_cols = [c for c, d in decisions.items() if d == "random"]

        for col in self.structural_missing_cols:
            df[f"has_{col}"] = df[col].notna().astype("int8")
            df[col] = df[col].fillna(-1)

        for col in random_cols:
            median_val = df[col].median()
            self.missingness_medians[col] = median_val
            df[col] = df[col].fillna(median_val)

        return df

    def apply_handle_missingness(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replay the fitted Step-4 decisions on new data (test set or a
        live inference request) — never recompute medians here."""
        df = df.copy()
        for col in self.structural_missing_cols:
            if col not in df.columns:
                continue
            df[f"has_{col}"] = df[col].notna().astype("int8")
            df[col] = df[col].fillna(-1)

        for col, median_val in self.missingness_medians.items():
            if col in df.columns:
                df[col] = df[col].fillna(median_val)

        return df

    # ------------------------------------------------------------------
    # Step 6: log-transform heavy-tailed features. log1p is stateless
    # and row-wise, so there is nothing to "fit" beyond remembering
    # which columns qualify — fit_log_transform records that list once
    # (at training time), apply_log_transform replays it everywhere else.
    # ------------------------------------------------------------------
    def fit_log_transform(self, df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        self.log_cols = [c for c in cols if c in df.columns]
        return self.apply_log_transform(df)

    def apply_log_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in self.log_cols:
            if c in df.columns:
                df[c] = np.log1p(df[c].clip(lower=0))
        return df

    # ------------------------------------------------------------------
    # Step 7: Min-Max scaling — fit on train, apply to train and test
    # ------------------------------------------------------------------
    def fit_minmax(self, df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        df = df.copy()
        self.minmax_ranges = {}
        for c in cols:
            if c not in df.columns:
                continue
            col_min, col_max = float(df[c].min()), float(df[c].max())
            self.minmax_ranges[c] = (col_min, col_max)
            span = col_max - col_min
            df[c] = 0.0 if span == 0 else (df[c] - col_min) / span
        return df

    def apply_minmax(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c, (col_min, col_max) in self.minmax_ranges.items():
            if c not in df.columns:
                continue
            span = col_max - col_min
            df[c] = 0.0 if span == 0 else (df[c] - col_min) / span
        return df

    # ------------------------------------------------------------------
    # Step 8: correlation pruning — computed on train only
    # ------------------------------------------------------------------
    def fit_correlation_prune(
        self, df: pd.DataFrame, cols: list[str], threshold: float = 0.9
    ) -> pd.DataFrame:
        corr_matrix = df[cols].corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        self.corr_drop_cols = [c for c in upper.columns if any(upper[c] > threshold)]
        return df.drop(columns=self.corr_drop_cols)

    def apply_correlation_prune(self, df: pd.DataFrame) -> pd.DataFrame:
        existing = [c for c in self.corr_drop_cols if c in df.columns]
        return df.drop(columns=existing) if existing else df

    # ------------------------------------------------------------------
    # Inference-time entry point: replay every fitted step in order on
    # a single uploaded DataFrame, using only parameters learned at
    # training time (no fitting happens here).
    # ------------------------------------------------------------------
    @property
    def missingness_handled_cols(self) -> set[str]:
        """Columns Step 4 was fitted to fill (median-imputed or structural
        sentinel+flag). A NaN in one of these is expected and handled; a
        NaN anywhere else would reach the model unfilled, so callers
        validating an upload can tell the two cases apart."""
        return set(self.missingness_medians) | set(self.structural_missing_cols)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.apply_log_transform(df)
        df = self.apply_handle_missingness(df)
        df = self.apply_minmax(df)
        df = self.apply_correlation_prune(df)
        return df


# ----------------------------------------------------------------------
# Derived features
#
# These run BEFORE a Preprocessor sees the data, because they create the
# columns the Preprocessor was fitted on. They live here rather than in a
# training script because inference has to apply the identical step -- a
# raw capture straight off the wire carries the string form, and the model
# was trained on the encoded form. Which derivations a model needs is
# recorded by name in its artifact bundle (see DERIVATIONS), so inference
# replays exactly what training did instead of hardcoding an assumption.
# ----------------------------------------------------------------------

HANDSHAKE_COLS = ["delta_start", "handshake_duration"]
INCOMPLETE_HANDSHAKE = "not a complete handshake"


def encode_handshake(df: pd.DataFrame) -> pd.DataFrame:
    """Turn 'not a complete handshake' into an explicit binary feature,
    then make the underlying columns genuinely numeric.

    Nulling these out (what ignore_errors=True did originally) throws away
    a real signal: a flow that never completed a handshake is behaviourally
    different from one that completed in 0.03s, and ~39% of rows are in
    that state."""
    df = df.copy()
    for col in HANDSHAKE_COLS:
        if col not in df.columns:
            continue
        incomplete = df[col].astype(str).str.strip() == INCOMPLETE_HANDSHAKE
        df[f"{col}_incomplete"] = incomplete.astype("int8")
        # -1 sentinel: distinguishable from any real duration (>= 0)
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
        df.loc[incomplete, col] = -1.0
    return df


DERIVATIONS = {"encode_handshake": encode_handshake}
