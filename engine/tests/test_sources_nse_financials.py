from datetime import date, datetime

from next_signal.sources.nse_financials import (
    fetch_filings,
    parse_financial_results,
    select_quarterly_filings,
)

# Field shapes below are the real ones confirmed by a live probe against NSE's own
# corporates-financial-results endpoint for GLENMARK (16 Oct 2026, see build-log.md).
RAW_ITEMS = [
    {
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Non-cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Oct-2024", "toDate": "31-Dec-2024",
        "broadCastDate": "14-Feb-2025 20:15:05", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1196663",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_120751_1385449_14022025081504.xml",
    },
    {
        # A Standalone filing for the same period: should lose to the Consolidated one above.
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Non-cumulative",
        "consolidated": "Standalone", "fromDate": "01-Oct-2024", "toDate": "31-Dec-2024",
        "broadCastDate": "14-Feb-2025 19:50:00", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1196600",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/STANDALONE_OLD.xml",
    },
    {
        # A revised Consolidated filing for the same period, broadcast later: should win over the
        # first Consolidated row above.
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Non-cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Oct-2024", "toDate": "31-Dec-2024",
        "broadCastDate": "20-Feb-2025 10:00:00", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1197100",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/REVISED.xml",
    },
    {
        # An older quarter, a different period entirely.
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Non-cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Jul-2024", "toDate": "30-Sep-2024",
        "broadCastDate": "13-Nov-2024 18:00:00", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1180000",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/Q2.xml",
    },
    {
        # Cumulative (half-year/nine-month) filing: must be excluded.
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Apr-2024", "toDate": "31-Dec-2024",
        "broadCastDate": "14-Feb-2025 20:15:05", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1196664",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/CUMULATIVE.xml",
    },
    {
        # Annual filing: must be excluded (period != Quarterly).
        "symbol": "GLENMARK", "period": "Annual", "cumulative": "Non-cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Apr-2024", "toDate": "31-Mar-2025",
        "broadCastDate": "15-May-2025 18:00:00", "financialYear": "01-Apr-2024 To 31-Mar-2025",
        "seqNumber": "1200000",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/ANNUAL.xml",
    },
    {
        # No XBRL URL at all: must be excluded.
        "symbol": "GLENMARK", "period": "Quarterly", "cumulative": "Non-cumulative",
        "consolidated": "Consolidated", "fromDate": "01-Jan-2024", "toDate": "31-Mar-2024",
        "broadCastDate": "10-May-2024 18:00:00", "financialYear": "01-Apr-2023 To 31-Mar-2024",
        "seqNumber": "1100000", "xbrl": None,
    },
]


def test_parse_financial_results_keeps_only_quarterly_noncumulative_with_xbrl():
    rows = parse_financial_results(RAW_ITEMS)
    # Of 7 raw items: 1 cumulative, 1 annual, 1 missing xbrl are dropped, leaving 4.
    assert len(rows) == 4
    assert all(r.xbrl_url for r in rows)


def test_parse_financial_results_parses_dates_correctly():
    rows = parse_financial_results(RAW_ITEMS)
    q3 = next(r for r in rows if r.seq_number == "1196663")
    assert q3.from_date == date(2024, 10, 1)
    assert q3.to_date == date(2024, 12, 31)
    assert q3.broadcast_at == datetime(2025, 2, 14, 20, 15, 5)
    assert q3.consolidated is True


def test_select_quarterly_filings_prefers_consolidated_over_standalone():
    rows = parse_financial_results(RAW_ITEMS)
    selected = select_quarterly_filings(rows)
    q3 = next(f for f in selected if f.to_date == date(2024, 12, 31))
    assert q3.consolidated is True
    assert "STANDALONE" not in q3.xbrl_url


def test_select_quarterly_filings_prefers_the_later_revision():
    rows = parse_financial_results(RAW_ITEMS)
    selected = select_quarterly_filings(rows)
    q3 = next(f for f in selected if f.to_date == date(2024, 12, 31))
    assert q3.xbrl_url.endswith("REVISED.xml")


def test_select_quarterly_filings_one_row_per_period():
    rows = parse_financial_results(RAW_ITEMS)
    selected = select_quarterly_filings(rows)
    periods = [f.to_date for f in selected]
    assert len(periods) == len(set(periods))
    assert len(selected) == 2  # Q3 (31 Dec 2024) and Q2 (30 Sep 2024)


def test_select_quarterly_filings_sorted_newest_first():
    rows = parse_financial_results(RAW_ITEMS)
    selected = select_quarterly_filings(rows)
    assert selected[0].to_date > selected[1].to_date


def test_select_quarterly_filings_drops_future_broadcasts_for_point_in_time():
    rows = parse_financial_results(RAW_ITEMS)
    # as_of before the Q3 revision but after the original Consolidated broadcast: the revision must be
    # excluded and the original Consolidated filing used instead.
    selected = select_quarterly_filings(rows, as_of=date(2025, 2, 15))
    q3 = next(f for f in selected if f.to_date == date(2024, 12, 31))
    assert q3.xbrl_url.endswith("14022025081504.xml")


async def test_fetch_filings_bare_list_shape():
    class FakeClient:
        async def financial_results(self, symbol):
            assert symbol == "GLENMARK"
            return RAW_ITEMS

    filings = await fetch_filings(FakeClient(), "GLENMARK")
    assert len(filings) == 2


async def test_fetch_filings_wrapped_data_shape():
    class FakeClient:
        async def financial_results(self, symbol):
            return {"data": RAW_ITEMS}

    filings = await fetch_filings(FakeClient(), "GLENMARK")
    assert len(filings) == 2


async def test_fetch_filings_degrades_on_exception():
    class BoomClient:
        async def financial_results(self, symbol):
            raise RuntimeError("network down")

    filings = await fetch_filings(BoomClient(), "GLENMARK")
    assert filings == []


async def test_fetch_filings_respects_limit():
    class FakeClient:
        async def financial_results(self, symbol):
            return RAW_ITEMS

    filings = await fetch_filings(FakeClient(), "GLENMARK", limit=1)
    assert len(filings) == 1
