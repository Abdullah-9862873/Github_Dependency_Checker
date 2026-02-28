"""
Unit tests for MemoryManager
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.memory_manager import MemoryManager


class TestMemoryManager:
    """Tests for the MemoryManager class"""
    
    @pytest.fixture
    def temp_memory_file(self):
        """Create a temporary memory file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_create_empty_memory(self, temp_memory_file):
        """Test creating empty memory structure"""
        memory = MemoryManager(temp_memory_file)
        
        assert memory.memory is not None
        assert 'repo_url' in memory.memory
        assert 'last_checked' in memory.memory
        assert 'last_updated' in memory.memory
    
    def test_record_upgrade(self, temp_memory_file):
        """Test recording an upgrade"""
        memory = MemoryManager(temp_memory_file)
        
        result = memory.record_upgrade(
            'auto/test-branch',
            ['lodash', 'axios'],
            'https://github.com/test/repo/pull/1'
        )
        
        assert result is True
        assert len(memory.memory['last_updated']) == 1
        assert memory.memory['last_updated'][0]['branch'] == 'auto/test-branch'
        assert memory.memory['last_updated'][0]['packages'] == ['lodash', 'axios']
        assert memory.memory['successful_upgrades'] == 1
    
    def test_has_been_upgraded(self, temp_memory_file):
        """Test checking if package was upgraded"""
        memory = MemoryManager(temp_memory_file)
        
        # Record an upgrade
        memory.record_upgrade('auto/test-branch', ['lodash'])
        
        # Check if lodash was upgraded
        assert memory.has_been_upgraded('lodash') is True
        
        # Check if react was upgraded
        assert memory.has_been_upgraded('react') is False
    
    def test_get_recently_upgraded_packages(self, temp_memory_file):
        """Test getting recently upgraded packages"""
        memory = MemoryManager(temp_memory_file)
        
        memory.record_upgrade('auto/test-branch', ['lodash', 'axios'])
        
        recent = memory.get_recently_upgraded_packages()
        
        assert 'lodash' in recent
        assert 'axios' in recent
    
    def test_get_stats(self, temp_memory_file):
        """Test getting statistics"""
        memory = MemoryManager(temp_memory_file)
        
        memory.record_upgrade('auto/test-branch', ['lodash'])
        memory.update_last_check_time()
        
        stats = memory.get_stats()
        
        assert stats['total_runs'] == 1
        assert stats['successful_upgrades'] == 1
        assert stats['last_checked'] is not None
    
    def test_update_last_check_time(self, temp_memory_file):
        """Test updating last check time"""
        memory = MemoryManager(temp_memory_file)
        
        assert memory.memory['last_checked'] is None
        
        memory.update_last_check_time()
        
        assert memory.memory['last_checked'] is not None
        assert memory.memory['total_runs'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
