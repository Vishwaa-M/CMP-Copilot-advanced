import os
from dotenv import load_dotenv
import openstack
import openstack.connection
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
logging.info("Loaded environment variables from .env file.")


class OpenStackClient:
    """
    A dedicated client for interacting with the OpenStack cloud.
    This version uses an explicit connection method.
    """

    def __init__(self):
        """
        Initializes the OpenStack client by explicitly building the connection object.
        """
        self.conn = None
        try:
            logging.info("Attempting to connect to OpenStack using credentials from .env file...")

            # --- Explicitly gather all required credentials from the environment ---
            auth_url = os.getenv('OS_AUTH_URL')
            username = os.getenv('OS_USERNAME')
            password = os.getenv('OS_PASSWORD')
            project_id = os.getenv('OS_PROJECT_ID')
            user_domain_name = os.getenv('OS_USER_DOMAIN_NAME')
            
            # --- CRITICAL FIX: Handle potentially missing OS_PROJECT_DOMAIN_NAME ---
            # If OS_PROJECT_DOMAIN_NAME is not in the .env, default it to OS_USER_DOMAIN_NAME.
            project_domain_name = os.getenv('OS_PROJECT_DOMAIN_NAME', user_domain_name)

            # --- Log the credentials being used (except password) for debugging ---
            logging.info(f"Auth URL: {auth_url}")
            logging.info(f"Username: {username}")
            logging.info(f"Project ID: {project_id}")
            logging.info(f"User Domain Name: {user_domain_name}")
            logging.info(f"Project Domain Name (Resolved): {project_domain_name}")

            if not all([auth_url, username, password, project_id, user_domain_name]):
                raise ConnectionError("One or more required OpenStack variables are missing from your .env file.")

            # --- Manually create the connection object using Project ID for reliability ---
            self.conn = openstack.connection.Connection(
                auth_url=auth_url,
                project_id=project_id,
                username=username,
                password=password,
                user_domain_name=user_domain_name,
                project_domain_name=project_domain_name,
            )
            
            # Verify the connection by checking the token
            self.conn.authorize()
            
            logging.info("Successfully connected and authenticated with OpenStack.")

        except Exception as e:
            error_message = (
                "Failed to connect to OpenStack. "
                "Please double-check all variables in your .env file. "
                f"Error: {e}"
            )
            logging.error(error_message, exc_info=True)
            raise ConnectionError(error_message) from e

    def list_vms(self, **filters) -> list[dict]:
        """
        Retrieves a list of virtual machines from the OpenStack cloud.
        """
        if not self.conn:
            logging.error("Connection not established. Cannot list VMs.")
            return []

        logging.info(f"Fetching list of VMs from OpenStack with filters: {filters}")
        try:
            servers = self.conn.compute.servers(details=True, **filters)
            
            vm_list = []
            for server in servers:
                ip_address = ""
                if server.addresses:
                    for network_name, addresses in server.addresses.items():
                        if addresses:
                            ip_address = addresses[0].get('addr')
                            break

                vm_list.append({
                    "id": server.id,
                    "name": server.name,
                    "ip_address": ip_address,
                    "status": server.status,
                })
            
            logging.info(f"Found {len(vm_list)} VMs.")
            return vm_list

        except openstack.exceptions.SDKException as e:
            logging.error(f"An error occurred while fetching VMs: {e}")
            return []

# --- Standalone Test Block ---
if __name__ == '__main__':
    logging.info("--- Running OpenStack Client Standalone Test (using .env file) ---")
    try:
        client = OpenStackClient()
        if client.conn:
            virtual_machines = client.list_vms()
            if virtual_machines:
                print("\n--- Discovered Virtual Machines ---")
                for i, vm in enumerate(virtual_machines):
                    print(f"{i+1}. Name: {vm['name']}, IP: {vm['ip_address']}, Status: {vm['status']}")
                print("-----------------------------------")
            else:
                logging.warning("Connection successful, but no virtual machines were found.")

    except ConnectionError as e:
        logging.error(f"\nTest failed. Please check your .env file and logs.")
    except Exception as e:
        logging.error(f"\nAn unexpected error occurred during the test: {e}", exc_info=True)
