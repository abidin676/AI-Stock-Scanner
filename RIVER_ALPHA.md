# River Alpha

## Vision

River Alpha is an AI-powered Decision Support System for stock trading.

The objective is NOT to predict the market.

The objective is to identify high-quality trading opportunities using quantitative analysis.

---

# Core Philosophy

River Alpha is NOT:

* A TradingView clone
* An Indicator collection
* A Buy/Sell bot

River Alpha IS:

* A Feature Engine
* A Strategy Engine
* A Decision Engine

---

# Architecture

```
Market Data
    │
    ▼
Indicators
    │
    ▼
Derived Features
    │
    ▼
Feature Engine
    │
    ▼
Trend Engine
Momentum Engine
Volume Engine
Base Engine
Price Engine
    │
    ▼
Decision Engine
    │
    ▼
Dashboard
Alerts
Backtest
Portfolio
```

---

# Design Principles

## 1. Indicators are raw calculations

Examples:

* EMA
* RSI
* MACD
* ATR
* RVOL

Indicators never make decisions.

---

## 2. Derived Features describe the market

Examples:

* ema20_slope
* ema_alignment
* rsi_slope
* macd_hist_slope
* ema_compression

Derived Features are reusable.

---

## 3. Strategy Engines score one aspect only

Trend Engine

Evaluates trend quality.

Momentum Engine

Evaluates momentum quality.

Volume Engine

Evaluates participation.

Base Engine

Evaluates setup quality.

Price Engine

Evaluates entry quality.

Each engine is independent.

---

## 4. Decision Engine combines everything

Decision Engine never calculates indicators.

Decision Engine consumes engine outputs only.

Decision Engine produces:

* total_score
* confidence
* risk
* reward
* grade
* signal
* action

---

# Development Rules

Always prefer:

* Small commits
* Minimal patches
* Backward compatibility
* Vectorized pandas operations

Never:

* Duplicate calculations
* Recalculate existing indicators
* Rewrite large modules unnecessarily
* Mix business logic across engines

---

# Feature Pipeline

```
Indicator

↓

Derived Feature

↓

Engine Score

↓

Decision

↓

Action
```

Every calculation should appear only once.

---

# Signal Ladder

```
SKIP

↓

EARLY

↓

WATCH

↓

BUY

↓

STRONG BUY
```

---

# Quality Grades

```
AAA

AA

A

B

C

D
```

Signal and Grade are different concepts.

---

# Long-Term Roadmap

Phase 1

Indicators

✅ Complete

Phase 2

Derived Features

🚧 In Progress

Phase 3

Feature Engine

Phase 4

Decision Engine

Phase 5

Backtest Engine

Phase 6

Portfolio Manager

Phase 7

AI Ranking System

---

# Project Goal

Build a professional AI trading decision platform.

The scanner is only one component.

The Decision Engine is the product.
