# River Alpha Scanner

River Alpha Scanner is a Fresh EMA9-over-EMA20 Cross Scanner for SET and US markets. Its main recommendations only include symbols where EMA9 is currently above EMA20 and the bullish cross occurred within the latest 0–2 daily trading bars. It combines market data, indicators, modular strategy engines, portfolio tracking, watchlists, alerts, and a Strategy Lab for backtesting ideas.

This project is designed as a decision-support tool, not an automated trading bot or financial advice.

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

## Permanent Fresh Cross Policy

- `MAX_FRESH_CROSS_DAYS = 2` is the standard policy limit.
- Cross age is counted from daily trading bars, not calendar days.
- Cross age starts only on a real bullish crossover bar: `EMA9 > EMA20` while the previous bar had `EMA9 <= EMA20`. EMA9 merely being above EMA20 never implies age 0.
- Today's Picks, Top 5 SET/USA, BUY, PREPARE, alert candidates, and Buy Queue always require a Fresh EMA9-over-EMA20 Cross aged 0, 1, or 2 trading days.
- AI Score, Volume, and RVOL cannot override the Fresh Cross gate.
- Scanner Results can display all symbols through `Show all`, but non-fresh rows are diagnostic only and are labeled `Cross เก่า`, `ยังไม่ Cross`, or `EMA9 ต่ำกว่า EMA20`.
- No dashboard toggle promotes a non-fresh row into a main recommendation.
- Scanner output includes `LatestPriceDate` and `CrossDate` so provider-confirmed daily data can be compared with TradingView's potentially live daily bar. The matching Pine reference is `tradingview/river_alpha_early_trend.pine`.

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
