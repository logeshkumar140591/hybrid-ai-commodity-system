from __future__ import annotations
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config import CAPITAL_DEFAULT, RISK_PER_TRADE_DEFAULT, DAILY_LOSS_LIMIT_DEFAULT
from angel_data import AngelData
from contracts import load_contracts, save_contract_template
from paper_engine import init_db, add_paper_trade, list_paper_trades, close_paper_trade
from risk_manager import calculate_lots, validate_expiry
from strategies.crude_strategy import generate_signal as crude_signal
from strategies.gold_strategy import generate_signal as gold_signal
from strategies.silver_strategy import generate_signal as silver_signal
from backtests.engine import run_backtest

st.set_page_config(page_title="Hybrid AI Commodity Swing V1.0", page_icon="🪙", layout="wide")
init_db()

STRATEGIES = {
    "Crude Oil": ("CRUDEOILM", crude_signal),
    "Gold": ("GOLDM", gold_signal),
    "Silver": ("SILVERM", silver_signal),
}

st.title("🪙 Hybrid AI Commodity Swing System V1.0")
st.caption("MCX • Angel One SmartAPI • Daily + 4H Swing • Paper Trading Only")

with st.sidebar:
    st.header("Paper Risk Settings")
    capital = st.number_input("Research Capital (₹)", min_value=1000, value=CAPITAL_DEFAULT, step=5000)
    risk = st.number_input("Risk per trade (₹)", min_value=50, value=RISK_PER_TRADE_DEFAULT, step=50)
    daily_limit = st.number_input("Daily loss limit (₹)", min_value=100, value=DAILY_LOSS_LIMIT_DEFAULT, step=100)
    max_open = st.number_input("Maximum open paper trades", min_value=1, max_value=3, value=2)
    st.warning("No broker orders are placed. All trades are simulated and stored locally.")

tabs = st.tabs(["Overview", "Crude Oil", "Gold", "Silver", "Risk Manager", "Backtest", "Paper Trading", "Setup"])

@st.cache_resource
def get_angel():
    return AngelData()

angel = get_angel()

def get_data(symbol, token, days=180):
    if not angel.ready:
        raise RuntimeError("Angel SmartAPI credentials/session not configured. Open Setup tab.")
    end = datetime.now(ZoneInfo("Asia/Kolkata"))
    start = end - timedelta(days=days)
    daily = angel.candles(symbol, token, "ONE_DAY", start, end)
    h1 = angel.candles(symbol, token, "ONE_HOUR", start, end)

    # Exclude the current unfinished daily candle.
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if daily is not None and not daily.empty:
        daily = daily[daily.index.date < today].copy()

    # Hourly candles are grouped into 4-hour research bars.
    # Session-aligned 4H aggregation must be validated against MCX timestamps.
    h4 = pd.DataFrame()
    if h1 is not None and not h1.empty:
        h4 = h1.resample(
            "4h",
            origin="start_day",
            offset="9h",
            label="right",
            closed="right",
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["open", "high", "low", "close"])

    return daily, h4

contracts = load_contracts()
contract_by_name = {r["commodity"]: r for r in contracts if r.get("symboltoken")}

def scan_one(name):
    contract = contract_by_name.get(name)
    if not contract:
        raise RuntimeError(f"{name} contract token missing. Complete contract_master.csv in Setup.")
    if not validate_expiry(contract.get("expiry", "")):
        raise RuntimeError("Contract expiry is invalid or too close. Select a valid active MCX contract.")
    daily, h4 = get_data(contract["tradingsymbol"], contract["symboltoken"])
    fn = STRATEGIES[name][1]
    result = fn(daily, h4)
    return contract, daily, h4, result

with tabs[0]:
    st.subheader("Commodity Market Overview")
    st.info(
        "Select a valid MCX futures contract token in Setup. "
        "Strategy signals remain disabled until valid contract metadata and data are available."
    )
    cols = st.columns(3)
    for col, name in zip(cols, STRATEGIES):
        col.metric(name, "NOT CONFIGURED" if name not in contract_by_name else "CONTRACT MAPPED")
        col.caption("Paper mode • No orders")
    st.subheader("Open Paper Positions")
    trades = list_paper_trades(status="OPEN")
    if trades:
        st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
    else:
        st.info("No open paper trades.")

for tab, name in zip(tabs[1:4], STRATEGIES):
    with tab:
        st.subheader(f"{name} – Independent Swing Scanner")
        st.caption("Strategy-specific conditions; Daily trend + 4H trigger. No signal is a guaranteed trade.")
        if st.button(f"Run {name} Scanner", key=f"scan_{name}"):
            try:
                contract, daily, h4, result = scan_one(name)
                st.session_state[f"data_{name}"] = (contract, daily, h4, result)
            except Exception as e:
                st.error(str(e))
        cached = st.session_state.get(f"data_{name}")
        if cached:
            contract, daily, h4, result = cached
            st.write(f"Contract: {contract['tradingsymbol']} | Lot size: {contract['lotsize']} | Expiry: {contract['expiry']}")
            st.metric("Signal", result["signal"])
            st.write(result["reason"])
            if result.get("entry") and result.get("stop"):
                sizing = calculate_lots(
                    capital=float(capital), risk_budget=float(risk),
                    entry=float(result["entry"]), stop=float(result["stop"]),
                    lot_size=int(contract["lotsize"]), tick_size=float(contract["ticksize"])
                )
                c1,c2,c3 = st.columns(3)
                c1.metric("Lots", sizing["lots"])
                c2.metric("Estimated Risk", f"₹{sizing['risk']:.2f}")
                c3.metric("Estimated Margin", "Manual broker check required")
                st.write(f"Indicative Entry ₹{result['entry']:.2f} | SL ₹{result['stop']:.2f} | Target ₹{result['target']:.2f}")
                if sizing["lots"] > 0 and result["signal"] in ("BUY","SELL"):
                    if st.button(f"Create Paper {result['signal']} Trade", key=f"paper_{name}"):
                        add_paper_trade(
                            commodity=name, symbol=contract["tradingsymbol"],
                            side=result["signal"], entry=float(result["entry"]),
                            stop=float(result["stop"]), target=float(result["target"]),
                            lots=int(sizing["lots"]), lot_size=int(contract["lotsize"]),
                            risk=float(sizing["risk"]), note=result["reason"]
                        )
                        st.success("Paper trade saved. No broker order was sent.")
            st.subheader("Recent Daily Candles")
            st.dataframe(daily.tail(10), use_container_width=True)
            st.subheader("Recent 4H Candles")
            st.dataframe(h4.tail(10), use_container_width=True)

with tabs[4]:
    st.subheader("Commodity Risk Manager")
    st.write(f"Capital ₹{capital:,.0f} | Per-trade risk ₹{risk:,.0f} | Daily loss limit ₹{daily_limit:,.0f} | Max open trades {max_open}")
    st.info("Lot size, tick size and expiry must be verified from the current MCX contract master. Margin is not inferred by this tool.")
    if contracts:
        st.dataframe(pd.DataFrame(contracts), use_container_width=True, hide_index=True)
    else:
        st.warning("No contract mappings loaded.")

with tabs[5]:
    st.subheader("Historical Strategy Backtest")
    name = st.selectbox("Commodity", list(STRATEGIES))
    if st.button("Run Backtest", key="run_bt"):
        cached = st.session_state.get(f"data_{name}")
        if not cached:
            st.warning("Run the selected commodity scanner first to load data.")
        else:
            contract, daily, h4, _ = cached
            result = run_backtest(daily, STRATEGIES[name][1])
            st.json(result["metrics"])
            st.dataframe(result["trades"], use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Paper Trading Book")
    open_trades = list_paper_trades("OPEN")
    closed_trades = list_paper_trades("CLOSED")
    st.write("Open positions")
    if open_trades:
        st.dataframe(pd.DataFrame(open_trades), use_container_width=True, hide_index=True)
    else:
        st.info("No open positions.")
    if open_trades:
        ids = [str(x["id"]) for x in open_trades]
        selected = st.selectbox("Select paper trade to close", ids)
        exit_price = st.number_input("Exit price", min_value=0.01, value=100.0)
        if st.button("Close Paper Trade"):
            close_paper_trade(int(selected), float(exit_price))
            st.success("Paper trade closed.")
            st.rerun()
    st.write("Closed positions")
    if closed_trades:
        st.dataframe(pd.DataFrame(closed_trades), use_container_width=True, hide_index=True)
    else:
        st.info("No closed paper trades.")

with tabs[7]:
    st.subheader("Angel One SmartAPI Setup")
    st.markdown("Set these as Streamlit secrets or environment variables: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`.")
    st.warning("Never paste API keys, PINs, TOTP secrets or access tokens into chat or GitHub. Use Streamlit Secrets.")
    st.markdown("Angel SmartAPI requires Client Code, PIN and TOTP. This app does not place orders.")
    st.code("""[angel]
api_key = "YOUR_API_KEY"
client_code = "YOUR_CLIENT_CODE"
pin = "YOUR_PIN"
totp_secret = "YOUR_TOTP_SECRET"
""", language="toml")
    st.subheader("MCX Contract Mapping")
    st.write("Fill `contract_master.csv` with current active contract details from Angel One's instrument master / MCX contract list. Do not guess tokens, expiry, lot size or tick size.")
    st.download_button("Download contract_master.csv template", data=save_contract_template(), file_name="contract_master.csv", mime="text/csv")
    st.write("Connection status:", "Credentials present" if angel.credentials_present else "Credentials not configured")
    if st.button("Test Angel SmartAPI Login"):
        try:
            angel.login()
            st.success("Angel SmartAPI login successful. Session is for data access in this paper-trading app.")
        except Exception as e:
            st.error(f"Login failed: {e}")
    st.caption("Historical candles: MCX exchange, Daily and 1-hour source candles aggregated to 4H. Confirm data entitlement and API limits with Angel One.")

st.divider()
st.caption("Hybrid AI Commodity Swing V1.0 | Paper Trading Only | No live order placement")
