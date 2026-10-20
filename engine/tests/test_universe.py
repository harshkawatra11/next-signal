from next_signal.universe import (
    UniverseRow,
    peers,
    playbook_for,
    resolve_offline,
    track_d_n50,
    track_d_tiebreak,
)

# "industry" here reflects NSE's finer-grained basicIndustry text (as the live quote-equity API returns
# it), not the coarse "Industry" column of the index-constituent CSV (which just says "Healthcare" for
# all five Track D names and would be useless for playbook routing). track_d_n50 below filters on that
# coarse CSV-level label (which IS "Healthcare" in the real list files); playbook_for operates on the
# finer label that a live enrichment call adds, which is what these fixture rows represent.
FIXTURE = {
    "nifty50": [
        UniverseRow("SUN PHARMACEUTICAL INDUSTRIES LTD.", "Healthcare", "SUNPHARMA", "INE044A01036", "nifty50"),
        UniverseRow("CIPLA LTD.", "Healthcare", "CIPLA", "INE059A01026", "nifty50"),
        UniverseRow("DR. REDDY'S LABORATORIES LTD.", "Healthcare", "DRREDDY", "INE089A01023", "nifty50"),
        UniverseRow("APOLLO HOSPITALS ENTERPRISE LTD.", "Healthcare", "APOLLOHOSP", "INE437A01024", "nifty50"),
        UniverseRow("MAX HEALTHCARE INSTITUTE LTD.", "Healthcare", "MAXHEALTH", "INE027H01010", "nifty50"),
        UniverseRow("HDFC BANK LTD.", "Financial Services", "HDFCBANK", "INE040A01034", "nifty50"),
    ],
    "niftypharma": [
        UniverseRow("LUPIN LTD.", "Pharmaceuticals & Biotechnology", "LUPIN", "INE326A01037", "niftypharma"),
        UniverseRow("ZYDUS LIFESCIENCES LTD.", "Pharmaceuticals & Biotechnology", "ZYDUSLIFE", "INE010B01027", "niftypharma"),
        UniverseRow("SUN PHARMACEUTICAL INDUSTRIES LTD.", "Pharmaceuticals & Biotechnology", "SUNPHARMA", "INE044A01036", "niftypharma"),
    ],
    "niftyhealthcare": [
        UniverseRow("FORTIS HEALTHCARE LTD.", "Healthcare Services", "FORTIS", "INE061F01013", "niftyhealthcare"),
        UniverseRow("APOLLO HOSPITALS ENTERPRISE LTD.", "Healthcare Services", "APOLLOHOSP", "INE437A01024", "niftyhealthcare"),
    ],
}

# For the fine-grained playbook/peers tests below, use a richer per-symbol industry map (simulating what
# pipeline/resolve.py would have after a live NSE quote-equity enrichment call), rather than relying on
# the coarse "Healthcare" label alone.
FINE_INDUSTRY = {
    "SUNPHARMA": "Pharmaceuticals & Biotechnology",
    "CIPLA": "Pharmaceuticals & Biotechnology",
    "DRREDDY": "Pharmaceuticals & Biotechnology",
    "APOLLOHOSP": "Healthcare Services",
    "MAXHEALTH": "Healthcare Services",
    "HDFCBANK": "Financial Services",
}


def _enrich(universe):
    """Return a copy of the universe with each row's industry field replaced by its fine-grained label."""
    out = {}
    for key, rows in universe.items():
        out[key] = [
            UniverseRow(r.company_name, FINE_INDUSTRY.get(r.symbol, r.industry), r.symbol, r.isin, r.source_index)
            for r in rows
        ]
    return out


def test_track_d_n50_filters_healthcare_industry_only():
    rows = track_d_n50(FIXTURE)
    symbols = {r.symbol for r in rows}
    assert symbols == {"SUNPHARMA", "CIPLA", "DRREDDY", "APOLLOHOSP", "MAXHEALTH"}
    assert "HDFCBANK" not in symbols


def test_track_d_tiebreak_excludes_n50_members():
    rows = track_d_tiebreak(FIXTURE)
    symbols = {r.symbol for r in rows}
    assert "SUNPHARMA" not in symbols  # already in NIFTY 50
    assert "APOLLOHOSP" not in symbols  # already in NIFTY 50
    assert "LUPIN" in symbols
    assert "FORTIS" in symbols


def test_playbook_for_pharma():
    assert playbook_for("Pharmaceuticals") == "pharma"
    assert playbook_for("Biotechnology") == "pharma"


def test_playbook_for_hospital():
    assert playbook_for("Healthcare Services", "Hospital") == "hospital"


def test_playbook_for_diagnostics():
    assert playbook_for("Healthcare Facilities", "Diagnostics") == "diagnostics"


def test_playbook_for_generic_fallback_unknown_company():
    # Must work for any company, not just the five we researched - this is the no-hard-coding mechanism.
    assert playbook_for("Steel") == "generic"
    assert playbook_for("Information Technology") == "generic"


def test_resolve_offline_by_symbol():
    ident = resolve_offline("CIPLA", FIXTURE)
    assert ident is not None
    assert ident.symbol == "CIPLA"
    assert ident.playbook == "pharma" or ident.playbook == "generic"
    assert ident.in_nifty50 is True


def test_resolve_offline_by_fuzzy_name():
    ident = resolve_offline("Dr Reddys Laboratories", FIXTURE)
    assert ident is not None
    assert ident.symbol == "DRREDDY"


def test_resolve_offline_tiebreak_company_not_in_n50():
    ident = resolve_offline("LUPIN", FIXTURE)
    assert ident is not None
    assert ident.in_nifty50 is False


def test_resolve_offline_unknown_returns_none():
    assert resolve_offline("ZZZZZZZZZ NOT A REAL COMPANY", FIXTURE) is None


def test_peers_same_playbook_excludes_subject():
    caps = {"CIPLA": 1000.0, "SUNPHARMA": 1200.0, "DRREDDY": 900.0, "HDFCBANK": 50000.0}
    result = peers("CIPLA", _enrich(FIXTURE), caps, k=5)
    assert "CIPLA" not in result
    assert "HDFCBANK" not in result  # different playbook (financial services vs pharma)
    assert "SUNPHARMA" in result or "DRREDDY" in result
