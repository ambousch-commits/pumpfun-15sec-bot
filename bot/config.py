import os

MODE = os.getenv('MODE', 'paper')
PORT = int(os.getenv('PORT', '8080'))
POLL_SECONDS = float(os.getenv('POLL_SECONDS', '2'))
POSITION_SIZE_SOL = float(os.getenv('POSITION_SIZE_SOL', '0.05'))
MIN_LIQUIDITY_USD = float(os.getenv('MIN_LIQUIDITY_USD', '1200'))
MAX_LIQUIDITY_USD = float(os.getenv('MAX_LIQUIDITY_USD', '2500'))
HOLD_SECONDS = float(os.getenv('HOLD_SECONDS', '15'))
DEXSCREENER_BASE_URL = os.getenv('DEXSCREENER_BASE_URL', 'https://api.dexscreener.com')
DB_PATH = os.getenv('DB_PATH', '/data/pumpfun-15sec.sqlite3')

PUMPFUN_PROGRAM_ID = '6EF8rrecthR5D6Yk2W7Nn2f8qB8pC3G9N8VnV8o7jD5T'

if MODE != 'paper':
    raise ValueError('MODE must be paper for this research bot')
if POSITION_SIZE_SOL <= 0:
    raise ValueError('POSITION_SIZE_SOL must be positive')
if MIN_LIQUIDITY_USD <= 0 or MAX_LIQUIDITY_USD < MIN_LIQUIDITY_USD:
    raise ValueError('Invalid liquidity range')
if HOLD_SECONDS <= 0:
    raise ValueError('HOLD_SECONDS must be positive')
