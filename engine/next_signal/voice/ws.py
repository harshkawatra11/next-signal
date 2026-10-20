"""The voice analyst WebSocket: one connection per call, one VoiceSession, grounded on one Report
(PLAN.md §5.15 point 2). Ported from ai-healthcare platform's app/api/v1/voice_ws.py: same frame
protocol and origin-check pattern, with district/forecast/recommendation services replaced by a
run_id-keyed report lookup (the `hello` frame now carries `runId`).

Client frames: hello (language, mode, protocol, runId) | audio (b64) | text (body, clientTurnId) |
context (runId, to switch reports) | ptt (state) | interrupt | bye.
Server frames: ready | vad | partial | final | thinking | tool | reply_delta | reply | audio |
interrupted | turn_end | error.

CORS middleware does not apply to WebSocket upgrades in Starlette, so the Origin header is checked by
hand against the same allow-list the REST API uses, before the handshake is accepted.
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import store
from ..config import settings
from ..schemas import Report
from .session import VoiceSession

logger = logging.getLogger("next_signal.voice")

router = APIRouter(tags=["voice"])


def _origin_allowed(origin: str | None) -> bool:
    if origin is None:
        # Non-browser clients (curl, a test harness) send no Origin header at all; only browser-
        # originated cross-origin requests carry one.
        return True
    allowed = {settings.web_origin, "http://localhost:3000"}
    if "localhost" in settings.web_origin:
        allowed.add(settings.web_origin.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in settings.web_origin:
        allowed.add(settings.web_origin.replace("127.0.0.1", "localhost"))
    return origin in allowed


def load_report(run_id: str) -> Report | None:
    raw = store.get_report_json(run_id)
    if raw is None:
        return None
    return Report.model_validate(json.loads(raw))


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if not _origin_allowed(origin):
        await websocket.close(code=4403)
        return

    await websocket.accept()

    first_frame_raw = None
    session: VoiceSession | None = None
    try:
        while True:
            raw = first_frame_raw or await websocket.receive_text()
            first_frame_raw = None
            try:
                frame = json.loads(raw)
            except (ValueError, TypeError):
                continue

            kind = frame.get("t")
            if kind == "hello":
                if frame.get("protocol") != 2:
                    await websocket.send_json({
                        "t": "error", "message": "Unsupported voice protocol. Reload the page to update the client.",
                        "fatal": True, "code": "protocol_unsupported",
                    })
                    break
                run_id = frame.get("runId")
                report = load_report(str(run_id)) if run_id else None
                if report is None:
                    await websocket.send_json({
                        "t": "error", "message": "No report found for that run id.", "fatal": True, "code": "report_not_found",
                    })
                    break
                session = VoiceSession(settings=settings, report=report, send=websocket.send_json)
                await session.start(language=frame.get("language", "auto"), mode=frame.get("mode", "handsfree"))
            elif session is None:
                continue  # ignore any frame before a successful hello
            elif kind == "audio":
                await session.handle_audio_chunk(frame.get("b64", ""))
            elif kind == "text":
                await session.handle_typed_text(frame.get("body", ""), frame.get("clientTurnId"))
            elif kind == "context":
                await session.handle_context(frame, report_loader=load_report)
            elif kind == "ptt":
                await session.handle_ptt(str(frame.get("state", "")))
            elif kind == "interrupt":
                await session.interrupt()
            elif kind == "bye":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("voice websocket failed for session %s", session.session_id if session else "unknown")
    finally:
        if session is not None:
            await session.dispose()
