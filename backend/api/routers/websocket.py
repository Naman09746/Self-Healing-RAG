"""
WebSocket router with JWT authentication (Phase 6).

WebSocket connections are authenticated using a JWT token passed as a query
parameter (?token=...). Connections with invalid or missing tokens are rejected.

Security events are logged to the audit log.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from backend.core.logging import get_logger
from backend.core.security import decode_access_token
from backend.core.audit import log_rbac_denied

logger = get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages authenticated WebSocket connections keyed by session_id."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_map: Dict[str, str] = {}  # session_id -> user_uuid

    async def connect(
        self, session_id: str, websocket: WebSocket, user_uuid: str
    ) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.user_map[session_id] = user_uuid
        logger.info(
            "WebSocket connected",
            session_id=session_id,
            user_uuid=user_uuid,
        )

    def disconnect(self, session_id: str) -> None:
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        self.user_map.pop(session_id, None)
        logger.info("WebSocket disconnected", session_id=session_id)

    async def send_event(self, session_id: str, event: Dict[str, Any]) -> None:
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(json.dumps(event))
            except Exception as e:
                logger.error(
                    "Failed to send WS event",
                    session_id=session_id,
                    error=str(e),
                )
                self.disconnect(session_id)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    # --- Authenticate ---
    if not token:
        logger.warn("WebSocket connection rejected: missing token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_uuid = payload.get("user_uuid")
        if not user_uuid:
            logger.warn("WebSocket connection rejected: no user_uuid in token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception as e:
        logger.warn("WebSocket connection rejected: invalid token", error=str(e))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # --- Accept connection ---
    await manager.connect(session_id, websocket, user_uuid)

    try:
        while True:
            data = await websocket.receive_text()

            # Handle ping/pong keep-alive
            if data == "ping":
                await websocket.send_text("pong")
                continue

            # Handle client messages (future extensibility)
            # Messages are acknowledged but not processed at this layer.
            logger.debug(
                "WebSocket message received",
                session_id=session_id,
                data_preview=data[:200],
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(
            "WebSocket error",
            session_id=session_id,
            error=str(e),
        )
        manager.disconnect(session_id)