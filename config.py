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
