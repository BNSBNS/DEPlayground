"""Project configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class NetworkSecuritySettings(BaseSettings):
    """Runtime configuration for the network security monitor."""

    # Alert storage
    db_path: str = "alerts.db"

    # Detection thresholds
    port_scan_threshold: int = 20  # unique ports within window
    port_scan_window_s: int = 60
    brute_force_threshold: int = 10  # failed connections within window
    brute_force_window_s: int = 300  # 5 minutes
    dns_exfil_subdomain_len: int = 30
    dns_exfil_entropy_threshold: float = 4.0
    dns_exfil_volume_per_min: int = 100
    beacon_min_count: int = 10  # minimum intervals to classify as beacon
    beacon_regularity_threshold: float = 0.15  # std_dev/mean

    # API
    api_port: int = 8003

    model_config = {"env_prefix": "NS_", "env_file": ".env", "extra": "ignore"}
