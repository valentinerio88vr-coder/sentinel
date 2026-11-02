"""In-process pub/sub for live UI updates.

Deliberately simple: subscribers get an asyncio.Queue and a fan-out loop pushes JSON.
For a multi-process deployment swap this for Redis pub/sub — the interface is one call.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

_subscribers: set[asyncio.Queue] = set()
_lock = asyncio.Lock()


async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    async with _lock:
        _subscribers.add(q)
    return q


async def unsubscribe(q: asyncio.Queue) -> None:
    async with _lock:
        _subscribers.discard(q)


def publish_sync(org_id: str, topic: str, data: dict[str, Any]) -> None:
    """Callable from sync code (endpoints, worker threads)."""
    msg = {"org": org_id, "topic": topic, "data": data}
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


def subscriber_count() -> int:
    return len(_subscribers)
