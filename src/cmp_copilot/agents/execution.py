# src/cmp_copilot/agents/execution.py

import logging
import asyncio
import os
from typing import Dict, List, Coroutine

# --- CORRECTED IMPORTS ---
# Use relative imports to correctly locate modules within the same package.
from .state import AgentState
from ..tools.ansible_executor import run_playbook

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def _run_scan_on_vm(vm: Dict, playbook_path: str, state: AgentState) -> Dict:
    """
    A helper coroutine to run a scan on a single VM and stream updates.
    """
    vm_name = vm.get('name', 'N/A')
    ip_address = vm.get('ip_address')
    
    if not ip_address:
        logging.warning(f"Skipping VM '{vm_name}' because it has no IP address.")
        return {"vm_name": vm_name, "status": "skipped", "error": "No IP address"}

    # Announce the start of the scan for this specific VM
    start_scan_message = f"Starting OVAL scan on {vm_name} ({ip_address})..."
    logging.info(start_scan_message)
    state['messages'].append(("system", start_scan_message))

    # In a real-world scenario, you would fetch credentials securely.
    # For this project, we'll use placeholder credentials from the successful test.
    ssh_user = "root"
    ssh_pass = "stackmax"

    # Because run_playbook is a standard synchronous function, we need to run it
    # in a separate thread to avoid blocking the asyncio event loop.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,  # Use the default thread pool executor
        run_playbook,
        playbook_path,
        ip_address,
        ssh_user,
        ssh_pass
    )
    
    result['vm_name'] = vm_name
    
    end_scan_message = f"Scan completed for {vm_name}. Status: {result.get('status')}."
    logging.info(end_scan_message)
    state['messages'].append(("system", end_scan_message))
    
    return result


async def execution_node(state: AgentState) -> Dict:
    """
    This agent node takes the list of target VMs and runs the specified
    Ansible playbook on each one in parallel.
    """
    logging.info("--- EXECUTION NODE ---")
    
    all_vms = state.get('target_vms', [])
    playbook_name = state.get('plan', {}).get('playbook')

    # --- ADDED FILTERING LOGIC ---
    # Filter the list to only include VMs whose names start with 'kafka' (case-insensitive).
    logging.info(f"Received {len(all_vms)} VMs. Filtering for names starting with 'kafka'...")
    target_vms = [
        vm for vm in all_vms 
        if vm.get('name', '').lower().startswith('kafka')
    ]
    logging.info(f"Found {len(target_vms)} VMs matching the 'kafka' filter.")
    # --- END OF FILTERING LOGIC ---

    if not target_vms:
        logging.warning("Execution: No target VMs found after applying the filter. Skipping execution.")
        state['messages'].append(("system", "No 'kafka' VMs found to scan. Skipping execution step."))
        return {}

    if not playbook_name:
        logging.error("Execution: No playbook specified in the plan.")
        state['messages'].append(("system", "Error: No playbook specified in the plan."))
        return {"error_log": ["Execution: No playbook specified."]}

    # --- FINAL CORRECTED PATH LOGIC ---
    # This robustly calculates the path to the playbook based on your specified structure.
    try:
        # Go up three directories (from agents/ -> cmp_copilot/ -> src/)
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        playbook_path = os.path.join(src_dir, 'playbooks', 'security', playbook_name)
        
        logging.info(f"Attempting to locate playbook at: {playbook_path}")
        if not os.path.exists(playbook_path):
             raise FileNotFoundError(f"Playbook not found at calculated path: {playbook_path}")
    except Exception as e:
        error_message = f"Execution: Could not find playbook '{playbook_name}'. Error: {e}"
        logging.error(error_message, exc_info=True)
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}

    initial_message = f"Beginning security scans on {len(target_vms)} VMs. This may take some time..."
    logging.info(initial_message)
    state['messages'].append(("system", initial_message))

    # Create a list of concurrent tasks
    tasks: List[Coroutine] = [_run_scan_on_vm(vm, playbook_path, state) for vm in target_vms]
    
    # Run all scan tasks in parallel
    scan_outcomes = await asyncio.gather(*tasks)
    
    # Process the results
    successful_reports = [
        res for res in scan_outcomes if res.get('status') == 'successful' and res.get('report_path')
    ]
    errors = [
        f"Scan failed on {res['vm_name']}: {res.get('error', 'Unknown error')}" 
        for res in scan_outcomes if res.get('status') != 'successful'
    ]

    final_message = f"All scans complete. Successful reports: {len(successful_reports)}. Failures: {len(errors)}."
    logging.info(final_message)
    state['messages'].append(("system", final_message))

    return {
        "scan_results": successful_reports,
        "error_log": errors
    }