import structlog

from src.analysis.classifier import classify_error
from src.analysis.context_builder import gather_context
from src.analysis.log_parser import extract_relevant_lines
from src.generators.dbt_fixer import generate_dbt_fix
from src.generators.pr_description import generate_pr_body, generate_pr_title
from src.generators.sql_fixer import generate_sql_fix
from src.generators.test_generator import generate_dbt_tests
from src.models.diagnosis import Diagnosis, DiagnosisCategory
from src.models.events import ErrorType
from src.models.fixes import FixProposal
from src.models.state import AgentState
from src.validators.dbt_validator import validate_dbt_model
from src.validators.safety import validate_safety
from src.validators.sql_validator import validate_sql

log = structlog.get_logger(__name__)

# Map ErrorType to DiagnosisCategory
_ERROR_TO_CATEGORY: dict[ErrorType, DiagnosisCategory] = {
    ErrorType.SCHEMA_MISMATCH: DiagnosisCategory.SCHEMA_DRIFT,
    ErrorType.NULL_VIOLATION: DiagnosisCategory.DATA_QUALITY,
    ErrorType.TYPE_MISMATCH: DiagnosisCategory.DATA_QUALITY,
    ErrorType.VOLUME_ANOMALY: DiagnosisCategory.DATA_QUALITY,
    ErrorType.MISSING_SOURCE: DiagnosisCategory.DEPENDENCY,
    ErrorType.PERMISSION_ERROR: DiagnosisCategory.PERMISSION,
    ErrorType.TIMEOUT: DiagnosisCategory.INFRASTRUCTURE,
    ErrorType.LOGIC_ERROR: DiagnosisCategory.LOGIC_ERROR,
    ErrorType.UNKNOWN: DiagnosisCategory.UNKNOWN,
}


async def parse_event_node(state: AgentState) -> AgentState:
    """Parse and classify the incoming event."""
    event = state["event"]
    error_type = classify_error(event.error_message)
    event.error_type = error_type

    logs = extract_relevant_lines(event.log_snippet)

    await log.ainfo("event_parsed", error_type=error_type, pipeline=event.pipeline_name)
    return {
        **state,
        "error_classification": error_type.value,
        "logs": logs,
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 3),
    }


async def gather_context_node(state: AgentState) -> AgentState:
    """Gather contextual information for diagnosis."""
    event = state["event"]
    context = await gather_context(event)
    await log.ainfo("context_gathered", table=event.affected_table)
    return {**state, "context": context}


async def diagnose_node(state: AgentState) -> AgentState:
    """Produce a diagnosis from classification + context."""
    event = state["event"]
    error_type = ErrorType(state.get("error_classification", "unknown"))
    category = _ERROR_TO_CATEGORY.get(error_type, DiagnosisCategory.UNKNOWN)

    confidence = 0.85 if category != DiagnosisCategory.UNKNOWN else 0.3

    diagnosis = Diagnosis(
        category=category,
        confidence=confidence,
        explanation=f"{category.value} detected: {event.error_message}",
        evidence=[event.error_message, event.log_snippet[:200] if event.log_snippet else ""],
        affected_objects=[event.affected_table, event.affected_column],
        suggested_approach=f"Apply {category.value} fix template",
    )

    await log.ainfo("diagnosis_complete", category=category, confidence=confidence)
    return {**state, "diagnosis": diagnosis}


async def generate_fixes_node(state: AgentState) -> AgentState:
    """Generate fix proposals based on diagnosis."""
    event = state["event"]
    diagnosis = state["diagnosis"]
    proposal = FixProposal()

    # Try SQL fix
    sql_fix = generate_sql_fix(event, diagnosis)
    if sql_fix:
        proposal.fixes.append(sql_fix)

    # Try dbt fix
    dbt_fix = generate_dbt_fix(event, diagnosis)
    if dbt_fix:
        proposal.fixes.append(dbt_fix)
        # Generate tests for dbt fixes
        test_fix = generate_dbt_tests(dbt_fix)
        if test_fix:
            proposal.fixes.append(test_fix)

    # Generate PR metadata
    proposal.pr_title = generate_pr_title(event, diagnosis)
    proposal.pr_body = generate_pr_body(event, diagnosis, proposal)

    await log.ainfo("fixes_generated", count=len(proposal.fixes))
    return {**state, "proposed_fixes": proposal}


async def validate_node(state: AgentState) -> AgentState:
    """Validate all proposed fixes."""
    proposal = state["proposed_fixes"]
    all_errors: list[str] = []

    for fix in proposal.fixes:
        if fix.file_path.endswith(".sql"):
            valid, errors = validate_sql(fix.content)
            if not valid:
                all_errors.extend(errors)
        elif fix.file_path.endswith(".yml") or fix.file_path.endswith(".yaml"):
            pass  # YAML validated by dbt_validator if needed
        elif "{{" in fix.content:
            valid, errors = validate_dbt_model(fix.content)
            if not valid:
                all_errors.extend(errors)

    passed = len(all_errors) == 0
    await log.ainfo("validation_complete", passed=passed, errors=all_errors)
    return {**state, "validation_passed": passed, "validation_errors": all_errors}


async def check_safety_node(state: AgentState) -> AgentState:
    """Run safety checks on all fixes."""
    proposal = state["proposed_fixes"]
    all_errors: list[str] = []

    for fix in proposal.fixes:
        safe, errors = validate_safety(fix)
        if not safe:
            all_errors.extend(errors)

    if all_errors:
        await log.awarning("safety_violations", errors=all_errors)
        return {
            **state,
            "validation_passed": False,
            "validation_errors": state.get("validation_errors", []) + all_errors,
            "requires_human_approval": True,
        }

    # High-risk fixes require approval
    requires_approval = any(
        fix.risk_level.value in ("high", "critical") for fix in proposal.fixes
    )
    await log.ainfo("safety_check_complete", requires_approval=requires_approval)
    return {**state, "requires_human_approval": requires_approval}


async def create_pr_node(state: AgentState) -> AgentState:
    """Create a PR (or simulate it)."""
    from src.actions.github import create_pull_request
    from src.config import get_settings

    settings = get_settings()
    proposal = state["proposed_fixes"]

    if settings.simulation_mode:
        pr_url = f"https://github.com/{settings.github_owner}/{settings.github_repo}/pull/SIM-1"
        await log.ainfo("pr_simulated", url=pr_url)
    else:
        pr_url = await create_pull_request(proposal)

    return {**state, "pr_url": pr_url}


async def notify_node(state: AgentState) -> AgentState:
    """Send notification about the fix."""
    from src.actions.slack import send_notification
    from src.config import get_settings

    settings = get_settings()

    if settings.simulation_mode:
        await log.ainfo("notification_simulated", pr_url=state.get("pr_url", ""))
    else:
        await send_notification(state)

    return {**state, "notification_sent": True}


async def await_approval_node(state: AgentState) -> AgentState:
    """Send approval request to Slack then poll until approved, rejected, or timed out.

    Polls the shared approval_store every 5 seconds. On timeout, sets validation_passed=False
    so the graph routes to escalate_node instead of create_pr_node.
    """
    import asyncio

    from src.actions.approval import request_approval
    from src.approval_store import get_approval
    from src.config import get_settings

    settings = get_settings()
    proposal = state["proposed_fixes"]
    pr_url = state.get("pr_url", "")
    timeout = settings.approval_timeout_seconds
    poll_interval = 5

    await request_approval(proposal, pr_url)
    await log.ainfo(
        "awaiting_approval",
        proposal_id=str(proposal.proposal_id),
        timeout_seconds=timeout,
    )

    elapsed = 0
    while elapsed < timeout:
        decision = get_approval(str(proposal.proposal_id))
        if decision:
            if decision["action"] == "approved":
                await log.ainfo("approval_received", reviewer=decision.get("reviewer", ""))
                return {**state, "requires_human_approval": False}
            await log.awarning("approval_rejected", reviewer=decision.get("reviewer", ""))
            return {
                **state,
                "validation_passed": False,
                "error": f"fix rejected by {decision.get('reviewer', 'reviewer')}",
            }
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    await log.awarning("approval_timeout", elapsed_seconds=elapsed)
    return {
        **state,
        "validation_passed": False,
        "error": f"approval timeout after {timeout}s",
    }


async def escalate_node(state: AgentState) -> AgentState:
    """Escalate when fixes cannot be auto-resolved."""
    from src.actions.escalate import send_escalation

    await send_escalation(state)
    await log.awarning("escalated", error=state.get("error", "max iterations exceeded"))
    return {**state, "notification_sent": True}
