# src/cmp_copilot/core/agent.py
import os
import logging
import asyncio
import json
from typing import Dict, List, Tuple
from langgraph.graph import StateGraph, END

# --- CORRECTED IMPORTS ---
from ..agents.state import AgentState
from ..agents.supervisor import supervisor_node
from ..agents.discovery import discovery_node
from ..agents.execution import execution_node
from ..agents.analysis import analysis_node
from ..tools.notification_service import send_email
from ..tools.openstack_client import OpenStackClient
from ..utils.config_loader import load_yaml_config

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Agent Nodes ---

async def notification_node(state: AgentState) -> Dict:
    # This node remains unchanged
    logging.info("--- NOTIFICATION NODE ---")
    messages_to_return: List[Tuple[str, str]] = []
    subject = state.get("draft_email_subject")
    body = state.get("draft_email_body")
    attachment_path = state.get("draft_attachment_path")
    if not all([subject, body]):
        error_msg = "Notification Error: Draft email subject or body not found in state."
        messages_to_return.append(("system", error_msg))
        return {"error_log": [error_msg], "messages": messages_to_return}
    try:
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(src_dir)
        config_path = os.path.join(project_root, 'config', 'notification_config.yaml')
        recipients = load_yaml_config(config_path).get('manager_recipients', [])
        if recipients:
            message = f"✅ Approval received. Sending notification to: {recipients}"
            messages_to_return.append(("system", message))
            send_email(recipient_emails=recipients, subject=subject, body=body, attachment_path=attachment_path)
            email_sent = True
        else:
            message = "⚠️ No recipients found in config. Skipping email."
            messages_to_return.append(("system", message))
            email_sent = False
        return {"awaiting_acknowledgment": False, "email_sent": email_sent, "messages": messages_to_return}
    except Exception as e:
        error_msg = f"Failed to send notification email. Error: {e}"
        messages_to_return.append(("system", error_msg))
        return {"error_log": [error_msg], "messages": messages_to_return}

async def cloning_node(state: AgentState) -> Dict:
    # This node remains unchanged
    logging.info("--- CLONING NODE ---")
    messages_to_return: List[Tuple[str, str]] = []
    vms_to_clone = state.get("vulnerable_vms", [])
    if not vms_to_clone:
        message = "Cloning Error: List of vulnerable VMs not found in state."
        messages_to_return.append(("system", message))
        return {"error_log": [message], "messages": messages_to_return}
    try:
        client = OpenStackClient()
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(src_dir)
        config_path = os.path.join(project_root, 'config', 'cloning_config.yaml')
        cloning_config = load_yaml_config(config_path)
        net_prefix = cloning_config.get("forensics_network_name_prefix", "forensics-net")
        network_name = f"{net_prefix}-{state.get('report_id', '')[:8]}"
        messages_to_return.append(("system", f"Creating isolated network: {network_name}..."))
        net_info = client.create_isolated_network(network_name)
        network_id = net_info['network_id']
        messages_to_return.append(("system", f"✅ Network '{network_name}' created successfully."))
        async def clone_vm(vm):
            vm_name, vm_id = vm['name'], vm['id']
            try:
                snapshot_name = f"{vm_name}-snapshot-{state.get('report_id', '')[:8]}"
                messages_to_return.append(("system", f"Creating snapshot for {vm_name}..."))
                snapshot_id = client.create_vm_snapshot(vm_id, snapshot_name)
                messages_to_return.append(("system", f"✅ Snapshot for {vm_name} created."))
                clone_name = f"{vm_name}-clone"
                messages_to_return.append(("system", f"Launching clone of {vm_name} in isolated network..."))
                client.create_vm_from_snapshot(clone_name, snapshot_id, network_id)
                messages_to_return.append(("system", f"✅ Clone of {vm_name} launched successfully."))
            except Exception as e:
                 messages_to_return.append(("system", f"❌ Failed to clone {vm_name}. Error: {e}"))
        await asyncio.gather(*[clone_vm(vm) for vm in vms_to_clone])
        final_message = "Forensic cloning process complete."
        messages_to_return.append(("system", final_message))
        return {"final_summary": final_message, "messages": messages_to_return}
    except Exception as e:
        error_msg = f"A critical error occurred during the cloning process: {e}"
        messages_to_return.append(("system", error_msg))
        return {"error_log": [error_msg], "messages": messages_to_return}

# --- FIX: New Entry Router Node ---
async def entry_router_node(state: AgentState) -> Dict:
    """
    This node is the new entry point. It performs the routing logic and
    returns a dictionary to update the state, which is valid for a node.
    """
    logging.info("--- ENTRY ROUTER ---")
    
    if state.get("awaiting_acknowledgment"):
        if "send email" in str(state.get("user_query", "")).lower():
            decision = "send_notification"
        else:
            decision = "supervisor"
    elif isinstance(state.get("user_query"), dict) and state.get("user_query", {}).get("action") == "initiate_cloning":
        decision = "start_cloning"
    else:
        decision = "supervisor"
        
    logging.info(f"Decision: {decision}")
    # Return a dictionary to update the 'next_node' field in the state
    return {"next_node": decision}

# --- FIX: New Conditional Edge Function ---
def route_from_entry(state: AgentState) -> str:
    """
    This simple function reads the decision from the state to direct the graph.
    """
    return state.get("next_node", "supervisor")

# --- Original Routing Functions (unchanged) ---
def route_after_plan(state: AgentState) -> str:
    action = state.get("plan", {}).get("action")
    return "discover" if action in ["security_scan", "list_vms"] else "end"

def route_after_discovery(state: AgentState) -> str:
    if state.get("plan", {}).get("action") == "list_vms":
        return "end"
    return "execute" if state.get("target_vms") else "analysis"

# --- Graph Definition ---
def create_agent_graph():
    """
    Creates the graph definition for the agent.
    """
    workflow = StateGraph(AgentState)

    logging.info("Defining agent graph nodes...")
    workflow.add_node("entry_router", entry_router_node) # Use the new node function
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("discovery", discovery_node)
    workflow.add_node("execution", execution_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("notification", notification_node)
    workflow.add_node("cloning", cloning_node)
    
    workflow.set_entry_point("entry_router")

    logging.info("Defining agent graph edges...")
    # --- FIX: Use the new conditional edge function ---
    workflow.add_conditional_edges(
        "entry_router",
        route_from_entry,
        {
            "supervisor": "supervisor",
            "send_notification": "notification",
            "start_cloning": "cloning",
        }
    )
    
    workflow.add_conditional_edges("supervisor", route_after_plan, {"discover": "discovery", "end": END})
    workflow.add_conditional_edges("discovery", route_after_discovery, {"execute": "execution", "analysis": "analysis", "end": END})
    workflow.add_edge("execution", "analysis")
    
    workflow.add_edge("notification", END)
    workflow.add_edge("cloning", END)

    logging.info("Agent graph definition complete.")
    return workflow