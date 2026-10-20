from next_signal.metrics.series import resolve_inputs, with_derived_items

RAW = {
    "Q1FY27": {"revenue": 6142.0, "materials": 2200.0, "purchases": 183.1, "inventory_change": 0.0,
               "pbt_before_exceptional": 1428.0, "finance_costs": 24.0, "dna": 196.0, "other_income": 103.0,
               "pbt": 1428.0, "pat": 1088.0, "tax_expense": 340.0},
    "Q1FY26": {"revenue": 5467.0, "materials": 1986.3, "purchases": 0.0, "inventory_change": 0.0,
               "pbt_before_exceptional": 1298.0, "finance_costs": 19.0, "dna": 181.0, "other_income": 79.0,
               "pbt": 1298.0, "pat": 990.0, "tax_expense": 308.0},
    "Q4FY26": {"revenue": 5894.0, "materials": 2234.6, "purchases": 0.0, "inventory_change": 0.0,
               "pbt_before_exceptional": 1392.0, "finance_costs": 22.0, "dna": 191.0, "other_income": 97.0,
               "pbt": 1392.0, "pat": 1061.0, "tax_expense": 331.0},
    # Q3FY26 deliberately missing one derived-item input (no "dna"), to test a period that cannot
    # produce ebitda but can still produce cogs.
    "Q3FY26": {"revenue": 5721.0, "materials": 2099.4, "purchases": 0.0, "inventory_change": 0.0,
               "pbt": 1371.0, "pat": 1046.0, "tax_expense": 325.0},
}


def test_with_derived_items_computes_cogs_when_inputs_present():
    out = with_derived_items(RAW)
    assert out["Q1FY27"]["cogs"] == 2200.0 + 183.1 + 0.0


def test_with_derived_items_computes_ebitda_when_inputs_present():
    out = with_derived_items(RAW)
    expected = 1428.0 + 24.0 + 196.0 - 103.0
    assert out["Q1FY27"]["ebitda"] == expected


def test_with_derived_items_skips_ebitda_when_an_input_is_missing():
    out = with_derived_items(RAW)
    assert "ebitda" not in out["Q3FY26"]
    assert "cogs" in out["Q3FY26"]  # cogs' own inputs are all present for this period


def test_with_derived_items_preserves_original_values():
    out = with_derived_items(RAW)
    assert out["Q1FY27"]["revenue"] == 6142.0


def test_resolve_inputs_same_period_name():
    out = with_derived_items(RAW)
    resolved = resolve_inputs(out, "Q1FY27", ["revenue", "cogs"])
    assert resolved == {"revenue": 6142.0, "cogs": 2383.1}


def test_resolve_inputs_t_suffix_maps_to_same_period():
    resolved = resolve_inputs(RAW, "Q1FY27", ["revenue_t"])
    assert resolved == {"revenue_t": 6142.0}


def test_resolve_inputs_t_minus_4q_resolves_by_calendar_not_position():
    # Q1FY27's same quarter one year earlier is Q1FY26, not whatever happens to sort earlier in a dict.
    resolved = resolve_inputs(RAW, "Q1FY27", ["revenue_t", "revenue_t_minus_4q"])
    assert resolved == {"revenue_t": 6142.0, "revenue_t_minus_4q": 5467.0}


def test_resolve_inputs_t_minus_1q_resolves_the_immediately_preceding_quarter():
    resolved = resolve_inputs(RAW, "Q1FY27", ["revenue_t", "revenue_t_minus_1q"])
    assert resolved == {"revenue_t": 6142.0, "revenue_t_minus_1q": 5894.0}  # Q4FY26


def test_resolve_inputs_returns_none_when_the_lagged_period_is_missing():
    # Q4FY26's t_minus_4q would be Q4FY25, which is not in RAW at all.
    resolved = resolve_inputs(RAW, "Q4FY26", ["revenue_t", "revenue_t_minus_4q"])
    assert resolved is None


def test_resolve_inputs_returns_none_when_the_base_item_is_missing_in_the_target_period():
    # Q3FY26 has no "dna"; asking for dna_t at Q3FY26 must fail cleanly, not silently return nothing.
    resolved = resolve_inputs(RAW, "Q3FY26", ["dna_t"])
    assert resolved is None


def test_resolve_inputs_returns_none_for_unrecognised_period_string():
    resolved = resolve_inputs(RAW, "FY26", ["revenue_t_minus_4q"])
    assert resolved is None


def test_resolve_inputs_never_confuses_t_minus_4q_suffix_with_bare_t():
    # A naive suffix check using "endswith('_t')" before checking the longer suffixes would wrongly
    # strip only the trailing "t" off "revenue_t_minus_4q" and look up a nonsense base item name.
    resolved = resolve_inputs(RAW, "Q1FY27", ["revenue_t_minus_4q"])
    assert resolved == {"revenue_t_minus_4q": 5467.0}
