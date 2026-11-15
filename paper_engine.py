import sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB = Path('commodity_paper.db')


def connect():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
            entry REAL NOT NULL, stop REAL NOT NULL, target REAL NOT NULL,
            lots INTEGER NOT NULL, lot_size INTEGER NOT NULL, risk REAL NOT NULL,
            note TEXT DEFAULT '', status TEXT DEFAULT 'OPEN', opened_at TEXT,
            exit_price REAL, pnl REAL, closed_at TEXT,
            updated_at TEXT
        )''')
        existing = {r['name'] for r in con.execute('PRAGMA table_info(trades)').fetchall()}
        additions = {
            'updated_at': 'TEXT',
            'exit_reason': 'TEXT',
        }
        for name, typ in additions.items():
            if name not in existing:
                con.execute(f'ALTER TABLE trades ADD COLUMN {name} {typ}')
        con.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)')


def add_paper_trade(**kw):
    side = str(kw['side']).upper()
    if side not in ('BUY', 'SELL'):
        raise ValueError('Side must be BUY or SELL.')
    entry, stop, target = float(kw['entry']), float(kw['stop']), float(kw['target'])
    lots, lot_size = int(kw['lots']), int(kw['lot_size'])
    if entry <= 0 or stop <= 0 or target <= 0 or lots <= 0 or lot_size <= 0:
        raise ValueError('Entry, SL, target, lots and lot size must be positive.')
    if side == 'BUY' and not stop < entry < target:
        raise ValueError('For BUY: Stop Loss < Entry < Target.')
    if side == 'SELL' and not target < entry < stop:
        raise ValueError('For SELL: Target < Entry < Stop Loss.')
    now = datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        con.execute('''INSERT INTO trades
            (commodity,symbol,side,entry,stop,target,lots,lot_size,risk,note,status,opened_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (kw['commodity'], kw['symbol'], side, entry, stop, target, lots, lot_size,
             float(kw['risk']), kw.get('note',''), 'OPEN', now, now))


def list_paper_trades(status=None):
    with connect() as con:
        if status:
            rows = con.execute('SELECT * FROM trades WHERE status=? ORDER BY id DESC', (status,)).fetchall()
        else:
            rows = con.execute('SELECT * FROM trades ORDER BY id DESC').fetchall()
        return [dict(r) for r in rows]


def update_paper_trade(trade_id, stop, target):
    with connect() as con:
        row = con.execute('SELECT side,entry,status FROM trades WHERE id=?', (int(trade_id),)).fetchone()
        if not row or row['status'] != 'OPEN':
            raise ValueError('Open paper trade not found.')
        stop, target, entry = float(stop), float(target), float(row['entry'])
        if row['side'] == 'BUY' and not stop < entry < target:
            raise ValueError('For BUY: Stop Loss < Entry < Target.')
        if row['side'] == 'SELL' and not target < entry < stop:
            raise ValueError('For SELL: Target < Entry < Stop Loss.')
        con.execute('UPDATE trades SET stop=?,target=?,updated_at=? WHERE id=?',
                    (stop, target, datetime.now().isoformat(timespec='seconds'), int(trade_id)))


def close_paper_trade(trade_id, exit_price, reason='MANUAL'):
    exit_price = float(exit_price)
    if exit_price <= 0:
        raise ValueError('Exit price must be positive.')
    with connect() as con:
        row = con.execute('SELECT side,entry,lots,lot_size,status FROM trades WHERE id=?', (int(trade_id),)).fetchone()
        if not row or row['status'] != 'OPEN':
            raise ValueError('Open paper trade not found.')
        sign = 1 if row['side'] == 'BUY' else -1
        pnl = (exit_price - float(row['entry'])) * int(row['lots']) * int(row['lot_size']) * sign
        now = datetime.now().isoformat(timespec='seconds')
        con.execute('''UPDATE trades SET status='CLOSED',exit_price=?,pnl=?,closed_at=?,updated_at=?,exit_reason=? WHERE id=?''',
                    (exit_price, round(pnl, 2), now, now, reason, int(trade_id)))
        return round(pnl, 2)


def daily_realized_pnl():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    with connect() as con:
        row = con.execute("SELECT COALESCE(SUM(pnl),0) AS pnl FROM trades WHERE status='CLOSED' AND substr(closed_at,1,10)=?", (today,)).fetchone()
        return float(row['pnl'] or 0.0)


def open_trade_count():
    with connect() as con:
        return int(con.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0])
