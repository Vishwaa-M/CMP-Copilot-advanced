# utils/config_loader.py
import yaml
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_yaml_config(file_path: str) -> dict:
    """
    Loads a YAML configuration file safely.

    Args:
        file_path (str): The absolute path to the YAML file.

    Returns:
        dict: The configuration as a dictionary, or an empty dict on error.
    """
    if not os.path.exists(file_path):
        logging.error(f"Configuration file not found at: {file_path}")
        return {}
    
    try:
        with open(file_path, 'r') as f:
            # Use yaml.safe_load to prevent arbitrary code execution
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {file_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading {file_path}: {e}")
        return {}

