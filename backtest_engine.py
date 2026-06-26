def run_backtest(df):
    LOOKBACK = 250
    MAX_HOLD = 20
    STOP_LOSS = -8  # %
    TAKE_PROFIT = 30  # %

    if len(df) < LOOKBACK:
        return pd.DataFrame(), pd.DataFrame()

    trades = []
    scores = []

    i = LOOKBACK
    while i < len(df) - MAX_HOLD:
        # สร้างสัญญาณเทรด (เช่น ดูจากข้อมูลที่คำนวณแล้ว)
        # สมมติว่ามีสัญญาณเทรดที่เป็นจริง
        signal = True  # แทนด้วยตรรกะของคุณ

        if signal:
            # คำนวณผลตอบแทน
            exit_price = None
            holding = MAX_HOLD
            for j in range(i + 1, min(i + MAX_HOLD + 1, len(df))):
                # ตรวจสอบเงื่อนไขหยุดทำกำไรหรือขาดทุน
                if (df.loc[j, 'close'] / df.loc[i, 'close'] - 1) * 100 >= TAKE_PROFIT:
                    exit_price = df.loc[j, 'close']
                    holding = j - i
                    break
                elif (df.loc[j, 'close'] / df.loc[i, 'close'] - 1) * 100 <= STOP_LOSS:
                    exit_price = df.loc[j, 'close']
                    holding = j - i
                    break

            if exit_price is None:
                exit_price = df.loc[i + MAX_HOLD, 'close']
                holding = MAX_HOLD

            # คำนวณผลตอบแทน
            ret = (exit_price - df.loc[i, 'close']) / df.loc[i, 'close'] * 100
            trades.append({
                'entry_date': df.index[i],
                'exit_date': df.index[j] if exit_price is not None else df.index[i + MAX_HOLD],
                'entry_price': df.loc[i, 'close'],
                'exit_price': exit_price,
                'return': ret,
                'holding': holding
            })

            # บันทึกคะแนน (scores)
            scores.append({
                'entry_date': df.index[i],
                'exit_date': df.index[j] if exit_price is not None else df.index[i + MAX_HOLD],
                'return': ret
            })

        # อัปเดต i ให้ข้ามช่วงที่เทรดแล้ว
        i += holding

    return pd.DataFrame(trades), pd.DataFrame(scores)
