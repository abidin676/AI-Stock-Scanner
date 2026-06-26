# AGENTS.md

## River Alpha AI Agent Instructions

Read this file before making any changes.

---

# Project Philosophy

River Alpha is a Decision Support System.

It is NOT just a stock scanner.

Always prioritize architecture, maintainability, and backward compatibility.

---

# Development Principles

1. Design before coding.
2. Produce minimal patches.
3. Never rewrite existing modules without approval.
4. Keep backward compatibility.
5. Reuse existing indicators.
6. Never duplicate calculations.
7. Prefer vectorized pandas operations.
8. Keep algorithms O(n) whenever possible.
9. Explain the implementation plan before writing code.
10. Wait for approval before major changes.

---

# Architecture

Market Data

↓

Indicators

↓

Derived Features

↓

Feature Engine

↓

Trend Engine

Momentum Engine

Volume Engine

Base Engine

↓

Decision Engine

↓

Dashboard / Backtest / Alerts

---

# Coding Rules

* Functional programming preferred.
* Avoid classes unless explicitly requested.
* Never create helper functions for derived features.
* Derived features must become DataFrame columns.
* Never recalculate indicators that already exist.
* Do not rename existing columns.
* Do not change function signatures without approval.

---

# Testing

Before every commit:

* python -m py_compile indicators.py
* python scanner.py
* python test_strategy.py

Fix all errors before continuing.

---

# Git Workflow

Feature

↓

Review

↓

Test

↓

Commit

↓

Push

Never skip testing.

---

# Communication

Always:

1. Analyze first.
2. Explain the plan.
3. Wait for approval.
4. Implement.
5. Self-review.
6. Stop.

Never continue to the next phase without approval.
