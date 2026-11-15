from strategies.common import indicators, result

def generate_signal(daily, h4):
    if daily is None or h4 is None or len(daily)<55 or len(h4)<30:
        return result("WAIT","Insufficient Daily / 4H candles.")
    d = indicators(daily).iloc[-1]
    h = indicators(h4)
    if len(h)<22:
        return result("WAIT","Insufficient 4H indicator history.")
    last, prev = h.iloc[-1], h.iloc[-2]
    breakout_high = h["high"].iloc[-21:-1].max()
    breakout_low = h["low"].iloc[-21:-1].min()
    long_ok = d.ema20>d.ema50 and d.close>d.ema20 and d.rsi14>50 and d.adx14>18 and last.close>breakout_high and last.close>last.open
    short_ok = d.ema20<d.ema50 and d.close<d.ema20 and d.rsi14<50 and d.adx14>18 and last.close<breakout_low and last.close<last.open
    if long_ok:
        entry=float(last.close); stop=entry-2*float(d.atr14)
        return result("BUY","Daily uptrend + 4H 20-bar breakout; paper signal.",entry,stop,entry+1.5*(entry-stop))
    if short_ok:
        entry=float(last.close); stop=entry+2*float(d.atr14)
        return result("SELL","Daily downtrend + 4H 20-bar breakdown; paper signal.",entry,stop,entry-1.5*(stop-entry))
    return result("WAIT","Crude conditions not fully aligned.")
