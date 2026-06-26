# River Alpha AI Prompts

## Purpose

เอกสารนี้รวบรวม Prompt มาตรฐานสำหรับใช้กับ AI Assistant ทุกตัว

AI ทุกตัวควรอ่านเอกสารใน docs ก่อน

PROJECT.md

↓

ARCHITECTURE.md

↓

SCORING.md

↓

CODING_RULES.md

↓

AI_GUIDE.md

ก่อนเริ่มแก้ไขโค้ด

---

# Prompt 1 — Analyze Before Coding

```text
คุณคือ Senior Python Developer ของโปรเจกต์ River Alpha

ก่อนแก้ไขโค้ด

ให้อ่าน

docs/PROJECT.md
docs/ARCHITECTURE.md
docs/SCORING.md
docs/CODING_RULES.md
docs/AI_GUIDE.md

จากนั้น

1. อธิบายปัญหา
2. วิเคราะห์สาเหตุ
3. ระบุไฟล์ที่ต้องแก้
4. อธิบายผลกระทบ
5. รออนุมัติก่อนแก้

ห้ามแก้โค้ดทันที
```

---

# Prompt 2 — Add New Indicator

```text
เพิ่ม Indicator ใหม่

กฎ

1. เพิ่มเฉพาะใน indicators.py

2. ห้ามแก้ strategy.py

3. ห้ามคำนวณ Indicator ซ้ำ

4. คืนค่า DataFrame รูปแบบเดิม

5. อธิบายวิธีทดสอบ
```

---

# Prompt 3 — Improve Engine

```text
ปรับปรุง Engine

trend.py

momentum.py

volume.py

base.py

โดย

- ไม่เปลี่ยน Interface

- ไม่เปลี่ยน Return Structure

- อธิบายเหตุผลของคะแนนทุกข้อ

- รักษา max_score เดิม

- ส่งเฉพาะโค้ดที่เปลี่ยน
```

---

# Prompt 4 — Debug

```text
วิเคราะห์ Bug

ก่อนแก้

อธิบาย

Problem

Cause

Solution

Impact

Test Plan

จากนั้นจึงเสนอ Code

ห้ามเดาสาเหตุ
```

---

# Prompt 5 — Refactor

```text
Refactor

โดย

- ไม่เปลี่ยนผลลัพธ์

- ไม่เปลี่ยน Interface

- ลด Code Duplication

- เพิ่ม Comment

- เพิ่ม Readability

ห้ามเปลี่ยน Logic
```

---

# Prompt 6 — Documentation

```text
เมื่อเพิ่ม Feature ใหม่

ให้อัปเดต

PROJECT.md

SCORING.md

ROADMAP.md

TODO.md

CHANGELOG.md

พร้อมสรุปสิ่งที่เปลี่ยน
```

---

# Prompt 7 — Test

```text
สร้าง Unit Test

สำหรับ Feature ใหม่

ครอบคลุม

Normal Case

Edge Case

Invalid Data

Expected Output
```

---

# Prompt 8 — Score Calibration

```text
ช่วยวิเคราะห์การให้คะแนนของ River Alpha

อย่าเพิ่งแก้โค้ด

ให้อธิบายก่อนว่า

Module ไหน

ให้คะแนนมากเกินไป

ให้คะแนนน้อยเกินไป

มีคะแนนซ้ำหรือไม่

มี Bias หรือไม่

จากนั้นเสนอวิธีปรับปรุง
```

---

# Prompt 9 — Strategy Review

```text
รีวิว Strategy ทั้งระบบ

ตรวจสอบ

Trend

Momentum

Volume

Base

Price

Signal

Setup

Mandatory Filters

เสนอเฉพาะจุดที่ควรปรับปรุง

ห้ามเขียนใหม่ทั้งหมด
```

---

# Prompt 10 — Add New Feature

```text
ต้องการเพิ่ม Feature ใหม่

ให้ทำตามลำดับ

1. วิเคราะห์ Architecture

2. เลือกไฟล์ที่เหมาะสม

3. อธิบายเหตุผล

4. เพิ่ม Feature

5. เพิ่ม Test

6. อัปเดต Documentation

ห้ามแก้หลายไฟล์โดยไม่จำเป็น
```

---

# Prompt 11 — Backtest Review

```text
วิเคราะห์ผล Backtest

อธิบาย

Win Rate

Average Return

Drawdown

Risk

Reward

Expectancy

Profit Factor

เสนอวิธีปรับปรุงระบบ

อย่าเดาจากตัวเลข
```

---

# Prompt 12 — AI Code Review

```text
ทำ Code Review

ตรวจสอบ

Architecture

Readability

Maintainability

Performance

Bug Risk

Scalability

เสนอคะแนนเต็ม 100

พร้อมเหตุผล
```

---

# Golden Prompt

```text
คุณคือ Lead AI Engineer ของโปรเจกต์ River Alpha

หน้าที่ของคุณคือพัฒนาโปรเจกต์โดยไม่ทำลาย Architecture

ก่อนแก้ไขทุกครั้ง

ต้องอ่าน

PROJECT.md

ARCHITECTURE.md

SCORING.md

CODING_RULES.md

AI_GUIDE.md

ROADMAP.md

TODO.md

CHANGELOG.md

จากนั้น

1. วิเคราะห์

2. อธิบาย

3. เสนอแนวทาง

4. รออนุมัติ

5. แก้เฉพาะไฟล์ที่เกี่ยวข้อง

6. สรุปผล

7. อัปเดต Documentation

ห้าม Refactor ทั้งโปรเจกต์

ห้ามเปลี่ยน Interface

ห้ามเปลี่ยน Return Structure

ห้ามเดา

ให้ใช้หลัก Modular Architecture ของ River Alpha เท่านั้น
```
