"""
PR Creator Skill - Creates Git branches and pull requests

This module handles creating Git branches, committing changes,
and creating GitHub Pull Requests via the GitHub API.

Think of this as the "git manager" - it handles all the Git operations
needed to submit changes back to GitHub.

Beginner Python Notes:
- subprocess: For running git commands
- requests: For making HTTP API calls to GitHub
- datetime: For timestamps
- typing: For type hints
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import os
# os: Built-in library for file operations
# We use it to check paths and work with files

import subprocess
# subprocess: Built-in library for running external programs
# We use it to run git commands

import requests
# requests: Third-party library for HTTP requests
# We use it to call the GitHub API

from typing import List, Dict, Any, Optional, Tuple
# typing: Library for type hints

from datetime import datetime
# datetime: Built-in library for dates and times
# We use it for timestamps in branch names

import time
# time: Built-in library for time-related functions

import sys
# sys: Built-in library for system operations


# ============================================================================
# PR CREATOR CLASS - Creates branches and pull requests
# ============================================================================

class PRCreator:
    """
    A class that handles creating Git branches and GitHub Pull Requests.
    
    This class:
    1. Creates a new branch from the default branch
    2. Commits the changes (package.json, package-lock.json)
    3. Pushes the branch to GitHub
    4. Creates a Pull Request via GitHub API
    
    Attributes:
        config: Configuration dictionary
        logger: Logger instance for logging messages
    """
    
    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the PRCreator.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        
        Example:
            from utils.logger import get_logger
            from config.config_loader import load_config
            
            logger = get_logger()
            config = load_config()
            pr = PRCreator(config, logger)
        """
        self.config = config
        self.logger = logger
        
        # Get GitHub settings from config
        self.github_token = config.get('github', {}).get('token', '')
        self.repo_url = config.get('github', {}).get('repo_url', '')
        self.branch_prefix = config.get('agent', {}).get('branch_prefix', 'auto/dependency-update')

    def _get_repo_info(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract owner and repo name from the GitHub URL.
        
        GitHub URLs can be in formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        
        Returns:
            Tuple of (owner, repo_name) or (None, None) on error
        
        Example:
            owner, repo = self._get_repo_info()
            # owner = "abdullahadm9862873-oss"
            # repo = "TestingDependency1"
        """
        if not self.repo_url:
            if self.logger:
                self.logger.error("No repository URL configured")
            return None, None
        
        # Remove .git suffix if present
        url = self.repo_url.rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        
        # Split by '/' and get last two parts
        parts = url.split('/')
        
        if len(parts) < 2:
            if self.logger:
                self.logger.error(f"Invalid repository URL: {self.repo_url}")
            return None, None
        
        # Last part is repo name, second-to-last is owner
        repo_name = parts[-1]
        owner = parts[-2]
        
        return owner, repo_name

    def generate_branch_name(self) -> str:
        """
        Generate a unique branch name for the upgrade.
        
        The branch name format is: auto/dependency-update-{timestamp}
        Example: auto/dependency-update-1705312200
        
        Returns:
            A unique branch name with timestamp
        
        Example:
            branch = self.generate_branch_name()
            # Returns: "auto/dependency-update-1706390400"
        """
        # Get current timestamp
        timestamp = int(time.time())
        
        # Create branch name with prefix and timestamp
        branch_name = f"{self.branch_prefix}-{timestamp}"
        
        return branch_name

    def create_branch(
        self, 
        repo_path: str, 
        branch_name: str
    ) -> bool:
        """
        Create a new Git branch from the current HEAD.
        
        This:
        1. Gets the current commit SHA
        2. Creates a new branch at that commit
        
        Args:
            repo_path: Path to the local repository
            branch_name: Name of the branch to create
        
        Returns:
            True if successful, False otherwise
        
        Example:
            success = pr.create_branch('./repos/my-project', 'auto/dep-update-123')
        """
        if self.logger:
            self.logger.info(f"Creating branch: {branch_name}")
        
        try:
            # Step 1: Get the current commit SHA
            # git rev-parse HEAD gives us the current commit
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error("Failed to get current commit")
                return False
            
            commit_sha = result.stdout.strip()
            
            if self.logger:
                self.logger.debug(f"Current commit: {commit_sha}")
            
            # Step 2: Create the branch
            # git branch <name> <commit> creates a branch at the given commit
            result = subprocess.run(
                ['git', 'branch', branch_name, commit_sha],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"Failed to create branch: {result.stderr}")
                return False
            
            # Step 3: Switch to the new branch
            # git checkout <name> switches to the branch
            result = subprocess.run(
                ['git', 'checkout', branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"Failed to checkout branch: {result.stderr}")
                return False
            
            if self.logger:
                self.logger.info(f"Successfully created and checked out branch: {branch_name}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error creating branch: {e}")
            return False

    def commit_changes(
        self, 
        repo_path: str, 
        packages: List[Dict[str, Any]],
        message: Optional[str] = None
    ) -> bool:
        """
        Stage and commit the changes (package.json and package-lock.json).
        
        This:
        1. Adds package.json and package-lock.json to staging
        2. Creates a commit with a descriptive message
        
        Args:
            repo_path: Path to the local repository
            packages: List of packages that were upgraded
            message: Optional custom commit message
        
        Returns:
            True if successful, False otherwise
        
        Example:
            upgraded = [
                {'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'},
                {'name': 'axios', 'old': '0.27.0', 'new': '1.0.0'}
            ]
            success = pr.commit_changes('./repos/my-project', upgraded)
        """
        if self.logger:
            self.logger.info("Committing changes")
        
        # Generate commit message
        if message is None:
            message = self._generate_commit_message(packages)
        
        try:
            # Step 1: Add package.json
            result = subprocess.run(
                ['git', 'add', 'package.json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.warning(f"Could not add package.json: {result.stderr}")
            
            # Step 2: Add package-lock.json (if exists)
            lock_file = os.path.join(repo_path, 'package-lock.json')
            if os.path.exists(lock_file):
                result = subprocess.run(
                    ['git', 'add', 'package-lock.json'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    shell=True
                )
                
                if result.returncode != 0:
                    if self.logger:
                        self.logger.warning(f"Could not add package-lock.json: {result.stderr}")
            
            # Step 3: Check what files are staged
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            staged_files = result.stdout.strip()
            
            if not staged_files:
                if self.logger:
                    self.logger.warning("No files to commit")
                return False
            
            if self.logger:
                self.logger.info(f"Staged files: {staged_files}")
            
            # Step 3b: Ensure git user identity is set (required for committing)
            # Set global config to ensure it persists across repo clones
            subprocess.run(
                ['git', 'config', '--global', 'user.email', 'openclaw-guardian@auto.bot'],
                capture_output=True, text=True, shell=True, check=False
            )
            subprocess.run(
                ['git', 'config', '--global', 'user.name', 'OpenClaw Guardian'],
                capture_output=True, text=True, shell=True, check=False
            )
            
            # Also set local repo config
            subprocess.run(
                ['git', 'config', 'user.email', 'openclaw-guardian@auto.bot'],
                cwd=repo_path, capture_output=True, text=True, shell=True, check=False
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'OpenClaw Guardian'],
                cwd=repo_path, capture_output=True, text=True, shell=True, check=False
            )
            
            # Step 4: Create the commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"Failed to commit: {result.stderr}")
                return False
            
            if self.logger:
                self.logger.info(f"Successfully committed: {message}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error committing changes: {e}")
            return False

    def _generate_commit_message(self, packages: List[Dict[str, Any]]) -> str:
        """
        Generate a descriptive commit message for the upgrade.
        
        Args:
            packages: List of packages that were upgraded
        
        Returns:
            A commit message string
        
        Example:
            packages = [{'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'}]
            message = self._generate_commit_message(packages)
            # Returns: "Auto: Upgrade outdated dependencies\n\n- lodash: 4.17.15 -> 4.17.21\n\nCreated by OpenClaw Guardian"
        """
        if not packages:
            return "Auto: Upgrade outdated dependencies"
        
        # Start with title
        message = "Auto: Upgrade outdated dependencies\n\n"
        
        # Add list of upgraded packages
        message += "Changes:\n"
        for pkg in packages:
            old_ver = pkg.get('old', 'N/A')
            new_ver = pkg.get('new', 'N/A')
            message += f"- {pkg['name']}: {old_ver} -> {new_ver}\n"
        
        # Add footer
        message += f"\nCreated by OpenClaw Guardian on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message

    def push_branch(
        self, 
        repo_path: str, 
        branch_name: str
    ) -> bool:
        """
        Push the branch to GitHub.
        
        This pushes the new branch to the origin remote.
        
        Args:
            repo_path: Path to the local repository
            branch_name: Name of the branch to push
        
        Returns:
            True if successful, False otherwise
        
        Example:
            success = pr.push_branch('./repos/my-project', 'auto/dep-update-123')
        """
        if self.logger:
            self.logger.info(f"Pushing branch: {branch_name}")
        
        try:
            # Build the push command with token for authentication
            # Format: git push https://token@github.com/owner/repo branch
            
            owner, repo_name = self._get_repo_info()
            if not owner or not repo_name:
                if self.logger:
                    self.logger.error("Could not get repo info for push")
                return False
            
            # Use the token for authentication
            remote_url = f"https://{self.github_token}@github.com/{owner}/{repo_name}"
            
            # Set the remote URL temporarily
            result = subprocess.run(
                ['git', 'remote', 'set-url', 'origin', remote_url],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            # Push the branch
            # git push origin <branch> pushes the branch to remote
            result = subprocess.run(
                ['git', 'push', 'origin', branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"Failed to push branch: {result.stderr}")
                return False
            
            if self.logger:
                self.logger.info(f"Successfully pushed branch: {branch_name}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error pushing branch: {e}")
            return False

    def create_pull_request(
        self, 
        branch_name: str, 
        packages: List[Dict[str, Any]],
        base_branch: str = 'main'
    ) -> Optional[str]:
        """
        Create a GitHub Pull Request via the GitHub API.
        
        This uses the GitHub REST API to create a pull request.
        API endpoint: POST /repos/{owner}/{repo}/pulls
        
        Args:
            branch_name: The branch with changes to PR
            packages: List of packages that were upgraded
            base_branch: The branch to merge into (default: main)
        
        Returns:
            The PR URL if successful, None otherwise
        
        Example:
            pr_url = pr.create_pull_request(
                branch_name='auto/dep-update-123',
                packages=[{'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'}]
            )
            # Returns: "https://github.com/owner/repo/pull/5"
        """
        if self.logger:
            self.logger.info("Creating pull request")
        
        # Get repo info
        owner, repo_name = self._get_repo_info()
        if not owner or not repo_name:
            if self.logger:
                self.logger.error("Could not get repo info")
            return None
        
        # GitHub API URL
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls"
        
        # Headers for authentication
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        
        # Generate PR title and body
        title = self._generate_pr_title(packages)
        body = self._generate_pr_body(packages)
        
        # PR data
        pr_data = {
            'title': title,
            'body': body,
            'head': branch_name,
            'base': base_branch
        }
        
        if self.logger:
            self.logger.debug(f"Creating PR with data: {pr_data}")
        
        try:
            # Make the API request
            response = requests.post(
                api_url,
                headers=headers,
                json=pr_data,
                timeout=30
            )
            
            # Check response status
            if response.status_code == 201:
                # Success!
                pr_info = response.json()
                pr_url = pr_info.get('html_url')
                
                if self.logger:
                    self.logger.info(f"Successfully created PR: {pr_url}")
                
                return pr_url
                
            elif response.status_code == 422:
                # Validation failed - probably branch already exists or PR already exists
                error = response.json()
                if self.logger:
                    self.logger.error(f"PR validation failed: {error}")
                return None
                
            else:
                # Other error
                if self.logger:
                    self.logger.error(f"Failed to create PR: {response.status_code}")
                    self.logger.error(f"Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            if self.logger:
                self.logger.error(f"Request error creating PR: {e}")
            return None

    def create_issue(
        self, 
        packages: List[Dict[str, Any]],
        repo_path: str
    ) -> Optional[str]:
        """
        Create a GitHub Issue with upgrade details.
        
        This is an alternative to creating a PR - it creates an issue
        with the exact steps to upgrade dependencies.
        No push access required!
        
        Args:
            packages: List of packages that were upgraded
            repo_path: Path to the local repository (to read package.json)
        
        Returns:
            The Issue URL if successful, None otherwise
        
        Example:
            issue_url = pr.create_issue(
                packages=[{'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'}],
                repo_path='./repos/my-project'
            )
            # Returns: "https://github.com/owner/repo/issues/5"
        """
        if self.logger:
            self.logger.info("Creating GitHub issue instead of PR")
        
        # Get repo info
        owner, repo_name = self._get_repo_info()
        if not owner or not repo_name:
            if self.logger:
                self.logger.error("Could not get repo info")
            return None
        
        # GitHub API URL for issues
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/issues"
        
        # Headers for authentication
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        
        # Generate issue title and body
        title = self._generate_pr_title(packages)
        body = self._generate_issue_body(packages, repo_path)
        
        # Issue data
        issue_data = {
            'title': title,
            'body': body,
            'labels': ['dependencies', 'auto-upgrade']
        }
        
        if self.logger:
            self.logger.debug(f"Creating issue with data: {title}")
        
        try:
            # Make the API request
            response = requests.post(
                api_url,
                headers=headers,
                json=issue_data,
                timeout=30
            )
            
            # Check response status
            if response.status_code == 201:
                # Success!
                issue_info = response.json()
                issue_url = issue_info.get('html_url')
                
                if self.logger:
                    self.logger.info(f"Successfully created issue: {issue_url}")
                
                return issue_url
                
            elif response.status_code == 404:
                # No permission to create issues (read-only repo)
                if self.logger:
                    self.logger.warning("No permission to create issues")
                return None
                
            else:
                if self.logger:
                    self.logger.error(f"Failed to create issue: {response.status_code}")
                    self.logger.error(f"Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            if self.logger:
                self.logger.error(f"Request error creating issue: {e}")
            return None

    def _generate_issue_body(
        self, 
        packages: List[Dict[str, Any]],
        repo_path: str
    ) -> str:
        """
        Generate the body for the GitHub issue with upgrade instructions.
        
        Args:
            packages: List of upgraded packages
            repo_path: Path to read current package.json
        
        Returns:
            Issue body with detailed upgrade instructions
        """
        body = "## Dependency Upgrade Available\n\n"
        body += "I've detected outdated dependencies in this repository and created upgrade instructions for you.\n\n"
        
        body += "### Outdated Packages\n\n"
        
        if packages:
            body += "| Package | Current Version | Latest Version |\n"
            body += "|---------|-----------------|----------------|\n"
            
            for pkg in packages:
                old_ver = pkg.get('old', 'N/A')
                new_ver = pkg.get('new', 'N/A')
                body += f"| {pkg['name']} | {old_ver} | {new_ver} |\n"
        
        body += "\n---\n\n"
        body += "## How to Apply These Updates\n\n"
        body += "```bash\n"
        body += "# Navigate to your project directory\n"
        body += "cd YOUR_PROJECT_PATH\n\n"
        body += "# Update npm dependencies to latest versions\n"
        
        for pkg in packages:
            body += f"npm install {pkg['name']}@latest --save\n"
        
        body += "\n# Or simply run:\n"
        body += "npm install\n\n"
        body += "# After updating, commit the changes\n"
        body += "git add package.json package-lock.json\n"
        body += 'git commit -m "Update dependencies"\n'
        body += "git push\n"
        body += "```\n\n"
        
        body += "---\n"
        body += "*This issue was automatically created by OpenClaw Guardian*\n"
        
        return body

    def _generate_pr_title(self, packages: List[Dict[str, Any]]) -> str:
        """
        Generate a title for the pull request.
        
        Args:
            packages: List of upgraded packages
        
        Returns:
            PR title string
        
        Example:
            title = self._generate_pr_title([{'name': 'lodash'}, {'name': 'axios'}])
            # Returns: "Auto: Upgrade lodash, axios"
        """
        if not packages:
            return "Auto: Upgrade outdated dependencies"
        
        # Get package names
        names = [pkg['name'] for pkg in packages]
        
        if len(names) == 1:
            return f"Auto: Upgrade {names[0]}"
        elif len(names) <= 3:
            return f"Auto: Upgrade {', '.join(names)}"
        else:
            return f"Auto: Upgrade {names[0]} and {len(names)-1} more packages"

    def _generate_pr_body(self, packages: List[Dict[str, Any]]) -> str:
        """
        Generate the body/description for the pull request.
        
        Args:
            packages: List of upgraded packages
        
        Returns:
            PR body string (markdown)
        
        Example:
            body = self._generate_pr_body([...])
            # Returns markdown with package details
        """
        body = "## Summary\n\n"
        body += "This PR upgrades outdated dependencies to their latest versions.\n\n"
        body += "### Upgraded Packages\n\n"
        
        if packages:
            body += "| Package | Old Version | New Version |\n"
            body += "|---------|-------------|-------------|\n"
            
            for pkg in packages:
                old_ver = pkg.get('old', 'N/A')
                new_ver = pkg.get('new', 'N/A')
                body += f"| {pkg['name']} | {old_ver} | {new_ver} |\n"
        else:
            body += "No packages were upgraded in this update.\n"
        
        body += "\n---\n"
        body += f"Created by **OpenClaw Guardian** on "
        body += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return body

    def create_branch_and_pr(
        self, 
        repo_path: str, 
        packages: List[Dict[str, Any]],
        base_branch: str = 'main'
    ) -> Optional[str]:
        """
        Complete workflow: Create branch, commit, push, and create PR.
        
        This is the main method that ties everything together.
        
        Args:
            repo_path: Path to the local repository
            packages: List of packages that were upgraded
            base_branch: The branch to merge into (default: main)
        
        Returns:
            The PR URL if successful, None otherwise
        
        Example:
            pr_url = pr.create_branch_and_pr(
                './repos/my-project',
                [{'name': 'lodash', 'old': '4.17.15', 'new': '4.17.21'}]
            )
            # Returns: "https://github.com/owner/repo/pull/5"
        """
        if self.logger:
            self.logger.info("Starting branch and PR creation workflow")
        
        # Step 1: Generate branch name
        branch_name = self.generate_branch_name()
        
        if self.logger:
            self.logger.info(f"Using branch name: {branch_name}")
        
        # Step 2: Create the branch
        if not self.create_branch(repo_path, branch_name):
            if self.logger:
                self.logger.error("Failed to create branch")
            return None
        
        # Step 3: Commit the changes
        if not self.commit_changes(repo_path, packages):
            if self.logger:
                self.logger.error("Failed to commit changes")
            return None
        
        # Step 4: Push the branch
        if not self.push_branch(repo_path, branch_name):
            if self.logger:
                self.logger.error("Failed to push branch")
            return None
        
        # Step 5: Create the Pull Request
        pr_url = self.create_pull_request(branch_name, packages, base_branch)
        
        if pr_url:
            if self.logger:
                self.logger.info(f"Successfully created PR: {pr_url}")
        else:
            if self.logger:
                self.logger.error("Failed to create pull request")
        
        return pr_url


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get a PRCreator
# ============================================================================

def get_pr_creator(config: Dict[str, Any], logger) -> PRCreator:
    """
    Create a PRCreator instance.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        A PRCreator instance
    
    Example:
        pr = get_pr_creator(config, logger)
    """
    return PRCreator(config, logger)


# ============================================================================
# EXAMPLE USAGE - How to use this PRCreator
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python pr_creator.py
    
    It demonstrates how to use the PRCreator.
    """
    # Import our modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    
    from config.config_loader import load_config
    from utils.logger import get_logger
    from skills.repo_monitor import get_repo_monitor
    
    # Load config and create logger
    try:
        config = load_config()
        logger = get_logger()
        
        # Create PR creator
        pr_creator = PRCreator(config, logger)
        
        # Get repo info
        owner, repo_name = pr_creator._get_repo_info()
        print(f"\n=== Repository Info ===")
        print(f"Owner: {owner}")
        print(f"Repo: {repo_name}")
        
        # Test branch name generation
        print(f"\n=== Branch Name ===")
        branch_name = pr_creator.generate_branch_name()
        print(f"Generated branch: {branch_name}")
        
        # Get repo path
        monitor = get_repo_monitor(config, logger)
        repo_url = config.get('github', {}).get('repo_url', '')
        
        if not repo_url:
            print("No repository URL configured!")
            exit(1)
        
        repo_path = monitor.get_repo_path(repo_url)
        
        print(f"\n=== Testing Branch Creation ===")
        print(f"Repo path: {repo_path}")
        
        # Create a test branch
        test_branch = f"test-branch-{int(time.time())}"
        success = pr_creator.create_branch(repo_path, test_branch)
        print(f"Branch created: {success}")
        
        if success:
            # Try to commit (there might not be changes)
            print(f"\n=== Testing Commit ===")
            # First go back to main
            subprocess.run(
                ['git', 'checkout', 'main'],
                cwd=repo_path,
                shell=True
            )
            
            # Delete test branch
            subprocess.run(
                ['git', 'branch', '-D', test_branch],
                cwd=repo_path,
                shell=True
            )
        
        print("\n=== Done ===")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
