# Linux CLI Lab Exercises

These exercises are designed to be done inside the `linux-lab` container.

## Start the lab

```bash
cd StandAlone/docker/linux-lab
docker compose up -d
docker exec -it linux-lab bash
```

## Sample data in /data/

| File | Rows | Description |
|------|------|-------------|
| `trades.csv` | 100 | Trades: trade_id, instrument_id, symbol, price, volume, side, timestamp |
| `quotes.csv` | 80 | Quotes: instrument_id, symbol, bid, ask, spread, timestamp |
| `instruments_comma.csv` | 15 | Instruments (CSV): id, symbol, venue, asset_class, currency, tick_size, lot_size |
| `instruments.tsv` | 15 | Instruments (TSV): same fields, tab-delimited |
| `orders_morning.csv` | 40 | Morning orders: order_id, instrument_id, symbol, side, quantity, order_type, timestamp |
| `orders_afternoon.csv` | 35 | Afternoon orders: same schema |
| `app.log` | 60 | Application log with INFO/WARN/ERROR levels |
| `access.log` | 50 | HTTP access log (Apache combined format) |

## Stop the lab

```bash
docker compose down
```
