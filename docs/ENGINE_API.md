# River Alpha Engine API Standard

Version: 1.0

---

# Purpose

This document defines the standard API contract for every analysis engine inside River Alpha.

Goals:

* One consistent interface
* Explainable outputs
* No duplicated logic
* Backward compatible
* Easy to extend

Every engine should consume facts only and return structured results.

---

# Standard Return Object

Every engine must return a dictionary.

```python
{
    "engine": str,
    "score": int,
    "max_score": int,
    "quality": str,
    "reasons": list[str],
}
```

Field descriptions

| Field     | Description                               |
| --------- | ----------------------------------------- |
| engine    | Engine name                               |
| score     | Current score                             |
| max_score | Maximum possible score                    |
| quality   | EXCELLENT / STRONG / GOOD / NORMAL / WEAK |
| reasons   | Human-readable explanations               |

---

# Trend Engine

File

```
strategy_engine/trend.py
```

Function

```python
trend_score(last)
```

Consumes

* ema20
* ema50
* ema200
* ema20_slope
* ema50_slope
* higher_low
* higher_high
* trend_change

Returns

```python
{
    "engine": "trend",
    "score": int,
    "max_score": 30,
    "quality": str,
    "reasons": list[str],
}
```

---

# Momentum Engine

File

```
strategy_engine/momentum.py
```

Function

```python
momentum_score(
    last,
    df,
    ema_cross_func,
)
```

Consumes

* ema9
* ema20
* macd
* macd_signal
* macd_hist
* rsi

Returns

```python
{
    "engine": "momentum",
    "score": int,
    "max_score": 25,
    "quality": str,
    "reasons": list[str],
}
```

---

# Volume Engine

File

```
strategy_engine/volume.py
```

Function

```python
volume_score(last)
```

Consumes

* rvol
* dry_volume

Returns

```python
{
    "engine": "volume",
    "score": int,
    "max_score": 20,
    "quality": str,
    "reasons": list[str],
}
```

---

# Base Engine

File

```
strategy_engine/base.py
```

Function

```python
base_score(last)
```

Consumes

* ema_compression
* atr_compression
* dry_volume
* move_from_low90

Returns

```python
{
    "engine": "base",
    "score": int,
    "max_score": 15,
    "quality": str,
    "reasons": list[str],
}
```

---

# Quality Gate

File

```
strategy_engine/quality_gate.py
```

Function

```python
quality_gate(
    trend,
    momentum,
    volume,
    base,
    price_score,
)
```

Returns

```python
{
    "engine": "quality_gate",
    "passed": bool,
    "grade": str,
    "reasons": list[str],
}
```

Purpose

Acts as a filter.

Does NOT calculate trading signals.

---

# Stage Engine

File

```
strategy_engine/score.py
```

Function

```python
calculate_score(df)
```

Recommended return format

```python
{
    "engine": "stage",
    "score": int,
    "reasons": list[str],
}
```

Purpose

Evaluates market stage only.

---

# Signal Engine

File

```
strategy_engine/signal.py
```

Function

```python
build_signal(score)
```

Recommended return format

```python
{
    "engine": "signal",
    "signal": str,
    "passed": bool,
}
```

Purpose

Maps total score into a trading signal.

Does NOT calculate scores.

---

# Decision Engine

File

```
strategy_engine/decision_engine.py
```

Purpose

Acts as an orchestrator only.

Responsibilities

* Call Trend Engine
* Call Momentum Engine
* Call Volume Engine
* Call Base Engine
* Call Quality Gate
* Call Stage Engine
* Call Signal Engine
* Aggregate outputs
* Return one unified result

The Decision Engine MUST NOT duplicate scoring logic.

---

# Design Principles

Every engine should have one responsibility.

Engines must never calculate another engine's score.

All scoring logic must remain inside its own module.

The Decision Engine orchestrates only.

The Dashboard consumes Decision Engine output.

Backtesting consumes Decision Engine output.

Portfolio consumes Decision Engine output.

---

# River Alpha Philosophy

Indicators

↓

Feature Engine

↓

Trend / Momentum / Volume / Base

↓

Quality Gate

↓

Stage Engine

↓

Decision Engine

↓

Signal Engine

↓

Scanner / Dashboard / Portfolio / Backtest
