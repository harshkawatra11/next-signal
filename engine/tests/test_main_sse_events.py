"""Tests for the /api/runs/{id}/events SSE endpoint: Last-Event-ID resume and the run_error naming
that keeps the server's own failure event from colliding with EventSource's native "error" Event
(see main.py's run_events and pipeline/run.py's drive()).
"""
from __future__ import annotations

from next_signal import store


def test_events_after_respects_after_query_param():
    store.append_event("r1", "stage", {"stage": "Discover", "state": "start"})
    store.append_event("r1", "stage", {"stage": "Discover", "state": "end"})
    store.append_event("r1", "done", {"run_id": "r1"})

    events = list(store.events_after("r1", after=1))
    assert [e["seq"] for e in events] == [2, 3]
    assert events[-1]["type"] == "done"


def test_events_after_from_zero_replays_everything():
    store.append_event("r2", "stage", {"stage": "Discover", "state": "start"})
    store.append_event("r2", "done", {"run_id": "r2"})

    events = list(store.events_after("r2", after=0))
    assert len(events) == 2
    assert events[0]["seq"] == 1


def test_main_run_events_route_honours_last_event_id_header():
    from fastapi.testclient import TestClient

    from next_signal.main import app

    store.append_event("r3", "stage", {"stage": "Discover", "state": "start"})
    store.append_event("r3", "stage", {"stage": "Discover", "state": "end"})
    store.append_event("r3", "done", {"run_id": "r3"})

    client = TestClient(app)
    with client.stream(
        "GET", "/api/runs/r3/events", headers={"Last-Event-ID": "2"}
    ) as response:
        body = response.read().decode()

    # Only the event after seq 2 (the "done" at seq 3) should have been replayed; the two earlier
    # stage events, already seen by the reconnecting client per its Last-Event-ID header, must not
    # appear again.
    assert "event: done" in body
    assert body.count("event: stage") == 0


def test_main_run_events_route_prefers_the_further_along_of_after_and_last_event_id():
    from fastapi.testclient import TestClient

    from next_signal.main import app

    store.append_event("r4", "stage", {"stage": "Discover", "state": "start"})
    store.append_event("r4", "stage", {"stage": "Discover", "state": "end"})
    store.append_event("r4", "stage", {"stage": "Connect", "state": "start"})
    store.append_event("r4", "done", {"run_id": "r4"})

    client = TestClient(app)
    # ?after=1 asks to resume from seq 2 onward, but Last-Event-ID: 2 says the client already saw
    # seq 2 as well; the header should win since it is further along.
    with client.stream(
        "GET", "/api/runs/r4/events?after=1", headers={"Last-Event-ID": "2"}
    ) as response:
        body = response.read().decode()

    assert body.count("event: stage") == 1  # only the Connect/start event (seq 3)
    assert "event: done" in body
