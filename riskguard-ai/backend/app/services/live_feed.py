import asyncio
import json
from typing import List

_CLIENTS: List[asyncio.Queue] = []


def _serialize(event: dict) -> str:
    payload = json.dumps(event)
    return f"data: {payload}\n\n"


def subscribe() -> asyncio.Queue:
    q = asyncio.Queue()
    _CLIENTS.append(q)
    return q


def unsubscribe(q: asyncio.Queue):
    if q in _CLIENTS:
        _CLIENTS.remove(q)


def broadcast(event: dict):
    """Best-effort broadcast to all connected SSE clients."""
    payload = _serialize(event)
    for q in list(_CLIENTS):
        try:
            q.put_nowait(payload)
        except Exception:
            continue


def client_count() -> int:
    return len(_CLIENTS)
