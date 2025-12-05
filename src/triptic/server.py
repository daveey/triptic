"""HTTP server for triptic."""

import base64
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
import http.server
import json
import logging
import logging.handlers
import os
import shutil
import socketserver
import threading
import urllib.parse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Import SQLite backend
from triptic import db, storage

# Global dictionary to track video generation jobs
video_jobs = {}


# Data Models
@dataclass
class AssetVersion:
    """Represents a single version of an asset (image or video) with its generation metadata."""
    content: str  # UUID of the file in the assets directory
    prompt: str   # The prompt used to generate this version
    version_uuid: Optional[str] = None  # Unique identifier for this version
    timestamp: Optional[str] = None  # ISO format timestamp of creation

    def __post_init__(self):
        """Generate version UUID if not provided."""
        if self.version_uuid is None:
            self.version_uuid = str(uuid.uuid4())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'AssetVersion':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Asset:
    """Represents a single asset (left, center, or right screen content) with version history."""
    versions: list[AssetVersion] = field(default_factory=list)
    current_version_uuid: Optional[str] = None  # UUID of the current version
    image_url: Optional[str] = None  # URL to the current version's image
    local_path: Optional[str] = None  # Local filesystem path to the current version's file

    def get_versions(self) -> list[AssetVersion]:
        """Get all versions of this asset."""
        return self.versions

    def set_version(self, version_uuid: str) -> bool:
        """Set the current version by UUID. Returns True if successful."""
        for version in self.versions:
            if version.version_uuid == version_uuid:
                self.current_version_uuid = version_uuid
                return True
        return False

    def get_current_version(self) -> Optional[AssetVersion]:
        """Get the currently active version. Returns placeholder if not found."""
        if self.current_version_uuid:
            for version in self.versions:
                if version.version_uuid == self.current_version_uuid:
                    return version

        # Return first version if current_version_uuid not set or not found
        if self.versions:
            return self.versions[0]

        return None

    def add_version(self, version: AssetVersion, set_as_current: bool = True) -> None:
        """Add a new version to the history.

        Maintains a maximum of 9 versions. When adding a 10th version,
        the oldest version is removed.
        """
        self.versions.append(version)

        # Keep only the most recent 9 versions
        if len(self.versions) > 9:
            # Remove the oldest version (first in list)
            removed_version = self.versions.pop(0)
            logging.info(f"Removed old version {removed_version.version_uuid} (keeping max 9)")

        if set_as_current:
            self.current_version_uuid = version.version_uuid

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            'versions': [v.to_dict() for v in self.versions],
            'current_version_uuid': self.current_version_uuid
        }
        if self.image_url:
            result['image_url'] = self.image_url
        if self.local_path:
            result['local_path'] = self.local_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'Asset':
        """Create from dictionary."""
        return cls(
            versions=[AssetVersion.from_dict(v) for v in data.get('versions', [])],
            current_version_uuid=data.get('current_version_uuid'),
            image_url=data.get('image_url'),
            local_path=data.get('local_path')
        )


@dataclass
class AssetGroup:
    """Represents a triple of assets for left, center, and right screens."""
    id: str  # Unique identifier for this asset group (e.g., "animals-1")
    left: Asset = field(default_factory=Asset)
    center: Asset = field(default_factory=Asset)
    right: Asset = field(default_factory=Asset)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'left': self.left.to_dict(),
            'center': self.center.to_dict(),
            'right': self.right.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AssetGroup':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            left=Asset.from_dict(data.get('left', {})),
            center=Asset.from_dict(data.get('center', {})),
            right=Asset.from_dict(data.get('right', {}))
        )


@dataclass
class Playlist:
    """Represents a playlist containing multiple asset groups with playback position."""
    name: str
    assets: list[str] = field(default_factory=list)  # List of asset_group IDs
    current_position: int = 0  # Index into assets array (0-based)

    def get_current_asset_id(self) -> Optional[str]:
        """Get the currently displayed asset group ID."""
        if 0 <= self.current_position < len(self.assets):
            return self.assets[self.current_position]
        return None

    def next(self) -> Optional[str]:
        """Move to next asset and return its ID."""
        if self.assets:
            self.current_position = (self.current_position + 1) % len(self.assets)
            return self.get_current_asset_id()
        return None

    def previous(self) -> Optional[str]:
        """Move to previous asset and return its ID."""
        if self.assets:
            self.current_position = (self.current_position - 1) % len(self.assets)
            return self.get_current_asset_id()
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Playlist':
        """Create from dictionary."""
        return cls(**data)


def setup_logging() -> None:
    """Configure logging to write to separate log files with rotation."""
    # Create logs directory
    log_dir = Path.home() / ".triptic" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger for general operations
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Server operations log (Imagen calls, etc.)
    server_log_file = log_dir / "server.log"
    server_handler = logging.handlers.RotatingFileHandler(
        server_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    server_handler.setLevel(logging.INFO)

    # Create console handler for foreground mode
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('[%(asctime)s] [triptic] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    server_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to root logger
    logger.addHandler(server_handler)
    logger.addHandler(console_handler)

    # Configure separate logger for HTTP requests
    requests_logger = logging.getLogger('requests')
    requests_logger.setLevel(logging.INFO)
    requests_logger.propagate = False  # Don't propagate to root logger

    # HTTP requests log
    requests_log_file = log_dir / "requests.log"
    requests_handler = logging.handlers.RotatingFileHandler(
        requests_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    requests_handler.setLevel(logging.INFO)
    requests_handler.setFormatter(formatter)

    requests_logger.addHandler(requests_handler)

    logging.info(f"Logging configured. Server log: {server_log_file}, Requests log: {requests_log_file}")


class TripticHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves from the public directory."""

    def __init__(self, *args, directory: str = None, **kwargs):
        self.public_dir = directory or str(get_public_dir())
        super().__init__(*args, directory=self.public_dir, **kwargs)

    def _requires_auth(self, path: str) -> bool:
        """Check if a path requires authentication.

        Protected paths:
        - Management pages: /wall.html, /playlists.html, /settings.html, /asset_group.html
        - API endpoints (except heartbeat)

        Unprotected paths:
        - Screen views: / and index.html (with or without ?id= parameter)
        - Static assets: /content/*, /shared/*
        """
        # Parse the path without query string
        parsed_path = urllib.parse.urlparse(path).path

        # Allow screen view (index.html and root)
        if parsed_path in ['/', '/index.html', '']:
            return False

        # Allow static assets
        if parsed_path.startswith('/content/') or parsed_path.startswith('/shared/'):
            return False

        # Allow defaults
        if parsed_path.startswith('/defaults/'):
            return False

        # Allow heartbeat endpoint (for screen health monitoring)
        if parsed_path.startswith('/heartbeat/'):
            return False

        # Everything else requires auth
        return True

    def _check_auth(self) -> bool:
        """Check if the request has valid basic authentication.

        Returns True if auth is valid or not required, False otherwise.
        """
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            return False

        try:
            # Parse "Basic <base64>" header
            auth_type, auth_string = auth_header.split(' ', 1)
            if auth_type.lower() != 'basic':
                return False

            # Decode base64
            decoded = base64.b64decode(auth_string).decode('utf-8')
            username, password = decoded.split(':', 1)

            # Get credentials from environment or use defaults
            expected_username = os.environ.get('TRIPTIC_AUTH_USERNAME', 'daveey')
            expected_password = os.environ.get('TRIPTIC_AUTH_PASSWORD', 'daviddavid')

            return username == expected_username and password == expected_password
        except Exception as e:
            logging.debug(f"Auth check failed: {e}")
            return False

    def _send_auth_required(self) -> None:
        """Send 401 Unauthorized response with WWW-Authenticate header."""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Triptic Management"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>401 Unauthorized</h1><p>Authentication required.</p></body></html>')

    def log_message(self, format: str, *args) -> None:
        """Log HTTP requests to separate requests log."""
        requests_logger = logging.getLogger('requests')
        if len(args) >= 3:
            requests_logger.info(f"{args[0]} {args[1]} {args[2]}")
        else:
            requests_logger.info(format % args)

    def _send_json_error(self, code: int, message: str) -> None:
        """Send a JSON error response instead of HTML."""
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_response = json.dumps({'status': 'error', 'message': message})
        self.wfile.write(error_response.encode())

    def do_GET(self) -> None:
        """Handle GET requests."""
        # Check authentication for protected paths
        if self._requires_auth(self.path):
            if not self._check_auth():
                self._send_auth_required()
                return

        if self.path == '/config':
            self._handle_get_config()
        elif self.path == '/settings':
            self._handle_get_settings()
        elif self.path == '/video-models':
            self._handle_get_video_models()
        elif self.path == '/playlist':
            self._handle_get_playlist()
        elif self.path == '/playlists':
            self._handle_get_playlists()
        elif self.path.startswith('/playlists/') and self.path.endswith('/asset-groups'):
            self._handle_get_playlist_asset_groups()
        elif self.path.startswith('/playlists/') and self.path.endswith('/imagesets'):
            # Keep old endpoint for backward compatibility
            self._handle_get_playlist_asset_groups()
        elif self.path.startswith('/playlists/'):
            self._handle_get_playlist_by_name()
        elif self.path == '/asset-groups':
            self._handle_get_asset_groups()
        elif self.path == '/state/current-asset-group':
            self._handle_get_current_asset_group()
        elif self.path.startswith('/asset-group/') and '/versions/' in self.path:
            self._handle_get_image_versions()
        elif self.path.startswith('/asset-group/'):
            self._handle_get_asset_group()
        elif self.path.startswith('/video-job/'):
            self._handle_get_video_job_status()
        elif self.path.startswith('/content/assets/'):
            self._handle_get_asset_file()
        elif self.path == '/' or self.path == '':
            # Redirect root to wall
            self.send_response(302)
            self.send_header('Location', '/wall.html')
            self.end_headers()
        else:
            # Delegate to parent for static file serving (includes /defaults/)
            super().do_GET()

    def end_headers(self) -> None:
        """Add no-cache headers to HTML files and images."""
        # Add no-cache headers for HTML files and images
        if hasattr(self, 'path'):
            if self.path.endswith('.html') or self.path.endswith(('.svg', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.webm')):
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self) -> None:
        """Handle POST requests."""
        # Check authentication for protected paths
        if self._requires_auth(self.path):
            if not self._check_auth():
                self._send_auth_required()
                return

        if self.path.startswith('/heartbeat/'):
            screen_id = self.path.split('/')[-1]
            self._handle_heartbeat(screen_id)
        elif self.path == '/config':
            self._handle_post_config()
        elif self.path == '/settings':
            self._handle_post_settings()
        elif self.path == '/playlist':
            self._handle_set_playlist()
        elif self.path == '/state/current-asset-group':
            self._handle_set_current_asset_group()
        elif self.path == '/playlist/create':
            self._handle_create_playlist()
        elif self.path.startswith('/playlist/') and self.path.endswith('/rename'):
            self._handle_rename_playlist()
        elif self.path.startswith('/playlists/') and self.path.endswith('/reorder'):
            self._handle_reorder_playlist()
        elif self.path.startswith('/playlists/') and self.path.endswith('/remove'):
            self._handle_remove_from_playlist()
        elif self.path.startswith('/asset-group/') and self.path.endswith('/add-to-playlists'):
            self._handle_add_asset_group_to_playlists()
        elif self.path == '/asset-group/create':
            self._handle_create_asset_group()
        elif self.path.startswith('/asset-group/') and '/regenerate-with-context/' in self.path:
            self._handle_regenerate_with_context()
        elif self.path.startswith('/asset-group/') and '/regenerate/' in self.path:
            self._handle_regenerate_image()
        elif self.path.startswith('/asset-group/') and '/edit/' in self.path:
            self._handle_edit_image()
        elif self.path.startswith('/asset-group/') and '/rename' in self.path:
            self._handle_rename_asset_group()
        elif self.path.startswith('/asset-group/') and '/duplicate' in self.path:
            self._handle_duplicate_asset_group()
        elif self.path.startswith('/asset-group/') and '/upload/' in self.path:
            self._handle_upload_image()
        elif self.path.startswith('/asset-group/') and '/video/' in self.path:
            self._handle_generate_video()
        elif self.path.startswith('/asset-group/') and '/flip/' in self.path:
            self._handle_flip_image()
        elif self.path.startswith('/asset-group/') and '/delete-version/' in self.path:
            self._handle_delete_image_version()
        elif self.path.startswith('/asset-group/') and '/version/' in self.path:
            self._handle_restore_image_version()
        elif self.path.startswith('/asset-group/') and '/swap' in self.path:
            self._handle_swap_images()
        elif self.path.startswith('/asset-group/') and '/copy' in self.path:
            self._handle_copy_image()
        elif self.path.startswith('/asset-group/') and '/save-prompt' in self.path:
            self._handle_save_prompt()
        elif self.path == '/prompt/fluff':
            self._handle_fluff_prompt()
        elif self.path == '/prompt/fluff-plus':
            self._handle_fluff_plus_prompt()
        elif self.path == '/prompt/diff-single':
            self._handle_diff_single_prompt()
        else:
            self._send_json_error(404, "Not found")

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        # Check authentication for protected paths
        if self._requires_auth(self.path):
            if not self._check_auth():
                self._send_auth_required()
                return

        if self.path.startswith('/asset-group/'):
            self._handle_delete_asset_group()
        elif self.path.startswith('/playlist/'):
            self._handle_delete_playlist()
        else:
            self._send_json_error(404, "Not found")

    def _handle_get_config(self) -> None:
        """Get configuration."""
        try:
            config = get_config()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps(config)
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting config: {e}")

    def _handle_post_config(self) -> None:
        """Update configuration."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            update_config(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok'})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error updating config: {e}")

    def _handle_get_settings(self) -> None:
        """Get settings."""
        try:
            settings = get_settings()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps(settings)
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting settings: {e}")

    def _handle_post_settings(self) -> None:
        """Update settings."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            update_settings(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok'})
            self.wfile.write(response.encode())
            logging.info(f"Settings updated: model={data.get('model', 'N/A')}")
        except Exception as e:
            self.send_error(500, f"Error updating settings: {e}")

    def _handle_get_video_models(self) -> None:
        """Get available video generation models from Gemini API."""
        try:
            # Get API key from settings
            settings = get_settings()
            api_key = settings.get('gemini_api_key', '')

            if not api_key:
                self.send_error(400, "Gemini API key not configured")
                return

            try:
                from google import genai
            except ImportError:
                self.send_error(500, "google-genai package not available")
                return

            # Create Gemini client
            client = genai.Client(api_key=api_key)

            # List all models and filter for video generation models
            video_models = []
            try:
                models = client.models.list()
                for model in models:
                    # Check if model supports video generation
                    if hasattr(model, 'name') and 'veo' in model.name.lower():
                        model_info = {
                            'name': model.name,
                            'display_name': getattr(model, 'display_name', model.name),
                            'description': getattr(model, 'description', 'Video generation model')
                        }
                        video_models.append(model_info)
            except Exception as e:
                logging.warning(f"Error listing models from API: {e}")
                # Fallback to known models if API call fails
                video_models = [
                    {
                        'name': 'veo-2.0-generate-001',
                        'display_name': 'Veo 2.0',
                        'description': 'Google\'s Veo 2.0 video generation model'
                    }
                ]

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps({'models': video_models})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error getting video models: {e}")
            self.send_error(500, f"Error getting video models: {e}")

    def _handle_get_playlist(self) -> None:
        """Get current playlist items."""
        try:
            current_name = get_current_playlist()
            items = get_playlist_items(current_name)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps({'name': current_name, 'items': items})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting playlist: {e}")

    def _handle_get_playlists(self) -> None:
        """Get all available playlists."""
        try:
            playlists = get_all_playlists()
            current = get_current_playlist()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            # Return both the list of playlist names and full playlist data
            response = json.dumps({
                'playlists': list(playlists.keys()),
                'current': current,
                'data': {name: playlist.to_dict() for name, playlist in playlists.items()}
            })
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting playlists: {e}")

    def _handle_get_playlist_by_name(self) -> None:
        """Get a specific playlist's items by name."""
        try:
            # Extract playlist name from path: /playlists/{name}
            playlist_name = self.path.split('/')[-1]
            items = get_playlist_items(playlist_name)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps({'name': playlist_name, 'items': items})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting playlist: {e}")

    def _handle_get_playlist_asset_groups(self) -> None:
        """Get just the asset group IDs from a playlist (for navigation)."""
        try:
            # Extract playlist name from path: /playlists/{name}/asset-groups or /playlists/{name}/imagesets
            parts = self.path.split('/')
            playlist_name = urllib.parse.unquote(parts[2])

            # Get playlist using new model
            playlists = get_all_playlists()
            if playlist_name not in playlists:
                # Try old-style playlist items for backward compatibility
                items = get_playlist_items(playlist_name)
                asset_group_names = [item['name'] for item in items]
            else:
                # Use new Playlist model - return asset_group IDs
                playlist = playlists[playlist_name]
                asset_group_names = playlist.assets

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # Return both old and new keys for compatibility
            response = json.dumps({
                'asset_groups': asset_group_names,
                'imagesets': asset_group_names  # For backward compatibility
            })
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            logging.error(f"Error getting playlist asset groups for '{playlist_name}': {e}")
            logging.error(traceback.format_exc())
            self.send_error(500, f"Error getting playlist asset groups: {e}")

    def _handle_get_imagesets(self) -> None:
        """Get image sets, optionally filtered by prefix."""
        try:
            # Parse query parameters
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            prefix = query.get('prefix', [None])[0]

            imagesets = list_imagesets(prefix)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({
                'imagesets': [{'name': name, 'files': files} for name, files in imagesets]
            })
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting imagesets: {e}")

    def _handle_get_asset_groups(self) -> None:
        """Get all asset groups."""
        try:
            asset_groups = get_asset_groups()
            # Convert to dict format for JSON
            response_data = {
                group_id: group.to_dict()
                for group_id, group in asset_groups.items()
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps({'asset_groups': response_data})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error getting asset groups: {e}")
            self.send_error(500, f"Error getting asset groups: {e}")

    def _handle_get_asset_group(self) -> None:
        """Get a specific asset group by ID."""
        try:
            from urllib.parse import unquote

            # Extract group ID from path: /asset-group/{id}
            group_id = unquote(self.path.split('/')[-1])
            if not group_id:
                self.send_error(400, "Missing asset group ID")
                return

            asset_group = get_asset_group(group_id)
            if not asset_group:
                self.send_error(404, f"Asset group not found: {group_id}")
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps(asset_group.to_dict())
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error getting asset group: {e}")
            self.send_error(500, f"Error getting asset group: {e}")

    def _handle_create_asset_group(self) -> None:
        """Create or update an asset group."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())

            if 'id' not in data:
                self.send_error(400, "Missing asset group ID")
                return

            # Create AssetGroup from data
            asset_group = AssetGroup.from_dict(data)
            save_asset_group(asset_group)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'success': True, 'id': asset_group.id})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error creating asset group: {e}")
            self.send_error(500, f"Error creating asset group: {e}")

    def _handle_delete_asset_group(self) -> None:
        """Delete an asset group."""
        try:
            # Extract group ID from path: /asset-group/{id}
            group_id = self.path.split('/')[-1]
            if not group_id:
                self.send_error(400, "Missing asset group ID")
                return

            success = delete_asset_group(group_id)
            if not success:
                self.send_error(404, f"Asset group not found: {group_id}")
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'success': True})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error deleting asset group: {e}")
            self.send_error(500, f"Error deleting asset group: {e}")

    def _handle_add_asset_group_to_playlists(self) -> None:
        """Add an asset group to one or more playlists."""
        try:
            # Extract group ID from path: /asset-group/{id}/add-to-playlists
            path_parts = self.path.split('/')
            group_id = path_parts[2] if len(path_parts) > 2 else None

            if not group_id:
                self.send_error(400, "Missing asset group ID")
                return

            # Decode URL-encoded group ID
            from urllib.parse import unquote
            group_id = unquote(group_id)

            # Verify asset group exists
            if not get_asset_group(group_id):
                self.send_error(404, f"Asset group not found: {group_id}")
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            playlist_names = data.get('playlists', [])

            if not playlist_names:
                self.send_error(400, "Missing playlists array")
                return

            # Add to each playlist
            results = {}
            for playlist_name in playlist_names:
                playlists = get_all_playlists()
                if playlist_name in playlists:
                    playlist = playlists[playlist_name]
                    if group_id not in playlist.assets:
                        playlist.assets.append(group_id)
                        save_playlist(playlist)
                        results[playlist_name] = True
                    else:
                        results[playlist_name] = True  # Already in playlist
                else:
                    results[playlist_name] = False  # Playlist doesn't exist

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'results': results})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error adding asset group to playlists: {e}")
            self.send_error(500, f"Error adding to playlists: {e}")

    def _handle_set_playlist(self) -> None:
        """Set current playlist."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            playlist_name = data.get('name')
            if not playlist_name:
                self.send_error(400, "Missing playlist name")
                return
            if set_current_playlist(playlist_name):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'playlist': playlist_name})
                self.wfile.write(response.encode())
            else:
                self.send_error(404, f"Playlist not found: {playlist_name}")
        except Exception as e:
            self.send_error(500, f"Error setting playlist: {e}")

    def _handle_get_current_imageset(self) -> None:
        """Get current imageset override."""
        try:
            state = read_state()
            imageset = state.get('current_imageset_override', None)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'imageset': imageset})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting current imageset: {e}")

    def _handle_set_current_imageset(self) -> None:
        """Set current imageset override for dashboard preview."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            imageset = data.get('imageset')
            if not imageset:
                self.send_error(400, "Missing imageset name")
                return

            # Store the current imageset override in state
            state = read_state()
            old_imageset = state.get('current_imageset_override')
            state['current_imageset_override'] = imageset
            write_state(state)

            logging.info(f"[MUTATION] Set current imageset: '{old_imageset}' -> '{imageset}'")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'imageset': imageset})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            logging.error(f"[MUTATION] Set current imageset failed: {e}")
            logging.error(traceback.format_exc())
            self.send_error(500, f"Error setting current imageset: {e}")

    def _handle_get_current_asset_group(self) -> None:
        """Get current asset group override (new endpoint name)."""
        try:
            state = read_state()
            asset_group = state.get('current_imageset_override', None)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # Return both old and new keys for compatibility
            response = json.dumps({
                'asset_group': asset_group,
                'imageset': asset_group
            })
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error getting current asset group: {e}")

    def _handle_set_current_asset_group(self) -> None:
        """Set current asset group override (new endpoint name)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            # Accept both 'asset_group' and 'imageset' keys
            asset_group = data.get('asset_group') or data.get('imageset')
            if not asset_group:
                self.send_error(400, "Missing asset_group name")
                return

            # Store the current asset group override in state
            state = read_state()
            old_asset_group = state.get('current_imageset_override')
            state['current_imageset_override'] = asset_group
            write_state(state)

            logging.info(f"[MUTATION] Set current asset group: '{old_asset_group}' -> '{asset_group}'")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'asset_group': asset_group})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            logging.error(f"[MUTATION] Set current imageset failed: {e}")
            logging.error(traceback.format_exc())
            self.send_error(500, f"Error setting current imageset: {e}")

    def _handle_create_playlist(self) -> None:
        """Create a new empty playlist."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            playlist_name = data.get('name', '').strip()

            if not playlist_name:
                logging.error(f"[MUTATION] Create playlist failed: Missing playlist name")
                self.send_error(400, "Missing playlist name")
                return

            # Validate name (letters, numbers, hyphens, underscores only)
            import re
            if not re.match(r'^[a-zA-Z0-9_\-]+$', playlist_name):
                logging.error(f"[MUTATION] Create playlist failed: Invalid name '{playlist_name}'")
                self.send_error(400, "Playlist name can only contain letters, numbers, hyphens, and underscores")
                return

            # Check if playlist already exists
            state = read_state()
            if 'playlists' not in state:
                state['playlists'] = {}

            if playlist_name in state['playlists']:
                logging.error(f"[MUTATION] Create playlist failed: Playlist already exists '{playlist_name}'")
                self.send_error(409, f"Playlist already exists: {playlist_name}")
                return

            # Create empty playlist using new Playlist model
            playlist = Playlist(name=playlist_name, assets=[], current_position=0)
            save_playlist(playlist)

            logging.info(f"[MUTATION] Created playlist: '{playlist_name}'")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'name': playlist_name})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            logging.error(f"[MUTATION] Create playlist exception: {e}")
            logging.error(traceback.format_exc())
            traceback.print_exc()
            self.send_error(500, f"Error creating playlist: {e}")

    def _handle_rename_playlist(self) -> None:
        """Rename an existing playlist."""
        try:
            # Extract old playlist name from URL
            old_name = self.path.split('/')[2]  # /playlist/{name}/rename
            old_name = urllib.parse.unquote(old_name)

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            new_name = data.get('new_name', '').strip()

            if not new_name:
                logging.error(f"[MUTATION] Rename playlist failed: Missing new playlist name")
                self._send_json_error(400, "Missing new playlist name")
                return

            # Validate name (letters, numbers, hyphens, underscores only)
            import re
            if not re.match(r'^[a-zA-Z0-9_\-]+$', new_name):
                logging.error(f"[MUTATION] Rename playlist failed: Invalid name '{new_name}'")
                self._send_json_error(400, "Playlist name can only contain letters, numbers, hyphens, and underscores")
                return

            # Check if old playlist exists and new name doesn't conflict
            playlists = get_all_playlists()

            if old_name not in playlists:
                logging.error(f"[MUTATION] Rename playlist failed: Playlist not found '{old_name}'")
                self._send_json_error(404, f"Playlist not found: {old_name}")
                return

            if new_name in playlists:
                logging.error(f"[MUTATION] Rename playlist failed: Playlist already exists '{new_name}'")
                self._send_json_error(409, f"Playlist already exists: {new_name}")
                return

            # Rename playlist in database
            success = rename_playlist(old_name, new_name)
            if not success:
                logging.error(f"[MUTATION] Rename playlist failed: Database error")
                self._send_json_error(500, "Failed to rename playlist in database")
                return

            # Update current playlist if needed
            current = get_current_playlist()
            if current == old_name:
                set_current_playlist(new_name)

            # Rename physical directory if it exists
            content_dir = Path.home() / ".triptic" / "content"
            old_dir = content_dir / old_name
            new_dir = content_dir / new_name

            if old_dir.exists():
                old_dir.rename(new_dir)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'old_name': old_name, 'new_name': new_name})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            logging.error(f"[MUTATION] Rename playlist exception: {e}")
            logging.error(traceback.format_exc())
            traceback.print_exc()
            self._send_json_error(500, f"Error renaming playlist: {e}")

    def _handle_delete_playlist(self) -> None:
        """Delete a playlist."""
        try:
            # Extract playlist name from URL: /playlist/{name}
            playlist_name = self.path.split('/')[2]
            playlist_name = urllib.parse.unquote(playlist_name)

            if not playlist_name:
                logging.error("[MUTATION] Delete playlist failed: Missing playlist name")
                self.send_error(400, "Missing playlist name")
                return

            # Use the existing delete_playlist function
            success = delete_playlist(playlist_name)

            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'playlist': playlist_name})
                self.wfile.write(response.encode())
                logging.info(f"[MUTATION] Deleted playlist: '{playlist_name}'")
            else:
                logging.error(f"[MUTATION] Delete playlist failed: Playlist not found '{playlist_name}'")
                self.send_error(404, f"Playlist not found: {playlist_name}")
        except Exception as e:
            import traceback
            logging.error(f"[MUTATION] Delete playlist exception: {e}")
            logging.error(traceback.format_exc())
            traceback.print_exc()
            self.send_error(500, f"Error deleting playlist: {e}")

    def _handle_heartbeat(self, screen_id: str) -> None:
        """Record screen heartbeat."""
        try:
            update_screen_heartbeat(screen_id)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'screen_id': screen_id})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error recording heartbeat: {e}")

    def _handle_add_imageset_to_playlists(self) -> None:
        """Add an imageset to one or more playlists."""
        try:
            # Extract imageset name from path: /imageset/{name}/add-to-playlists
            path_parts = self.path.split('/')
            imageset_name = path_parts[2] if len(path_parts) > 2 else None

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Decode URL-encoded imageset name
            from urllib.parse import unquote
            imageset_name = unquote(imageset_name)

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            playlist_names = data.get('playlists', [])

            if not playlist_names:
                self.send_error(400, "Missing playlists array")
                return

            # Add to each playlist
            results = {}
            for playlist_name in playlist_names:
                results[playlist_name] = add_to_playlist(playlist_name, imageset_name)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'results': results})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error adding to playlists: {e}")

    def _handle_create_imageset(self) -> None:
        """Create a new imageset with auto-generated prompt."""
        try:
            # Read the imageset name from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            imageset_name = data.get('name', '').strip()

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Generate prompt based on name following Imagen best practices
            # Extract the last part of the name (after the last slash if present)
            name_parts = imageset_name.split('/')
            base_name = name_parts[-1]

            # Create a descriptive narrative prompt following Imagen best practices:
            # - Use descriptive narratives, not just keywords
            # - Include specific details about lighting, mood, composition
            # - Use photography terminology for photorealistic images
            # - Be explicit about aspect ratio and requirements
            subject = base_name.replace('-', ' ').replace('_', ' ')
            auto_prompt = (
                f"A stunning photograph of {subject}, captured in cinematic lighting with professional composition. "
                f"The scene features rich colors and detailed textures, shot with an 85mm lens for beautiful depth of field. "
                f"Natural lighting creates a warm, inviting atmosphere. High-resolution photography with sharp focus on the subject. "
                f"Vertical 9:16 aspect ratio, perfect for portrait orientation display."
            )

            # Get the prompt file path
            content_dir = get_content_dir()
            img_dir = content_dir / "img"

            if '/' in imageset_name:
                # Playlist-specific imageset
                playlist_dir = img_dir / name_parts[0]
                playlist_dir.mkdir(parents=True, exist_ok=True)
                prompt_file = playlist_dir / f"{base_name}.prompt.txt"
            else:
                # Screen-specific imageset (save in left directory)
                left_dir = img_dir / "left"
                left_dir.mkdir(parents=True, exist_ok=True)
                prompt_file = left_dir / f"{imageset_name}.prompt.txt"

            # Write the prompt file
            prompt_content = f"Main prompt: {auto_prompt}\n\nScreen-specific prompts:\n  Left: {auto_prompt}\n  Center: {auto_prompt}\n  Right: {auto_prompt}\n"
            prompt_file.write_text(prompt_content)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'name': imageset_name, 'prompt': auto_prompt})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error creating imageset: {e}")

    def _handle_delete_imageset(self) -> None:
        """Delete an imageset and its files."""
        try:
            # Extract imageset name from path: /imageset/{name}
            path_parts = self.path.split('/')
            imageset_name = path_parts[2] if len(path_parts) > 2 else None

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Decode URL-encoded imageset name
            from urllib.parse import unquote
            imageset_name = unquote(imageset_name)

            # Delete the imageset
            if delete_imageset(imageset_name):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'deleted': imageset_name})
                self.wfile.write(response.encode())
            else:
                self.send_error(404, f"Imageset not found: {imageset_name}")
        except Exception as e:
            self.send_error(500, f"Error deleting imageset: {e}")

    def _handle_regenerate_image(self) -> None:
        """Regenerate a single image in an imageset."""
        try:
            # Parse path: /imageset/{name}/regenerate/{screen}
            from urllib.parse import unquote
            from datetime import datetime
            from triptic import storage
            from triptic.imgen import generate_image_with_gemini

            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self._send_json_error(400, "Missing imageset name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self._send_json_error(400, "Invalid screen name")
                return

            # Try to read prompt from request body, fallback to prompt file or database
            prompt = None
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                data = json.loads(body.decode())
                prompt = data.get('prompt')

            # Get or create asset group
            asset_group = get_asset_group(imageset_name)

            if not prompt:
                # Fallback to reading from prompt file
                prompt = read_imageset_prompt(imageset_name, screen)

            if not prompt and asset_group:
                # Fallback to getting prompt from the current version in database
                screen_asset = getattr(asset_group, screen)
                if screen_asset.versions:
                    prompt = screen_asset.versions[-1].prompt

            if not prompt:
                # Return 404 if asset group doesn't exist, 400 otherwise
                if not asset_group:
                    self._send_json_error(404, f"Asset group '{imageset_name}' not found")
                else:
                    self._send_json_error(400, "No prompt provided or found")
                return

            if not asset_group:
                # Create new asset group
                asset_group = AssetGroup(id=imageset_name)

            # Generate UUID for new image
            content_uuid = storage.generate_uuid()

            # Generate output path
            assets_dir = storage.get_assets_dir()
            output_path = assets_dir / f"{content_uuid}.png"

            # Generate the image
            generate_image_with_gemini(prompt, output_path, screen)

            # Create version and add to asset
            version = AssetVersion(
                content=content_uuid,
                prompt=prompt,
                timestamp=datetime.now().isoformat()
            )

            # Add version to the appropriate screen
            screen_asset = getattr(asset_group, screen)
            screen_asset.add_version(version, set_as_current=True)

            # Save to database
            save_asset_group(asset_group)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'regenerated': screen})
            self.wfile.write(response.encode())
        except Exception as e:
            logging.error(f"Error regenerating image: {e}", exc_info=True)
            self._send_json_error(500, f"Error regenerating image: {e}")

    def _handle_regenerate_with_context(self) -> None:
        """Regenerate an image using the other two images as context."""
        try:
            # Parse path: /imageset/{name}/regenerate-with-context/{screen}
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self.send_error(400, "Missing imageset name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            # Read request body to get context screens
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            context_screens = data.get('contextScreens', [])

            if len(context_screens) != 2:
                self.send_error(400, "Expected exactly 2 context screens")
                return

            # Read the screen-specific prompt from file or database
            prompt = read_imageset_prompt(imageset_name, screen)

            if not prompt:
                # Fallback to getting prompt from the database
                asset_group = get_asset_group(imageset_name)
                if asset_group:
                    screen_asset = getattr(asset_group, screen)
                    if screen_asset.versions:
                        prompt = screen_asset.versions[-1].prompt

            if not prompt:
                self.send_error(404, "No prompt file found for this imageset")
                return

            # Get paths to context images
            context_images = {}
            for ctx_screen in context_screens:
                ctx_path = get_imageset_image_path(imageset_name, ctx_screen)
                if not ctx_path or not ctx_path.exists():
                    self.send_error(404, f"Context image not found for {ctx_screen}")
                    return
                context_images[ctx_screen] = ctx_path

            # Get output path
            output_path = get_imageset_image_path(imageset_name, screen)
            if not output_path:
                self.send_error(404, "Imageset not found")
                return

            # Create backup before regenerating
            create_image_backup(output_path)

            # Regenerate with context
            from triptic.imgen import generate_image_with_context
            generate_image_with_context(prompt, output_path, screen, context_images)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'regenerated': screen, 'with_context': context_screens})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error regenerating image with context: {e}")

    def _handle_edit_image(self) -> None:
        """Edit an image using Gemini's edit_image API."""
        try:
            # Parse path: /imageset/{name}/edit/{screen}
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self.send_error(400, "Missing imageset name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            # Read the edit prompt from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            edit_prompt = data.get('prompt', '')

            if not edit_prompt:
                self.send_error(400, "Missing edit prompt")
                return

            # Get the current image path
            output_path = get_imageset_image_path(imageset_name, screen)
            if not output_path or not output_path.exists():
                self.send_error(404, "Image not found")
                return

            # Create backup before editing
            create_image_backup(output_path)

            # Edit the image
            from triptic.imgen import edit_image_with_gemini
            edit_image_with_gemini(edit_prompt, output_path, output_path)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'edited': screen})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error editing image: {e}")

    def _handle_upload_image(self) -> None:
        """Upload a replacement image for a screen."""
        try:
            # Parse path: /imageset/{name}/upload/{screen}
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self.send_error(400, "Missing imageset name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            # Read the uploaded image data
            content_length = int(self.headers.get('Content-Length', 0))
            image_data = self.rfile.read(content_length)

            # Get the output path
            output_path = get_imageset_image_path(imageset_name, screen)
            if not output_path:
                self.send_error(404, "Imageset not found")
                return

            # Create backup before uploading
            if output_path.exists():
                create_image_backup(output_path)

            # Save the uploaded image
            output_path.write_bytes(image_data)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'uploaded': screen})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error uploading image: {e}")

    def _handle_generate_video(self) -> None:
        """Generate a video from an image using Google Veo API (async)."""
        try:
            # Parse path: /imageset/{name}/video/{screen}
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self.send_error(400, "Missing imageset name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            # Get the image path
            image_path = get_imageset_image_path(imageset_name, screen)
            if not image_path or not image_path.exists():
                self.send_error(404, "Image not found")
                return

            # Determine video output path (same directory as image, .mp4 extension)
            video_path = image_path.with_suffix('.mp4')

            # Create a unique job ID for this video generation
            import uuid
            job_id = str(uuid.uuid4())

            # Store job status
            video_jobs[job_id] = {
                'status': 'processing',
                'imageset': imageset_name,
                'screen': screen,
                'video_path': video_path,
                'error': None
            }

            logging.info(f"Starting async video generation for {imageset_name} {screen} screen (job: {job_id})")

            # Start video generation in background thread
            import threading
            def generate_video_async():
                try:
                    from triptic.imgen import generate_video_from_image
                    result_path = generate_video_from_image(image_path, video_path)

                    # Update job status
                    content_dir = get_content_dir()
                    video_relative = result_path.relative_to(content_dir.parent)
                    video_url = f"/{video_relative}"

                    video_jobs[job_id]['status'] = 'complete'
                    video_jobs[job_id]['video_url'] = video_url
                    logging.info(f"Video generation complete for job {job_id}")
                except Exception as e:
                    logging.error(f"Video generation failed for job {job_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    video_jobs[job_id]['status'] = 'error'
                    video_jobs[job_id]['error'] = str(e)

            thread = threading.Thread(target=generate_video_async, daemon=True)
            thread.start()

            # Return immediately with job ID
            self.send_response(202)  # 202 Accepted
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'processing', 'job_id': job_id})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error starting video generation: {e}")

    def _handle_get_video_job_status(self) -> None:
        """Get the status of a video generation job."""
        try:
            # Parse path: /video-job/{job_id}
            job_id = self.path.split('/')[-1]

            if job_id not in video_jobs:
                self.send_error(404, "Job not found")
                return

            job = video_jobs[job_id]

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response_data = {
                'status': job['status'],
                'imageset': job['imageset'],
                'screen': job['screen']
            }

            if job['status'] == 'complete':
                response_data['video_url'] = job['video_url']
            elif job['status'] == 'error':
                response_data['error'] = job['error']

            self.wfile.write(json.dumps(response_data).encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error getting job status: {e}")

    def _handle_get_asset_file(self) -> None:
        """Serve asset files from the assets directory."""
        try:
            # Extract filename from path: /content/assets/{uuid}.{ext}
            # Strip query parameters (e.g., ?t=timestamp) if present
            path_without_query = self.path.split('?')[0]
            filename = path_without_query.split('/')[-1]

            # Get the file from storage
            assets_dir = storage.get_assets_dir()
            file_path = assets_dir / filename

            if not file_path.exists():
                self.send_error(404, "Asset not found")
                return

            # Determine content type
            import mimetypes
            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type is None:
                content_type = 'application/octet-stream'

            # Send the file
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=31536000')  # Cache for 1 year
            self.end_headers()

            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error serving asset file: {e}")

    def _handle_reorder_playlist(self) -> None:
        """Reorder imagesets in a playlist."""
        try:
            # Parse path: /playlists/{name}/reorder
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            playlist_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not playlist_name:
                self._send_json_error(400, "Missing playlist name")
                return

            # Read the new order from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            new_order = data.get('order', [])

            if not isinstance(new_order, list):
                self._send_json_error(400, "Invalid order format")
                return

            # Update the playlist order
            if reorder_playlist(playlist_name, new_order):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'playlist': playlist_name})
                self.wfile.write(response.encode())
            else:
                self._send_json_error(404, f"Playlist not found: {playlist_name}")
        except Exception as e:
            self._send_json_error(500, f"Error reordering playlist: {e}")

    def _handle_remove_from_playlist(self) -> None:
        """Remove an asset group from a playlist."""
        try:
            # Parse path: /playlists/{name}/remove
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            playlist_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not playlist_name:
                self._send_json_error(400, "Missing playlist name")
                return

            # Read the asset ID from request body (support 'asset_group', 'asset', and 'imageset' for compatibility)
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            asset_id = data.get('asset_group') or data.get('asset') or data.get('imageset')

            if not asset_id:
                self._send_json_error(400, "Missing asset ID")
                return

            # Remove from playlist
            if remove_from_playlist(playlist_name, asset_id):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'removed': asset_id})
                self.wfile.write(response.encode())
            else:
                self._send_json_error(404, f"Playlist or asset not found")
        except Exception as e:
            self._send_json_error(500, f"Error removing from playlist: {e}")

    def _handle_flip_image(self) -> None:
        """Flip an image horizontally and create a new version."""
        try:
            from urllib.parse import unquote
            from PIL import Image
            from io import BytesIO
            import uuid
            from . import storage

            # Parse path: /asset-group/{name}/flip/{screen}
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self.send_error(400, "Missing asset group name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            # Get asset group from database
            asset_group = get_asset_group(imageset_name)
            if not asset_group:
                self.send_error(404, f"Asset group '{imageset_name}' not found")
                return

            # Get the current screen asset
            screen_asset = getattr(asset_group, screen)
            if not screen_asset.current_version_uuid:
                self.send_error(404, "No current version to flip")
                return

            # Load current image from storage
            current_uuid = screen_asset.current_version_uuid
            image_path = storage.get_path(current_uuid)
            if not image_path or not image_path.exists():
                self.send_error(404, "Image file not found")
                return

            # Flip the image
            img = Image.open(image_path)
            flipped = img.transpose(Image.FLIP_LEFT_RIGHT)

            # Save as new version with new UUID
            new_uuid = str(uuid.uuid4())
            new_path = storage.get_path(new_uuid)
            flipped.save(new_path)

            # Find current version to copy the prompt
            current_version = None
            for version in screen_asset.versions:
                if version.version_uuid == current_uuid:
                    current_version = version
                    break

            prompt = current_version.prompt if current_version else ""

            # Add new version to asset
            new_version = AssetVersion(
                version_uuid=new_uuid,
                content_uuid=new_uuid,
                prompt=prompt,
                timestamp=datetime.now().isoformat()
            )
            screen_asset.add_version(new_version, set_as_current=True)

            # Save to database
            save_asset_group(asset_group)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'flipped': screen, 'new_uuid': new_uuid})
            self.wfile.write(response.encode())

            logging.info(f"Flipped {screen} image for '{imageset_name}', created version {new_uuid}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error flipping image: {e}")

    def _handle_get_image_versions(self) -> None:
        """Get available version numbers and current version for an image."""
        try:
            # Parse path: /asset-group/{name}/versions/{screen}
            from urllib.parse import unquote
            from . import storage

            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            assert imageset_name and screen, "Missing asset group name or screen"
            assert screen in ['left', 'center', 'right'], f"Invalid screen: {screen}"

            # Get asset group from database
            asset_group = get_asset_group(imageset_name)

            if not asset_group:
                # New asset group with no versions
                versions = []
                current_version = 0
            else:
                # Get versions from database (not from file names)
                screen_asset = getattr(asset_group, screen)
                version_count = len(screen_asset.versions)

                # Map versions to 1-9 indices (most recent = 9, older = 8, 7, etc.)
                # We store up to 9 versions, with 9 being the most recent
                if version_count == 0:
                    versions = []
                    current_version = 0
                else:
                    # Create version numbers 1-N based on how many versions exist
                    # Oldest version is 1, newest is N
                    versions = list(range(1, version_count + 1))

                    # Find which version number corresponds to the current UUID
                    current_uuid = screen_asset.current_version_uuid
                    current_index = None
                    for i, v in enumerate(screen_asset.versions):
                        if v.version_uuid == current_uuid:
                            current_index = i
                            break

                    # Map array index to version number (1-N)
                    # Index 0 = version 1, index 1 = version 2, etc.
                    if current_index is not None:
                        current_version = current_index + 1
                    else:
                        # Fallback: oldest version (version 1)
                        current_version = 1

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({
                'versions': versions,
                'current': current_version
            })
            self.wfile.write(response.encode())
        except AssertionError as e:
            self._send_json_error(400, str(e))
        except Exception as e:
            self._send_json_error(500, f"Error getting image versions: {e}")

    def _handle_restore_image_version(self) -> None:
        """Restore a specific version of an image."""
        try:
            # Parse path: /asset-group/{name}/version/{screen}
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            if not imageset_name or not screen:
                self._send_json_error(400, "Missing asset group name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self._send_json_error(400, "Invalid screen name")
                return

            # Read request body to get version number
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            version = data.get('version')

            if version is None:
                self._send_json_error(400, "Missing version number")
                return

            # Set the version as current (database only)
            if restore_image_version(imageset_name, screen, version):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({'status': 'ok', 'version': version})
                self.wfile.write(response.encode())
            else:
                self._send_json_error(500, "Failed to set current version")
        except AssertionError as e:
            self._send_json_error(404, str(e))
        except Exception as e:
            self._send_json_error(500, f"Error restoring image version: {e}")

    def _handle_delete_image_version(self) -> None:
        """Delete the current version of an image."""
        try:
            # Parse path: /asset-group/{name}/delete-version/{screen}
            from urllib.parse import unquote
            import traceback

            logging.info(f"[DELETE_VERSION] ========== HANDLER CALLED ==========")
            logging.info(f"[DELETE_VERSION] Request path: {self.path}")

            path_parts = self.path.split('/')
            logging.info(f"[DELETE_VERSION] Path parts: {path_parts}")

            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None
            screen = path_parts[4] if len(path_parts) > 4 else None

            logging.info(f"[DELETE_VERSION] Asset group: {imageset_name}, Screen: {screen}")

            if not imageset_name or not screen:
                self._send_json_error(400, "Missing asset group name or screen")
                return

            if screen not in ['left', 'center', 'right']:
                self._send_json_error(400, "Invalid screen name")
                return

            # Delete the current version
            result = delete_image_version(imageset_name, screen)
            logging.info(f"[DELETE_VERSION] Delete result: {result}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok'})
            self.wfile.write(response.encode())
            logging.info(f"[DELETE_VERSION] Success")

        except AssertionError as e:
            logging.error(f"[DELETE_VERSION] Assertion failed: {e}")
            self._send_json_error(400, str(e))
        except Exception as e:
            import traceback
            logging.error(f"[DELETE_VERSION] Exception: {e}")
            logging.error(traceback.format_exc())
            self._send_json_error(500, f"Error deleting image version: {str(e)}")

    def _handle_swap_images(self) -> None:
        """Swap two images in an imageset."""
        try:
            # Parse path: /imageset/{name}/swap
            from urllib.parse import unquote
            import shutil
            import tempfile

            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Read request body to get the two screens to swap
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            screen1 = data.get('screen1')
            screen2 = data.get('screen2')

            if not screen1 or not screen2:
                self.send_error(400, "Missing screen1 or screen2")
                return

            if screen1 not in ['left', 'center', 'right'] or screen2 not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen names")
                return

            if screen1 == screen2:
                self.send_error(400, "Cannot swap the same screen")
                return

            # Get the image paths
            image_path1 = get_imageset_image_path(imageset_name, screen1)
            image_path2 = get_imageset_image_path(imageset_name, screen2)

            if not image_path1 or not image_path1.exists():
                self.send_error(404, f"Image not found for {screen1}")
                return

            if not image_path2 or not image_path2.exists():
                self.send_error(404, f"Image not found for {screen2}")
                return

            # Create backups before swapping
            create_image_backup(image_path1)
            create_image_backup(image_path2)

            # Swap the images using a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp_path = Path(tmp.name)

            shutil.copy2(image_path1, tmp_path)
            shutil.copy2(image_path2, image_path1)
            shutil.copy2(tmp_path, image_path2)
            tmp_path.unlink()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'swapped': [screen1, screen2]})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error swapping images: {e}")

    def _handle_copy_image(self) -> None:
        """Copy an image from one screen to another in an imageset."""
        try:
            # Parse path: /imageset/{name}/copy
            from urllib.parse import unquote
            import shutil

            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Read request body to get source and target screens
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            source_screen = data.get('sourceScreen')
            target_screen = data.get('targetScreen')

            if not source_screen or not target_screen:
                self.send_error(400, "Missing sourceScreen or targetScreen")
                return

            if source_screen not in ['left', 'center', 'right'] or target_screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen names")
                return

            if source_screen == target_screen:
                self.send_error(400, "Cannot copy to the same screen")
                return

            # Get the image paths
            source_path = get_imageset_image_path(imageset_name, source_screen)
            target_path = get_imageset_image_path(imageset_name, target_screen)

            if not source_path or not source_path.exists():
                self.send_error(404, f"Source image not found for {source_screen}")
                return

            if not target_path:
                self.send_error(404, f"Target path not found for {target_screen}")
                return

            # Create backup before copying
            if target_path.exists():
                create_image_backup(target_path)

            # Copy the image
            shutil.copy2(source_path, target_path)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'copied': {'source': source_screen, 'target': target_screen}})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error copying image: {e}")

    def _handle_rename_imageset(self) -> None:
        """Rename an imageset (asset group) in the database."""
        try:
            from .db import rename_asset_group_db
            from urllib.parse import unquote

            # Parse path: /asset-group/{name}/rename
            path_parts = self.path.split('/')
            old_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not old_name:
                self._send_json_error(400, "Missing asset group name")
                return

            # Read the new name from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            new_name = data.get('newName', '').strip()

            if not new_name:
                self._send_json_error(400, "Missing new name")
                return

            # Rename in database
            try:
                success = rename_asset_group_db(old_name, new_name)
                if not success:
                    self._send_json_error(404, f"Asset group '{old_name}' not found")
                    return
            except ValueError as e:
                self._send_json_error(400, str(e))
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'oldName': old_name, 'newName': new_name})
            self.wfile.write(response.encode())

            logging.info(f"Renamed asset group '{old_name}' to '{new_name}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json_error(500, f"Error renaming asset group: {e}")

    def _handle_duplicate_imageset(self) -> None:
        """Duplicate an imageset with a new name."""
        try:
            # Parse path: /imageset/{name}/duplicate
            from urllib.parse import unquote
            import shutil

            path_parts = self.path.split('/')
            source_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not source_name:
                self._send_json_error(400, "Missing source imageset name")
                return

            # Read the new name from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            new_name = data.get('newName', '').strip()

            if not new_name:
                self._send_json_error(400, "Missing new name")
                return

            # Validate new name
            if '/' in new_name and new_name.count('/') != 1:
                self._send_json_error(400, "Invalid imageset name format")
                return

            content_dir = get_content_dir()
            img_dir = content_dir / "img"

            # Get source file paths
            source_paths = {}
            for screen in ['left', 'center', 'right']:
                source_paths[screen] = get_imageset_image_path(source_name, screen)
                if not source_paths[screen] or not source_paths[screen].exists():
                    self._send_json_error(404, f"Source image not found for screen: {screen}")
                    return

            # Get source prompt file path
            if '/' in source_name:
                source_parts = source_name.split('/')
                source_prompt_path = img_dir / source_parts[0] / f"{source_parts[1]}.prompt.txt"
            else:
                source_prompt_path = img_dir / "left" / f"{source_name}.prompt.txt"

            # Determine destination paths
            dest_paths = {}
            if '/' in new_name:
                # Playlist-specific imageset
                new_parts = new_name.split('/')
                new_playlist_dir = img_dir / new_parts[0]
                new_base = new_parts[1]

                # Create playlist directory if it doesn't exist
                new_playlist_dir.mkdir(parents=True, exist_ok=True)

                for screen in ['left', 'center', 'right']:
                    source_path = source_paths[screen]
                    ext = source_path.suffix
                    dest_paths[screen] = new_playlist_dir / f"{new_base}.{screen}{ext}"

                dest_prompt_path = new_playlist_dir / f"{new_base}.prompt.txt"
            else:
                # Screen-specific imageset
                for screen in ['left', 'center', 'right']:
                    screen_dir = img_dir / screen
                    screen_dir.mkdir(parents=True, exist_ok=True)

                    source_path = source_paths[screen]
                    ext = source_path.suffix
                    dest_paths[screen] = screen_dir / f"{new_name}{ext}"

                dest_prompt_path = img_dir / "left" / f"{new_name}.prompt.txt"

            # Check if destination already exists
            for screen, dest_path in dest_paths.items():
                if dest_path and dest_path.exists():
                    self._send_json_error(400, f"Imageset '{new_name}' already exists")
                    return

            # Copy all files
            for screen in ['left', 'center', 'right']:
                source_path = source_paths[screen]
                dest_path = dest_paths[screen]

                if source_path and source_path.exists() and dest_path:
                    shutil.copy2(str(source_path), str(dest_path))

            # Copy prompt file if it exists
            if source_prompt_path.exists():
                shutil.copy2(str(source_prompt_path), str(dest_prompt_path))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'sourceName': source_name, 'newName': new_name})
            self.wfile.write(response.encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json_error(500, f"Error duplicating imageset: {e}")

    # Aliases for new asset_group naming
    def _handle_rename_asset_group(self) -> None:
        """Alias for backward compatibility with new asset_group naming."""
        return self._handle_rename_imageset()

    def _handle_duplicate_asset_group(self) -> None:
        """Alias for backward compatibility with new asset_group naming."""
        return self._handle_duplicate_imageset()

    def _handle_save_prompt(self) -> None:
        """Save the prompt file for an imageset."""
        try:
            # Parse path: /imageset/{name}/save-prompt
            from urllib.parse import unquote
            path_parts = self.path.split('/')
            imageset_name = unquote(path_parts[2]) if len(path_parts) > 2 else None

            if not imageset_name:
                self.send_error(400, "Missing imageset name")
                return

            # Read the prompt content
            content_length = int(self.headers.get('Content-Length', 0))
            prompt_content = self.rfile.read(content_length).decode('utf-8')

            # Get the prompt file path
            content_dir = get_content_dir()
            img_dir = content_dir / "img"

            if '/' in imageset_name:
                # Playlist-specific imageset
                parts = imageset_name.split('/')
                playlist_dir = img_dir / parts[0]
                base_name = parts[1]
                prompt_file = playlist_dir / f"{base_name}.prompt.txt"
            else:
                # Screen-specific imageset
                prompt_file = img_dir / "left" / f"{imageset_name}.prompt.txt"

            # Create parent directory if needed
            prompt_file.parent.mkdir(parents=True, exist_ok=True)

            # Save the prompt file
            prompt_file.write_text(prompt_content)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({'status': 'ok', 'saved': str(prompt_file)})
            self.wfile.write(response.encode())
        except Exception as e:
            self.send_error(500, f"Error saving prompt: {e}")

    def _handle_fluff_prompt(self) -> None:
        """Use Gemini to expand a simple prompt into a more descriptive one."""
        try:
            # Read the prompt from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            simple_prompt = data.get('prompt', '').strip()

            if not simple_prompt:
                self.send_error(400, "Missing prompt")
                return

            # Use Gemini to expand the prompt
            try:
                from google import genai
                from triptic.imgen import get_api_key

                api_key = get_api_key()
                if not api_key:
                    self.send_error(500, "No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")
                    return

                client = genai.Client(api_key=api_key)

                # Ask Gemini to expand the prompt following Imagen best practices
                expansion_prompt = f"""You are a prompt engineer for Google's Imagen image generation AI.

Given this simple prompt: "{simple_prompt}"

Expand it into a detailed, descriptive prompt following these best practices:

1. Use descriptive narratives, not just keywords
2. Include specific details about:
   - Photography terminology (lens, composition, lighting setup)
   - Visual style and artistic approach
   - Color palette and mood
   - Textures and materials
   - Atmospheric conditions
3. Be explicit about technical requirements:
   - Aspect ratio: 9:16 (vertical portrait)
   - Resolution and quality level
4. Describe the scene with rich contextual details
5. Keep it focused and coherent - don't add unrelated elements

Generate a single, well-crafted prompt (2-4 sentences) that will produce stunning results with Imagen. Return ONLY the expanded prompt text, nothing else."""

                response = client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=expansion_prompt
                )

                fluffed_prompt = response.text.strip()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response_data = json.dumps({'status': 'ok', 'fluffed_prompt': fluffed_prompt})
                self.wfile.write(response_data.encode())

            except ImportError:
                self.send_error(500, "google-genai is not installed. Install with: uv add google-genai")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Error expanding prompt with Gemini: {e}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error processing request: {e}")

    def _handle_fluff_plus_prompt(self) -> None:
        """Use Gemini to generate 3 sub-prompts from a category prompt."""
        try:
            # Read the category prompt from request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            category_prompt = data.get('prompt', '').strip()

            if not category_prompt:
                self.send_error(400, "Missing prompt")
                return

            # Use Gemini to generate 3 sub-prompts
            try:
                from google import genai
                from triptic.imgen import get_api_key

                api_key = get_api_key()
                if not api_key:
                    self.send_error(500, "No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")
                    return

                client = genai.Client(api_key=api_key)

                # Ask Gemini to generate 3 related sub-prompts
                generation_prompt = f"""You are a prompt engineer for Google's Imagen image generation AI.

Given this category/theme: "{category_prompt}"

Generate exactly 3 related but distinct sub-prompts that would work well as a triptych (three-panel artwork).
Each prompt should be a variation on the theme, offering a different perspective, angle, or interpretation.

Example:
Category: "jazz musician"
Sub-prompts:
1. "jazz pianist performing at a dimly lit club"
2. "saxophone player on a street corner at sunset"
3. "jazz bass player in a recording studio"

Guidelines:
1. Each sub-prompt should be distinct but thematically connected
2. Use descriptive language suitable for image generation
3. Keep each prompt concise (5-15 words)
4. Ensure they work together as a cohesive set
5. Number them 1, 2, 3 for left, center, right panels

Return ONLY the 3 numbered prompts, nothing else. Format as:
1. [prompt for left]
2. [prompt for center]
3. [prompt for right]"""

                response = client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=generation_prompt
                )

                # Parse the response to extract the 3 prompts
                response_text = response.text.strip()
                lines = [line.strip() for line in response_text.split('\n') if line.strip()]

                # Extract prompts from numbered lines
                sub_prompts = {}
                panel_names = ['left', 'center', 'right']

                for i, panel in enumerate(panel_names):
                    # Look for lines starting with "1.", "2.", "3."
                    prefix = f"{i+1}."
                    for line in lines:
                        if line.startswith(prefix):
                            # Remove the number prefix and clean up
                            prompt = line[len(prefix):].strip()
                            sub_prompts[panel] = prompt
                            break

                    # If we didn't find a numbered prompt, fall back to using lines in order
                    if panel not in sub_prompts and i < len(lines):
                        sub_prompts[panel] = lines[i].lstrip('123.-) ').strip()

                # Ensure we have all 3 prompts
                if len(sub_prompts) != 3:
                    self.send_error(500, f"Failed to generate 3 sub-prompts (got {len(sub_prompts)})")
                    return

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response_data = json.dumps({'status': 'ok', 'sub_prompts': sub_prompts})
                self.wfile.write(response_data.encode())

            except ImportError:
                self.send_error(500, "google-genai is not installed. Install with: uv add google-genai")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Error generating sub-prompts with Gemini: {e}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error processing request: {e}")

    def _handle_diff_single_prompt(self) -> None:
        """Use Gemini to generate a single prompt that fits with two others."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            main_prompt = data.get('main_prompt', '').strip()
            screen = data.get('screen', '').strip()
            other_prompts = data.get('other_prompts', {})

            if not screen or screen not in ['left', 'center', 'right']:
                self.send_error(400, "Invalid screen name")
                return

            if len(other_prompts) != 2:
                self.send_error(400, "Need exactly 2 other prompts")
                return

            # Use Gemini to generate a matching prompt
            try:
                from google import genai
                from triptic.imgen import get_api_key

                api_key = get_api_key()
                if not api_key:
                    self.send_error(500, "No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")
                    return

                client = genai.Client(api_key=api_key)

                # Build the prompt for Gemini
                other_screens = [k for k in other_prompts.keys()]
                generation_prompt = f"""You are a prompt engineer for Google's Imagen image generation AI.

You are working on a triptych (three-panel artwork) with the theme: "{main_prompt}"

Two panels already have prompts:
- {other_screens[0].upper()}: "{other_prompts[other_screens[0]]}"
- {other_screens[1].upper()}: "{other_prompts[other_screens[1]]}"

Generate a prompt for the {screen.upper()} panel that:
1. Fits thematically with the existing two prompts
2. Relates to the main theme: "{main_prompt}"
3. Creates a cohesive triptych when combined with the other two
4. Is distinct but complementary to the existing prompts
5. Uses similar style and tone to the other prompts
6. Is concise (5-15 words)

Return ONLY the prompt text, nothing else. No numbering, no explanations."""

                response = client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=generation_prompt
                )

                # Extract the generated prompt
                generated_prompt = response.text.strip()
                # Remove quotes if Gemini added them
                generated_prompt = generated_prompt.strip('"\'')

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response_data = json.dumps({'status': 'ok', 'prompt': generated_prompt})
                self.wfile.write(response_data.encode())

            except ImportError:
                self.send_error(500, "google-genai is not installed. Install with: uv add google-genai")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Error generating prompt with Gemini: {e}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error processing diff-single request: {e}")


class TripticServer:
    """Threaded HTTP server for triptic."""

    def __init__(self, port: int = 3000, host: str = "localhost"):
        self.port = port
        self.host = host
        self.httpd = None
        self.thread = None
        self.running = False

    def start(self) -> None:
        """Start the server in a background thread."""
        public_dir = get_public_dir()

        if not public_dir.exists():
            raise FileNotFoundError(f"Public directory not found: {public_dir}")

        # Initialize SQLite database
        logging.info("Initializing SQLite database...")
        db.init_database()
        logging.info("Database initialized")

        # Run legacy imageset migrations
        logging.info("Running legacy data model migrations...")
        migrate_imagesets_to_asset_groups()
        migrate_playlists_to_new_format()
        logging.info("Migrations complete")

        handler = lambda *args, **kwargs: TripticHandler(
            *args, directory=str(public_dir), **kwargs
        )

        self.httpd = socketserver.TCPServer((self.host, self.port), handler)
        self.httpd.allow_reuse_address = True

        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.running = True

    def stop(self) -> None:
        """Stop the server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.running = False

    def wait(self) -> None:
        """Wait for the server to stop."""
        if self.thread:
            self.thread.join()


def get_state_dir() -> Path:
    """Get the path to the state directory."""
    state_dir = Path.home() / ".state"
    state_dir.mkdir(exist_ok=True)
    return state_dir


def get_state_file() -> Path:
    """Get the path to the state file."""
    return get_state_dir() / "triptic.json"


def read_state() -> dict:
    """Read screen state from file."""
    state_file = get_state_file()

    # Migrate old state file if it exists
    old_state_file = Path.home() / ".triptic.state"
    if old_state_file.exists() and not state_file.exists():
        try:
            shutil.copy2(old_state_file, state_file)
            logging.info(f"Migrated state from {old_state_file} to {state_file}")
        except Exception as e:
            logging.warning(f"Could not migrate old state file: {e}")

    if not state_file.exists():
        return {}
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def write_state(state: dict) -> None:
    """Write screen state to file."""
    state_file = get_state_file()
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logging.warning(f"Could not write state file: {e}")


def update_screen_heartbeat(screen_id: str) -> None:
    """Update the heartbeat timestamp for a screen."""
    db.update_screen_heartbeat_db(screen_id, datetime.now().isoformat())


def get_config() -> dict:
    """Get configuration from SQLite database."""
    return {
        'frequency': db.get_setting_db('frequency', 60)  # Default to 60 seconds
    }


def update_config(config: dict) -> None:
    """Update configuration in SQLite database."""
    if 'frequency' in config:
        db.set_setting_db('frequency', config['frequency'])


def get_settings() -> dict:
    """Get settings from SQLite database."""
    # Load API key from .env if not in settings
    gemini_api_key = db.get_setting_db('gemini_api_key', '')
    if not gemini_api_key:
        # Try to read from .env file
        env_file = Path.cwd() / '.env'
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY='):
                        gemini_api_key = line.split('=', 1)[1].strip()
                        break

    return {
        'model': db.get_setting_db('model', 'imagen-4.0-fast-generate-001'),
        'video_model': db.get_setting_db('video_model', 'veo-2.0-generate-001'),
        'gemini_api_key': gemini_api_key,
        'grok_api_key': db.get_setting_db('grok_api_key', '')
    }


def update_settings(settings: dict) -> None:
    """Update settings in SQLite database."""
    if 'model' in settings:
        db.set_setting_db('model', settings['model'])
    if 'video_model' in settings:
        db.set_setting_db('video_model', settings['video_model'])
    if 'gemini_api_key' in settings:
        db.set_setting_db('gemini_api_key', settings['gemini_api_key'])
    if 'grok_api_key' in settings:
        db.set_setting_db('grok_api_key', settings['grok_api_key'])


def get_default_playlists() -> dict:
    """Get default playlists using imageset names."""
    return {
        'animals': [f'animals/{i}' for i in [1, 3, 5, 7, 9, 2, 4, 6, 8, 10]],
        'numbers': [f'numbers/{i}' for i in range(1, 11)],
        'letters': [f'letters/{i}' for i in [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]]
    }


def get_playlists() -> dict:
    """Get all playlists."""
    state = read_state()
    if 'playlists' not in state:
        state['playlists'] = get_default_playlists()
        write_state(state)
    return state['playlists']


def get_current_playlist() -> str:
    """Get the current playlist name from SQLite database."""
    return db.get_setting_db('current_playlist', 'letters')


def set_current_playlist(playlist_name: str) -> bool:
    """Set the current playlist in SQLite database."""
    playlists = get_all_playlists()
    if playlist_name not in playlists:
        return False
    db.set_setting_db('current_playlist', playlist_name)
    return True


def add_to_playlist(playlist_name: str, asset_id: str) -> bool:
    """
    Add an asset group to a playlist.

    Args:
        playlist_name: Name of the playlist to add to
        asset_id: ID of the asset group to add (e.g., 'animals-1')

    Returns:
        True if successful, False if playlist doesn't exist
    """
    playlists = get_all_playlists()
    if playlist_name not in playlists:
        return False

    playlist = playlists[playlist_name]
    # Add to playlist if not already present
    if asset_id not in playlist.assets:
        playlist.assets.append(asset_id)
        save_playlist(playlist)

    return True


def remove_from_playlist(playlist_name: str, asset_id: str) -> bool:
    """
    Remove an asset group from a playlist.

    Args:
        playlist_name: Name of the playlist to remove from
        asset_id: ID of the asset group to remove (e.g., 'animals-1')

    Returns:
        True if successful, False if playlist doesn't exist or asset not in playlist
    """
    playlists = get_all_playlists()
    if playlist_name not in playlists:
        return False

    playlist = playlists[playlist_name]
    if asset_id in playlist.assets:
        playlist.assets.remove(asset_id)
        # Adjust current position if needed
        if playlist.current_position >= len(playlist.assets) and playlist.assets:
            playlist.current_position = len(playlist.assets) - 1
        elif not playlist.assets:
            playlist.current_position = 0
        save_playlist(playlist)
        return True

    return False


def reorder_playlist(playlist_name: str, new_order: list) -> bool:
    """
    Reorder asset groups in a playlist.

    Args:
        playlist_name: Name of the playlist to reorder
        new_order: List of asset group IDs in the new order

    Returns:
        True if successful, False if playlist doesn't exist
    """
    playlists = get_all_playlists()
    if playlist_name not in playlists:
        return False

    playlist = playlists[playlist_name]
    playlist.assets = new_order
    # Reset position if it's out of bounds
    if playlist.current_position >= len(playlist.assets):
        playlist.current_position = max(0, len(playlist.assets) - 1)
    save_playlist(playlist)
    return True


def get_playlist_items(playlist_name: str = None) -> list:
    """
    Get items from a playlist, resolving asset group names to image URLs.

    Returns: [{'left': 'url', 'center': 'url', 'right': 'url', 'name': 'asset_group_name'}, ...]
    """
    from . import storage

    if playlist_name is None:
        playlist_name = get_current_playlist()

    # Get playlist from database
    playlist_data = db.get_playlist_db(playlist_name)
    if not playlist_data:
        return []

    asset_group_names = playlist_data.get('assets', [])
    if not asset_group_names:
        return []

    # Get all asset groups from database
    all_groups = get_asset_groups()

    result = []
    for asset_group_name in asset_group_names:
        if asset_group_name in all_groups:
            asset_group = all_groups[asset_group_name]

            # Build item with image URLs for each screen
            item = {'name': asset_group_name}

            for screen in ['left', 'center', 'right']:
                screen_asset = getattr(asset_group, screen)
                if screen_asset and screen_asset.versions:
                    # Get current version using UUID-based method
                    current_version = screen_asset.get_current_version()

                    if current_version:
                        content_uuid = current_version.content

                        # Build URL
                        if content_uuid and not content_uuid.startswith('img/'):
                            # UUID-based path (no version suffix needed)
                            item[screen] = f"/content/assets/{content_uuid}.png"
                        else:
                            # Fallback
                            item[screen] = f"/img/{screen}/{asset_group_name}.png"
                    else:
                        # No current version - use placeholder
                        item[screen] = f"/img/{screen}/{asset_group_name}.png"
                else:
                    # No versions - use placeholder
                    item[screen] = f"/img/{screen}/{asset_group_name}.png"

            result.append(item)
        else:
            logging.warning(f"Asset group '{asset_group_name}' in playlist '{playlist_name}' not found in database")

    return result


# Asset Group Management Functions (SQLite-backed)
def get_asset_groups() -> dict[str, AssetGroup]:
    """Get all asset groups from SQLite database."""
    groups_data = db.get_all_asset_groups_db()
    return {
        group_id: AssetGroup.from_dict(data)
        for group_id, data in groups_data.items()
    }


def get_asset_group(group_id: str) -> Optional[AssetGroup]:
    """Get a specific asset group by ID from SQLite database."""
    group_data = db.get_asset_group_db(group_id)
    if group_data:
        return AssetGroup.from_dict(group_data)
    return None


def save_asset_group(asset_group: AssetGroup) -> None:
    """Save or update an asset group in SQLite database."""
    db.save_asset_group_db(
        asset_group.id,
        asset_group.left,
        asset_group.center,
        asset_group.right
    )
    logging.info(f"Saved asset group: {asset_group.id}")


def delete_asset_group(group_id: str) -> bool:
    """Delete an asset group from SQLite database."""
    success = db.delete_asset_group_db(group_id)
    if success:
        logging.info(f"Deleted asset group: {group_id}")
    return success


def get_all_playlists() -> dict[str, Playlist]:
    """Get all playlists as Playlist objects from SQLite database."""
    playlists_data = db.get_all_playlists_db()
    return {
        name: Playlist.from_dict(data)
        for name, data in playlists_data.items()
    }


def save_playlist(playlist: Playlist) -> None:
    """Save or update a playlist in SQLite database."""
    db.save_playlist_db(playlist.name, playlist.assets, playlist.current_position)
    logging.info(f"Saved playlist: {playlist.name}")


def delete_playlist(name: str) -> bool:
    """Delete a playlist from SQLite database."""
    success = db.delete_playlist_db(name)
    if success:
        logging.info(f"Deleted playlist: {name}")
    return success


def rename_playlist(old_name: str, new_name: str) -> bool:
    """Rename a playlist in SQLite database."""
    success = db.rename_playlist_db(old_name, new_name)
    if success:
        logging.info(f"Renamed playlist: '{old_name}' -> '{new_name}'")
    return success


def migrate_imagesets_to_asset_groups() -> None:
    """
    Migrate existing filesystem imagesets to asset_groups in state.
    Creates AssetGroup objects for any discovered imagesets that don't have one.
    """
    imagesets = discover_imagesets()
    asset_groups = get_asset_groups()

    for imageset_name, files in imagesets.items():
        # Skip png/ prefixed imagesets (legacy duplicates)
        if imageset_name.startswith('png/'):
            continue

        # Skip if asset_group already exists
        if imageset_name in asset_groups:
            continue

        logging.info(f"Migrating imageset '{imageset_name}' to asset_group")

        # Create asset_group with single version for each screen
        asset_group = AssetGroup(id=imageset_name)

        # Add version for each screen if file exists
        for screen in ['left', 'center', 'right']:
            if screen in files:
                version = AssetVersion(
                    content=files[screen],
                    prompt=f"Legacy imageset: {imageset_name}",
                    timestamp=datetime.now().isoformat()
                )
                getattr(asset_group, screen).add_version(version)

        save_asset_group(asset_group)

    logging.info(f"Migrated {len(imagesets) - len(asset_groups)} imagesets to asset_groups")


def migrate_playlists_to_new_format() -> None:
    """
    Migrate old-style playlists (list of strings) to new Playlist objects.
    """
    state = read_state()
    if 'playlists' not in state:
        return

    playlists_to_migrate = []
    for name, data in state['playlists'].items():
        # Skip if already new format
        if isinstance(data, dict) and 'assets' in data:
            continue
        playlists_to_migrate.append((name, data))

    for name, old_data in playlists_to_migrate:
        if isinstance(old_data, list):
            # Convert list of imageset names to Playlist object
            playlist = Playlist(name=name, assets=old_data, current_position=0)
            save_playlist(playlist)
            logging.info(f"Migrated playlist '{name}' to new format with {len(old_data)} assets")


def discover_imagesets(prefix: str = None) -> dict:
    """
    Discover image sets in the public/img directory.

    Supports two patterns:
    1. New pattern: img/prefix/name.screen.ext (e.g., img/numbers/1.left.png)
    2. Old pattern: img/screen/name.ext (e.g., img/left/1.svg) - grouped by extension

    Returns a dict mapping imageset names to their files:
    {
        'numbers/1': {'left': 'img/numbers/1.left.png', 'center': ..., 'right': ...},
        'svg/1': {'left': 'img/left/1.svg', 'center': ..., 'right': ...},
    }
    """
    try:
        public_dir = get_public_dir()
        img_dir = public_dir / "img"

        if not img_dir.exists():
            return {}

        # Collect all image files
        imagesets = defaultdict(dict)
        old_pattern_files = defaultdict(lambda: defaultdict(dict))  # {ext: {name: {screen: path}}}
        screens = ['left', 'center', 'right']
        extensions = ['.png', '.jpg', '.jpeg', '.svg', '.gif', '.mp4', '.webm']

        # Walk through all files in img directory
        for file_path in img_dir.rglob('*'):
            if not file_path.is_file():
                continue

            # Check if it has a valid extension
            ext = file_path.suffix.lower()
            if ext not in extensions:
                continue

            # Get relative path from img directory
            rel_path = file_path.relative_to(img_dir)

            # Check if parent directory is a screen name (old pattern)
            parent_name = rel_path.parent.name
            if parent_name in screens:
                # Old pattern: screen/name.ext
                name = file_path.stem
                screen = parent_name
                ext_name = ext[1:]  # Remove the dot
                imageset_name = f"{ext_name}/{name}"
                old_pattern_files[ext_name][name][screen] = f"img/{rel_path}".replace('\\', '/')
                continue

            # Try new pattern: name.screen.ext
            parts = file_path.stem.split('.')
            if len(parts) >= 2:
                # Last part before extension should be the screen
                screen = parts[-1]
                if screen in screens:
                    # Everything before the screen is the imageset name
                    name_parts = parts[:-1]
                    name = '.'.join(name_parts)

                    # Include parent directories in the name (but not if parent is '.')
                    if rel_path.parent != Path('.'):
                        name = str(rel_path.parent / name).replace('\\', '/')

                    # Store the relative path from public root
                    relative_from_public = f"img/{rel_path}".replace('\\', '/')
                    imagesets[name][screen] = relative_from_public

        # Add old pattern files to imagesets
        for ext_name, names_dict in old_pattern_files.items():
            for name, screens_dict in names_dict.items():
                imageset_name = f"{ext_name}/{name}"
                imagesets[imageset_name] = screens_dict

        # Apply prefix filter and only return complete imagesets
        complete_sets = {}
        for name, screens_dict in imagesets.items():
            # Apply prefix filter if specified
            if prefix and not name.startswith(prefix):
                continue

            # Must have all 3 screens
            if len(screens_dict) == 3:
                complete_sets[name] = screens_dict

        return complete_sets

    except Exception as e:
        logging.error(f"Error discovering imagesets: {e}")
        return {}


def list_imagesets(prefix: str = None) -> list:
    """
    List image sets, optionally filtered by prefix.

    Returns a sorted list of tuples: [(name, files_dict), ...]
    """
    imagesets = discover_imagesets(prefix)
    return sorted(imagesets.items())


def read_imageset_prompt(imageset_name: str, screen: str = None) -> str | None:
    """
    Read a prompt from an imageset's .prompt.txt file.

    Args:
        imageset_name: Name of the imageset (e.g., "animals/banana")
        screen: Screen position (left, center, right). If None, returns main prompt.

    Returns:
        The prompt text, or None if not found
    """
    content_dir = get_content_dir()
    img_dir = content_dir / "img"

    if '/' in imageset_name:
        # Playlist-specific imageset
        parts = imageset_name.split('/')
        prompt_file = img_dir / parts[0] / f"{parts[1]}.prompt.txt"
    else:
        # Screen-specific imageset
        prompt_file = img_dir / "left" / f"{imageset_name}.prompt.txt"

    if not prompt_file.exists():
        return None

    try:
        content = prompt_file.read_text()
        # Parse the prompt from the file
        if screen:
            # Look for screen-specific prompt
            screen_key = f"{screen.capitalize()}:"
            for line in content.split('\n'):
                if line.startswith(screen_key):
                    return line.replace(screen_key, '').strip()
            # If screen prompt not found, fall back to main prompt
            for line in content.split('\n'):
                if line.startswith('Main prompt:'):
                    return line.replace('Main prompt:', '').strip()
        else:
            # Return main prompt
            for line in content.split('\n'):
                if line.startswith('Main prompt:'):
                    return line.replace('Main prompt:', '').strip()
    except Exception as e:
        logging.error(f"Error reading prompt file: {e}")

    return None


def get_imageset_image_path(imageset_name: str, screen: str, version: int | None = None) -> Path | None:
    """
    Get the file path for a specific image in an imageset.

    Args:
        imageset_name: Name of the imageset
        screen: Screen position (left, center, right)
        version: Specific version (1-9), or None for current version from DB

    Returns:
        Path to the image file (may be versioned like .v3.png)
    """
    from . import storage

    # Get the base file path (UUID-based)
    file_path = storage.get_asset_file_path_by_group(imageset_name, screen)
    assert file_path, f"Asset not found: {imageset_name}/{screen}"

    # If no specific version requested, use current from database
    if version is None:
        version = storage.get_current_version_number(imageset_name, screen)

    # Return versioned path if not version 9
    if version < 9:
        base_path = file_path.parent / file_path.stem
        ext = file_path.suffix
        return Path(f"{base_path}.v{version}{ext}")

    return file_path


def create_image_backup(image_path: Path) -> None:
    """
    Create a backup of an image file, keeping the last 9 versions.

    Versions are numbered 1-9, where version 1 is the oldest and version 9 is the current.
    Backups are named: filename.v1.ext, filename.v2.ext, ..., filename.v8.ext
    The current file (no version suffix) is considered version 9.

    When creating a new backup:
    - v1 is deleted (oldest)
    - v2 -> v1, v3 -> v2, ... v8 -> v7
    - current -> v8

    Args:
        image_path: Path to the image file to backup
    """
    if not image_path.exists():
        return

    # Get the base path without extension
    base_path = image_path.parent / image_path.stem
    ext = image_path.suffix

    # Remove oldest backup (v1) if it exists
    v1_path = Path(f"{base_path}.v1{ext}")
    if v1_path.exists():
        v1_path.unlink()

    # Rotate existing backups: v2->v1, v3->v2, ..., v8->v7
    for i in range(2, 9):
        old_path = Path(f"{base_path}.v{i}{ext}")
        new_path = Path(f"{base_path}.v{i-1}{ext}")
        if old_path.exists():
            old_path.rename(new_path)

    # Create new backup from current file (current -> v8)
    v8_path = Path(f"{base_path}.v8{ext}")
    shutil.copy2(image_path, v8_path)


def get_image_versions_by_uuid(content_uuid: str) -> list[int]:
    """
    Get a list of available version numbers for an image by UUID.

    Args:
        content_uuid: UUID of the asset

    Returns:
        List of version numbers (1-9) that exist for this image
    """
    from . import storage

    versions = []
    assets_dir = storage.get_assets_dir()

    # Check for versions 1-8
    for i in range(1, 9):
        version_path = assets_dir / f"{content_uuid}.v{i}.png"
        if version_path.exists():
            versions.append(i)

    # Check if main file exists (version 9)
    main_path = assets_dir / f"{content_uuid}.png"
    if main_path.exists():
        versions.append(9)

    return versions


def get_image_versions(image_path: Path) -> list[int]:
    """
    Get a list of available version numbers for an image.

    Args:
        image_path: Path to the current image file

    Returns:
        List of version numbers (1-9) that exist for this image
    """
    versions = []
    base_path = image_path.parent / image_path.stem
    ext = image_path.suffix

    # Check for versions 1-8
    for i in range(1, 9):
        version_path = Path(f"{base_path}.v{i}{ext}")
        if version_path.exists():
            versions.append(i)

    # Check if current file exists (version 9)
    if image_path.exists():
        versions.append(9)

    return versions


def compact_image_versions(image_path: Path) -> None:
    """
    Compact version files so they fill 1-9 with newest always being 9.

    This reorganizes version files to remove gaps in the sequence.

    Args:
        image_path: Path to the current image file
    """
    base_path = image_path.parent / image_path.stem
    ext = image_path.suffix

    # Collect all existing versions (excluding current/9)
    existing_versions = []
    for i in range(1, 9):
        version_path = Path(f"{base_path}.v{i}{ext}")
        if version_path.exists():
            existing_versions.append((i, version_path))

    # If no compaction needed (versions are sequential starting from 1)
    if not existing_versions or (len(existing_versions) == existing_versions[-1][0]):
        return

    # Rename versions to fill gaps starting from 1
    temp_suffix = ".tmp_version"
    renamed_versions = []

    # First pass: rename to temporary names to avoid conflicts
    for new_idx, (old_idx, old_path) in enumerate(existing_versions, start=1):
        if new_idx != old_idx:
            temp_path = Path(f"{base_path}.v{new_idx}{temp_suffix}{ext}")
            shutil.move(str(old_path), str(temp_path))
            renamed_versions.append((new_idx, temp_path))
        else:
            renamed_versions.append((new_idx, old_path))

    # Second pass: rename from temp names to final names
    for idx, temp_path in renamed_versions:
        final_path = Path(f"{base_path}.v{idx}{ext}")
        if temp_suffix in str(temp_path):
            shutil.move(str(temp_path), str(final_path))


def restore_image_version(asset_group_id: str, screen: str, version: int) -> bool:
    """
    Set a specific version as current (database-only operation).

    Args:
        asset_group_id: Asset group identifier
        screen: Screen position (left/center/right)
        version: Version number to set as current (1-N where N is number of versions)

    Returns:
        True if successful
    """
    assert version >= 1, f"Version must be >= 1, got {version}"

    # Get asset group from database
    asset_group = get_asset_group(asset_group_id)
    assert asset_group, f"Asset group not found: {asset_group_id}"

    # Get the screen asset
    screen_asset = getattr(asset_group, screen)
    assert screen_asset.versions, f"No versions found for {asset_group_id}/{screen}"

    # Map version number (1-N) to array index
    # Version 1 = oldest (index 0)
    # Version 2 = second oldest (index 1), etc.
    # Version N = newest (index N-1)
    version_count = len(screen_asset.versions)

    assert version <= version_count, f"Version {version} not available (only versions 1-{version_count} exist)"

    # Calculate array index: version 1 -> index 0, version 2 -> index 1, etc.
    array_index = version - 1
    assert 0 <= array_index < version_count, f"Invalid version mapping: {version} -> index {array_index}"

    # Set this version as current
    target_version = screen_asset.versions[array_index]
    screen_asset.current_version_uuid = target_version.version_uuid

    # Save to database
    save_asset_group(asset_group)
    return True


def delete_image_version(asset_group_id: str, screen: str) -> bool:
    """
    Delete the currently selected version from database and switch to previous version.

    Args:
        asset_group_id: Asset group identifier
        screen: Screen position (left/center/right)

    Returns:
        True if successful
    """
    # Get asset group from database
    asset_group = get_asset_group(asset_group_id)
    assert asset_group, f"Asset group not found: {asset_group_id}"

    # Get the screen asset
    screen_asset = getattr(asset_group, screen)
    assert screen_asset.versions, f"No versions found for {asset_group_id}/{screen}"
    assert len(screen_asset.versions) > 1, "Cannot delete last remaining version"

    # Find the current version in the versions list
    current_uuid = screen_asset.current_version_uuid
    current_index = None
    for i, version in enumerate(screen_asset.versions):
        if version.version_uuid == current_uuid:
            current_index = i
            break

    assert current_index is not None, "Current version not found in versions list"

    # Remove the current version from the list
    deleted_version = screen_asset.versions.pop(current_index)
    logging.info(f"Deleted version {deleted_version.version_uuid} from {asset_group_id}/{screen}")

    # Set the most recent remaining version as current (last in list)
    if screen_asset.versions:
        screen_asset.current_version_uuid = screen_asset.versions[-1].version_uuid
    else:
        # This shouldn't happen due to the assertion above, but be safe
        screen_asset.current_version_uuid = None

    # Save to database
    save_asset_group(asset_group)
    return True


def delete_imageset(imageset_name: str) -> bool:
    """
    Delete an imageset and all its associated files.

    Args:
        imageset_name: Name of the imageset (e.g., "animals/banana" or "test")

    Returns:
        True if deleted successfully, False if not found
    """
    content_dir = get_content_dir()
    img_dir = content_dir / "img"

    # Parse imageset name to get directory and base name
    if '/' in imageset_name:
        # Playlist-specific imageset (e.g., "animals/banana")
        parts = imageset_name.split('/')
        playlist_dir = img_dir / parts[0]
        base_name = parts[1]

        # Delete all files for this imageset
        import glob
        pattern = str(playlist_dir / f"{base_name}.*")
        files = glob.glob(pattern)

        if not files:
            return False

        for file_path in files:
            Path(file_path).unlink()
            logging.info(f"Deleted: {file_path}")

        # Remove from all playlists
        state = read_state()
        playlists = state.get('playlists', {})
        for playlist_name, items in playlists.items():
            if imageset_name in items:
                items.remove(imageset_name)
        write_state(state)

        return True
    else:
        # Screen-specific imageset (left/center/right directories)
        found = False
        for screen in ['left', 'center', 'right']:
            screen_dir = img_dir / screen
            if not screen_dir.exists():
                continue

            import glob
            pattern = str(screen_dir / f"{imageset_name}.*")
            files = glob.glob(pattern)

            for file_path in files:
                Path(file_path).unlink()
                logging.info(f"Deleted: {file_path}")
                found = True

        return found


def get_content_dir() -> Path:
    """Get the path to the content directory."""
    import os

    # Check for environment variable override (e.g., for production deployment)
    if 'TRIPTIC_CONTENT_DIR' in os.environ:
        content_dir = Path(os.environ['TRIPTIC_CONTENT_DIR'])
    # Check if /data exists (Fly.io persistent volume)
    elif Path('/data').exists() and Path('/data').is_dir():
        content_dir = Path('/data/content')
    else:
        content_dir = Path.home() / ".triptic" / "content"

    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir


def get_public_dir() -> Path:
    """Get the path to the public directory."""
    # Try relative to this file first
    module_dir = Path(__file__).parent
    public_dir = module_dir.parent.parent / "public"

    if public_dir.exists():
        return public_dir.resolve()

    # Try current working directory
    cwd_public = Path.cwd() / "public"
    if cwd_public.exists():
        return cwd_public.resolve()

    # Try TRIPTIC_PUBLIC_DIR environment variable
    env_dir = os.environ.get("TRIPTIC_PUBLIC_DIR")
    if env_dir:
        env_path = Path(env_dir)
        if env_path.exists():
            return env_path.resolve()

    raise FileNotFoundError("Could not find public directory")


def ensure_content_symlink() -> None:
    """Ensure public/img is symlinked to ~/.triptic/content/img."""
    public_dir = get_public_dir()
    public_img = public_dir / "img"
    content_img = get_content_dir() / "img"

    # Create content img directory
    content_img.mkdir(parents=True, exist_ok=True)

    # Remove existing img if it's not a symlink
    if public_img.exists() and not public_img.is_symlink():
        import shutil
        logging.warning(f"{public_img} exists but is not a symlink. Moving to {public_img}.backup")
        shutil.move(str(public_img), str(public_img) + ".backup")

    # Create symlink if it doesn't exist
    if not public_img.exists():
        public_img.symlink_to(content_img)
        logging.info(f"Created symlink: {public_img} -> {content_img}")


def run_server(port: int = 3000, host: str = "localhost") -> None:
    """Run the server in the foreground."""
    # Set up logging first
    setup_logging()

    public_dir = get_public_dir()

    # Ensure content directory and symlink are set up
    ensure_content_symlink()

    # Initialize SQLite database
    logging.info("Initializing SQLite database...")
    db.init_database()
    logging.info("Database initialized")

    # Run UUID versioning migration
    db.migrate_to_uuid_versioning()

    # Initialize default placeholder assets
    logging.info("Initializing default assets...")
    storage.initialize_default_assets()
    logging.info("Default assets initialized")

    logging.info(f"Serving from: {public_dir}")
    logging.info(f"Content dir: {get_content_dir()}")
    logging.info(f"Server running at http://{host}:{port}")
    logging.info("")
    logging.info("URLs:")
    logging.info(f"  Dashboard:  http://{host}:{port}/")
    logging.info(f"  Playlists:  http://{host}:{port}/playlists.html")
    logging.info(f"  Left:       http://{host}:{port}/?id=left")
    logging.info(f"  Center:     http://{host}:{port}/?id=center")
    logging.info(f"  Right:      http://{host}:{port}/?id=right")
    logging.info("")
    logging.info("Press Ctrl+C to stop")

    handler = lambda *args, **kwargs: TripticHandler(
        *args, directory=str(public_dir), **kwargs
    )

    # Set allow_reuse_address before creating the server
    socketserver.TCPServer.allow_reuse_address = True

    httpd = socketserver.TCPServer((host, port), handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("\nShutting down...")
    finally:
        httpd.shutdown()
        httpd.server_close()
        logging.info("Server stopped")
