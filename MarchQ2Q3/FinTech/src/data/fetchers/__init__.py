"""Data fetcher factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import get_settings

if TYPE_CHECKING:
    from src.data.fetchers.base import BaseFetcher


def get_fetcher() -> BaseFetcher:
    """Return the appropriate fetcher based on DATA_SOURCE config."""
    settings = get_settings()
    if settings.DATA_SOURCE == "live":
        from src.data.fetchers.live_fetcher import LiveFetcher  # noqa: PLC0415

        return LiveFetcher()

    from src.data.fetchers.mock_fetcher import MockFetcher  # noqa: PLC0415

    return MockFetcher()
