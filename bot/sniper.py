import asyncio
import base64
import json
import struct
import time
import websockets

from .config import (
    SOLANA_RPC_WS_URL,
    PUMPFUN_PROGRAM_ID,
    MIN_LIQUIDITY_USD,
    MAX_LIQUIDITY_USD,
    DISCOVERY_TIMEOUT_SECONDS,
    DISCOVERY_POLL_SECONDS,
    MAX_OPEN_POSITIONS,
    POSITION_SIZE_SOL,
    HOLD_SECONDS,
)

CREATE_EVENT_DISCRIMINATOR = bytes([27, 114, 169, 77, 222, 235, 99, 118])


def _log(message):
    print(f"[SNIPER] {message}", flush=True)


def _read_string(buf, off):
    n = struct.unpack_from('<I', buf, off)[0]
    off += 4
    raw = buf[off:off+n]
    return raw.decode('utf-8', errors='replace'), off + n


def _b58(raw):
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n = int.from_bytes(raw, 'big')
    out = ''
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    pad = len(raw) - len(raw.lstrip(b'\x00'))
    return '1' * pad + (out or '')


def decode_create_event(encoded):
    try:
        data = base64.b64decode(encoded)
        if not data.startswith(CREATE_EVENT_DISCRIMINATOR):
            return None
        off = 8
        name, off = _read_string(data, off)
        symbol, off = _read_string(data, off)
        uri, off = _read_string(data, off)
        mint = _b58(data[off:off+32]); off += 32
        bonding_curve = _b58(data[off:off+32]); off += 32
        user = _b58(data[off:off+32]); off += 32
        creator = _b58(data[off:off+32]); off += 32
        timestamp = struct.unpack_from('<q', data, off)[0]; off += 8
        virtual_token_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        virtual_sol_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        real_token_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        token_total_supply = struct.unpack_from('<Q', data, off)[0]
        return {
            'name': name, 'symbol': symbol, 'uri': uri, 'mint': mint,
            'bonding_curve': bonding_curve, 'user': user, 'creator': creator,
            'timestamp': timestamp, 'virtual_sol_reserves': virtual_sol_reserves,
            'virtual_token_reserves': virtual_token_reserves,
            'real_sol_reserves': real_sol_reserves,
            'real_token_reserves': real_token_reserves,
            'token_total_supply': token_total_supply,
        }
    except Exception:
        return None


class PumpFunSniper:
    def __init__(self, db, scanner):
        self.db = db
        self.scanner = scanner
        self.seen = set()
        self.sem = asyncio.Semaphore(MAX_OPEN_POSITIONS)

    async def _wait_for_liquidity(self, event):
        deadline = time.monotonic() + DISCOVERY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            snap = await self.scanner.snapshot(event['mint'])
            if snap:
                liq = snap['liquidity_usd']
                if MIN_LIQUIDITY_USD <= liq <= MAX_LIQUIDITY_USD:
                    _log(f"LIQUIDITY ACCEPTED {event['symbol']} ${liq:.0f} pair={snap['pair_address']}")
                    return snap
                self.db.event('sniper_liquidity_seen', event['mint'], f"liquidity_usd={liq}")
            await asyncio.sleep(DISCOVERY_POLL_SECONDS)
        return None

    async def handle_create(self, event, signature):
        token = event['mint']
        if token in self.seen:
            return
        self.seen.add(token)
        self.db.event('pumpfun_create_detected', token, f"symbol={event['symbol']};name={event['name']};signature={signature};creator={event['creator']};timestamp={event['timestamp']}")
        _log(f"CREATE DETECTED {event['symbol']} name={event['name']} mint={token} sig={signature}")
        async with self.sem:
            snap = await self._wait_for_liquidity(event)
            if not snap:
                self.db.event('sniper_reject', token, 'liquidity_not_in_1200_2500_range')
                _log(f"REJECTED {event['symbol']} liquidity not in ${MIN_LIQUIDITY_USD:.0f}-${MAX_LIQUIDITY_USD:.0f} within {DISCOVERY_TIMEOUT_SECONDS:.1f}s")
                return
            trade_id = self.db.open_trade(token, event['symbol'], snap['pair_address'], snap['price_usd'], POSITION_SIZE_SOL, snap['liquidity_usd'])
            self.db.event('paper_buy', token, f"sniper=true;price={snap['price_usd']};size_sol={POSITION_SIZE_SOL};liquidity_usd={snap['liquidity_usd']};pair={snap['pair_address']};detection_signature={signature}")
            _log(f"PAPER BUY trade={trade_id} {event['symbol']} size={POSITION_SIZE_SOL} SOL price=${snap['price_usd']:.10g} liq=${snap['liquidity_usd']:.0f}")
            await asyncio.sleep(HOLD_SECONDS)
            exit_snap = await self.scanner.snapshot(token)
            if exit_snap and exit_snap['price_usd'] > 0:
                self.db.close_trade(trade_id, exit_snap['price_usd'], '15s_time_exit')
                self.db.event('paper_sell', token, f"sniper=true;price={exit_snap['price_usd']};trade_id={trade_id};reason=15s_time_exit;liquidity_usd={exit_snap['liquidity_usd']}")
                _log(f"PAPER SELL trade={trade_id} {event['symbol']} price=${exit_snap['price_usd']:.10g} after {HOLD_SECONDS:.1f}s liq=${exit_snap['liquidity_usd']:.0f}")
            else:
                self.db.event('exit_price_unavailable', token, f'trade_id={trade_id}')
                _log(f"EXIT PRICE UNAVAILABLE trade={trade_id} {event['symbol']}")

    async def run(self):
        while True:
            try:
                _log(f"CONNECTING websocket={SOLANA_RPC_WS_URL} program={PUMPFUN_PROGRAM_ID}")
                async with websockets.connect(SOLANA_RPC_WS_URL, ping_interval=20, ping_timeout=20, max_size=2**20) as ws:
                    await ws.send(json.dumps({
                        'jsonrpc': '2.0', 'id': 1, 'method': 'logsSubscribe',
                        'params': [{'mentions': [PUMPFUN_PROGRAM_ID]}, {'commitment': 'processed'}]
                    }))
                    ack = await ws.recv()
                    self.db.event('sniper_connected', payload=f'ws={SOLANA_RPC_WS_URL};ack={ack[:200]}')
                    _log(f"CONNECTED websocket ack={ack[:200]}")
                    async for raw in ws:
                        msg = json.loads(raw)
                        value = (((msg.get('params') or {}).get('result') or {}).get('value') or {})
                        if value.get('err') is not None:
                            continue
                        signature = value.get('signature', '')
                        for line in value.get('logs') or []:
                            if line.startswith('Program data: '):
                                event = decode_create_event(line.split(': ', 1)[1])
                                if event:
                                    asyncio.create_task(self.handle_create(event, signature))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.db.event('sniper_ws_error', payload=repr(exc))
                _log(f"WEBSOCKET ERROR {exc!r}; reconnecting in 2s")
                await asyncio.sleep(2)
