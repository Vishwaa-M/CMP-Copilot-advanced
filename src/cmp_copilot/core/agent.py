# src/cmp_copilot/core/agent.py

import logging
import asyncio
from langgraph.graph import StateGraph, END

# --- CORRECTED IMPORTS ---
# Use relative imports to find modules within the same package.
from ..agents.state import AgentState
from ..agents.supervisor import supervisor_node
from ..agents.discovery import discovery_node
from ..agents.execution import execution_node
from ..agents.analysis import analysis_node

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Conditional Logic for Routing ---

def route_after_plan(state: AgentState) -> str:
    """
    Determines the next step based on the plan created by the supervisor.
    """
    logging.info("--- ROUTING: After Supervisor ---")
    plan = state.get("plan", {})
    action = plan.get("action")
    
    if action in ["security_scan", "list_vms"]:
        logging.info(f"Decision: Plan action is '{action}'. Proceeding to discovery.")
        return "discover"
    else:
        logging.info(f"Decision: Invalid or missing action '{action}'. Ending workflow.")
        return "end"

def route_after_discovery(state: AgentState) -> str:
    """
    Determines the next step after the discovery node has run.
    """
    logging.info("--- ROUTING: After Discovery ---")
    plan = state.get("plan", {})
    action = plan.get("action")
    target_vms = state.get("target_vms", [])

    if action == "list_vms":
        logging.info("Decision: 'list_vms' action is complete. Ending workflow.")
        return "end"
    
    if target_vms:
        logging.info(f"Decision: Found {len(target_vms)} VMs to scan. Proceeding to execution.")
        return "execute"
    else:
        logging.info("Decision: No active VMs found to scan. Proceeding to analysis to report this.")
        return "analyze"


# --- Graph Definition ---

def create_agent_graph():
    """
    Creates and compiles the LangGraph agent.
    """
    workflow = StateGraph(AgentState)

    # Add each agent function as a node in the graph
    logging.info("Defining agent graph nodes...")
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("discovery", discovery_node)
    workflow.add_node("execution", execution_node)
    workflow.add_node("analysis", analysis_node)

    # Set the entry point of the graph
    workflow.set_entry_point("supervisor")

    # Define the routing logic (edges) between the nodes
    logging.info("Defining agent graph edges...")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_plan,
        {
            "discover": "discovery",
            "end": END
        }
    )
    workflow.add_conditional_edges(
        "discovery",
        route_after_discovery,
        {
            "execute": "execution",
            "analyze": "analysis",
            "end": END
        }
    )
    workflow.add_edge("execution", "analysis")
    workflow.add_edge("analysis", END)

    # Compile the graph into a runnable application
    logging.info("Compiling agent graph...")
    app = workflow.compile()
    logging.info("Agent graph compiled successfully.")
    return app

