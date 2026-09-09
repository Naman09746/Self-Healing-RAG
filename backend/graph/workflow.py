from langgraph.graph import StateGraph, END
from backend.graph.state import RAGState
from backend.graph.nodes import (
    create_intake_node,
    create_planning_node,
    create_retrieval_node,
    create_generation_node,
    create_critic_node,
    create_healing_node,
    create_evaluation_node,
    create_output_node,
)
from backend.graph.edges import should_heal, should_generate


def create_rag_graph(deps, checkpointer=None):
    """Create and compile the LangGraph workflow using injected dependencies.

    Args:
        deps: A ``ServiceContainer`` instance with all services initialized.
        checkpointer: Optional ``PostgresCheckpointer`` instance for stateful
                      checkpoint persistence across runs (Phase 4A).

    Returns:
        A compiled ``CompiledStateGraph`` ready for ``.astream()`` / ``.invoke()``.

    **Thread-safety**: The compiled graph is stateless — all per-request state
    lives in ``RAGState``. Multiple concurrent requests can safely share the
    same graph instance.
    """
    workflow = StateGraph(RAGState)

    # Build nodes with injected dependencies via factory functions
    workflow.add_node("intake", create_intake_node(deps))
    workflow.add_node("planning", create_planning_node(deps))
    workflow.add_node("retrieval", create_retrieval_node(deps))
    workflow.add_node("generation", create_generation_node(deps))
    workflow.add_node("critic", create_critic_node(deps))
    workflow.add_node("healing", create_healing_node(deps))
    workflow.add_node("evaluation", create_evaluation_node(deps))
    workflow.add_node("output", create_output_node(deps))

    # Set Entry Point
    workflow.set_entry_point("intake")

    # Add Edges
    workflow.add_edge("intake", "planning")
    workflow.add_edge("planning", "retrieval")

    # Fast-fail conditional edge: skip generation/critic if knowledge is absent
    workflow.add_conditional_edges(
        "retrieval",
        should_generate,
        {
            "generation": "generation",
            "output": "output",
        },
    )
    workflow.add_edge("generation", "critic")

    # Conditional Edge from Critic — Phase 3B: 4-way routing
    workflow.add_conditional_edges(
        "critic",
        should_heal,
        {
            "output": "evaluation",
            "targeted_healing": "healing",
            "retrieval_expansion": "healing",
            "aggressive_rewrite": "healing",
        },
    )

    # Healing loops back to Retrieval (single node handles all 3 healing strategies)
    workflow.add_edge("healing", "retrieval")

    workflow.add_edge("evaluation", "output")
    workflow.add_edge("output", END)

    return workflow.compile(checkpointer=checkpointer)
