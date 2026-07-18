# River Alpha Scanner

River Alpha Scanner is a Fresh EMA9-over-EMA20 Cross Scanner for SET and US markets. Its main recommendations only include symbols where EMA9 is currently above EMA20 and the bullish cross occurred within the latest 0–2 daily trading bars. It combines market data, indicators, modular strategy engines, portfolio tracking, watchlists, alerts, and a Strategy Lab for backtesting ideas.

This project is a decision-support scanner with an approval-gated Paper Trading Robot. It never connects to a real broker or sends real-money orders, and it is not financial advice.

## Release Status

- Version: River Alpha v2.3
- Status: Dashboard UI Frozen
- Future Scanner UI changes: bug fixes only

## Features

- Scanner for SET, US100, S&P 500, and Dow 30 watchlists
- Modular decision architecture: Trend, Momentum, Volume, Base, Breakout, Price, Stage, Quality Gate, and Signal Engine
- Market Quality Score for SET and USA after each scan
- Streamlit dashboard with filters, market summary, top SET/USA candidates, and scanner results
- Seed-focused Dashboard with AI Pick Today, Top 5 SET/USA Seed cards, Buy Queue, and Market Quality recommendations
- Watchlist workflow with notes, status, stop loss, target, and alerts
- Portfolio Manager with SET/USA fee support and THB summary
- Strategy Lab with backtest trades, equity curve, monthly returns, benchmark comparison, and run history
- CSV/XLSX outputs for dashboard compatibility
- SET-only Paper Trading Robot with strict Scanner hard gates, Risk Manager sizing, manual Approval Queue control, and simulated Paper Broker fills

## Permanent Fresh Cross Policy

- `MAX_FRESH_CROSS_DAYS = 2` is the standard policy limit.
- Cross age is counted from daily trading bars, not calendar days.
- Cross age starts only on a real bullish crossover bar: `EMA9 > EMA20` while the previous bar had `EMA9 <= EMA20`. EMA9 merely being above EMA20 never implies age 0.
- Today's Picks, Top 5 SET/USA, BUY, PREPARE, alert candidates, and Buy Queue always require a Fresh EMA9-over-EMA20 Cross aged 0, 1, or 2 trading days.
- AI Score, Volume, and RVOL cannot override the Fresh Cross gate.
- Scanner Results can display all symbols through `Show all`, but non-fresh rows are diagnostic only and are labeled `Cross เก่า`, `ยังไม่ Cross`, or `EMA9 ต่ำกว่า EMA20`.
- No dashboard toggle promotes a non-fresh row into a main recommendation.
- Scanner output includes `LatestPriceDate` and `CrossDate` so provider-confirmed daily data can be compared with TradingView's potentially live daily bar. The matching Pine reference is `tradingview/river_alpha_early_trend.pine`.
- `output/fresh_cross_candidates.csv` is the canonical eligible universe. Top 5 SET/USA are deterministic rankings taken from this set; they do not define or truncate the universe.
- Canonical ranking sorts by cross age (Today, 1D, 2D), then AI score descending, priority score descending, and symbol ascending as the deterministic tie-breaker.
- `output/candidate_ranking_audit.csv` records every symbol's cross provenance, hard-gate result, canonical rank, Top 5 inclusion, and one primary exclusion reason.

## Paper Trading Robot

The first execution scope is SET and is permanently paper-only. The robot reuses the existing pipeline in this order:

`Scanner -> Candidate Eligibility -> AI Decision -> Risk Manager -> Approval Queue -> Paper Broker`

- Entry proposals require every Scanner hard gate, a canonical Fresh Cross aged 0-2 trading bars, `EMA9 > EMA20`, AI decision `BUY`, SET `RVOL >= 1.5x`, and no `EXTENDED`, `SKIP`, trend, liquidity, market-quality, or risk block.
- Score and priority only rank candidates; they cannot bypass a hard gate.
- A Risk Manager pass creates `PENDING` only. No order is filled until a user explicitly clicks `Approve` and then confirms `Fill Paper Order` on the Paper Trading dashboard.
- Duplicate proposals are blocked by `Symbol + ScanRunId`. Max positions, total exposure, available cash, and cash reserve are checked before a pending proposal is created.
- Filled paper positions track the configured stop loss, target, highest price, and trailing stop. Exit triggers create a new pending exit proposal and still require manual approval and fill.
- Safety config is locked to `paper_only=true` and `execution_mode=MANUAL`; the Paper Broker only creates simulated `MARKET_SIMULATED` orders.
- `output/paper_trading_robot_audit.csv` records every accepted or excluded candidate and its primary reason. `output/paper_trading_robot_proposals.csv` records robot proposals passed to Risk Manager/Approval Queue.

## Screenshot

![River Alpha Scanner dashboard](docs/screenshots/scanner.png)

## Installation

```powershell
git clone https://github.com/abidin676/AI-Stock-Scanner.git
cd AI-Stock-Scanner

python -m venv venv
.\venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

On Windows, double-click `AI Stock Scanner.bat` for the normal daily workflow. The launcher always waits for a fresh SET + USA scan (`--mode ALL --force-refresh`) to finish successfully before it opens the Dashboard. If the scan fails, the Dashboard is not opened and the launcher shows the error.

Double-click `Open Dashboard Only.bat` only when you intentionally want to view the last successful output without running a new scan. Both launchers reuse an existing River Alpha Streamlit process when possible instead of starting duplicate Dashboard processes.

To run the scanner manually:

```powershell
python scanner.py --mode ALL --force-refresh
```

Start the dashboard:

```powershell
python -m streamlit run dashboard.py
```

Benchmark scanner performance:

```powershell
python tools/benchmark_scanner.py --workers 8
```

Then open:

```text
http://localhost:8501
```

## Main Outputs

- `output/scanner_results.csv`
- `output/scanner_results.xlsx`
- `output/fresh_cross_candidates.csv`
- `output/candidate_ranking_audit.csv`
- `output/paper_trading_robot_audit.csv`
- `output/paper_trading_robot_proposals.csv`
- `output/market_quality.csv`
- `data/watchlist.csv`
- `data/portfolio.csv`
- `data/strategy_history.csv`
- `output/strategy_lab_trades.csv`
- `output/strategy_lab_summary.csv`
- `output/strategy_lab_equity.csv`
- `output/strategy_lab_monthly.csv`
- `output/strategy_lab_benchmark.csv`

## Project Structure

```text
scanner.py
data.py
indicators.py
strategy.py
strategy_engine/
views/
dashboard.py
watchlist.py
portfolio.py
backtest_engine.py
strategy_history.py
market_quality.py
```

## Project Docs

- [About](ABOUT.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [License](LICENSE)

## Notes

River Alpha runs locally and stores portfolio, watchlist, scanner, and Strategy Lab files on your machine. Review every signal manually before making any trading decision.
