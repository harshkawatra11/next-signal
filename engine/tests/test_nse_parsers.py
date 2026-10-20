import httpx
import pytest
import respx

from next_signal.sources.nse import NSE, classify_kind, parse_nse_date


def test_classify_kind_results():
    assert classify_kind("Financial Results for the Quarter ended June 2026") == "results"


def test_classify_kind_usfda_before_results_when_both_present():
    # regulatory_usfda rule is checked before capacity/litigation; "warning letter" must win
    assert classify_kind("USFDA Warning Letter - Halol Facility") == "regulatory_usfda"


def test_classify_kind_capacity():
    assert classify_kind("Commissioning of new bed capacity at Hospital X") == "capacity"


def test_classify_kind_acquisition():
    assert classify_kind("Scheme of Amalgamation approved by NCLT") == "acquisition"


def test_classify_kind_falls_back_to_other():
    assert classify_kind("General updates for shareholders") == "other"


def test_parse_nse_date_with_time():
    d = parse_nse_date("22-Jul-2026 17:03:12")
    assert d is not None
    assert d.year == 2026 and d.month == 7 and d.day == 22


def test_parse_nse_date_date_only():
    d = parse_nse_date("05-Aug-2026")
    assert d is not None and d.day == 5


def test_parse_nse_date_invalid_returns_none():
    assert parse_nse_date("not a date") is None


@pytest.mark.asyncio
async def test_nse_api_refreshes_cookies_on_401_and_retries():
    """The whole point of NSE.api(): a 401/403 triggers exactly one cookie-refresh round, then one
    retry. This is the mechanism that keeps a live demo working when NSE's session cookie expires
    mid-run, and it must not loop forever or silently swallow a persistent failure."""
    async with httpx.AsyncClient() as client:
        with respx.mock(base_url="https://www.nseindia.com") as mock:
            mock.get("/").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get(path__regex=r"/get-quotes/equity.*").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get("/companies-listing/corporate-filings-announcements").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )
            calls = {"n": 0}

            def quote_side_effect(request):
                calls["n"] += 1
                if calls["n"] == 1:
                    return httpx.Response(401, json={"error": "session expired"})
                return httpx.Response(200, json={"info": {"symbol": "CIPLA"}})

            mock.get(path__regex=r"/api/quote-equity.*").mock(side_effect=quote_side_effect)

            nse = NSE(client=client)
            data = await nse.quote("CIPLA")
            assert data["info"]["symbol"] == "CIPLA"
            assert calls["n"] == 2  # one 401, one successful retry after cookie refresh


@pytest.mark.asyncio
async def test_nse_api_refreshes_cookies_on_timeout_and_retries():
    """A real research pass against the live NSE site found that a cold/expired session does not
    reliably return 401/403; it can simply hang until timeout on every NSE host tested. This must
    be treated the same as 401/403: one cookie refresh, one retry, not a bare failure."""
    async with httpx.AsyncClient() as client:
        with respx.mock(base_url="https://www.nseindia.com") as mock:
            mock.get("/").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get(path__regex=r"/get-quotes/equity.*").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get("/companies-listing/corporate-filings-announcements").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )
            calls = {"n": 0}

            def quote_side_effect(request):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise httpx.ReadTimeout("simulated cold-session hang")
                return httpx.Response(200, json={"info": {"symbol": "CIPLA"}})

            mock.get(path__regex=r"/api/quote-equity.*").mock(side_effect=quote_side_effect)

            nse = NSE(client=client)
            data = await nse.quote("CIPLA")
            assert data["info"]["symbol"] == "CIPLA"
            assert calls["n"] == 2  # one timeout, one successful retry after cookie refresh


@pytest.mark.asyncio
async def test_nse_api_raises_after_persistent_failure():
    async with httpx.AsyncClient() as client:
        with respx.mock(base_url="https://www.nseindia.com") as mock:
            mock.get("/").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get(path__regex=r"/get-quotes/equity.*").mock(return_value=httpx.Response(200, text="<html></html>"))
            mock.get("/companies-listing/corporate-filings-announcements").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )
            mock.get(path__regex=r"/api/quote-equity.*").mock(return_value=httpx.Response(403))

            nse = NSE(client=client)
            with pytest.raises(httpx.HTTPStatusError):
                await nse.quote("CIPLA")
