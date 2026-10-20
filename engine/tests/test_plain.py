from datetime import date

from next_signal import plain
from next_signal.schemas import Falsification


def test_indian_group():
    assert plain.indian_group(123456.78, 1) == "1,23,456.8"


def test_metric_phrase_override():
    assert "US dollars" in plain.metric_phrase("us_rev_usd_yoy")


def test_value_phrase_gross_margin():
    assert plain.value_phrase("gross_margin", 0.4213) == "42.1 per cent"


def test_scrub_identifiers():
    out = plain.scrub_identifiers("the us_rev_usd_yoy moved")
    assert "_" not in out


def test_falsification_plain():
    f = Falsification(
        statement="x",
        metric_id="gross_margin",
        comparator=">=",
        threshold=0.42,
        periods_required=2,
        next_check=date(2026, 7, 22),
        check_source="quarterly results",
    )
    out = plain.falsification_plain(f, "Cipla Limited")
    assert "rises to or above" in out
    assert ">=" not in out


def test_angle_question():
    assert plain.angle_question("P9").startswith("Is there a hidden")
