import pandas as pd

def indicators(df):
    x = df.copy()
    x["ema20"] = x["close"].ewm(span=20, adjust=False).mean()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200, adjust=False).mean()
    delta = x["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, pd.NA)
    x["rsi14"] = 100 - (100 / (1 + rs))
    prev = x["close"].shift(1)
    tr = pd.concat([(x["high"]-x["low"]), (x["high"]-prev).abs(), (x["low"]-prev).abs()], axis=1).max(axis=1)
    x["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()
    plus_dm = x["high"].diff()
    minus_dm = -x["low"].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    atr = x["atr14"].replace(0, pd.NA)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, pd.NA)
    x["adx14"] = dx.ewm(alpha=1/14, adjust=False).mean()
    return x.dropna(subset=["ema50","rsi14","atr14"])

def result(signal, reason, entry=None, stop=None, target=None):
    return {"signal":signal, "reason":reason, "entry":entry, "stop":stop, "target":target}
