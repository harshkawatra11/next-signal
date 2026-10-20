"""VoiceSession protocol 2 with all Sarvam calls mocked. Ported from ai-healthcare platform's
tests/test_voice_session_v2.py, trimmed to the load-bearing cases, adapted to pytest-asyncio and a
Report-grounded session (voice_fakes.py plays the role of test_voice_fakes.py)."""
import pytest

from next_signal.voice import sarvam_chat
from voice_fakes import (
    ChatScript,
    discovery_tool,
    make_session,
    run_typed,
    text_delta,
    tool_delta,
)

DISCOVERY_TOOLS = {"get_discovery": lambda **_: discovery_tool()}


def _use(monkeypatch, script: ChatScript) -> ChatScript:
    monkeypatch.setattr(sarvam_chat, "stream_chat", script)
    return script


@pytest.mark.asyncio
async def test_tool_path_emits_full_frame_sequence(monkeypatch):
    script = _use(
        monkeypatch,
        ChatScript(
            [tool_delta("get_discovery", "{}")],
            [text_delta("The discovery is about "), text_delta("North America revenue. ")],
        ),
    )
    session, frames, tts = make_session(tools=DISCOVERY_TOOLS)
    await run_typed(session, "What is the discovery?", "c-1")

    kinds = frames.kinds()
    assert kinds[0] == "final"
    assert frames.of("final")[0]["clientTurnId"] == "c-1"
    stages = [f["stage"] for f in frames.of("thinking")]
    assert stages == ["planning", "tools", "answering"]
    tool = frames.of("tool")[0]
    assert (tool["name"], tool["ok"]) == ("get_discovery", True)
    reply = frames.of("reply")[0]
    assert reply["text"] == "The discovery is about North America revenue."
    assert reply["toolCalls"] == ["get_discovery"]
    assert reply["cards"][0]["type"] == "discovery"
    audio = frames.of("audio")
    assert audio and all(a["encoding"] == "pcm_s16le" and a["filler"] is False for a in audio)
    end = frames.of("turn_end")[0]
    assert end["metrics"]["tools"] == ["get_discovery"]
    assert kinds.index("tool") < kinds.index("reply_delta") < kinds.index("reply") < kinds.index("turn_end")

    assert [c["tool_choice"] for c in script.calls] == ["auto", "none"]
    second = script.calls[1]["messages"]
    assert second[0]["content"] == "SYSTEM"
    assert second[1]["role"] == "system" and second[1]["content"].startswith("Context: report for")
    assert tts.said == ["The discovery is about North America revenue."]
    assert tts.ended == 1


@pytest.mark.asyncio
async def test_no_tool_path_streams_directly(monkeypatch):
    _use(monkeypatch, ChatScript([text_delta("Revenue grew 14 percent. "), text_delta("Margins held steady.")]))
    session, frames, _ = make_session(tools=DISCOVERY_TOOLS)
    await run_typed(session, "How did revenue grow?")
    assert frames.of("tool") == []
    assert [f["stage"] for f in frames.of("thinking")] == ["planning"]
    reply = frames.of("reply")[0]
    assert reply["toolCalls"] == [] and reply["cards"] == []
    assert reply["text"] == "Revenue grew 14 percent. Margins held steady."
    assert session.history[-1] == {"role": "assistant", "content": reply["text"]}


@pytest.mark.asyncio
async def test_markdown_and_currency_are_spoken_correctly(monkeypatch):
    _use(monkeypatch, ChatScript([text_delta("**Revenue** was Rs 162 cr (up from last year).")]))
    session, _frames, tts = make_session(tools={})
    await run_typed(session, "What was revenue?")
    assert tts.said == ["Revenue was rupees 162 crore."]


@pytest.mark.asyncio
async def test_no_api_key_sends_error_not_a_crash():
    session, frames, _ = make_session(tools={}, sarvam_api_key="")
    await run_typed(session, "Anything")
    errors = frames.of("error")
    assert errors and errors[0]["code"] == "no_key"
    assert frames.of("reply") == []  # the turn never got far enough to reply


@pytest.mark.asyncio
async def test_honest_no_discovery_case_does_not_fabricate(monkeypatch):
    import json

    from next_signal.schemas import Report
    from voice_fakes import load_fixture_report

    data = json.loads(load_fixture_report().model_dump_json())
    data["discovery"] = None
    empty_report = Report.model_validate(data)
    script = _use(monkeypatch, ChatScript([text_delta("I do not have a discovery to report for this run.")]))
    session, frames, _ = make_session(tools={}, report=empty_report)
    await run_typed(session, "What is the discovery?")

    # the context message built for the LLM must state plainly that nothing survived, not omit it
    # or imply a discovery exists
    context_msg = script.calls[0]["messages"][1]
    assert context_msg["role"] == "system"
    assert "no discovery survived" in context_msg["content"]
    reply = frames.of("reply")[0]
    assert "discovery" in reply["text"].lower()
