# Hybrid AI Commodity Swing System V1.1

Independent Streamlit project for MCX Crude Oil, Gold and Silver swing research. This project is separate from the Equity Trading Dashboard.

## V1.1 updates
- Manual paper BUY/SELL entry when a verified contract mapping is available.
- Validates BUY/SELL entry, stop-loss and target relationships.
- Calculates lots using configured per-trade risk and verified lot size.
- Enforces maximum open paper trade count and blocks new entries after the configured daily realized-loss limit is reached.
- Update open-trade stop loss / target and manually close a paper trade.
- Closed-trade history, realized P&L, win rate and CSV export.
- SQLite schema migration preserves existing paper trades.

## Safety
- Paper trading only. No broker order placement code is included.
- Never commit API keys, PIN, TOTP secret or access tokens.
- Do not invent MCX symbol tokens, expiry, lot size or tick size. Use current Angel One instrument master / MCX contract details.
- Daily loss gate currently uses realized P&L only; it does not include unrealized P&L or a live mark-to-market feed.
- Margin is not calculated. Check margin separately with Angel One before any real-world decision.
- The historical Daily + 4H backtest is not implemented. The app explicitly avoids fabricating performance results.
- Hourly-to-4H aggregation is a research approximation and requires validation against MCX session timestamps.
- Strategy rules are initial hypotheses, not proven profitable.

## Setup
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Configure Streamlit secrets using `.streamlit/secrets.toml.example`. Keep the real secrets file private.

Edit `contract_master.csv` with the currently active contracts and verified values:
`commodity,tradingsymbol,symboltoken,expiry,lotsize,ticksize`

Supported commodity labels: `Crude Oil`, `Gold`, `Silver`.
