import pytest

from pipeline.application import analyze_evidence
from pipeline.ingestion import (EvidenceIngestionService, EvidenceUpload,
                                IncompatibleEvidenceError)
from pcap_fixtures import pcap_bytes, pcapng_bytes, two_way_udp_packets


@pytest.mark.parametrize("extension,builder", [("pcap", pcap_bytes), ("pcapng", pcapng_bytes)])
def test_unproven_capture_features_cannot_reach_production_model(extension, builder):
    parsed = EvidenceIngestionService().ingest(
        EvidenceUpload(f"capture.{extension}", builder(two_way_udp_packets()), "network")
    )
    with pytest.raises(IncompatibleEvidenceError, match="inference is disabled"):
        analyze_evidence(parsed)
