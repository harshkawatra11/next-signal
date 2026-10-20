"""Per-run async event bus for SSE streaming, backed by store.append_event for replay."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from . import store


class Bus:
    def __init__(self) -> None:
        self.subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def emit_nowait(self, run_id: str, type_: str, data: dict) -> int:
        seq = store.append_event(run_id, type_, data)
        msg = {"seq": seq, "type": type_, "data": data, "ts": time.time()}
        for q in list(self.subs.get(run_id, [])):
            q.put_nowait(msg)
        return seq

    async def emit(self, run_id: str, type_: str, data: dict) -> int:
        return self.emit_nowait(run_id, type_, data)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subs[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        if q in self.subs.get(run_id, []):
            self.subs[run_id].remove(q)


bus = Bus()
