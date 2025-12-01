"""HTTP server for triptic."""

import http.server
import os
import socketserver
import threading
from pathlib import Path


class TripticHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves from the public directory."""

    def __init__(self, *args, directory: str = None, **kwargs):
        self.public_dir = directory or str(get_public_dir())
        super().__init__(*args, directory=self.public_dir, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Log HTTP requests."""
        print(f"[triptic] {args[0]} {args[1]} {args[2]}")


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


def run_server(port: int = 3000, host: str = "localhost") -> None:
    """Run the server in the foreground."""
    public_dir = get_public_dir()
    print(f"[triptic] Serving from: {public_dir}")
    print(f"[triptic] Server running at http://{host}:{port}")
    print(f"[triptic] Press Ctrl+C to stop")

    handler = lambda *args, **kwargs: TripticHandler(
        *args, directory=str(public_dir), **kwargs
    )

    with socketserver.TCPServer((host, port), handler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[triptic] Server stopped")
