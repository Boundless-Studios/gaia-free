"""Tests for image artifact store environment detection and path generation."""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from gaia.infra.image.image_artifact_store import ImageArtifactStore


class TestEnvironmentDetection:
    """Test that environment detection correctly identifies production vs development."""

    def test_production_env_via_env_variable(self):
        """Verify ENV=prod is detected as production."""
        with patch.dict(os.environ, {'ENV': 'prod'}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_production_env_via_environment_name(self):
        """Verify ENVIRONMENT_NAME=prod is detected as production."""
        with patch.dict(os.environ, {'ENVIRONMENT_NAME': 'prod'}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_staging_env_via_env_variable(self):
        """Verify ENV=stg is detected as production (not development)."""
        with patch.dict(os.environ, {'ENV': 'stg'}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_staging_env_via_environment_name(self):
        """Verify ENVIRONMENT_NAME=stg is detected as production (not development)."""
        with patch.dict(os.environ, {'ENVIRONMENT_NAME': 'stg'}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_development_env_via_environment_variable(self):
        """Verify ENVIRONMENT=development is detected as development."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is True

    def test_production_takes_precedence_over_development(self):
        """Verify production indicators take precedence."""
        with patch.dict(os.environ, {
            'ENV': 'prod',
            'ENVIRONMENT': 'development'
        }, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_default_to_production_when_no_env_set(self):
        """Verify defaults to production (False) when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            store = ImageArtifactStore()
            assert store._is_dev_env() is False

    def test_case_insensitive_detection(self):
        """Verify environment detection is case-insensitive."""
        test_cases = [
            ({'ENV': 'PROD'}, False),
            ({'ENV': 'Prod'}, False),
            ({'ENVIRONMENT_NAME': 'PRODUCTION'}, False),
            ({'ENVIRONMENT': 'DEVELOPMENT'}, True),
            ({'ENVIRONMENT': 'Development'}, True),
        ]
        for env_vars, expected_is_dev in test_cases:
            with patch.dict(os.environ, env_vars, clear=True):
                store = ImageArtifactStore()
                assert store._is_dev_env() is expected_is_dev, \
                    f"Failed for env_vars={env_vars}, expected is_dev={expected_is_dev}"


class TestPathGeneration:
    """Test that paths are generated correctly for production vs development."""

    def test_production_path_no_hostname(self):
        """Verify production paths don't include hostname prefix."""
        with patch.dict(os.environ, {'ENV': 'prod'}, clear=True):
            store = ImageArtifactStore()
            path = store._blob_path('campaign_104', 'portrait_123.png', 'portrait')

            # Should NOT contain hostname
            assert 'localhost' not in path
            assert path == 'media/images/campaign_104/portraits/portrait_123.png'

    def test_development_path_includes_hostname(self):
        """Verify development paths include hostname prefix."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            with patch('socket.gethostname', return_value='dev-machine'):
                store = ImageArtifactStore()
                path = store._blob_path('campaign_104', 'portrait_123.png', 'portrait')

                # Should contain hostname
                assert 'dev-machine' in path
                assert path == 'media/images/dev-machine/campaign_104/portraits/portrait_123.png'

    def test_staging_path_no_hostname(self):
        """Verify staging paths don't include hostname prefix."""
        with patch.dict(os.environ, {'ENV': 'stg'}, clear=True):
            store = ImageArtifactStore()
            path = store._blob_path('campaign_104', 'scene_456.png', 'scene')

            # Should NOT contain hostname
            assert 'localhost' not in path
            assert path == 'media/images/campaign_104/scenes/scene_456.png'

    def test_path_different_image_types(self):
        """Verify different image types generate correct directory names."""
        with patch.dict(os.environ, {'ENV': 'prod'}, clear=True):
            store = ImageArtifactStore()

            test_cases = [
                ('portrait', 'portraits'),
                ('scene', 'scenes'),
                ('moment', 'moments'),
                ('character', 'characters'),
            ]

            for image_type, expected_dir in test_cases:
                path = store._blob_path('campaign_99', 'image.png', image_type)
                assert expected_dir in path
                assert path == f'media/images/campaign_99/{expected_dir}/image.png'


class TestBackwardCompatibilityFallback:
    """Test that hostname-prefixed paths are tried as fallback."""

    def test_reads_hostname_prefixed_images_as_fallback(self):
        """Verify read_artifact_bytes tries hostname-prefixed path as fallback."""
        with patch.dict(os.environ, {'ENV': 'prod'}, clear=True):
            store = ImageArtifactStore()
            store._bucket = MagicMock()

            # Mock blob existence checks
            # New path doesn't exist, legacy doesn't exist, but hostname-prefixed exists
            new_blob = MagicMock()
            new_blob.exists.return_value = False

            legacy_blob = MagicMock()
            legacy_blob.exists.return_value = False

            hostname_blob = MagicMock()
            hostname_blob.exists.return_value = True
            hostname_blob.download_as_bytes.return_value = b'image_data'

            def mock_blob(path):
                if 'localhost' in path:
                    return hostname_blob
                elif 'campaign_104/media' in path:
                    return legacy_blob
                else:
                    return new_blob

            store._bucket.blob.side_effect = mock_blob

            # Try to read an image
            with patch('socket.gethostname', return_value='localhost'):
                result = store.read_artifact_bytes('campaign_104', 'portrait_123.png')

            # Should have tried new path, then hostname-prefixed path, and succeeded with hostname-prefixed
            assert result == b'image_data'
            assert store._bucket.blob.call_count >= 2  # new, then hostname-prefixed (found)

    def test_hostname_normalization(self):
        """Verify hostname is normalized (lowercase, replace dots and underscores)."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            test_cases = [
                ('Dev-Machine.local', 'dev-machine-local'),
                ('localhost', 'localhost'),
                ('my_server.example.com', 'my-server-example-com'),
            ]

            for hostname, expected_normalized in test_cases:
                with patch('socket.gethostname', return_value=hostname):
                    store = ImageArtifactStore()
                    path = store._blob_path('campaign_1', 'img.png', 'portrait')
                    assert expected_normalized in path
