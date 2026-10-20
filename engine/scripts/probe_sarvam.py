"""Usage: .venv/Scripts/python.exe scripts/probe_sarvam.py
Tries five request shapes against Sarvam chat completions and reports which return valid JSON."""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from next_signal.config import settings  # noqa: E402

URL = "https://api.sarvam.ai/v1/chat/completions"
SCHEMA = {"type": "object", "properties": {"company": {"type": "string"}, "quarters": {"type": "integer"}},
          "required": ["company", "quarters"]}
MSGS = [
    {"role": "system", "content": "Return only a JSON object. No prose."},
    {"role": "user", "content": 'Return {"company": "Cipla Limited", "quarters": 8} exactly as JSON with keys company and quarters.'},
]
VARIANTS = {
    "A_current": {"model": settings.sarvam_research_model, "reasoning_effort": "medium", "max_tokens": 4000,
                  "response_format": {"type": "json_schema", "json_schema": {"name": "probe", "schema": SCHEMA, "strict": False}}},
    "B_no_format": {"model": settings.sarvam_research_model, "reasoning_effort": "medium", "max_tokens": 4000},
    "C_no_reasoning": {"model": settings.sarvam_research_model, "max_tokens": 1500},
    "D_conversations": {"model": "sarvam-105b-conversations", "max_tokens": 1500},
    "E_json_object": {"model": settings.sarvam_research_model, "max_tokens": 1500, "response_format": {"type": "json_object"}},
}


def main() -> None:
    if not settings.sarvam_api_key:
        print("SARVAM_API_KEY is empty in engine/.env"); return
    rows = []
    with httpx.Client(timeout=120) as c:
        for name, extra in VARIANTS.items():
            body = {"messages": MSGS, "temperature": 0.2, **extra}
            t0 = time.perf_counter()
            try:
                r = c.post(URL, json=body, headers={"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"})
                ms = int((time.perf_counter() - t0) * 1000)
                ok_json = False
                content = ""
                if r.status_code == 200:
                    msg = r.json()["choices"][0]["message"]
                    content = msg.get("content") or ""
                    try:
                        s = content[content.find("{"): content.rfind("}") + 1]
                        ok_json = json.loads(s).get("quarters") == 8
                    except Exception:
                        ok_json = False
                rows.append((name, r.status_code, ms, ok_json, (content or r.text)[:160].replace("\n", " ")))
            except Exception as e:
                rows.append((name, "EXC", int((time.perf_counter() - t0) * 1000), False, str(e)[:160]))
    for row in rows:
        print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    main()
