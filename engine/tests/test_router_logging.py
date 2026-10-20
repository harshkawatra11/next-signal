import json

from pydantic import BaseModel

from next_signal.llm import router as R
from next_signal.llm.router import LLMError, llm_json


class Probe(BaseModel):
    company: str
    quarters: int


async def test_llm_json_logs_sarvam_failure_then_gemini_success(monkeypatch):
    R.RECENT.clear()

    async def fake_sarvam(client, messages, schema_name, schema, effort):
        raise LLMError("sarvam 500: boom")

    async def fake_gemini(client, messages, schema_name, schema, effort):
        return json.dumps({"company": "Cipla Limited", "quarters": 8}), {}

    monkeypatch.setattr(R, "_call_sarvam", fake_sarvam)
    monkeypatch.setattr(R, "_call_gemini", fake_gemini)
    monkeypatch.setattr(R.settings, "llm_provider", "sarvam")
    monkeypatch.setattr(R.settings, "sarvam_api_key", "x")
    monkeypatch.setattr(R.settings, "gemini_api_key", "y")

    out = await llm_json(None, None, "r1", "test_purpose", [{"role": "user", "content": "hi"}], Probe, effort="low")
    assert out.company == "Cipla Limited"

    attempts = list(R.RECENT)
    assert len(attempts) == 2
    assert attempts[0]["provider"] == "sarvam" and attempts[0]["ok"] is False
    assert attempts[1]["provider"] == "gemini" and attempts[1]["ok"] is True
