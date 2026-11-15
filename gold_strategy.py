from strategies.common import indicators, result

def generate_signal(daily, h4):
    if daily is None or h4 is None or len(daily)<205 or len(h4)<55:
        return result("WAIT","Insufficient Daily / 4H candles for Gold EMA200 filter.")
    d = indicators(daily).iloc[-1]
    h = indicators(h4)
    last, prev = h.iloc[-1], h.iloc[-2]
    long_reclaim = prev.close<=prev.ema20 and last.close>last.ema20 and last.close>last.open
    short_reclaim = prev.close>=prev.ema20 and last.close<last.ema20 and last.close<last.open
    long_ok = d.ema20>d.ema50 and d.close>d.ema200 and d.rsi14>52 and d.adx14>18 and long_reclaim
    short_ok = d.ema20<d.ema50 and d.close<d.ema200 and d.rsi14<48 and d.adx14>18 and short_reclaim
    if long_ok:
        entry=float(last.close); stop=entry-1.8*float(d.atr14)
        return result("BUY","Gold Daily trend + 4H EMA20 pullback reclaim.",entry,stop,entry+1.5*(entry-stop))
    if short_ok:
        entry=float(last.close); stop=entry+1.8*float(d.atr14)
        return result("SELL","Gold Daily downtrend + 4H EMA20 rejection.",entry,stop,entry-1.5*(stop-entry))
    return result("WAIT","Gold conditions not fully aligned.")
