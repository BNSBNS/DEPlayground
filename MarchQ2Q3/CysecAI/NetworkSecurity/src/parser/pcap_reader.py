"""Read PCAP files and produce PacketRecord objects via dpkt.

This module is excluded from mypy checking (dpkt has no stubs).
It is also excluded from coverage measurement (requires real PCAP files).
"""

from __future__ import annotations

import base64
import pathlib
import socket
import struct

import dpkt  # type: ignore[import-untyped]

from src.models import PacketRecord, Protocol, TCPFlags

# ── TCP flag bit masks ────────────────────────────────────────────────────────

_TCP_FIN = 0x01
_TCP_SYN = 0x02
_TCP_RST = 0x04
_TCP_PSH = 0x08
_TCP_ACK = 0x10
_TCP_URG = 0x20


def _decode_tcp_flags(flags: int) -> TCPFlags | None:
    if flags & _TCP_FIN and flags & _TCP_PSH and flags & _TCP_URG:
        return TCPFlags.XMAS
    if flags & _TCP_SYN and flags & _TCP_ACK:
        return TCPFlags.SYN_ACK
    if flags & _TCP_FIN and flags & _TCP_ACK:
        return TCPFlags.FIN_ACK
    if flags & _TCP_PSH and flags & _TCP_ACK:
        return TCPFlags.PSH_ACK
    if flags & _TCP_SYN:
        return TCPFlags.SYN
    if flags & _TCP_FIN:
        return TCPFlags.FIN
    if flags & _TCP_RST:
        return TCPFlags.RST
    if flags & _TCP_ACK:
        return TCPFlags.ACK
    return None


def _safe_ip(raw: bytes) -> str:
    try:
        return socket.inet_ntop(socket.AF_INET, raw)
    except Exception:
        return "0.0.0.0"


def _parse_http(payload: bytes) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (method, url, host, auth_header_redacted)."""
    try:
        text = payload.decode("utf-8", errors="replace")
        lines = text.split("\r\n")
        first = lines[0].split()
        if len(first) < 2 or first[0] not in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}:
            return None, None, None, None
        method = first[0]
        url = first[1]
        host: str | None = None
        auth: str | None = None
        for line in lines[1:]:
            low = line.lower()
            if low.startswith("host:"):
                host = line.split(":", 1)[1].strip()
            if low.startswith("authorization: basic "):
                # Redact — just note that Basic auth was present
                try:
                    decoded = base64.b64decode(line.split(" ", 2)[-1]).decode()
                    user = decoded.split(":")[0]
                    auth = f"Basic {user}:[REDACTED]"
                except Exception:
                    auth = "Basic [REDACTED]"
        return method, url, host, auth
    except Exception:
        return None, None, None, None


def _parse_ftp(payload: bytes) -> tuple[str | None, str | None]:
    """Return (command, redacted_arg)."""
    try:
        line = payload.decode("utf-8", errors="replace").strip()
        parts = line.split(" ", 1)
        cmd = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else None
        if cmd == "PASS":
            arg = "[REDACTED]"
        return cmd, arg
    except Exception:
        return None, None


def read_pcap(path: str | pathlib.Path) -> list[PacketRecord]:
    """Read a PCAP file and return normalised PacketRecord objects."""
    records: list[PacketRecord] = []
    pcap_path = pathlib.Path(path)
    with pcap_path.open("rb") as f:
        try:
            capture = dpkt.pcap.Reader(f)
        except Exception:
            return records
        for ts, buf in capture:
            try:
                eth = dpkt.ethernet.Ethernet(buf)
            except Exception:
                continue
            if not isinstance(eth.data, dpkt.ip.IP):
                # Handle ARP at Ethernet layer
                if isinstance(eth.data, dpkt.arp.ARP):
                    arp = eth.data
                    records.append(
                        PacketRecord(
                            timestamp=float(ts),
                            src_ip=_safe_ip(arp.spa),
                            dst_ip=_safe_ip(arp.tpa),
                            protocol=Protocol.ARP,
                            arp_sender_mac=":".join(f"{b:02x}" for b in arp.sha),
                            arp_sender_ip=_safe_ip(arp.spa),
                            arp_target_mac=":".join(f"{b:02x}" for b in arp.tha),
                        )
                    )
                continue
            ip = eth.data
            src_ip = _safe_ip(ip.src)
            dst_ip = _safe_ip(ip.dst)
            if isinstance(ip.data, dpkt.tcp.TCP):
                tcp = ip.data
                payload = bytes(tcp.data) if tcp.data else b""
                flags = _decode_tcp_flags(tcp.flags)
                # HTTP detection
                method = url = host = auth = None
                proto = Protocol.TCP
                ftp_cmd = ftp_arg = None
                if tcp.dport == 80 or tcp.sport == 80:
                    method, url, host, auth = _parse_http(payload)
                    if method:
                        proto = Protocol.HTTP
                elif tcp.dport == 21 or tcp.sport == 21:
                    ftp_cmd, ftp_arg = _parse_ftp(payload)
                    proto = Protocol.FTP
                elif tcp.dport == 23 or tcp.sport == 23:
                    proto = Protocol.TELNET
                elif tcp.dport == 22 or tcp.sport == 22:
                    proto = Protocol.SSH
                records.append(
                    PacketRecord(
                        timestamp=float(ts),
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=int(tcp.sport),
                        dst_port=int(tcp.dport),
                        protocol=proto,
                        tcp_flags=flags,
                        payload_size=len(payload),
                        http_method=method,
                        http_url=url,
                        http_host=host,
                        http_auth_header=auth,
                        ftp_command=ftp_cmd,
                        ftp_arg=ftp_arg,
                    )
                )
            elif isinstance(ip.data, dpkt.udp.UDP):
                udp = ip.data
                payload = bytes(udp.data) if udp.data else b""
                proto = Protocol.UDP
                dns_query = dns_response = None
                if udp.dport == 53 or udp.sport == 53:
                    proto = Protocol.DNS
                    try:
                        dns = dpkt.dns.DNS(payload)
                        if dns.qd:
                            dns_query = dns.qd[0].name
                        if dns.an:
                            dns_response = str(dns.an[0].name)
                    except Exception:
                        pass
                records.append(
                    PacketRecord(
                        timestamp=float(ts),
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=int(udp.sport),
                        dst_port=int(udp.dport),
                        protocol=proto,
                        payload_size=len(payload),
                        dns_query=dns_query,
                        dns_response=dns_response,
                    )
                )
            elif isinstance(ip.data, dpkt.icmp.ICMP):
                records.append(
                    PacketRecord(
                        timestamp=float(ts),
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        protocol=Protocol.ICMP,
                        payload_size=len(bytes(ip.data)),
                    )
                )
    return records


def write_minimal_pcap(records: list[PacketRecord], path: str | pathlib.Path) -> None:
    """Write a minimal valid PCAP from PacketRecord objects (for test data)."""
    # PCAP global header: magic, ver_major, ver_minor, thiszone, sigfigs, snaplen, network
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        f.write(header)
        for rec in records:
            # Build a minimal Ethernet + IP + TCP packet (for TCP records)
            ts = rec.timestamp
            ts_sec = int(ts)
            ts_usec = int((ts - ts_sec) * 1_000_000)
            # Minimal 42-byte Ethernet+IP+TCP skeleton
            eth_bytes = b"\xff" * 6 + b"\x00" * 6 + b"\x08\x00"  # Ethernet header
            try:
                src = socket.inet_aton(rec.src_ip)
                dst = socket.inet_aton(rec.dst_ip)
            except OSError:
                src = dst = b"\x7f\x00\x00\x01"
            sport = rec.src_port or 0
            dport = rec.dst_port or 0
            ip_payload = struct.pack(">HHBBBBH4s4s", sport, dport, 0, 0, 0, 0, 0, b"", b"")
            ip_bytes = (
                struct.pack(
                    ">BBHHHBBH4s4s", 0x45, 0, 40 + len(ip_payload), 0, 0, 64, 6, 0, src, dst
                )
                + ip_payload
            )
            frame = eth_bytes + ip_bytes
            pkt_hdr = struct.pack("<IIII", ts_sec, ts_usec, len(frame), len(frame))
            f.write(pkt_hdr + frame)
