# Next Signal

An autonomous research agent for NIFTY 50 Track D (Pharma and Healthcare) companies, built for "Finding the Next
Signal" (ATMOS 2026, BITS Pilani Hyderabad Campus, The Wall Street Club and The Economics Association).

Given any NIFTY 50 pharma or healthcare company, the system collects public evidence from exchange filings, USFDA
records, peers and market data, computes what changed and when, tests every hypothesis against its strongest rival,
and reports only what survives, with a verbatim source behind every number. It does not give investment advice.

Full build plan: `../../PPTS-CASE-STUDY/nsut-innovators-court/next-signal-bits/PLAN.md`.

## Structure

- `engine/` — Python FastAPI research engine (six stages: Discover, Connect, Calculate, Reason, Challenge, Prove)
- `apps/web/` — Next.js dashboard (red/white/black, click-through evidence trail, voice analyst)
- `docs/` — architecture and demo runbook

## Running locally

```powershell
engine\.venv\Scripts\python.exe -m uvicorn next_signal.main:app --port 8080 --app-dir engine --reload
cd apps\web
npm run dev
```

Run a single company from the CLI (developer shortcut):

```powershell
engine\.venv\Scripts\python.exe engine\scripts\run_one.py CIPLA
```

Run the evaluation harness across the Track D universe:

```powershell
engine\.venv\Scripts\python.exe -m next_signal.eval.harness --set N50,TB
```

## Credentials

Copy `engine/.env.example` to `engine/.env` and fill in the keys, or run
`engine\.venv\Scripts\python.exe engine\scripts\import_keys.py` to pull them from sibling projects
(`stocksense`, `ai-healthcare platform`) automatically. `SEC_USER_AGENT` is optional; without it, the SEC EDGAR
collector is skipped and tagged WIRED rather than LIVE.

## Disclaimer

Public data only. Research output for evaluation purposes. Not investment advice.
