# Schema Contract Test

## Purpose
The schema contract test validates that the `TradeAggregate` model, database schema, and SQL statements stay in sync. This prevents schema drift when fields are added to the model but forgotten in the database migration or SQL queries.

## What It Validates

The test checks that `db_writer.py` SQL and param extraction are in sync with the `TradeAggregate` model.

### Persisted Fields

All of these fields must appear in the UPSERT SQL, VALUES placeholders, ON CONFLICT UPDATE, param dicts, and SELECT queries:

- `symbol`, `window_start`, `window_end`
- `vwap`, `total_volume`, `trade_count`, `max_price`, `min_price`
- `lmp`, `lmp_energy`, `lmp_congestion`, `lmp_loss`
- `created_at`, `updated_at` (managed by SQL `NOW()`)

### Model-Only Fields

`total_value` is a **model-only field** (used for VWAP calculation but not persisted). This is intentional and correct - we only store the final VWAP result, not the intermediate sum.

---

## How the Test Works

The test suite in `test_schema_contract.py` includes:

1. **`test_model_has_all_expected_fields`**
   Verifies `TradeAggregate` has all expected persisted fields

2. **`test_upsert_sql_includes_all_persisted_fields`**
   Checks UPSERT SQL INSERT clause includes all persisted fields

3. **`test_upsert_sql_has_matching_values_placeholders`**
   Validates VALUES placeholders match INSERT fields

4. **`test_upsert_sql_on_conflict_updates_all_mutable_fields`**
   Checks ON CONFLICT UPDATE includes all updateable fields

5. **`test_write_aggregates_batch_prepares_correct_params`**
   Validates param extraction includes all persisted fields

6. **`test_to_db_tuple_includes_all_persisted_fields`**
   Verifies `to_db_tuple()` includes all persisted fields

7. **`test_model_only_fields_are_not_persisted`**
   Ensures `total_value` (calculation-only field) is NOT in SQL

8. **`test_nullable_lmp_fields_have_defaults`**
   Verifies LMP fields default to None for backward compatibility

9. **`test_database_schema_matches_model`**
   Documents expected database schema

---

## Running the Test

### In Docker (Recommended):
```bash
# Start Docker Desktop, then:
docker compose -f docker-compose-full.yml run --rm consumer python -m pytest tests/test_schema_contract.py -v
```

### Expected Output:
```
PASSED test_model_has_all_expected_fields
PASSED test_upsert_sql_includes_all_persisted_fields
PASSED test_upsert_sql_has_matching_values_placeholders
PASSED test_upsert_sql_on_conflict_updates_all_mutable_fields
PASSED test_write_aggregates_batch_prepares_correct_params
PASSED test_to_db_tuple_includes_all_persisted_fields
PASSED test_model_only_fields_are_not_persisted
PASSED test_nullable_lmp_fields_have_defaults
PASSED test_database_schema_matches_model
```

---

## Benefits

This test acts as a **"pre-requisite check"** that:

1. **Catches field additions early** - If someone adds a field to `TradeAggregate`, the test immediately fails until the database and SQL are updated
2. **Prevents data loss** - Catches cases where computed data (like LMP) isn't being persisted
3. **Documents the schema contract** - The test itself serves as living documentation of what should be persisted
4. **Low maintenance** - No database connection required, pure static analysis of code
5. **Fast feedback** - Runs in <1 second, can run on every commit
