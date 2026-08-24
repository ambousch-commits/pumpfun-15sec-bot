import os

MODE = os.getenv('MODE', 'paper')
PORT = int(os.getenv('PORT', '8080'))
POSITION_SIZE_SOL = float(os.getenv('POSITION_SIZE_SOL', '0.05'))
MIN_LIQUIDITY_USD = float(os.getenv('MIN_LIQUIDITY_USD', '1200'))
MAX_LIQUIDITY_USD = float(os.getenv('MAX_LIQUIDITY_USD', '2500'))
HOLD_SECONDS = float(os.getenv('HOLD_SECONDS', '15'))
DISCOVERY_TIMEOUT_SECONDS = float(os.getenv('DISCOVERY_TIMEOUT_SECONDS', '12'))
DISCOVERY_POLL_SECONDS = float(os.getenv('DISCOVERY_POLL_SECONDS', '0.5'))
MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '3'))
DEXSCREENER_BASE_URL = os.getenv('DEXSCREENER_BASE_URL', 'https://api.dexscreener.com')
SOLANA_RPC_WS_URL = os.getenv('SOLANA_RPC_WS_URL', 'wss://api.mainnet-beta.solana.com')
DB_PATH = os.getenv('DB_PATH', '/data/pumpfun-15sec.sqlite3')

# Canonical Pump program ID from Pump.fun public documentation.
PUMPFUN_PROGRAM_ID = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'

if MODE != 'paper':
    raise ValueError('MODE must be paper for this research bot')
if POSITION_SIZE_SOL <= 0:
    raise ValueError('POSITION_SIZE_SOL must be positive')
if MIN_LIQUIDITY_USD <= 0 or MAX_LIQUIDITY_USD < MIN_LIQUIDITY_USD:
    raise ValueError('Invalid liquidity range')
if HOLD_SECONDS <= 0:
    raise ValueError('HOLD_SECONDS must be positive')
if DISCOVERY_TIMEOUT_SECONDS <= 0 or DISCOVERY_POLL_SECONDS <= 0:
    raise ValueError('Invalid discovery timing')
if MAX_OPEN_POSITIONS < 1:
    raise ValueError('MAX_OPEN_POSITIONS must be at least 1')
