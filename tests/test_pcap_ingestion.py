import pytest

from pipeline.ingestion import (EvidenceIngestionService, EvidenceType, EvidenceUpload,
                                MalformedEvidenceError)
from pipeline.network_contract import CompatibilityStatus
from pcap_fixtures import pcap_bytes, pcapng_bytes, two_way_udp_packets


@pytest.mark.parametrize("extension,builder,evidence_type", [
    ("pcap", pcap_bytes, EvidenceType.NETWORK_PCAP),
    ("pcapng", pcapng_bytes, EvidenceType.NETWORK_PCAPNG),
])
def test_capture_parsers_preserve_metadata_and_return_diagnostics(extension, builder, evidence_type):
    content = builder(two_way_udp_packets())
    parsed = EvidenceIngestionService().ingest(
        EvidenceUpload(f"capture.{extension}", content, "network")
    )
    assert parsed.evidence_type is evidence_type
    assert parsed.stream == "network"
    assert parsed.metadata["packet_count"] == 2
    assert parsed.metadata["flow_count"] == 1
    assert parsed.metadata["capture_duration"] == pytest.approx(0.25)
    assert parsed.row_count == 1
    assert parsed.compatibility_status is CompatibilityStatus.PARTIALLY_COMPATIBLE


@pytest.mark.parametrize("name,content", [
    ("empty.pcap", b""), ("bad.pcap", b"not a capture"),
    ("bad.pcapng", b"not a capture"),
])
def test_empty_or_malformed_capture_is_rejected(name, content):
    with pytest.raises(MalformedEvidenceError):
        EvidenceIngestionService().ingest(EvidenceUpload(name, content, "network"))


def test_capture_with_no_usable_flows_is_rejected():
    ethernet_non_ip = b"\x00" * 12 + b"\x08\x06" + b"\x00" * 28
    content = pcap_bytes([(1.0, ethernet_non_ip)])
    with pytest.raises(MalformedEvidenceError, match="zero usable"):
        EvidenceIngestionService().ingest(EvidenceUpload("arp.pcap", content, "network"))
