"""
River Alpha Market Profiles

All market-specific configuration lives here.

Markets
--------
- SET
- USA

Future
------
- Crypto
- Forex
- HKEX
"""

MARKET_PROFILES = {

    "SET": {

        "thresholds": {
            "BUY": 70,
            "WATCH": 60,
            "EARLY": 50,
        },

        "filters": {
            "max_distance_ema20": 0.10,
            "max_rsi": 80,
            "max_move_from_low90": 100,
            "allow_stage1": True,
        },

        "weights": {
            "trend": 25,
            "momentum": 20,
            "volume": 15,
            "base": 10,
            "price": 5,
            "stage": 15,
            "breakout": 10,
        },

        "trend": {
            "ema20_ema50": 10,
            "ema50_ema200": 5,
            "ema20_slope": 8,
            "ema50_slope": 5,
            "higher_low": 6,
            "higher_high": 2,
            "trend_change": 5,
        },
        "RVOL_STRONG": 1.5,
        "RVOL_GOOD": 1.2,
        
        "momentum": {

            "fresh_cross": 10,
            "recent_cross": 5,

            "ema9_above": 5,

            "macd_cross": 3,
            "macd_hist": 2,

            "rsi_strong": 5,
            "rsi_recover": 2,
        },
        

    },

    "USA": {

        "thresholds": {
            "BUY": 68,
            "WATCH": 60,
            "EARLY": 50,
        },

        "filters": {
            "max_distance_ema20": 0.08,
            "max_rsi": 75,
            "max_move_from_low90": 80,
            "allow_stage1": False,
        },

        "weights": {
            "trend": 25,
            "momentum": 20,
            "volume": 15,
            "base": 10,
            "price": 5,
            "stage": 15,
            "breakout": 10,
        },

        "trend": {
            "ema20_ema50": 6,
            "ema50_ema200": 6,
            "ema20_slope": 5,
            "ema50_slope": 5,
            "higher_low": 3,
            "higher_high": 2,
            "trend_change": 3,
        },
        "RVOL_STRONG": 2.0,
        "RVOL_GOOD": 1.5,
        
        "momentum": {

            "fresh_cross": 10,
            "recent_cross": 5,

            "ema9_above": 5,

            "macd_cross": 3,
            "macd_hist": 2,

            "rsi_strong": 5,
            "rsi_recover": 2,
        },

    }

}


def get_profile(market: str):

    """
    Return market profile.

    Defaults to USA.
    """

    return MARKET_PROFILES.get(
        market.upper(),
        MARKET_PROFILES["USA"],
    )
