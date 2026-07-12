# River Alpha Roadmap

## v1.5 Stabilization Sprint
- Scan coverage integrity for SET and USA routes.
- Explicit market status: SUCCESS / PARTIAL / FAILED / STALE / MISMATCH / NOT_REQUESTED.
- ScanRunId and output freshness validation across scanner, opportunity, priority, AI and risk outputs.
- Atomic runtime output writes to avoid mixed-run CSV/XLSX files.
- Opportunity score audit diagnostics.
- Pipeline funnel diagnostics for empty Buy/Watch queues.
- Queue consistency through central eligibility semantics.
- Risk summary clarification for current exposure vs proposed additional exposure.
- Regression tests for scan routing, metadata, eligibility and pipeline alignment.

Known test debt not included in v1.5 scope:
- `test/test_backtest.py` still calls the legacy `run_backtest()` signature.
- `test_strategy.py` collides with `test/test_strategy.py` during pytest collection.

## v2.3
- Dashboard UI frozen
- Scanner UI future changes: bug fixes only

## Future Focus
- Portfolio AI
- Alert Engine
- Auto Watchlist
- Backtest improvements
- Risk Manager
- Notification System

## v3.1
- AI Decision Engine Phase 1 — Explainable deterministic decision layer
- Decision support only, no broker execution
- Prepared for Paper Trading, Risk Manager, and future broker integrations
- Risk Manager Phase 1 — Position sizing, portfolio constraints and approval-gated order proposals
- Approval Queue Phase 1 — Manual approval gate before Paper Broker integration
- Paper Broker Phase 1 — Deterministic simulated execution, trade ledger and paper portfolio
- Paper Broker Phase 2 — Controlled paper order lifecycle, audit events and portfolio controls

## Decision Pipeline Alignment Phase 1
- Central eligibility policy for BUY / PREPARE / WATCH / IGNORE.
- PREPARE queue class for strong early-stage setups that are not actionable yet.
- USA scan diagnostics for requested, loaded, no-data, cache/download, errors and status.
- ScanRunId propagation across scanner, opportunity, priority, AI and risk outputs.
- Buy Queue and Watch Queue aligned to the same policy result.
- Risk projected exposure corrected to use valid proposals only.

Policy defaults:
- BUY: PriorityScore >= 70, RR >= 1.8, valid entry/stop/target, no hard block.
- PREPARE: SeedScore >= 80, PriorityScore >= 55, RR >= 1.5, early/base context.
- WATCH: OpportunityScore >= 45 or equivalent early watch context.
- AI confidence below 55 is a warning, not a duplicate hard veto.

Remaining Phase 2 work:
- Calibrate thresholds with recommendation history and scorecard evidence.
- Add richer per-symbol provider failure telemetry where data providers expose it.
- Expand ScanRunId checks to every dashboard page that reads runtime outputs.

## v1.0
- Stable Scanner
- Portfolio
- Strategy Lab

## v1.1
- Strategy Optimizer
- Strategy Presets

## v1.2
- Confidence Engine
- AI Ranking

## v1.3
- LINE Notification
- Remote Dashboard
