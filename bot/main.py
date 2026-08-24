import asyncio
import os
import threading

from .config import MODE, PORT, POSITION_SIZE_SOL, HOLD_SECONDS, MIN_LIQUIDITY_USD, MAX_LIQUIDITY_USD
from .db import DB
from .scanner import Scanner
from .dashboard import serve
from .sniper import PumpFunSniper

async def heartbeat(db):
    while True:
        db.set_status('running', 'scanner heartbeat')
        await asyncio.sleep(10)

async def run():
    db = DB(os.getenv('DB_PATH', '/data/pumpfun-15sec.sqlite3'))
    scanner = Scanner()
    sniper = PumpFunSniper(db, scanner)
    threading.Thread(target=serve, args=(db, '0.0.0.0', PORT), daemon=True).start()
    db.set_status('starting', 'initializing Pump.fun sniper')
    db.event('bot_started', payload=(
        f'mode={MODE};strategy=pumpfun_event_sniper;size_sol={POSITION_SIZE_SOL};'
        f'liquidity_range_usd={MIN_LIQUIDITY_USD}-{MAX_LIQUIDITY_USD};hold_seconds={HOLD_SECONDS}'
    ))
    hb = asyncio.create_task(heartbeat(db))
    try:
        db.set_status('running', f'paper sniper; Pump.fun; liquidity=${MIN_LIQUIDITY_USD:.0f}-${MAX_LIQUIDITY_USD:.0f}; hold={HOLD_SECONDS:.0f}s')
        await sniper.run()
    except asyncio.CancelledError:
        db.set_status('stopped', 'process cancelled')
        raise
    except Exception as exc:
        db.set_status('error', repr(exc))
        db.event('bot_fatal_error', payload=repr(exc))
        raise
    finally:
        hb.cancel()
        await scanner.close()
        db.close()

if __name__ == '__main__':
    asyncio.run(run())
