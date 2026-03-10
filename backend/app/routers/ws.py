"""WebSocket endpoint for live repository processing updates."""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/repos/{repo_id}/status")
async def repo_status_ws(websocket: WebSocket, repo_id: int):
    """WebSocket that pushes live processing updates for a repository.

    Subscribes to a Redis pub/sub channel for real-time updates.
    Falls back to polling Redis key if no pub/sub message is received.
    Closes automatically when status is 'processed' or 'failed'.
    """
    await websocket.accept()

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    channel = f"repo:{repo_id}:updates"

    try:
        await pubsub.subscribe(channel)

        while True:
            # Try to get a pub/sub message (non-blocking with timeout)
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )

            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

                # Close if terminal state
                if data.get("status") in ("processed", "failed"):
                    await websocket.close()
                    break
            else:
                # Fallback: poll the Redis key
                progress_data = await redis_client.get(f"repo:{repo_id}:progress")
                if progress_data:
                    data = json.loads(progress_data)
                    await websocket.send_json(data)

                    if data.get("status") in ("processed", "failed"):
                        await websocket.close()
                        break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis_client.aclose()
