"""Tests for triptic modules."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from triptic.server import get_public_dir, TripticServer


class TestServer:
    """Tests for the server module."""

    def test_get_public_dir(self):
        """Test that public directory can be found."""
        public_dir = get_public_dir()
        assert public_dir.exists()
        assert public_dir.is_dir()
        assert (public_dir / "index.html").exists()

    def test_triptic_server_start_stop(self):
        """Test server start and stop."""
        server = TripticServer(port=3999, host="localhost")
        server.start()
        assert server.running

        server.stop()
        assert not server.running

    def test_public_dir_contains_required_files(self):
        """Test that public directory has required files."""
        public_dir = get_public_dir()
        assert (public_dir / "index.html").exists()
        assert (public_dir / "wall.html").exists()
        assert (public_dir / "asset_group.html").exists()
        assert (public_dir / "playlists.html").exists()


class TestCLI:
    """Tests for the CLI module."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from triptic.cli import main
        assert callable(main)

    def test_cli_help(self):
        """Test that CLI help works."""
        from triptic.cli import main

        with patch.object(sys, "argv", ["triptic", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_version(self):
        """Test that CLI version works."""
        from triptic.cli import main

        with patch.object(sys, "argv", ["triptic", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_status_not_running(self):
        """Test status command when server is not running."""
        from triptic.cli import main, remove_pid

        # Ensure no PID file exists
        remove_pid()

        with patch.object(sys, "argv", ["triptic", "status"]):
            result = main()
            assert result == 1  # Not running
