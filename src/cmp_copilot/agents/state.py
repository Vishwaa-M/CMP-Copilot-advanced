
from typing import TypedDict, List, Dict, Annotated, Tuple, Optional
import operator

def add_messages(left: List, right: List) -> List:
    """Helper function to append messages for LangGraph state."""
    return left + right

class AgentState(TypedDict):
    
    # === Core Workflow State ===
    user_query: str
    plan: Dict
    target_vms: List[Dict]
    scan_results: Annotated[list, operator.add]
    error_log: Annotated[list, operator.add]
    final_summary: str
    email_sent: bool
    messages: Annotated[List[Tuple[str, str]], add_messages]

    next_node: Optional[str]

    report_id: Optional[str]

    vulnerable_vms: Optional[List[Dict]]

    awaiting_acknowledgment: Optional[bool]

    draft_email_subject: Optional[str]

    draft_email_body: Optional[str]

    draft_attachment_path: Optional[str]
