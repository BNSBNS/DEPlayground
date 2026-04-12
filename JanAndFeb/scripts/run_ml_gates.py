"""Run ML quality gates inside the ml-trainer container.

Usage (from JanAndFeb/):
    docker-compose --profile ml run --rm --user 0 \
        -v "%cd%:/workspace" -w /workspace \
        --entrypoint python ml-trainer scripts/run_ml_gates.py
"""

import subprocess
import sys


def run(cmd: list[str]) -> None:
    print(f"\n{'='*60}\n>>> {' '.join(cmd)}\n{'='*60}")
    subprocess.check_call(cmd)


run([
    sys.executable, "-m", "pip", "install", "--quiet",
    "ruff", "mypy", "pytest", "pytest-asyncio", "pytest-cov",
    "pandas-stubs", "types-python-dateutil",
])
run([sys.executable, "-m", "ruff", "check", "src/ml", "tests/unit/ml"])
run([sys.executable, "-m", "mypy", "src/ml", "--strict", "--follow-imports=silent"])
run([
    sys.executable, "-m", "pytest", "tests/unit/ml", "-v",
    "--cov=src/ml", "--cov-fail-under=0",
])

print("\n✓ All gates passed.")
