from io import BytesIO

import pandas as pd
import pytest

from pipeline.ingestion import (EvidenceIngestionService, EvidenceType, EvidenceUpload,
                                MalformedEvidenceError, MemoryCSVParser, NetworkCSVParser,
                                StreamMismatchError, UnsupportedEvidenceError)


def upload(frame, stream, name="sample.csv", evidence_type=None):
    return EvidenceUpload(
        filename=name, content=frame.to_csv(index=False).encode(),
        declared_stream=stream, mime_type="text/csv", evidence_type=evidence_type,
    )


@pytest.mark.parametrize("member,value", [
    (EvidenceType.NETWORK_CSV, "network_csv"),
    (EvidenceType.MEMORY_CSV, "memory_csv"),
])
def test_supported_evidence_types_are_explicit(member, value):
    assert member.value == value


def test_invalid_evidence_type_is_rejected():
    item = upload(pd.DataFrame({"a": [1]}), "network", evidence_type="pcap")
    with pytest.raises(UnsupportedEvidenceError, match="not supported in the current version"):
        EvidenceIngestionService().ingest(item)


@pytest.mark.parametrize("parser,stream,evidence_type", [
    (NetworkCSVParser(), "network", EvidenceType.NETWORK_CSV),
    (MemoryCSVParser(), "memory", EvidenceType.MEMORY_CSV),
])
def test_csv_parsers_preserve_filename_rows_columns_order_and_values(parser, stream, evidence_type):
    expected = pd.DataFrame({"second": [3, 1], "first": ["z", "a"], "missing": [None, 4.5]})
    parsed = parser.parse(upload(expected, stream, name="Evidence.CSV"))
    assert parsed.evidence_type is evidence_type
    assert parsed.stream == stream
    assert parsed.original_filename == "Evidence.CSV"
    assert parsed.row_count == 2
    assert list(parsed.dataframe.columns) == ["second", "first", "missing"]
    pd.testing.assert_frame_equal(parsed.dataframe, expected)
    assert parsed.metadata == {"mime_type": "text/csv", "column_count": 3}


def test_parser_performs_no_scientific_coercion_or_cleanup():
    expected = pd.DataFrame({"feature": ["not numeric", "  preserved  "], "extra": [2, 1]})
    parsed = NetworkCSVParser().parse(upload(expected, "network"))
    pd.testing.assert_frame_equal(parsed.dataframe, expected)


def test_upload_from_file_copies_bytes_and_preserves_pointer_and_metadata():
    file = BytesIO(b"a,b\n1,2\n")
    file.name, file.type = "capture.csv", "text/csv"
    file.seek(3)
    item = EvidenceUpload.from_file(file, "network")
    assert item.content == b"a,b\n1,2\n"
    assert item.filename == "capture.csv"
    assert item.mime_type == "text/csv"
    assert file.tell() == 3


@pytest.mark.parametrize("content", [b"", b"   \n", b'a,b\n1,"unterminated'])
def test_empty_or_malformed_csv_is_rejected(content):
    item = EvidenceUpload("bad.csv", content, "network")
    with pytest.raises(MalformedEvidenceError):
        EvidenceIngestionService().ingest(item)


def test_invalid_encoding_is_rejected():
    item = EvidenceUpload("bad.csv", b"name\n\xff\xfe\n", "memory")
    with pytest.raises(MalformedEvidenceError, match="could not be read"):
        EvidenceIngestionService().ingest(item)


def test_missing_filename_is_rejected():
    with pytest.raises(MalformedEvidenceError, match="must have a filename"):
        EvidenceIngestionService().ingest(EvidenceUpload("", b"a\n1", "network"))


@pytest.mark.parametrize("extension", [
    ".raw", ".mem", ".dmp", ".exe", ".dll", ".evtx", ".zip",
])
def test_unsupported_formats_are_explicitly_rejected(extension):
    item = EvidenceUpload(f"sample{extension}", b"not executed", "network")
    with pytest.raises(UnsupportedEvidenceError, match="not supported in the current version"):
        EvidenceIngestionService().ingest(item)


def test_stream_and_evidence_type_mismatch_is_rejected():
    item = upload(
        pd.DataFrame({"a": [1]}), "memory", evidence_type=EvidenceType.NETWORK_CSV,
    )
    with pytest.raises(StreamMismatchError, match="cannot be routed"):
        EvidenceIngestionService().ingest(item)


def test_invalid_declared_stream_is_rejected():
    item = upload(pd.DataFrame({"a": [1]}), "disk")
    with pytest.raises(StreamMismatchError, match="Unsupported evidence stream"):
        EvidenceIngestionService().ingest(item)


@pytest.mark.parametrize("extension", [".pcap", ".pcapng"])
def test_capture_cannot_be_routed_to_memory(extension):
    item = EvidenceUpload(f"capture{extension}", b"capture", "memory")
    with pytest.raises(StreamMismatchError, match="only be routed to the network"):
        EvidenceIngestionService().ingest(item)


def test_normalized_evidence_contains_no_analysis_or_framework_objects():
    parsed = EvidenceIngestionService().ingest(upload(pd.DataFrame({"a": [1]}), "network"))
    names = set(vars(parsed))
    assert not names & {"controller", "classifier", "model", "explainer", "session_state", "result"}
