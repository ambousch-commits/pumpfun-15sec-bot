import asyncio
import threading

from .config import MODE, PORT, POSITION_SIZE_SOL, HOLD_SECONDS, MIN_LIQUIDITY_USD, MAX_LIQUIDITY_USD
from .db import DB
from .scanner import Scanner
from .dashboard import serve
from .sniper import PumpFunSniper

async def run():
    db = DB(__import__('os').getenv('DB_PATH', '/data/pumpfun-15sec.sqlite3'))
    scanner = Scanner()
    sniper = PumpFunSniper(db, scanner)
    threading.Thread(target=serve, args=(db, '0.0.0.0', PORT), daemon=True).start()
    db.event('bot_started', payload=(
        f'mode={MODE};strategy=pumpfun_event_sniper;size_sol={POSITION_SIZE_SOL};'
        f'liquidity_range_usd={MIN_LIQUIDITY_USD}-{MAX_LIQUIDITY_USD};hold_seconds={HOLD_SECONDS}'
    ))
    try:
        await sniper.run()
    finally:
        await scanner.close()
        db.close()

if __name__ == '__main__':
    asyncio.run(run())
