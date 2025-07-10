# src/cmp_copilot/agents/state.py

from typing import TypedDict, List, Dict, Annotated, Tuple, Optional
import operator

def add_messages(left: List, right: List) -> List:
    """Helper function to append messages for LangGraph state."""
    return left + right

class AgentState(TypedDict):
    """
    Defines the structure of the agent's memory or "state".

    This TypedDict is passed between all the nodes in the LangGraph. Each node
    can read from it and write to it, allowing the agent to build up information
    and context as it executes a task.
    """
    
    # === Core Workflow State ===
    user_query: str
    plan: Dict
    target_vms: List[Dict]
    scan_results: Annotated[list, operator.add]
    error_log: Annotated[list, operator.add]
    final_summary: str
    email_sent: bool
    messages: Annotated[List[Tuple[str, str]], add_messages]

    # === NEW: Routing State ===
    # This field will hold the decision made by the entry router node.
    next_node: Optional[str]

    # === Human-in-the-Loop (HITL) & Persistence State ===
    # These fields manage the multi-day workflow where the agent waits for
    # an external acknowledgment before proceeding with further actions.

    # A unique ID for the entire scan-to-remediation session, used in the
    # acknowledgment link and for retrieving the state from the database.
    report_id: Optional[str]

    # The specific list of VM objects that were found to have vulnerabilities.
    # This list is saved by the checkpointer for the cloning workflow.
    vulnerable_vms: Optional[List[Dict]]

    # A flag to indicate that the agent has sent its initial report and is
    # now paused, waiting for the acknowledgment signal.
    awaiting_acknowledgment: Optional[bool]

    # The drafted subject of the notification email, held in state.
    draft_email_subject: Optional[str]

    # The drafted body of the notification email, held in state.
    draft_email_body: Optional[str]

    # The file path of the drafted CSV attachment, held in state.
    draft_attachment_path: Optional[str]