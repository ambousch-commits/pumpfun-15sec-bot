# Pump.fun Sniper 15sec Bot

Paper-trading research bot for fast Pump.fun launch detection.

- Pump.fun on-chain `CreateEvent` listener via Solana WebSocket
- Liquidity band: **$1,200–$2,500**
- Paper position size: **0.05 SOL**
- Exit: **15 seconds after paper entry**
- Fast `processed` log subscription for low-latency detection
- DexScreener used only to confirm the token pair, price and liquidity before paper entry
- Persistent SQLite trade/event history
- CSV exports
- Live stats dashboard
- Paper mode is enforced; no real-money transaction signing

The canonical Pump.fun program ID is `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`. Pump.fun documents its on-chain program and CreateEvent as the canonical way to observe new coin launches. Solana's `logsSubscribe` supports filtering transaction logs by a single mentioned pubkey.

Configure `SOLANA_RPC_WS_URL` in Railway for a reliable Solana WebSocket endpoint. Keep secrets in Railway variables and never commit private keys.
