from next_signal.llm.guards import BANNED_INVEST, copy_issues, numbers_in, stray_numbers


def test_indian_grouping_normalised_number_allowed():
    allowed = {"151836"}
    text = "Revenue stood at Rs 1,51,836 million for the quarter."
    assert stray_numbers(text, allowed) == []


def test_missing_number_is_flagged():
    allowed = {"151836"}
    text = "Revenue grew 14.2 percent year on year."
    hits = stray_numbers(text, allowed)
    assert "14.2" in hits


def test_period_label_has_no_numbers_falsely_flagged():
    # Q1 FY27 contains digits "1" and "27" - caller must pre-seed allowed with small constants (0-10, years)
    allowed = numbers_in("Q1 FY27") | {str(i) for i in range(0, 11)} | {str(y) for y in range(1990, 2036)}
    text = "This was reported in Q1 FY27."
    assert stray_numbers(text, allowed) == []


def test_investment_language_banned():
    assert BANNED_INVEST.search("We recommend buying the stock now")
    assert BANNED_INVEST.search("Our target price is Rs 1500")
    assert not BANNED_INVEST.search("The company's revenue target for the year is Rs 1500 crore")


def test_copy_issues_detects_dash_and_exclamation():
    assert "dash" in copy_issues("Revenue grew — sharply.")
    assert "exclamation" in copy_issues("This is a huge discovery!")
    assert copy_issues("Revenue grew by 10 percent this quarter.") == []


def test_copy_issues_detects_investment_language():
    assert "investment language" in copy_issues("Investors should buy the stock immediately.")
