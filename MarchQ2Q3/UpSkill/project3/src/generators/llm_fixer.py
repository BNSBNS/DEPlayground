import structlog

from src.llm.factory import get_llm_provider
from src.models.diagnosis import Diagnosis
from src.models.events import PipelineFailureEvent
from src.models.fixes import FixType, GeneratedFix, RiskLevel

log = structlog.get_logger(__name__)

PROMPT_TEMPLATE = """You are a senior data engineer. A data pipeline has failed.

Error: {error_message}
Table: {table}
Column: {column}
Diagnosis: {diagnosis}
Evidence: {evidence}

Generate a SQL or dbt fix. Return ONLY the fix code, no explanation.
"""


async def generate_llm_fix(
    event: PipelineFailureEvent,
    diagnosis: Diagnosis,
) -> GeneratedFix | None:
    """Use LLM as fallback for complex fixes that templates cannot handle."""
    try:
        provider = get_llm_provider()
        prompt = PROMPT_TEMPLATE.format(
            error_message=event.error_message,
            table=event.affected_table,
            column=event.affected_column,
            diagnosis=diagnosis.explanation,
            evidence="; ".join(diagnosis.evidence),
        )
        response = await provider.generate(prompt)
        if not response.strip():
            return None

        return GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            file_path=f"migrations/llm_fix_{event.affected_table}.sql",
            content=response.strip(),
            description=f"LLM-generated fix for {event.affected_table}",
            risk_level=RiskLevel.HIGH,
        )
    except Exception:
        await log.aexception("llm_fix_generation_failed")
        return None
