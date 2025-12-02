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
    get_playlists,
    get_public_dir,
    list_imagesets,
    run_server,
    set_current_playlist,
)


def get_pid_file() -> Path:
    """Get the path to the PID file."""
    return Path.home() / ".triptic.pid"


def read_pid() -> int | None:
    """Read the PID from the PID file."""
    pid_file = get_pid_file()
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def write_pid(pid: int) -> None:
    """Write the PID to the PID file."""
    get_pid_file().write_text(str(pid))


def remove_pid() -> None:
    """Remove the PID file."""
    pid_file = get_pid_file()
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
    # Check if already running
    pid = read_pid()
    if pid and is_process_running(pid):
        print(f"[triptic] Server already running (PID: {pid})")
        return 1

    port = args.port
    host = args.host

    if args.daemon:
        # Fork and run in background
        pid = os.fork()
        if pid > 0:
            # Parent process
            write_pid(pid)
            print(f"[triptic] Server started in background (PID: {pid})")
            print(f"[triptic] Listening at http://{host}:{port}")
            print(f"\n[triptic] URLs:")
            print(f"  Dashboard:  http://{host}:{port}/dashboard.html")
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
                remove_pid()
            return 0
    else:
        # Run in foreground
        write_pid(os.getpid())
        try:
            run_server(port=port, host=host)
        finally:
            remove_pid()
        return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the triptic server."""
    pid = read_pid()
    if not pid:
        print("[triptic] No server running (no PID file found)")
        return 1

    if not is_process_running(pid):
        print(f"[triptic] Server not running (stale PID: {pid})")
        remove_pid()
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"[triptic] Stopping server (PID: {pid})...")

        # Wait for process to stop
        for _ in range(50):  # 5 seconds max
            if not is_process_running(pid):
                break
            time.sleep(0.1)

        if is_process_running(pid):
            print("[triptic] Server did not stop gracefully, sending SIGKILL")
            os.kill(pid, signal.SIGKILL)

        remove_pid()
        print("[triptic] Server stopped")
        return 0
    except (OSError, ProcessLookupError) as e:
        print(f"[triptic] Error stopping server: {e}")
        remove_pid()
        return 1


def cmd_imageset(args: argparse.Namespace) -> int:
    """Manage image sets."""
    if args.imageset_action == 'list':
        prefix = args.prefix if hasattr(args, 'prefix') and args.prefix else None
        imagesets = list_imagesets(prefix)

        if not imagesets:
            if prefix:
                print(f"[triptic] No image sets found with prefix '{prefix}'")
            else:
                print("[triptic] No image sets found")
            return 1

        print(f"[triptic] Image sets{' with prefix ' + prefix if prefix else ''}:")
        for name, files in imagesets:
            left = files.get('left', 'N/A')
            center = files.get('center', 'N/A')
            right = files.get('right', 'N/A')
            print(f"  {name}:")
            print(f"    ({left}, {center}, {right})")
        return 0
    else:
        print(f"[triptic] Error: unknown imageset action '{args.imageset_action}'")
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


def cmd_status(args: argparse.Namespace) -> int:
    """Check server status."""
    pid = read_pid()
    if not pid:
        print("[triptic] Server is not running (no PID file)")
        return 1

    if is_process_running(pid):
        print(f"[triptic] Server is running (PID: {pid})")

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
        print(f"[triptic] Server is not running (stale PID: {pid})")
        remove_pid()
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
    start_parser.set_defaults(func=cmd_start)

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the triptic server")
    stop_parser.set_defaults(func=cmd_stop)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.set_defaults(func=cmd_status)

    # ImageSet command (with alias 'is')
    imageset_parser = subparsers.add_parser(
        "imageset",
        aliases=["is"],
        help="Manage image sets"
    )
    imageset_parser.add_argument(
        "imageset_action",
        choices=["list"],
        help="Action to perform"
    )
    imageset_parser.add_argument(
        "prefix",
        nargs="?",
        help="Optional prefix to filter image sets (e.g., 'numbers/1')",
    )
    imageset_parser.set_defaults(func=cmd_imageset)

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
