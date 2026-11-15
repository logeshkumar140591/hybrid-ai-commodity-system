from datetime import date, datetime
from math import floor


def calculate_lots(capital, risk_budget, entry, stop, lot_size, tick_size=0.01):
    distance = abs(float(entry) - float(stop))
    lot_size = int(lot_size)
    if distance <= 0 or lot_size <= 0 or float(risk_budget) <= 0:
        return {'lots': 0, 'risk': 0.0, 'risk_per_lot': 0.0, 'reason': 'Invalid stop, lot size or risk budget'}
    risk_per_lot = distance * lot_size
    lots = max(0, floor(float(risk_budget) / risk_per_lot))
    return {'lots': lots, 'risk': round(lots * risk_per_lot, 2),
            'risk_per_lot': round(risk_per_lot, 2),
            'reason': 'OK' if lots else 'One lot exceeds risk budget'}


def validate_expiry(expiry, min_days=5):
    try:
        exp = datetime.strptime(str(expiry)[:10], '%Y-%m-%d').date()
        return (exp - date.today()).days >= min_days
    except Exception:
        return False
