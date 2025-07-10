# src/cmp_copilot/agents/discovery.py
import logging
import asyncio
from typing import Dict
import sys
import os
import json

# This allows the script to find the other modules when run directly
try:
    src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, src_path)
    from src.cmp_copilot.agents.state import AgentState
    from src.cmp_copilot.tools.openstack_client import OpenStackClient
except (ImportError, ModuleNotFoundError):
    # This is to allow the file to be imported by other modules without path issues
    from src.cmp_copilot.agents.state import AgentState
    from src.cmp_copilot.tools.openstack_client import OpenStackClient


# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def discovery_node(state: AgentState) -> Dict:
    """
    This agent node connects to the cloud provider and discovers the target
    virtual machines based on the plan from the supervisor.

    Args:
        state (AgentState): The current state of the agent's memory.

    Returns:
        Dict: A dictionary containing the updates to be made to the state.
              Specifically, it returns the 'target_vms' list.
    """
    logging.info("--- DISCOVERY NODE ---")
    
    plan = state.get('plan', {})
    if not plan:
        error_message = "Discovery: No plan found in state. Cannot proceed."
        logging.error(error_message)
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}

    filters = plan.get('filters', {})
    
    # Announce the action for the streaming UI
    if filters:
        initial_message = f"Searching for VMs with the following filters: {json.dumps(filters)}..."
    else:
        initial_message = "Searching for all VMs..."
    state['messages'].append(("system", initial_message))

    try:
        # Initialize our OpenStack tool
        client = OpenStackClient()
        
        # Call the tool to list the VMs with the specified filters
        vms = client.list_vms(**filters)
        
        if not vms:
            result_message = "No VMs found matching the criteria."
            logging.warning(result_message)
            state['messages'].append(("system", result_message))
            return {"target_vms": []}
        
        # We only want to run scans on ACTIVE VMs.
        active_vms = [vm for vm in vms if vm.get('status') == 'ACTIVE']
        
        if not active_vms:
            result_message = f"Found {len(vms)} VMs, but none are currently ACTIVE. No action will be taken."
            logging.warning(result_message)
            state['messages'].append(("system", result_message))
            return {"target_vms": []}

        result_message = f"Discovery complete. Found {len(active_vms)} ACTIVE VMs to target."
        logging.info(result_message)
        state['messages'].append(("system", result_message))
        
        # Return the list of active VMs to be updated in the state
        return {"target_vms": active_vms}

    except ConnectionError as e:
        # This catches connection errors from the OpenStackClient
        error_message = f"Discovery: Failed to connect to OpenStack. Please check credentials. Error: {e}"
        logging.error(error_message)
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}
        
    except Exception as e:
        error_message = f"Discovery: An unexpected error occurred: {e}"
        logging.error(error_message, exc_info=True)
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}


# --- Standalone Test Block ---
if __name__ == '__main__':
    
    async def test_discovery():
        print("--- Testing Discovery Node ---")
        
        # 1. Create a mock state object with a plan from the supervisor
        mock_state = AgentState(
            user_query="Scan all VMs.",
            plan={
                "action": "security_scan",
                "playbook": "openscap_scan.yml",
                "filters": {} # No filters for this test
            },
            target_vms=[],
            scan_results=[],
            error_log=[],
            final_summary="",
            email_sent=False,
            messages=[]
        )
        
        # 2. Run the discovery node with the mock state
        result = await discovery_node(mock_state)
        
        # 3. Print the results
        print("\n--- Result from Discovery Node ---")
        print(json.dumps(result, indent=2))
        
        print("\n--- Final State of Messages ---")
        for role, content in mock_state['messages']:
            print(f"[{role.upper()}]: {content}")

    # Run the async test function
    asyncio.run(test_discovery())
