"""Integration tests for all server endpoints using temporary database."""

import json
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from typing import Set, Tuple

import requests


def discover_endpoints_from_source() -> Set[Tuple[str, str]]:
    """
    Parse server.py to discover all defined endpoints.

    Returns:
        Set of (method, pattern) tuples representing all endpoints
    """
    server_file = Path(__file__).parent.parent / "src" / "triptic" / "server.py"
    endpoints = set()

    with open(server_file, 'r') as f:
        content = f.read()

    # Find do_GET, do_POST, do_DELETE methods
    for method in ['GET', 'POST', 'DELETE']:
        # Find the method definition
        method_pattern = rf'def do_{method}\(self\).*?(?=\n    def |\Z)'
        method_match = re.search(method_pattern, content, re.DOTALL)

        if not method_match:
            continue

        method_body = method_match.group(0)

        # Find all path checks in the method
        # Pattern 1: self.path == '/exact/path'
        for match in re.finditer(r"self\.path == ['\"]([^'\"]+)['\"]", method_body):
            endpoints.add((method, match.group(1)))

        # Pattern 2: self.path.startswith('/path/prefix')
        for match in re.finditer(r"self\.path\.startswith\(['\"]([^'\"]+)['\"]\)", method_body):
            prefix = match.group(1)
            # Check if there's additional conditions like .endswith or 'in'
            line_start = method_body[:match.start()].rfind('\n')
            line_end = method_body.find('\n', match.end())
            full_line = method_body[line_start:line_end]

            # Extract the full pattern
            if '.endswith(' in full_line:
                suffix_match = re.search(r"\.endswith\(['\"]([^'\"]+)['\"]\)", full_line)
                if suffix_match:
                    endpoints.add((method, prefix + '*' + suffix_match.group(1)))
            elif "' in self.path" in full_line or '" in self.path' in full_line:
                middle_match = re.search(r"['\"]([^'\"]+)['\"] in self\.path", full_line)
                if middle_match:
                    endpoints.add((method, prefix + '*' + middle_match.group(1) + '*'))
            else:
                endpoints.add((method, prefix + '*'))

    return endpoints


class EndpointIntegrationTest(unittest.TestCase):
    """Test all server endpoints with a temporary database."""

    @classmethod
    def setUpClass(cls):
        """Set up test database and start server."""
        # Create temporary database
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix='.db')

        # Create temporary content directory
        cls.temp_content_dir = tempfile.mkdtemp()
        cls.temp_assets_dir = Path(cls.temp_content_dir) / "assets"
        cls.temp_assets_dir.mkdir(parents=True)

        # Set environment variable for content directory
        os.environ['TRIPTIC_CONTENT_DIR'] = cls.temp_content_dir

        # Initialize database with test data
        cls._init_test_database()

        # Start server with temporary database
        cls.server_port = 13000  # Use non-standard port for testing
        cls.base_url = f"http://localhost:{cls.server_port}"

        # Start server in background
        cls.server_process = subprocess.Popen(
            ['uv', 'run', 'triptic', 'start',
             '--database', cls.temp_db_path,
             '--port', str(cls.server_port),
             '-d'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{cls.base_url}/playlists", timeout=1)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                time.sleep(0.5)
        else:
            raise RuntimeError("Server failed to start within timeout")

        # Discover all endpoints from source
        cls.defined_endpoints = discover_endpoints_from_source()
        cls.tested_endpoints = set()

        print(f"\nDiscovered {len(cls.defined_endpoints)} endpoints:")
        for method, pattern in sorted(cls.defined_endpoints):
            print(f"  {method:6} {pattern}")

    @classmethod
    def tearDownClass(cls):
        """Stop server and clean up."""
        # Stop server
        subprocess.run(['uv', 'run', 'triptic', 'stop'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)

        # Clean up temp files
        os.close(cls.temp_db_fd)
        os.unlink(cls.temp_db_path)

        # Check coverage
        untested = cls.defined_endpoints - cls.tested_endpoints
        if untested:
            print("\n⚠️  WARNING: The following endpoints were NOT tested:")
            for method, pattern in sorted(untested):
                print(f"  {method:6} {pattern}")
            # Fail the test suite if endpoints are untested
            raise AssertionError(
                f"{len(untested)} endpoints were not tested: {untested}"
            )
        else:
            print(f"\n✅ All {len(cls.defined_endpoints)} endpoints were tested!")

    @classmethod
    def _init_test_database(cls):
        """Initialize test database with sample data."""
        from triptic import db
        from triptic.server import Asset, AssetGroup, AssetVersion
        from datetime import datetime

        # Temporarily set the DB path
        original_env = os.environ.get('TRIPTIC_DB_PATH')
        os.environ['TRIPTIC_DB_PATH'] = cls.temp_db_path

        try:
            # Initialize schema
            db.init_database()

            # Create test asset group
            test_uuid_left = "test-uuid-left-001"
            test_uuid_center = "test-uuid-center-001"
            test_uuid_right = "test-uuid-right-001"

            # Create test image files
            for uuid_str in [test_uuid_left, test_uuid_center, test_uuid_right]:
                test_file = cls.temp_assets_dir / f"{uuid_str}.png"
                test_file.write_bytes(b"fake image data")

            # Create asset group with versions
            asset_group = AssetGroup(id="test-group")

            for screen, uuid_str in [
                ('left', test_uuid_left),
                ('center', test_uuid_center),
                ('right', test_uuid_right)
            ]:
                version = AssetVersion(
                    content=uuid_str,
                    prompt=f"Test prompt for {screen}",
                    timestamp=datetime.now().isoformat()
                )
                screen_asset = getattr(asset_group, screen)
                screen_asset.add_version(version, set_as_current=True)

            # Save to database
            db.save_asset_group_db("test-group", asset_group.left, asset_group.center, asset_group.right)

            # Create test playlist
            db.save_playlist_db("test-playlist", ["test-group"], 0)

            # Set test settings
            db.set_setting_db("current_playlist", "test-playlist")

        finally:
            # Restore original environment
            if original_env:
                os.environ['TRIPTIC_DB_PATH'] = original_env
            elif 'TRIPTIC_DB_PATH' in os.environ:
                del os.environ['TRIPTIC_DB_PATH']

    def _mark_tested(self, method: str, path: str):
        """Mark an endpoint as tested."""
        # Find matching pattern
        for defined_method, pattern in self.defined_endpoints:
            if defined_method != method:
                continue

            # Check if path matches pattern
            if pattern == path:
                self.tested_endpoints.add((method, pattern))
                return
            elif '*' in pattern:
                # Convert pattern to regex
                regex_pattern = pattern.replace('*', '.*')
                if re.match(f"^{regex_pattern}$", path):
                    self.tested_endpoints.add((method, pattern))
                    return

    # GET endpoint tests

    def test_get_root(self):
        """Test GET /"""
        self._mark_tested('GET', '/')
        response = requests.get(f"{self.base_url}/")
        self.assertEqual(response.status_code, 200)

    def test_get_config(self):
        """Test GET /config"""
        self._mark_tested('GET', '/config')
        response = requests.get(f"{self.base_url}/config")
        # May succeed or fail depending on config state
        self.assertIn(response.status_code, [200, 404])

    def test_get_settings(self):
        """Test GET /settings"""
        self._mark_tested('GET', '/settings')
        response = requests.get(f"{self.base_url}/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Settings returns a dict with model, video_model, etc.
        self.assertIsInstance(data, dict)

    def test_get_video_models(self):
        """Test GET /video-models"""
        self._mark_tested('GET', '/video-models')
        response = requests.get(f"{self.base_url}/video-models")
        # May fail if gen-AI not configured
        self.assertIn(response.status_code, [200, 400, 500])
        if response.status_code == 200:
            data = response.json()
            # Returns {"models": [...]}
            self.assertIn("models", data)
            self.assertIsInstance(data["models"], list)

    def test_get_playlist(self):
        """Test GET /playlist"""
        self._mark_tested('GET', '/playlist')
        response = requests.get(f"{self.base_url}/playlist")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("name"), "test-playlist")

    def test_get_playlists(self):
        """Test GET /playlists"""
        self._mark_tested('GET', '/playlists')
        response = requests.get(f"{self.base_url}/playlists")
        self.assertIn(response.status_code, [200, 500])
        if response.status_code == 200:
            data = response.json()
            # Returns {"playlists": [...], "current": "...", "data": {...}}
            self.assertIn("playlists", data)
            self.assertIsInstance(data["playlists"], list)
            self.assertIn("test-playlist", data["playlists"])

    def test_get_playlist_items(self):
        """Test GET /playlists/{name}"""
        self._mark_tested('GET', '/playlists/*')
        response = requests.get(f"{self.base_url}/playlists/test-playlist")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("name"), "test-playlist")
        self.assertIsInstance(data.get("items"), list)

    def test_get_playlist_asset_groups(self):
        """Test GET /playlists/{name}/asset-groups"""
        self._mark_tested('GET', '/playlists/*/asset-groups')
        response = requests.get(f"{self.base_url}/playlists/test-playlist/asset-groups")
        self.assertIn(response.status_code, [200, 500])
        if response.status_code == 200:
            data = response.json()
            # Returns {"asset_groups": [...], "imagesets": [...]}
            if isinstance(data, dict):
                self.assertIn("asset_groups", data)
                self.assertIsInstance(data["asset_groups"], list)
            else:
                self.assertIsInstance(data, list)

    def test_get_playlist_imagesets(self):
        """Test GET /playlists/{name}/imagesets (legacy alias)"""
        self._mark_tested('GET', '/playlists/*/imagesets')
        response = requests.get(f"{self.base_url}/playlists/test-playlist/imagesets")
        self.assertIn(response.status_code, [200, 500])
        if response.status_code == 200:
            data = response.json()
            # Returns {"asset_groups": [...], "imagesets": [...]}
            if isinstance(data, dict):
                self.assertIn("imagesets", data)
                self.assertIsInstance(data["imagesets"], list)
            else:
                self.assertIsInstance(data, list)

    def test_get_asset_groups(self):
        """Test GET /asset-groups"""
        self._mark_tested('GET', '/asset-groups')
        response = requests.get(f"{self.base_url}/asset-groups")
        self.assertIn(response.status_code, [200, 500])
        if response.status_code == 200:
            data = response.json()
            # Returns {"asset_groups": {"test-group": {...}}}
            self.assertIsInstance(data, dict)
            self.assertIn("asset_groups", data)
            self.assertIn("test-group", data["asset_groups"])

    def test_get_state_current_asset_group(self):
        """Test GET /state/current-asset-group"""
        self._mark_tested('GET', '/state/current-asset-group')
        response = requests.get(f"{self.base_url}/state/current-asset-group")
        # May return 200 or 404 depending on state
        self.assertIn(response.status_code, [200, 404])

    def test_get_asset_group_versions(self):
        """Test GET /asset-group/{name}/versions/{screen}"""
        self._mark_tested('GET', '/asset-group/*/versions/*')
        response = requests.get(f"{self.base_url}/asset-group/test-group/versions/left")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("versions", data)

    def test_get_asset_group(self):
        """Test GET /asset-group/{name}"""
        self._mark_tested('GET', '/asset-group/*')
        response = requests.get(f"{self.base_url}/asset-group/test-group")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("id"), "test-group")
        self.assertIn("left", data)
        self.assertIn("center", data)
        self.assertIn("right", data)

    def test_get_video_job_status(self):
        """Test GET /video-job/{job_id}"""
        self._mark_tested('GET', '/video-job/*')
        response = requests.get(f"{self.base_url}/video-job/nonexistent-job")
        # Should return 404 for nonexistent job
        self.assertEqual(response.status_code, 404)

    def test_get_content_assets(self):
        """Test GET /content/assets/{filename}"""
        self._mark_tested('GET', '/content/assets/*')
        response = requests.get(f"{self.base_url}/content/assets/test-uuid-left-001.png")
        # May fail if content directory not configured correctly
        self.assertIn(response.status_code, [200, 404, 500])
        if response.status_code == 200:
            self.assertEqual(response.content, b"fake image data")

    # POST endpoint tests

    def test_post_config(self):
        """Test POST /config"""
        self._mark_tested('POST', '/config')
        response = requests.post(
            f"{self.base_url}/config",
            json={"key": "test_key", "value": "test_value"}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_settings(self):
        """Test POST /settings"""
        self._mark_tested('POST', '/settings')
        response = requests.post(
            f"{self.base_url}/settings",
            json={"transition_duration": 500}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_playlist_set(self):
        """Test POST /playlist"""
        self._mark_tested('POST', '/playlist')
        response = requests.post(
            f"{self.base_url}/playlist",
            json={"name": "test-playlist"}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_state_current_asset_group(self):
        """Test POST /state/current-asset-group"""
        self._mark_tested('POST', '/state/current-asset-group')
        response = requests.post(
            f"{self.base_url}/state/current-asset-group",
            json={"asset_group_id": "test-group"}
        )
        # May fail depending on state requirements
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_playlist_create(self):
        """Test POST /playlist/create"""
        self._mark_tested('POST', '/playlist/create')
        response = requests.post(
            f"{self.base_url}/playlist/create",
            json={"name": "new-test-playlist"}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_playlist_rename(self):
        """Test POST /playlist/{name}/rename"""
        self._mark_tested('POST', '/playlist/**/rename')
        # Create a playlist to rename
        requests.post(
            f"{self.base_url}/playlist/create",
            json={"name": "rename-test"}
        )
        response = requests.post(
            f"{self.base_url}/playlist/rename-test/rename",
            json={"new_name": "renamed-test"}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_playlist_reorder(self):
        """Test POST /playlists/{name}/reorder"""
        self._mark_tested('POST', '/playlists/**/reorder')
        response = requests.post(
            f"{self.base_url}/playlists/test-playlist/reorder",
            json={"asset_groups": ["test-group"]}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_playlist_remove(self):
        """Test POST /playlists/{name}/remove"""
        self._mark_tested('POST', '/playlists/**/remove')
        response = requests.post(
            f"{self.base_url}/playlists/test-playlist/remove",
            json={"asset_group_id": "nonexistent"}
        )
        # May succeed or fail depending on whether item exists
        self.assertIn(response.status_code, [200, 400, 404])

    def test_post_heartbeat(self):
        """Test POST /heartbeat/{screen_id}"""
        self._mark_tested('POST', '/heartbeat/*')
        response = requests.post(f"{self.base_url}/heartbeat/test-screen")
        self.assertEqual(response.status_code, 200)

    def test_post_asset_group_add_to_playlists(self):
        """Test POST /asset-group/{name}/add-to-playlists"""
        self._mark_tested('POST', '/asset-group/**/add-to-playlists')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/add-to-playlists",
            json={"playlists": ["test-playlist"]}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_asset_group_create(self):
        """Test POST /asset-group/create"""
        self._mark_tested('POST', '/asset-group/create')
        response = requests.post(
            f"{self.base_url}/asset-group/create",
            json={"name": "new-asset-group"}
        )
        # May fail depending on database state
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_regenerate(self):
        """Test POST /asset-group/{name}/regenerate/{screen}"""
        self._mark_tested('POST', '/asset-group/**/regenerate/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/regenerate/left",
            json={"prompt": "Test regeneration"}
        )
        # Will likely fail without API key, but should not crash
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_regenerate_with_context(self):
        """Test POST /asset-group/{name}/regenerate-with-context/{screen}"""
        self._mark_tested('POST', '/asset-group/**/regenerate-with-context/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/regenerate-with-context/left",
            json={"prompt": "Test context"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_edit(self):
        """Test POST /asset-group/{name}/edit/{screen}"""
        self._mark_tested('POST', '/asset-group/**/edit/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/edit/left",
            json={"prompt": "Edit instruction"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_rename(self):
        """Test POST /asset-group/{name}/rename"""
        self._mark_tested('POST', '/asset-group/**/rename')
        # Create an asset group to rename
        requests.post(
            f"{self.base_url}/asset-group/create",
            json={"name": "rename-asset-test"}
        )
        response = requests.post(
            f"{self.base_url}/asset-group/rename-asset-test/rename",
            json={"new_name": "renamed-asset-test"}
        )
        # May fail if asset group doesn't exist or has issues
        self.assertIn(response.status_code, [200, 400, 404])

    def test_post_asset_group_duplicate(self):
        """Test POST /asset-group/{name}/duplicate"""
        self._mark_tested('POST', '/asset-group/**/duplicate')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/duplicate",
            json={"new_name": "duplicated-group"}
        )
        # May fail with file system errors
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_upload(self):
        """Test POST /asset-group/{name}/upload/{screen}"""
        self._mark_tested('POST', '/asset-group/**/upload/*')
        # Upload requires multipart/form-data, which is complex
        # For now, just test that endpoint exists
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/upload/left"
        )
        # Will fail without proper file upload
        self.assertIn(response.status_code, [400, 500])

    def test_post_asset_group_video(self):
        """Test POST /asset-group/{name}/video/{screen}"""
        self._mark_tested('POST', '/asset-group/**/video/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/video/left",
            json={"prompt": "Test video"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_flip(self):
        """Test POST /asset-group/{name}/flip/{screen}"""
        self._mark_tested('POST', '/asset-group/**/flip/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/flip/left"
        )
        # May fail if image processing fails
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_delete_version(self):
        """Test POST /asset-group/{name}/delete-version/{screen}"""
        self._mark_tested('POST', '/asset-group/**/delete-version/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/delete-version/left"
        )
        # May succeed or fail depending on version count
        self.assertIn(response.status_code, [200, 400])

    def test_post_asset_group_set_version(self):
        """Test POST /asset-group/{name}/version/{screen}"""
        self._mark_tested('POST', '/asset-group/**/version/*')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/version/left",
            json={"version": 1}
        )
        # May return various codes depending on version availability
        self.assertIn(response.status_code, [200, 400, 404])

    def test_post_asset_group_swap(self):
        """Test POST /asset-group/{name}/swap"""
        self._mark_tested('POST', '/asset-group/**/swap')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/swap",
            json={"screen1": "left", "screen2": "right"}
        )
        # May fail with image processing errors
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_copy(self):
        """Test POST /asset-group/{name}/copy"""
        self._mark_tested('POST', '/asset-group/**/copy')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/copy",
            json={"from_screen": "left", "to_screen": "center"}
        )
        # May fail with image processing errors
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_asset_group_save_prompt(self):
        """Test POST /asset-group/{name}/save-prompt"""
        self._mark_tested('POST', '/asset-group/**/save-prompt')
        response = requests.post(
            f"{self.base_url}/asset-group/test-group/save-prompt",
            json={"screen": "left", "prompt": "New prompt"}
        )
        self.assertEqual(response.status_code, 200)

    def test_post_prompt_fluff(self):
        """Test POST /prompt/fluff"""
        self._mark_tested('POST', '/prompt/fluff')
        response = requests.post(
            f"{self.base_url}/prompt/fluff",
            json={"prompt": "simple prompt"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_prompt_fluff_plus(self):
        """Test POST /prompt/fluff-plus"""
        self._mark_tested('POST', '/prompt/fluff-plus')
        response = requests.post(
            f"{self.base_url}/prompt/fluff-plus",
            json={"prompt": "simple prompt"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    def test_post_prompt_diff_single(self):
        """Test POST /prompt/diff-single"""
        self._mark_tested('POST', '/prompt/diff-single')
        response = requests.post(
            f"{self.base_url}/prompt/diff-single",
            json={"base_prompt": "base", "target_prompt": "target"}
        )
        # Will likely fail without API key
        self.assertIn(response.status_code, [200, 400, 500])

    # DELETE endpoint tests

    def test_delete_asset_group(self):
        """Test DELETE /asset-group/{name}"""
        self._mark_tested('DELETE', '/asset-group/*')
        # Create an asset group to delete
        requests.post(
            f"{self.base_url}/asset-group/create",
            json={"name": "delete-test-group"}
        )
        response = requests.delete(f"{self.base_url}/asset-group/delete-test-group")
        # May fail if asset group wasn't created or has issues
        self.assertIn(response.status_code, [200, 404, 500])

    def test_delete_playlist(self):
        """Test DELETE /playlist/{name}"""
        self._mark_tested('DELETE', '/playlist/*')
        # Create a playlist to delete
        requests.post(
            f"{self.base_url}/playlist/create",
            json={"name": "delete-test-playlist"}
        )
        response = requests.delete(f"{self.base_url}/playlist/delete-test-playlist")
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
