"""WebSocket endpoints for real-time trade streaming.

Reads from Kafka trades topic and pushes to connected clients.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from src.common.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket, request: Request) -> None:
    """Stream raw trade events from Kafka to WebSocket clients.

    Connects to the Kafka streamer and broadcasts all trade events
    to the connected client in real-time.
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info("WebSocket client connected", client_id=client_id)

    streamer = request.app.state.kafka_streamer

    # Subscribe to all trades
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    await streamer.subscribe(client_id, queue)

    try:
        while True:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
    finally:
        await streamer.unsubscribe(client_id)


@router.websocket("/ws/trades/{symbol}")
async def websocket_trades_by_symbol(
    websocket: WebSocket,
    symbol: str,
    request: Request,
) -> None:
    """Stream trade events for a specific symbol.

    Filters the Kafka stream to only send trades matching the requested symbol.
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info(
        "WebSocket client connected for symbol",
        client_id=client_id,
        symbol=symbol,
    )

    streamer = request.app.state.kafka_streamer

    # Subscribe with symbol filter
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    await streamer.subscribe(client_id, queue, symbol_filter=symbol)

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
    finally:
        await streamer.unsubscribe(client_id)


@router.websocket("/ws/aggregates")
async def websocket_aggregates(websocket: WebSocket, request: Request) -> None:
    """Stream completed aggregates to WebSocket clients.

    Broadcasts completed 1-minute window aggregates as they are computed.
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info("WebSocket client connected for aggregates", client_id=client_id)

    streamer = request.app.state.kafka_streamer

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    await streamer.subscribe_aggregates(client_id, queue)

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
    finally:
        await streamer.unsubscribe_aggregates(client_id)
