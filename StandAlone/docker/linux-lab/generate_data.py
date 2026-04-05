"""Generate sample trading data files for the Linux CLI lab.

Run once: python generate_data.py
Outputs to ./data/
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# --- Instruments ---

INSTRUMENTS = [
    ("I001", "AAPL", "NASDAQ", "EQUITY", "USD", "0.01", "1"),
    ("I002", "MSFT", "NASDAQ", "EQUITY", "USD", "0.01", "1"),
    ("I003", "GOOGL", "NASDAQ", "EQUITY", "USD", "0.01", "1"),
    ("I004", "AMZN", "NASDAQ", "EQUITY", "USD", "0.01", "1"),
    ("I005", "TSLA", "NASDAQ", "EQUITY", "USD", "0.01", "1"),
    ("I006", "JPM", "NYSE", "EQUITY", "USD", "0.01", "1"),
    ("I007", "GS", "NYSE", "EQUITY", "USD", "0.01", "1"),
    ("I008", "BAC", "NYSE", "EQUITY", "USD", "0.01", "1"),
    ("I009", "WFC", "NYSE", "EQUITY", "USD", "0.01", "1"),
    ("I010", "C", "NYSE", "EQUITY", "USD", "0.01", "1"),
    ("I011", "EURUSD", "CME", "FX", "USD", "0.00001", "1000"),
    ("I012", "GBPUSD", "CME", "FX", "USD", "0.00001", "1000"),
    ("I013", "USDJPY", "CME", "FX", "JPY", "0.001", "1000"),
    ("I014", "CL", "NYMEX", "COMMODITY", "USD", "0.01", "1000"),
    ("I015", "GC", "COMEX", "COMMODITY", "USD", "0.10", "100"),
]

INST_HEADER_CSV = "instrument_id,symbol,venue,asset_class,currency,tick_size,lot_size"
INST_HEADER_TSV = "instrument_id\tsymbol\tvenue\tasset_class\tcurrency\ttick_size\tlot_size"

with open(os.path.join(DATA_DIR, "instruments_comma.csv"), "w", newline="") as f:
    f.write(INST_HEADER_CSV + "\n")
    for row in INSTRUMENTS:
        f.write(",".join(row) + "\n")

with open(os.path.join(DATA_DIR, "instruments.tsv"), "w", newline="") as f:
    f.write(INST_HEADER_TSV + "\n")
    for row in INSTRUMENTS:
        f.write("\t".join(row) + "\n")

# --- Price generators ---

BASE_PRICES = {
    "AAPL": 178.50, "MSFT": 405.20, "GOOGL": 141.80, "AMZN": 185.60,
    "TSLA": 245.30, "JPM": 195.40, "GS": 385.10, "BAC": 33.80,
    "WFC": 49.20, "C": 53.10, "EURUSD": 1.0875, "GBPUSD": 1.2680,
    "USDJPY": 148.25, "CL": 72.50, "GC": 2045.30,
}

INST_MAP = {row[0]: row[1] for row in INSTRUMENTS}


def jitter_price(base: float, pct: float = 0.02) -> float:
    return round(base * (1 + random.uniform(-pct, pct)), 2)


# --- Trades (100 rows) ---

base_time = datetime(2024, 1, 15, 9, 30, 0)

with open(os.path.join(DATA_DIR, "trades.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["trade_id", "instrument_id", "symbol", "price", "volume", "side", "timestamp"])
    for i in range(1, 101):
        inst = random.choice(INSTRUMENTS)
        inst_id, symbol = inst[0], inst[1]
        price = jitter_price(BASE_PRICES[symbol])
        volume = random.choice([10, 25, 50, 100, 200, 500, 1000])
        side = random.choice(["BUY", "SELL"])
        ts = base_time + timedelta(seconds=random.randint(0, 23400))
        w.writerow([
            f"T{i:04d}", inst_id, symbol,
            f"{price:.2f}", volume, side,
            ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(0, 999):03d}Z",
        ])


# --- Quotes (80 rows) ---

with open(os.path.join(DATA_DIR, "quotes.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["instrument_id", "symbol", "bid", "ask", "spread", "timestamp"])
    for i in range(80):
        inst = random.choice(INSTRUMENTS)
        inst_id, symbol = inst[0], inst[1]
        base = BASE_PRICES[symbol]
        bid = jitter_price(base, 0.015)
        spread = round(base * random.uniform(0.0001, 0.002), 4)
        ask = round(bid + spread, 4)
        ts = base_time + timedelta(seconds=random.randint(0, 23400))
        w.writerow([
            inst_id, symbol, f"{bid:.4f}", f"{ask:.4f}", f"{spread:.4f}",
            ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(0, 999):03d}Z",
        ])


# --- Orders (morning: 40, afternoon: 35) ---

def write_orders(path: str, count: int, start_hour: int, end_hour: int) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "instrument_id", "symbol", "side", "quantity", "order_type", "timestamp"])
        # Use a subset of symbols for interesting join/comm exercises
        order_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "JPM", "GS", "EURUSD", "CL"]
        for i in range(1, count + 1):
            symbol = random.choice(order_symbols)
            inst_id = next(r[0] for r in INSTRUMENTS if r[1] == symbol)
            side = random.choice(["BUY", "SELL"])
            qty = random.choice([10, 25, 50, 100, 500])
            otype = random.choice(["LIMIT", "MARKET", "STOP"])
            ts = base_time.replace(hour=start_hour) + timedelta(
                seconds=random.randint(0, (end_hour - start_hour) * 3600)
            )
            w.writerow([
                f"O{start_hour}{i:03d}", inst_id, symbol, side, qty, otype,
                ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(0, 999):03d}Z",
            ])


write_orders(os.path.join(DATA_DIR, "orders_morning.csv"), 40, 9, 12)
write_orders(os.path.join(DATA_DIR, "orders_afternoon.csv"), 35, 13, 16)


# --- Application log (60 lines) ---

LOG_TEMPLATES = [
    ("INFO", "market_data_consumer", "connected to kafka broker at kafka:9092"),
    ("INFO", "market_data_consumer", "processing batch of {n} trades"),
    ("INFO", "ingestion_pipeline", "wrote {n} records to timescaledb"),
    ("INFO", "api_server", "health check passed"),
    ("INFO", "api_server", "request completed: GET /api/v1/trades duration={d}ms"),
    ("WARN", "market_data_consumer", "high latency detected: {d}ms for {sym} trade"),
    ("WARN", "ingestion_pipeline", "duplicate trade_id detected: T{tid}, skipping"),
    ("WARN", "api_server", "slow query: {d}ms for symbol={sym}"),
    ("ERROR", "market_data_consumer", "connection to kafka lost: broker not available"),
    ("ERROR", "ingestion_pipeline", "schema validation failed: missing field 'volume'"),
    ("ERROR", "ingestion_pipeline", "connection to postgres lost: timeout after 30s"),
    ("ERROR", "api_server", "internal server error: division by zero in vwap calculation"),
]

with open(os.path.join(DATA_DIR, "app.log"), "w") as f:
    ts = datetime(2024, 1, 15, 9, 30, 0)
    for i in range(60):
        ts += timedelta(seconds=random.randint(1, 120))
        level, component, msg = random.choice(LOG_TEMPLATES)
        msg = msg.format(
            n=random.randint(10, 500),
            d=random.randint(5, 800),
            sym=random.choice(["AAPL", "MSFT", "GOOGL", "TSLA", "JPM"]),
            tid=random.randint(1000, 9999),
        )
        f.write(f"{ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:23]} {level:5s} [{component}] {msg}\n")


# --- HTTP access log (50 lines, Apache combined format) ---

ENDPOINTS = [
    ("GET", "/api/v1/trades?symbol=AAPL", 200, 1234),
    ("GET", "/api/v1/trades?symbol=MSFT", 200, 2345),
    ("GET", "/api/v1/quotes/latest", 200, 567),
    ("GET", "/api/v1/instruments", 200, 890),
    ("POST", "/api/v1/trades/ingest", 201, 45),
    ("POST", "/api/v1/trades/ingest", 400, 123),
    ("GET", "/api/v1/trades?symbol=INVALID", 404, 78),
    ("GET", "/api/v1/health", 200, 12),
    ("GET", "/api/v1/aggregates?window=1m", 200, 3456),
    ("GET", "/api/v1/trades?symbol=GOOGL", 500, 0),
    ("GET", "/api/v1/trades?limit=1000", 200, 8901),
    ("DELETE", "/api/v1/cache", 204, 0),
]

CLIENTS = [
    "192.168.1.10", "192.168.1.11", "192.168.1.15",
    "10.0.5.20", "10.0.5.21", "10.0.5.42",
]

USER_AGENTS = [
    "python-requests/2.31.0",
    "curl/8.4.0",
    "Mozilla/5.0 (compatible; Monitoring/1.0)",
    "Go-http-client/2.0",
]

with open(os.path.join(DATA_DIR, "access.log"), "w") as f:
    ts = datetime(2024, 1, 15, 9, 30, 0)
    for _ in range(50):
        ts += timedelta(seconds=random.randint(1, 60))
        client = random.choice(CLIENTS)
        method, path, status, size = random.choice(ENDPOINTS)
        ua = random.choice(USER_AGENTS)
        f.write(
            f'{client} - - [{ts.strftime("%d/%b/%Y:%H:%M:%S")} +0000] '
            f'"{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"\n'
        )

print("Generated all sample data files in", DATA_DIR)
for fn in sorted(os.listdir(DATA_DIR)):
    path = os.path.join(DATA_DIR, fn)
    if os.path.isfile(path):
        with open(path) as fh:
            lines = fh.readlines()
        print(f"  {fn}: {len(lines)} lines")
