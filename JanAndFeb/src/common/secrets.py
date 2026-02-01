"""Secret management with multi-source fallback.

This module provides a unified interface for loading secrets from multiple sources:
1. Kubernetes Secrets (mounted as files at /run/secrets/)
2. Docker Secrets (mounted as files at /run/secrets/)
3. Environment variables from .env.secrets file
4. Regular environment variables (fallback)

For Kubernetes compatibility, secrets are loaded in order of precedence:
K8s Secrets > Docker Secrets > .env.secrets > Environment Variables > Defaults

Usage:
    from src.common.secrets import get_secret, SecretsManager

    # Simple usage
    password = get_secret("POSTGRES_PASSWORD", default="trading")

    # With validation
    manager = SecretsManager()
    manager.require("POSTGRES_PASSWORD", "FINNHUB_API_KEY")
    manager.validate()  # Raises if required secrets are missing
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecretNotFoundError(Exception):
    """Raised when a required secret is not found in any source."""

    def __init__(self, secret_name: str, sources_checked: list[str]):
        self.secret_name = secret_name
        self.sources_checked = sources_checked
        super().__init__(
            f"Secret '{secret_name}' not found. "
            f"Checked sources: {', '.join(sources_checked)}"
        )


class SecretsManager:
    """Manages secrets from multiple sources with fallback chain.

    Sources are checked in order:
    1. Kubernetes/Docker secrets (/run/secrets/<name>)
    2. .env.secrets file (if exists)
    3. Environment variables
    4. Default values

    Attributes:
        k8s_secrets_path: Path to mounted Kubernetes secrets
        env_secrets_file: Path to .env.secrets file
        required_secrets: Set of secret names that must be present
    """

    def __init__(
        self,
        k8s_secrets_path: str = "/run/secrets",
        env_secrets_file: str | None = None,
    ):
        """Initialize the secrets manager.

        Args:
            k8s_secrets_path: Path where K8s/Docker secrets are mounted
            env_secrets_file: Path to .env.secrets file (auto-detected if None)
        """
        self.k8s_secrets_path = Path(k8s_secrets_path)
        self._required_secrets: set[str] = set()
        self._cached_secrets: dict[str, str] = {}
        self._env_secrets: dict[str, str] = {}

        # Auto-detect .env.secrets file
        if env_secrets_file:
            self.env_secrets_file = Path(env_secrets_file)
        else:
            # Look in common locations
            candidates = [
                Path.cwd() / ".env.secrets",
                Path.cwd().parent / ".env.secrets",
                Path(__file__).parent.parent.parent.parent / ".env.secrets",
            ]
            self.env_secrets_file = next(
                (p for p in candidates if p.exists()),
                Path.cwd() / ".env.secrets"
            )

        self._load_env_secrets_file()

    def _load_env_secrets_file(self) -> None:
        """Load secrets from .env.secrets file if it exists."""
        if self.env_secrets_file.exists():
            logger.info(
                "Loading secrets from file",
                file=str(self.env_secrets_file),
            )
            try:
                with open(self.env_secrets_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key and value:
                                self._env_secrets[key] = value
                logger.debug(
                    "Loaded secrets from file",
                    count=len(self._env_secrets),
                )
            except Exception as e:
                logger.warning(
                    "Failed to load .env.secrets file",
                    error=str(e),
                )

    def _read_k8s_secret(self, name: str) -> str | None:
        """Read a secret from Kubernetes/Docker secrets mount.

        Args:
            name: Secret name (file name in secrets directory)

        Returns:
            Secret value if found, None otherwise
        """
        # Try lowercase (K8s convention)
        secret_file = self.k8s_secrets_path / name.lower()
        if secret_file.exists():
            return secret_file.read_text().strip()

        # Try uppercase (Docker convention)
        secret_file = self.k8s_secrets_path / name.upper()
        if secret_file.exists():
            return secret_file.read_text().strip()

        # Try original case
        secret_file = self.k8s_secrets_path / name
        if secret_file.exists():
            return secret_file.read_text().strip()

        return None

    def get(
        self,
        name: str,
        default: str | None = None,
        required: bool = False,
    ) -> str | None:
        """Get a secret value from available sources.

        Sources are checked in order:
        1. Cache (if previously loaded)
        2. K8s/Docker secrets mount
        3. .env.secrets file
        4. Environment variables
        5. Default value

        Args:
            name: Secret name
            default: Default value if not found
            required: If True, raise error when not found

        Returns:
            Secret value or default

        Raises:
            SecretNotFoundError: If required and not found
        """
        # Check cache first
        if name in self._cached_secrets:
            return self._cached_secrets[name]

        sources_checked = []
        value = None

        # 1. Check K8s/Docker secrets mount
        if self.k8s_secrets_path.exists():
            value = self._read_k8s_secret(name)
            sources_checked.append(f"k8s:{self.k8s_secrets_path}")
            if value:
                logger.debug("Secret loaded from K8s/Docker mount", secret=name)
                self._cached_secrets[name] = value
                return value

        # 2. Check .env.secrets file
        if name in self._env_secrets:
            value = self._env_secrets[name]
            sources_checked.append(f"file:{self.env_secrets_file}")
            logger.debug("Secret loaded from .env.secrets", secret=name)
            self._cached_secrets[name] = value
            return value
        sources_checked.append(f"file:{self.env_secrets_file}")

        # 3. Check environment variables
        value = os.environ.get(name)
        sources_checked.append("environment")
        if value:
            logger.debug("Secret loaded from environment", secret=name)
            self._cached_secrets[name] = value
            return value

        # 4. Use default
        if default is not None:
            logger.debug(
                "Using default value for secret",
                secret=name,
                has_default=True,
            )
            return default

        # 5. Handle required secrets
        if required:
            raise SecretNotFoundError(name, sources_checked)

        return None

    def require(self, *secret_names: str) -> "SecretsManager":
        """Mark secrets as required.

        Args:
            *secret_names: Names of required secrets

        Returns:
            Self for method chaining
        """
        self._required_secrets.update(secret_names)
        return self

    def validate(self) -> None:
        """Validate that all required secrets are available.

        Raises:
            SecretNotFoundError: If any required secret is missing
        """
        missing = []
        for name in self._required_secrets:
            try:
                value = self.get(name, required=True)
                if not value:
                    missing.append(name)
            except SecretNotFoundError:
                missing.append(name)

        if missing:
            raise SecretNotFoundError(
                f"Missing required secrets: {', '.join(missing)}",
                ["k8s", ".env.secrets", "environment"],
            )

    def get_all(self) -> dict[str, str]:
        """Get all loaded secrets (from cache and env file).

        Returns:
            Dictionary of secret names to values
        """
        # Merge env secrets and cached secrets
        all_secrets = dict(self._env_secrets)
        all_secrets.update(self._cached_secrets)
        return all_secrets

    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cached_secrets.clear()


# Global singleton instance
_secrets_manager: SecretsManager | None = None


@lru_cache(maxsize=1)
def _get_secrets_manager() -> SecretsManager:
    """Get or create the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_secret(
    name: str,
    default: str | None = None,
    required: bool = False,
) -> str | None:
    """Get a secret value (convenience function).

    This is the recommended way to access secrets in application code.

    Args:
        name: Secret name
        default: Default value if not found
        required: If True, raise error when not found

    Returns:
        Secret value or default

    Example:
        >>> password = get_secret("POSTGRES_PASSWORD", default="trading")
        >>> api_key = get_secret("FINNHUB_API_KEY", required=True)
    """
    return _get_secrets_manager().get(name, default, required)


def require_secrets(*secret_names: str) -> None:
    """Validate that required secrets are available.

    Call this at application startup to fail fast if secrets are missing.

    Args:
        *secret_names: Names of required secrets

    Raises:
        SecretNotFoundError: If any required secret is missing

    Example:
        >>> require_secrets("POSTGRES_PASSWORD", "FINNHUB_API_KEY")
    """
    manager = _get_secrets_manager()
    manager.require(*secret_names)
    manager.validate()
