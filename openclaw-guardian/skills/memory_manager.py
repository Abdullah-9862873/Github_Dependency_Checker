"""
Memory Manager - Handles persistent memory for OpenClaw Guardian

This module stores what the agent has done so it doesn't repeat work.
It saves information to memory.json and reads it back when needed.

Think of this as the agent's "memory" - it remembers:
- When it last checked for updates
- Which packages were already upgraded
- How many successful upgrades it's made
- Links to created PRs

Beginner Python Notes:
- json: Built-in library for reading/writing JSON files
- datetime: Built-in library for dates and times
- pathlib: For file path operations
- Optional: Type hint meaning value can be None
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import json
# json: Built-in Python library for working with JSON data
# JSON is a text format for storing data (like dictionaries)
# json.load() reads JSON from a file
# json.dump() writes JSON to a file

import os
# os: Built-in Python library for file operations
# os.path.exists() checks if a file exists
# os.makedirs() creates directories

from datetime import datetime, timezone
# datetime: Built-in library for dates and times
# datetime.now() gets current time
# timezone: For working with timezones (UTC)
# timezone.utc is the UTC timezone

from pathlib import Path
# pathlib: Built-in library for file paths

from typing import Any, Dict, List, Optional
# typing: Library for type hints
# Any: Any type of value
# Dict: Dictionary type
# List: List type
# Optional: Can be None


# ============================================================================
# MEMORY MANAGER CLASS - Handles persistent memory
# ============================================================================

class MemoryManager:
    """
    A class that manages the agent's persistent memory.
    
    The memory stores:
    - repo_url: Which repository we're monitoring
    - last_checked: When we last checked for updates
    - last_updated: List of all upgrades performed
    - total_runs: How many times the agent has run
    - successful_upgrades: How many successful upgrades
    
    This prevents the agent from upgrading the same package repeatedly.
    
    Example memory.json structure:
    {
        "repo_url": "https://github.com/user/project",
        "last_checked": "2024-01-15T10:30:00Z",
        "last_updated": [
            {
                "branch": "auto/dependency-update-1705312200",
                "packages": ["lodash", "axios"],
                "timestamp": "2024-01-15T10:35:00Z",
                "pr_url": "https://github.com/user/project/pull/5"
            }
        ],
        "total_runs": 15,
        "successful_upgrades": 8
    }
    """
    
    def __init__(self, memory_file: str = 'memory.json', logger=None):
        """
        Initialize the MemoryManager.
        
        Args:
            memory_file: Path to the memory JSON file (defaults to 'memory.json')
            logger: Optional logger for logging messages
        
        Example:
            manager = MemoryManager('memory.json')
        """
        self.memory_file = memory_file
        self.logger = logger
        self.memory: Dict[str, Any] = {}
        
        # Load existing memory if file exists
        self.load_memory()

    def load_memory(self) -> Dict[str, Any]:
        """
        Read memory from the JSON file.
        
        If the file doesn't exist, create a new empty memory.
        
        Returns:
            The memory dictionary
        
        Example:
            memory = manager.load_memory()
            print(memory['total_runs'])  # Shows total runs
        """
        # Check if memory file exists
        if os.path.exists(self.memory_file):
            try:
                # Open and read the JSON file
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memory = json.load(f)
                
                if self.logger:
                    self.logger.info(f"Loaded memory from {self.memory_file}")
                
                return self.memory
                
            except (json.JSONDecodeError, IOError) as e:
                # If file is corrupted or can't be read, start fresh
                if self.logger:
                    self.logger.warning(f"Could not load memory file: {e}. Starting fresh.")
                self.memory = self._create_empty_memory()
        else:
            # File doesn't exist, create empty memory
            self.memory = self._create_empty_memory()
        
        return self.memory

    def _create_empty_memory(self) -> Dict[str, Any]:
        """
        Create a new empty memory structure.
        
        This is used when:
        - The memory file doesn't exist
        - The memory file is corrupted
        - We want to reset the memory
        
        Returns:
            A dictionary with default/empty values
        """
        return {
            'repo_url': '',
            'last_checked': None,
            'last_updated': [],
            'total_runs': 0,
            'successful_upgrades': 0
        }

    def save_memory(self) -> bool:
        """
        Save the current memory to the JSON file.
        
        This writes all changes to disk so they persist between runs.
        
        Returns:
            True if save was successful, False otherwise
        
        Example:
            manager.save_memory()  # Saves current memory to file
        """
        try:
            # Ensure the directory exists
            memory_path = Path(self.memory_file)
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file with pretty formatting
            # indent=4 makes the JSON readable (each level indented 4 spaces)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=4)
            
            if self.logger:
                self.logger.info(f"Saved memory to {self.memory_file}")
            
            return True
            
        except IOError as e:
            if self.logger:
                self.logger.error(f"Failed to save memory: {e}")
            return False

    def get_last_check_time(self) -> Optional[str]:
        """
        Get the time when we last checked for updates.
        
        Returns:
            ISO format timestamp string, or None if never checked
        
        Example:
            last_check = manager.get_last_check_time()
            if last_check:
                print(f"Last checked: {last_check}")
        """
        return self.memory.get('last_checked')

    def update_last_check_time(self):
        """
        Update the last_checked timestamp to now.
        
        This should be called every time we check for updates.
        
        Example:
            manager.update_last_check_time()
        """
        # Get current time in UTC
        # isoformat() converts to string like "2024-01-15T10:30:00+00:00"
        self.memory['last_checked'] = datetime.now(timezone.utc).isoformat()
        
        # Increment total runs
        self.memory['total_runs'] = self.memory.get('total_runs', 0) + 1
        
        if self.logger:
            self.logger.info(f"Updated last check time: {self.memory['last_checked']}")

    def record_upgrade(
        self, 
        branch_name: str, 
        packages: List[str], 
        pr_url: str = ''
    ) -> bool:
        """
        Record an upgrade that was performed.
        
        This saves information about what was upgraded so we don't
        upgrade the same packages again too soon.
        
        Args:
            branch_name: The git branch name (e.g., "auto/dependency-update-1705312200")
            packages: List of package names that were upgraded
            pr_url: URL to the pull request (optional)
        
        Returns:
            True if recorded successfully
        
        Example:
            manager.record_upgrade(
                branch_name="auto/dependency-update-1705312200",
                packages=["lodash", "axios"],
                pr_url="https://github.com/user/project/pull/5"
            )
        """
        # Create a new entry for this upgrade
        upgrade_entry = {
            'branch': branch_name,
            'packages': packages,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pr_url': pr_url
        }
        
        # Add to the list of last_updated entries
        # We keep a history of all upgrades
        last_updated = self.memory.get('last_updated', [])
        last_updated.append(upgrade_entry)
        self.memory['last_updated'] = last_updated
        
        # Increment successful upgrades counter
        self.memory['successful_upgrades'] = self.memory.get('successful_upgrades', 0) + 1
        
        if self.logger:
            self.logger.info(f"Recorded upgrade: {packages} on branch {branch_name}")
        
        # Save to file
        return self.save_memory()

    def has_been_upgraded(self, package_name: str, days: int = 7) -> bool:
        """
        Check if a package was upgraded recently.
        
        This prevents us from upgrading the same package too frequently.
        
        Args:
            package_name: Name of the package to check
            days: How many days to look back (default 7)
        
        Returns:
            True if package was upgraded in the last 'days', False otherwise
        
        Example:
            if manager.has_been_upgraded('lodash', days=7):
                print("Skip lodash - upgraded recently")
            else:
                print("Upgrade lodash")
        """
        # Get all upgrade entries
        last_updated = self.memory.get('last_updated', [])
        
        # Calculate the cutoff date
        # datetime.now(timezone.utc) gives current time
        # We subtract 'days' to get the cutoff time
        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
        
        # Check each upgrade entry
        for entry in last_updated:
            # Get the timestamp of this upgrade
            timestamp_str = entry.get('timestamp', '')
            if not timestamp_str:
                continue
            
            try:
                # Parse the ISO timestamp string back to datetime
                entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                # Skip if this entry is older than our cutoff
                if entry_time.timestamp() < cutoff_time:
                    continue
                
                # Check if this package was in this upgrade
                packages = entry.get('packages', [])
                if package_name in packages:
                    return True
                    
            except (ValueError, TypeError):
                # If timestamp is invalid, skip this entry
                continue
        
        # Package wasn't upgraded recently
        return False

    def get_recently_upgraded_packages(self, days: int = 7) -> List[str]:
        """
        Get a list of all packages upgraded in the last N days.
        
        Args:
            days: How many days to look back (default 7)
        
        Returns:
            List of package names that were recently upgraded
        
        Example:
            recent = manager.get_recently_upgraded_packages(days=7)
            print(f"Recently upgraded: {recent}")  # ['lodash', 'axios']
        """
        recently_upgraded = set()
        last_updated = self.memory.get('last_updated', [])
        
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
        
        for entry in last_updated:
            timestamp_str = entry.get('timestamp', '')
            if not timestamp_str:
                continue
            
            try:
                entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                if entry_time.timestamp() < cutoff_time:
                    continue
                
                # Add all packages from this entry to our set
                packages = entry.get('packages', [])
                recently_upgraded.update(packages)
                
            except (ValueError, TypeError):
                continue
        
        return list(recently_upgraded)

    def clear_old_entries(self, days: int = 30) -> int:
        """
        Remove old entries from memory to keep it clean.
        
        This is optional cleanup - it removes entries older than 'days'
        to prevent the memory file from getting too big.
        
        Args:
            days: Remove entries older than this many days (default 30)
        
        Returns:
            Number of entries removed
        
        Example:
            removed = manager.clear_old_entries(days=30)
            print(f"Removed {removed} old entries")
        """
        last_updated = self.memory.get('last_updated', [])
        
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
        
        # Filter to keep only recent entries
        new_list = []
        removed_count = 0
        
        for entry in last_updated:
            timestamp_str = entry.get('timestamp', '')
            if not timestamp_str:
                continue
            
            try:
                entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                # Keep entry if it's recent enough
                if entry_time.timestamp() >= cutoff_time:
                    new_list.append(entry)
                else:
                    removed_count += 1
                    
            except (ValueError, TypeError):
                # Keep entries with invalid timestamps
                new_list.append(entry)
        
        # Update memory
        self.memory['last_updated'] = new_list
        
        if removed_count > 0:
            if self.logger:
                self.logger.info(f"Cleared {removed_count} old entries from memory")
            self.save_memory()
        
        return removed_count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the agent's activity.
        
        Returns:
            Dictionary with stats (total_runs, successful_upgrades, etc.)
        
        Example:
            stats = manager.get_stats()
            print(f"Total runs: {stats['total_runs']}")
            print(f"Successful upgrades: {stats['successful_upgrades']}")
        """
        return {
            'total_runs': self.memory.get('total_runs', 0),
            'successful_upgrades': self.memory.get('successful_upgrades', 0),
            'last_checked': self.memory.get('last_checked'),
            'recently_upgraded_count': len(self.get_recently_upgraded_packages())
        }

    def set_repo_url(self, repo_url: str):
        """
        Set the repository URL being monitored.
        
        Args:
            repo_url: The GitHub repository URL
        
        Example:
            manager.set_repo_url('https://github.com/user/project')
        """
        self.memory['repo_url'] = repo_url
        self.save_memory()


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get memory manager
# ============================================================================

def get_memory_manager(
    memory_file: str = 'memory.json', 
    logger = None
) -> MemoryManager:
    """
    Create a MemoryManager instance.
    
    Args:
        memory_file: Path to the memory JSON file
        logger: Optional logger instance
    
    Returns:
        A MemoryManager instance
    
    Example:
        memory = get_memory_manager('memory.json')
        memory.record_upgrade('branch', ['package'])
    """
    return MemoryManager(memory_file, logger)


# ============================================================================
# EXAMPLE USAGE - How to use this memory manager
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python memory_manager.py
    
    It demonstrates how to use the MemoryManager.
    """
    # Import our logger (from the file we created earlier)
    import sys
    sys.path.insert(0, 'utils')
    from logger import get_logger
    
    # Create a logger
    logger = get_logger()
    
    # Create memory manager
    memory = get_memory_manager('memory.json', logger)
    
    # Show current stats
    print("\n=== Current Stats ===")
    stats = memory.get_stats()
    print(f"Total runs: {stats['total_runs']}")
    print(f"Successful upgrades: {stats['successful_upgrades']}")
    print(f"Last checked: {stats['last_checked']}")
    
    # Record an upgrade
    print("\n=== Recording Upgrade ===")
    memory.record_upgrade(
        branch_name="auto/dependency-update-1705312200",
        packages=["lodash", "axios"],
        pr_url="https://github.com/abdullahadm9862873-oss/TestingDependency1/pull/1"
    )
    
    # Check if a package was upgraded
    print("\n=== Checking Packages ===")
    print(f"Was 'lodash' upgraded recently? {memory.has_been_upgraded('lodash')}")
    print(f"Was 'react' upgraded recently? {memory.has_been_upgraded('react')}")
    
    # Show updated stats
    print("\n=== Updated Stats ===")
    stats = memory.get_stats()
    print(f"Total runs: {stats['total_runs']}")
    print(f"Successful upgrades: {stats['successful_upgrades']}")
