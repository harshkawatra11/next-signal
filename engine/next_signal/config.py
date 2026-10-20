from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENGINE = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENGINE / ".env"), extra="ignore")

    sarvam_api_key: str = ""
    sarvam_research_model: str = "sarvam-105b"
    sarvam_chat_model: str = "sarvam-105b-conversations"
    sarvam_stt_model: str = "saaras:v3-realtime"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_speaker: str = "simran"
    sarvam_tts_mode: str = "ws"
    sarvam_stream_with_tools: bool = True
    sarvam_max_tokens: int = 16000  # the real, confirmed root cause (20 Oct): this model reasons
    # internally on every call regardless of whether reasoning_effort is sent at all. A direct probe
    # with a realistic write_discovery-shaped prompt (1496 prompt tokens) burned 3544 to 3999 reasoning
    # tokens before emitting a single content token; at max_tokens 3000/4000/8000 that reasoning alone
    # exhausted the budget (finish_reason "length", content empty), which is why hypothesise and
    # write_discovery failed on every real pipeline call with "no JSON object or array found in model
    # output" even though a tiny two-field probe schema succeeded in well under 1000 tokens. 16000
    # leaves headroom for both the reasoning (observed up to ~4000 tokens) and a full discovery or
    # paper-section response (observed up to ~2500 tokens); confirmed working end to end at this value.
    sarvam_json_mode: str = "prompt"  # every production schema (Hypotheses, DiscoveryText) uses
    # Pydantic's "$defs"/"$ref" for nested sub-models; response_format: json_schema may not resolve
    # those refs cleanly, so the schema is sent as a text instruction instead (matches the working
    # B_no_format/C_no_reasoning probe variants) rather than relying on provider-side schema validation.
    sarvam_reasoning: str = "off"  # the reasoning_effort parameter does not actually gate whether this
    # model reasons (confirmed: it reasoned heavily even with the parameter absent), so leaving it off
    # just avoids sending a parameter that has no observed effect; sarvam_max_tokens is the real fix.

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_provider: str = "sarvam"

    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_access_token: str = ""
    upstox_analytics_token: str = ""

    angel_api_key: str = ""
    angel_client_code: str = ""
    angel_password: str = ""
    angel_totp_secret: str = ""

    nse_mcp_bhavcopy_url: str = "https://mcp.nseindia.in/bhavcopy/cm/mcp"
    nse_mcp_cmmkt_url: str = "https://mcp.nseindia.in/cmmkt/mcp"

    sec_user_agent: str = ""
    voice_language: str = "auto"
    web_origin: str = "http://localhost:3000"

    cache_dir: Path = ENGINE / ".cache"
    db_path: Path = ENGINE / "data" / "next_signal.sqlite"
    universe_cache_dir: Path = ENGINE / "data" / "universe_cache"

    run_budget_s: int = 420   # soft budget for a live run (7 min)
    run_hard_cap_s: int = 540  # hard cap (9 min); Prove runs with what exists


settings = Settings()
