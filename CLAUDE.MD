# CLAUDE.md

# River Alpha Project Knowledge

This document describes the architecture, design philosophy and business rules of River Alpha.

It is intended for AI assistants to understand WHY the project is built this way.

---

# Project Goal

River Alpha is an AI-powered stock analysis platform.

Its objective is to identify high-quality early trend reversals before institutional breakouts.

The emphasis is on:

* Explainability
* Modularity
* Consistency
* Long-term maintainability

---

# Core Philosophy

Every module has one responsibility.

Trend is not Momentum.

Momentum is not Volume.

Volume is not Base.

Signal is not Setup.

Never mix business logic across modules.

---

# Architecture

Indicators
↓

Strategy Engine

* trend.py
* momentum.py
* volume.py
* base.py
* signal.py
* setup.py

↓

scanner.py

↓

dashboard.py

---

# Scoring

Trend

30

Momentum

25

Volume

20

Base

15

Price

10

Total

100

Weights should only change after discussion.

---

# Signal Philosophy

SKIP

Reject weak trends.

EARLY

Potential early-stage trend.

WATCH

High-quality candidate.

BUY

Reserved for exceptional setups.

---

# Development Priorities

1. Feature Engine
2. Trend Quality
3. Decision Engine
4. Backtesting
5. Dashboard
6. Portfolio

---

# Design Principles

* Prefer composition over duplication.
* Keep functions small.
* Keep modules independent.
* Avoid hidden side effects.
* Explain every score.

---

# AI Behaviour

Before proposing code:

1. Understand the current implementation.
2. Explain weaknesses.
3. Suggest improvements.
4. Wait for approval.

Never rewrite the whole project.

Never move logic across modules.

Never change public interfaces without approval.

---

# Mission

River Alpha aims to become a professional AI investment platform with transparent, modular and explainable decision making.
