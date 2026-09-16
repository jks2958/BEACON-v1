"""Dependency-free PCAP/PCAPNG parsing and conservative flow diagnostics.

This module intentionally does not manufacture the shipped model's 342-column
schema. It extracts only packet facts whose semantics are unambiguous; the
feature-contract gate decides that the result is not safe for inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
import ipaddress
import struct

import pandas as pd


MAX_CAPTURE_BYTES = 100 * 1024 * 1024
MAX_PACKETS = 1_000_000


class CaptureParseError(ValueError):
    pass


@dataclass(frozen=True)
class CapturePacket:
    timestamp: float
    captured_length: int
    original_length: int
    data: bytes


@dataclass(frozen=True)
class ParsedCapture:
    format: str
    link_type: int
    packets: tuple[CapturePacket, ...]

    @property
    def duration(self) -> float:
        if len(self.packets) < 2:
            return 0.0
        return max(0.0, self.packets[-1].timestamp - self.packets[0].timestamp)


def parse_capture(content: bytes, format_hint: str) -> ParsedCapture:
    if not content:
        raise CaptureParseError("The uploaded capture is empty.")
    if len(content) > MAX_CAPTURE_BYTES:
        raise CaptureParseError(f"Capture exceeds the {MAX_CAPTURE_BYTES // (1024 * 1024)} MB limit.")
    if format_hint == "pcap":
        return _parse_pcap(content)
    if format_hint == "pcapng":
        return _parse_pcapng(content)
    raise CaptureParseError(f"Unknown capture format: {format_hint}")


def _parse_pcap(content: bytes) -> ParsedCapture:
    if len(content) < 24:
        raise CaptureParseError("Malformed PCAP: truncated global header.")
    magic = content[:4]
    variants = {
        b"\xd4\xc3\xb2\xa1": ("<", 1_000_000), b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
        b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000), b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
    }
    if magic not in variants:
        raise CaptureParseError("Malformed PCAP: unsupported magic number.")
    endian, fraction_scale = variants[magic]
    _, _, _, _, _, link_type = struct.unpack_from(endian + "HHIIII", content, 4)
    if link_type != 1:
        raise CaptureParseError(f"Unsupported PCAP link-layer type {link_type}; Ethernet is required.")
    packets, offset = [], 24
    while offset < len(content):
        if len(content) - offset < 16:
            raise CaptureParseError("Malformed PCAP: truncated packet header.")
        sec, fraction, captured, original = struct.unpack_from(endian + "IIII", content, offset)
        offset += 16
        if captured > len(content) - offset:
            raise CaptureParseError("Malformed PCAP: truncated packet data.")
        packets.append(CapturePacket(sec + fraction / fraction_scale, captured, original,
                                     content[offset:offset + captured]))
        offset += captured
        if len(packets) > MAX_PACKETS:
            raise CaptureParseError(f"Capture exceeds the {MAX_PACKETS:,}-packet limit.")
    if not packets:
        raise CaptureParseError("The capture contains no packets.")
    return ParsedCapture("pcap", link_type, tuple(packets))


def _parse_pcapng(content: bytes) -> ParsedCapture:
    if len(content) < 28 or content[:4] != b"\x0a\x0d\x0d\x0a":
        raise CaptureParseError("Malformed PCAPNG: missing section header.")
    byte_order = content[8:12]
    if byte_order == b"\x4d\x3c\x2b\x1a":
        endian = "<"
    elif byte_order == b"\x1a\x2b\x3c\x4d":
        endian = ">"
    else:
        raise CaptureParseError("Malformed PCAPNG: invalid byte-order magic.")
    packets, interfaces, offset = [], [], 0
    while offset < len(content):
        if len(content) - offset < 12:
            raise CaptureParseError("Malformed PCAPNG: truncated block header.")
        block_type, total_length = struct.unpack_from(endian + "II", content, offset)
        if total_length < 12 or total_length % 4 or offset + total_length > len(content):
            raise CaptureParseError("Malformed PCAPNG: invalid block length.")
        trailing = struct.unpack_from(endian + "I", content, offset + total_length - 4)[0]
        if trailing != total_length:
            raise CaptureParseError("Malformed PCAPNG: block lengths do not match.")
        body = content[offset + 8:offset + total_length - 4]
        if block_type == 1:  # Interface Description Block
            if len(body) < 8:
                raise CaptureParseError("Malformed PCAPNG: truncated interface block.")
            link_type = struct.unpack_from(endian + "H", body)[0]
            if link_type != 1:
                raise CaptureParseError(
                    f"Unsupported PCAPNG link-layer type {link_type}; Ethernet is required."
                )
            interfaces.append((link_type, 1_000_000))
        elif block_type == 6:  # Enhanced Packet Block
            if len(body) < 20:
                raise CaptureParseError("Malformed PCAPNG: truncated enhanced packet block.")
            interface, high, low, captured, original = struct.unpack_from(endian + "IIIII", body)
            if interface >= len(interfaces):
                raise CaptureParseError("Malformed PCAPNG: packet references an unknown interface.")
            if captured > len(body) - 20:
                raise CaptureParseError("Malformed PCAPNG: truncated packet data.")
            scale = interfaces[interface][1]
            timestamp = ((high << 32) | low) / scale
            packets.append(CapturePacket(timestamp, captured, original, body[20:20 + captured]))
            if len(packets) > MAX_PACKETS:
                raise CaptureParseError(f"Capture exceeds the {MAX_PACKETS:,}-packet limit.")
        offset += total_length
    if not interfaces:
        raise CaptureParseError("Malformed PCAPNG: no interface description.")
    if not packets:
        raise CaptureParseError("The capture contains no packets.")
    return ParsedCapture("pcapng", interfaces[0][0], tuple(packets))


def _decode_transport(packet: CapturePacket):
    data = packet.data
    if len(data) < 14 or struct.unpack_from("!H", data, 12)[0] != 0x0800:
        return None
    ip = data[14:]
    if len(ip) < 20 or ip[0] >> 4 != 4:
        return None
    ihl = (ip[0] & 0x0F) * 4
    total_length = struct.unpack_from("!H", ip, 2)[0]
    protocol = ip[9]
    if len(ip) < ihl or protocol not in (6, 17):
        return None
    src, dst = str(ipaddress.ip_address(ip[12:16])), str(ipaddress.ip_address(ip[16:20]))
    transport = ip[ihl:total_length]
    minimum = 20 if protocol == 6 else 8
    if len(transport) < minimum:
        return None
    src_port, dst_port = struct.unpack_from("!HH", transport)
    transport_header = ((transport[12] >> 4) * 4) if protocol == 6 else 8
    if transport_header < minimum or len(transport) < transport_header:
        return None
    flags = transport[13] if protocol == 6 else 0
    payload_len = max(0, total_length - ihl - transport_header)
    return src, dst, src_port, dst_port, protocol, ihl + transport_header, payload_len, flags


def extract_diagnostic_flows(capture: ParsedCapture) -> pd.DataFrame:
    """Extract an intentionally incomplete set of unambiguous flow facts."""
    flows = OrderedDict()
    for packet in capture.packets:
        decoded = _decode_transport(packet)
        if decoded is None:
            continue
        src, dst, sport, dport, protocol, header_len, payload_len, flags = decoded
        forward = (src, sport, dst, dport)
        reverse = (dst, dport, src, sport)
        key = (protocol, *forward) if (protocol, *reverse) not in flows else (protocol, *reverse)
        if key not in flows:
            flows[key] = {"start": packet.timestamp, "end": packet.timestamp, "dst_port": dport,
                          "payload": [], "headers": [], "fwd": 0, "bwd": 0,
                          "fwd_payload": 0, "bwd_payload": 0, "flags": [0] * 8}
        flow = flows[key]
        is_forward = key[1:] == forward
        flow["end"] = packet.timestamp
        flow["payload"].append(payload_len)
        flow["headers"].append(header_len)
        flow["fwd" if is_forward else "bwd"] += 1
        flow["fwd_payload" if is_forward else "bwd_payload"] += payload_len
        for bit in range(8):
            flow["flags"][bit] += int(bool(flags & (1 << bit)))
    rows = []
    for flow in flows.values():
        rows.append({
            "dst_port": flow["dst_port"], "duration": flow["end"] - flow["start"],
            "packets_count": len(flow["payload"]), "fwd_packets_count": flow["fwd"],
            "bwd_packets_count": flow["bwd"], "total_payload_bytes": sum(flow["payload"]),
            "fwd_total_payload_bytes": flow["fwd_payload"],
            "bwd_total_payload_bytes": flow["bwd_payload"],
            "payload_bytes_max": max(flow["payload"]), "payload_bytes_min": min(flow["payload"]),
            "payload_bytes_mean": sum(flow["payload"]) / len(flow["payload"]),
            "total_header_bytes": sum(flow["headers"]),
            "fin_flag_counts": flow["flags"][0], "syn_flag_counts": flow["flags"][1],
            "rst_flag_counts": flow["flags"][2], "psh_flag_counts": flow["flags"][3],
            "ack_flag_counts": flow["flags"][4], "urg_flag_counts": flow["flags"][5],
            "ece_flag_counts": flow["flags"][6], "cwr_flag_counts": flow["flags"][7],
        })
    if not rows:
        raise CaptureParseError("The capture contains zero usable IPv4 TCP/UDP flows.")
    return pd.DataFrame(rows)
