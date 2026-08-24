import httpx
from .config import DEXSCREENER_BASE_URL, MIN_LIQUIDITY_USD, MAX_LIQUIDITY_USD

PUMPFUN_IDENTIFIERS = ('pump.fun', 'pumpfun')

class Scanner:
    def __init__(self):
        self.client=httpx.AsyncClient(base_url=DEXSCREENER_BASE_URL, timeout=10.0, headers={'User-Agent':'pumpfun-15sec-bot/1.0'})

    async def discover(self):
        candidates=[]
        for q in ('pump.fun','pumpfun'):
            r=await self.client.get('/latest/dex/search',params={'q':q})
            r.raise_for_status()
            for p in r.json().get('pairs') or []:
                if str(p.get('chainId','')).lower()!='solana': continue
                url=str(p.get('url') or '').lower()
                dex=str(p.get('dexId') or '').lower()
                if not any(x in url or x in dex for x in PUMPFUN_IDENTIFIERS): continue
                liq=float((p.get('liquidity') or {}).get('usd') or 0)
                if liq < MIN_LIQUIDITY_USD or liq > MAX_LIQUIDITY_USD: continue
                price=float(p.get('priceUsd') or 0)
                if price<=0: continue
                candidates.append({
                    'token_address':str((p.get('baseToken') or {}).get('address') or ''),
                    'symbol':str((p.get('baseToken') or {}).get('symbol') or ''),
                    'pair_address':str(p.get('pairAddress') or ''),
                    'price_usd':price,
                    'liquidity_usd':liq,
                    'url':str(p.get('url') or ''),
                    'created_at':int(p.get('pairCreatedAt') or 0),
                })
        out={x['pair_address']:x for x in candidates if x['pair_address']}
        return sorted(out.values(), key=lambda x:x['liquidity_usd'], reverse=True)

    async def price(self, token_address):
        r=await self.client.get(f'/latest/dex/tokens/{token_address}')
        r.raise_for_status()
        pairs=r.json().get('pairs') or []
        sol=[p for p in pairs if str(p.get('chainId','')).lower()=='solana']
        if not sol:return None
        sol.sort(key=lambda p:float((p.get('liquidity') or {}).get('usd') or 0), reverse=True)
        return float(sol[0].get('priceUsd') or 0) or None

    async def close(self): await self.client.aclose()
