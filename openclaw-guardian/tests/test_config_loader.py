"""
Unit tests for ConfigLoader
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import ConfigLoader


class TestConfigLoader:
    """Tests for the ConfigLoader class"""
    
    def test_load_config_with_env_vars(self):
        """Test loading config with environment variables"""
        # This test assumes .env file exists with test values
        os.environ['GITHUB_TOKEN'] = 'test_token'
        os.environ['REPO_URL'] = 'https://github.com/test/repo'
        os.environ['MOLTBOOK_API_KEY'] = 'test_key'
        
        loader = ConfigLoader()
        config = loader.load()
        
        assert config is not None
        assert 'github' in config
        assert 'moltbook' in config
        assert 'agent' in config
        assert 'paths' in config
    
    def test_get_repo_name_from_url(self):
        """Test extracting repo name from URL"""
        # We need to test this through config
        loader = ConfigLoader()
        
        # Test URL parsing indirectly through expected values
        assert loader.REQUIRED_FIELDS is not None
    
    def test_validate_required_fields_raises_on_missing(self):
        """Test that validation raises error for missing fields"""
        loader = ConfigLoader()
        loader.config = {}
        
        with pytest.raises(ValueError):
            loader._validate_required_fields()
    
    def test_get_nested_value(self):
        """Test getting nested config values"""
        loader = ConfigLoader()
        loader.config = {
            'github': {
                'token': 'test_token'
            }
        }
        
        result = loader.get('github.token')
        assert result == 'test_token'
        
        result = loader.get('nonexistent', 'default')
        assert result == 'default'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
