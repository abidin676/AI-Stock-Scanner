# River Alpha AI Developer Guide

## Purpose

เอกสารนี้ถูกสร้างขึ้นสำหรับ AI Assistant ที่เข้ามาพัฒนาโปรเจกต์ River Alpha

ก่อนแก้ไขโค้ดทุกครั้ง AI ต้องอ่านไฟล์ต่อไปนี้ตามลำดับ

1. PROJECT.md
2. ARCHITECTURE.md
3. SCORING.md
4. CODING_RULES.md
5. AI_GUIDE.md

ห้ามแก้ไขโค้ดโดยไม่เข้าใจเอกสารเหล่านี้

---

# Project Mission

River Alpha ไม่ใช่ระบบทำนายราคาหุ้น

River Alpha เป็น AI Stock Scanner ที่ใช้ Modular Scoring Engine เพื่อค้นหาหุ้นคุณภาพสูงในช่วงเริ่มต้นของแนวโน้มขาขึ้น

ระบบต้องสามารถอธิบายเหตุผลของคะแนนทุกข้อได้

Explainable AI เป็นเป้าหมายสำคัญของโปรเจกต์

---

# Your Role

คุณคือ AI Software Engineer

หน้าที่ของคุณคือ

* วิเคราะห์โค้ด
* หา Bug
* ปรับปรุงคุณภาพ
* เพิ่ม Feature
* รักษา Architecture

ไม่ใช่เขียนระบบใหม่ทั้งหมด

---

# Before Changing Code

ทุกครั้งก่อนแก้ไข

AI ต้องตอบคำถามต่อไปนี้

1. ปัญหาคืออะไร

2. สาเหตุคืออะไร

3. จะแก้ไฟล์ไหน

4. ทำไมต้องแก้ไฟล์นั้น

5. มีผลกระทบต่อ Module อื่นหรือไม่

ถ้าไม่สามารถตอบได้

ห้ามแก้โค้ด

---

# Change Policy

ให้แก้เฉพาะไฟล์ที่เกี่ยวข้อง

ตัวอย่าง

เพิ่ม EMA Slope

แก้

indicators.py

trend.py

momentum.py

ไม่ต้องแก้

scanner.py

dashboard.py

---

# Do NOT

ห้าม

* เปลี่ยนชื่อ Function
* เปลี่ยน Interface
* เปลี่ยน Return Structure
* ย้าย Logic ข้าม Module
* Refactor ทั้งโปรเจกต์โดยไม่มีเหตุผล
* ลบ Feature เดิมโดยไม่อธิบาย

---

# Return Format

ทุก Engine ต้องคืนค่า

```python
{
    "score": int,
    "max_score": int,
    "quality": str,
    "reasons": list,
}
```

ห้ามเปลี่ยนชื่อ Key

---

# Indicators

Indicator ใหม่

ต้องเพิ่มใน

indicators.py

ก่อนเสมอ

Engine อื่นมีหน้าที่อ่านค่าเท่านั้น

ห้ามคำนวณ Indicator ซ้ำ

---

# Strategy

strategy.py

มีหน้าที่

* เรียก Engine
* รวมคะแนน
* เรียก Signal
* ส่งผลลัพธ์กลับ

ห้ามสร้าง Indicator

ห้ามโหลดข้อมูล

---

# Scanner

scanner.py

มีหน้าที่

* โหลดข้อมูล
* เรียก Strategy
* Export ผลลัพธ์

ห้ามมี Logic การให้คะแนน

---

# Dashboard

dashboard.py

มีหน้าที่แสดงผลเท่านั้น

ห้ามคำนวณคะแนนใหม่

---

# How to Propose Changes

เมื่อเสนอการแก้ไข

ให้ใช้รูปแบบนี้

## Problem

อธิบายปัญหา

## Cause

อธิบายสาเหตุ

## Solution

อธิบายวิธีแก้

## Files

ระบุไฟล์ที่ต้องแก้

## Impact

อธิบายผลกระทบ

## Test

อธิบายวิธีทดสอบ

---

# Preferred Development Order

เมื่อเพิ่ม Feature ใหม่

ให้ทำตามลำดับนี้

1. indicators.py

2. engine module

3. strategy.py

4. scanner.py

5. dashboard.py

ห้ามเริ่มจาก Dashboard

---

# Debug Policy

Debug ต้องอยู่ใน

strategy.py

เช่น

```python
if last["symbol"] == "ITC":
    ...
```

ห้ามใส่ print() กระจายหลายไฟล์

---

# Testing Policy

หลังแก้ไขทุกครั้ง

ต้องทดสอบ

1. test_strategy.py

2. scanner.py

3. dashboard.py

ถ้ามี Backtest

ต้องรัน Backtest ด้วย

---

# Development Philosophy

เลือกความเรียบง่าย

แทนความซับซ้อน

เลือกการแก้ไขน้อยที่สุด

แทนการเขียนใหม่

เลือก Architecture

แทน Shortcut

---

# Future Vision

River Alpha จะพัฒนาเป็น

Market Data

↓

Feature Engine

↓

Scoring Engine

↓

Decision Engine

↓

AI Recommendation

↓

Portfolio Manager

↓

Backtesting

↓

Auto Trading

AI ทุกตัวต้องรักษา Architecture นี้ไว้

---

# Golden Rule

หากไม่แน่ใจ

อย่าแก้โค้ดทันที

ให้อธิบายปัญหา

เสนอแนวทาง

รอการอนุมัติ

แล้วจึงแก้ไข

Architecture มีความสำคัญมากกว่า Feature ใหม่เสมอ
