from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.broadcast import events_manager, sales_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sales")
async def ws_sales(websocket: WebSocket) -> None:
    """WebSocket endpoint for live sales aggregation updates."""
    await sales_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        sales_manager.disconnect(websocket)


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """WebSocket endpoint for live raw event stream."""
    await events_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        events_manager.disconnect(websocket)
