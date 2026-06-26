# River Alpha Testing Guide

## Purpose

เอกสารนี้กำหนดมาตรฐานการทดสอบของโปรเจกต์ River Alpha

ทุก Feature ใหม่ ทุก Bug Fix และทุก Refactor ต้องผ่านขั้นตอนการทดสอบก่อน Commit หรือ Release

---

# Testing Philosophy

River Alpha ใช้หลัก

> Small Change → Small Test → Integration Test → Scanner Test

ห้ามเพิ่ม Feature แล้วไม่ทดสอบ

---

# Test Levels

## Level 1 — Unit Test

ทดสอบแต่ละ Module แยกกัน

ตัวอย่าง

* trend.py
* momentum.py
* volume.py
* base.py
* signal.py
* setup.py

เป้าหมาย

ตรวจสอบว่าแต่ละ Engine ให้คะแนนถูกต้อง

---

## Level 2 — Strategy Test

ไฟล์

```text
test_strategy.py
```

ตรวจสอบ

* Score
* Signal
* Setup
* Reasons
* Score Breakdown

ตัวอย่าง

```bash
python test_strategy.py
```

Expected

```text
Trend      : 30
Momentum   : 18
Volume     : 15
Base       : 10
Price      : 10

TOTAL      : 83
```

---

## Level 3 — Scanner Test

ไฟล์

```bash
python scanner.py
```

ตรวจสอบ

* ไม่มี Exception
* Scanner ทำงานครบ
* Summary ถูกต้อง
* Top 10 ถูกต้อง
* CSV Export สำเร็จ

---

## Level 4 — Dashboard Test

ไฟล์

```bash
streamlit run dashboard.py
```

ตรวจสอบ

* Dashboard เปิดได้
* ตารางแสดงผลถูกต้อง
* Filter ทำงาน
* Score ตรงกับ Scanner

---

## Level 5 — Backtest

ไฟล์

```bash
python backtest.py
```

ตรวจสอบ

* ไม่มี Error
* Report ถูกสร้าง
* Trades ถูกต้อง
* Summary ถูกต้อง

---

# Regression Test

ทุกครั้งหลังแก้ไข

ต้องตรวจสอบว่า

* Trend ยังถูกต้อง
* Momentum ยังถูกต้อง
* Volume ยังถูกต้อง
* Base ยังถูกต้อง
* Scanner ยังรันได้
* Dashboard ยังเปิดได้

Feature ใหม่ต้องไม่ทำให้ Feature เดิมเสีย

---

# Test Checklist

ก่อน Commit

* [ ] ไม่มี Syntax Error
* [ ] ไม่มี Import Error
* [ ] test_strategy.py ผ่าน
* [ ] scanner.py ผ่าน
* [ ] dashboard.py ผ่าน
* [ ] Documentation อัปเดต

ก่อน Release

* [ ] Backtest ผ่าน
* [ ] Scanner ผ่านทุกตลาด
* [ ] Dashboard ผ่าน
* [ ] Changelog อัปเดต
* [ ] TODO อัปเดต

---

# Expected Return Structure

ทุก Engine ต้องคืนค่า

```python
{
    "score": int,
    "max_score": int,
    "quality": str,
    "reasons": list,
}
```

ห้ามเปลี่ยนโครงสร้างนี้โดยไม่อัปเดต Documentation

---

# Debug Mode

ใช้เฉพาะใน strategy.py

ตัวอย่าง

```python
if last["symbol"] == "ITC":
    print(...)
```

ห้ามเพิ่ม print() กระจายใน Module ย่อย

---

# Performance Targets

Scanner

* SET + USA ต้องทำงานจบโดยไม่ Error

Strategy

* ใช้หน่วยความจำอย่างมีประสิทธิภาพ
* ไม่มีการคำนวณ Indicator ซ้ำ

Dashboard

* โหลดข้อมูลได้รวดเร็ว
* ไม่คำนวณคะแนนใหม่

---

# Bug Report Template

เมื่อพบ Bug

บันทึกข้อมูลดังนี้

## Environment

* Python Version
* pandas Version
* yfinance Version

## File

ไฟล์ที่เกิดปัญหา

## Error

ข้อความ Error

## Expected

ผลลัพธ์ที่คาดหวัง

## Actual

ผลลัพธ์ที่เกิดขึ้น

## Steps to Reproduce

1.
2.
3.

---

# AI Testing Rules

เมื่อ AI เพิ่ม Feature ใหม่

ต้อง

1. อธิบายวิธีทดสอบ

2. ระบุไฟล์ที่ต้องรัน

3. ระบุ Expected Output

4. ระบุความเสี่ยง

5. ระบุผลกระทบต่อ Module อื่น

ห้ามส่งโค้ดโดยไม่มี Test Plan

---

# Release Checklist

ก่อน Release

* Scanner ผ่าน
* Dashboard ผ่าน
* Backtest ผ่าน
* Documentation ครบ
* CHANGELOG อัปเดต
* TODO อัปเดต

เมื่อผ่านทั้งหมด

จึงสามารถสร้าง Release ใหม่ได้

---

# Long-term Goal

อนาคต River Alpha จะมี

* Automated Unit Tests
* Integration Tests
* Performance Tests
* Regression Tests
* Continuous Integration (CI)

ทุก Feature ใหม่ควรออกแบบให้สามารถทดสอบอัตโนมัติได้ในอนาคต
