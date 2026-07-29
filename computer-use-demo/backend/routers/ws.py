"""WebSocket routes for real-time streaming and VNC proxy."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time session event streaming.

    Clients connect here to receive live updates (text deltas, tool calls,
    tool results, screenshots, errors) as the agent loop processes messages.
    """
    await websocket.accept()

    state = await session_manager.get_or_load_session(session_id)
    if state is None:
        await websocket.send_json({"type": "error", "data": {"message": "Session not found"}})
        await websocket.close()
        return

    # Register this client
    state.websockets.append(websocket)
    logger.info(f"WebSocket client connected to session {session_id}")

    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "data": {
                "session_id": session_id,
                "is_running": state.is_running,
            },
        })

        # Keep connection alive and read client messages (cancellation, etc.)
        while True:
            try:
                client_data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if client_data:
                    import json
                    data = json.loads(client_data)
                    if data.get("type") == "cancel":
                        if state:
                            state.cancel_event.set()
                            await state.broadcast("cancelled", {"message": "Cancelled by user"})
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from session {session_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Unregister
        if state and websocket in state.websockets:
            state.websockets.remove(websocket)


@router.websocket("/ws/vnc")
async def vnc_proxy_websocket(client_ws: WebSocket):
    """WebSocket proxy for noVNC VNC connection.

    Forwards WebSocket traffic between the client and noVNC's websockify
    (port 6080). This allows a single-port deployment behind a reverse proxy.
    """
    await client_ws.accept()
    logger.info("VNC WebSocket proxy client connected")

    try:
        async with httpx.AsyncClient() as http_client:
            # Connect to noVNC's WebSocket (websockify)
            # We use raw TCP since httpx doesn't natively do WS-to-WS bridging
            reader, writer = await asyncio.open_connection("localhost", 6080)

            # Send WebSocket upgrade request to noVNC
            upgrade_request = (
                "GET /websockify HTTP/1.1\r\n"
                "Host: localhost:6080\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            )
            writer.write(upgrade_request.encode())
            await writer.drain()

            # Read upgrade response
            response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)

            if b"101" not in response:
                await client_ws.close(code=1011, reason="VNC connection failed")
                writer.close()
                return

            # Bidirectional proxy
            async def forward_client_to_vnc():
                try:
                    while True:
                        data = await client_ws.receive_bytes()
                        writer.write(data)
                        await writer.drain()
                except Exception:
                    pass
                finally:
                    writer.close()

            async def forward_vnc_to_client():
                try:
                    while True:
                        data = await reader.read(65536)
                        if not data:
                            break
                        await client_ws.send_bytes(data)
                except Exception:
                    pass

            # Run both directions concurrently
            task1 = asyncio.create_task(forward_client_to_vnc())
            task2 = asyncio.create_task(forward_vnc_to_client())

            done, pending = await asyncio.wait(
                [task1, task2], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.exception(f"VNC proxy error: {e}")
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
