"""Copy credentials from the user's existing projects into engine/.env without printing any value.

Run: engine\\.venv\\Scripts\\python.exe -X utf8 engine\\scripts\\import_keys.py
"""
import pathlib
import re

HOME = pathlib.Path(r"C:\Users\harsh\Desktop\HARSH\WEB-DEV-PROJECTS")
SRC = {
    HOME / "stocksense" / ".env": {
        "STOCKSENSE_UPSTOX_API_KEY": "UPSTOX_API_KEY",
        "STOCKSENSE_UPSTOX_API_SECRET": "UPSTOX_API_SECRET",
        "STOCKSENSE_UPSTOX_ACCESS_TOKEN": "UPSTOX_ACCESS_TOKEN",
        "STOCKSENSE_UPSTOX_ANALYTICS_TOKEN": "UPSTOX_ANALYTICS_TOKEN",
        "STOCKSENSE_ANGEL_API_KEY": "ANGEL_API_KEY",
        "STOCKSENSE_ANGEL_CLIENT_CODE": "ANGEL_CLIENT_CODE",
        "STOCKSENSE_ANGEL_PASSWORD": "ANGEL_PASSWORD",
        "STOCKSENSE_ANGEL_TOTP_SECRET": "ANGEL_TOTP_SECRET",
    },
    HOME / "ai-healthcare platform" / "backend" / ".env": {
        "SARVAM_API_KEY": "SARVAM_API_KEY",
        "GEMINI_API_KEY": "GEMINI_API_KEY",
        "GEMINI_MODEL": "GEMINI_MODEL",
    },
    HOME / "nsut-maudrik" / "backend" / ".env": {
        "SARVAM_API_KEY": "SARVAM_API_KEY",
        "GEMINI_API_KEY": "GEMINI_API_KEY",
    },
    HOME / "sih-apix" / ".env.local": {
        "SARVAM_API_KEY": "SARVAM_API_KEY",
    },
}


def parse(p: pathlib.Path) -> dict:
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def main():
    dst = pathlib.Path(__file__).resolve().parents[1] / ".env"
    cur = parse(dst)
    found = {}
    sources_checked = []
    for src, mapping in SRC.items():
        sources_checked.append(str(src))
        vals = parse(src)
        for a, b in mapping.items():
            if b not in found and vals.get(a):
                found[b] = vals[a]

    fixed = {
        "NSE_MCP_BHAVCOPY_URL": "https://mcp.nseindia.in/bhavcopy/cm/mcp",
        "NSE_MCP_CMMKT_URL": "https://mcp.nseindia.in/cmmkt/mcp",
        "SARVAM_RESEARCH_MODEL": "sarvam-105b",
        "SARVAM_CHAT_MODEL": "sarvam-105b-conversations",
        "SARVAM_STT_MODEL": "saaras:v3-realtime",
        "SARVAM_TTS_MODEL": "bulbul:v3",
        "SARVAM_SPEAKER": "simran",
        "SARVAM_TTS_MODE": "ws",
        "VOICE_LANGUAGE": "auto",
        "WEB_ORIGIN": "http://localhost:3000",
        "SEC_USER_AGENT": "",
        "LLM_PROVIDER": "sarvam",
    }
    merged = {**fixed, **cur, **found}
    dst.write_text(
        "\n".join(f"{k}={v}" for k, v in sorted(merged.items())) + "\n",
        encoding="utf-8",
    )
    print(f"Checked {len(sources_checked)} source files for credentials (paths not printed to avoid noise).")
    print(f"Wrote {dst} with {len(merged)} keys.")
    for k in sorted(merged):
        print(f"{k}: {'present' if merged[k] else 'MISSING'}")


if __name__ == "__main__":
    main()
