"""Small deterministic packet-capture fixtures built without external tools."""
import ipaddress
import struct


def ethernet_ipv4_udp(src, dst, sport, dport, payload=b"data"):
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    ip = bytearray(20)
    ip[0], ip[8], ip[9] = 0x45, 64, 17
    struct.pack_into("!H", ip, 2, 20 + len(udp))
    ip[12:16], ip[16:20] = ipaddress.ip_address(src).packed, ipaddress.ip_address(dst).packed
    ethernet = b"\x00" * 12 + struct.pack("!H", 0x0800)
    return ethernet + bytes(ip) + udp


def pcap_bytes(packets):
    output = bytearray(b"\xd4\xc3\xb2\xa1" + struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1))
    for timestamp, packet in packets:
        sec, usec = int(timestamp), round((timestamp - int(timestamp)) * 1_000_000)
        output += struct.pack("<IIII", sec, usec, len(packet), len(packet)) + packet
    return bytes(output)


def _block(block_type, body):
    padding = b"\x00" * ((-len(body)) % 4)
    total = 12 + len(body) + len(padding)
    return struct.pack("<II", block_type, total) + body + padding + struct.pack("<I", total)


def pcapng_bytes(packets):
    shb = _block(0x0A0D0D0A, b"\x4d\x3c\x2b\x1a" + struct.pack("<HHq", 1, 0, -1))
    idb = _block(1, struct.pack("<HHI", 1, 0, 65535))
    epbs = []
    for timestamp, packet in packets:
        ticks = round(timestamp * 1_000_000)
        body = struct.pack("<IIIII", 0, ticks >> 32, ticks & 0xFFFFFFFF,
                           len(packet), len(packet)) + packet
        epbs.append(_block(6, body))
    return shb + idb + b"".join(epbs)


def two_way_udp_packets():
    return [
        (1.0, ethernet_ipv4_udp("10.0.0.1", "10.0.0.2", 50000, 53, b"abc")),
        (1.25, ethernet_ipv4_udp("10.0.0.2", "10.0.0.1", 53, 50000, b"reply")),
    ]
