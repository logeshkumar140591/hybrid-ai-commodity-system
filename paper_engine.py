import sqlite3
from pathlib import Path
from datetime import datetime
DB = Path("commodity_paper.db")

def connect():
    return sqlite3.connect(DB)

def init_db():
    with connect() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity TEXT, symbol TEXT, side TEXT,
            entry REAL, stop REAL, target REAL,
            lots INTEGER, lot_size INTEGER, risk REAL,
            note TEXT, status TEXT DEFAULT 'OPEN',
            opened_at TEXT, exit_price REAL, pnl REAL, closed_at TEXT
        )
        """)

def add_paper_trade(**kwargs):
    with connect() as con:
        con.execute("""
        INSERT INTO trades
        (commodity,symbol,side,entry,stop,target,lots,lot_size,risk,note,status,opened_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            kwargs["commodity"], kwargs["symbol"], kwargs["side"],
            kwargs["entry"], kwargs["stop"], kwargs["target"],
            kwargs["lots"], kwargs["lot_size"], kwargs["risk"],
            kwargs.get("note",""), "OPEN", datetime.now().isoformat()
        ))

def list_paper_trades(status=None):
    with connect() as con:
        con.row_factory = sqlite3.Row
        if status:
            rows = con.execute("SELECT * FROM trades WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def close_paper_trade(trade_id, exit_price):
    with connect() as con:
        row = con.execute("SELECT side,entry,lots,lot_size,status FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not row or row[4] != "OPEN":
            raise ValueError("Open paper trade not found.")
        side, entry, lots, lot_size, _ = row
        sign = 1 if side == "BUY" else -1
        pnl = (float(exit_price)-float(entry))*int(lots)*int(lot_size)*sign
        con.execute(
            "UPDATE trades SET status='CLOSED',exit_price=?,pnl=?,closed_at=? WHERE id=?",
            (float(exit_price), round(pnl,2), datetime.now().isoformat(), trade_id)
        )
