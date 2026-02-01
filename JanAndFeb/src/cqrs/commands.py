"""CQRS Commands - Actions that change system state.

Commands represent intentions to change the system. They are validated,
processed by handlers, and result in domain events being published.

In the energy trading platform:
- SubmitTradeCommand: Submit a new trade for processing
- CancelTradeCommand: Cancel a pending trade (future)
- AdjustTradeCommand: Modify trade details (future)

Commands flow: API/Producer → CommandBus → Handler → Kafka (events)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable, TypeVar
from uuid import UUID, uuid4

import structlog

from src.common.models import TradeSide, TradeEvent

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound="Command")


@dataclass
class Command(ABC):
    """Base class for all commands.

    Commands are immutable value objects that represent an intention
    to change the system state.

    Attributes:
        command_id: Unique identifier for this command
        timestamp: When the command was created
        correlation_id: Optional ID to correlate related commands/events
    """

    command_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None

    @abstractmethod
    def validate(self) -> list[str]:
        """Validate the command.

        Returns:
            List of validation error messages (empty if valid)
        """
        pass


@dataclass
class SubmitTradeCommand(Command):
    """Command to submit a new trade event.

    This command is the entry point for trade data. It can come from:
    - External APIs (Finnhub, DexPaprika, ENTSO-E)
    - Synthetic producer
    - Batch file imports
    - Manual entry

    The handler validates the command, creates a TradeEvent, and
    publishes it to Kafka.
    """

    symbol: str = ""
    price: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    side: TradeSide = TradeSide.BUY
    trader_id: str = ""
    event_timestamp: datetime | None = None
    source: str = "unknown"

    def validate(self) -> list[str]:
        """Validate trade submission parameters."""
        errors = []

        if not self.symbol:
            errors.append("Symbol is required")
        elif len(self.symbol) > 20:
            errors.append("Symbol must be 20 characters or less")

        if self.price < Decimal("0"):
            errors.append("Price cannot be negative")

        if self.volume <= Decimal("0"):
            errors.append("Volume must be positive")

        if not self.trader_id:
            errors.append("Trader ID is required")

        return errors

    def to_trade_event(self) -> TradeEvent:
        """Convert command to TradeEvent for Kafka publication."""
        return TradeEvent(
            trade_id=uuid4(),
            symbol=self.symbol.upper(),
            price=self.price,
            volume=self.volume,
            side=self.side,
            trader_id=self.trader_id,
            event_timestamp=self.event_timestamp or datetime.now(UTC),
        )


@dataclass
class CancelTradeCommand(Command):
    """Command to cancel a trade (future implementation).

    In real trading systems, cancellation is complex:
    - May require the trade to be in a cancellable state
    - May need approval workflows
    - Must maintain audit trail
    """

    trade_id: UUID = field(default_factory=uuid4)
    reason: str = ""
    cancelled_by: str = ""

    def validate(self) -> list[str]:
        """Validate cancellation parameters."""
        errors = []
        if not self.reason:
            errors.append("Cancellation reason is required")
        if not self.cancelled_by:
            errors.append("Cancelled by (user ID) is required")
        return errors


# Type alias for command handlers
CommandHandler = Callable[[Command], Any]


class CommandBus:
    """Dispatches commands to their handlers.

    The CommandBus is the central point for command processing:
    1. Receives a command
    2. Validates it
    3. Finds the appropriate handler
    4. Executes the handler
    5. Returns the result or raises an error

    Example:
        >>> bus = CommandBus()
        >>> bus.register(SubmitTradeCommand, trade_handler)
        >>> result = await bus.execute(SubmitTradeCommand(symbol="AAPL", ...))
    """

    def __init__(self):
        """Initialize the command bus."""
        self._handlers: dict[type[Command], CommandHandler] = {}

    def register(
        self,
        command_type: type[T],
        handler: Callable[[T], Any],
    ) -> None:
        """Register a handler for a command type.

        Args:
            command_type: The command class to handle
            handler: Function that processes commands of this type
        """
        self._handlers[command_type] = handler
        logger.info(
            "Registered command handler",
            command_type=command_type.__name__,
        )

    def execute(self, command: Command) -> Any:
        """Execute a command through its handler.

        Args:
            command: The command to execute

        Returns:
            Result from the handler

        Raises:
            ValueError: If command validation fails
            KeyError: If no handler is registered for the command type
        """
        # Validate command
        errors = command.validate()
        if errors:
            logger.warning(
                "Command validation failed",
                command_type=type(command).__name__,
                command_id=str(command.command_id),
                errors=errors,
            )
            raise ValueError(f"Command validation failed: {', '.join(errors)}")

        # Find handler
        handler = self._handlers.get(type(command))
        if not handler:
            raise KeyError(
                f"No handler registered for command type: {type(command).__name__}"
            )

        # Execute
        logger.info(
            "Executing command",
            command_type=type(command).__name__,
            command_id=str(command.command_id),
            correlation_id=str(command.correlation_id) if command.correlation_id else None,
        )

        result = handler(command)

        logger.info(
            "Command executed successfully",
            command_type=type(command).__name__,
            command_id=str(command.command_id),
        )

        return result

    async def execute_async(self, command: Command) -> Any:
        """Execute a command asynchronously.

        Same as execute() but for async handlers.
        """
        import asyncio

        errors = command.validate()
        if errors:
            raise ValueError(f"Command validation failed: {', '.join(errors)}")

        handler = self._handlers.get(type(command))
        if not handler:
            raise KeyError(
                f"No handler registered for command type: {type(command).__name__}"
            )

        if asyncio.iscoroutinefunction(handler):
            return await handler(command)
        return handler(command)
