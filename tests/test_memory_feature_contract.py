import json

import joblib
import pandas as pd

from pipeline.memory_feature_contract import (CONTRACT_PATH, MEMORY_FEATURE_CONTRACT,
                                                MemoryFeatureContract)
from pipeline.network_contract import CompatibilityStatus


def test_contract_has_exactly_94_unique_ordered_features():
    assert len(MEMORY_FEATURE_CONTRACT.entries) == 94
    assert len(set(MEMORY_FEATURE_CONTRACT.feature_names)) == 94
    payload = json.loads(open(CONTRACT_PATH).read())
    assert [item["position"] for item in payload["features"]] == list(range(94))


def test_contract_exactly_aligns_with_committed_preprocessing_artifact():
    artifact = joblib.load("models/memory_preprocessing_artifacts.joblib")
    assert list(MEMORY_FEATURE_CONTRACT.feature_names) == artifact["feature_cols"]


def test_shipped_contract_is_structurally_complete_but_empirically_unproven():
    frame = pd.DataFrame([[1.0] * 94], columns=MEMORY_FEATURE_CONTRACT.feature_names)
    report = MEMORY_FEATURE_CONTRACT.validate(frame)
    assert report.present_count == 94 and report.exact_order
    assert report.status is CompatibilityStatus.PARTIALLY_COMPATIBLE
    assert not report.empirically_reproduced and not report.safe_for_inference


def test_fully_proven_contract_can_be_compatible_without_changing_shipped_contract():
    entries = [{"name": "a", "reproduction_status": "exact"},
               {"name": "b", "reproduction_status": "exact"}]
    report = MemoryFeatureContract(entries).validate(pd.DataFrame({"a": [1], "b": [2]}))
    assert report.status is CompatibilityStatus.COMPATIBLE
    assert report.safe_for_inference
