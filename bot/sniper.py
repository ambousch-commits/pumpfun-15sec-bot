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

# Anchor discriminator for Pump.fun CreateEvent.
CREATE_EVENT_DISCRIMINATOR = bytes([27, 114, 169, 77, 222, 235, 99, 118])


def _read_string(buf, off):
    n = struct.unpack_from('<I', buf, off)[0]
    off += 4
    raw = buf[off:off+n]
    return raw.decode('utf-8', errors='replace'), off + n


def decode_create_event(encoded):
    try:
        data = base64.b64decode(encoded)
        if not data.startswith(CREATE_EVENT_DISCRIMINATOR):
            return None
        off = 8
        name, off = _read_string(data, off)
        symbol, off = _read_string(data, off)
        uri, off = _read_string(data, off)
        mint = data[off:off+32].hex(); off += 32
        bonding_curve = data[off:off+32].hex(); off += 32
        user = data[off:off+32].hex(); off += 32
        creator = data[off:off+32].hex(); off += 32
        timestamp = struct.unpack_from('<q', data, off)[0]; off += 8
        virtual_token_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        virtual_sol_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        real_token_reserves = struct.unpack_from('<Q', data, off)[0]; off += 8
        token_total_supply = struct.unpack_from('<Q', data, off)[0]
        # Reconstruct base58 addresses from bytes without a third-party package.
        def b58(raw):
            alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
            n = int.from_bytes(raw, 'big')
            out = ''
            while n:
                n, r = divmod(n, 58); out = alphabet[r] + out
            pad = len(raw) - len(raw.lstrip(b'\\x00'))
            return '1' * pad + (out or '')
        return {
            'name': name,
            'symbol': symbol,
            'uri': uri,
            'mint': b58(bytes.fromhex(mint)),
            'bonding_curve': b58(bytes.fromhex(bonding_curve)),
            'user': b58(bytes.fromhex(user)),
            'creator': b58(bytes.fromhex(creator)),
            'timestamp': timestamp,
            'virtual_sol_reserves': virtual_sol_reserves,
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
        self.active = set()
        self.seen = set()
        self.sem = asyncio.Semaphore(MAX_OPEN_POSITIONS)

    async def _wait_for_liquidity(self, event):
        deadline = time.monotonic() + DISCOVERY_TIMEOUT_SECONDS
        last = None
        while time.monotonic() < deadline:
            snap = await self.scanner.snapshot(event['mint'])
            if snap:
                last = snap
                liq = snap['liquidity_usd']
                if MIN_LIQUIDITY_USD <= liq <= MAX_LIQUIDITY_USD:
                    return snap
            await asyncio.sleep(DISCOVERY_POLL_SECONDS)
        if last:
            self.db.event('sniper_timeout', event['mint'], f"last_liquidity_usd={last['liquidity_usd']};min={MIN_LIQUIDITY_USD};max={MAX_LIQUIDITY_USD}")
        return None

    async def handle_create(self, event, signature):
        token = event['mint']
        if token in self.seen:
            return
        self.seen.add(token)
        self.db.event('pumpfun_create_detected', token, f"symbol={event['symbol']};name={event['name']};signature={signature};creator={event['creator']};timestamp={event['timestamp']}")
        async with self.sem:
            snap = await self._wait_for_liquidity(event)
            if not snap:
                self.db.event('sniper_reject', token, 'liquidity_not_in_1200_2500_range')
                return
            price = snap['price_usd']
            pair = snap['pair_address']
            trade_id = self.db.open_trade(token, event['symbol'], pair, price, POSITION_SIZE_SOL, snap['liquidity_usd'])
            self.active.add(token)
            self.db.event('paper_buy', token, f"sniper=true;price={price};size_sol={POSITION_SIZE_SOL};liquidity_usd={snap['liquidity_usd']};pair={pair};detection_signature={signature}")
            try:
                await asyncio.sleep(HOLD_SECONDS)
                exit_snap = await self.scanner.snapshot(token)
                if exit_snap and exit_snap['price_usd'] > 0:
                    self.db.close_trade(trade_id, exit_snap['price_usd'], '15s_time_exit')
                    self.db.event('paper_sell', token, f"sniper=true;price={exit_snap['price_usd']};trade_id={trade_id};reason=15s_time_exit;liquidity_usd={exit_snap['liquidity_usd']}")
                else:
                    self.db.event('exit_price_unavailable', token, f'trade_id={trade_id}')
            finally:
                self.active.discard(token)

    async def run(self):
        request_id = 1
        while True:
            try:
                async with websockets.connect(SOLANA_RPC_WS_URL, ping_interval=20, ping_timeout=20, max_size=2**20) as ws:
                    await ws.send(json.dumps({
                        'jsonrpc': '2.0', 'id': request_id, 'method': 'logsSubscribe',
                        'params': [{'mentions': [PUMPFUN_PROGRAM_ID]}, {'commitment': 'processed'}]
                    }))
                    request_id += 1
                    ack = await ws.recv()
                    self.db.event('sniper_connected', payload=f'ws={SOLANA_RPC_WS_URL};ack={ack[:200]}')
                    async for raw in ws:
                        msg = json.loads(raw)
                        value = (((msg.get('params') or {}).get('result') or {}).get('value') or {})
                        if value.get('err') is not None:
                            continue
                        signature = value.get('signature', '')
                        for line in value.get('logs') or []:
                            if not line.startswith('Program data: '):
                                continue
                            event = decode_create_event(line.split(': ', 1)[1])
                            if event:
                                asyncio.create_task(self.handle_create(event, signature))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.db.event('sniper_ws_error', payload=repr(exc))
                await asyncio.sleep(2)
