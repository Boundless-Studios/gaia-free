"""Tests for Ollama service management."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import subprocess

class TestOllamaManager:
    """Test Ollama service manager."""
    
    @pytest.fixture
    def ollama_manager(self):
        """Create Ollama manager instance."""
        with patch('subprocess.Popen'):
            from gaia.infra.llm.providers.ollama import OllamaManager
            return OllamaManager()
    
    def test_check_ollama_installed(self, ollama_manager):
        """Test checking if Ollama is installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='Ollama v1.0.0')
            result = ollama_manager.check_ollama_installed()
            assert result is True
            mock_run.assert_called_once_with(
                ["ollama", "--version"],
                capture_output=True, text=True, check=True
            )

    def test_ollama_not_installed(self, ollama_manager):
        """Test when Ollama is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = ollama_manager.check_ollama_installed()
            assert result is False

    def test_start_ollama_service(self, ollama_manager):
        """Test starting Ollama service."""
        with patch('subprocess.run') as mock_run, patch('subprocess.Popen') as mock_popen:
            # Simulate service not running, so Popen is called
            mock_run.side_effect = [subprocess.CalledProcessError(1, 'ollama list'), Mock(returncode=0)]
            mock_process = Mock()
            mock_process.pid = 1234
            mock_popen.return_value = mock_process
            result = ollama_manager.start_ollama_service()
            assert result is True
            mock_popen.assert_called_once()
            assert "ollama" in mock_popen.call_args[0][0]
            assert "serve" in mock_popen.call_args[0][0]

    def test_stop_ollama_service(self, ollama_manager):
        """Test stopping Ollama service."""
        ollama_manager.service_running = True
        ollama_manager.service_pid = 1234
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = ollama_manager.stop_ollama_service()
            assert result is True
            mock_run.assert_any_call(["kill", "1234"], capture_output=True, check=False)

    def test_get_available_models(self, ollama_manager):
        """Test listing available models."""
        ollama_manager.service_running = True
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="MODEL NAME\nllama3.1:8b\nllama3.2:3b\ndeepseek-coder:6.7b\n"
            )
            models = ollama_manager.get_available_models(force_refresh=True)
            assert len(models) == 3
            assert "llama3.1:8b" in models
            assert "llama3.2:3b" in models
            assert "deepseek-coder:6.7b" in models

    def test_download_model_if_needed(self, ollama_manager):
        """Test downloading a model if not available."""
        ollama_manager.service_running = True
        with patch.object(ollama_manager, 'get_available_models') as mock_get:
            mock_get.return_value = ["llama3.1:8b"]
            # Already available
            assert ollama_manager.download_model_if_needed("llama3.1:8b") is True
            # Not available, simulate download
            mock_get.return_value = []
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                assert ollama_manager.download_model_if_needed("llama3.2:3b") is True