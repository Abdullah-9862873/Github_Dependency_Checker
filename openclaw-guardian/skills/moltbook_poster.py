"""
Moltbook Poster - Posts upgrade notifications to Moltbook

This module handles posting upgrade notifications to the Moltbook API,
a social network for AI agents.
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime


class MoltbookPoster:
    """Handles posting upgrade notifications to Moltbook."""
    
    BASE_URL = "https://www.moltbook.com/api/v1"
    DEFAULT_MOLT_NAME = "github-upgrades"
    
    def __init__(self, config: Dict, logger):
        """
        Initialize the Moltbook poster.
        
        Args:
            config: Configuration dictionary containing moltbook settings
            logger: Logger instance for logging messages
        """
        self.config = config
        self.logger = logger
        self.api_key = config.get('moltbook', {}).get('api_key', '')
        self.molt_name = config.get('moltbook', {}).get('molt_name', self.DEFAULT_MOLT_NAME)
        self.enabled = bool(self.api_key)
        self._submolt_created = False
    
    def _get_repo_name(self, repo_url: str) -> str:
        """Extract repo name from URL."""
        if repo_url.endswith('/'):
            repo_url = repo_url.rstrip('/')
        parts = repo_url.rsplit('/', 1)
        return parts[-1] if parts else repo_url
    
    def _get_repo_owner(self, repo_url: str) -> str:
        """Extract repo owner from URL."""
        if repo_url.endswith('/'):
            repo_url = repo_url.rstrip('/')
        parts = repo_url.rsplit('/', 2)
        return parts[-2] if len(parts) >= 2 else ''
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _submolt_exists(self, molt_name: str) -> bool:
        """Check if a submolt already exists."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/submolts/{molt_name}",
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                self.logger.warning(f"Could not check submolt existence: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Error checking submolt existence: {e}")
            return False
    
    def _create_submolt(self, molt_name: str) -> bool:
        """Create a new submolt if it doesn't exist."""
        if self._submolt_created:
            return True
        
        payload = {
            "name": molt_name,
            "display_name": molt_name.replace('-', ' ').replace('_', ' ').title(),
            "description": f"Automated dependency upgrades for GitHub repositories"
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/submolts",
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code in (200, 201):
                self.logger.info(f"Created new submolt: {molt_name}")
                self._submolt_created = True
                return True
            elif response.status_code == 400:
                error_msg = response.json().get('message', '')
                if 'already exists' in error_msg.lower():
                    self.logger.info(f"Submolt {molt_name} already exists")
                    self._submolt_created = True
                    return True
                self.logger.error(f"Failed to create submolt: {error_msg}")
                return False
            else:
                self.logger.error(f"Failed to create submolt: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error creating submolt: {e}")
            return False
    
    def _ensure_submolt(self) -> bool:
        """Ensure submolt exists, create if needed."""
        if self._submolt_created:
            return True
        
        if self._submolt_exists(self.molt_name):
            self.logger.info(f"Submolt '{self.molt_name}' already exists")
            self._submolt_created = True
            return True
        
        self.logger.info(f"Submolt '{self.molt_name}' not found, creating it...")
        return self._create_submolt(self.molt_name)
    
    def _format_upgrade_message(self, upgraded: List[Dict], pr_url: str) -> str:
        """Format the upgrade details as a message."""
        lines = [f"Upgraded {len(upgraded)} package(s):"]
        
        for pkg in upgraded:
            name = pkg.get('name', 'unknown')
            old_version = pkg.get('old_version', '?')
            new_version = pkg.get('new_version', '?')
            lines.append(f"• {name}: {old_version} → {new_version}")
        
        lines.append(f"\nPR: {pr_url}")
        return '\n'.join(lines)
    
    def post_upgrade(self, repo_url: str, upgraded: List[Dict], pr_url: str) -> bool:
        """
        Post upgrade notification to Moltbook.
        
        Args:
            repo_url: GitHub repository URL
            upgraded: List of upgraded packages with name, old_version, new_version
            pr_url: URL of the created pull request
            
        Returns:
            bool: True if post was successful, False otherwise
        """
        if not self.enabled:
            self.logger.info("Moltbook posting disabled - no API key configured")
            return False
        
        if not self.api_key:
            self.logger.warning("Moltbook API key is empty")
            return False
        
        if not self._ensure_submolt():
            self.logger.error(f"Could not ensure submolt '{self.molt_name}' exists")
            return False
        
        owner = self._get_repo_owner(repo_url)
        repo_name = self._get_repo_name(repo_url)
        
        title = f"✅ Dependency Upgrade: {owner}/{repo_name}"
        content = self._format_upgrade_message(upgraded, pr_url)
        
        payload = {
            "submolt": self.molt_name,
            "title": title,
            "content": content
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/posts",
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code == 201:
                self.logger.info(f"Successfully posted upgrade to Moltbook: {title}")
                return True
            elif response.status_code == 401:
                self.logger.error("Moltbook API authentication failed - check API key")
                return False
            elif response.status_code == 429:
                self.logger.warning("Moltbook API rate limit exceeded")
                return False
            elif response.status_code == 404:
                self.logger.warning(f"Submolt '{self.molt_name}' not found, trying to create it...")
                if self._create_submolt(self.molt_name):
                    response = requests.post(
                        f"{self.BASE_URL}/posts",
                        json=payload,
                        headers=self._get_headers(),
                        timeout=30
                    )
                    if response.status_code == 201:
                        self.logger.info(f"Successfully posted upgrade to Moltbook: {title}")
                        return True
                return False
            else:
                self.logger.error(f"Moltbook API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error("Moltbook API request timed out")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Moltbook API request failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error posting to Moltbook: {e}")
            return False
