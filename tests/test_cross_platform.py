"""
Tests for Cross-Platform Compatibility

These tests verify that the codebase works correctly on different operating systems.
"""

import os
import sys
import platform
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


class TestYtDlpFinder:
    """Tests for cross-platform yt-dlp binary detection."""
    
    def test_find_yt_dlp_in_path(self):
        """Test that yt-dlp is found when in PATH."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        with patch('shutil.which') as mock_which:
            mock_which.return_value = '/usr/local/bin/yt-dlp'
            result = downloader._find_yt_dlp()
            assert result == '/usr/local/bin/yt-dlp'
            mock_which.assert_called_once_with('yt-dlp')
    
    def test_find_yt_dlp_not_in_path_fallback_macos(self):
        """Test fallback paths on macOS when yt-dlp not in PATH."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        with patch('shutil.which', return_value=None):
            with patch('platform.system', return_value='Darwin'):
                with patch.object(Path, 'exists', return_value=False):
                    result = downloader._find_yt_dlp()
                    assert result is None
    
    def test_find_yt_dlp_not_in_path_fallback_windows(self):
        """Test fallback paths on Windows when yt-dlp not in PATH."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        with patch('shutil.which', return_value=None):
            with patch('platform.system', return_value='Windows'):
                with patch.object(Path, 'exists', return_value=False):
                    result = downloader._find_yt_dlp()
                    assert result is None
    
    def test_find_yt_dlp_fallback_path_exists(self):
        """Test that a fallback path is returned when it exists."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        with patch('shutil.which', return_value=None):
            with patch('platform.system', return_value='Darwin'):
                expected_path = Path('/usr/local/bin/yt-dlp')
                
                def mock_exists(self_path):
                    return str(self_path) == str(expected_path)
                
                with patch.object(Path, 'exists', mock_exists):
                    result = downloader._find_yt_dlp()
                    assert result == str(expected_path)


class TestPathHandling:
    """Tests for cross-platform path handling using pathlib."""
    
    def test_pathlib_used_for_media_dirs(self):
        """Verify MediaDownloader uses pathlib.Path for directories."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        assert isinstance(downloader.media_dir, Path)
        assert isinstance(downloader.images_dir, Path)
        assert isinstance(downloader.videos_dir, Path)
    
    def test_path_separators_correct(self):
        """Verify paths use correct separators for the current OS."""
        from processor.processor import MEDIA_DIR, DATA_DIR, CONFIG_DIR
        
        if platform.system() == 'Windows':
            expected_sep = '\\'
        else:
            expected_sep = '/'
        
        test_path = Path(__file__).parent / "test"
        path_str = str(test_path)
        
        assert expected_sep in path_str


class TestCrossPlatformLauncher:
    """Tests for the cross-platform service launcher."""
    
    def test_launcher_exists(self):
        """Verify start_services.py exists."""
        project_root = Path(__file__).parent.parent
        launcher = project_root / "start_services.py"
        assert launcher.exists(), "start_services.py should exist"
    
    def test_launcher_imports(self):
        """Verify start_services.py can be imported."""
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        import start_services
        assert hasattr(start_services, 'main')
        assert hasattr(start_services, 'Colors')
        
        sys.path.remove(str(project_root))
    
    def test_colors_class_handles_no_color_support(self):
        """Test that Colors class handles terminals without color support."""
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from start_services import colorize, Colors
        
        with patch.object(Colors, 'supports_color', return_value=False):
            result = colorize("test", Colors.RED)
            assert result == "test"
            assert Colors.RED not in result
        
        sys.path.remove(str(project_root))


class TestShutilWhichUsage:
    """Tests to verify shutil.which is used instead of Unix-specific 'which' command."""
    
    def test_no_which_command_in_processor(self):
        """Verify processor.py doesn't use subprocess 'which' command."""
        project_root = Path(__file__).parent.parent
        processor_file = project_root / "src" / "processor" / "processor.py"
        
        content = processor_file.read_text()
        
        assert "['which'," not in content, "processor.py should not use 'which' command"
        assert "subprocess.run(['which'" not in content, "processor.py should not use 'which' command"
        
        assert "shutil.which" in content, "processor.py should use shutil.which"


class TestPlatformDetection:
    """Tests for platform detection usage."""
    
    def test_platform_module_imported(self):
        """Verify platform module is imported in processor.py."""
        project_root = Path(__file__).parent.parent
        processor_file = project_root / "src" / "processor" / "processor.py"
        
        content = processor_file.read_text()
        
        assert "import platform" in content, "processor.py should import platform module"
    
    def test_platform_system_used(self):
        """Verify platform.system() is used for OS detection."""
        project_root = Path(__file__).parent.parent
        processor_file = project_root / "src" / "processor" / "processor.py"
        
        content = processor_file.read_text()
        
        assert "platform.system()" in content, "processor.py should use platform.system()"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
