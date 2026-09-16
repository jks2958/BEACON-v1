import json

import numpy as np
import pytest

from pipeline.ingestion import (EvidenceIngestionService, EvidenceType, EvidenceUpload,
                                MalformedEvidenceError, StreamMismatchError)
from pipeline.memory_feature_contract import MEMORY_FEATURE_CONTRACT
from pipeline.network_contract import CompatibilityStatus


def upload(records, metadata=None, filename="evidence.json"):
    content = json.dumps({"metadata": metadata or {}, "records": records}).encode()
    return EvidenceUpload(filename, content, "memory")


def test_structured_evidence_preserves_values_order_and_metadata_without_filling():
    records = [{"pslist.nproc": 3, "custom": 9}, {"pslist.nproc": 5, "custom": 7}]
    parsed = EvidenceIngestionService().ingest(
        upload(records, {"tool": "Volatility", "plugins": ["pslist"]})
    )
    assert parsed.evidence_type is EvidenceType.MEMORY_VOLATILITY
    assert parsed.stream == "memory" and parsed.row_count == 2
    assert list(parsed.dataframe.columns) == ["pslist.nproc", "custom"]
    assert parsed.dataframe.to_dict("records") == records
    assert parsed.metadata["declared_tool"] == "Volatility"
    assert parsed.metadata["declared_plugins"] == ("pslist",)
    assert len(parsed.metadata["missing_features"]) == 93
    assert parsed.metadata["extra_fields"] == ("custom",)
    assert not parsed.dataframe.isna().any().any()


def test_complete_named_record_remains_gated_when_semantics_are_unproven():
    record = {name: 1.0 for name in MEMORY_FEATURE_CONTRACT.feature_names}
    parsed = EvidenceIngestionService().ingest(upload([record]))
    report = parsed.metadata["feature_contract"]
    assert report.present_count == 94 and report.exact_order
    assert report.status is CompatibilityStatus.PARTIALLY_COMPATIBLE
    assert not report.safe_for_inference


def test_non_numeric_and_non_finite_values_are_reported_not_coerced():
    record = {name: 1.0 for name in MEMORY_FEATURE_CONTRACT.feature_names}
    record[MEMORY_FEATURE_CONTRACT.feature_names[0]] = "not-a-number"
    record[MEMORY_FEATURE_CONTRACT.feature_names[1]] = np.inf
    # JSON has no portable infinity, so construct its accepted representation.
    parsed = EvidenceIngestionService().ingest(upload([record]))
    report = parsed.metadata["feature_contract"]
    assert MEMORY_FEATURE_CONTRACT.feature_names[0] in report.non_numeric_features
    assert MEMORY_FEATURE_CONTRACT.feature_names[1] in report.non_finite_features
    assert parsed.dataframe.iloc[0, 0] == "not-a-number"


@pytest.mark.parametrize("content", [b"", b"not json", b"{}", b'{"records": []}', b'{"records": [1]}'])
def test_malformed_structured_evidence_is_rejected(content):
    with pytest.raises(MalformedEvidenceError):
        EvidenceIngestionService().ingest(EvidenceUpload("evidence.json", content, "memory"))


def test_structured_evidence_cannot_route_to_network():
    with pytest.raises(StreamMismatchError):
        EvidenceIngestionService().ingest(EvidenceUpload("evidence.json", b"{}", "network"))


def test_plugin_metadata_must_be_a_fixed_list_not_freeform_arguments():
    bad = json.dumps({"metadata": {"plugins": "pslist --arbitrary"},
                      "records": [{"pslist.nproc": 1}]}).encode()
    with pytest.raises(MalformedEvidenceError, match="list of names"):
        EvidenceIngestionService().ingest(EvidenceUpload("evidence.json", bad, "memory"))


@pytest.mark.parametrize("extension", ["raw", "mem", "dmp"])
def test_raw_memory_formats_remain_unsupported(extension):
    from pipeline.ingestion import UnsupportedEvidenceError
    with pytest.raises(UnsupportedEvidenceError, match="not supported"):
        EvidenceIngestionService().ingest(EvidenceUpload(f"image.{extension}", b"bytes", "memory"))
