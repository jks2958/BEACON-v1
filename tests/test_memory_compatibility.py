import json

import pytest

from pipeline.application import analyze_evidence
from pipeline.ingestion import (EvidenceIngestionService, EvidenceUpload,
                                IncompatibleEvidenceError)
from pipeline.memory_feature_contract import MEMORY_FEATURE_CONTRACT


def test_partial_volatility_evidence_fails_closed_before_controller(monkeypatch):
    parsed = EvidenceIngestionService().ingest(EvidenceUpload(
        "volatility.json", json.dumps({"records": [{"pslist.nproc": 4}]}).encode(), "memory"
    ))
    with pytest.raises(IncompatibleEvidenceError, match="Memory diagnostic inference is disabled"):
        analyze_evidence(parsed)


def test_all_94_named_fields_still_fail_closed_without_empirical_equivalence():
    record = {name: 1 for name in MEMORY_FEATURE_CONTRACT.feature_names}
    parsed = EvidenceIngestionService().ingest(EvidenceUpload(
        "volatility.json", json.dumps({"records": [record]}).encode(), "memory"
    ))
    with pytest.raises(IncompatibleEvidenceError, match="unproven"):
        analyze_evidence(parsed)
