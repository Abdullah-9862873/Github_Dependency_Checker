"""
Dependency Checker Skill - Checks for outdated npm packages

This module handles checking which packages in a Node.js project are outdated.
It runs 'npm outdated' and parses the output to find packages that need updating.

Think of this as the "package inspector" - it looks at package.json and
package-lock.json to see what's old and needs updating.

Beginner Python Notes:
- subprocess: For running npm commands
- json: For parsing npm output
- typing: For type hints
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in library for file operations
# We use it to check if directories/files exist

import subprocess
# subprocess: Built-in library for running external programs
# We use it to run 'npm outdated' command

import json
# json: Built-in library for working with JSON data
# npm outdated --json returns JSON output

from typing import List, Dict, Any, Optional
# typing: Library for type hints
# List: List type (e.g., List[str] is a list of strings)
# Dict: Dictionary type (e.g., Dict[str, int] is a dict with string keys, int values)
# Any: Any type
# Optional: Can be the type or None

import sys
# sys: Built-in library for system operations


# ============================================================================
# DEPENDENCY CHECKER CLASS - Checks for outdated packages
# ============================================================================

class DependencyChecker:
    """
    A class that checks for outdated npm packages in a project.
    
    This class runs 'npm outdated' to find packages that have newer versions
    available than what's currently installed.
    
    It can parse the output and filter out packages that were recently
    upgraded (to avoid upgrading the same package repeatedly).
    
    Attributes:
        config: Configuration dictionary
        logger: Logger instance for logging messages
    """
    
    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the DependencyChecker.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        
        Example:
            from utils.logger import get_logger
            from config.config_loader import load_config
            
            logger = get_logger()
            config = load_config()
            checker = DependencyChecker(config, logger)
        """
        self.config = config
        self.logger = logger

    def check_outdated(self, repo_path: str) -> List[Dict[str, Any]]:
        """
        Check for outdated packages in a repository.
        
        This runs 'npm outdated --json' and parses the output to find
        packages that have newer versions available.
        
        Args:
            repo_path: Path to the repository to check
        
        Returns:
            List of dictionaries, each containing package information:
            - name: Package name
            - current: Currently installed version
            - wanted: Version that satisfies semver range
            - latest: Latest available version
            - dependent: Package that depends on this
            - location: Where the package is installed
        
        Example:
            outdated = checker.check_outdated('./repos/my-project')
            for pkg in outdated:
                print(f"{pkg['name']}: {pkg['current']} -> {pkg['latest']}")
        """
        if self.logger:
            self.logger.info("Checking for outdated packages")
        
        # Validate that the repo exists
        if not os.path.exists(repo_path):
            if self.logger:
                self.logger.error(f"Repository not found: {repo_path}")
            return []
        
        # Check if package.json exists
        package_json = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json):
            if self.logger:
                self.logger.warning(f"No package.json found in {repo_path}")
            return []
        
        try:
            # Run 'npm outdated --json' command
            # --json gives us machine-readable output
            
            # On Windows, we need to use shell=True to find npm
            # or we can explicitly pass the environment
            result = subprocess.run(
                ['npm', 'outdated', '--json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                shell=True    # Use shell on Windows to find npm
            )
            
            # npm outdated returns exit code 1 when there are outdated packages
            # (it's not an error, just indicating packages are outdated)
            # So we capture both stdout and stderr regardless of return code
            
            output = result.stdout
            
            # Handle empty output (no outdated packages)
            if not output or output.strip() == '':
                if self.logger:
                    self.logger.info("No outdated packages found")
                return []
            
            # Parse the JSON output
            # npm outdated returns a dictionary like:
            # {
            #   "lodash": {
            #     "current": "4.17.15",
            #     "wanted": "4.17.21",
            #     "latest": "4.17.21",
            #     "dependent": "myproject",
            #     "location": "/path/to/node_modules/lodash"
            #   }
            # }
            try:
                outdated_data = json.loads(output)
            except json.JSONDecodeError as e:
                if self.logger:
                    self.logger.error(f"Failed to parse npm output: {e}")
                return []
            
            # Convert the dictionary into a list of packages
            packages = self.parse_outdated_packages(outdated_data)
            
            if self.logger:
                self.logger.info(f"Found {len(packages)} outdated packages")
                for pkg in packages:
                    self.logger.info(
                        f"  {pkg['name']}: {pkg['current']} -> {pkg['latest']}"
                    )
            
            return packages
            
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error("npm outdated command timed out")
            return []
            
        except FileNotFoundError:
            if self.logger:
                self.logger.error("npm is not installed or not in PATH")
            return []
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking outdated packages: {e}")
            return []

    def parse_outdated_packages(self, json_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse the npm outdated JSON output into a list format.
        
        npm outdated returns a dictionary where keys are package names.
        This converts it to a list of dictionaries for easier processing.
        
        Args:
            json_output: The JSON output from npm outdated
        
        Returns:
            List of package dictionaries with standardized keys
        
        Example:
            Input: {"lodash": {"current": "4.17.15", "wanted": "4.17.21", ...}}
            Output: [{"name": "lodash", "current": "4.17.15", "wanted": "4.17.21", ...}]
        """
        packages = []
        
        # Iterate through each package in the dictionary
        # .items() gives us both key (name) and value (info)
        for name, info in json_output.items():
            # Create a standardized package dictionary
            package_info = {
                'name': name,  # Package name
                'current': info.get('current', 'N/A'),  # Currently installed version
                'wanted': info.get('wanted', 'N/A'),    # Wanted version (semver range)
                'latest': info.get('latest', 'N/A'),    # Latest available version
                'dependent': info.get('dependent', 'unknown'),  # Parent package
                'location': info.get('location', '')    # File location
            }
            
            packages.append(package_info)
        
        return packages

    def filter_packages_to_upgrade(
        self, 
        outdated_list: List[Dict[str, Any]], 
        memory: Any
    ) -> List[Dict[str, Any]]:
        """
        Filter out packages that were recently upgraded.
        
        This uses the memory manager to check which packages were upgraded
        recently (in the last 7 days by default). We don't want to upgrade
        the same package repeatedly - it wastes time and might break things.
        
        Args:
            outdated_list: List of outdated packages from check_outdated()
            memory: MemoryManager instance to check upgrade history
        
        Returns:
            Filtered list of packages that should be upgraded
        
        Example:
            outdated = checker.check_outdated('./repos/my-project')
            filtered = checker.filter_packages_to_upgrade(outdated, memory)
            # filtered won't include packages upgraded in the last 7 days
        """
        if not outdated_list:
            return []
        
        if self.logger:
            self.logger.info(f"Filtering {len(outdated_list)} outdated packages")
        
        # Get list of packages that were recently upgraded
        # This uses the memory manager to check history
        recently_upgraded = set()
        
        if memory:
            # Get packages upgraded in the last 7 days
            recent = memory.get_recently_upgraded_packages(days=7)
            recently_upgraded = set(recent)
            
            if recently_upgraded and self.logger:
                self.logger.info(
                    f"Excluding recently upgraded packages: {recently_upgraded}"
                )
        
        # Filter out recently upgraded packages
        filtered = []
        for pkg in outdated_list:
            if pkg['name'] in recently_upgraded:
                if self.logger:
                    self.logger.info(
                        f"Skipping {pkg['name']} - upgraded recently"
                    )
            else:
                filtered.append(pkg)
        
        if self.logger:
            self.logger.info(
                f"Filtered to {len(filtered)} packages to upgrade"
            )
        
        return filtered

    def get_package_json(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """
        Read and return the package.json file contents.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            The package.json contents as a dictionary, or None if not found
        
        Example:
            pkg_json = checker.get_package_json('./repos/my-project')
            name = pkg_json.get('name')
        """
        package_json_path = os.path.join(repo_path, 'package.json')
        
        if not os.path.exists(package_json_path):
            if self.logger:
                self.logger.warning(f"package.json not found at {package_json_path}")
            return None
        
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            if self.logger:
                self.logger.error(f"Failed to read package.json: {e}")
            return None

    def get_installed_packages(self, repo_path: str) -> List[str]:
        """
        Get a list of all installed packages.
        
        This runs 'npm ls --depth=0' to get all top-level dependencies.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            List of installed package names
        
        Example:
            installed = checker.get_installed_packages('./repos/my-project')
            print(f"Installed {len(installed)} packages")
        """
        if self.logger:
            self.logger.info("Getting installed packages")
        
        try:
            result = subprocess.run(
                ['npm', 'ls', '--depth=0', '--json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout
            if not output or output.strip() == '':
                return []
            
            data = json.loads(output)
            
            # Get dependencies from package.json
            package_json = self.get_package_json(repo_path)
            if not package_json:
                return []
            
            packages = []
            
            # Combine dependencies and devDependencies
            deps = package_json.get('dependencies', {})
            dev_deps = package_json.get('devDependencies', {})
            
            packages = list(deps.keys()) + list(dev_deps.keys())
            
            return packages
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get installed packages: {e}")
            return []

    def has_package_json(self, repo_path: str) -> bool:
        """
        Check if a repository has a package.json file.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            True if package.json exists, False otherwise
        
        Example:
            if checker.has_package_json('./repos/my-project'):
                print("This is a Node.js project")
        """
        package_json = os.path.join(repo_path, 'package.json')
        return os.path.exists(package_json)

    def has_node_modules(self, repo_path: str) -> bool:
        """
        Check if a repository has node_modules installed.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            True if node_modules exists, False otherwise
        
        Example:
            if not checker.has_node_modules('./repos/my-project'):
                print("Need to run npm install first")
        """
        node_modules = os.path.join(repo_path, 'node_modules')
        return os.path.exists(node_modules)


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get a DependencyChecker
# ============================================================================

def get_dependency_checker(config: Dict[str, Any], logger) -> DependencyChecker:
    """
    Create a DependencyChecker instance.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        A DependencyChecker instance
    
    Example:
        checker = get_dependency_checker(config, logger)
    """
    return DependencyChecker(config, logger)


# ============================================================================
# EXAMPLE USAGE - How to use this DependencyChecker
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python dependency_checker.py
    
    It demonstrates how to use the DependencyChecker.
    """
    # Import our modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    
    from config.config_loader import load_config
    from utils.logger import get_logger
    from skills.memory_manager import get_memory_manager
    
    # Load config and create logger
    try:
        config = load_config()
        logger = get_logger()
        
        # Create DependencyChecker
        checker = DependencyChecker(config, logger)
        
        # Get repo path from config
        from skills.repo_monitor import get_repo_monitor
        monitor = get_repo_monitor(config, logger)
        repo_url = config.get('github', {}).get('repo_url', '')
        
        if not repo_url:
            print("No repository URL configured!")
            exit(1)
        
        # Get the local repo path
        repo_path = monitor.get_repo_path(repo_url)
        
        # Check if it's a Node.js project
        print(f"\n=== Checking Repository ===")
        print(f"Repo path: {repo_path}")
        print(f"Has package.json: {checker.has_package_json(repo_path)}")
        print(f"Has node_modules: {checker.has_node_modules(repo_path)}")
        
        # Get package.json info
        print(f"\n=== Package.json Info ===")
        pkg_json = checker.get_package_json(repo_path)
        if pkg_json:
            print(f"Project name: {pkg_json.get('name', 'unknown')}")
            print(f"Version: {pkg_json.get('version', 'unknown')}")
        
        # Check for outdated packages
        print(f"\n=== Checking Outdated Packages ===")
        outdated = checker.check_outdated(repo_path)
        
        if outdated:
            print(f"Found {len(outdated)} outdated packages:")
            for pkg in outdated:
                print(f"  {pkg['name']}: {pkg['current']} -> {pkg['latest']}")
        else:
            print("All packages are up to date!")
        
        # Test filtering with memory
        print(f"\n=== Testing Memory Filter ===")
        memory = get_memory_manager('memory.json', logger)
        
        # Get packages that were recently upgraded
        recent = memory.get_recently_upgraded_packages(days=7)
        print(f"Recently upgraded: {recent}")
        
        # Filter outdated packages
        filtered = checker.filter_packages_to_upgrade(outdated, memory)
        print(f"After filtering: {len(filtered)} packages to upgrade")
        
        print("\n=== Done ===")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
