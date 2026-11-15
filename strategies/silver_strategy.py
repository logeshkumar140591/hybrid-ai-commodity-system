from strategies.common import indicators, result

def generate_signal(daily, h4):
    if daily is None or h4 is None or len(daily)<205 or len(h4)<55:
        return result("WAIT","Insufficient Daily / 4H candles for Silver EMA200 filter.")
    d = indicators(daily).iloc[-1]
    h = indicators(h4)
    last = h.iloc[-1]
    prior_high = h["high"].iloc[-21:-1].max()
    prior_low = h["low"].iloc[-21:-1].min()
    # Avoid chasing unusually expanded 4H candles.
    range_ok = (float(last.high)-float(last.low)) <= 1.8*float(d.atr14)
    long_ok = d.ema20>d.ema50 and d.close>d.ema200 and d.rsi14>55 and d.adx14>20 and last.close>prior_high and last.close>last.open and range_ok
    short_ok = d.ema20<d.ema50 and d.close<d.ema200 and d.rsi14<45 and d.adx14>20 and last.close<prior_low and last.close<last.open and range_ok
    if long_ok:
        entry=float(last.close); stop=entry-2.2*float(d.atr14)
        return result("BUY","Silver Daily trend + 4H 20-bar volatility-filtered breakout.",entry,stop,entry+1.5*(entry-stop))
    if short_ok:
        entry=float(last.close); stop=entry+2.2*float(d.atr14)
        return result("SELL","Silver Daily downtrend + 4H 20-bar breakdown.",entry,stop,entry-1.5*(stop-entry))
    return result("WAIT","Silver conditions not fully aligned.")
