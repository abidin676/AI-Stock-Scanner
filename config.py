"""
AI Stock Scanner Configuration
"""

# ==========================================
# Markets
# ==========================================

# เลือกตลาดที่จะสแกน
#
# ตัวเลือก:
# SET50
# SET100
# US100
# SP500
# ALL

SCAN_MARKETS = [
    ("SET", "SET"),
    ("US100", "USA"),
    ("SP500", "USA"),
    ("DOW30", "USA"),
]

# ==========================================
# Data
# ==========================================

PERIOD = "1y"
INTERVAL = "1d"

# ==========================================
# Output
# ==========================================

OUTPUT_FOLDER = "output"

CSV_FILE = "scanner_results.csv"

EXCEL_FILE = "scanner_results.xlsx"

# ==========================================
# Strategy
# ==========================================

MIN_SCORE = 70

# Maximum number of daily trading bars since EMA9 crossed above EMA20
# for a candidate to be considered a fresh cross.
MAX_FRESH_CROSS_DAYS = 2

# Market-specific relative-volume gates for actionable candidates.  Keep these
# values centralized so scanner, AI, queues, alerts, ranking, and dashboard all
# use the same definition of PREPARE and BUY.
MARKET_RVOL_THRESHOLDS = {
    "SET": {
        "PREPARE": 1.0,
        "BUY": 1.5,
    },
    "USA": {
        "PREPARE": 0.8,
        "BUY": 1.2,
    },
}


def normalize_rvol_market(market):
    """Return the supported market key, defaulting conservatively to SET."""

    value = str(market or "").strip().upper()
    if value in {"USA", "US", "US100", "SP500", "DOW30"}:
        return "USA"
    return "SET"


def rvol_thresholds_for_market(market):
    """Return a copy of the PREPARE/BUY RVOL thresholds for one market."""

    return MARKET_RVOL_THRESHOLDS[normalize_rvol_market(market)].copy()


def rvol_action_for_market(market, rvol):
    """Classify RVOL without allowing volume to bypass any other hard gate."""

    try:
        value = float(rvol)
    except (TypeError, ValueError):
        value = 0.0

    thresholds = rvol_thresholds_for_market(market)
    if value >= thresholds["BUY"]:
        return "BUY"
    if value >= thresholds["PREPARE"]:
        return "PREPARE"
    return "WATCH"

SHOW_ONLY = [
    "EARLY BUY",
    "WATCH",
]

# ==========================================
# Scanner
# ==========================================

VERBOSE = True

SAVE_EXCEL = True

SAVE_CSV = True

# ==========================================
# Future
# ==========================================

USE_CACHE = False

MAX_WORKERS = 8

# ===============================
# Backtest
# ===============================

LOOKBACK = 250
MAX_HOLD = 20

STOP_LOSS = -8
TAKE_PROFIT = 30

# ===============================
# Portfolio
# ===============================

START_CAPITAL = 100000
RISK_PER_TRADE = 1.0


# ==========================
# Portfolio
# ==========================

START_CAPITAL = 100000

MAX_POSITIONS = 5

POSITION_SIZE = 0.20      # 20%

RISK_PER_TRADE = 1.0
