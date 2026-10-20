"""Shared fakes for the voice session tests. Sarvam is never called. Ported from ai-healthcare
platform's tests/test_voice_fakes.py: same ChatScript/FakeTts/Frames pattern, adapted to a Report-
grounded VoiceSession (district/forecast/recommendation services replaced by a single `report` fixture).
"""
import asyncio
import base64
import json
from pathlib import Path
from typing import Any

from next_signal.config import Settings
from next_signal.schemas import Report
from next_signal.voice.sarvam_chat import ChatDelta
from next_signal.voice.sarvam_tts_ws import AudioChunk
from next_signal.voice.session import VoiceSession
from next_signal.voice.tools import ToolResult

PCM_B64 = base64.b64encode(b"\x01\x00" * 480).decode()
FIXTURE = Path(__file__).parent / "fixtures" / "report_min.json"


def load_fixture_report() -> Report:
    return Report.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def text_delta(text: str) -> ChatDelta:
    return ChatDelta(content=text)


def tool_delta(name: str, args: str = "{}", call_id: str = "call_1", index: int = 0) -> ChatDelta:
    return ChatDelta(tool_calls=[{"index": index, "id": call_id, "function": {"name": name, "arguments": args}}], finish_reason="tool_calls")


class ChatScript:
    """Stands in for `sarvam_chat.stream_chat`. Each call consumes one response: a list of ChatDelta,
    an Exception (raised), a float (sleep) or an Event (wait)."""

    def __init__(self, *responses: list[Any]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kw: Any):
        self.calls.append({"tool_choice": kw.get("tool_choice"), "messages": [dict(m) for m in kw["messages"]], "max_tokens": kw.get("max_tokens")})
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        for item in resp:
            if isinstance(item, Exception):
                raise item
            if callable(item):
                item()
            elif isinstance(item, (int, float)):
                await asyncio.sleep(item)
            elif isinstance(item, asyncio.Event):
                await item.wait()
            else:
                yield item


class FakeTts:
    """Records the calls a session makes on a `TtsStream` and emits one PCM chunk per sentence."""

    mode = "ws"

    def __init__(self, *, hang_begin: bool = False):
        self.language: str | None = None
        self.said: list[str] = []
        self.begun = 0
        self.ended = 0
        self.cancelled = 0
        self.closed = False
        self.hang_begin = hang_begin
        self._on_audio = None
        self._seq = 0

    async def begin_turn(self, language, on_audio):
        self.begun += 1
        self.language = language
        self._on_audio = on_audio
        self._seq = 0
        if self.hang_begin:
            await asyncio.sleep(3600)

    async def say(self, sentence):
        self.said.append(sentence)
        if self._on_audio is not None:
            await self._on_audio(AudioChunk(PCM_B64, "pcm_s16le", 24000, self._seq))
            self._seq += 1

    async def end_turn(self):
        self.ended += 1

    async def cancel_turn(self):
        self.cancelled += 1

    async def close(self):
        self.closed = True


class Frames:
    def __init__(self):
        self.items: list[dict[str, Any]] = []

    async def __call__(self, frame):
        self.items.append(frame)

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [f for f in self.items if f["t"] == kind]

    def kinds(self) -> list[str]:
        return [f["t"] for f in self.items]


def make_session(tools=None, tts="default", speak=True, clock=None, sleep=None, report=None, **overrides) -> tuple[VoiceSession, Frames, FakeTts | None]:
    frames = Frames()
    defaults = {"sarvam_api_key": "test-key", "sarvam_stream_with_tools": True}
    defaults.update(overrides)
    settings = Settings(**defaults)
    fake_tts = FakeTts() if tts == "default" else tts
    session = VoiceSession(
        settings=settings,
        report=report or load_fixture_report(),
        send=frames,
        protocol=2,
        tools=tools,
        tts=fake_tts,
        speak=speak,
        **({"clock": clock} if clock else {}),
        **({"sleep": sleep} if sleep else {}),
    )
    session.history = [{"role": "system", "content": "SYSTEM"}]
    return session, frames, fake_tts


async def run_typed(session: VoiceSession, text: str, client_turn_id: str | None = None) -> None:
    await session.handle_typed_text(text, client_turn_id)
    turn = session.turns.current
    assert turn is not None and turn.task is not None
    await asyncio.wait_for(asyncio.shield(_wait(turn.task)), 5)


async def _wait(task: asyncio.Task) -> None:
    try:
        await task
    except asyncio.CancelledError:
        pass


def discovery_tool() -> ToolResult:
    return ToolResult({"sentence": "test discovery"}, {"type": "discovery", "sentence": "test discovery"})
