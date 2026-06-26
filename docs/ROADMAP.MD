# River Alpha Development Roadmap

## Vision

River Alpha จะพัฒนาจาก AI Stock Scanner ไปเป็น AI Investment Platform ที่สามารถ

* วิเคราะห์หุ้น
* จัดอันดับหุ้น
* อธิบายเหตุผล
* จัดการพอร์ต
* ทดสอบกลยุทธ์
* ช่วยตัดสินใจลงทุน
* รองรับ Local AI
* รองรับ Auto Trading

Roadmap นี้เป็นแนวทางการพัฒนาหลักของโปรเจกต์

---

# Version 2.0

## Core Scanner

Status

Completed

Features

* Market Scanner
* EMA
* RSI
* MACD
* ATR
* RVOL
* Trend Engine
* Momentum Engine
* Volume Engine
* Base Engine
* Price Engine
* Signal Engine
* Setup Detection

---

# Version 2.5

## Feature Engine

Status

In Progress

Features

* ema9_slope
* ema20_slope
* rsi_slope
* macd_hist_slope
* volume_slope
* base_range
* volume_contraction
* distance_from_52w_high
* distance_from_52w_low

Goal

เพิ่มคุณภาพของข้อมูลก่อนเข้าสู่ Scoring Engine

---

# Version 3.0

## Advanced Setup Detection

Planned

Features

* VCP Detection
* Pocket Pivot
* Tight Range
* Power Trend
* Trend Continuation
* Failed Breakout
* Shakeout Detection

Goal

ทำให้ระบบสามารถแยกประเภท Setup ได้ละเอียดขึ้น

---

# Version 3.5

## Decision Engine

Planned

แทนการใช้คะแนนรวมเพียงอย่างเดียว

ระบบจะประเมินจาก

* Trend
* Momentum
* Volume
* Base
* Price
* Setup

ผลลัพธ์

* Signal
* Confidence
* Risk
* Reward
* AI Recommendation

---

# Version 4.0

## Relative Strength Engine

Planned

Features

* Sector Relative Strength
* Industry Relative Strength
* Market Relative Strength
* Relative Volume Ranking

Goal

เลือกหุ้นที่แข็งกว่าตลาด

---

# Version 4.5

## Portfolio Manager

Planned

Features

* Portfolio Tracking
* Position Sizing
* Risk Control
* Exposure Management
* Performance Tracking

Goal

เปลี่ยนจาก Scanner เป็นระบบช่วยบริหารพอร์ต

---

# Version 5.0

## Backtesting Platform

Planned

Features

* Historical Backtest
* Walk Forward Test
* Parameter Optimization
* Trade Statistics
* Equity Curve
* Drawdown Analysis
* Monte Carlo Simulation

Goal

ประเมินคุณภาพของกลยุทธ์ด้วยข้อมูลย้อนหลัง

---

# Version 5.5

## AI Assistant

Planned

รองรับ Local AI

เช่น

* Qwen Coder
* DeepSeek Coder
* Claude
* ChatGPT
* Gemini

AI สามารถ

* วิเคราะห์หุ้น
* อธิบายคะแนน
* แนะนำการแก้โค้ด
* วิเคราะห์ผล Backtest
* สร้างรายงาน

---

# Version 6.0

## Auto Trading

Future

Features

* Broker API
* Position Management
* Risk Management
* Auto Entry
* Auto Exit
* Trade Journal

Goal

สร้างระบบลงทุนอัตโนมัติแบบครบวงจร

---

# Development Priorities

Priority 1

Core Engine

* Indicators
* Trend
* Momentum
* Volume
* Base
* Price

Priority 2

Decision Layer

* Setup
* Confidence
* Risk
* Reward

Priority 3

Analytics

* Backtesting
* Portfolio
* Reports

Priority 4

Artificial Intelligence

* Local AI
* Recommendation
* Strategy Improvement

Priority 5

Automation

* Broker Integration
* Auto Trading

---

# Milestones

## Milestone A

Stable Scoring Engine

Target

คะแนนมีความสม่ำเสมอและผ่านการทดสอบ

---

## Milestone B

Reliable Scanner

Target

สามารถคัดเลือกหุ้นคุณภาพได้อย่างต่อเนื่อง

---

## Milestone C

Decision Engine

Target

ให้คำแนะนำการลงทุนพร้อมเหตุผล

---

## Milestone D

Backtesting Platform

Target

สามารถประเมินประสิทธิภาพของกลยุทธ์ได้

---

## Milestone E

AI Investment Platform

Target

River Alpha ทำหน้าที่เป็นผู้ช่วยนักลงทุนแบบครบวงจร

---

# Long-Term Architecture

```text
Market Data
      │
      ▼
Indicators
      │
      ▼
Feature Engine
      │
      ▼
Scoring Engine
      │
      ▼
Decision Engine
      │
      ▼
AI Recommendation
      │
      ▼
Portfolio Manager
      │
      ▼
Backtesting
      │
      ▼
Auto Trading
```

---

# Guiding Principle

River Alpha จะเติบโตแบบค่อยเป็นค่อยไป

ทุก Version ต้องรักษา

* Modular Design
* Explainable AI
* Testability
* Maintainability
* Backward Compatibility

การเพิ่ม Feature ใหม่ต้องไม่ทำให้ Architecture เดิมเสียหาย

คุณภาพของระบบสำคัญกว่าความเร็วในการพัฒนา
