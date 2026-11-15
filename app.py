from __future__ import annotations
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import CAPITAL_DEFAULT, RISK_PER_TRADE_DEFAULT, DAILY_LOSS_LIMIT_DEFAULT, MAX_OPEN_TRADES_DEFAULT
from angel_data import AngelData
from contracts import load_contracts, save_contract_template
from paper_engine import (init_db, add_paper_trade, list_paper_trades, close_paper_trade,
                          update_paper_trade, daily_realized_pnl, open_trade_count)
from risk_manager import calculate_lots, validate_expiry
from strategies.crude_strategy import generate_signal as crude_signal
from strategies.gold_strategy import generate_signal as gold_signal
from strategies.silver_strategy import generate_signal as silver_signal
from backtests.engine import run_backtest

st.set_page_config(page_title='Hybrid AI Commodity Swing V1.1', page_icon='🪙', layout='wide')
init_db()
STRATEGIES = {
    'Crude Oil': ('CRUDEOILM', crude_signal),
    'Gold': ('GOLDM', gold_signal),
    'Silver': ('SILVERM', silver_signal),
}

st.title('🪙 Hybrid AI Commodity Swing System V1.1')
st.caption('MCX • Angel One SmartAPI • Daily + 4H Swing • Paper Trading Only')

with st.sidebar:
    st.header('Paper Risk Settings')
    capital = st.number_input('Research Capital (₹)', min_value=1000, value=CAPITAL_DEFAULT, step=5000)
    risk = st.number_input('Risk per trade (₹)', min_value=50, value=RISK_PER_TRADE_DEFAULT, step=50)
    daily_limit = st.number_input('Daily loss limit (₹)', min_value=100, value=DAILY_LOSS_LIMIT_DEFAULT, step=100)
    max_open = st.number_input('Maximum open paper trades', min_value=1, max_value=3, value=MAX_OPEN_TRADES_DEFAULT)
    st.warning('Paper mode only. No broker orders are placed.')

@st.cache_resource
def get_angel():
    return AngelData()

angel = get_angel()
contracts = load_contracts()
contract_by_name = {r['commodity']: r for r in contracts if r.get('symboltoken') and r.get('tradingsymbol')}


def get_data(symbol, token, days=180):
    if not angel.ready:
        raise RuntimeError('Angel SmartAPI credentials/session not configured. Configure Setup first.')
    end = datetime.now(ZoneInfo('Asia/Kolkata'))
    start = end - timedelta(days=days)
    daily = angel.candles(symbol, token, 'ONE_DAY', start, end)
    h1 = angel.candles(symbol, token, 'ONE_HOUR', start, end)
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    if daily is not None and not daily.empty:
        daily = daily[daily.index.date < today].copy()
    h4 = pd.DataFrame()
    if h1 is not None and not h1.empty:
        h4 = h1.resample('4h', origin='start_day', offset='9h', label='right', closed='right').agg({
            'open':'first','high':'max','low':'min','close':'last','volume':'sum'
        }).dropna(subset=['open','high','low','close'])
    return daily, h4


def risk_gate():
    realised = daily_realized_pnl()
    if realised <= -float(daily_limit):
        raise RuntimeError(f'Daily loss limit reached. Realized P&L today: ₹{realised:,.2f}. New paper entries blocked.')
    if open_trade_count() >= int(max_open):
        raise RuntimeError(f'Maximum open paper trades ({max_open}) reached.')


def scan_one(name):
    contract = contract_by_name.get(name)
    if not contract:
        raise RuntimeError(f'{name} contract is not mapped. Complete contract_master.csv in Setup.')
    if not validate_expiry(contract.get('expiry','')):
        raise RuntimeError('Contract expiry is invalid or less than 5 days away.')
    daily, h4 = get_data(contract['tradingsymbol'], contract['symboltoken'])
    result = STRATEGIES[name][1](daily, h4)
    return contract, daily, h4, result


tabs = st.tabs(['Overview','Crude Oil','Gold','Silver','Risk Manager','Backtest','Paper Trading','Setup'])

with tabs[0]:
    st.subheader('Commodity Market Overview')
    st.info('Signals remain disabled until valid MCX contract metadata and Angel One data are available.')
    cols = st.columns(3)
    for col, name in zip(cols, STRATEGIES):
        col.metric(name, 'CONTRACT MAPPED' if name in contract_by_name else 'NOT CONFIGURED')
        col.caption('Paper mode • No orders')
    st.subheader('Open Paper Positions')
    open_rows = list_paper_trades('OPEN')
    st.dataframe(pd.DataFrame(open_rows) if open_rows else pd.DataFrame(), use_container_width=True, hide_index=True)

for tab, name in zip(tabs[1:4], STRATEGIES):
    with tab:
        st.subheader(f'{name} – Independent Swing Scanner')
        st.caption('Daily trend + 4H trigger. Strategy rules are research hypotheses, not guaranteed signals.')
        if st.button(f'Run {name} Scanner', key=f'scan_{name}'):
            try:
                st.session_state[f'data_{name}'] = scan_one(name)
            except Exception as exc:
                st.error(str(exc))
        cached = st.session_state.get(f'data_{name}')
        if cached:
            contract, daily, h4, result = cached
            st.write(f"Contract: {contract['tradingsymbol']} | Lot size: {contract['lotsize']} | Expiry: {contract['expiry']}")
            st.metric('Signal', result['signal'])
            st.write(result['reason'])
            if result.get('entry') and result.get('stop') and result.get('target'):
                sizing = calculate_lots(capital, risk, result['entry'], result['stop'], int(contract['lotsize']), float(contract['ticksize']))
                a,b,c = st.columns(3)
                a.metric('Lots', sizing['lots'])
                b.metric('Estimated Risk', f"₹{sizing['risk']:,.2f}")
                c.metric('Sizing Status', sizing['reason'])
                st.write(f"Entry ₹{result['entry']:.2f} | SL ₹{result['stop']:.2f} | Target ₹{result['target']:.2f}")
                if sizing['lots'] > 0 and result['signal'] in ('BUY','SELL'):
                    if st.button(f'Create Paper {result["signal"]} Trade', key=f'paper_{name}'):
                        try:
                            risk_gate()
                            add_paper_trade(commodity=name, symbol=contract['tradingsymbol'], side=result['signal'],
                                entry=result['entry'], stop=result['stop'], target=result['target'], lots=sizing['lots'],
                                lot_size=int(contract['lotsize']), risk=sizing['risk'], note=result['reason'])
                            st.success('Paper trade saved. No broker order was sent.')
                        except Exception as exc:
                            st.error(str(exc))
            st.subheader('Recent Daily Candles')
            st.dataframe(daily.tail(10), use_container_width=True)
            st.subheader('Recent 4H Candles')
            st.dataframe(h4.tail(10), use_container_width=True)

with tabs[4]:
    st.subheader('Commodity Risk Manager')
    st.write(f'Capital ₹{capital:,.0f} | Per-trade risk ₹{risk:,.0f} | Daily loss limit ₹{daily_limit:,.0f} | Max open trades {max_open}')
    realised = daily_realized_pnl()
    st.metric('Realized P&L Today', f'₹{realised:,.2f}')
    st.metric('Open Paper Trades', open_trade_count())
    st.info('Lot size, tick size, expiry and margin must be verified from current MCX contract details. Margin is not inferred.')
    st.dataframe(pd.DataFrame(contracts) if contracts else pd.DataFrame(columns=['commodity','tradingsymbol','symboltoken','expiry','lotsize','ticksize']), use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader('Historical Strategy Backtest')
    name = st.selectbox('Commodity', list(STRATEGIES), key='bt_commodity')
    st.warning('The current engine is a placeholder. A genuine Daily + 4H historical backtest is not implemented yet; no performance result is fabricated.')
    if st.button('Run Backtest', key='run_bt'):
        cached = st.session_state.get(f'data_{name}')
        if not cached:
            st.warning('Run the selected commodity scanner first to load data.')
        else:
            _, daily, _, _ = cached
            result = run_backtest(daily, STRATEGIES[name][1])
            st.json(result['metrics'])
            st.dataframe(result['trades'], use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader('Paper Trading Book')
    open_rows = list_paper_trades('OPEN')
    closed_rows = list_paper_trades('CLOSED')
    st.caption('Manual entries are allowed only when that commodity has a verified contract mapping.')
    mapped_names = [n for n in STRATEGIES if n in contract_by_name]
    with st.expander('➕ Create Manual Paper Trade', expanded=not bool(open_rows)):
        if not mapped_names:
            st.info('No verified MCX contracts are mapped yet. Add valid contract details in Setup before creating a trade.')
        else:
            with st.form('manual_trade_form'):
                commodity = st.selectbox('Commodity', mapped_names)
                side = st.selectbox('Side', ['BUY','SELL'])
                entry = st.number_input('Entry Price', min_value=0.01, value=100.0, step=0.1)
                stop = st.number_input('Stop Loss', min_value=0.01, value=98.0 if side == 'BUY' else 102.0, step=0.1)
                target = st.number_input('Target', min_value=0.01, value=103.0 if side == 'BUY' else 97.0, step=0.1)
                note = st.text_input('Trade note (optional)')
                submitted = st.form_submit_button('Calculate & Save Paper Trade')
            if submitted:
                try:
                    risk_gate()
                    contract = contract_by_name[commodity]
                    sizing = calculate_lots(capital, risk, entry, stop, int(contract['lotsize']), float(contract['ticksize']))
                    if sizing['lots'] < 1:
                        raise ValueError(f"No trade: {sizing['reason']}. Risk per lot ₹{sizing['risk_per_lot']:,.2f} exceeds ₹{risk:,.2f}.")
                    add_paper_trade(commodity=commodity, symbol=contract['tradingsymbol'], side=side,
                        entry=entry, stop=stop, target=target, lots=sizing['lots'], lot_size=int(contract['lotsize']),
                        risk=sizing['risk'], note=note)
                    st.success(f"Saved {side} paper trade: {sizing['lots']} lot(s), estimated risk ₹{sizing['risk']:,.2f}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    st.markdown('#### Open Positions')
    if open_rows:
        st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)
        ids = [int(r['id']) for r in open_rows]
        selected_id = st.selectbox('Select open trade', ids, format_func=lambda x: f"Trade #{x} — {next(r['commodity']+' '+r['side'] for r in open_rows if r['id']==x)}")
        selected = next(r for r in open_rows if r['id'] == selected_id)
        with st.expander('Update Stop Loss / Target'):
            with st.form('update_trade_form'):
                new_stop = st.number_input('New Stop Loss', min_value=0.01, value=float(selected['stop']), key='upd_sl')
                new_target = st.number_input('New Target', min_value=0.01, value=float(selected['target']), key='upd_tp')
                update_clicked = st.form_submit_button('Update SL / Target')
            if update_clicked:
                try:
                    update_paper_trade(selected_id, new_stop, new_target)
                    st.success('Paper trade levels updated.')
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with st.form('close_trade_form'):
            exit_price = st.number_input('Exit Price', min_value=0.01, value=float(selected['entry']), key='exit_price')
            exit_reason = st.selectbox('Exit Reason', ['MANUAL','STOP_LOSS','TARGET','OTHER'])
            close_clicked = st.form_submit_button('Close Paper Trade')
        if close_clicked:
            try:
                pnl = close_paper_trade(selected_id, exit_price, exit_reason)
                st.success(f'Paper trade closed. Realized P&L: ₹{pnl:,.2f}')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.info('No open positions.')

    st.markdown('#### Closed Positions / Trade History')
    if closed_rows:
        hist = pd.DataFrame(closed_rows)
        st.dataframe(hist, use_container_width=True, hide_index=True)
        total = float(hist['pnl'].fillna(0).sum())
        wins = int((hist['pnl'].fillna(0) > 0).sum())
        st.metric('Total Realized P&L', f'₹{total:,.2f}')
        st.metric('Win Rate', f'{wins / len(hist) * 100:.1f}%')
        st.download_button('Download Trade History CSV', hist.to_csv(index=False).encode('utf-8'), 'commodity_paper_trade_history.csv', 'text/csv')
    else:
        st.info('No closed paper trades yet.')

with tabs[7]:
    st.subheader('Angel One SmartAPI Setup')
    st.markdown('Set these as Streamlit secrets or environment variables: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`.')
    st.warning('Never paste API keys, PINs, TOTP secrets or access tokens into chat or GitHub. Use Streamlit Secrets.')
    st.code('''[angel]\napi_key = "YOUR_API_KEY"\nclient_code = "YOUR_CLIENT_CODE"\npin = "YOUR_PIN"\ntotp_secret = "YOUR_TOTP_SECRET"\n''', language='toml')
    st.subheader('MCX Contract Mapping')
    st.write('Fill `contract_master.csv` with current active MCX futures details from Angel One instrument master. Do not guess token, expiry, lot size or tick size.')
    st.download_button('Download contract_master.csv template', data=save_contract_template(), file_name='contract_master.csv', mime='text/csv')
    st.write('Connection status:', 'Credentials present' if angel.credentials_present else 'Credentials not configured')
    if st.button('Test Angel SmartAPI Login'):
        try:
            angel.login()
            st.success('Angel SmartAPI login successful. Data access only; this app has no live order placement.')
        except Exception as exc:
            st.error(f'Login failed: {exc}')
    st.caption('Historical candles: MCX Daily and 1-hour source candles aggregated to 4H. Validate session alignment and API entitlements before relying on signals.')

st.divider()
st.caption('Hybrid AI Commodity Swing System V1.1 | Paper Trading Only | No live order placement')
