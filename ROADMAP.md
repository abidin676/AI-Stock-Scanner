# River Alpha Roadmap

## v1.5 Stabilization Sprint
- Scan coverage integrity for SET and USA routes.
- Explicit market status: SUCCESS / PARTIAL / FAILED / STALE / MISMATCH / NOT_REQUESTED.
- ScanRunId and output freshness validation across scanner, opportunity, priority, AI and risk outputs.
- Atomic runtime output writes to avoid mixed-run CSV/XLSX files.
- Opportunity score audit diagnostics.
- Pipeline funnel diagnostics for empty Buy/Watch queues.
- Queue consistency through central eligibility semantics.
- Permanent Fresh EMA9-over-EMA20 Cross policy for every main recommendation surface.
- Risk summary clarification for current exposure vs proposed additional exposure.
- Regression tests for scan routing, metadata, eligibility and pipeline alignment.

## Paper Trading Approval Automation

- SET-only execution scope for the first robot release.
- Existing Scanner, Candidate Eligibility, AI Decision, and Risk Manager rules remain authoritative and unchanged.
- Strict entry gate: Fresh EMA9-over-EMA20 cross age 0-2 trading bars, EMA9 above EMA20, BUY only, SET RVOL at least 1.5x, and no EXTENDED/SKIP or existing quality/risk block.
- Risk-approved proposals enter Approval Queue as PENDING; approval and simulated fill are two separate manual actions.
- No live broker connection, API, credential, or real-money order path. Paper Broker is locked to paper-only manual execution.
- Symbol + ScanRunId deduplication plus pre-proposal max-position, exposure, cash, and reserve controls.
- Stop loss, target, highest-price trailing stop, and exit triggers remain approval-gated throughout the paper position lifecycle.
- Unified Paper Trading dashboard for PENDING, APPROVED, FILLED, REJECTED, CANCELLED, EXPIRED, and hard-gate rejection reasons.
- Paper robot proposal and audit CSVs provide an explainable trace for every scanned candidate.

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
- FRESH CROSS (mandatory): EMA9 > EMA20 and cross age 0–2 daily trading bars. This hard gate applies to Today's Picks, Top 5 SET/USA, BUY, PREPARE, alert candidates, and Buy Queue.
- BUY: PriorityScore >= 70, RR >= 1.8, valid entry/stop/target, no hard block.
- PREPARE: SeedScore >= 80, PriorityScore >= 55, RR >= 1.5, early/base context.
- WATCH: OpportunityScore >= 45 or equivalent early watch context.
- AI confidence below 55 is a warning, not a duplicate hard veto.

Show all policy:
- `Show all` is diagnostic-only and cannot bypass the Fresh Cross gate.
- Crosses older than two trading bars remain visible as `Cross เก่า`; missing cross history is labeled `ยังไม่ Cross`.

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
