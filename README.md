# Pump.fun 15sec Bot

Paper-trading bot specification:
- Pump.fun tokens only
- Minimum liquidity: $1,200
- Position size: 0.05 SOL
- Exit exactly 15 seconds after entry
- Persistent SQLite trade/event history
- CSV exports
- Live stats dashboard

Paper mode by default. Never commit secrets; configure API/RPC credentials through Railway environment variables.
