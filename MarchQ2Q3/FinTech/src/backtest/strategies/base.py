"""Base strategy interface for the backtest engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from src.backtest.models import Position


class BaseStrategy(ABC):
    """Abstract base class for backtest strategies."""

    @abstractmethod
    def generate_signals(
        self,
        current_date: date,
        spot: float,
        iv: float,
        features: dict | None = None,
    ) -> list[Position]:
        """Generate new position signals for the current date.

        Returns a list of Position objects to open (may be empty).
        """

    @abstractmethod
    def should_exit(
        self,
        position: Position,
        current_date: date,
        spot: float,
        iv: float,
    ) -> str | None:
        """Check if a position should be exited.

        Returns exit reason string if should exit, None otherwise.
        """
