# River Alpha Architecture

## System Overview

River Alpha ถูกออกแบบให้เป็น Modular AI Stock Scanner

แต่ละ Module ทำหน้าที่เฉพาะของตัวเอง

ไม่มี Module ใดควรรับผิดชอบหลายหน้าที่

---

# High Level Architecture

```
Market Data
      │
      ▼
Indicators
      │
      ▼
Mandatory Filters
      │
      ▼
Trend Engine
      │
      ▼
Momentum Engine
      │
      ▼
Volume Engine
      │
      ▼
Base Engine
      │
      ▼
Price Engine
      │
      ▼
Overall Score
      │
      ▼
Signal Engine
      │
      ▼
Setup Detection
      │
      ▼
Scanner
      │
      ▼
Dashboard
```

---

# Folder Structure

```
AI Stock Scanner/

│
├── strategy.py
├── scanner.py
├── indicators.py
├── dashboard.py
│
├── strategy_engine/
│   ├── trend.py
│   ├── momentum.py
│   ├── volume.py
│   ├── base.py
│   ├── setup.py
│   ├── signal.py
│   └── filters.py
│
├── providers/
│
├── watchlists/
│
├── output/
│
└── docs/
```

---

# Module Responsibilities

## indicators.py

หน้าที่

* สร้าง Indicator ทั้งหมด
* คำนวณ EMA
* RSI
* MACD
* ATR
* RVOL
* Indicator ใหม่ทั้งหมด

ข้อสำคัญ

Indicator ใหม่ต้องถูกเพิ่มที่ไฟล์นี้เท่านั้น

ห้ามคำนวณ Indicator ใน strategy.py

---

## filters.py

Mandatory Filters

ใช้กรองหุ้นที่ไม่ควรเข้าสู่การให้คะแนน

เช่น

* ข้อมูลไม่ครบ
* Downtrend รุนแรง
* ราคา Over Extended

ห้ามใช้ไฟล์นี้เพื่อลดคะแนน

Filter มีหน้าที่ "ผ่าน" หรือ "ไม่ผ่าน" เท่านั้น

---

## trend.py

ประเมินคุณภาพของแนวโน้ม

คะแนนเต็ม

30

ตัวอย่าง

* EMA Alignment
* EMA Slope
* Higher High
* Higher Low
* Trend Change

---

## momentum.py

ประเมินแรงส่งของราคา

คะแนนเต็ม

25

ตัวอย่าง

* EMA Cross
* EMA9 Momentum
* MACD
* RSI
* Momentum Quality

---

## volume.py

ประเมินคุณภาพของ Volume

คะแนนเต็ม

20

ตัวอย่าง

* Relative Volume
* Dry Volume
* Volume Expansion

---

## base.py

ประเมินคุณภาพของฐานราคา

คะแนนเต็ม

15

ตัวอย่าง

* EMA Compression
* ATR Compression
* Near Base
* Tight Base

---

## signal.py

แปลงคะแนนรวมเป็น Signal

ตัวอย่าง

```
85+

ELITE

75+

BUY

65+

WATCH

55+

EARLY
```

ไฟล์นี้ไม่มีหน้าที่คำนวณคะแนน

---

## setup.py

ระบุประเภทของ Setup

เช่น

* Breakout
* Pullback
* Early Reversal
* Base Building

ในอนาคต

* VCP
* Pocket Pivot
* Power Trend
* Tight Range

---

## strategy.py

หัวใจของระบบ

หน้าที่

* เรียกทุก Engine
* รวมคะแนน
* สร้าง Score Breakdown
* เรียก Signal
* ส่งผลลัพธ์กลับ Scanner

strategy.py ไม่ควรคำนวณ Indicator

---

## scanner.py

ทำหน้าที่

* โหลดหุ้น
* โหลดข้อมูลราคา
* เรียก strategy.py
* รวมผลลัพธ์
* Export CSV
* ส่งข้อมูลไป Dashboard

---

## dashboard.py

แสดงผลผ่าน Streamlit

ข้อมูลที่แสดง

* Symbol
* Score
* Signal
* Setup
* RSI
* RVOL
* Reasons
* Score Breakdown

---

# Data Flow

```
Price Data

↓

Indicators

↓

Features

↓

Strategy Engine

↓

Overall Score

↓

Signal

↓

Scanner

↓

Dashboard
```

---

# Design Rules

1. Indicators คำนวณเฉพาะใน indicators.py

2. Engine แต่ละตัวห้ามแก้ไขข้อมูลของ Engine อื่น

3. Engine ต้องคืนค่าในรูปแบบเดียวกัน

```
{
    "score": ...,
    "max_score": ...,
    "quality": ...,
    "reasons": [...]
}
```

4. strategy.py มีหน้าที่รวมคะแนนเท่านั้น

5. Scanner ห้ามมี Logic การให้คะแนน

6. Dashboard ห้ามคำนวณคะแนนใหม่

---

# Future Architecture

```
Market Data

↓

Indicators

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
```

---

# Development Philosophy

River Alpha เน้น

* Modular
* Explainable
* Testable
* Extensible

ทุกการตัดสินใจของระบบต้องสามารถอธิบายเหตุผลได้

ทุก Module ต้องสามารถพัฒนาแยกจากกันได้โดยไม่กระทบ Module อื่น
