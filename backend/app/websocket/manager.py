"""Centralized WebSocket connection manager with authentication, RBAC dispatch, and thread-safety."""
import asyncio
import logging
from typing import Dict, Set, Optional, Union, Any, List
from fastapi import WebSocket, WebSocketDisconnect

from backend.app.schemas.user import UserResponse, UserRole
from backend.app.websocket.alerts import (
    create_connected_event,
    create_ping_event,
    WebSocketEventType,
)
from backend.app.core.config import settings

logger = logging.getLogger("websocket_manager")


class ConnectionManager:
    """Manages active authenticated WebSocket connections, heartbeats, and broadcasting."""

    def __init__(self) -> None:
        # Mapping from WebSocket connection to authenticated UserResponse
        self._active_connections: Dict[WebSocket, UserResponse] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Sets the application's primary async event loop for threadsafe dispatching."""
        self._loop = loop

    @property
    def active_count(self) -> int:
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket, user: UserResponse) -> None:
        """Registers a new authenticated client connection and transmits the initial CONNECTED event."""
        await websocket.accept()
        async with self._lock:
            self._active_connections[websocket] = user
        logger.info(
            "WebSocket client connected: user_id=%s, username=%s, role=%s (Total active: %d)",
            user.id,
            user.username,
            user.role.value if hasattr(user.role, "value") else user.role,
            self.active_count,
        )

        # Transmit initial handshake confirmation event
        handshake = create_connected_event(user)
        await self.send_personal_message(websocket, handshake)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Cleans up a disconnected client."""
        user = None
        async with self._lock:
            if websocket in self._active_connections:
                user = self._active_connections.pop(websocket)

        if user:
            logger.info(
                "WebSocket client disconnected: user_id=%s (Remaining active: %d)",
                user.id,
                self.active_count,
            )

    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Sends a JSON message directly to a specific connected client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("Failed to send message to websocket client: %s", e)
            await self.disconnect(websocket)

    async def broadcast(self, event: Dict[str, Any]) -> int:
        """Broadcasts a JSON event to all connected authenticated clients.
        
        Returns the number of clients to which the message was successfully dispatched.
        """
        if not self._active_connections:
            return 0

        # Snapshot of connections to iterate over without holding lock during I/O
        async with self._lock:
            connections = list(self._active_connections.keys())

        dispatched = 0
        dead_connections: List[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_json(event)
                dispatched += 1
            except Exception as e:
                logger.debug("Failed broadcasting to connection, marking for removal: %s", e)
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                for dead_ws in dead_connections:
                    self._active_connections.pop(dead_ws, None)

        return dispatched

    async def send_to_user(self, user_id: str, event: Dict[str, Any]) -> int:
        """Dispatches an event specifically to all active connections belonging to a single user."""
        async with self._lock:
            targets = [ws for ws, u in self._active_connections.items() if u.id == user_id]

        dispatched = 0
        for ws in targets:
            try:
                await ws.send_json(event)
                dispatched += 1
            except Exception:
                await self.disconnect(ws)

        return dispatched

    async def send_to_role(self, role: Union[UserRole, str], event: Dict[str, Any]) -> int:
        """Dispatches an event to all connected users possessing the specified role or higher."""
        target_role = role.value if isinstance(role, UserRole) else str(role)
        async with self._lock:
            targets = [
                ws for ws, u in self._active_connections.items()
                if (u.role.value if hasattr(u.role, "value") else str(u.role)) == target_role
            ]

        dispatched = 0
        for ws in targets:
            try:
                await ws.send_json(event)
                dispatched += 1
            except Exception:
                await self.disconnect(ws)

        return dispatched

    def broadcast_threadsafe(
        self,
        event: Dict[str, Any],
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Thread-safe and non-blocking broadcast invokable from background camera threads.
        
        Never blocks the camera worker thread or IncidentEngine execution.
        """
        target_loop = loop or self._loop

        # 1. Try to find a running loop if not explicitly designated
        if not target_loop:
            try:
                target_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        if not target_loop:
            logger.warning("Cannot broadcast_threadsafe: no active event loop available.")
            return

        try:
            if target_loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event), target_loop)
            else:
                target_loop.run_until_complete(self.broadcast(event))
        except Exception as e:
            # Resilient isolation: never let broadcast issues crash background camera worker
            logger.error("Error in broadcast_threadsafe: %s", e)

    async def start_heartbeat(self, interval_seconds: Optional[int] = None) -> None:
        """Starts a background periodic ping loop to detect stale or dead connections."""
        interval = interval_seconds or settings.WEBSOCKET_HEARTBEAT_SECONDS
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def _heartbeat_loop():
            logger.info("WebSocket heartbeat monitor started (Interval: %ds)", interval)
            while True:
                try:
                    await asyncio.sleep(interval)
                    if self._active_connections:
                        ping = create_ping_event()
                        await self.broadcast(ping)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug("Heartbeat broadcast error: %s", e)

        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())

    def stop_heartbeat(self) -> None:
        """Stops the periodic heartbeat monitor."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            logger.info("WebSocket heartbeat monitor stopped.")


# Singleton ConnectionManager instance
_connection_manager_instance: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Returns the singleton ConnectionManager instance."""
    global _connection_manager_instance
    if _connection_manager_instance is None:
        _connection_manager_instance = ConnectionManager()
    return _connection_manager_instance
