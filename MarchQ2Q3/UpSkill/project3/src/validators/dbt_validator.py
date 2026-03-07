import re


def validate_dbt_model(content: str) -> tuple[bool, list[str]]:
    """Basic validation for dbt SQL models (Jinja + SQL)."""
    errors: list[str] = []

    if not content.strip():
        errors.append("Empty dbt model")
        return False, errors

    # Check balanced Jinja braces
    open_expr = content.count("{{")
    close_expr = content.count("}}")
    if open_expr != close_expr:
        errors.append(f"Unbalanced Jinja expression braces: {open_expr} open, {close_expr} close")

    open_block = content.count("{%")
    close_block = content.count("%}")
    if open_block != close_block:
        errors.append(f"Unbalanced Jinja block braces: {open_block} open, {close_block} close")

    # Check ref/source calls are valid
    ref_pattern = re.compile(r"\{\{\s*ref\(\s*'[^']+'\s*\)\s*\}\}")
    source_pattern = re.compile(r"\{\{\s*source\(\s*'[^']+'\s*,\s*'[^']+'\s*\)\s*\}\}")
    jinja_expr = re.compile(r"\{\{.*?\}\}")

    for match in jinja_expr.finditer(content):
        expr = match.group(0)
        if "ref(" in expr and not ref_pattern.match(expr):
            errors.append(f"Invalid ref() syntax: {expr}")
        if "source(" in expr and not source_pattern.match(expr):
            errors.append(f"Invalid source() syntax: {expr}")

    return len(errors) == 0, errors


def validate_dbt_yaml(content: str) -> tuple[bool, list[str]]:
    """Basic YAML validation for dbt schema files."""
    errors: list[str] = []

    if not content.strip():
        errors.append("Empty YAML content")
        return False, errors

    if "version:" not in content:
        errors.append("Missing 'version:' key in schema YAML")

    if "models:" not in content and "sources:" not in content:
        errors.append("Missing 'models:' or 'sources:' key")

    return len(errors) == 0, errors
