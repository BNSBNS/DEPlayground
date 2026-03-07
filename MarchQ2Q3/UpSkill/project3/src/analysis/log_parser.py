import re


def extract_relevant_lines(log_snippet: str, max_lines: int = 30) -> str:
    """Extract error-relevant lines from a log snippet."""
    if not log_snippet.strip():
        return ""

    lines = log_snippet.strip().splitlines()
    relevant: list[str] = []
    error_patterns = re.compile(r"(error|exception|traceback|failed|fatal)", re.I)

    for i, line in enumerate(lines):
        if error_patterns.search(line):
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            relevant.extend(lines[start:end])

    if not relevant:
        # Fall back to last N lines
        relevant = lines[-max_lines:]

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for line in relevant:
        if line not in seen:
            seen.add(line)
            deduped.append(line)

    return "\n".join(deduped[:max_lines])


def extract_traceback(log_snippet: str) -> str:
    """Extract Python traceback from logs if present."""
    tb_pattern = re.compile(
        r"Traceback \(most recent call last\):.*?(?=\n\S|\Z)",
        re.DOTALL,
    )
    match = tb_pattern.search(log_snippet)
    return match.group(0) if match else ""
