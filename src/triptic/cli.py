"""Command-line interface for triptic."""

import argparse
import os
import signal
import sys
import time
import webbrowser
from pathlib import Path

from triptic.server import TripticServer, get_public_dir, run_server


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


def cmd_test(args: argparse.Namespace) -> int:
    """Run the test simulator."""
    port = args.port
    host = args.host

    # Start server
    server = TripticServer(port=port, host=host)

    try:
        print(f"[triptic] Starting test server...")
        server.start()
        print(f"[triptic] Server running at http://{host}:{port}")

        # Open test page in browser
        test_url = f"http://{host}:{port}/test.html"
        print(f"[triptic] Opening test simulator: {test_url}")

        if not args.no_browser:
            webbrowser.open(test_url)

        print(f"[triptic] Press Ctrl+C to stop")

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[triptic] Stopping server...")
    finally:
        server.stop()
        print("[triptic] Server stopped")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Check server status."""
    pid = read_pid()
    if not pid:
        print("[triptic] Server is not running (no PID file)")
        return 1

    if is_process_running(pid):
        print(f"[triptic] Server is running (PID: {pid})")
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

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Run the test simulator with 3 iframes",
    )
    test_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 3000)),
        help="Port to listen on (default: 3000)",
    )
    test_parser.add_argument(
        "-H", "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    test_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open the browser automatically",
    )
    test_parser.set_defaults(func=cmd_test)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
