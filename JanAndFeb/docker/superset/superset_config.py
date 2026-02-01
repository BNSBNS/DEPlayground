# Superset configuration file
# This file is mounted into the container at /app/pythonpath/superset_config.py

import os

# =============================================================================
# Superset specific config
# =============================================================================
ROW_LIMIT = 5000
SUPERSET_WEBSERVER_PORT = 8088

# =============================================================================
# Flask App Builder configuration
# =============================================================================
# Your App secret key will be used for securely signing the session cookie
# Make sure to change this for production
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "energy-trading-dev-key")

# =============================================================================
# Database configuration
# =============================================================================
# The SQLAlchemy connection string to your database backend
# This connects to the same PostgreSQL used for trade data
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql://trading:trading@timescaledb:5432/trades"
)

# =============================================================================
# Cache configuration (Redis)
# =============================================================================
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
}

# =============================================================================
# Feature flags
# =============================================================================
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "EMBEDDED_SUPERSET": True,
}

# =============================================================================
# Security - CSRF and CORS
# =============================================================================
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.api.Api"]
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["http://localhost:3000", "http://localhost:8080"],
}

# =============================================================================
# SQL Lab
# =============================================================================
SQL_MAX_ROW = 100000
DISPLAY_MAX_ROW = 10000

# =============================================================================
# Logging
# =============================================================================
LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
LOG_LEVEL = "INFO"
