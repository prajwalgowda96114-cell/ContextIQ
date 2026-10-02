"""Local in-memory asyncio event bus adapter for SSE streaming."""
import asyncio
import json
from collections.abc import AsyncGenerator


class BusLocal:
    def __init__(self):
        # Map incident_id -> list of subscriber Queues
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, incident_id: str) -> asyncio.Queue:
        if incident_id not in self._subscribers:
            self._subscribers[incident_id] = []
        queue = asyncio.Queue()
        self._subscribers[incident_id].append(queue)
        return queue

    def unsubscribe(self, incident_id: str, queue: asyncio.Queue):
        if incident_id in self._subscribers and queue in self._subscribers[incident_id]:
            self._subscribers[incident_id].remove(queue)

    async def publish(self, incident_id: str, event: dict):
        """Emits event dict to all subscribed SSE queues for an incident."""
        if incident_id in self._subscribers:
            for q in self._subscribers[incident_id]:
                await q.put(event)

    async def event_generator(self, incident_id: str) -> AsyncGenerator[str, None]:
        queue = self.subscribe(incident_id)
        try:
            while True:
                # Wait for next event or 15s heartbeat
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("stage") == "Validating Evidence" and event.get("status") in ["done", "error"]:
                        # End stream when pipeline completes
                        break
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            self.unsubscribe(incident_id, queue)
