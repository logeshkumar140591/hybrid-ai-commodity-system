import pandas as pd
from strategies.common import indicators

def run_backtest(daily, strategy_fn):
    # Daily-only signal proxy: useful for initial smoke testing, not a full
    # multi-timeframe historical simulation. 4H alignment is required for
    # production-grade validation and is intentionally not fabricated here.
    x = indicators(daily)
    trades = []
    for i in range(205, len(x)-1):
        hist = x.iloc[:i+1]
        # A strategy requires a 4H series; do not invent 4H candles.
        # Return no synthetic trades until proper 4H historical data is loaded.
    return {
        "metrics": {
            "status": "DAILY DATA LOADED; 4H BACKTEST NOT YET IMPLEMENTED",
            "candles": int(len(x)),
            "trades": 0,
            "note": "No performance claims. A true historical 4H dataset is required."
        },
        "trades": pd.DataFrame(columns=["entry_time","side","entry","stop","target","exit_time","exit","pnl"])
    }
