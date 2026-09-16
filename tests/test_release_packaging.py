from pathlib import Path

import pandas as pd
import pytest

from pipeline.application import analyze_upload
from pipeline.ingestion import EvidenceIngestionService, EvidenceUpload, MalformedEvidenceError
from pipeline.volatility import MAX_STRUCTURED_EVIDENCE_BYTES

ROOT = Path(__file__).parents[1]


def test_release_version_and_required_final_documents_exist():
    assert (ROOT / "VERSION").read_text().strip() == "1.0.0"
    for relative in [
        "docs/Final_Architecture.md", "docs/Final_Validation_Matrix.md",
        "docs/Limitations_and_Future_Work.md", "docs/Project_Summary.md",
        "docs/Release_Notes_v1.0.0.md", "docs/Supervisor_Demo_Guide.md",
    ]:
        assert (ROOT / relative).is_file()


def _analyze_demo(stream):
    path = ROOT / "demo" / f"{stream}_sample.csv"
    with path.open("rb") as upload:
        output = analyze_upload(stream, upload)
    assert output.stream == stream
    assert output.result["n_rows"] == len(pd.read_csv(path))
    assert output.result["verdict"] in output.result["aggregate_probabilities"].index
    assert output.result["top_features"].shape[0] > 0
    return output


def test_network_demo_fixture_runs_real_production_pipeline():
    _analyze_demo("network")


def test_memory_demo_fixture_runs_real_production_pipeline():
    _analyze_demo("memory")


def test_demo_fixtures_are_explicitly_disclosed_as_synthetic_not_benchmarks():
    disclosure = (ROOT / "demo" / "README.md").read_text().lower()
    assert "synthetic" in disclosure and "not malware captures" in disclosure
    assert "not" in disclosure and "benchmark" in disclosure


def test_oversized_volatility_diagnostic_is_rejected_before_json_parsing():
    content = b"{" + b"x" * MAX_STRUCTURED_EVIDENCE_BYTES
    with pytest.raises(MalformedEvidenceError, match="10 MiB"):
        EvidenceIngestionService().ingest(
            EvidenceUpload("oversized.json", content, "memory")
        )
