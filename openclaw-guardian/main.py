#!/usr/bin/env python3
"""
OpenClaw Guardian - Automated GitHub Dependency Updater
Main entry point

This is the brain of the application - it orchestrates all the skills
to create an autonomous agent that:
1. Checks repositories for outdated packages
2. Downgrades then upgrades them
3. Creates pull requests

Beginner Python Notes:
- argparse: For command-line arguments
- time: For sleep/delay between cycles
- signal: For handling Ctrl+C gracefully
- sys: For system operations
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in library for file operations
# We use it to change directories, check paths, etc.

import sys
# sys: Built-in library for system operations
# We use it for exit codes and arguments

import time
# time: Built-in library for time-related functions
# We use it for sleep() between cycles

import signal
# signal: Built-in library for handling signals
# We use it to handle Ctrl+C gracefully

import argparse
# argparse: Built-in library for command-line arguments
# We use it to parse --once, --config, --verbose flags

import importlib
# importlib: Built-in library for dynamic imports
# We use it to import modules dynamically if needed


# ============================================================================
# MAIN ORCHESTRATOR CLASS - Ties everything together
# ============================================================================

class OpenClawGuardian:
    """
    The main orchestrator class that runs the autonomous agent.
    
    This class coordinates all the different skills to:
    1. Load configuration
    2. Set up logging
    3. Clone/pull repository
    4. Check for outdated packages
    5. Downgrade then upgrade dependencies (if needed)
    6. Create pull request (if upgraded)
    7. Remember what was done (memory)
    8. Wait and repeat
    
    Attributes:
        config: Configuration dictionary
        logger: Logger instance
        memory: Memory manager
        monitor: Repository monitor
        checker: Dependency checker
        executor: Upgrade executor
        pr_creator: PR creator
    """
    
    def __init__(self, args):
        """
        Initialize the OpenClaw Guardian.
        
        Args:
            args: Parsed command-line arguments
        
        Example:
            guardian = OpenClawGuardian(args)
        """
        self.args = args
        self.config = None
        self.logger = None
        self.memory = None
        self.monitor = None
        self.checker = None
        self.executor = None
        self.pr_creator = None
        
        # Track if we're running
        self.running = False
        
        # Initialize everything
        self._initialize()
    
    def _initialize(self):
        """
        Initialize all components.
        
        This sets up:
        1. Configuration loader
        2. Logger
        3. Memory manager
        4. All the skills
        """
        print("Initializing OpenClaw Guardian...")
        
        # Step 1: Load configuration
        self._load_config()
        
        # Step 2: Set up logger
        self._setup_logger()
        
        # Step 3: Initialize memory manager
        self._setup_memory()
        
        # Step 4: Initialize all skills
        self._setup_skills()
        
        print("Initialization complete!")
    
    def _load_config(self):
        """
        Load configuration from config.yaml.
        
        This uses our ConfigLoader to read the config file
        and environment variables.
        """
        # Import here to avoid issues if not installed
        from config.config_loader import load_config
        
        # Get config file path from args or use default
        config_path = self.args.config if self.args else 'config.yaml'
        
        self.config = load_config(config_path)
        
        # Validate that we have what we need
        if not self.config.get('github', {}).get('repo_url'):
            raise ValueError("No repository URL configured. Please save configuration first.")
        if not self.config.get('github', {}).get('token'):
            raise ValueError("No GitHub token configured. Please save configuration first.")
    
    def _setup_logger(self):
        """
        Set up the logger.
        
        This creates a logger that writes to both console and file.
        """
        # Import here
        from utils.logger import get_logger
        
        # Determine log level from args
        log_level = 10  # DEBUG
        if self.args and not self.args.verbose:
            log_level = 20  # INFO
        
        self.logger = get_logger(
            name='openclaw-guardian',
            log_dir='logs',
            level=log_level
        )
        
        self.logger.info("Logger initialized")
    
    def _setup_memory(self):
        """
        Set up the memory manager.

        Memory is intentionally kept stateless — we NEVER read historical
        data from memory.json. Every run starts with an empty slate so that
        no previous upgrade history can influence the current run.
        """
        from skills.memory_manager import get_memory_manager

        memory_file = self.config.get('paths', {}).get('memory_file', 'memory.json')

        # Create manager object but immediately overwrite its in-memory state
        # with an empty dict, regardless of what is on disk.
        self.memory = get_memory_manager(memory_file, self.logger)
        self.memory.memory = self.memory._create_empty_memory()  # force blank state

        # Record which repo we're working on (doesn't affect upgrade logic)
        repo_url = self.config.get('github', {}).get('repo_url', '')
        self.memory.memory['repo_url'] = repo_url

        self.logger.info("Memory manager initialised with clean/empty state")
    
    def _setup_skills(self):
        """
        Initialize all the skill modules.
        
        This creates instances of:
        - RepoMonitor: for cloning/pulling repos
        - DependencyChecker: for checking outdated packages
        - UpgradeExecutor: for upgrading packages
        - PRCreator: for creating pull requests
        - MoltbookPoster: for posting upgrade notifications
        """
        from skills.repo_monitor import get_repo_monitor
        from skills.dependency_checker import get_dependency_checker
        from skills.upgrade_executor import get_upgrade_executor
        from skills.pr_creator import get_pr_creator
        from skills.moltbook_poster import MoltbookPoster
        
        # Create all skill instances
        self.monitor = get_repo_monitor(self.config, self.logger)
        self.checker = get_dependency_checker(self.config, self.logger)
        self.executor = get_upgrade_executor(self.config, self.logger)
        self.pr_creator = get_pr_creator(self.config, self.logger)
        self.moltbook_poster = MoltbookPoster(self.config, self.logger)
        
        self.logger.info("All skills initialized")
    
    def _install_dependencies(self, repo_path: str):
        """
        Install npm dependencies for the repository.
        
        This runs 'npm install' to ensure all dependencies are properly installed
        before checking for outdated packages.
        
        Args:
            repo_path: Path to the repository
        """
        import subprocess
        
        if not os.path.exists(repo_path):
            self.logger.error(f"Repository not found: {repo_path}")
            return False
        
        package_json = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json):
            self.logger.warning(f"No package.json found in {repo_path}")
            return False
        
        self.logger.info("Running npm install...")
        
        try:
            result = subprocess.run(
                ['npm', 'install'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for npm install
                shell=True
            )
            
            if result.returncode == 0:
                self.logger.info("npm install completed successfully")
                return True
            else:
                self.logger.warning(f"npm install had issues: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("npm install timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error running npm install: {e}")
            return False
    
    def _cleanup_repo(self, repo_path: str):
        """
        Delete the cloned repository after a cycle to keep things clean.

        Uses 'rd /s /q' on Windows (instead of shutil.rmtree) because .git
        object files have read-only attributes that shutil cannot remove,
        causing WinError 5 (Access Denied) and leaving stale directories.
        """
        import subprocess, time
        if not (repo_path and os.path.exists(repo_path)):
            return
        try:
            # First: strip read-only flags recursively so rmtree can work
            for attempt in range(3):
                try:
                    # Use Windows 'rd /s /q' which ignores read-only attrs
                    result = subprocess.run(
                        ['cmd', '/c', 'rd', '/s', '/q', repo_path],
                        capture_output=True, text=True, timeout=60
                    )
                    if not os.path.exists(repo_path):
                        self.logger.info(f"Cleaned up repository: {repo_path}")
                        return
                    time.sleep(1)
                except Exception as e_inner:
                    if attempt < 2:
                        time.sleep(1)
                        continue
            # Fallback: shutil with onerror handler for read-only files
            import stat
            def _force_remove(func, path, _):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            import shutil
            shutil.rmtree(repo_path, onerror=_force_remove)
            if not os.path.exists(repo_path):
                self.logger.info(f"Cleaned up repository: {repo_path}")
            else:
                self.logger.warning(f"Could not fully clean up: {repo_path}")
        except Exception as e:
            self.logger.warning(f"Could not clean up repository: {e}")

    def _UNUSED_cleanup_repo_old(self, repo_path: str):
        """(kept for reference only — replaced by _cleanup_repo above)"""
        import shutil, time
        if repo_path and os.path.exists(repo_path):
            try:
                for attempt in range(3):
                    try:
                        shutil.rmtree(repo_path)
                        self.logger.info(f"Cleaned up repository: {repo_path}")
                        break
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(0.5)
                            continue
                        self.logger.warning(f"Could not clean up repository: {e}")
            except Exception as e:
                self.logger.warning(f"Could not clean up repository: {e}")

    def run_cycle(self):
        """
        Run one complete cycle of the agent.
        
        This is the main workflow that runs on each iteration:
        1. Clone the repository fresh (always clone, delete after)
        2. Check for outdated packages
        3. If outdated: upgrade -> commit -> push -> create PR
        4. If not outdated: report no updates
        5. Cleanup (delete cloned repo)
        6. Return whether upgrades were made
        """
        self.logger.info("=" * 50)
        self.logger.info("Starting new cycle")
        
        # Get configuration
        repo_url = self.config.get('github', {}).get('repo_url', '')
        token = self.config.get('github', {}).get('token', '')
        
        repo_path = None
        
        # Step 1: Always clone fresh (delete existing first for clean state)
        self.logger.info("Step 1: Cloning repository fresh")
        try:
            repo_path = self.monitor.get_repo_path(repo_url)
            
            # Always start fresh — delete existing clone if present
            if os.path.exists(repo_path):
                self.logger.info("Removing old clone for fresh start...")
                self._cleanup_repo(repo_path)
            
            self.logger.info(f"Cloning {repo_url}...")
            self.monitor.clone_repo(repo_url, token)
            
            # Install dependencies after clone
            self.logger.info("Step 1b: Installing npm dependencies...")
            self._install_dependencies(repo_path)
                
        except Exception as e:
            self.logger.error(f"Failed to clone repository: {e}")
            self._cleanup_repo(repo_path)
            return (False, [], '')
        
        try:
            # Step 2: Check for outdated packages
            self.logger.info("Step 2: Checking for outdated packages")
            
            # Check if this is a Node.js project
            if not self.checker.has_package_json(repo_path):
                self.logger.warning("No package.json found - not a Node.js project")
                self._cleanup_repo(repo_path)
                return (False, [], '')
            
            # Check for outdated packages
            outdated = self.checker.check_outdated(repo_path)

            if not outdated:
                self.logger.info("No outdated packages found — all packages are at their latest versions")
                # Do NOT call update_last_check_time() — memory is stateless
                self._cleanup_repo(repo_path)
                return (False, [], '')
            
            self.logger.info(f"Found {len(outdated)} outdated packages — processing all of them")
            
            # No filter — always process every package npm outdated reports
            # (Memory is cleared on every page reload, so filtering would cause
            # false "up-to-date" results if the same repo is used again)
            package_names = [pkg['name'] for pkg in outdated]
            
            # Step 3: Upgrade dependencies
            self.logger.info("Step 3: Upgrading dependencies to latest versions")
            
            success, upgraded = self.executor.upgrade_dependencies(repo_path, package_names)
            
            if not success or not upgraded:
                self.logger.error("Upgrade failed or no packages were changed")
                self._cleanup_repo(repo_path)
                return (False, [], '')
            
            self.logger.info(f"Successfully upgraded {len(upgraded)} packages")
            
            # Step 4: Create Pull Request ONLY (no issue fallback)
            self.logger.info("Step 4: Creating pull request")
            
            pr_url = self.pr_creator.create_branch_and_pr(
                repo_path,
                upgraded,
                base_branch='main'
            )
            
            if not pr_url:
                self.logger.error("Failed to create pull request")
                self._cleanup_repo(repo_path)
                return (False, [], '')
            
            self.logger.info(f"Pull request created: {pr_url}")
            
            # Step 5: Record in memory
            branch_name = self.pr_creator.generate_branch_name()
            upgraded_names = [pkg['name'] for pkg in upgraded]
            self.memory.record_upgrade(branch_name, upgraded_names, pr_url)
            self.memory.update_last_check_time()
            
            # Step 6: Post to Moltbook (if configured)
            repo_url = self.config.get('github', {}).get('repo_url', '')
            self.moltbook_poster.post_upgrade(repo_url, upgraded, pr_url)
            
            self.logger.info("Cycle complete!")
            self._cleanup_repo(repo_path)
            
            # Return more info: (success, upgraded_packages, pr_url)
            return (True, upgraded_names, pr_url)
            
        except Exception as e:
            self.logger.error(f"Error during cycle: {e}")
            self._cleanup_repo(repo_path)
            return (False, [], '')
    
    def run(self):
        """
        Run the main loop.
        
        This runs cycles continuously based on the configured interval.
        """
        self.running = True
        
        # Get check interval from config
        check_interval = self.config.get('agent', {}).get('check_interval', 3600)
        
        self.logger.info(f"Starting main loop (check every {check_interval} seconds)")
        
        # Handle Ctrl+C gracefully
        def signal_handler(sig, frame):
            print("\n\nReceived interrupt signal, shutting down...")
            self.logger.info("Shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Main loop
        cycles = 0
        while self.running:
            cycles += 1
            self.logger.info(f"\n=== Cycle {cycles} ===")
            
            try:
                # Run one cycle
                did_work = self.run_cycle()
                
                if did_work:
                    self.logger.info("Work completed in this cycle")
                else:
                    self.logger.info("No work done in this cycle")
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
            
            # Check if we should run again
            if self.args and self.args.once:
                self.logger.info("Running in --once mode, exiting")
                break
            
            # Wait before next cycle
            self.logger.info(f"Waiting {check_interval} seconds before next check...")
            time.sleep(check_interval)
        
        self.logger.info("OpenClaw Guardian stopped")
        print("OpenClaw Guardian stopped")


# ============================================================================
# COMMAND-LINE ARGUMENT PARSING
# ============================================================================

def parse_arguments():
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments object
    
    Supported arguments:
        --once: Run one cycle only (for testing)
        --config: Custom config file path
        --verbose: Enable verbose (debug) logging
    """
    parser = argparse.ArgumentParser(
        description='OpenClaw Guardian - Automated GitHub Dependency Updater',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run continuously
  python main.py --once             # Run once for testing
  python main.py --verbose          # Run with debug logging
  python main.py --config my.yaml   # Use custom config file
        """
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run one cycle only (for testing)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose (debug) logging'
    )
    
    return parser.parse_args()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    Main entry point for OpenClaw Guardian.
    
    This:
    1. Parses command-line arguments
    2. Creates the Guardian instance
    3. Runs the main loop
    """
    # Print welcome message
    print("=" * 60)
    print("  OpenClaw Guardian - Automated Dependency Updater")
    print("=" * 60)
    print()
    
    # Parse arguments
    args = parse_arguments()
    
    # Show configuration info
    print(f"Config file: {args.config}")
    print(f"Run mode: {'Once' if args.once else 'Continuous'}")
    print(f"Log level: {'DEBUG' if args.verbose else 'INFO'}")
    print()
    
    try:
        # Create and run the guardian
        guardian = OpenClawGuardian(args)
        guardian.run()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
