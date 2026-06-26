# River Alpha Coding Rules

## Purpose

เอกสารนี้กำหนดมาตรฐานการพัฒนา River Alpha

ทั้งนักพัฒนาและ AI Assistant ต้องปฏิบัติตามกฎนี้ทุกครั้งก่อนแก้ไขโค้ด

เป้าหมายคือให้ระบบสามารถพัฒนาต่อได้โดยไม่ทำให้สถาปัตยกรรมเสียหาย

---

# Core Principles

1. แก้ไขให้น้อยที่สุด (Minimal Change)

เมื่อเพิ่ม Feature ใหม่

ให้แก้เฉพาะไฟล์ที่เกี่ยวข้อง

ห้าม Refactor ทั้งโปรเจกต์โดยไม่มีเหตุผล

---

2. Single Responsibility

แต่ละไฟล์มีหน้าที่เดียว

ห้ามเพิ่ม Logic ที่ไม่เกี่ยวข้อง

---

3. Modular Design

ทุก Module ต้องทำงานแยกจากกัน

ห้าม Module หนึ่งแก้ไขข้อมูลของอีก Module

---

# File Responsibilities

## indicators.py

หน้าที่

* คำนวณ Indicator ทั้งหมด

เช่น

* EMA
* RSI
* MACD
* ATR
* RVOL

ห้าม

* ให้คะแนน
* สร้าง Signal
* วิเคราะห์หุ้น

---

## strategy.py

หน้าที่

* เรียก Engine ทุกตัว
* รวมคะแนน
* เรียก Signal
* ส่งผลลัพธ์กลับ Scanner

ห้าม

* คำนวณ Indicator
* ดึงข้อมูลจากอินเทอร์เน็ต
* เขียนไฟล์

---

## trend.py

รับผิดชอบ Trend Score เท่านั้น

---

## momentum.py

รับผิดชอบ Momentum Score เท่านั้น

---

## volume.py

รับผิดชอบ Volume Score เท่านั้น

---

## base.py

รับผิดชอบ Base Score เท่านั้น

---

## signal.py

แปลงคะแนนเป็น Signal เท่านั้น

ห้ามคำนวณคะแนน

---

## scanner.py

หน้าที่

* โหลดข้อมูล
* เรียก strategy.py
* Export ผลลัพธ์

ห้ามมี Logic การให้คะแนน

---

## dashboard.py

แสดงผลเท่านั้น

ห้ามคำนวณคะแนนใหม่

---

# Interface Rules

ห้ามเปลี่ยนชื่อ Function ที่ใช้งานอยู่

ตัวอย่าง

```python
trend_score()

momentum_score()

volume_score()

base_score()

build_signal()

trend_start()
```

ถ้าจำเป็นต้องเพิ่ม

ให้เพิ่ม Function ใหม่

ไม่ใช่เปลี่ยนชื่อ Function เดิม

---

# Return Structure

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

* score
* max_score
* quality
* reasons

---

# Adding Indicators

Indicator ใหม่

ต้องเพิ่มใน

indicators.py

ก่อน

จากนั้นจึงเรียกใช้ใน Engine

ห้ามคำนวณ Indicator ซ้ำในหลายไฟล์

---

# Score Rules

คะแนนแต่ละ Module ต้องเป็นอิสระ

ตัวอย่าง

EMA20 > EMA50

ให้คะแนนใน Trend เท่านั้น

Momentum ห้ามให้คะแนนซ้ำ

---

# Debug Rules

Debug ต้องอยู่ใน strategy.py

ตัวอย่าง

```python
if last["symbol"] == "ITC":
    ...
```

ห้ามใส่ print() ใน Module ย่อย

---

# Code Style

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

test
```

---

# Comments

ทุก Section ใช้รูปแบบเดียวกัน

```python
# ======================================
# Trend
# ======================================
```

เพื่อให้ค้นหาและอ่านง่าย

---

# AI Development Rules

เมื่อ AI แก้ไขโค้ด

ต้องปฏิบัติตามลำดับนี้

1. วิเคราะห์ปัญหา

2. อธิบายสาเหตุ

3. เสนอแนวทางแก้

4. แก้เฉพาะไฟล์ที่เกี่ยวข้อง

5. สรุปสิ่งที่เปลี่ยน

ห้ามแก้หลายไฟล์โดยไม่มีเหตุผล

---

# Backward Compatibility

Feature ใหม่

ต้องไม่ทำให้

* Scanner
* Dashboard
* Backtest

พัง

Interface เดิมต้องใช้งานได้

---

# Pull Request Checklist

ก่อน Commit หรือ Merge

ตรวจสอบว่า

* โค้ดรันได้
* ไม่มี Syntax Error
* Return Structure ไม่เปลี่ยน
* Interface ไม่เปลี่ยน
* Documentation อัปเดตแล้ว
* Feature ใหม่มีเหตุผลรองรับ

---

# Long-Term Goal

River Alpha จะเติบโตเป็น AI Investment Platform

ดังนั้น

ความเสถียรของ Architecture

สำคัญกว่าการเพิ่ม Feature อย่างรวดเร็ว

ทุกการเปลี่ยนแปลงต้องรักษาหลักการ

* Modular
* Explainable
* Testable
* Maintainable
* Extensible

เสมอ
