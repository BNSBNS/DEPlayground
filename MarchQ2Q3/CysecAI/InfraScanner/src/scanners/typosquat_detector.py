"""Typosquatting detector — flag packages suspiciously similar to well-known ones."""

from __future__ import annotations

from src.models import Dependency, Ecosystem, TyposquatFinding

# Top 50 PyPI packages by download count (curated list for portfolio)
_TOP_PYPI: frozenset[str] = frozenset(
    {
        "boto3",
        "botocore",
        "certifi",
        "charset-normalizer",
        "click",
        "colorama",
        "cryptography",
        "decorator",
        "fastapi",
        "filelock",
        "idna",
        "importlib-metadata",
        "jinja2",
        "markupsafe",
        "numpy",
        "packaging",
        "pandas",
        "pillow",
        "pip",
        "platformdirs",
        "psutil",
        "pydantic",
        "pygments",
        "pytest",
        "python-dateutil",
        "python-dotenv",
        "pytz",
        "pyyaml",
        "regex",
        "requests",
        "rich",
        "s3transfer",
        "setuptools",
        "six",
        "soupsieve",
        "sqlalchemy",
        "tqdm",
        "typing-extensions",
        "urllib3",
        "uvicorn",
        "virtualenv",
        "wheel",
        "zipp",
    }
)

# Top 50 npm packages by download count (curated list)
_TOP_NPM: frozenset[str] = frozenset(
    {
        "accepts",
        "async",
        "axios",
        "balanced-match",
        "chalk",
        "commander",
        "debug",
        "express",
        "glob",
        "graceful-fs",
        "inherits",
        "isarray",
        "jest",
        "js-yaml",
        "lodash",
        "mime",
        "minimatch",
        "minimist",
        "mkdirp",
        "mocha",
        "moment",
        "ms",
        "node-fetch",
        "once",
        "path-is-absolute",
        "pump",
        "readable-stream",
        "react",
        "resolve",
        "rimraf",
        "semver",
        "source-map",
        "strip-ansi",
        "supports-color",
        "typescript",
        "uuid",
        "webpack",
        "wrappy",
        "yargs",
    }
)

_POPULAR_BY_ECOSYSTEM: dict[Ecosystem, frozenset[str]] = {
    Ecosystem.PYPI: _TOP_PYPI,
    Ecosystem.NPM: _TOP_NPM,
}


def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    # Early exits
    if a == b:
        return 0
    if m == 0:
        return n
    if n == 0:
        return m
    # Use a single rolling row
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = min(
                dp[j] + 1,  # deletion
                dp[j - 1] + 1,  # insertion
                prev + (0 if a[i - 1] == b[j - 1] else 1),  # substitution
            )
            prev = temp
    return dp[n]


def detect_typosquats(
    dependencies: list[Dependency],
    max_distance: int = 2,
) -> list[TyposquatFinding]:
    """Flag packages with names within `max_distance` edits of well-known packages."""
    findings: list[TyposquatFinding] = []

    for dep in dependencies:
        popular = _POPULAR_BY_ECOSYSTEM.get(dep.ecosystem)
        if popular is None:
            continue
        # Skip if the package IS a well-known package
        if dep.name in popular:
            continue

        for known in popular:
            dist = levenshtein(dep.name, known)
            if 0 < dist <= max_distance:
                findings.append(
                    TyposquatFinding(
                        package=dep.name,
                        similar_to=known,
                        distance=dist,
                        ecosystem=dep.ecosystem,
                    )
                )
                break  # Report closest match only

    return findings
