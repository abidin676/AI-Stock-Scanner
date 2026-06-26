# Contributing to River Alpha

ขอบคุณที่สนใจพัฒนา River Alpha

ก่อนเริ่มแก้ไขโค้ด กรุณาอ่านเอกสารทั้งหมดในโฟลเดอร์ docs ก่อน

PROJECT.md

↓

ARCHITECTURE.md

↓

SCORING.md

↓

CODING_RULES.md

↓

AI_GUIDE.md

↓

ROADMAP.md

↓

TODO.md

↓

CHANGELOG.md

↓

TESTING.md

---

# Project Philosophy

River Alpha ถูกออกแบบให้เป็น

* Modular
* Explainable
* Testable
* Maintainable
* Extensible

ทุกการเปลี่ยนแปลงควรรักษาหลักการเหล่านี้

---

# Before You Start

ก่อนเริ่มพัฒนา

1. อ่าน Documentation

2. ตรวจสอบ TODO.md

3. ตรวจสอบ CHANGELOG.md

4. ตรวจสอบ Issue ที่เกี่ยวข้อง

5. วิเคราะห์ผลกระทบของการเปลี่ยนแปลง

---

# Development Workflow

ใช้ลำดับการพัฒนาดังนี้

```text
Issue

↓

Analysis

↓

Design

↓

Implementation

↓

Testing

↓

Documentation

↓

Review

↓

Merge
```

ห้ามข้ามขั้นตอน

---

# Branch Naming

ใช้รูปแบบ

```text
feature/indicator-rsi-slope

feature/vcp-detection

feature/decision-engine

fix/volume-score

fix/backtest-error

docs/scoring-update

refactor/momentum-engine
```

---

# Commit Message Convention

ใช้รูปแบบ

```text
feat(momentum): improve EMA cross scoring

feat(indicators): add ema9_slope

fix(strategy): correct total score calculation

fix(scanner): handle empty dataframe

docs(scoring): update scoring rules

refactor(volume): simplify RVOL logic

test(strategy): add regression tests
```

---

# Pull Request Checklist

ก่อนส่ง Pull Request

* [ ] โค้ดรันได้
* [ ] ไม่มี Syntax Error
* [ ] test_strategy.py ผ่าน
* [ ] scanner.py ผ่าน
* [ ] dashboard.py ผ่าน
* [ ] Documentation อัปเดต
* [ ] CHANGELOG.md อัปเดต
* [ ] TODO.md อัปเดต

---

# Coding Standards

ใช้ชื่อที่สื่อความหมาย

ตัวอย่าง

```python
trend

momentum

volume

base

overall

price_score
```

หลีกเลี่ยง

```python
x

y

temp

aaa

test
```

---

# Function Rules

ห้ามเปลี่ยนชื่อ Function หลัก

ตัวอย่าง

```python
trend_score()

momentum_score()

volume_score()

base_score()

build_signal()

trend_start()
```

หากต้องเพิ่มความสามารถ

ให้เพิ่ม Function ใหม่

ไม่ใช่เปลี่ยนชื่อ Function เดิม

---

# Module Rules

Indicators

อยู่ใน

indicators.py

เท่านั้น

Trend

อยู่ใน

trend.py

เท่านั้น

Momentum

อยู่ใน

momentum.py

เท่านั้น

Volume

อยู่ใน

volume.py

เท่านั้น

Base

อยู่ใน

base.py

เท่านั้น

Signal

อยู่ใน

signal.py

เท่านั้น

Scanner

อยู่ใน

scanner.py

เท่านั้น

Dashboard

อยู่ใน

dashboard.py

เท่านั้น

---

# Documentation Rules

เมื่อเพิ่ม Feature ใหม่

ให้อัปเดต

* PROJECT.md
* SCORING.md
* ROADMAP.md
* TODO.md
* CHANGELOG.md

Documentation ถือเป็นส่วนหนึ่งของ Feature

---

# Testing Rules

ทุกการเปลี่ยนแปลงต้องผ่าน

```bash
python test_strategy.py

python scanner.py
```

หากมีการแก้ Backtest

ให้รัน

```bash
python backtest.py
```

หากมีการแก้ Dashboard

ให้รัน

```bash
streamlit run dashboard.py
```

---

# AI Contributors

หาก Contributor เป็น AI

ต้องปฏิบัติตาม

AI_GUIDE.md

และ

PROMPTS.md

ทุกครั้ง

AI ต้อง

1. วิเคราะห์ก่อนแก้

2. อธิบายเหตุผล

3. แก้เฉพาะไฟล์ที่เกี่ยวข้อง

4. สรุปสิ่งที่เปลี่ยน

5. ระบุวิธีทดสอบ

ห้าม Refactor ทั้งโปรเจกต์โดยไม่มีเหตุผล

---

# Code Review Guidelines

ผู้รีวิวควรตรวจสอบ

* Architecture
* Readability
* Performance
* Testability
* Backward Compatibility
* Documentation

---

# Project Roadmap

ก่อนเพิ่ม Feature ใหม่

ตรวจสอบ

ROADMAP.md

และ

TODO.md

เพื่อหลีกเลี่ยงการทำงานซ้ำ

---

# Community Guidelines

เรายินดีรับ

* Bug Reports
* Feature Requests
* Documentation Improvements
* Performance Improvements
* Code Refactoring (ที่ไม่เปลี่ยนพฤติกรรม)

---

# Long-term Vision

River Alpha มีเป้าหมายเป็น AI Investment Platform

ทุกการมีส่วนร่วมควรช่วยให้ระบบ

* แม่นยำขึ้น
* อธิบายได้
* ดูแลรักษาง่าย
* ขยายต่อได้
* รองรับทั้งนักพัฒนาและ AI

คุณภาพของ Architecture สำคัญกว่าการเพิ่ม Feature อย่างรวดเร็ว

ขอบคุณที่ร่วมพัฒนา River Alpha ❤️
