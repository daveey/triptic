"""HTTP server for triptic."""

import http.server
import json
import os
import shutil
import socketserver
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class TripticHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves from the public directory."""

    def __init__(self, *args, directory: str = None, **kwargs):
        self.public_dir = directory or str(get_public_dir())
        super().__init__(*args, directory=self.public_dir, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Log HTTP requests."""
        print(f"[triptic] {args[0]} {args[1]} {args[2]}")

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == '/config':
            self._handle_get_config()
        elif self.path == '/playlist':
            self._handle_get_playlist()
        elif self.path == '/playlists':
            self._handle_get_playlists()
        elif self.path.startswith('/playlists/'):
            self._handle_get_playlist_by_name()
        elif self.path.startswith('/imagesets'):
            self._handle_get_imagesets()
        elif self.path == '/' or self.path == '':
            # Redirect root to dashboard
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
        else:
            # Delegate to parent for static file serving
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
        if self.path.startswith('/heartbeat/'):
            screen_id = self.path.split('/')[-1]
            self._handle_heartbeat(screen_id)
        elif self.path == '/config':
            self._handle_post_config()
        elif self.path == '/playlist':
            self._handle_set_playlist()
        else:
            self.send_error(404, "Not found")

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
            playlists = get_playlists()
            current = get_current_playlist()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            response = json.dumps({
                'playlists': list(playlists.keys()),
                'current': current
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
            print(f"[triptic] Migrated state from {old_state_file} to {state_file}")
        except Exception as e:
            print(f"[triptic] Warning: Could not migrate old state file: {e}")

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
        print(f"[triptic] Warning: Could not write state file: {e}")


def update_screen_heartbeat(screen_id: str) -> None:
    """Update the heartbeat timestamp for a screen."""
    state = read_state()
    if 'screens' not in state:
        state['screens'] = {}
    state['screens'][screen_id] = {
        'last_sync': datetime.now().isoformat()
    }
    write_state(state)


def get_config() -> dict:
    """Get configuration."""
    state = read_state()
    return {
        'frequency': state.get('frequency', 60)  # Default to 60 seconds
    }


def update_config(config: dict) -> None:
    """Update configuration."""
    state = read_state()
    if 'frequency' in config:
        state['frequency'] = config['frequency']
    write_state(state)


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
    """Get the current playlist name."""
    state = read_state()
    return state.get('current_playlist', 'letters')


def set_current_playlist(playlist_name: str) -> bool:
    """Set the current playlist."""
    playlists = get_playlists()
    if playlist_name not in playlists:
        return False
    state = read_state()
    state['current_playlist'] = playlist_name
    write_state(state)
    return True


def add_to_playlist(playlist_name: str, imageset_name: str) -> bool:
    """
    Add an imageset to a playlist.

    Args:
        playlist_name: Name of the playlist to add to
        imageset_name: Name of the imageset to add (e.g., 'animals/11')

    Returns:
        True if successful, False if playlist doesn't exist
    """
    state = read_state()
    if 'playlists' not in state:
        state['playlists'] = get_default_playlists()

    if playlist_name not in state['playlists']:
        return False

    # Add to playlist if not already present
    if imageset_name not in state['playlists'][playlist_name]:
        state['playlists'][playlist_name].append(imageset_name)
        write_state(state)

    return True


def get_playlist_items(playlist_name: str = None) -> list:
    """
    Get items from a playlist, resolving imageset names to file paths.

    Supports both:
    - New format: ['svg/1', 'svg/2', ...] (imageset names)
    - Old format: [{'left': '...', 'center': '...', 'right': '...'}, ...] (explicit paths)

    Returns: [{'left': 'path', 'center': 'path', 'right': 'path'}, ...]
    """
    if playlist_name is None:
        playlist_name = get_current_playlist()

    playlists = get_playlists()
    playlist = playlists.get(playlist_name, [])

    if not playlist:
        return []

    # Resolve imageset names to file paths
    result = []
    imagesets = discover_imagesets()  # Get all available imagesets

    for item in playlist:
        if isinstance(item, str):
            # New format: imageset name
            if item in imagesets:
                result.append(imagesets[item])
            else:
                print(f"[triptic] Warning: imageset '{item}' not found")
        elif isinstance(item, dict):
            # Old format: explicit paths (backward compatibility)
            result.append(item)
        else:
            print(f"[triptic] Warning: invalid playlist item: {item}")

    return result


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
        print(f"[triptic] Error discovering imagesets: {e}")
        return {}


def list_imagesets(prefix: str = None) -> list:
    """
    List image sets, optionally filtered by prefix.

    Returns a sorted list of tuples: [(name, files_dict), ...]
    """
    imagesets = discover_imagesets(prefix)
    return sorted(imagesets.items())


def get_content_dir() -> Path:
    """Get the path to the content directory."""
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
        print(f"[triptic] Warning: {public_img} exists but is not a symlink. Moving to {public_img}.backup")
        shutil.move(str(public_img), str(public_img) + ".backup")

    # Create symlink if it doesn't exist
    if not public_img.exists():
        public_img.symlink_to(content_img)
        print(f"[triptic] Created symlink: {public_img} -> {content_img}")


def run_server(port: int = 3000, host: str = "localhost") -> None:
    """Run the server in the foreground."""
    public_dir = get_public_dir()

    # Ensure content directory and symlink are set up
    ensure_content_symlink()

    print(f"[triptic] Serving from: {public_dir}")
    print(f"[triptic] Content dir: {get_content_dir()}")
    print(f"[triptic] Server running at http://{host}:{port}")
    print(f"\n[triptic] URLs:")
    print(f"  Dashboard:  http://{host}:{port}/")
    print(f"  Playlists:  http://{host}:{port}/playlists.html")
    print(f"  Left:       http://{host}:{port}/?id=left")
    print(f"  Center:     http://{host}:{port}/?id=center")
    print(f"  Right:      http://{host}:{port}/?id=right")
    print(f"\n[triptic] Press Ctrl+C to stop")

    handler = lambda *args, **kwargs: TripticHandler(
        *args, directory=str(public_dir), **kwargs
    )

    # Set allow_reuse_address before creating the server
    socketserver.TCPServer.allow_reuse_address = True

    httpd = socketserver.TCPServer((host, port), handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[triptic] Shutting down...")
    finally:
        httpd.shutdown()
        httpd.server_close()
        print("[triptic] Server stopped")
