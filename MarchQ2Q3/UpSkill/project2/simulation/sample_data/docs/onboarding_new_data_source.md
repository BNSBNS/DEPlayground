# Onboarding a New Data Source

## Process

1. **Request**: Submit a data source request in the #data-eng Slack channel with: source system name, tables needed, expected volume, refresh frequency, and business justification.

2. **Schema Review**: The data engineering team reviews the source schema and proposes a staging model design. Column naming follows our conventions (snake_case, descriptive names).

3. **Ingestion Setup**: Configure CDC or batch extraction. Raw data lands in the `raw` schema of the `warehouse` database. Each source gets its own schema prefix if multiple tables are involved.

4. **Staging Model**: Create a `stg_` model that handles type casting, renaming, and basic filtering. Add dbt tests for primary keys, not-null constraints, and foreign key relationships.

5. **Documentation**: Update the data dictionary and add descriptions to all columns in the dbt schema.yml file.

6. **Ownership**: Assign an owner from the responsible team. The owner is accountable for data quality and freshness SLAs.

7. **Monitoring**: Configure freshness and volume monitors. Set up alerts in the data_quality_monitor dashboard.

## Timeline

Typical onboarding takes 3-5 business days for simple sources (single table, batch) and 1-2 weeks for complex sources (multiple tables, streaming, custom transformations).
