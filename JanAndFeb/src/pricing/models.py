"""Pricing models for LMP/LBMP calculations.

Location Marginal Pricing (LMP) represents the cost of delivering one additional
unit of energy to a specific location on the grid. It consists of:
- Energy Component: System-wide energy cost
- Congestion Component: Cost due to transmission constraints
- Loss Component: Cost due to electrical losses

In energy markets:
- PJM, NYISO, ISO-NE use LMP/LBMP
- ERCOT uses LMP
- European markets (EPEX, Nord Pool) use zonal pricing (simplified LMP)
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class LMPComponents:
    """Breakdown of Location Marginal Price components.

    LMP = Energy + Congestion + Loss

    Attributes:
        energy: Base energy cost (system marginal price)
        congestion: Cost due to transmission constraints
        loss: Cost due to electrical losses on transmission
        total: Total LMP (sum of components)
    """

    energy: Decimal
    congestion: Decimal
    loss: Decimal

    @property
    def total(self) -> Decimal:
        """Calculate total LMP from components."""
        return (self.energy + self.congestion + self.loss).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary with string values for JSON serialization."""
        return {
            "energy": str(self.energy),
            "congestion": str(self.congestion),
            "loss": str(self.loss),
            "total": str(self.total),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LMPComponents":
        """Create from dictionary."""
        return cls(
            energy=Decimal(str(data["energy"])),
            congestion=Decimal(str(data["congestion"])),
            loss=Decimal(str(data["loss"])),
        )

    @classmethod
    def zero(cls) -> "LMPComponents":
        """Create zero-valued components."""
        return cls(
            energy=Decimal("0"),
            congestion=Decimal("0"),
            loss=Decimal("0"),
        )


class PricingNode(BaseModel):
    """Configuration for a pricing node/location.

    Each node has characteristics that affect LMP calculations:
    - Loss factor: Higher for nodes far from generation
    - Congestion sensitivity: How much congestion affects price
    - Zone: Bidding zone for zonal pricing markets

    Example nodes:
    - POWER_DE: German power market (DE-LU zone)
    - POWER_FR: French power market
    - POWER_NL: Dutch power market
    """

    node_id: str = Field(description="Unique identifier (e.g., POWER_DE)")
    zone: str = Field(description="Bidding zone (e.g., DE-LU, FR, NL)")
    name: str = Field(default="", description="Human-readable name")

    # Loss factors (typically 0.01 - 0.05 for distribution, 0.02-0.10 for long distance)
    base_loss_factor: Decimal = Field(
        default=Decimal("0.02"),
        ge=Decimal("0"),
        le=Decimal("0.20"),
        description="Base marginal loss factor (2% typical)",
    )

    # Congestion sensitivity (0 = no congestion, 1 = highly constrained)
    congestion_sensitivity: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        description="How sensitive this node is to congestion",
    )

    # Reference node indicator (reference node has zero congestion by definition)
    is_reference_node: bool = Field(
        default=False,
        description="True if this is the reference/slack node",
    )

    # Typical congestion adder for this node (historical average)
    typical_congestion_adder: Decimal = Field(
        default=Decimal("0"),
        description="Historical average congestion component",
    )

    class Config:
        """Pydantic configuration."""

        str_strip_whitespace = True


class PricingNodeRegistry:
    """Registry of pricing nodes with default configurations.

    This provides default configurations for common energy market nodes.
    In production, these would be loaded from a database or configuration file.
    """

    # Default nodes for common markets
    DEFAULT_NODES: dict[str, dict[str, Any]] = {
        # European Energy Markets
        "POWER_DE": {
            "zone": "DE-LU",
            "name": "Germany-Luxembourg",
            "base_loss_factor": "0.02",
            "congestion_sensitivity": "0.05",
            "typical_congestion_adder": "1.50",
        },
        "POWER_FR": {
            "zone": "FR",
            "name": "France",
            "base_loss_factor": "0.025",
            "congestion_sensitivity": "0.08",
            "typical_congestion_adder": "2.00",
        },
        "POWER_NL": {
            "zone": "NL",
            "name": "Netherlands",
            "base_loss_factor": "0.015",
            "congestion_sensitivity": "0.03",
            "typical_congestion_adder": "0.75",
        },
        "GAS_NL": {
            "zone": "TTF",
            "name": "Title Transfer Facility (Dutch Gas Hub)",
            "base_loss_factor": "0.01",
            "congestion_sensitivity": "0.02",
            "typical_congestion_adder": "0.25",
        },
        # US Energy Markets (for reference)
        "POWER_PJM": {
            "zone": "PJM",
            "name": "PJM Interconnection",
            "base_loss_factor": "0.03",
            "congestion_sensitivity": "0.10",
            "typical_congestion_adder": "5.00",
        },
        # Crypto/Stock symbols (no LMP, use defaults)
        "AAPL": {
            "zone": "NASDAQ",
            "name": "Apple Inc.",
            "base_loss_factor": "0",
            "congestion_sensitivity": "0",
            "typical_congestion_adder": "0",
        },
        "BTC": {
            "zone": "CRYPTO",
            "name": "Bitcoin",
            "base_loss_factor": "0",
            "congestion_sensitivity": "0",
            "typical_congestion_adder": "0",
        },
    }

    _nodes: dict[str, PricingNode] = {}

    @classmethod
    def get_node(cls, node_id: str) -> PricingNode:
        """Get a pricing node by ID, creating default if not found.

        Args:
            node_id: Node identifier (e.g., POWER_DE)

        Returns:
            PricingNode configuration
        """
        if node_id in cls._nodes:
            return cls._nodes[node_id]

        # Check defaults
        if node_id in cls.DEFAULT_NODES:
            config = cls.DEFAULT_NODES[node_id]
            node = PricingNode(node_id=node_id, **config)
        else:
            # Create generic node with conservative defaults
            node = PricingNode(
                node_id=node_id,
                zone="UNKNOWN",
                name=f"Unknown Node: {node_id}",
                base_loss_factor=Decimal("0.02"),
                congestion_sensitivity=Decimal("0.05"),
            )

        cls._nodes[node_id] = node
        return node

    @classmethod
    def register_node(cls, node: PricingNode) -> None:
        """Register a custom pricing node.

        Args:
            node: PricingNode configuration to register
        """
        cls._nodes[node.node_id] = node

    @classmethod
    def list_nodes(cls) -> list[str]:
        """List all registered node IDs."""
        return list(set(cls._nodes.keys()) | set(cls.DEFAULT_NODES.keys()))
