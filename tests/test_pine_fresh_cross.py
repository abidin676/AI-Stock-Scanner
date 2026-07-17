from pathlib import Path


PINE_FILE = Path("tradingview") / "river_alpha_early_trend.pine"


def pine_source():
    return PINE_FILE.read_text(encoding="utf-8")


def test_pine_uses_same_real_bullish_crossover_definition_as_python():
    source = pine_source()

    assert (
        "bullishCross = emaFast > emaSlow and emaFast[1] <= emaSlow[1]"
        in source
    )
    assert "barsSinceCross = ta.barssince(bullishCross)" in source
    assert "crossTime = ta.valuewhen(bullishCross, time, 0)" in source


def test_pine_fresh_limit_is_locked_and_cannot_be_changed_by_input():
    source = pine_source()

    assert "int maxFreshBars = 2" in source
    assert "Maximum bars since bullish cross" not in source
    assert "freshCross and trendOK" in source


def test_pine_displays_cross_date_latest_bar_and_live_bar_state():
    source = pine_source()

    assert 'str.format_time(crossTime, "yyyy-MM-dd"' in source
    assert 'str.format_time(time, "yyyy-MM-dd"' in source
    assert 'barstate.isconfirmed ? "Confirmed" : "Live"' in source
    assert '"Cross date"' in source
    assert '"Latest bar"' in source
