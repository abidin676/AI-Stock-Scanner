# River Alpha Scoring System

## Purpose

River Alpha ใช้ระบบ Modular Scoring Engine

แทนที่จะตัดสินหุ้นจาก Indicator เพียงตัวเดียว ระบบจะประเมินหุ้นจากหลายมิติ แล้วรวมคะแนนเป็น Overall Score

คะแนนทั้งหมดมีค่าสูงสุด 100 คะแนน

---

# Score Distribution

| Module    | Max Score |
| --------- | --------: |
| Trend     |        30 |
| Momentum  |        25 |
| Volume    |        20 |
| Base      |        15 |
| Price     |        10 |
| **Total** |   **100** |

ทุก Module ทำงานอย่างอิสระ

ห้าม Module หนึ่งแก้คะแนนของอีก Module

---

# Trend Score (30)

Trend ใช้วัด "คุณภาพของแนวโน้ม"

ตัวอย่างองค์ประกอบ

| Condition      | Score |
| -------------- | ----: |
| EMA20 > EMA50  |     5 |
| EMA50 > EMA200 |     5 |
| EMA20 Rising   |     5 |
| EMA50 Rising   |     5 |
| Higher Low     |     3 |
| Higher High    |     3 |
| Trend Change   |     4 |

Trend Score เต็ม = 30

---

# Momentum Score (25)

Momentum ใช้วัดแรงส่งของราคา

องค์ประกอบ

| Condition               | Score |
| ----------------------- | ----: |
| Fresh EMA Cross         |    10 |
| Recent EMA Cross        |     5 |
| EMA9 > EMA20            |     5 |
| MACD Bullish            |     3 |
| MACD Histogram Positive |     2 |
| Healthy RSI             |     5 |
| RSI Recovering          |     2 |

คะแนนสูงสุดไม่เกิน 25

Momentum จะสะท้อน "ความเร็วของแนวโน้ม"

---

# Volume Score (20)

Volume ใช้วัดแรงซื้อขาย

ตัวอย่าง

| RVOL   | Score |
| ------ | ----: |
| >= 5.0 |    20 |
| >= 3.0 |    18 |
| >= 2.0 |    15 |
| >= 1.5 |    10 |
| >= 1.2 |     6 |
| >= 1.0 |     3 |
| < 0.8  |   -10 |

Dry Volume

+5

คะแนนรวมสูงสุด = 20

---

# Base Score (15)

Base ใช้วัดคุณภาพของฐานราคา

องค์ประกอบ

| Condition       | Score |
| --------------- | ----: |
| EMA Compression |     3 |
| ATR Compression |     3 |
| Dry Volume      |     2 |
| Near Base       |     4 |
| Still Near Base |     2 |
| Tight Base      |     1 |

คะแนนรวมสูงสุด = 15

---

# Price Score (10)

Price ใช้วัดตำแหน่งของราคา

| Condition   | Score |
| ----------- | ----: |
| Above EMA20 |     5 |
| Near EMA20  |     5 |

คะแนนรวมสูงสุด = 10

---

# Overall Score

```text
Overall

=

Trend

+

Momentum

+

Volume

+

Base

+

Price
```

คะแนนจะถูกจำกัดให้อยู่ในช่วง

0 ถึง 100

---

# Signal Mapping

|      Score | Signal   |
| ---------: | -------- |
|   85 - 100 | 🚀 ELITE |
|    75 - 84 | 🟢 BUY   |
|    65 - 74 | 👀 WATCH |
|    55 - 64 | 🌱 EARLY |
| ต่ำกว่า 55 | SKIP     |

EXTENDED และ NO DATA ไม่ได้มาจากคะแนน

แต่เกิดจาก Mandatory Filters

---

# Quality Levels

ทุก Module ต้องคืนค่า

```python
{
    "score": ...,
    "max_score": ...,
    "quality": "...",
    "reasons": [...]
}
```

ตัวอย่างระดับคุณภาพ

| Quality   | Meaning   |
| --------- | --------- |
| EXCELLENT | เกือบเต็ม |
| STRONG    | แข็งแรง   |
| GOOD      | ดี        |
| NORMAL    | ปานกลาง   |
| WEAK      | อ่อน      |

---

# Scoring Rules

1. ห้ามให้คะแนนซ้ำในหลาย Module

ตัวอย่าง

EMA20 > EMA50

ให้คะแนนเฉพาะ Trend

ไม่ให้ Momentum ให้คะแนนซ้ำ

---

2. Indicator ใหม่

ต้องสร้างใน

indicators.py

ก่อน

แล้วจึงนำมาใช้ใน Module ต่าง ๆ

---

3. คะแนนต้องอธิบายได้

ทุกคะแนนที่เพิ่ม

ต้องมีข้อความใน

Reasons

เสมอ

---

4. Return Structure

ทุก Module ต้องคืนค่าในรูปแบบเดียวกัน

ห้ามเปลี่ยนชื่อ Key

* score
* max_score
* quality
* reasons

---

# Future Expansion

Version 3 จะเพิ่มการให้คะแนนจาก

* Relative Strength
* Stage Analysis
* VCP Pattern
* Pocket Pivot
* Tight Range
* Power Trend
* Market Breadth
* Sector Strength

โดยยังคงหลักการ Modular Scoring Engine เหมือนเดิม

---

# Design Philosophy

River Alpha ไม่ได้พยายาม "ทำนายอนาคต"

แต่พยายาม "วัดคุณภาพของหุ้น"

คะแนนที่สูงกว่า หมายถึงหุ้นมีคุณสมบัติตรงตามเงื่อนไขของระบบมากกว่า ไม่ใช่การรับประกันว่าจะปรับตัวขึ้นในอนาคต
