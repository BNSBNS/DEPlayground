"""Generate synthetic network traffic fixtures as JSON PacketRecord files."""

from __future__ import annotations

import json
import pathlib
import random
import time

# Base timestamp: 2026-01-01 00:00:00 UTC
_BASE_TS = 1735689600.0
_OUT = pathlib.Path(__file__).parent


def _pkt(
    src_ip: str,
    dst_ip: str,
    protocol: str = "TCP",
    **kwargs: object,
) -> dict[str, object]:
    return {
        "timestamp": _BASE_TS,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "protocol": protocol,
        **kwargs,
    }


def generate_normal_traffic(seed: int = 42) -> list[dict[str, object]]:
    """Normal HTTP + DNS traffic — no attack patterns."""
    rng = random.Random(seed)
    packets: list[dict[str, object]] = []
    for i in range(50):
        ts = _BASE_TS + i * 10
        src = f"10.0.0.{rng.randint(1, 20)}"
        dst = f"93.184.{rng.randint(1, 200)}.{rng.randint(1, 200)}"
        packets.append({
            "timestamp": ts,
            "src_ip": src,
            "dst_ip": dst,
            "src_port": rng.randint(49152, 65535),
            "dst_port": 80,
            "protocol": "HTTP",
            "tcp_flags": "PSH-ACK",
            "payload_size": rng.randint(100, 1500),
            "http_method": rng.choice(["GET", "POST"]),
            "http_url": f"/api/resource/{rng.randint(1, 100)}",
            "http_host": dst,
        })
        # DNS query
        packets.append({
            "timestamp": ts + 0.1,
            "src_ip": src,
            "dst_ip": "8.8.8.8",
            "src_port": rng.randint(49152, 65535),
            "dst_port": 53,
            "protocol": "DNS",
            "payload_size": 40,
            "dns_query": f"www.example{rng.randint(1, 5)}.com",
        })
    return packets


def generate_port_scan(src_ip: str = "192.168.1.99", target: str = "10.0.0.1") -> list[dict[str, object]]:
    """SYN scan of 100 ports from a single source."""
    packets: list[dict[str, object]] = []
    ts = _BASE_TS
    for port in range(1, 101):
        packets.append({
            "timestamp": ts + port * 0.1,
            "src_ip": src_ip,
            "dst_ip": target,
            "src_port": 54321,
            "dst_port": port,
            "protocol": "TCP",
            "tcp_flags": "SYN",
            "payload_size": 0,
        })
    return packets


def generate_brute_force(src_ip: str = "203.0.113.5", target: str = "10.0.0.2") -> list[dict[str, object]]:
    """50 failed SSH connections (RST responses)."""
    packets: list[dict[str, object]] = []
    ts = _BASE_TS
    for i in range(50):
        packets.append({
            "timestamp": ts + i * 4,
            "src_ip": src_ip,
            "dst_ip": target,
            "src_port": 50000 + i,
            "dst_port": 22,
            "protocol": "SSH",
            "tcp_flags": "RST",
            "payload_size": 0,
        })
    return packets


def generate_dns_exfil(src_ip: str = "10.0.0.5", resolver: str = "8.8.8.8") -> list[dict[str, object]]:
    """DNS queries with long encoded subdomains (exfiltration pattern)."""
    # High-entropy subdomains > 30 chars
    encoded_chunks = [
        "aGVsbG93b3JsZGhlbGxvd29ybGQxMjM",  # 32 chars, base64-like
        "dGhpc2lzYXNlY3JldG1lc3NhZ2VoZXJl",  # 34 chars
        "c2Vuc2l0aXZlZGF0YWV4ZmlsdHJhdGlvbg",  # 35 chars
    ]
    packets: list[dict[str, object]] = []
    ts = _BASE_TS
    for i, chunk in enumerate(encoded_chunks):
        packets.append({
            "timestamp": ts + i * 2,
            "src_ip": src_ip,
            "dst_ip": resolver,
            "src_port": 49000 + i,
            "dst_port": 53,
            "protocol": "DNS",
            "payload_size": len(chunk) + 10,
            "dns_query": f"{chunk}.attacker-c2.example.com",
        })
    return packets


def generate_beaconing(src_ip: str = "10.0.0.10", c2: str = "198.51.100.1") -> list[dict[str, object]]:
    """Periodic SYN connections every ~60 seconds (±2s jitter)."""
    packets: list[dict[str, object]] = []
    rng = random.Random(99)
    ts = _BASE_TS
    for i in range(12):
        jitter = rng.uniform(-2, 2)
        packets.append({
            "timestamp": ts + i * 60 + jitter,
            "src_ip": src_ip,
            "dst_ip": c2,
            "src_port": rng.randint(49152, 65535),
            "dst_port": 443,
            "protocol": "TCP",
            "tcp_flags": "SYN",
            "payload_size": 0,
        })
    return packets


def generate_arp_spoof(victim_ip: str = "10.0.0.1") -> list[dict[str, object]]:
    """ARP packets showing same IP claimed by two different MACs."""
    return [
        {
            "timestamp": _BASE_TS,
            "src_ip": victim_ip,
            "dst_ip": "10.0.0.255",
            "protocol": "ARP",
            "arp_sender_mac": "aa:bb:cc:dd:ee:ff",
            "arp_sender_ip": victim_ip,
        },
        {
            "timestamp": _BASE_TS + 1,
            "src_ip": victim_ip,
            "dst_ip": "10.0.0.255",
            "protocol": "ARP",
            "arp_sender_mac": "11:22:33:44:55:66",  # different MAC, same IP
            "arp_sender_ip": victim_ip,
        },
    ]


def generate_cleartext_creds() -> list[dict[str, object]]:
    """HTTP Basic auth and FTP PASS commands in cleartext."""
    return [
        {
            "timestamp": _BASE_TS,
            "src_ip": "10.0.0.20",
            "dst_ip": "10.0.0.100",
            "src_port": 54321,
            "dst_port": 80,
            "protocol": "HTTP",
            "tcp_flags": "PSH-ACK",
            "payload_size": 200,
            "http_method": "GET",
            "http_url": "/admin",
            "http_host": "10.0.0.100",
            "http_auth_header": "Basic admin:[REDACTED]",
        },
        {
            "timestamp": _BASE_TS + 1,
            "src_ip": "10.0.0.21",
            "dst_ip": "10.0.0.101",
            "src_port": 54322,
            "dst_port": 21,
            "protocol": "FTP",
            "tcp_flags": "PSH-ACK",
            "payload_size": 20,
            "ftp_command": "PASS",
            "ftp_arg": "[REDACTED]",
        },
    ]


def main() -> None:
    fixtures = {
        "normal_traffic.json": generate_normal_traffic(),
        "port_scan.json": generate_port_scan(),
        "brute_force.json": generate_brute_force(),
        "dns_exfil.json": generate_dns_exfil(),
        "beaconing.json": generate_beaconing(),
        "arp_spoof.json": generate_arp_spoof(),
        "cleartext_creds.json": generate_cleartext_creds(),
    }
    for filename, data in fixtures.items():
        out = _OUT / filename
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Written {len(data)} records → {out}")


if __name__ == "__main__":
    main()
