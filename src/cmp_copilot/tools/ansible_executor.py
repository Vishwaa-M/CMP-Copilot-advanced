
import os
import ansible_runner
import logging
import tempfile
import yaml
import json

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_playbook(playbook_path: str, target_host: str, ssh_user: str, ssh_pass: str) -> dict:
    """
    Runs an Ansible playbook on a single target host. The playbook is expected
    to fetch the report file to a 'reports' subdirectory relative to the playbook.
    """
    if not os.path.exists(playbook_path):
        error_msg = f"Playbook not found at path: {playbook_path}"
        logging.error(error_msg)
        return {'status': 'failed', 'error': error_msg}

    with tempfile.TemporaryDirectory() as temp_dir:
        inventory = {
            'all': {
                'hosts': {
                    target_host: {
                        'ansible_user': ssh_user,
                        'ansible_password': ssh_pass,
                        'ansible_ssh_common_args': '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null',
                        'ansible_ssh_pipelining': 'True'
                    }
                }
            }
        }
        
        inventory_path = os.path.join(temp_dir, 'inventory.yml')
        with open(inventory_path, 'w') as f:
            yaml.dump(inventory, f)

        logging.info(f"Running playbook '{playbook_path}' on host '{target_host}'")

        try:
            r = ansible_runner.run(
                private_data_dir=temp_dir,
                playbook=playbook_path,
                inventory=inventory_path,
                quiet=False
            )

            if r.status == 'successful':
                logging.info(f"Playbook run completed successfully.")
                
       
                playbook_dir = os.path.dirname(playbook_path)
                expected_report_filename = f"{target_host}_report.html"
                local_report_path = os.path.join(playbook_dir, 'reports', expected_report_filename)
                
                logging.info(f"Verifying if report was fetched to: {local_report_path}")

                if os.path.exists(local_report_path):
                    logging.info(f"SUCCESS: Verified report exists at: {local_report_path}")
                    return {
                        "status": "successful",
                        "report_path": local_report_path
                    }
                else:
                    logging.error(f"FAILURE: Playbook ran, but the expected report was NOT found at {local_report_path}")
                    return {"status": "failed", "error": "Report file not fetched by playbook."}

            else:
                logging.error(f"Playbook run failed on {target_host} with status: {r.status}")
                return {"status": "failed", "error": f"Ansible run failed with status: {r.status}"}

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {'status': 'failed', 'error': str(e)}


# --- Standalone Test Block ---
if __name__ == '__main__':
    logging.info("--- Running Ansible Executor REAL WORLD OVAL Test (Final Corrected Version) ---")

    TEST_HOST_IP = "192.168.190.181"
    TEST_SSH_USER = "root"
    TEST_SSH_PASS = "stackmax"

    try:
        # Construct the absolute path to the playbook
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        playbook_to_run = os.path.join(project_root, 'playbooks', 'security', 'openscap_scan.yml')
        
        logging.info(f"Attempting to run real playbook: {playbook_to_run}")

        if not os.path.exists(playbook_to_run):
             raise FileNotFoundError(f"Playbook not found. Please create it at: {playbook_to_run}")

        result = run_playbook(
            playbook_path=playbook_to_run,
            target_host=TEST_HOST_IP,
            ssh_user=TEST_SSH_USER,
            ssh_pass=TEST_SSH_PASS
        )
        
        print("\n--- Real World Test Run Result ---")
        print(json.dumps(result, indent=2))
        print("----------------------------------")

    except Exception as e:
        logging.error(f"An unexpected error occurred during the test: {e}", exc_info=True)
