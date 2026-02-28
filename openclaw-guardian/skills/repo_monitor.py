"""
Repository Monitor Skill - Handles Git clone/pull operations

This module handles interacting with Git repositories:
- Cloning repositories from GitHub
- Pulling latest changes
- Checking if the working directory is clean
- Managing Git authentication

Think of this as the "Git manager" for our agent.

Beginner Python Notes:
- subprocess: Built-in library for running external commands
- urllib: Built-in library for parsing URLs
- pathlib: For file path operations
- os: For file/directory operations
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in Python library for file operations
# We use it to check if directories exist, create paths, etc.

import subprocess
# subprocess: Built-in library for running external programs
# We use it to run git commands
# subprocess.run() executes a command and waits for it to finish

from pathlib import Path
# pathlib: Built-in library for working with paths
# Path is cleaner than raw strings for file operations

from urllib.parse import urlparse
# urllib.parse: Built-in library for parsing URLs
# urlparse() breaks a URL into parts (scheme, netloc, path, etc.)
# Example: urlparse("https://github.com/user/repo")
#   -> scheme="https", netloc="github.com", path="/user/repo"

from typing import Optional, Tuple
# typing: Library for type hints
# Optional: Can be the type or None
# Tuple: Fixed-size collection of values

import sys
# sys: Built-in Python library for system operations
# sys.path is used to add directories to Python's import search path


# ============================================================================
# REPO MONITOR CLASS - Handles Git operations
# ============================================================================

class RepoMonitor:
    """
    A class that manages Git repository operations.
    
    This is responsible for:
    1. Cloning repositories from GitHub
    2. Pulling the latest changes
    3. Checking if there are uncommitted changes
    4. Handling Git authentication
    
    The class uses GitPython or direct git commands to interact with Git.
    
    Attributes:
        config: Configuration dictionary with paths and settings
        logger: Logger instance for logging messages
        working_dir: Directory where repositories are stored
    """
    
    def __init__(self, config: dict, logger):
        """
        Initialize the RepoMonitor.
        
        Args:
            config: Configuration dictionary (from config_loader)
            logger: Logger instance for logging
        
        Example:
            from utils.logger import get_logger
            from config.config_loader import load_config
            
            logger = get_logger()
            config = load_config()
            monitor = RepoMonitor(config, logger)
        """
        self.config = config
        self.logger = logger
        
        # Get the working directory from config
        # This is where we'll clone repositories
        # Default to './repos' if not specified
        paths_config = config.get('paths', {})
        self.working_dir = paths_config.get('working_directory', './repos')
        
        # Convert to absolute path to avoid issues with relative paths
        self.working_dir = os.path.abspath(self.working_dir)
        
        # Create the working directory if it doesn't exist
        # exist_ok=True means don't error if it already exists
        os.makedirs(self.working_dir, exist_ok=True)
        
        if self.logger:
            self.logger.info(f"RepoMonitor initialized. Working directory: {self.working_dir}")

    def get_repo_name(self, repo_url: str) -> str:
        """
        Extract the repository name from a GitHub URL.
        
        The repository name is the last part of the URL, without .git
        
        Args:
            repo_url: The GitHub repository URL
        
        Returns:
            The repository name
        
        Example:
            get_repo_name("https://github.com/user/my-project.git")
            # Returns: "my-project"
            
            get_repo_name("https://github.com/user/my-project")
            # Returns: "my-project"
        """
        # Parse the URL into parts
        parsed = urlparse(repo_url)
        
        # Get the path part (e.g., "/user/my-project.git")
        # .rstrip('/') removes trailing slashes
        # .split('/') breaks it into ["", "user", "my-project.git"]
        # [-1] gets the last element: "my-project.git"
        # .replace('.git', '') removes the .git extension
        repo_name = parsed.path.rstrip('/').split('/')[-1].replace('.git', '')
        
        return repo_name

    def get_repo_path(self, repo_url: str) -> str:
        """
        Get the full local path where a repository should be stored.
        
        Args:
            repo_url: The GitHub repository URL
        
        Returns:
            Full path to where the repository will be stored locally
        
        Example:
            get_repo_path("https://github.com/user/my-project")
            # Returns: "./repos/my-project"
        """
        # Get the repository name
        repo_name = self.get_repo_name(repo_url)
        
        # Combine with working directory
        repo_path = os.path.join(self.working_dir, repo_name)
        
        return repo_path

    def _run_git_command(
        self, 
        args: list, 
        cwd: str, 
        check: bool = True
    ) -> Tuple[bool, str]:
        """
        Run a git command and return the result.
        
        This is a helper function that runs git commands safely.
        
        Args:
            args: List of command arguments (e.g., ['git', 'clone', 'url', 'path'])
            cwd: Current working directory for the command
            check: Whether to raise exception on command failure
        
        Returns:
            Tuple of (success: bool, output: str)
        
        Example:
            success, output = self._run_git_command(
                ['git', 'status', '--porcelain'],
                cwd='/path/to/repo'
            )
        """
        try:
            # Run the git command
            # capture_output=True: capture both stdout and stderr
            # text=True: return strings instead of bytes
            # check=True: raise CalledProcessError if command fails
            result = subprocess.run(
                args,
                cwd=cwd,
                check=check,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for network operations
            )
            
            # Return success and output
            return True, result.stdout
            
        except subprocess.CalledProcessError as e:
            # Command failed
            error_msg = e.stderr if e.stderr else str(e)
            if self.logger:
                self.logger.error(f"Git command failed: {' '.join(args)}")
                self.logger.error(f"Error: {error_msg}")
            return False, error_msg
            
        except subprocess.TimeoutExpired:
            # Command took too long
            if self.logger:
                self.logger.error(f"Git command timed out: {' '.join(args)}")
            return False, "Command timed out"
            
        except FileNotFoundError:
            # Git is not installed
            if self.logger:
                self.logger.error("Git is not installed or not in PATH")
            return False, "Git not found"

    def clone_repo(self, repo_url: str, token: Optional[str] = None) -> str:
        """
        Clone a GitHub repository if it doesn't exist locally.
        
        If the repository already exists, this will skip cloning
        and just return the path.
        
        Args:
            repo_url: The GitHub repository URL
            token: Optional GitHub Personal Access Token for authentication
        
        Returns:
            Path to the cloned repository
        
        Raises:
            ValueError: If repo_url is empty
            RuntimeError: If cloning fails
        
        Example:
            # Clone with token (for private repos)
            path = monitor.clone_repo(
                "https://github.com/user/repo",
                "ghp_token..."
            )
            
            # Clone without token (for public repos)
            path = monitor.clone_repo("https://github.com/user/repo")
        """
        # Validate input
        if not repo_url:
            raise ValueError("repo_url cannot be empty")

        # Get where this repo should be stored locally
        repo_path = self.get_repo_path(repo_url)

        # ALWAYS delete existing directory before cloning — never reuse a stale clone.
        # 'rd /s /q' is used because .git object files are read-only on Windows and
        # shutil.rmtree raises WinError 5 (Access Denied) on them.
        if os.path.exists(repo_path):
            if self.logger:
                self.logger.info(f"Removing existing clone for fresh reclone: {repo_path}")
            import subprocess as _sp, time as _t, stat as _stat, shutil as _shutil
            try:
                _sp.run(['cmd', '/c', 'rd', '/s', '/q', repo_path],
                        capture_output=True, text=True, timeout=60)
                if os.path.exists(repo_path):
                    # Fallback: chmod then rmtree
                    def _rm_ro(func, path, _):
                        os.chmod(path, _stat.S_IWRITE)
                        func(path)
                    _shutil.rmtree(repo_path, onerror=_rm_ro)
            except Exception as del_err:
                if self.logger:
                    self.logger.warning(f"Could not remove old clone: {del_err}")
        
        if self.logger:
            self.logger.info(f"Cloning repository: {repo_url}")
        
        # Add authentication to URL if token provided
        # This allows cloning private repos
        if token:
            # Replace "https://" with "https://token@"
            # This embeds the token in the URL
            auth_url = repo_url.replace('https://', f'https://{token}@')
        else:
            # No token, use URL as-is (works for public repos)
            auth_url = repo_url
        
        # Run git clone command
        # git clone <url> <directory>
        success, output = self._run_git_command(
            ['git', 'clone', '--quiet', auth_url, repo_path],
            cwd=self.working_dir,
            check=False
        )
        
        if success:
            if self.logger:
                self.logger.info(f"Successfully cloned repository to {repo_path}")
            return repo_path
        else:
            # Cloning failed
            error_msg = f"Failed to clone repository: {output}"
            if self.logger:
                self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def pull_latest(self, repo_path: str) -> bool:
        """
        Pull the latest changes from the remote repository.
        
        This fetches and merges changes from the origin remote.
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            True if successful, False otherwise
        
        Example:
            success = monitor.pull_latest('./repos/my-project')
        """
        # Validate that repo exists
        if not os.path.exists(repo_path):
            if self.logger:
                self.logger.error(f"Repository not found at {repo_path}")
            return False
        
        if self.logger:
            self.logger.info(f"Pulling latest changes for {repo_path}")
        
        # Step 1: Fetch from origin
        # git fetch downloads info about remote branches without merging
        success, output = self._run_git_command(
            ['git', 'fetch', 'origin'],
            cwd=repo_path,
            check=False
        )
        
        if not success:
            if self.logger:
                self.logger.warning(f"Failed to fetch: {output}")
            # Continue anyway - might work with local data
        
        # Step 2: Get the default branch name (main or master)
        branch = self._get_default_branch(repo_path)
        
        # Step 3: Pull the changes
        # git pull origin <branch> fetches and merges in one command
        success, output = self._run_git_command(
            ['git', 'pull', 'origin', branch, '--quiet'],
            cwd=repo_path,
            check=False
        )
        
        if success:
            if self.logger:
                self.logger.info(f"Successfully pulled latest changes from {branch}")
            return True
        else:
            # Pull failed - might be because we're ahead or diverged
            if self.logger:
                self.logger.warning(f"Failed to pull latest: {output}")
                self.logger.info("Repository may have local changes or diverged from remote")
            return False

    def _get_default_branch(self, repo_path: str) -> str:
        """
        Detect what the default branch is (main, master, etc.).
        
        GitHub now uses 'main' as default, but older repos use 'master'.
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            The default branch name (usually 'main' or 'master')
        
        Example:
            branch = monitor._get_default_branch('./repos/my-project')
            # Returns: 'main'
        """
        # Run: git rev-parse --abbrev-ref HEAD
        # This returns the name of the current branch
        success, output = self._run_git_command(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path,
            check=False
        )
        
        if success:
            # Output has trailing newline, .strip() removes it
            return output.strip()
        else:
            # Default to 'main' if detection fails
            if self.logger:
                self.logger.warning("Could not detect default branch, using 'main'")
            return 'main'

    def is_clean_working_directory(self, repo_path: str) -> bool:
        """
        Check if there are uncommitted changes in the repository.
        
        This checks for:
        - Modified files (staged or unstaged)
        - New files (untracked)
        - Stashed changes
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            True if there are no uncommitted changes, False otherwise
        
        Example:
            if monitor.is_clean_working_directory('./repos/my-project'):
                print("Safe to proceed")
            else:
                print("Has uncommitted changes!")
        """
        # Validate repo exists
        if not os.path.exists(repo_path):
            # If repo doesn't exist, it's "clean" (nothing to mess up)
            return True
        
        # Run: git status --porcelain
        # --porcelain gives a simple, machine-readable output
        # Empty output means clean
        success, output = self._run_git_command(
            ['git', 'status', '--porcelain'],
            cwd=repo_path,
            check=False
        )
        
        if not success:
            # Could not run git status
            if self.logger:
                self.logger.warning("Could not check git status")
            return False
        
        # Check if output is empty
        # .strip() removes leading/trailing whitespace
        # If empty after stripping, directory is clean
        is_clean = len(output.strip()) == 0
        
        if self.logger:
            if is_clean:
                self.logger.debug(f"Working directory is clean: {repo_path}")
            else:
                self.logger.debug(f"Working directory has changes: {repo_path}")
        
        return is_clean

    def stash_changes(self, repo_path: str) -> bool:
        """
        Stash any uncommitted changes in the repository.
        
        This saves changes temporarily so we can pull/update without conflicts.
        Later, these changes can be restored with 'git stash pop'.
        
        This is useful when:
        - You want to pull latest but have local changes
        - You want to make sure the upgrade doesn't conflict
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            True if changes were stashed (or none existed), False on error
        
        Example:
            stashed = monitor.stash_changes('./repos/my-project')
        """
        # First check if there are changes
        if not self.is_clean_working_directory(repo_path):
            if self.logger:
                self.logger.info("Stashing local changes")
            
            # Run: git stash --include-untracked
            # --include-untracked also saves new files
            success, output = self._run_git_command(
                ['git', 'stash', '--include-untracked'],
                cwd=repo_path,
                check=False
            )
            
            if success:
                if self.logger:
                    self.logger.info("Changes stashed successfully")
                return True
            else:
                if self.logger:
                    self.logger.error(f"Failed to stash changes: {output}")
                return False
        else:
            # No changes to stash
            if self.logger:
                self.logger.debug("No changes to stash")
            return True

    def get_current_branch(self, repo_path: str) -> Optional[str]:
        """
        Get the name of the currently checked-out branch.
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            Branch name, or None if not a git repository
        
        Example:
            branch = monitor.get_current_branch('./repos/my-project')
            # Returns: 'main'
        """
        success, output = self._run_git_command(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path,
            check=False
        )
        
        if success:
            return output.strip()
        return None

    def checkout_branch(self, repo_path: str, branch_name: str) -> bool:
        """
        Switch to a different branch.
        
        Args:
            repo_path: Path to the local repository
            branch_name: Name of the branch to checkout
        
        Returns:
            True if successful, False otherwise
        
        Example:
            success = monitor.checkout_branch('./repos/my-project', 'main')
        """
        if self.logger:
            self.logger.info(f"Checking out branch: {branch_name}")
        
        success, output = self._run_git_command(
            ['git', 'checkout', branch_name],
            cwd=repo_path,
            check=False
        )
        
        if success:
            if self.logger:
                self.logger.info(f"Switched to branch: {branch_name}")
            return True
        else:
            if self.logger:
                self.logger.error(f"Failed to checkout branch: {output}")
            return False


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get a RepoMonitor
# ============================================================================

def get_repo_monitor(config: dict, logger) -> RepoMonitor:
    """
    Create a RepoMonitor instance.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        A RepoMonitor instance
    
    Example:
        from config.config_loader import load_config
        from utils.logger import get_logger
        
        config = load_config()
        logger = get_logger()
        monitor = get_repo_monitor(config, logger)
    """
    return RepoMonitor(config, logger)


# ============================================================================
# EXAMPLE USAGE - How to use this RepoMonitor
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python repo_monitor.py
    
    It demonstrates how to use the RepoMonitor.
    """
    # Import our modules - add parent directory to path
    # Also change to project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    
    from config.config_loader import load_config
    from utils.logger import get_logger
    
    # Load config and create logger
    try:
        config = load_config()
        logger = get_logger()
        
        # Create RepoMonitor
        monitor = RepoMonitor(config, logger)
        
        # Get repo URL from config
        repo_url = config.get('github', {}).get('repo_url', '')
        token = config.get('github', {}).get('token', '')
        
        if not repo_url:
            print("No repository URL configured!")
        else:
            # Step 1: Clone repository
            print(f"\n=== Cloning Repository ===")
            try:
                repo_path = monitor.clone_repo(repo_url, token)
                print(f"Repository cloned to: {repo_path}")
            except RuntimeError as e:
                print(f"Clone failed: {e}")
                exit(1)
            
            # Step 2: Check if clean
            print(f"\n=== Checking Working Directory ===")
            is_clean = monitor.is_clean_working_directory(repo_path)
            print(f"Working directory clean: {is_clean}")
            
            # Step 3: Stash if needed (for demo)
            if not is_clean:
                print("Stashing changes...")
                monitor.stash_changes(repo_path)
            
            # Step 4: Pull latest
            print(f"\n=== Pulling Latest ===")
            success = monitor.pull_latest(repo_path)
            print(f"Pull success: {success}")
            
            # Step 5: Get current branch
            print(f"\n=== Current Branch ===")
            branch = monitor.get_current_branch(repo_path)
            print(f"Current branch: {branch}")
            
            print("\n=== Done ===")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
