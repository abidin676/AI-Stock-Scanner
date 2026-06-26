# River Alpha Changelog

การเปลี่ยนแปลงทั้งหมดของโปรเจกต์จะถูกบันทึกไว้ในไฟล์นี้

รูปแบบอ้างอิงจาก Keep a Changelog และใช้หลัก Semantic Versioning

---

# Versioning

River Alpha ใช้รูปแบบ

Major.Minor.Patch

ตัวอย่าง

```text
2.5.0
```

Major

เปลี่ยน Architecture

Minor

เพิ่ม Feature

Patch

แก้ Bug

---

# Version 2.5.0

Status

Current Development

Release Date

TBD

## Added

* Modular Strategy Engine
* Trend Engine
* Momentum Engine
* Volume Engine
* Base Engine
* Price Engine
* Signal Engine
* Setup Detection
* Score Breakdown
* Documentation System

## Changed

* strategy.py ถูกเขียนใหม่ให้เป็น Modular
* Score Engine แยกออกเป็นหลาย Module
* Mandatory Filters ปรับให้เรียบง่ายขึ้น
* Price Score แยกออกจาก Trend
* Overall Score คำนวณจากทุก Module

## Fixed

* แก้ปัญหา NameError ใน Strategy Engine
* แก้ปัญหา Syntax Error ใน trend.py
* แก้ปัญหา Score รวมผิดลำดับ
* แก้ปัญหา Return Structure ไม่สม่ำเสมอ
* ปรับ Debug Output

---

# Version 2.4.0

Status

Released

## Added

* Dashboard
* CSV Export
* Scanner Summary
* Reasons Output

## Changed

* Signal Threshold
* Score Display

## Fixed

* Scanner Stability
* Dashboard Rendering

---

# Version 2.3.0

Status

Released

## Added

* Base Engine
* Volume Engine

---

# Version 2.2.0

Status

Released

## Added

* Momentum Engine
* EMA Cross Detection
* MACD Score
* RSI Score

---

# Version 2.1.0

Status

Released

## Added

* Trend Engine
* EMA Alignment
* Higher High
* Higher Low

---

# Version 2.0.0

Initial Public Architecture

## Added

* Scanner
* Indicators
* EMA
* RSI
* MACD
* ATR
* RVOL

---

# Upcoming Version

## Version 2.6.0

Planned

### Added

* ema9_slope
* rsi_slope
* base_range
* volume_contraction
* Relative Strength

### Changed

* Momentum Calibration
* Volume Calibration
* Base Calibration

### Goal

Feature Engine

---

# Version 3.0.0

Planned

## Added

* VCP Detection
* Pocket Pivot
* Decision Engine
* Confidence Score
* Risk Score
* Reward Score

---

# Version 4.0.0

Planned

## Added

* Relative Strength Engine
* Sector Ranking
* Industry Ranking

---

# Version 5.0.0

Planned

## Added

* Backtesting Platform
* Walk Forward Test
* Strategy Comparison

---

# Version 6.0.0

Future

## Added

* Portfolio Manager
* AI Recommendation
* Local AI Integration
* Auto Trading

---

# Changelog Rules

เมื่อมีการเปลี่ยนแปลง

ให้เพิ่มรายการใหม่ด้านบนสุด

ทุกการเปลี่ยนแปลงควรอยู่ในหมวด

* Added
* Changed
* Fixed
* Removed
* Deprecated
* Security

ห้ามลบประวัติการเปลี่ยนแปลงเก่า

---

# Commit Guideline

ตัวอย่างข้อความ Commit

```text
feat(momentum): improve EMA cross scoring

fix(strategy): correct overall score calculation

docs(scoring): update scoring rules

refactor(volume): simplify RVOL calculation

test(scanner): add strategy regression test
```

---

# Release Checklist

ก่อนออกรุ่นใหม่

* ผ่านการทดสอบ Scanner
* ผ่าน test_strategy.py
* Documentation อัปเดต
* TODO.md อัปเดต
* ROADMAP.md อัปเดต
* CHANGELOG.md อัปเดต

เมื่อครบทุกข้อจึงเพิ่ม Version ใหม่
