from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / 'signal_flow.db'

DEMO_USER = 'demo'
BOOTSTRAP_CANDLES = 60
TICK_SECONDS = 2
CANDLE_INTERVAL_SECONDS = 5
SIGNAL_DEDUP_SECONDS = 60
MARKETS = {
    'BTC-KRW': {'name': 'Bitcoin', 'market_type': 'COIN', 'base_price': 145_000_000.0, 'volatility': 0.006},
    'ETH-KRW': {'name': 'Ethereum', 'market_type': 'COIN', 'base_price': 5_100_000.0, 'volatility': 0.008},
    'XRP-KRW': {'name': 'XRP', 'market_type': 'COIN', 'base_price': 920.0, 'volatility': 0.015},
}
