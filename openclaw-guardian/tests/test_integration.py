"""
Integration tests for OpenClaw Guardian

These tests run the full workflow to ensure all components work together.
"""

import os
import sys
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestIntegration:
    """Integration tests for the full workflow"""
    
    def test_all_imports_work(self):
        """Test that all modules can be imported"""
        from config.config_loader import load_config
        from utils.logger import get_logger
        from skills.memory_manager import get_memory_manager
        from skills.repo_monitor import get_repo_monitor
        from skills.dependency_checker import get_dependency_checker
        from skills.upgrade_executor import get_upgrade_executor
        from skills.pr_creator import get_pr_creator
        from skills.moltbook_poster import get_moltbook_poster
        
        # If we get here, all imports worked
        assert True
    
    def test_config_loading(self):
        """Test that config can be loaded"""
        from config.config_loader import load_config
        
        config = load_config('config.yaml')
        
        assert config is not None
        assert 'github' in config
        assert 'moltbook' in config
        assert 'agent' in config
        assert 'paths' in config
    
    def test_logger_creation(self):
        """Test that logger can be created"""
        from utils.logger import get_logger
        
        logger = get_logger()
        
        assert logger is not None
        
        # Test logging methods
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")
    
    def test_memory_manager_creation(self):
        """Test that memory manager can be created"""
        from utils.logger import get_logger
        from skills.memory_manager import get_memory_manager
        
        logger = get_logger()
        memory = get_memory_manager('test_memory.json', logger)
        
        assert memory is not None
        
        # Cleanup
        if os.path.exists('test_memory.json'):
            os.remove('test_memory.json')
    
    def test_pr_creator_generates_branch_name(self):
        """Test that PR creator can generate branch names"""
        from config.config_loader import load_config
        from utils.logger import get_logger
        from skills.pr_creator import get_pr_creator
        
        config = load_config('config.yaml')
        logger = get_logger()
        pr = get_pr_creator(config, logger)
        
        branch_name = pr.generate_branch_name()
        
        assert branch_name is not None
        assert branch_name.startswith('auto/dependency-update-')
    
    def test_moltbook_poster_message_formatting(self):
        """Test that Moltbook poster formats messages correctly"""
        from config.config_loader import load_config
        from utils.logger import get_logger
        from skills.moltbook_poster import MoltbookPoster, EventType
        
        config = load_config('config.yaml')
        logger = get_logger()
        poster = MoltbookPoster(config, logger)
        
        # Test message formatting
        msg = poster.format_progress_message(
            EventType.STARTED,
            {'repo': 'test-repo'}
        )
        
        assert 'test-repo' in msg
        assert 'STARTED' in msg


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
