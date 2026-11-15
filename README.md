# Hybrid AI Commodity Swing System V1.0

Independent Streamlit project for MCX Crude Oil, Gold and Silver swing research.

## Safety mode
- Paper trading only.
- No order placement code is included.
- Never commit API keys, PIN, TOTP secret or tokens.
- Contract token, expiry, lot size and tick size must be populated from the current Angel One instrument master / MCX contract details. Do not guess them.

## Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Configure `.streamlit/secrets.toml` using the example. Keep the real secrets file private.

## Contract master
Edit `contract_master.csv` with the current active MCX contract:
- commodity: Crude Oil, Gold, Silver
- tradingsymbol: exact Angel One trading symbol
- symboltoken: exact instrument token
- expiry: YYYY-MM-DD
- lotsize: current contract quantity
- ticksize: current tick size

Contract specs change. Verify every field before use.

## Data
The adapter uses Angel One SmartAPI login (client code, PIN, TOTP) and historical candle API for MCX. It requests ONE_DAY and ONE_HOUR candles. Hourly candles are resampled to 4-hour bars for strategy screening. Validate exchange session boundaries and bar alignment before relying on signals.

## Strategy profiles (initial hypotheses, not proven)
- Crude: Daily EMA20/50 trend, RSI/ADX filter, 4H 20-bar breakout, 2 ATR stop.
- Gold: Daily EMA20/50/200 trend, RSI/ADX, 4H EMA20 reclaim, 1.8 ATR stop.
- Silver: Daily EMA20/50/200 trend, RSI/ADX, 4H 20-bar breakout with volatility filter, 2.2 ATR stop.
- Initial target: 1.5R.

## Important limitations
- Current version is a project scaffold and paper-research prototype.
- 4H bars are aggregated from hourly data; exchange-session-aware resampling needs validation.
- Historical backtest deliberately reports that a proper multi-timeframe backtest is not implemented. It does not fabricate results.
- Margin is not calculated. Obtain current margin from Angel One / exchange before any live use.
- Daily loss limit and max-open-trade controls are displayed as configuration; a portfolio-wide enforcement ledger is a next implementation step.
- No live order API calls exist in this project.
