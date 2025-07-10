import os
from dotenv import load_dotenv
import openstack
import openstack.connection
import logging
import time

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
logging.info("Loaded environment variables from .env file.")


class OpenStackClient:
    """
    A dedicated client for interacting with the OpenStack cloud.
    This version includes methods for VM snapshotting and creation.
    """

    def __init__(self):
        """
        Initializes the OpenStack client by explicitly building the connection object.
        """
        self.conn = None
        try:
            logging.info("Attempting to connect to OpenStack using credentials from .env file...")
            auth_url = os.getenv('OS_AUTH_URL')
            username = os.getenv('OS_USERNAME')
            password = os.getenv('OS_PASSWORD')
            project_id = os.getenv('OS_PROJECT_ID')
            user_domain_name = os.getenv('OS_USER_DOMAIN_NAME')
            project_domain_name = os.getenv('OS_PROJECT_DOMAIN_NAME', user_domain_name)

            logging.info(f"Auth URL: {auth_url}")
            logging.info(f"Username: {username}")
            logging.info(f"Project ID: {project_id}")
            logging.info(f"User Domain Name: {user_domain_name}")
            logging.info(f"Project Domain Name (Resolved): {project_domain_name}")

            if not all([auth_url, username, password, project_id, user_domain_name]):
                raise ConnectionError("One or more required OpenStack variables are missing from your .env file.")

            self.conn = openstack.connection.Connection(
                auth_url=auth_url,
                project_id=project_id,
                username=username,
                password=password,
                user_domain_name=user_domain_name,
                project_domain_name=project_domain_name,
            )
            self.conn.authorize()
            logging.info("Successfully connected and authenticated with OpenStack.")

        except Exception as e:
            error_message = (
                "Failed to connect to OpenStack. Please double-check all variables in your .env file. "
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
                    for addresses in server.addresses.values():
                        if addresses:
                            ip_address = addresses[0].get('addr')
                            break
                vm_list.append({
                    "id": server.id, "name": server.name,
                    "ip_address": ip_address, "status": server.status,
                })
            logging.info(f"Found {len(vm_list)} VMs.")
            return vm_list
        except openstack.exceptions.SDKException as e:
            logging.error(f"An error occurred while fetching VMs: {e}")
            return []

    # --- NEW METHOD ---
    def create_vm_snapshot(self, vm_id: str, snapshot_name: str) -> str:
        """
        Creates a snapshot of a given VM.
        Returns the ID of the new snapshot.
        """
        logging.info(f"Creating snapshot '{snapshot_name}' for VM ID: {vm_id}...")
        try:
            server = self.conn.compute.get_server(vm_id)
            if not server:
                raise ValueError(f"VM with ID {vm_id} not found.")
            
            # This call starts the snapshot process and returns an image object immediately.
            image = self.conn.compute.create_server_image(server, snapshot_name)
            
            # We must wait for the image status to become 'active'.
            self.conn.image.wait_for_status(image, status='active', failures=['error'], interval=5, wait=300)
            
            logging.info(f"Successfully created snapshot. Image ID: {image.id}")
            return image.id
        except Exception as e:
            logging.error(f"Failed to create snapshot for VM {vm_id}: {e}", exc_info=True)
            raise

    # --- NEW METHOD ---
    def create_isolated_network(self, network_name: str) -> dict:
        """
        Creates a new network and a subnet for the forensic environment.
        Returns a dictionary with the new network and subnet IDs.
        """
        logging.info(f"Creating isolated network '{network_name}'...")
        try:
            # Check if network already exists to avoid errors
            existing_network = self.conn.network.find_network(network_name, ignore_missing=True)
            if existing_network:
                logging.warning(f"Network '{network_name}' already exists. Reusing it.")
                subnet = next(self.conn.network.subnets(network_id=existing_network.id), None)
                if not subnet:
                    raise ValueError(f"Network '{network_name}' exists but has no subnet.")
                return {'network_id': existing_network.id, 'subnet_id': subnet.id}

            # Create the new network
            network = self.conn.network.create_network(name=network_name)

            # Create a subnet for the network
            subnet_name = f"{network_name}-subnet"
            subnet = self.conn.network.create_subnet(
                name=subnet_name,
                network_id=network.id,
                ip_version=4,
                cidr="192.168.250.0/24", # Using a distinct CIDR for the isolated network
                enable_dhcp=True
            )
            logging.info(f"Successfully created network '{network.name}' and subnet '{subnet.name}'.")
            return {'network_id': network.id, 'subnet_id': subnet.id}
        except Exception as e:
            logging.error(f"Failed to create isolated network '{network_name}': {e}", exc_info=True)
            raise

    # --- NEW METHOD ---
    def create_vm_from_snapshot(self, vm_name: str, snapshot_id: str, network_id: str) -> str:
        """
        Launches a new VM from a snapshot into a specified network.
        Returns the ID of the new VM.
        """
        logging.info(f"Creating VM '{vm_name}' from snapshot ID: {snapshot_id}...")
        try:
            # Find a suitable flavor for the new VM (e.g., 'm1.small' or the smallest available)
            flavor = self.conn.compute.find_flavor("m1.small", ignore_missing=True)
            if not flavor:
                # Fallback to getting the first flavor in the list if m1.small isn't found
                flavors = list(self.conn.compute.flavors())
                if not flavors:
                    raise ValueError("No flavors found in this OpenStack project.")
                flavor = flavors[0]
            logging.info(f"Using flavor '{flavor.name}' for the new VM.")
            
            # Create the server
            server = self.conn.compute.create_server(
                name=vm_name,
                image_id=snapshot_id,
                flavor_id=flavor.id,
                networks=[{"uuid": network_id}]
            )
            
            # Wait for the server to become active
            self.conn.compute.wait_for_server(server, status='ACTIVE', failures=['ERROR'], interval=5, wait=600)
            
            new_vm = self.conn.compute.get_server(server.id)
            logging.info(f"Successfully created VM '{new_vm.name}' with ID: {new_vm.id}")
            return new_vm.id
        except Exception as e:
            logging.error(f"Failed to create VM from snapshot {snapshot_id}: {e}", exc_info=True)
            raise

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

    except ConnectionError:
        logging.error("\nTest failed. Please check your .env file and logs.")
    except Exception as e:
        logging.error(f"\nAn unexpected error occurred during the test: {e}", exc_info=True)