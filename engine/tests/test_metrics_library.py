from next_signal.metrics.library import REGISTRY, compute, metrics_for


def test_registry_has_at_least_30_metrics():
    assert len(REGISTRY) >= 30


def test_receivable_days_known_value():
    # Revenue growth example from the brief's own worked example: receivable days computed from
    # revenue and receivables, rising from 28 to 46.
    v = compute("receivable_days", {"trade_receivables": 100.0, "revenue": 1200.0, "days_in_period": 365})
    assert v is not None
    assert round(v, 1) == round(100.0 / 1200.0 * 365, 1)


def test_missing_input_returns_none_never_imputes():
    assert compute("receivable_days", {"trade_receivables": 100.0}) is None


def test_fx_effect_decomposition():
    v = compute("fx_effect_us", {"us_rev_inr_yoy": 0.05, "us_rev_usd_yoy": -0.02})
    assert round(v, 4) == 0.07


def test_arpob_formula():
    v = compute("arpob", {
        "hospital_revenue": 2982_00_00_000.0,  # Rs 2,982 crore in rupees
        "operational_beds": 5000.0,
        "occupancy": 0.75,
        "days_in_period": 91,
    })
    assert v is not None and v > 0


def test_price_vs_volume_generic_metric_present_for_generic_playbook():
    ids = {m.metric_id for m in metrics_for("generic")}
    assert "price_vs_volume_growth" in ids


def test_division_by_zero_returns_none():
    assert compute("gross_margin", {"revenue": 0.0, "cogs": 10.0}) is None
