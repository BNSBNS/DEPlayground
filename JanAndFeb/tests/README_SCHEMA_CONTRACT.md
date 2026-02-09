# Schema Contract Test (Fix #4)

## Purpose
The schema contract test validates that the `TradeAggregate` model, database schema, and SQL statements stay in sync. This prevents schema drift when fields are added to the model but forgotten in the database migration or SQL queries.

## What It Catches

###  Issue #1: Missing LMP Fields in UPSERT SQL

**Current State:**
- `TradeAggregate` model HAS: `lmp`, `lmp_energy`, `lmp_congestion`, `lmp_loss` fields
- Database schema HAS: `lmp`, `lmp_energy`, `lmp_congestion`, `lmp_loss` columns (from migration 004)
- **DatabaseWriter.UPSERT_AGGREGATE_SQL MISSING**: LMP fields! ❌

**Location:** `src/consumer/db_writer.py` lines 46-63

**Current SQL:**
```sql
INSERT INTO trade_aggregates (
    symbol, window_start, window_end, vwap, total_volume,
    trade_count, max_price, min_price, created_at, updated_at
)
VALUES (
    %(symbol)s, %(window_start)s, %(window_end)s, %(vwap)s, %(total_volume)s,
    %(trade_count)s, %(max_price)s, %(min_price)s, NOW(), NOW()
)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,
    total_volume = EXCLUDED.total_volume,
    ...
```

**Missing:** `lmp`, `lmp_energy`, `lmp_congestion`, `lmp_loss`

**Impact:** LMP data computed in the consumer is **not being saved to the database**!

---

###  Issue #2: Missing LMP Fields in write_aggregates_batch() Params

**Current State:**
`write_aggregates_batch()` param extraction (lines 211-223) only includes:
```python
params_list = [
    {
        "symbol": agg.symbol,
        "window_start": agg.window_start,
        "window_end": agg.window_end,
        "vwap": agg.vwap,
        "total_volume": agg.total_volume,
        "trade_count": agg.trade_count,
        "max_price": agg.max_price,
        "min_price": agg.min_price,
    }
    for agg in aggregates
]
```

**Missing:** LMP fields!

---

###  Issue #3: Missing LMP Fields in get_latest_aggregates() SELECT

**Current State:**
`get_latest_aggregates()` SELECT clause (line 346) only queries:
```sql
SELECT symbol, window_start, window_end, vwap, total_volume,
       trade_count, max_price, min_price, created_at, updated_at
FROM trade_aggregates
```

**Missing:** LMP columns!

---

## How the Test Works

The test suite in `test_schema_contract.py` includes:

1. **`test_model_has_all_expected_fields`**
   Verifies `TradeAggregate` has all expected persisted fields

2. **`test_upsert_sql_includes_all_persisted_fields`** ⚠️ **WILL FAIL**
   Checks UPSERT SQL INSERT clause includes all persisted fields
   **Expected failure:** Missing `lmp`, `lmp_energy`, `lmp_congestion`, `lmp_loss`

3. **`test_upsert_sql_has_matching_values_placeholders`** ⚠️ **WILL FAIL**
   Validates VALUES placeholders match INSERT fields
   **Expected failure:** Missing `%(lmp)s`, etc.

4. **`test_upsert_sql_on_conflict_updates_all_mutable_fields`** ⚠️ **WILL FAIL**
   Checks ON CONFLICT UPDATE includes all updateable fields
   **Expected failure:** Missing LMP updates

5. **`test_write_aggregates_batch_prepares_correct_params`** ⚠️ **WILL FAIL**
   Validates param extraction includes all persisted fields
   **Expected failure:** Missing LMP in params dict

6. **`test_to_db_tuple_includes_all_persisted_fields`**  **WILL PASS**
   Verifies `to_db_tuple()` includes all persisted fields
   **Status:** Already correct! Includes LMP fields

7. **`test_model_only_fields_are_not_persisted`**  **WILL PASS**
   Ensures `total_value` (calculation-only field) is NOT in SQL

8. **`test_nullable_lmp_fields_have_defaults`**  **WILL PASS**
   Verifies LMP fields default to None for backward compatibility

9. **`test_database_schema_matches_model`**  **WILL PASS**
   Documents expected database schema

---

## Running the Test

### In Docker (Recommended):
```bash
# Start Docker Desktop, then:
docker compose -f docker-compose-full.yml run --rm consumer python -m pytest tests/test_schema_contract.py -v
```

### Expected Output (Before Fix):
```
FAILED test_upsert_sql_includes_all_persisted_fields - AssertionError: UPSERT SQL is missing these fields: {'lmp_congestion', 'lmp', 'lmp_loss', 'lmp_energy'}
FAILED test_upsert_sql_has_matching_values_placeholders - AssertionError: Missing placeholder for field 'lmp'...
FAILED test_upsert_sql_on_conflict_updates_all_mutable_fields - AssertionError: ON CONFLICT UPDATE is missing these fields: {'lmp_congestion', 'lmp', 'lmp_loss', 'lmp_energy'}
FAILED test_write_aggregates_batch_prepares_correct_params - AssertionError: write_aggregates_batch params missing these fields: {'lmp_congestion', 'lmp', 'lmp_loss', 'lmp_energy'}
```

---

## Fix Required

To pass all tests, update `src/consumer/db_writer.py`:

### 1. Update UPSERT_AGGREGATE_SQL (lines 46-63):
```python
UPSERT_AGGREGATE_SQL = """
    INSERT INTO trade_aggregates (
        symbol, window_start, window_end, vwap, total_volume,
        trade_count, max_price, min_price,
        lmp, lmp_energy, lmp_congestion, lmp_loss,  -- ADD THIS LINE
        created_at, updated_at
    )
    VALUES (
        %(symbol)s, %(window_start)s, %(window_end)s, %(vwap)s, %(total_volume)s,
        %(trade_count)s, %(max_price)s, %(min_price)s,
        %(lmp)s, %(lmp_energy)s, %(lmp_congestion)s, %(lmp_loss)s,  -- ADD THIS LINE
        NOW(), NOW()
    )
    ON CONFLICT (symbol, window_start) DO UPDATE SET
        vwap = EXCLUDED.vwap,
        total_volume = EXCLUDED.total_volume,
        trade_count = EXCLUDED.trade_count,
        max_price = EXCLUDED.max_price,
        min_price = EXCLUDED.min_price,
        window_end = EXCLUDED.window_end,
        lmp = EXCLUDED.lmp,  -- ADD THESE LINES
        lmp_energy = EXCLUDED.lmp_energy,
        lmp_congestion = EXCLUDED.lmp_congestion,
        lmp_loss = EXCLUDED.lmp_loss,
        updated_at = NOW()
"""
```

### 2. Update write_aggregate() params (lines 174-183):
```python
params = {
    "symbol": aggregate.symbol,
    "window_start": aggregate.window_start,
    "window_end": aggregate.window_end,
    "vwap": aggregate.vwap,
    "total_volume": aggregate.total_volume,
    "trade_count": aggregate.trade_count,
    "max_price": aggregate.max_price,
    "min_price": aggregate.min_price,
    "lmp": aggregate.lmp,  -- ADD THESE LINES
    "lmp_energy": aggregate.lmp_energy,
    "lmp_congestion": aggregate.lmp_congestion,
    "lmp_loss": aggregate.lmp_loss,
}
```

### 3. Update write_aggregates_batch() params (lines 211-223):
```python
params_list = [
    {
        "symbol": agg.symbol,
        "window_start": agg.window_start,
        "window_end": agg.window_end,
        "vwap": agg.vwap,
        "total_volume": agg.total_volume,
        "trade_count": agg.trade_count,
        "max_price": agg.max_price,
        "min_price": agg.min_price,
        "lmp": agg.lmp,  -- ADD THESE LINES
        "lmp_energy": agg.lmp_energy,
        "lmp_congestion": agg.lmp_congestion,
        "lmp_loss": agg.lmp_loss,
    }
    for agg in aggregates
]
```

### 4. Update get_latest_aggregates() SELECT (line 346):
```python
sql = """
    SELECT symbol, window_start, window_end, vwap, total_volume,
           trade_count, max_price, min_price,
           lmp, lmp_energy, lmp_congestion, lmp_loss,  -- ADD THIS LINE
           created_at, updated_at
    FROM trade_aggregates
"""
```

---

## Benefits

This test acts as a **"pre-requisite check"** that:

1. **Catches field additions early** - If someone adds a field to `TradeAggregate`, the test immediately fails until the database and SQL are updated
2. **Prevents data loss** - Catches cases where computed data (like LMP) isn't being persisted
3. **Documents the schema contract** - The test itself serves as living documentation of what should be persisted
4. **Low maintenance** - No database connection required, pure static analysis of code
5. **Fast feedback** - Runs in <1 second, can run on every commit

---

## Model-Only Fields

The test explicitly documents that `total_value` is a **model-only field** (used for VWAP calculation but not persisted). This is intentional and correct - we only store the final VWAP result, not the intermediate sum.
