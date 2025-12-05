"""SQLite database management for triptic."""

import os
import sqlite3
import json
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import logging


def get_db_path() -> Path:
    """Get the path to the SQLite database."""
    # Check for custom database path from environment variable
    custom_path = os.environ.get('TRIPTIC_DB_PATH')
    if custom_path:
        db_path = Path(custom_path)
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Default path
    db_dir = Path.home() / ".triptic"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "triptic.db"


@contextmanager
def get_db_connection():
    """Get a database connection context manager."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Initialize the database schema."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Asset Versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                content_uuid TEXT NOT NULL,
                prompt TEXT NOT NULL,
                version_uuid TEXT,
                timestamp TEXT NOT NULL,
                version_index INTEGER NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
            )
        """)

        # Assets table (left, center, right)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_group_id INTEGER NOT NULL,
                screen TEXT NOT NULL CHECK(screen IN ('left', 'center', 'right')),
                current_version INTEGER,
                current_version_uuid TEXT,
                FOREIGN KEY (asset_group_id) REFERENCES asset_groups (id) ON DELETE CASCADE
            )
        """)

        # Asset Groups table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        # Playlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                current_position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # Playlist items (many-to-many with ordering)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                asset_group_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                FOREIGN KEY (asset_group_id) REFERENCES asset_groups (id) ON DELETE CASCADE,
                UNIQUE (playlist_id, position)
            )
        """)

        # Settings table (key-value store)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Screen heartbeats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screen_heartbeats (
                screen_id TEXT PRIMARY KEY,
                last_sync TEXT NOT NULL
            )
        """)

        # Create indices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_asset_versions_asset_id
            ON asset_versions (asset_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_group_id
            ON assets (asset_group_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist
            ON playlist_items (playlist_id, position)
        """)

        logging.info("Database schema initialized")


def migrate_to_uuid_versioning() -> None:
    """Migrate existing data from index-based to UUID-based versioning."""
    import uuid

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Add version_uuid column to asset_versions if it doesn't exist
        try:
            cursor.execute("SELECT version_uuid FROM asset_versions LIMIT 1")
        except sqlite3.OperationalError:
            logging.info("Adding version_uuid column to asset_versions...")
            cursor.execute("ALTER TABLE asset_versions ADD COLUMN version_uuid TEXT")

        # Add current_version_uuid column to assets if it doesn't exist
        try:
            cursor.execute("SELECT current_version_uuid FROM assets LIMIT 1")
        except sqlite3.OperationalError:
            logging.info("Adding current_version_uuid column to assets...")
            cursor.execute("ALTER TABLE assets ADD COLUMN current_version_uuid TEXT")

        conn.commit()

        # Check if migration is needed (if any version_uuid is NULL)
        cursor.execute("SELECT COUNT(*) FROM asset_versions WHERE version_uuid IS NULL")
        needs_migration = cursor.fetchone()[0] > 0

        if not needs_migration:
            logging.info("UUID versioning migration not needed")
            return

        logging.info("Starting UUID versioning migration...")

        # Generate UUIDs for all asset_versions that don't have one
        cursor.execute("SELECT id FROM asset_versions WHERE version_uuid IS NULL")
        version_ids = [row[0] for row in cursor.fetchall()]

        for version_id in version_ids:
            version_uuid = str(uuid.uuid4())
            cursor.execute(
                "UPDATE asset_versions SET version_uuid = ? WHERE id = ?",
                (version_uuid, version_id)
            )

        logging.info(f"Generated UUIDs for {len(version_ids)} asset versions")

        # Update assets to use UUID-based current_version
        cursor.execute("SELECT id, current_version FROM assets WHERE current_version_uuid IS NULL")
        assets_to_update = cursor.fetchall()

        for asset_id, current_version_index in assets_to_update:
            if current_version_index is None:
                continue

            # Get the version_uuid at the current_version index
            cursor.execute("""
                SELECT version_uuid FROM asset_versions
                WHERE asset_id = ?
                ORDER BY version_index
                LIMIT 1 OFFSET ?
            """, (asset_id, current_version_index))

            version_row = cursor.fetchone()
            if version_row:
                version_uuid = version_row[0]
                cursor.execute(
                    "UPDATE assets SET current_version_uuid = ? WHERE id = ?",
                    (version_uuid, asset_id)
                )

        logging.info(f"Updated {len(assets_to_update)} assets to UUID-based versioning")
        logging.info("UUID versioning migration complete")


# Asset Group CRUD Operations
def save_asset_group_db(asset_group_id: str, left_asset: 'Asset', center_asset: 'Asset', right_asset: 'Asset') -> int:
    """Save an asset group to the database."""
    from datetime import datetime

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert or get asset_group
        cursor.execute(
            "INSERT OR IGNORE INTO asset_groups (group_id, created_at) VALUES (?, ?)",
            (asset_group_id, datetime.now().isoformat())
        )

        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (asset_group_id,))
        group_db_id = cursor.fetchone()[0]

        # Save each screen's asset
        for screen_name, asset in [('left', left_asset), ('center', center_asset), ('right', right_asset)]:
            # Insert or update asset
            cursor.execute(
                "SELECT id FROM assets WHERE asset_group_id = ? AND screen = ?",
                (group_db_id, screen_name)
            )
            asset_row = cursor.fetchone()

            if asset_row:
                asset_db_id = asset_row[0]
                # Update current_version_uuid
                cursor.execute(
                    "UPDATE assets SET current_version_uuid = ? WHERE id = ?",
                    (asset.current_version_uuid, asset_db_id)
                )
            else:
                # Insert new asset
                cursor.execute(
                    "INSERT INTO assets (asset_group_id, screen, current_version_uuid) VALUES (?, ?, ?)",
                    (group_db_id, screen_name, asset.current_version_uuid)
                )
                asset_db_id = cursor.lastrowid

            # Delete old versions and insert new ones
            cursor.execute("DELETE FROM asset_versions WHERE asset_id = ?", (asset_db_id,))

            for idx, version in enumerate(asset.versions):
                cursor.execute(
                    "INSERT INTO asset_versions (asset_id, content_uuid, prompt, version_uuid, timestamp, version_index) VALUES (?, ?, ?, ?, ?, ?)",
                    (asset_db_id, version.content, version.prompt, version.version_uuid, version.timestamp or datetime.now().isoformat(), idx)
                )

        return group_db_id


def get_asset_group_db(asset_group_id: str) -> Optional[dict]:
    """Get an asset group from the database with current image URLs."""
    from . import storage

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (asset_group_id,))
        group_row = cursor.fetchone()

        if not group_row:
            return None

        group_db_id = group_row[0]

        result = {'id': asset_group_id}

        for screen in ['left', 'center', 'right']:
            cursor.execute(
                "SELECT id, current_version_uuid FROM assets WHERE asset_group_id = ? AND screen = ?",
                (group_db_id, screen)
            )
            asset_row = cursor.fetchone()

            if asset_row:
                asset_db_id, current_version_uuid = asset_row

                # Get all versions
                cursor.execute(
                    "SELECT content_uuid, prompt, version_uuid, timestamp FROM asset_versions WHERE asset_id = ? ORDER BY version_index",
                    (asset_db_id,)
                )
                versions = [
                    {'content': row[0], 'prompt': row[1], 'version_uuid': row[2], 'timestamp': row[3]}
                    for row in cursor.fetchall()
                ]

                # Get current version's content_uuid
                content_uuid = None
                if current_version_uuid and versions:
                    for v in versions:
                        if v['version_uuid'] == current_version_uuid:
                            content_uuid = v['content']
                            break

                # If no matching version found, use first version
                if not content_uuid and versions:
                    content_uuid = versions[0]['content']

                # Build image URL for current version
                local_path = None
                image_url = ""
                if content_uuid and not content_uuid.startswith('img/'):
                    # UUID-based path
                    image_url = f"/content/assets/{content_uuid}.png"
                    local_path = str(storage.get_assets_dir() / f"{content_uuid}.png")
                else:
                    # Fallback
                    image_url = f"/img/{screen}/{asset_group_id}.png"

                result[screen] = {
                    'versions': versions,
                    'current_version_uuid': current_version_uuid,
                    'image_url': image_url,
                    'local_path': local_path
                }
            else:
                result[screen] = {'versions': [], 'current_version_uuid': None, 'image_url': ''}

        return result


def get_all_asset_groups_db() -> dict:
    """Get all asset groups from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT group_id FROM asset_groups")
        group_ids = [row[0] for row in cursor.fetchall()]

        return {group_id: get_asset_group_db(group_id) for group_id in group_ids}


def delete_asset_group_db(asset_group_id: str) -> bool:
    """Delete an asset group from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM asset_groups WHERE group_id = ?", (asset_group_id,))

        return cursor.rowcount > 0


# Playlist CRUD Operations
def save_playlist_db(name: str, assets: list[str], current_position: int) -> int:
    """Save a playlist to the database."""
    from datetime import datetime

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert or update playlist
        cursor.execute(
            "SELECT id FROM playlists WHERE name = ?",
            (name,)
        )
        playlist_row = cursor.fetchone()

        if playlist_row:
            playlist_db_id = playlist_row[0]
            cursor.execute(
                "UPDATE playlists SET current_position = ? WHERE id = ?",
                (current_position, playlist_db_id)
            )
        else:
            cursor.execute(
                "INSERT INTO playlists (name, current_position, created_at) VALUES (?, ?, ?)",
                (name, current_position, datetime.now().isoformat())
            )
            playlist_db_id = cursor.lastrowid

        # Delete old playlist items
        cursor.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_db_id,))

        # Insert new playlist items
        for position, asset_group_id in enumerate(assets):
            # Get asset_group db_id
            cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (asset_group_id,))
            group_row = cursor.fetchone()

            if group_row:
                cursor.execute(
                    "INSERT INTO playlist_items (playlist_id, asset_group_id, position) VALUES (?, ?, ?)",
                    (playlist_db_id, group_row[0], position)
                )

        return playlist_db_id


def get_playlist_db(name: str) -> Optional[dict]:
    """Get a playlist from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, current_position FROM playlists WHERE name = ?",
            (name,)
        )
        playlist_row = cursor.fetchone()

        if not playlist_row:
            return None

        playlist_db_id, current_position = playlist_row

        # Get playlist items in order
        cursor.execute("""
            SELECT ag.group_id
            FROM playlist_items pi
            JOIN asset_groups ag ON pi.asset_group_id = ag.id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position
        """, (playlist_db_id,))

        assets = [row[0] for row in cursor.fetchall()]

        return {
            'name': name,
            'assets': assets,
            'current_position': current_position
        }


def get_all_playlists_db() -> dict:
    """Get all playlists from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM playlists")
        names = [row[0] for row in cursor.fetchall()]

        return {name: get_playlist_db(name) for name in names}


def delete_playlist_db(name: str) -> bool:
    """Delete a playlist from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM playlists WHERE name = ?", (name,))

        return cursor.rowcount > 0


def rename_playlist_db(old_name: str, new_name: str) -> bool:
    """Rename a playlist in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("UPDATE playlists SET name = ? WHERE name = ?", (new_name, old_name))

        return cursor.rowcount > 0


# Settings Operations
def get_setting_db(key: str, default=None):
    """Get a setting from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            return json.loads(row[0])
        return default


def set_setting_db(key: str, value):
    """Set a setting in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )


# Asset Group Operations
def rename_asset_group_db(old_name: str, new_name: str) -> bool:
    """Rename an asset group in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if old name exists
        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (old_name,))
        if not cursor.fetchone():
            return False

        # Check if new name already exists
        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (new_name,))
        if cursor.fetchone():
            raise ValueError(f"Asset group '{new_name}' already exists")

        # Update the group_id
        cursor.execute(
            "UPDATE asset_groups SET group_id = ? WHERE group_id = ?",
            (new_name, old_name)
        )

        return True


# Screen Heartbeat Operations
def update_screen_heartbeat_db(screen_id: str, timestamp: str) -> None:
    """Update screen heartbeat."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO screen_heartbeats (screen_id, last_sync) VALUES (?, ?)",
            (screen_id, timestamp)
        )
