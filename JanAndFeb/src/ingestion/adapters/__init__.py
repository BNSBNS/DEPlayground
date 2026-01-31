"""Adapters layer (Hexagonal Architecture).

This layer contains concrete implementations of the ports:
- Driving Adapters (connectors/): How data enters the system
- Data Format Adapters (formats/): Transform external formats
- Driven Adapters (publishers/): How data leaves the system
- Infrastructure Adapters (infrastructure/): Metrics, logging, etc.
"""
