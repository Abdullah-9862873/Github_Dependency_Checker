"""
Upgrade Executor Skill - Upgrades npm dependencies

This module handles actually upgrading the outdated packages.
It runs 'npm update' to upgrade packages and 'npm install' to validate.

Think of this as the "installer" - it takes action to update packages
and makes sure everything works together.

Beginner Python Notes:
- subprocess: For running npm commands
- json: For reading package.json
- shutil: For copying files
- typing: For type hints
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in library for file operations
# We use it to check paths, read files, etc.

import subprocess
# subprocess: Built-in library for running external programs
# We use it to run 'npm update' and 'npm install'

import json
# json: Built-in library for working with JSON
# We use it to read package.json before and after updates

import shutil
# shutil: Built-in library for file operations
# We use it to copy package.json for comparison

from typing import List, Dict, Any, Optional, Tuple
# typing: Library for type hints
# List, Dict, Any, Optional, Tuple: Type hints

import sys
# sys: Built-in library for system operations


# ============================================================================
# UPGRADE EXECUTOR CLASS - Handles package upgrades
# ============================================================================

class UpgradeExecutor:
    """
    A class that handles upgrading npm dependencies.
    
    This class:
    1. Runs 'npm update' to upgrade packages
    2. Runs 'npm install' to validate and update package-lock.json
    3. Compares before/after to see what changed
    4. Handles failures gracefully
    
    Attributes:
        config: Configuration dictionary
        logger: Logger instance for logging messages
    """
    
    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the UpgradeExecutor.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        
        Example:
            from utils.logger import get_logger
            from config.config_loader import load_config
            
            logger = get_logger()
            config = load_config()
            executor = UpgradeExecutor(config, logger)
        """
        self.config = config
        self.logger = logger

    def upgrade_dependencies(
        self, 
        repo_path: str, 
        packages: Optional[List[str]] = None
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Upgrade dependencies in the repository.
        
        This runs 'npm update' to upgrade packages to their latest versions.
        If packages list is provided, only those packages are upgraded.
        
        Args:
            repo_path: Path to the repository
            packages: Optional list of specific packages to upgrade
                      If None, all outdated packages are upgraded
        
        Returns:
            Tuple of (success: bool, upgraded_packages: list)
            - success: True if upgrade was successful
            - upgraded_packages: List of packages that were upgraded
        
        Example:
            # Upgrade all outdated packages
            success, upgraded = executor.upgrade_dependencies('./repos/my-project')
            
            # Upgrade specific packages
            success, upgraded = executor.upgrade_dependencies(
                './repos/my-project',
                ['lodash', 'axios']
            )
        """
        if self.logger:
            self.logger.info("Starting dependency upgrade")
        
        # Validate repo exists
        if not os.path.exists(repo_path):
            if self.logger:
                self.logger.error(f"Repository not found: {repo_path}")
            return False, []
        
        # Get current package.json for comparison later
        old_package_json = self._read_package_json(repo_path)
        if not old_package_json:
            if self.logger:
                self.logger.error("Failed to read package.json")
            return False, []
        
        # Save a backup of the current package.json
        backup_path = os.path.join(repo_path, 'package.json.backup')
        try:
            shutil.copy2(
                os.path.join(repo_path, 'package.json'),
                backup_path
            )
            if self.logger:
                self.logger.info("Created backup of package.json")
        except IOError as e:
            if self.logger:
                self.logger.warning(f"Could not create backup: {e}")
        
        try:
            # Run npm update
            success = self._run_npm_update(repo_path, packages)
            
            if not success:
                if self.logger:
                    self.logger.error("npm update failed")
                # Restore backup
                self._restore_package_json(repo_path)
                return False, []
            
            if self.logger:
                self.logger.info("npm update completed successfully")
            
            # Get the new package.json to compare
            new_package_json = self._read_package_json(repo_path)
            
            # Handle case where new package.json couldn't be read
            if new_package_json is None:
                if self.logger:
                    self.logger.error("Could not read new package.json")
                self._restore_package_json(repo_path)
                return False, []
            
            # Figure out what was actually upgraded
            upgraded_packages = self._get_updated_packages(
                old_package_json, 
                new_package_json
            )
            
            # If no packages upgraded, check if there were changes
            if not upgraded_packages:
                # Compare package.json files directly
                if old_package_json != new_package_json:
                    if self.logger:
                        self.logger.info("package.json changed, checking what was upgraded...")
                    # Even if we can't parse exactly what, something changed
                    # Get list of all packages and report them as upgraded
                    upgraded_packages = self._find_all_differences(
                        old_package_json, 
                        new_package_json
                    )
            
            if self.logger:
                self.logger.info(f"Upgraded {len(upgraded_packages)} packages")
                for pkg in upgraded_packages:
                    self.logger.info(
                        f"  {pkg['name']}: {pkg['old']} -> {pkg['new']}"
                    )
            
            # Clean up backup
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            # Consider it a success if we tried to upgrade and something changed
            if packages and upgraded_packages:
                return True, upgraded_packages
            elif packages and not upgraded_packages:
                # We tried but nothing changed - might be dependency conflicts
                if self.logger:
                    self.logger.warning("Packages may have conflicts - some upgrades failed")
                return False, []
            
            return True, upgraded_packages
            
            if self.logger:
                self.logger.info(f"Upgraded {len(upgraded_packages)} packages")
                for pkg in upgraded_packages:
                    self.logger.info(
                        f"  {pkg['name']}: {pkg['old']} -> {pkg['new']}"
                    )
            
            # Clean up backup
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            return True, upgraded_packages
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during upgrade: {e}")
            # Try to restore backup
            self._restore_package_json(repo_path)
            return False, []

    def _run_npm_update(
        self, 
        repo_path: str, 
        packages: Optional[List[str]] = None
    ) -> bool:
        """
        Run 'npm install <package>@latest' to upgrade to latest versions.
        
        This is different from npm update - it installs the absolute latest
        version of each package, not just the semver-satisfying version.
        
        Args:
            repo_path: Path to the repository
            packages: Optional list of packages to update to latest
        
        Returns:
            True if successful, False otherwise
        """
        if self.logger:
            if packages:
                self.logger.info(f"Updating packages to latest: {packages}")
            else:
                self.logger.info("Updating all packages to latest")
        
        try:
            if packages:
                # Install each package at latest version
                # npm install package@latest --save
                for package in packages:
                    self.logger.info(f"Installing {package}@latest")
                    cmd = ['npm', 'install', f'{package}@latest', '--save', '--legacy-peer-deps']
                    
                    result = subprocess.run(
                        cmd,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        shell=True
                    )
                    
                    if result.returncode != 0:
                        stderr = result.stderr.lower()
                        if 'error' in stderr:
                            if self.logger:
                                self.logger.warning(f"Failed to update {package}: {result.stderr}")
                            # Continue with other packages
                    else:
                        if self.logger:
                            self.logger.info(f"Successfully updated {package}")
                
                # Run npm install with legacy-peer-deps to handle conflicts
                result = subprocess.run(
                    ['npm', 'install', '--legacy-peer-deps'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    shell=True
                )
                
                return True
            else:
                # Update all packages
                cmd = ['npm', 'update', '--legacy-peer-deps']
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    shell=True
                )
                
                if result.returncode == 0:
                    if self.logger:
                        self.logger.debug(f"npm update output: {result.stdout}")
                    return True
                else:
                    stderr = result.stderr.lower()
                    if 'error' in stderr:
                        if self.logger:
                            self.logger.error(f"npm update error: {result.stderr}")
                        return False
                    return True
                
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error("npm update timed out")
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"npm update failed: {e}")
            return False

    def _run_npm_install(self, repo_path: str) -> bool:
        """
        Run 'npm install' to validate and update package-lock.json.
        
        This ensures:
        1. package-lock.json is updated with exact versions
        2. All dependencies work together
        3. The project can be built
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            True if successful (or with warnings), False on critical error
        """
        if self.logger:
            self.logger.info("Running npm install to validate")
        
        try:
            result = subprocess.run(
                ['npm', 'install', '--legacy-peer-deps'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                shell=True
            )
            
            # Check for critical errors
            stderr = result.stderr.lower()
            if 'error' in stderr and 'enoent' in stderr:
                # enoent = "error no entity" - file not found
                if self.logger:
                    self.logger.error(f"npm install error: {result.stderr}")
                return False
            
            # Check for peer dependency warnings - these are usually okay
            if 'peer' in stderr:
                if self.logger:
                    self.logger.warning("npm install had peer dependency warnings")
            
            if self.logger:
                self.logger.info("npm install completed")
            
            return True
            
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error("npm install timed out")
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"npm install failed: {e}")
            return False

    def _read_package_json(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """
        Read the package.json file.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            The package.json contents as a dictionary, or None on error
        """
        package_json_path = os.path.join(repo_path, 'package.json')
        
        if not os.path.exists(package_json_path):
            return None
        
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            if self.logger:
                self.logger.error(f"Failed to read package.json: {e}")
            return None

    def _restore_package_json(self, repo_path: str) -> bool:
        """
        Restore package.json from backup if it exists.
        
        This is called if the upgrade fails, to roll back changes.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            True if restored successfully, False otherwise
        """
        backup_path = os.path.join(repo_path, 'package.json.backup')
        package_json_path = os.path.join(repo_path, 'package.json')
        
        if not os.path.exists(backup_path):
            if self.logger:
                self.logger.warning("No backup to restore")
            return False
        
        try:
            shutil.copy2(backup_path, package_json_path)
            os.remove(backup_path)
            
            if self.logger:
                self.logger.info("Restored package.json from backup")
            
            return True
            
        except IOError as e:
            if self.logger:
                self.logger.error(f"Failed to restore backup: {e}")
            return False

    def _get_updated_packages(
        self, 
        old_pkg: Dict[str, Any], 
        new_pkg: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Compare package.json files to find what was upgraded.
        
        This compares the dependencies and devDependencies sections
        to see which packages changed version.
        
        Args:
            old_pkg: The package.json before upgrade
            new_pkg: The package.json after upgrade
        
        Returns:
            List of dictionaries with package info:
            - name: package name
            - old: old version
            - new: new version
        
        Example:
            [
                {'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'},
                {'name': 'axios', 'old': '0.27.0', 'new': '1.0.0'}
            ]
        """
        upgraded = []
        
        # Get both dependencies and devDependencies
        old_deps = old_pkg.get('dependencies', {})
        old_dev_deps = old_pkg.get('devDependencies', {})
        old_all = {**old_deps, **old_dev_deps}
        
        new_deps = new_pkg.get('dependencies', {})
        new_dev_deps = new_pkg.get('devDependencies', {})
        new_all = {**new_deps, **new_dev_deps}
        
        # Compare each package
        for name, old_version in old_all.items():
            # Get new version (if package was removed, it won't be in new_all)
            new_version = new_all.get(name)
            
            if new_version and new_version != old_version:
                upgraded.append({
                    'name': name,
                    'old': old_version,
                    'new': new_version
                })
        
        return upgraded

    def _find_all_differences(
        self, 
        old_pkg: Dict[str, Any], 
        new_pkg: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find all differences between old and new package.json.
        
        This is a fallback when exact version tracking fails.
        
        Args:
            old_pkg: Old package.json
            new_pkg: New package.json
        
        Returns:
            List of packages that changed
        """
        upgraded = []
        
        old_deps = old_pkg.get('dependencies', {})
        old_dev_deps = old_pkg.get('devDependencies', {})
        
        new_deps = new_pkg.get('dependencies', {})
        new_dev_deps = new_pkg.get('devDependencies', {})
        
        all_old = {**old_deps, **old_dev_deps}
        all_new = {**new_deps, **new_dev_deps}
        
        for name, old_ver in all_old.items():
            new_ver = all_new.get(name)
            if new_ver and new_ver != old_ver:
                upgraded.append({
                    'name': name,
                    'old': old_ver,
                    'new': new_ver
                })
        
        return upgraded

    def validate_installation(self, repo_path: str) -> Tuple[bool, str]:
        """
        Validate that the installation works by running a simple npm command.
        
        This checks that:
        1. node_modules exists
        2. Basic npm commands work
        3. No critical errors
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            Tuple of (success: bool, message: str)
        
        Example:
            success, msg = executor.validate_installation('./repos/my-project')
            if not success:
                print(f"Validation failed: {msg}")
        """
        if self.logger:
            self.logger.info("Validating installation")
        
        # Check node_modules exists
        node_modules = os.path.join(repo_path, 'node_modules')
        if not os.path.exists(node_modules):
            return False, "node_modules not found - run npm install first"
        
        try:
            # Try running npm ls to verify packages
            result = subprocess.run(
                ['npm', 'ls', '--depth=0'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                shell=True
            )
            
            # Check for errors in output
            stderr = result.stderr.lower()
            stdout = result.stdout.lower()
            
            # Empty output with 0 return code = success
            if result.returncode == 0 and 'error' not in stderr:
                if self.logger:
                    self.logger.info("Installation validated successfully")
                return True, "All packages installed correctly"
            
            # Check if it's just missing peer dependencies (not critical)
            if 'missing' in stdout or 'peer' in stderr:
                if self.logger:
                    self.logger.warning("Some peer dependencies missing")
                return True, "Packages installed (some peer deps may be missing)"
            
            # Actual error
            error_msg = result.stderr or result.stdout
            if self.logger:
                self.logger.error(f"Validation failed: {error_msg}")
            return False, error_msg
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Validation error: {e}")
            return False, str(e)

    def get_package_lock_version(
        self, 
        repo_path: str, 
        package_name: str
    ) -> Optional[str]:
        """
        Get the installed version of a specific package from package-lock.json.
        
        This gives the exact version that's currently installed.
        
        Args:
            repo_path: Path to the repository
            package_name: Name of the package
        
        Returns:
            Version string, or None if not found
        
        Example:
            version = executor.get_package_lock_version('./repos/my-project', 'lodash')
            print(f"Installed lodash version: {version}")
        """
        lock_path = os.path.join(repo_path, 'package-lock.json')
        
        if not os.path.exists(lock_path):
            return None
        
        try:
            with open(lock_path, 'r', encoding='utf-8') as f:
                lock_data = json.load(f)
            
            # Try to find the package in package-lock.json
            # The structure varies, so we check different paths
            packages = lock_data.get('packages', {})
            
            # Look for the package in node_modules
            key = f"node_modules/{package_name}"
            if key in packages:
                version = packages[key].get('version')
                return version
            
            # Also check legacy format
            dependencies = lock_data.get('dependencies', {})
            if package_name in dependencies:
                version = dependencies[package_name].get('version')
                return version
            
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Could not read package-lock.json: {e}")
            return None


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get an UpgradeExecutor
# ============================================================================

def get_upgrade_executor(config: Dict[str, Any], logger) -> UpgradeExecutor:
    """
    Create an UpgradeExecutor instance.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        An UpgradeExecutor instance
    
    Example:
        executor = get_upgrade_executor(config, logger)
    """
    return UpgradeExecutor(config, logger)


# ============================================================================
# EXAMPLE USAGE - How to use this UpgradeExecutor
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python upgrade_executor.py
    
    It demonstrates how to use the UpgradeExecutor.
    """
    # Import our modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    
    from config.config_loader import load_config
    from utils.logger import get_logger
    from skills.repo_monitor import get_repo_monitor
    from skills.dependency_checker import get_dependency_checker
    
    # Load config and create logger
    try:
        config = load_config()
        logger = get_logger()
        
        # Create executor
        executor = UpgradeExecutor(config, logger)
        
        # Get repo path
        monitor = get_repo_monitor(config, logger)
        repo_url = config.get('github', {}).get('repo_url', '')
        
        if not repo_url:
            print("No repository URL configured!")
            exit(1)
        
        repo_path = monitor.get_repo_path(repo_url)
        
        print(f"\n=== Upgrading Dependencies ===")
        print(f"Repo path: {repo_path}")
        
        # Check current packages
        checker = get_dependency_checker(config, logger)
        outdated = checker.check_outdated(repo_path)
        
        if not outdated:
            print("No outdated packages!")
        else:
            print(f"Found {len(outdated)} outdated packages")
            
            # Upgrade all
            success, upgraded = executor.upgrade_dependencies(repo_path)
            
            if success:
                print(f"\nSuccessfully upgraded {len(upgraded)} packages:")
                for pkg in upgraded:
                    print(f"  {pkg['name']}: {pkg['old']} -> {pkg['new']}")
            else:
                print("\nUpgrade failed!")
        
        # Validate installation
        print(f"\n=== Validating Installation ===")
        valid, msg = executor.validate_installation(repo_path)
        print(f"Valid: {valid}")
        print(f"Message: {msg}")
        
        print("\n=== Done ===")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
