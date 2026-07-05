SET_COMMISSION_RATE = 0.00157
SET_VAT_RATE = 0.07

USA_COMMISSION = 0.09
USA_VAT_RATE = 0.07


def calculate_fee(amount, market, side="BUY"):

    amount = float(amount)
    market = str(market).upper().strip()
    side = str(side).upper().strip()

    if amount <= 0:
        return {
            "commission": 0.0,
            "vat": 0.0,
            "total_fee": 0.0,
        }

    if side not in ("BUY", "SELL"):
        raise ValueError(f"Unsupported side: {side}")

    if market == "SET":
        commission = amount * SET_COMMISSION_RATE
        vat = commission * SET_VAT_RATE
    elif market == "USA":
        commission = USA_COMMISSION
        vat = commission * USA_VAT_RATE
    else:
        raise ValueError(f"Unsupported market: {market}")

    total_fee = commission + vat

    return {
        "commission": round(commission, 6),
        "vat": round(vat, 6),
        "total_fee": round(total_fee, 6),
    }
