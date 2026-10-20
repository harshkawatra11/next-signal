"""LLM research calls: structured JSON output via Sarvam sarvam-105b, with a Gemini fallback on
429/5xx/timeout. The deterministic core (metrics/*, grading/*) computes every number; the LLM only explains
anomalies and never originates a figure shown to the user.
"""
from __future__ import annotations

import collections
import json
import time
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from ..config import settings

SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"


class LLMError(Exception):
    pass


RECENT: "collections.deque[dict]" = collections.deque(maxlen=50)


def _parse_json(raw: str) -> Any:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON object or array found in model output")
    obj, _ = json.JSONDecoder().raw_decode(s[min(starts) :])
    return obj


async def _call_sarvam(
    client: httpx.AsyncClient, messages: list[dict], schema_name: str, schema: dict, effort: str
) -> tuple[str, dict]:
    body = {
        "model": settings.sarvam_research_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": settings.sarvam_max_tokens,
    }
    if settings.sarvam_reasoning == "on":
        body["reasoning_effort"] = effort
    if settings.sarvam_json_mode == "schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema, "strict": False}}
    elif settings.sarvam_json_mode == "object":
        body["response_format"] = {"type": "json_object"}
    if settings.sarvam_json_mode in ("object", "prompt"):
        body["messages"] = messages[:-1] + [{
            "role": messages[-1]["role"],
            "content": messages[-1]["content"] + f"\n\nReturn only JSON matching this JSON schema named {schema_name}:\n{json.dumps(schema)}",
        }]
    r = await client.post(
        SARVAM_URL,
        json=body,
        timeout=120,
        headers={"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"},
    )
    if r.status_code in (429, 500, 502, 503, 504):
        raise LLMError(f"sarvam {r.status_code}: {r.text[:200]}")
    r.raise_for_status()
    data = r.json()
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    if not content and msg.get("reasoning_content"):
        raise LLMError("sarvam returned reasoning without content")
    return content, data.get("usage", {})


async def _call_gemini(
    client: httpx.AsyncClient, messages: list[dict], schema_name: str, schema: dict, effort: str
) -> tuple[str, dict]:
    model = settings.gemini_model or "gemini-3.5-flash-lite"
    text = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
    text += f"\n\nReturn only JSON matching this JSON schema named {schema_name}:\n{json.dumps(schema)}"
    r = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": settings.gemini_api_key},
        timeout=120,
        json={
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        },
    )
    if r.status_code in (429, 500, 502, 503, 504):
        raise LLMError(f"gemini {r.status_code}: {r.text[:200]}")
    r.raise_for_status()
    data = r.json()
    part = data["candidates"][0]["content"]["parts"][0]["text"]
    return part, data.get("usageMetadata", {})


async def llm_json(
    client: httpx.AsyncClient,
    bus,
    run_id: str,
    purpose: str,
    messages: list[dict],
    out_type: type,
    effort: str = "low",
):
    """out_type should be a pydantic BaseModel subclass. For list-shaped outputs, wrap in a model with a
    single `items: list[...]` field (some json_schema backends reject a bare top-level array); see
    schemas.Hypotheses for the pattern.
    """
    ta = TypeAdapter(out_type)
    schema = ta.json_schema()
    name = purpose.replace(" ", "_")[:40]
    order = (
        [("sarvam", _call_sarvam), ("gemini", _call_gemini)]
        if settings.llm_provider == "sarvam"
        else [("gemini", _call_gemini), ("sarvam", _call_sarvam)]
    )
    last: Exception | None = None
    msgs = list(messages)
    for provider, fn in order:
        if provider == "gemini" and not settings.gemini_api_key:
            continue
        if provider == "sarvam" and not settings.sarvam_api_key:
            continue
        for _attempt in range(1):  # dropped from 2 on 20 Oct: a real live run showed Sarvam's
            # failures on production-sized prompts are a slow truncation (the model spends its whole
            # token budget on internal reasoning and the output gets cut off mid-string), not a
            # correctable formatting mistake a "please fix your JSON" repair message can fix. A single
            # attempt that already took 70+ seconds, retried a second time, pushed the whole stage past
            # its own time budget before the Gemini fallback could ever run, turning a recoverable
            # fallback into a "partial" run with zero LLM calls recorded. One attempt per provider lets
            # the fallback actually happen inside the stage's time budget; across every real run and
            # probe made while diagnosing this, a same-provider retry never once turned a failure into
            # a success.
            t0 = time.perf_counter()
            try:
                raw, usage = await fn(client, msgs, name, schema, effort)
                obj = ta.validate_python(_parse_json(raw))
                event = {
                    "purpose": purpose, "provider": provider, "ok": True,
                    "ms": int((time.perf_counter() - t0) * 1000), "usage": usage,
                }
                RECENT.append({**event, "at": time.time()})
                if bus is not None:
                    await bus.emit(run_id, "llm", event)
                return obj
            except (ValidationError, ValueError, json.JSONDecodeError) as e:
                last = e
                if bus is not None:
                    await bus.emit(run_id, "llm", {
                        "purpose": purpose, "provider": provider, "ok": False,
                        "ms": int((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:200]}",
                    })
                RECENT.append({
                    "purpose": purpose, "provider": provider, "ok": False,
                    "ms": int((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:200]}",
                    "at": time.time(),
                })
                msgs = msgs + [
                    {
                        "role": "user",
                        "content": f"Your previous output failed validation: {str(e)[:800]}. Return corrected JSON only, matching the schema exactly.",
                    }
                ]
            except (LLMError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last = e
                if bus is not None:
                    await bus.emit(run_id, "llm", {
                        "purpose": purpose, "provider": provider, "ok": False,
                        "ms": int((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:200]}",
                    })
                RECENT.append({
                    "purpose": purpose, "provider": provider, "ok": False,
                    "ms": int((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:200]}",
                    "at": time.time(),
                })
                break  # switch provider, don't retry this one again
    raise LLMError(f"{purpose}: all providers failed: {last}")
