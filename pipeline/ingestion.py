"""Framework-independent evidence ingestion for BEACON.

Phase 2 supports prepared Network and Memory CSV telemetry only. Parsers turn
uploaded bytes into a normalized evidence contract; scientific schema checks,
derivations, and numeric coercion remain exclusively in DashboardController.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from io import BytesIO
from pathlib import PurePath
from types import MappingProxyType
from typing import BinaryIO, Literal, Mapping, Protocol

import pandas as pd

from pipeline.network_contract import CompatibilityStatus, NETWORK_FEATURE_CONTRACT
from pipeline.pcap import CaptureParseError, extract_diagnostic_flows, parse_capture
from pipeline.volatility import VolatilityEvidenceError, adapt_volatility_json


StreamName = Literal["network", "memory"]


class EvidenceType(StrEnum):
    NETWORK_CSV = "network_csv"
    MEMORY_CSV = "memory_csv"
    NETWORK_PCAP = "network_pcap"
    NETWORK_PCAPNG = "network_pcapng"
    MEMORY_VOLATILITY = "memory_volatility"


class EvidenceIngestionError(ValueError):
    """Base class for failures before scientific feature validation."""


class UnsupportedEvidenceError(EvidenceIngestionError):
    pass


class MalformedEvidenceError(EvidenceIngestionError):
    pass


class StreamMismatchError(EvidenceIngestionError):
    pass


class IncompatibleEvidenceError(EvidenceIngestionError):
    pass


@dataclass(frozen=True)
class EvidenceUpload:
    filename: str
    content: bytes
    declared_stream: str
    mime_type: str | None = None
    evidence_type: EvidenceType | str | None = None

    @classmethod
    def from_file(cls, file: BinaryIO, declared_stream: str) -> "EvidenceUpload":
        """Copy a file-like upload without retaining framework-specific state."""
        getvalue = getattr(file, "getvalue", None)
        if callable(getvalue):
            content = getvalue()
        else:
            original_position = file.tell() if hasattr(file, "tell") else None
            if hasattr(file, "seek"):
                file.seek(0)
            content = file.read()
            if original_position is not None and hasattr(file, "seek"):
                file.seek(original_position)
        if isinstance(content, str):
            content = content.encode("utf-8")
        return cls(
            filename=getattr(file, "name", ""),
            content=bytes(content),
            declared_stream=declared_stream,
            mime_type=getattr(file, "type", None),
        )


@dataclass(frozen=True)
class ParsedEvidence:
    evidence_type: EvidenceType
    stream: StreamName
    dataframe: pd.DataFrame = field(repr=False, compare=False)
    original_filename: str
    row_count: int
    metadata: Mapping[str, object]
    source_bytes: bytes = field(repr=False)
    compatibility_status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE


class EvidenceParser(Protocol):
    evidence_type: EvidenceType
    stream: StreamName

    def parse(self, upload: EvidenceUpload) -> ParsedEvidence: ...


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    """The single low-level CSV reader used by every supported parser."""
    if not content or not content.strip():
        raise MalformedEvidenceError("The uploaded file is empty.")
    try:
        return pd.read_csv(BytesIO(content))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise MalformedEvidenceError(f"The uploaded CSV could not be read: {exc}") from exc


class _CSVParser:
    evidence_type: EvidenceType
    stream: StreamName

    def parse(self, upload: EvidenceUpload) -> ParsedEvidence:
        if upload.declared_stream != self.stream:
            raise StreamMismatchError(
                f"{self.evidence_type.value} evidence cannot be routed to "
                f"the {upload.declared_stream!r} stream."
            )
        dataframe = read_csv_bytes(upload.content)
        return ParsedEvidence(
            evidence_type=self.evidence_type,
            stream=self.stream,
            dataframe=dataframe,
            original_filename=upload.filename,
            row_count=len(dataframe),
            metadata=MappingProxyType({
                "mime_type": upload.mime_type,
                "column_count": len(dataframe.columns),
            }),
            source_bytes=upload.content,
        )


class NetworkCSVParser(_CSVParser):
    evidence_type = EvidenceType.NETWORK_CSV
    stream: StreamName = "network"


class MemoryCSVParser(_CSVParser):
    evidence_type = EvidenceType.MEMORY_CSV
    stream: StreamName = "memory"


class MemoryVolatilityParser:
    """Diagnostic parser for structured evidence; inference remains gated."""
    evidence_type = EvidenceType.MEMORY_VOLATILITY
    stream: StreamName = "memory"

    def parse(self, upload: EvidenceUpload) -> ParsedEvidence:
        if upload.declared_stream != self.stream:
            raise StreamMismatchError(
                "Structured Volatility evidence can only be routed to the memory stream."
            )
        try:
            adapted = adapt_volatility_json(upload.content)
        except VolatilityEvidenceError as exc:
            raise MalformedEvidenceError(str(exc)) from exc
        metadata = dict(adapted.metadata)
        metadata.update({"mime_type": upload.mime_type,
                         "feature_contract": adapted.compatibility})
        return ParsedEvidence(
            evidence_type=self.evidence_type, stream="memory", dataframe=adapted.dataframe,
            original_filename=upload.filename, row_count=len(adapted.dataframe),
            metadata=MappingProxyType(metadata), source_bytes=upload.content,
            compatibility_status=adapted.compatibility.status,
        )


class _NetworkCaptureParser:
    stream: StreamName = "network"
    format_hint: str
    evidence_type: EvidenceType

    def parse(self, upload: EvidenceUpload) -> ParsedEvidence:
        if upload.declared_stream != self.stream:
            raise StreamMismatchError(
                f"{self.evidence_type.value} evidence cannot be routed to "
                f"the {upload.declared_stream!r} stream."
            )
        try:
            capture = parse_capture(upload.content, self.format_hint)
            flows = extract_diagnostic_flows(capture)
        except CaptureParseError as exc:
            raise MalformedEvidenceError(str(exc)) from exc
        compatibility = NETWORK_FEATURE_CONTRACT.validate(flows)
        return ParsedEvidence(
            evidence_type=self.evidence_type, stream="network", dataframe=flows,
            original_filename=upload.filename, row_count=len(flows),
            metadata=MappingProxyType({
                "mime_type": upload.mime_type,
                "capture_format": capture.format,
                "packet_count": len(capture.packets),
                "flow_count": len(flows),
                "capture_duration": capture.duration,
                "link_type": capture.link_type,
                "feature_contract": compatibility,
            }),
            source_bytes=upload.content,
            compatibility_status=compatibility.status,
        )


class NetworkPCAPParser(_NetworkCaptureParser):
    evidence_type = EvidenceType.NETWORK_PCAP
    format_hint = "pcap"


class NetworkPCAPNGParser(_NetworkCaptureParser):
    evidence_type = EvidenceType.NETWORK_PCAPNG
    format_hint = "pcapng"


class EvidenceIngestionService:
    """Validate upload metadata and dispatch to one explicit parser."""

    def __init__(self, parsers: tuple[EvidenceParser, ...] | None = None):
        available = parsers or (
            NetworkCSVParser(), MemoryCSVParser(), NetworkPCAPParser(), NetworkPCAPNGParser(),
            MemoryVolatilityParser(),
        )
        self._parsers = {parser.evidence_type: parser for parser in available}

    def ingest(self, upload: EvidenceUpload) -> ParsedEvidence:
        if not upload.filename:
            raise MalformedEvidenceError("The uploaded file must have a filename.")
        extension = PurePath(upload.filename).suffix.lower()
        supported_extensions = {".csv", ".json", ".pcap", ".pcapng"}
        if extension not in supported_extensions:
            shown = extension or "a file without an extension"
            raise UnsupportedEvidenceError(
                f"{shown!r} is not supported in the current version; "
                "upload prepared CSV telemetry."
            )

        if upload.declared_stream not in {"network", "memory"}:
            raise StreamMismatchError(f"Unsupported evidence stream: {upload.declared_stream!r}")
        if extension in {".pcap", ".pcapng"} and upload.declared_stream != "network":
            raise StreamMismatchError("Packet captures can only be routed to the network stream.")
        if extension == ".json" and upload.declared_stream != "memory":
            raise StreamMismatchError("Structured Volatility JSON can only be routed to the memory stream.")
        expected = {
            ("network", ".csv"): EvidenceType.NETWORK_CSV,
            ("memory", ".csv"): EvidenceType.MEMORY_CSV,
            ("network", ".pcap"): EvidenceType.NETWORK_PCAP,
            ("network", ".pcapng"): EvidenceType.NETWORK_PCAPNG,
            ("memory", ".json"): EvidenceType.MEMORY_VOLATILITY,
        }[(upload.declared_stream, extension)]
        try:
            requested = EvidenceType(upload.evidence_type) if upload.evidence_type else expected
        except ValueError as exc:
            raise UnsupportedEvidenceError(
                f"Evidence type {upload.evidence_type!r} is not supported in the current version."
            ) from exc
        if requested != expected:
            raise StreamMismatchError(
                f"{requested.value} evidence cannot be routed to the {upload.declared_stream} stream."
            )
        return self._parsers[requested].parse(upload)


DEFAULT_INGESTION_SERVICE = EvidenceIngestionService()
