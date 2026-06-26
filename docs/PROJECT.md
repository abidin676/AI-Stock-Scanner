# River Alpha

## Project Overview

River Alpha เป็นระบบ AI Stock Scanner สำหรับค้นหาหุ้นที่อยู่ในช่วงเริ่มต้นของแนวโน้มขาขึ้น (Early Trend) โดยใช้ระบบให้คะแนนแบบ Modular Scoring Engine

เป้าหมายของโปรเจกต์คือการช่วยนักลงทุนค้นหาหุ้นที่มีคุณภาพก่อนเกิดการเคลื่อนไหวครั้งใหญ่ ไม่ใช่การไล่ซื้อหุ้นที่วิ่งไปแล้ว

---

# Vision

River Alpha จะพัฒนาจาก Stock Scanner ไปเป็น AI Decision System ที่สามารถ

* วิเคราะห์หุ้น
* ให้คะแนนคุณภาพ
* อธิบายเหตุผล
* ประเมินความเสี่ยง
* ช่วยตัดสินใจลงทุน
* รองรับ Backtesting
* รองรับ Portfolio Management
* รองรับ Local AI Assistant

---

# Core Philosophy

ระบบแบ่งการวิเคราะห์ออกเป็นหลาย Module

แต่ละ Module รับผิดชอบหน้าที่ของตัวเอง

* Trend
* Momentum
* Volume
* Base Quality
* Price Position

ผลลัพธ์ของทุก Module จะถูกนำมารวมเป็นคะแนนรวม (Overall Score)

ไม่มี Module ใดควรแก้ไขข้อมูลของ Module อื่น

---

# Current Architecture

Market Data

↓

Indicators

↓

Mandatory Filters

↓

Trend Engine

↓

Momentum Engine

↓

Volume Engine

↓

Base Engine

↓

Price Engine

↓

Overall Score

↓

Signal Engine

↓

Scanner

↓

Dashboard

---

# Current Score Model

Trend ............. 30

Momentum .......... 25

Volume ............ 20

Base .............. 15

Price ............. 10

---

Total ............ 100

---

# Current Signal

🚀 ELITE

🟢 BUY

👀 WATCH

🌱 EARLY

SKIP

EXTENDED

NO DATA

---

# Project Structure

```
strategy.py
```

รวมคะแนนจากทุก Module

```
strategy_engine/
```

เก็บ Logic ของแต่ละ Engine

```
indicators.py
```

สร้าง Indicator ทั้งหมด

```
scanner.py
```

สแกนหุ้น

```
dashboard.py
```

แสดงผลผ่าน Streamlit

---

# Development Principles

1. Indicator ใหม่ต้องอยู่ใน indicators.py

2. strategy.py มีหน้าที่รวมคะแนนเท่านั้น

3. แต่ละ Module ต้องคืนค่าเป็น

* score
* quality
* reasons

4. หลีกเลี่ยงการเขียน Logic ซ้ำ

5. ทุกการเปลี่ยนคะแนนต้องมีเหตุผลรองรับ

6. โครงสร้าง Return ของแต่ละ Module ต้องคงรูปแบบเดิม

---

# Long-term Goal

River Alpha Version 3

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

Portfolio Management

↓

Backtesting

↓

Auto Trading
