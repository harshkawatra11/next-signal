"""Resolve stage: turn a free-text query or symbol into a RunContext seed (identity, playbook, peers).

Order of attempts: offline match against the cached Track D + tie-break universe first (fast, always
available); live NSE quote-equity lookup second, for any listed company outside that universe (the brief's
robustness/tie-break requirement: "should be able to handle other listed companies in the same sector").
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from .context import RunContext
from .. import universe


async def run(query: str, as_of: str | None = None) -> RunContext:
    uni = await universe.load_universe()
    ident = universe.resolve_offline(query, uni)

    if ident is None:
        # Fall back to a live NSE lookup for a company outside the cached universe (tie-break robustness).
        from ..sources import nse  # local import: avoids a network-layer import at module load time

        ident = await nse.resolve_live(query)

    if ident is None:
        raise ValueError(f"could not resolve '{query}' to a listed company")

    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    # A 4-hex-digit random suffix prevents a run_id collision when two runs for the same symbol start
    # within the same second (the previous scheme used only the timestamp, with no such guard).
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = f"{ident.symbol}-{stamp}-{secrets.token_hex(2)}"

    # Peer selection moves to Connect once the subject's latest-quarter revenue is known from the XBRL
    # filings fetched there; universe.peers() needs a real market_caps dict to rank by, which Resolve has
    # no way to produce without that data.
    peer_symbols: list[str] = []

    return RunContext(
        run_id=run_id,
        symbol=ident.symbol,
        company=ident.company_name,
        sub_industry=ident.playbook,
        as_of=as_of_date,
        peers=peer_symbols,
    )
