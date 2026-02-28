"""
Unit tests for DependencyChecker
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.dependency_checker import DependencyChecker


class TestDependencyChecker:
    """Tests for the DependencyChecker class"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        return {
            'paths': {'working_directory': './repos'},
            'github': {'token': '', 'repo_url': ''}
        }
    
    @pytest.fixture
    def mock_logger(self):
        """Mock logger"""
        class MockLogger:
            def debug(self, msg): pass
            def info(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): pass
        return MockLogger()
    
    def test_parse_outdated_packages(self, mock_config, mock_logger):
        """Test parsing npm outdated output"""
        checker = DependencyChecker(mock_config, mock_logger)
        
        npm_output = {
            "lodash": {
                "current": "4.17.15",
                "wanted": "4.17.21",
                "latest": "4.17.21",
                "dependent": "myproject",
                "location": "/path/to/node_modules/lodash"
            },
            "axios": {
                "current": "0.27.0",
                "wanted": "0.27.2",
                "latest": "1.6.0",
                "dependent": "myproject",
                "location": "/path/to/node_modules/axios"
            }
        }
        
        result = checker.parse_outdated_packages(npm_output)
        
        assert len(result) == 2
        assert result[0]['name'] == 'lodash'
        assert result[0]['current'] == '4.17.15'
        assert result[0]['latest'] == '4.17.21'
        assert result[1]['name'] == 'axios'
        assert result[1]['current'] == '0.27.0'
    
    def test_filter_packages_to_upgrade(self, mock_config, mock_logger):
        """Test filtering packages based on memory"""
        checker = DependencyChecker(mock_config, mock_logger)
        
        outdated_list = [
            {'name': 'lodash', 'current': '4.17.15', 'wanted': '4.17.21', 'latest': '4.17.21'},
            {'name': 'axios', 'current': '0.27.0', 'wanted': '0.27.2', 'latest': '1.6.0'},
            {'name': 'react', 'current': '17.0.1', 'wanted': '17.0.2', 'latest': '18.2.0'}
        ]
        
        # Mock memory that has lodash as recently upgraded
        class MockMemory:
            def get_recently_upgraded_packages(self, days=7):
                return ['lodash']
        
        result = checker.filter_packages_to_upgrade(outdated_list, MockMemory())
        
        # lodash should be filtered out
        assert len(result) == 2
        assert 'lodash' not in [p['name'] for p in result]
        assert 'axios' in [p['name'] for p in result]
        assert 'react' in [p['name'] for p in result]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
