import sqlite3
import time
from pathlib import Path

class DB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS trades(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token_address TEXT NOT NULL,
          symbol TEXT,
          pair_address TEXT,
          entry_price REAL NOT NULL,
          exit_price REAL,
          entry_time REAL NOT NULL,
          exit_time REAL,
          size_sol REAL NOT NULL,
          liquidity_usd REAL,
          pnl_pct REAL,
          pnl_sol REAL,
          exit_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts REAL NOT NULL,
          event TEXT NOT NULL,
          token_address TEXT,
          payload TEXT
        );
        ''')
        self.conn.commit()

    def event(self, event, token=None, payload=''):
        self.conn.execute('INSERT INTO events(ts,event,token_address,payload) VALUES(?,?,?,?)',(time.time(),event,token,payload))
        self.conn.commit()

    def open_trade(self, token, symbol, pair, price, size_sol, liquidity):
        cur=self.conn.execute('INSERT INTO trades(token_address,symbol,pair_address,entry_price,entry_time,size_sol,liquidity_usd) VALUES(?,?,?,?,?,?,?)',(token,symbol,pair,price,time.time(),size_sol,liquidity))
        self.conn.commit(); return cur.lastrowid

    def close_trade(self, trade_id, exit_price, reason):
        row=self.conn.execute('SELECT entry_price,size_sol FROM trades WHERE id=?',(trade_id,)).fetchone()
        if not row:return
        pnl_pct=(exit_price/row['entry_price']-1.0)*100.0
        pnl_sol=row['size_sol']*pnl_pct/100.0
        self.conn.execute('UPDATE trades SET exit_price=?,exit_time=?,pnl_pct=?,pnl_sol=?,exit_reason=? WHERE id=?',(exit_price,time.time(),pnl_pct,pnl_sol,reason,trade_id))
        self.conn.commit()

    def close(self): self.conn.close()
