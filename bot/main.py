import asyncio
import threading
import time
from .config import MODE, PORT, POLL_SECONDS, POSITION_SIZE_SOL, HOLD_SECONDS, DB_PATH
from .db import DB
from .scanner import Scanner
from .dashboard import serve

async def run():
    db=DB(DB_PATH)
    scanner=Scanner()
    threading.Thread(target=serve,args=(db,'0.0.0.0',PORT),daemon=True).start()
    db.event('bot_started',payload=f'mode={MODE};size_sol={POSITION_SIZE_SOL};min_liquidity_usd=1200;hold_seconds={HOLD_SECONDS}')
    try:
        while True:
            try:
                candidates=await scanner.discover()
                for c in candidates:
                    price=c['price_usd']; token=c['token_address']
                    if not token or not c['pair_address']: continue
                    trade_id=db.open_trade(token,c['symbol'],c['pair_address'],price,POSITION_SIZE_SOL,c['liquidity_usd'])
                    db.event('paper_buy',token,f"symbol={c['symbol']};price={price};size_sol={POSITION_SIZE_SOL};liquidity_usd={c['liquidity_usd']};url={c['url']}")
                    await asyncio.sleep(HOLD_SECONDS)
                    exit_price=await scanner.price(token)
                    if exit_price and exit_price>0:
                        db.close_trade(trade_id,exit_price,'15s_time_exit')
                        db.event('paper_sell',token,f'price={exit_price};trade_id={trade_id};reason=15s_time_exit')
                    else:
                        db.event('exit_price_unavailable',token,f'trade_id={trade_id}')
                await asyncio.sleep(POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                db.event('loop_error',payload=repr(exc))
                await asyncio.sleep(min(30,max(2,POLL_SECONDS*2)))
    finally:
        await scanner.close(); db.close()

if __name__=='__main__': asyncio.run(run())
