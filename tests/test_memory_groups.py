import pandas as pd
import pytest

from pipeline.memory_groups import aggregate_snapshot_features, memory_group_id, snapshot_family


def test_snapshot_family_only_removes_a_terminal_numeric_suffix():
    assert snapshot_family("1028_5") == "1028"
    assert snapshot_family("abc_12_timeout") == "abc_12_timeout"
    assert snapshot_family("sha256") == "sha256"


def test_memory_group_modes_are_explicit_and_category_safe():
    assert memory_group_id("Trojan", "1028_2", "stem") == "1028_2"
    assert memory_group_id("Trojan", "1028_2", "category_stem") == "Trojan/1028_2"
    assert memory_group_id("Trojan", "1028_2") == "Trojan/1028"
    with pytest.raises(ValueError, match="Unknown Memory grouping"):
        memory_group_id("Trojan", "1028_2", "guess")


def test_snapshot_aggregation_builds_distribution_and_change_features():
    frame = pd.DataFrame({
        "group_id": ["Trojan/a", "Trojan/a", "Benign/b"],
        "label": ["Trojan", "Trojan", "Benign"],
        "count": [2.0, 8.0, 4.0],
    })
    result = aggregate_snapshot_features(frame, ["count"]).set_index("group_id")
    assert result.loc["Trojan/a", "count__mean"] == 5.0
    assert result.loc["Trojan/a", "count__delta"] == 6.0
    assert result.loc["Trojan/a", "count__range"] == 6.0
    assert result.loc["Benign/b", "count__std"] == 0.0


def test_snapshot_aggregation_rejects_mixed_label_groups():
    frame = pd.DataFrame({
        "group_id": ["same", "same"], "label": ["Trojan", "Benign"], "x": [1, 2]
    })
    with pytest.raises(ValueError, match="multiple labels"):
        aggregate_snapshot_features(frame, ["x"])
