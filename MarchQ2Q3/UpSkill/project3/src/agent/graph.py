from langgraph.graph import END, StateGraph

from src.agent.nodes import (
    await_approval_node,
    check_safety_node,
    create_pr_node,
    diagnose_node,
    escalate_node,
    gather_context_node,
    generate_fixes_node,
    notify_node,
    parse_event_node,
    validate_node,
)
from src.models.state import AgentState


def _should_retry(state: AgentState) -> str:
    """Decide whether to retry fix generation or proceed."""
    if state.get("validation_passed", False):
        return "check_safety"

    iteration = state.get("iteration", 0) + 1
    max_iter = state.get("max_iterations", 3)

    if iteration >= max_iter:
        return "escalate"

    return "generate_fixes"


def _after_safety(state: AgentState) -> str:
    """Route after safety check: escalate, await approval, or create PR directly."""
    if not state.get("validation_passed", False):
        return "escalate"
    if state.get("requires_human_approval", False):
        return "await_approval"
    return "create_pr"


def _after_approval(state: AgentState) -> str:
    """Route after approval gate: create PR if approved, escalate if rejected or timed out."""
    if not state.get("validation_passed", False):
        return "escalate"
    return "create_pr"


def build_graph() -> StateGraph:
    """Build the LangGraph state machine for the data agent."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("parse_event", parse_event_node)
    graph.add_node("gather_context", gather_context_node)
    graph.add_node("diagnose", diagnose_node)
    graph.add_node("generate_fixes", generate_fixes_node)
    graph.add_node("validate", validate_node)
    graph.add_node("check_safety", check_safety_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("create_pr", create_pr_node)
    graph.add_node("notify", notify_node)
    graph.add_node("escalate", escalate_node)

    # Define edges
    graph.set_entry_point("parse_event")
    graph.add_edge("parse_event", "gather_context")
    graph.add_edge("gather_context", "diagnose")
    graph.add_edge("diagnose", "generate_fixes")
    graph.add_edge("generate_fixes", "validate")

    # Conditional: retry loop or proceed
    graph.add_conditional_edges("validate", _should_retry)

    # Conditional: after safety
    graph.add_conditional_edges("check_safety", _after_safety)

    # Approval gate: poll for human decision, then route to create_pr or escalate
    graph.add_conditional_edges("await_approval", _after_approval)

    graph.add_edge("create_pr", "notify")
    graph.add_edge("notify", END)
    graph.add_edge("escalate", END)

    return graph


def compile_graph() -> object:
    """Compile the graph for execution."""
    return build_graph().compile()
