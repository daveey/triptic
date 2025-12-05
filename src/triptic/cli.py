"""Command-line interface for triptic."""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from triptic.server import (
    TripticServer,
    add_to_playlist,
    get_content_dir,
    get_playlists,
    get_public_dir,
    list_imagesets,
    run_server,
    set_current_playlist,
)


def get_pid_file(port: int = 3000) -> Path:
    """Get the path to the PID file for a specific port."""
    return Path.home() / f".triptic_{port}.pid"


def read_pid(port: int = 3000) -> int | None:
    """Read the PID from the PID file for a specific port."""
    pid_file = get_pid_file(port)
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def write_pid(pid: int, port: int = 3000) -> None:
    """Write the PID to the PID file for a specific port."""
    get_pid_file(port).write_text(str(pid))


def remove_pid(port: int = 3000) -> None:
    """Remove the PID file for a specific port."""
    pid_file = get_pid_file(port)
    if pid_file.exists():
        pid_file.unlink()


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_state_file() -> Path:
    """Get the path to the state file."""
    return Path.home() / ".triptic.state"


def read_screen_states() -> dict:
    """Read screen states from the state file."""
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
            return state.get('screens', {})
    except (json.JSONDecodeError, IOError):
        return {}


def format_time_since(iso_timestamp: str) -> str:
    """Format time since a timestamp in a human-readable way."""
    try:
        last_sync = datetime.fromisoformat(iso_timestamp)
        now = datetime.now()
        delta = now - last_sync

        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"
    except (ValueError, AttributeError):
        return "unknown"


def cmd_start(args: argparse.Namespace) -> int:
    """Start the triptic server."""
    port = args.port
    host = args.host

    # Check if already running on this port
    pid = read_pid(port)
    if pid and is_process_running(pid):
        print(f"[triptic] Server already running on port {port} (PID: {pid})")
        return 1

    # Set database path if provided
    if hasattr(args, 'database') and args.database:
        os.environ['TRIPTIC_DB_PATH'] = args.database
        print(f"[triptic] Using database: {args.database}")

    if args.daemon:
        # Fork and run in background
        pid = os.fork()
        if pid > 0:
            # Parent process
            write_pid(pid, port)
            print(f"[triptic] Server started in background (PID: {pid})")
            print(f"[triptic] Listening at http://{host}:{port}")
            print(f"\n[triptic] URLs:")
            print(f"  Wall:       http://{host}:{port}/wall.html")
            print(f"  Playlists:  http://{host}:{port}/playlists.html")
            print(f"  Left:       http://{host}:{port}/#left")
            print(f"  Center:     http://{host}:{port}/#center")
            print(f"  Right:      http://{host}:{port}/#right")
            return 0
        else:
            # Child process - run server
            try:
                run_server(port=port, host=host)
            finally:
                remove_pid(port)
            return 0
    else:
        # Run in foreground
        write_pid(os.getpid(), port)
        try:
            run_server(port=port, host=host)
        finally:
            remove_pid(port)
        return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the triptic server."""
    port = getattr(args, 'port', 3000)
    pid = read_pid(port)
    if not pid:
        print(f"[triptic] No server running on port {port} (no PID file found)")
        return 1

    if not is_process_running(pid):
        print(f"[triptic] Server not running on port {port} (stale PID: {pid})")
        remove_pid(port)
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"[triptic] Stopping server on port {port} (PID: {pid})...")

        # Wait for process to stop
        for _ in range(50):  # 5 seconds max
            if not is_process_running(pid):
                break
            time.sleep(0.1)

        if is_process_running(pid):
            print("[triptic] Server did not stop gracefully, sending SIGKILL")
            os.kill(pid, signal.SIGKILL)

        remove_pid(port)
        print(f"[triptic] Server on port {port} stopped")
        return 0
    except (OSError, ProcessLookupError) as e:
        print(f"[triptic] Error stopping server: {e}")
        remove_pid(port)
        return 1


def cmd_restart(args: argparse.Namespace) -> int:
    """Restart the triptic server (stop if running, then start)."""
    port = args.port
    # Try to stop if running (ignore errors if not running)
    pid = read_pid(port)
    if pid and is_process_running(pid):
        print(f"[triptic] Stopping running server on port {port}...")
        cmd_stop(args)
        time.sleep(1)  # Give it a moment to clean up
    else:
        print(f"[triptic] No server running on port {port}, starting fresh...")
        # Clean up stale PID file if it exists
        remove_pid(port)

    # Now start the server
    return cmd_start(args)


def cmd_asset_group(args: argparse.Namespace) -> int:
    """Manage asset groups."""
    if args.asset_group_action == 'list':
        prefix = args.prefix if hasattr(args, 'prefix') and args.prefix else None
        asset_groups = list_imagesets(prefix)  # TODO: rename to list_asset_groups in server.py

        if not asset_groups:
            if prefix:
                print(f"[triptic] No asset groups found with prefix '{prefix}'")
            else:
                print("[triptic] No asset groups found")
            return 1

        print(f"[triptic] Asset groups{' with prefix ' + prefix if prefix else ''}:")
        for name, files in asset_groups:
            left = files.get('left', 'N/A')
            center = files.get('center', 'N/A')
            right = files.get('right', 'N/A')
            print(f"  {name}:")
            print(f"    ({left}, {center}, {right})")
        return 0
    else:
        print(f"[triptic] Error: unknown asset group action '{args.asset_group_action}'")
        return 1


def cmd_playlist(args: argparse.Namespace) -> int:
    """Manage playlists."""
    if args.playlist_action == 'list':
        playlists = get_playlists()
        print("[triptic] Available playlists:")
        for name in sorted(playlists.keys()):
            print(f"  - {name}")
        return 0
    elif args.playlist_action == 'set':
        if not args.name:
            print("[triptic] Error: playlist name required")
            return 1
        if set_current_playlist(args.name):
            print(f"[triptic] Playlist set to: {args.name}")
            return 0
        else:
            print(f"[triptic] Error: playlist '{args.name}' not found")
            return 1
    else:
        print(f"[triptic] Error: unknown playlist action '{args.playlist_action}'")
        return 1


def cmd_imgen(args: argparse.Namespace) -> int:
    """Generate images for a playlist item."""
    from triptic import db

    # Initialize database if needed
    db.init_database()

    name = args.name
    prompt = args.prompt
    playlist = args.playlist if hasattr(args, 'playlist') and args.playlist else None

    # Determine the directory to save images (use content directory)
    content_dir = get_content_dir()
    img_dir = content_dir / "img"

    # Gemini always generates PNG images
    file_ext = ".png"

    if playlist:
        # Save to playlist-specific directory (e.g., ~/.triptic/content/img/animals/name.{left,center,right}.png)
        output_dir = img_dir / playlist
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = {
            'left': output_dir / f"{name}.left{file_ext}",
            'center': output_dir / f"{name}.center{file_ext}",
            'right': output_dir / f"{name}.right{file_ext}",
        }
    else:
        # Save to screen-specific directories (e.g., ~/.triptic/content/img/left/name.png)
        output_paths = {
            'left': img_dir / "left" / f"{name}{file_ext}",
            'center': img_dir / "center" / f"{name}{file_ext}",
            'right': img_dir / "right" / f"{name}{file_ext}",
        }
        for screen_dir in [img_dir / "left", img_dir / "center", img_dir / "right"]:
            screen_dir.mkdir(parents=True, exist_ok=True)

    print(f"[triptic] Generating images for '{name}' with prompt: {prompt}")

    # Generate SVG images for each screen
    from triptic.imgen import generate_svg_triplet

    try:
        result = generate_svg_triplet(name, prompt, output_paths)

        print(f"[triptic] Generated images:")
        for screen, path in output_paths.items():
            if path.exists():
                print(f"  {screen}: {path}")

        # Add to playlist if specified
        if playlist:
            asset_group_name = f"{playlist}/{name}"
            if add_to_playlist(playlist, asset_group_name):
                print(f"\n[triptic] Added '{asset_group_name}' to playlist '{playlist}'")
            else:
                print(f"\n[triptic] Warning: Could not add to playlist '{playlist}' (playlist may not exist)")

        # Generate dashboard and editor URLs
        port = os.environ.get("PORT", "3000")
        host = os.environ.get("HOST", "localhost")

        # Create URLs for viewing and editing
        if playlist:
            asset_group_id = f"{playlist}/{name}"
            preview_url = f"http://{host}:{port}/wall.html?preview={asset_group_id}"
            editor_url = f"http://{host}:{port}/asset_group.html?id={asset_group_id}"
        else:
            preview_url = f"http://{host}:{port}/wall.html"
            editor_url = f"http://{host}:{port}/asset_group.html?id={name}"

        print(f"\n[triptic] View in wall: {preview_url}")
        print(f"[triptic] Edit asset group:  {editor_url}")

        return 0
    except RuntimeError as e:
        print(f"\n[triptic] Error: {e}")
        return 1
    except Exception as e:
        print(f"\n[triptic] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Check server status."""
    port = getattr(args, 'port', 3000)
    pid = read_pid(port)
    if not pid:
        print(f"[triptic] Server is not running on port {port} (no PID file)")
        return 1

    if is_process_running(pid):
        print(f"[triptic] Server is running on port {port} (PID: {pid})")

        # Display screen sync status
        screens = read_screen_states()
        if screens:
            print("\nScreen status:")
            for screen_id in sorted(screens.keys()):
                screen_data = screens[screen_id]
                last_sync = screen_data.get('last_sync')
                if last_sync:
                    time_ago = format_time_since(last_sync)
                    print(f"  {screen_id}: {time_ago}")
                else:
                    print(f"  {screen_id}: never synced")
        else:
            print("\nNo screens have synced yet")

        return 0
    else:
        print(f"[triptic] Server is not running on port {port} (stale PID: {pid})")
        remove_pid(port)
        return 1


def cmd_generate_defaults(args: argparse.Namespace) -> int:
    """Generate default placeholder images for left, center, and right screens."""
    from triptic import db, storage
    from triptic.imgen import generate_svg_triplet

    # Initialize database if needed
    db.init_database()

    content_dir = get_content_dir()
    defaults_dir = content_dir / "defaults"
    defaults_dir.mkdir(parents=True, exist_ok=True)

    print("[triptic] Generating default placeholder images...")

    # Create a visually interesting prompt for default frames
    prompt = "Abstract modern art triptych with three connected panels. Vibrant colors, flowing shapes, geometric patterns creating a cohesive composition across left, center, and right screens. Portrait orientation (1080x1920)."

    output_paths = {
        'left': defaults_dir / "default_left.png",
        'center': defaults_dir / "default_center.png",
        'right': defaults_dir / "default_right.png",
    }

    try:
        print(f"[triptic] Generating all three placeholder images...")

        # Generate all three screens at once
        result = generate_svg_triplet(
            name="defaults",
            prompt=prompt,
            output_paths=output_paths
        )

        # Check which images were generated
        for screen, output_path in output_paths.items():
            if output_path.exists():
                print(f"[triptic]   ✓ {screen}: {output_path}")
            else:
                print(f"[triptic]   ✗ {screen}: Failed to generate")

        print(f"\n[triptic] Default placeholders generated successfully!")
        print(f"[triptic] Location: {defaults_dir}")

        return 0
    except RuntimeError as e:
        print(f"\n[triptic] Error: {e}")
        return 1
    except Exception as e:
        print(f"\n[triptic] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="triptic",
        description="Triptic - Time-based triptych display system",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the triptic server")
    start_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 3000)),
        help="Port to listen on (default: 3000)",
    )
    start_parser.add_argument(
        "-H", "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    start_parser.add_argument(
        "-d", "--daemon",
        action="store_true",
        help="Run as a background daemon",
    )
    start_parser.add_argument(
        "--database",
        type=str,
        help="Path to SQLite database file (default: ~/.triptic/triptic.db)",
    )
    start_parser.set_defaults(func=cmd_start)

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the triptic server")
    stop_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 3000)),
        help="Port of the server to stop (default: 3000)",
    )
    stop_parser.set_defaults(func=cmd_stop)

    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart the triptic server")
    restart_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 3000)),
        help="Port to listen on (default: 3000)",
    )
    restart_parser.add_argument(
        "-H", "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    restart_parser.add_argument(
        "-d", "--daemon",
        action="store_true",
        help="Run as a background daemon",
    )
    restart_parser.add_argument(
        "--database",
        type=str,
        help="Path to SQLite database file (default: ~/.triptic/triptic.db)",
    )
    restart_parser.set_defaults(func=cmd_restart)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 3000)),
        help="Port of the server to check (default: 3000)",
    )
    status_parser.set_defaults(func=cmd_status)

    # Asset Group command (with alias 'ag')
    asset_group_parser = subparsers.add_parser(
        "asset-group",
        aliases=["ag"],
        help="Manage asset groups"
    )
    asset_group_parser.add_argument(
        "asset_group_action",
        choices=["list"],
        help="Action to perform"
    )
    asset_group_parser.add_argument(
        "prefix",
        nargs="?",
        help="Optional prefix to filter asset groups (e.g., 'numbers/1')",
    )
    asset_group_parser.set_defaults(func=cmd_asset_group)

    # Playlist command
    playlist_parser = subparsers.add_parser("playlist", help="Manage playlists")
    playlist_parser.add_argument(
        "playlist_action",
        choices=["list", "set"],
        help="Action to perform (list or set)",
    )
    playlist_parser.add_argument(
        "name",
        nargs="?",
        help="Playlist name (required for 'set' action)",
    )
    playlist_parser.set_defaults(func=cmd_playlist)

    # ImGen command
    imgen_parser = subparsers.add_parser("imgen", help="Generate images for a playlist item")
    imgen_parser.add_argument(
        "name",
        help="Name/number of the image set (e.g., '1', 'elephant', etc.)",
    )
    imgen_parser.add_argument(
        "prompt",
        help="Text prompt describing the image to generate",
    )
    imgen_parser.add_argument(
        "-p", "--playlist",
        help="Playlist directory to save to (e.g., 'animals', 'numbers')",
    )
    imgen_parser.set_defaults(func=cmd_imgen)

    # Generate Defaults command
    generate_defaults_parser = subparsers.add_parser(
        "generate-defaults",
        help="Generate default placeholder images for left, center, and right screens"
    )
    generate_defaults_parser.set_defaults(func=cmd_generate_defaults)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
