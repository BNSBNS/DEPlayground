#!/bin/bash
# Superset initialization script
# This runs on container startup to ensure Superset is properly configured

set -e

echo "=== Superset Initialization ==="

# Wait for the database to be ready
echo "Waiting for database..."
sleep 5

# Initialize the database (safe to run multiple times)
echo "Running database migrations..."
superset db upgrade

# Check if admin user exists
ADMIN_EXISTS=$(superset fab list-users | grep -c "${SUPERSET_ADMIN_USERNAME:-admin}" || true)

if [ "$ADMIN_EXISTS" -eq "0" ]; then
    echo "Creating admin user..."
    superset fab create-admin \
        --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
        --firstname Admin \
        --lastname User \
        --email "${SUPERSET_ADMIN_EMAIL:-admin@localhost}" \
        --password "${SUPERSET_ADMIN_PASSWORD:-admin}"
else
    echo "Admin user already exists, skipping..."
fi

# Initialize Superset (roles, permissions)
echo "Initializing Superset..."
superset init

# Import database connection from datasources.yaml
echo "Importing database connection..."
if [ -f /app/datasources.yaml ]; then
    superset import-datasources -p /app/datasources.yaml || echo "Datasource may already exist, continuing..."
else
    echo "Warning: datasources.yaml not found, skipping import"
fi

echo "=== Superset Initialization Complete ==="

# Check if this is first run (no datasets exist)
echo ""
echo "========================================"
echo "DASHBOARD SETUP (run once after startup)"
echo "========================================"
echo "To create pre-built dashboards, run:"
echo "  docker exec superset python /app/bootstrap_dashboards.py"
echo ""
echo "This creates:"
echo "  - 12 datasets from SQL views"
echo "  - 9 pre-configured charts"
echo "  - 1 Energy Trading dashboard"
echo "========================================"
echo ""

# Start Superset
exec superset run -h 0.0.0.0 -p 8088 --with-threads --reload
