"""
Config Loader - Loads and validates configuration for OpenClaw Guardian

This module handles reading configuration from config.yaml and environment variables.
Think of it as the "settings manager" for our application.

Beginner Python Notes:
- import: brings in external code (libraries) to use in our file
- class: a blueprint for creating objects; groups related functions and variables together
- self: refers to the instance of the class; allows accessing variables inside the class
- def: defines a function (a reusable block of code)
- _: functions starting with _ are "private" - meant to be used inside the class only
- Dict[str, Any]: type hints - tells us this is a dictionary with string keys and any values
- None: a special value meaning "nothing" or "empty"
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in Python library for interacting with the operating system
# We use it to read environment variables (like system secrets)

import yaml
# yaml: Third-party library for reading .yaml files (configuration files)
# yaml.safe_load() converts YAML text into a Python dictionary

import re
# re: Built-in Python library for working with regular expressions
# Regular expressions (regex) are patterns used to match text

from pathlib import Path
# pathlib: Built-in Python library for file path operations
# Path is a cleaner way to work with file paths instead of raw strings

from dotenv import load_dotenv
# dotenv: Third-party library for loading .env files
# load_dotenv() reads .env file and sets environment variables

from typing import Any, Dict, Optional
# typing: Built-in Python library for type hints
# - Any: any type of value
# - Dict: dictionary type (key-value pairs)
# - Optional: value can be either the specified type or None


# ============================================================================
# CONFIGLOADER CLASS - The main configuration handler
# ============================================================================

class ConfigLoader:
    """
    A class that loads and validates configuration settings.
    
    Think of this like a form that:
    1. Reads the config file (config.yaml)
    2. Fills in any missing info from environment variables
    3. Checks that all required fields are filled in
    4. Returns the complete configuration
    
    Attributes:
        REQUIRED_FIELDS: A dictionary listing all required configuration sections and fields
        config_path: Path to the configuration file
        config: The loaded configuration dictionary (starts as None)
    """
    
    # This is a "class variable" - it's shared by all instances of this class
    # It's like a constant that doesn't change
    # This defines WHAT we need in our config file
    REQUIRED_FIELDS = {
        'github': ['token', 'repo_url'],      # GitHub settings we need
        'agent': ['check_interval', 'branch_prefix'],  # Agent behavior settings
        'paths': ['working_directory', 'memory_file']  # File path settings
    }

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Constructor - called when we create a new ConfigLoader object.
        
        Args:
            config_path: Path to the config file (defaults to 'config.yaml')
        
        Example:
            loader = ConfigLoader()  # Uses default 'config.yaml'
            loader = ConfigLoader('my_config.yaml')  # Uses custom file
        """
        self.config_path = config_path  # Store the path for later use
        self.config: Optional[Dict[str, Any]] = None  # Will hold our config (initially None)

    def load(self) -> Dict[str, Any]:
        """
        Main function that loads and returns the configuration.
        
        This is the "main door" - other code calls this to get the config.
        It does several steps in order:
        
        Returns:
            Dict[str, Any]: The complete configuration as a dictionary
        
        Steps:
            1. Check if config file exists
            2. Read the YAML file
            3. Load environment variables
            4. Replace ${VAR} placeholders with actual values
            5. Validate all required fields exist
        """
        # Create a Path object (cleaner file handling)
        config_file = Path(self.config_path)
        
        # Check if file exists
        # if not: is Python's way of saying "if this is False"
        if not config_file.exists():
            # raise: stops the program and shows an error message
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        # Open and read the file
        # with: ensures the file is properly closed after reading
        # 'r' means open for reading (not writing)
        with open(config_file, 'r') as f:
            # yaml.safe_load() converts YAML format to Python dictionary
            # YAML is just a text format for storing data (like JSON)
            self.config = yaml.safe_load(f)
        
        # Handle case where config file is empty
        # If yaml.safe_load() returns None (empty file), make it an empty dictionary
        if self.config is None:
            self.config = {}
        
        # Call private methods to process the config
        self._load_env_variables()       # Step 3: Load env vars
        self._substitute_env_vars()       # Step 4: Replace ${VAR} with actual values
        self._validate_required_fields()  # Step 5: Check all required fields exist
        
        # Return the complete configuration
        return self.config

    def _load_env_variables(self):
        """
        Sets default values for environment variables if they don't exist.
        
        Environment variables are system-level settings that can store
        sensitive information like API tokens.
        
        os.environ: A dictionary that holds all environment variables
        setdefault(key, default): Sets value only if key doesn't exist
        
        Example:
            If GITHUB_TOKEN is not set, it becomes empty string ''
        """
        # First, try to load from .env file if it exists
        # This allows users to store secrets in .env instead of system env vars
        env_path = Path('.env')
        if env_path.exists():
            load_dotenv(env_path)
        
        # Set default values if environment variables are not set
        os.environ.setdefault('GITHUB_TOKEN', '')
        os.environ.setdefault('MOLTBOOK_API_KEY', '')
        os.environ.setdefault('REPO_URL', '')
        os.environ.setdefault('CHECK_INTERVAL', '3600')

    def _substitute_env_vars(self):
        """
        Replaces ${VAR_NAME} placeholders in config with actual environment values.
        
        This allows us to write in config.yaml:
            token: ${GITHUB_TOKEN}
        
        And it gets replaced with the actual token from environment.
        
        Also fills in defaults from environment if values are missing in config.yaml.
        
        How it works:
            1. Convert config dict back to string (YAML format)
            2. Find patterns like ${GITHUB_TOKEN}
            3. Replace each with the actual environment variable value
            4. Convert back to dictionary
        """
        # Convert dictionary to YAML string so we can do text replacement
        config_str = yaml.dump(self.config)
        
        # Define a regex pattern to find ${VARIABLE_NAME}
        # - ${...} matches the dollar sign and curly braces
        # - (...) creates a "group" to capture what's inside
        # - [^}]+ means "one or more characters that are NOT }"
        pattern = r'\$\{([^}]+)\}'
        
        # Define a function to replace each match
        # This is called for every match found by re.sub()
        def replace_env_var(match):
            # match.group(1) gets the first captured group (the variable name)
            # e.g., if we matched ${GITHUB_TOKEN}, group(1) is 'GITHUB_TOKEN'
            var_name = match.group(1)
            # os.environ.get() retrieves the value, or '' if not found
            return os.environ.get(var_name, '')
        
        # re.sub() finds all matches of the pattern and replaces them
        # It calls replace_env_var for each match
        modified_str = re.sub(pattern, replace_env_var, config_str)
        
        # Convert the modified string back to a Python dictionary
        self.config = yaml.safe_load(modified_str)
        
        # Safety check - ensure config is a dictionary
        if self.config is None:
            self.config = {}
        
        # If repo_url is still empty in config, try to get it from REPO_URL env var
        # dict() creates a copy so we don't modify the original
        github_config = dict(self.config.get('github', {}))
        if not github_config.get('repo_url'):
            # If no repo_url in config, use environment variable
            github_config['repo_url'] = os.environ.get('REPO_URL', '')
            self.config['github'] = github_config
        
        # Similar for check_interval - default to 3600 seconds (1 hour)
        agent_config = dict(self.config.get('agent', {}))
        if not agent_config.get('check_interval'):
            # Convert to int because environment variables are always strings
            # int('3600') becomes the number 3600
            agent_config['check_interval'] = int(os.environ.get('CHECK_INTERVAL', '3600'))
            self.config['agent'] = agent_config

    def _validate_required_fields(self):
        """
        Checks that all required configuration fields are present.
        
        This prevents the program from running with incomplete configuration,
        which would cause errors later.
        
        If any required field is missing, it raises an error with a list
        of all missing fields.
        """
        # If config is somehow None, it's definitely invalid
        if self.config is None:
            raise ValueError("Configuration is empty")
        
        # List to collect all missing fields
        missing_fields = []
        
        # Loop through each section (github, moltbook, agent, paths)
        # .items() gives us both the key and value for each dictionary entry
        for section, fields in self.REQUIRED_FIELDS.items():
            # Get the section from config, or empty dict if not present
            # .get() returns None if key doesn't exist, so we use 'or {}' as fallback
            section_data = self.config.get(section) or {}
            
            # Check if section exists and has data
            if section not in self.config or not section_data:
                missing_fields.append(f"Missing section: {section}")
                continue  # Skip to next section
            
            # Check each required field in this section
            for field in fields:
                # Get the field value
                value = section_data.get(field)
                # Check if it's None or empty string
                if value is None or value == '':
                    missing_fields.append(f"Missing field: {section}.{field}")
        
        # If we found any missing fields, raise an error
        # '\n'.join() combines all missing fields into one string, separated by newlines
        if missing_fields:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(missing_fields))
        
        # If all required fields exist, also check the types are correct
        self._validate_types()

    def _validate_types(self):
        """
        Validates that each configuration field has the correct data type.
        
        For example:
        - check_interval should be a number (int)
        - branch_prefix should be text (str)
        
        This prevents subtle bugs where wrong types cause unexpected behavior.
        """
        # Get agent and paths sections (or empty dict if missing)
        # Using dict() to ensure we get a proper dictionary, not None
        agent_data = self.config.get('agent')
        agent = dict(agent_data) if agent_data else {}
        
        paths_data = self.config.get('paths')
        paths = dict(paths_data) if paths_data else {}
        
        # isinstance() checks if a value is of a specific type
        # isinstance(5, int) returns True, isinstance("hi", int) returns False
        
        # Check check_interval is an integer
        if not isinstance(agent.get('check_interval'), int):
            raise TypeError("agent.check_interval must be an integer")
        
        # Check branch_prefix is a string
        if not isinstance(agent.get('branch_prefix'), str):
            raise TypeError("agent.branch_prefix must be a string")
        
        # Check working_directory is a string
        if not isinstance(paths.get('working_directory'), str):
            raise TypeError("paths.working_directory must be a string")
        
        # Check memory_file is a string
        if not isinstance(paths.get('memory_file'), str):
            raise TypeError("paths.memory_file must be a string")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a configuration value using dot notation.
        
        This provides an easy way to access nested config values.
        
        Args:
            key: A dot-separated key like 'github.repo_url'
                 This would get config['github']['repo_url']
            default: Value to return if key is not found (defaults to None)
        
        Returns:
            The configuration value, or default if not found
        
        Example:
            loader.get('github.token') returns the GitHub token
            loader.get('nonexistent', 'default') returns 'default'
        """
        # Split the key by dots: 'github.repo_url' becomes ['github', 'repo_url']
        keys = key.split('.')
        
        # Start with the whole config dictionary
        value: Any = self.config
        
        # Loop through each key level
        for k in keys:
            # Only try to access dictionary keys if value is a dictionary
            if isinstance(value, dict):
                value = value.get(k)  # Get the next level
            else:
                # If we hit something that's not a dict, the key path is invalid
                return default
            
            # If we reached a None value, stop here and return default
            if value is None:
                return default
        
        # Return the final value we found
        return value


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to load config from anywhere
# ============================================================================

def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """
    Simple function to load configuration.
    
    This is a "wrapper" function that makes it easy to load config
    without creating a ConfigLoader object yourself.
    
    Args:
        config_path: Path to the configuration file
    
    Returns:
        The complete configuration dictionary
    
    Example:
        config = load_config()  # Loads from 'config.yaml'
        token = config['github']['token']
    """
    # Create a new ConfigLoader object
    loader = ConfigLoader(config_path)
    # Call its load() method and return the result
    return loader.load()


# ============================================================================
# MAIN - Code that runs when we execute this file directly
# ============================================================================

if __name__ == "__main__":
    """
    This block only runs when we execute: python config_loader.py
    
    It won't run when we import this file from another module.
    This is useful for testing the config loader.
    """
    try:
        # Try to load the configuration
        config = load_config()
        
        # If successful, print confirmation
        print("Configuration loaded successfully!")
        print(f"Repository: {config['github']['repo_url']}")
        print(f"Check Interval: {config['agent']['check_interval']} seconds")
        
    except Exception as e:
        # If anything goes wrong, print the error message
        # Exception is the base class for all errors
        print(f"Error: {e}")
