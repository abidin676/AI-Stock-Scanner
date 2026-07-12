# River Alpha Pipeline Stabilization

River Alpha v1.5 Stabilization focuses on making each scanner run traceable,
fresh, and explainable without changing trading logic or score formulas.

## Pipeline Stages

```text
Scanner
  -> Market Quality
  -> Opportunity Engine
  -> Priority Engine
  -> AI Decision Engine
  -> Candidate Eligibility
  -> Risk Manager
  -> Approval Queue
  -> Paper Broker
```

## Runtime Outputs

| Stage | Input | Output |
| --- | --- | --- |
| Scanner | market providers, price cache | `output/scanner_results.csv` |
| Market Quality | scanner rows | `output/market_quality.csv` |
| Opportunity Engine | scanner rows, market quality | `output/opportunity_results.csv` |
| Priority Engine | opportunities | `output/priority_results.csv` |
| AI Decision Engine | priority rows, portfolio | `output/ai_decisions.csv` |
| Risk Manager | AI decisions, portfolio/account context | `output/order_proposals.csv`, `output/risk_summary.csv` |
| Scan Metadata | scan timings and diagnostics | `output/scan_metadata.json`, `output/scan_run_manifest.json`, `output/scan_failures.csv` |

## ScanRunId Propagation

Each scanner run creates one `ScanRunId`. The same value must appear in:

- `scanner_results.csv`
- `market_quality.csv`
- `opportunity_results.csv`
- `priority_results.csv`
- `ai_decisions.csv`
- `order_proposals.csv`
- `risk_summary.csv`
- `scan_metadata.json`
- `scan_run_manifest.json`

If Dashboard finds different IDs across files, treat the data as stale or mixed.

## Market Status Meanings

| Status | Meaning |
| --- | --- |
| `SUCCESS` | All requested markets produced valid rows. |
| `PARTIAL` | At least one requested market produced rows, but one market or symbol subset failed. |
| `FAILED` | A requested market produced no valid rows. |
| `STALE` | Dashboard output files are older than the latest scan metadata or manifest. |
| `MISMATCH` | Runtime outputs do not share the same `ScanRunId`. |
| `NOT_REQUESTED` | The market was not part of the selected scan mode. |

`USA = 0` is valid only when USA is `NOT_REQUESTED`. If USA was requested and
has zero rows, Dashboard should show `FAILED` or `PARTIAL`, not market quality
`Avoid`.

## Candidate Eligibility Semantics

Central eligibility assigns one queue class per candidate:

- `BUY`: actionable candidate. Requires valid market, valid entry, no hard block,
  valid stop/target, PriorityScore >= 70 and RR >= 1.8.
- `PREPARE`: strong early-stage candidate, not actionable yet. Requires early/base
  context, SeedScore >= 80, PriorityScore >= 55 and RR >= 1.5.
- `WATCH`: monitor candidate that does not satisfy BUY/PREPARE.
- `IGNORE`: blocked or not useful for action.

Hard blocks include:

- missing symbol or invalid market
- missing or invalid entry price
- risk manager rejection
- extended/chasing setup
- scanner or lifecycle `SKIP`
- RR below hard minimum

Broad Ranking may show `SKIP` or `IGNORE` rows for diagnostics. Buy Queue and
Watch Queue must not treat those rows as actionable recommendations.

## Opportunity Score Diagnostics

Dashboard Opportunity Debug reports score source, min, median, mean, P90, max,
null count, zero count, market count, and lifecycle count.

Opportunity mean may look low when the table includes non-eligible rows. For
example, if many scanner rows are lifecycle `SKIP`, their OpportunityScore may
be zero by design. In that case the mean is not a scale bug; use the median,
zero count, lifecycle breakdown, and actionable queues to interpret the run.

## Troubleshooting USA = 0

1. Open `output/scan_metadata.json`.
2. Check `RequestedScanMode` and `ExpectedMarkets`.
3. If `USA` is expected, inspect:
   - `MarketDiagnostics.USA.Status`
   - `USASymbolsRequested`
   - `USASymbolsProcessed`
   - `USAError`
4. Open `output/scan_failures.csv` for failed symbols and reasons.
5. Verify Dashboard Pipeline Health shows USA as `SUCCESS`, `PARTIAL`, or
   `FAILED`. It should not show `N/A` when USA was requested.

## Troubleshooting Queue = 0

1. Open Dashboard -> Pipeline Health -> Funnel Summary.
2. Check where candidates drop:
   - Lifecycle/Base eligible
   - Opportunity score > 0
   - Priority score >= 55
   - AI BUY/PREPARE/WATCH
   - RR >= 1.5
   - Price/Stop/Target valid
   - Risk passed
3. Review top `BlockingReasons`.
4. If Scanner BUY exists but Buy Queue is empty, the rejection reasons must
   explain why. Common reasons are lifecycle `SKIP`, invalid stop/target,
   RR below minimum, or extended/chasing setup.
5. If AI WATCH exists but Watch Queue is empty, use `BlockingReasons` and
   `WarningReasons` to explain the gap.

## Risk Summary Labels

Risk Manager separates these concepts:

- Current portfolio exposure: existing open positions.
- Proposed additional exposure: valid new proposals only.
- Projected post-trade exposure: current plus valid proposed exposure.

When there are no actionable proposals, proposed additional exposure should be
zero even if current portfolio exposure is not zero.

## Output Atomicity

Runtime outputs are written to temporary files and atomically replaced. This
prevents a new partial run from mixing with old CSV/XLSX files.
