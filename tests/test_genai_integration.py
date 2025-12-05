"""Integration tests for gen-ai asset generation endpoints.

These tests verify that all server endpoints and CLI commands that generate
assets (images, videos) work correctly with the Gemini API.

Tests can be run with: pytest tests/test_genai_integration.py -v
To skip these tests: pytest -m "not genai"

IMPORTANT: These tests require a valid GEMINI_API_KEY environment variable.
Tests will be skipped if the API key is not available.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

import pytest

from triptic.cli import cmd_imgen
from triptic.imgen import get_api_key
from triptic.server import TripticServer, get_content_dir


# Check if API key is available
GEMINI_API_KEY = get_api_key()
skip_without_api_key = pytest.mark.skipif(
    not GEMINI_API_KEY,
    reason="GEMINI_API_KEY not found in environment or .env file"
)


@pytest.fixture
def temp_content_dir(monkeypatch):
    """Create a temporary content directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        content_path = Path(tmpdir) / "content"
        content_path.mkdir()

        # Create assets directory for UUID-based storage
        assets_path = content_path / "assets"
        assets_path.mkdir()

        # Create database path
        db_path = Path(tmpdir) / "triptic.db"

        # Mock the get_content_dir function to return our temp directory
        monkeypatch.setattr("triptic.server.get_content_dir", lambda: content_path)
        monkeypatch.setattr("triptic.cli.get_content_dir", lambda: content_path)

        # Mock storage paths
        monkeypatch.setattr("triptic.storage.get_assets_dir", lambda: assets_path)
        monkeypatch.setattr("triptic.storage.get_db_path", lambda: db_path)
        monkeypatch.setattr("triptic.db.get_db_path", lambda: db_path)

        yield content_path


@pytest.fixture
def test_server(temp_content_dir):
    """Start a test server and stop it after the test."""
    import socket
    import random

    # Find a random available port to avoid conflicts
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]

    server = TripticServer(port=port, host="localhost")
    server.start()

    # Wait for server to be ready
    max_retries = 20
    for i in range(max_retries):
        try:
            conn = HTTPConnection("localhost", port, timeout=1)
            conn.request("GET", "/")
            response = conn.getresponse()
            if response.status == 200:
                conn.close()
                break
        except Exception:
            pass
        time.sleep(0.1)

    yield server, port

    # Ensure server is stopped even if test fails
    try:
        server.stop()
    except Exception:
        pass


class TestCLIImageGeneration:
    """Test CLI image generation commands."""

    @pytest.mark.genai
    @skip_without_api_key
    def test_imgen_command_basic(self, temp_content_dir, monkeypatch):
        """Test basic image generation with 'triptic imgen' command."""
        # Prepare arguments
        from argparse import Namespace
        args = Namespace(
            name="test-image",
            prompt="A simple red circle on a blue background",
            playlist=None
        )

        # Run the command
        result = cmd_imgen(args)

        # Verify command succeeded
        assert result == 0, "imgen command should return 0 on success"

        # Verify images were created
        img_dir = temp_content_dir / "img"
        assert (img_dir / "left" / "test-image.png").exists(), "Left image should be created"
        assert (img_dir / "center" / "test-image.png").exists(), "Center image should be created"
        assert (img_dir / "right" / "test-image.png").exists(), "Right image should be created"

        # Verify prompt file was created
        prompt_file = img_dir / "left" / "test-image.prompt.txt"
        assert prompt_file.exists(), "Prompt file should be created"
        prompt_content = prompt_file.read_text()
        assert "A simple red circle" in prompt_content, "Prompt file should contain the prompt"

    @pytest.mark.genai
    @skip_without_api_key
    def test_imgen_command_with_playlist(self, temp_content_dir, monkeypatch):
        """Test image generation with playlist option."""
        from argparse import Namespace

        # Create playlist directory
        playlist_name = "test-playlist"
        playlist_dir = temp_content_dir / "img" / playlist_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        # Create playlist JSON file
        playlists_dir = temp_content_dir / "playlists"
        playlists_dir.mkdir(parents=True, exist_ok=True)
        playlist_file = playlists_dir / f"{playlist_name}.json"
        playlist_file.write_text(json.dumps({"name": playlist_name, "imagesets": []}))

        args = Namespace(
            name="test-with-playlist",
            prompt="A yellow star on a purple background",
            playlist=playlist_name
        )

        # Run the command
        result = cmd_imgen(args)

        # Verify command succeeded
        assert result == 0, "imgen command should return 0 on success"

        # Verify images were created in the playlist directory
        assert (playlist_dir / "test-with-playlist.left.png").exists()
        assert (playlist_dir / "test-with-playlist.center.png").exists()
        assert (playlist_dir / "test-with-playlist.right.png").exists()


class TestServerImageGeneration:
    """Test server endpoints for image generation."""

    def _create_test_imageset(self, content_dir: Path, name: str) -> dict[str, Path]:
        """Helper to create a test imageset with dummy images.

        Creates images and registers them in the database using the new storage system.
        """
        from PIL import Image
        from triptic import storage, db
        from triptic.server import AssetGroup, AssetVersion
        from datetime import datetime
        import tempfile

        # Create temporary images and store them via the storage system
        asset_group = AssetGroup(id=name)
        paths = {}

        for screen in ["left", "center", "right"]:
            # Create a temporary test image
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img = Image.new('RGB', (1080, 1920), color=(255, 0, 0))
                img.save(tmp.name)
                tmp_path = Path(tmp.name)

                # Store file in the UUID-based storage
                content_uuid = storage.store_file(tmp_path)
                tmp_path.unlink()  # Clean up temp file

                # Get the stored file path
                file_path = storage.get_file_path(content_uuid)
                paths[screen] = file_path

                # Create version for this screen
                version = AssetVersion(
                    content=content_uuid,
                    prompt=f"Test prompt for {name}",
                    timestamp=datetime.now().isoformat()
                )
                getattr(asset_group, screen).add_version(version)

        # Save the asset group to the database
        from triptic.server import save_asset_group
        save_asset_group(asset_group)

        return paths

    @pytest.mark.genai
    @skip_without_api_key
    def test_regenerate_image_endpoint(self, test_server, temp_content_dir):
        """Test the /asset-group/{name}/regenerate/{screen} endpoint."""
        server, port = test_server

        # Create a test imageset
        imageset_name = "test-regen"
        paths = self._create_test_imageset(temp_content_dir, imageset_name)

        # Get the original image modification time
        left_path = paths['left']
        original_mtime = left_path.stat().st_mtime

        # Wait a bit to ensure modification time will be different
        time.sleep(0.1)

        # Call the regenerate endpoint
        conn = HTTPConnection("localhost", port)
        conn.request("POST", f"/asset-group/{imageset_name}/regenerate/left")
        response = conn.getresponse()

        # Verify response
        assert response.status == 200, f"Expected 200, got {response.status}: {response.read().decode()}"

        response_data = json.loads(response.read().decode())
        assert response_data["status"] == "ok"
        assert response_data["regenerated"] == "left"

        # Get the new file path after regeneration (it will have a new UUID)
        from triptic import storage
        new_path = storage.get_asset_file_path_by_group(imageset_name, "left")
        assert new_path, "New image should exist after regeneration"
        assert new_path.exists(), f"New image file should exist at {new_path}"

        # Verify it's a different file (different UUID) or newer modification time
        assert new_path != left_path or new_path.stat().st_mtime > original_mtime, \
            "Image should have been regenerated with new content"

        conn.close()

    @pytest.mark.genai
    @skip_without_api_key
    def test_edit_image_endpoint(self, test_server, temp_content_dir):
        """Test the /asset-group/{name}/edit/{screen} endpoint."""
        server, port = test_server

        # Create a test imageset
        imageset_name = "test-edit"
        paths = self._create_test_imageset(temp_content_dir, imageset_name)

        # Get the original image modification time
        center_path = paths['center']
        original_mtime = center_path.stat().st_mtime

        # Wait a bit to ensure modification time will be different
        time.sleep(0.1)

        # Call the edit endpoint with a new prompt
        conn = HTTPConnection("localhost", port)
        body = json.dumps({"prompt": "Change the background to green"})
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        conn.request("POST", f"/asset-group/{imageset_name}/edit/center", body, headers)
        response = conn.getresponse()

        # Verify response
        assert response.status == 200, f"Expected 200, got {response.status}: {response.read().decode()}"

        response_data = json.loads(response.read().decode())
        assert response_data["status"] == "ok"
        assert response_data["edited"] == "center"

        # Verify the image was edited (modification time changed)
        new_mtime = center_path.stat().st_mtime
        assert new_mtime > original_mtime, "Image should have been edited"

        conn.close()

    @pytest.mark.genai
    @skip_without_api_key
    def test_regenerate_with_context_endpoint(self, test_server, temp_content_dir):
        """Test the /asset-group/{name}/regenerate-with-context/{screen} endpoint."""
        server, port = test_server

        # Create a test imageset
        imageset_name = "test-context"
        paths = self._create_test_imageset(temp_content_dir, imageset_name)

        # Get the original image modification time
        right_path = paths['right']
        original_mtime = right_path.stat().st_mtime

        # Wait a bit to ensure modification time will be different
        time.sleep(0.1)

        # Call the regenerate-with-context endpoint
        conn = HTTPConnection("localhost", port)
        body = json.dumps({"contextScreens": ["left", "center"]})
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        conn.request("POST", f"/asset-group/{imageset_name}/regenerate-with-context/right", body, headers)
        response = conn.getresponse()

        # Verify response
        assert response.status == 200, f"Expected 200, got {response.status}: {response.read().decode()}"

        response_data = json.loads(response.read().decode())
        assert response_data["status"] == "ok"
        assert response_data["regenerated"] == "right"
        assert response_data["with_context"] == ["left", "center"]

        # Verify the image was regenerated (modification time changed)
        new_mtime = right_path.stat().st_mtime
        assert new_mtime > original_mtime, "Image should have been regenerated with context"

        conn.close()

    @pytest.mark.genai
    @pytest.mark.slow
    @skip_without_api_key
    def test_generate_video_endpoint(self, test_server, temp_content_dir):
        """Test the /asset-group/{name}/video/{screen} endpoint.

        Note: This test is marked as 'slow' because video generation can take several minutes.
        Run with: pytest -m "genai and slow"
        """
        server, port = test_server

        # Create a test imageset
        imageset_name = "test-video"
        self._create_test_imageset(temp_content_dir, imageset_name)

        # Call the video generation endpoint
        conn = HTTPConnection("localhost", port)
        conn.request("POST", f"/asset-group/{imageset_name}/video/left")
        response = conn.getresponse()

        # Verify initial response (should be 202 Accepted with job_id)
        assert response.status == 202, f"Expected 202, got {response.status}: {response.read().decode()}"

        response_data = json.loads(response.read().decode())
        assert response_data["status"] == "processing"
        assert "job_id" in response_data

        job_id = response_data["job_id"]

        # Poll the job status endpoint until complete or timeout
        max_wait = 600  # 10 minutes
        poll_interval = 5  # 5 seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            time.sleep(poll_interval)

            conn = HTTPConnection("localhost", port)
            conn.request("GET", f"/video-job/{job_id}")
            response = conn.getresponse()

            assert response.status == 200
            status_data = json.loads(response.read().decode())

            if status_data["status"] == "complete":
                # Verify video file was created
                assert "video_url" in status_data
                video_path = temp_content_dir / "img" / "left" / f"{imageset_name}.mp4"
                assert video_path.exists(), "Video file should be created"
                assert video_path.stat().st_size > 0, "Video file should not be empty"
                conn.close()
                return
            elif status_data["status"] == "error":
                pytest.fail(f"Video generation failed: {status_data.get('error', 'Unknown error')}")

            conn.close()

        pytest.fail("Video generation timed out after 10 minutes")


class TestErrorHandling:
    """Test error handling for gen-ai endpoints."""

    def test_edit_without_prompt(self, test_server, temp_content_dir):
        """Test that editing without a prompt returns 400."""
        server, port = test_server

        # Create a test imageset
        from PIL import Image
        imageset_name = "test-error"
        left_dir = temp_content_dir / "img" / "left"
        left_dir.mkdir(parents=True, exist_ok=True)

        left_path = left_dir / f"{imageset_name}.png"
        img = Image.new('RGB', (1080, 1920), color=(255, 0, 0))
        img.save(left_path)

        # Call edit endpoint without prompt
        conn = HTTPConnection("localhost", port)
        body = json.dumps({})
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        conn.request("POST", f"/asset-group/{imageset_name}/edit/left", body, headers)
        response = conn.getresponse()

        # Should return 400 Bad Request
        assert response.status == 400
        conn.close()

    def test_regenerate_nonexistent_imageset(self, test_server):
        """Test that regenerating a non-existent imageset returns 404."""
        server, port = test_server

        conn = HTTPConnection("localhost", port)
        conn.request("POST", "/asset-group/nonexistent/regenerate/left")
        response = conn.getresponse()

        # Should return 404 Not Found
        assert response.status == 404
        conn.close()

    def test_edit_invalid_screen(self, test_server, temp_content_dir):
        """Test that editing with an invalid screen name returns 400."""
        server, port = test_server

        # Create a test imageset
        from PIL import Image
        imageset_name = "test-invalid"
        left_dir = temp_content_dir / "img" / "left"
        left_dir.mkdir(parents=True, exist_ok=True)

        left_path = left_dir / f"{imageset_name}.png"
        img = Image.new('RGB', (1080, 1920), color=(255, 0, 0))
        img.save(left_path)

        # Call edit endpoint with invalid screen name
        conn = HTTPConnection("localhost", port)
        body = json.dumps({"prompt": "test"})
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        conn.request("POST", f"/asset-group/{imageset_name}/edit/invalid", body, headers)
        response = conn.getresponse()

        # Should return 400 Bad Request
        assert response.status == 400
        conn.close()


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
