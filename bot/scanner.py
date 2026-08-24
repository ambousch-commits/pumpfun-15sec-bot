import httpx
from .config import DEXSCREENER_BASE_URL, MIN_LIQUIDITY_USD, MAX_LIQUIDITY_USD

PUMPFUN_IDENTIFIERS = ('pump.fun', 'pumpfun')

class Scanner:
    def __init__(self):
        self.client=httpx.AsyncClient(base_url=DEXSCREENER_BASE_URL, timeout=5.0, headers={'User-Agent':'pumpfun-15sec-bot/1.0'})

    @staticmethod
    def _is_pumpfun(p):
        url=str(p.get('url') or '').lower()
        dex=str(p.get('dexId') or '').lower()
        return any(x in url or x in dex for x in PUMPFUN_IDENTIFIERS)

    async def discover(self):
        candidates=[]
        for q in ('pump.fun','pumpfun'):
            r=await self.client.get('/latest/dex/search',params={'q':q})
            r.raise_for_status()
            for p in r.json().get('pairs') or []:
                if str(p.get('chainId','')).lower()!='solana' or not self._is_pumpfun(p): continue
                liq=float((p.get('liquidity') or {}).get('usd') or 0)
                if not MIN_LIQUIDITY_USD <= liq <= MAX_LIQUIDITY_USD: continue
                price=float(p.get('priceUsd') or 0)
                if price<=0: continue
                candidates.append(self._normalize(p, liq, price))
        out={x['pair_address']:x for x in candidates if x['pair_address']}
        return sorted(out.values(), key=lambda x:x['liquidity_usd'], reverse=True)

    @staticmethod
    def _normalize(p, liq, price):
        return {
            'token_address':str((p.get('baseToken') or {}).get('address') or ''),
            'symbol':str((p.get('baseToken') or {}).get('symbol') or ''),
            'pair_address':str(p.get('pairAddress') or ''),
            'price_usd':price,
            'liquidity_usd':liq,
            'url':str(p.get('url') or ''),
            'created_at':int(p.get('pairCreatedAt') or 0),
        }

    async def snapshot(self, token_address):
        r=await self.client.get(f'/latest/dex/tokens/{token_address}')
        r.raise_for_status()
        pairs=[p for p in (r.json().get('pairs') or []) if str(p.get('chainId','')).lower()=='solana' and self._is_pumpfun(p)]
        if not pairs:
            return None
        # Prefer the most liquid Pump.fun-origin Solana pair for the token.
        pairs.sort(key=lambda p:float((p.get('liquidity') or {}).get('usd') or 0), reverse=True)
        p=pairs[0]
        price=float(p.get('priceUsd') or 0)
        liq=float((p.get('liquidity') or {}).get('usd') or 0)
        if price<=0 or liq<=0:
            return None
        return self._normalize(p, liq, price)

    async def price(self, token_address):
        snap=await self.snapshot(token_address)
        return snap['price_usd'] if snap else None

    async def close(self):
        await self.client.aclose()
