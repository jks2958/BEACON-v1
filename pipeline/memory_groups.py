"""Grouping and aggregation helpers for Memory-stream experiments.

The BCCC archive commonly contains sibling names such as ``1028_1`` through
``1028_5``.  They may be repeated observations of one collection subject, so
experiments must be able to keep the whole family on one side of a split.  The
helpers live outside a training script so their behavior is small and tested.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


_SNAPSHOT_SUFFIX = re.compile(r"_(\d+)$")


def snapshot_family(stem: str) -> str:
    """Remove a terminal numeric run/snapshot suffix from a filename stem."""
    return _SNAPSHOT_SUFFIX.sub("", stem)


def memory_group_id(category: str, stem: str, mode: str = "snapshot_family") -> str:
    """Build one of the documented Memory split keys.

    ``stem`` reproduces the shipped model. ``category_stem`` fixes stems that
    collide between category directories. ``snapshot_family`` additionally
    keeps terminal ``_1`` ... ``_5`` siblings together; this is the strict,
    deliberately conservative benchmark until dataset provenance confirms
    whether those files are independent runs.
    """
    if mode == "stem":
        return stem
    if mode == "category_stem":
        return f"{category}/{stem}"
    if mode == "snapshot_family":
        return f"{category}/{snapshot_family(stem)}"
    raise ValueError(f"Unknown Memory grouping mode: {mode}")


def aggregate_snapshot_features(
    frame: pd.DataFrame,
    feature_cols: list[str],
    group_col: str = "group_id",
    label_col: str = "label",
) -> pd.DataFrame:
    """Create one temporal-summary row per snapshot family.

    Mean/std/min/max describe the family distribution; first/last/delta/range
    retain ordered change.  Input order is therefore significant and callers
    should load numbered siblings in natural filename order.
    """
    required = [group_col, label_col, *feature_cols]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot aggregate; missing columns: {missing}")

    labels_per_group = frame.groupby(group_col)[label_col].nunique()
    mixed = labels_per_group[labels_per_group != 1]
    if not mixed.empty:
        raise ValueError(f"Snapshot groups carry multiple labels: {mixed.index.tolist()[:5]}")

    grouped = frame.groupby(group_col, sort=False)[feature_cols]
    summary = grouped.agg(["mean", "std", "min", "max", "first", "last"])
    summary.columns = [f"{feature}__{stat}" for feature, stat in summary.columns]

    first = grouped.first().add_suffix("__first_value")
    last = grouped.last().add_suffix("__last_value")
    delta = last.to_numpy() - first.to_numpy()
    ranges = grouped.max().to_numpy() - grouped.min().to_numpy()
    derived = pd.DataFrame(
        np.concatenate([delta, ranges], axis=1),
        index=summary.index,
        columns=(
            [f"{column}__delta" for column in feature_cols]
            + [f"{column}__range" for column in feature_cols]
        ),
    )
    result = pd.concat([summary, derived], axis=1).replace([np.inf, -np.inf], np.nan).fillna(0)
    result.insert(0, label_col, frame.groupby(group_col, sort=False)[label_col].first())
    result.insert(0, group_col, result.index)
    return result.reset_index(drop=True)
