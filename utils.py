# utils.py

import os
import tomllib
from dotenv import load_dotenv
from typing import Dict, Any

def load_env() -> Dict[str, str]:
    """
    Loads environment variables from a .env file and verifies required credentials.
    Returns a dictionary of validated credentials.
    """
    load_dotenv()
    
    # Define required environment variables
    REQUIRED_VARS = ["RAMP_CLIENT_ID", "RAMP_CLIENT_SECRET"]
    
    env_vars = {}
    for var_name in REQUIRED_VARS:
        value = os.getenv(var_name, "").strip()
        if not value:
            raise ValueError(f"Environment variable '{var_name}' must be set in the .env file.")
        env_vars[var_name] = value
        
    return env_vars

def load_config(config_path: str = 'config.toml') -> Dict[str, Any]:
    """
    Loads configuration settings from a TOML file.
    """
    try:
        with open(config_path, 'r') as f:
            config = tomllib.loads(f.read())
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    except Exception as e:
        raise IOError(f"Error loading configuration file: {e}")