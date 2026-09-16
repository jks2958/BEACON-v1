import json

import joblib
import pytest

from pipeline.network_contract import (CONTRACT_PATH, CompatibilityStatus,
                                       NETWORK_FEATURE_CONTRACT)
from pipeline.pcap import extract_diagnostic_flows, parse_capture
from pcap_fixtures import pcap_bytes, two_way_udp_packets


def test_machine_contract_exactly_matches_shipped_feature_order():
    bundle = joblib.load("models/network_preprocessing_artifacts.joblib")
    assert len(NETWORK_FEATURE_CONTRACT.feature_names) == 342
    assert list(NETWORK_FEATURE_CONTRACT.feature_names) == bundle["feature_cols"]
    assert {entry["expected_type"] for entry in NETWORK_FEATURE_CONTRACT.entries} == {"float"}
    with open(CONTRACT_PATH) as handle:
        assert json.load(handle)["safe_for_native_capture_inference"] is False


def test_two_way_packets_form_one_bidirectional_diagnostic_flow():
    capture = parse_capture(pcap_bytes(two_way_udp_packets()), "pcap")
    frame = extract_diagnostic_flows(capture)
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["dst_port"] == 53
    assert row["duration"] == pytest.approx(0.25)
    assert row["packets_count"] == 2
    assert row["fwd_packets_count"] == 1
    assert row["bwd_packets_count"] == 1
    assert row["total_payload_bytes"] == 8
    assert row["fwd_total_payload_bytes"] == 3
    assert row["bwd_total_payload_bytes"] == 5


def test_diagnostic_frame_fails_closed_against_production_contract():
    capture = parse_capture(pcap_bytes(two_way_udp_packets()), "pcap")
    frame = extract_diagnostic_flows(capture)
    compatibility = NETWORK_FEATURE_CONTRACT.validate(frame)
    assert compatibility.status is CompatibilityStatus.PARTIALLY_COMPATIBLE
    assert compatibility.required_count == 342
    assert compatibility.present_count == 20
    assert len(compatibility.missing_features) == 322
    assert compatibility.extra_features == ()
    assert compatibility.empirically_reproduced is False
    assert compatibility.safe_for_inference is False
