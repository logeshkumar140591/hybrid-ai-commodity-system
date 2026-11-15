from datetime import date, datetime
from math import floor

def calculate_lots(capital, risk_budget, entry, stop, lot_size, tick_size):
    distance = abs(float(entry) - float(stop))
    lot_size = int(lot_size)
    if distance <= 0 or lot_size <= 0:
        return {"lots":0, "risk":0.0, "reason":"Invalid stop or lot size"}
    risk_per_lot = distance * lot_size
    lots = floor(float(risk_budget) / risk_per_lot)
    lots = max(0, lots)
    return {
        "lots": lots,
        "risk": round(lots * risk_per_lot, 2),
        "risk_per_lot": round(risk_per_lot, 2),
        "reason": "OK" if lots else "One lot exceeds risk budget"
    }

def validate_expiry(expiry, min_days=5):
    try:
        exp = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        return (exp - date.today()).days >= min_days
    except Exception:
        return False
