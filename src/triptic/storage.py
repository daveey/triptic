"""UUID-based file storage for triptic assets."""

import uuid
import shutil
import sqlite3
from pathlib import Path
from typing import Optional
import logging

# Default asset UUIDs (well-known UUIDs for default placeholder images)
DEFAULT_LEFT_UUID = "00000000-0000-0000-0000-000000000001"
DEFAULT_CENTER_UUID = "00000000-0000-0000-0000-000000000002"
DEFAULT_RIGHT_UUID = "00000000-0000-0000-0000-000000000003"


def get_assets_dir() -> Path:
    """Get the path to the assets directory."""
    assets_dir = Path.home() / ".triptic" / "content" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir


def get_public_dir() -> Path:
    """Get the public directory path."""
    # Check if running from installed package or development
    import sys
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS) / 'public'
    else:
        # Running as normal Python script
        return Path(__file__).parent.parent.parent / 'public'


def initialize_default_assets() -> None:
    """
    Copy default placeholder images to assets directory with known UUIDs.
    This should be called once at startup to ensure defaults are always available.
    """
    public_dir = get_public_dir()
    defaults_dir = public_dir / 'defaults'
    assets_dir = get_assets_dir()

    # Mapping of default files to their UUIDs
    defaults = {
        'default_left.png': DEFAULT_LEFT_UUID,
        'default_center.png': DEFAULT_CENTER_UUID,
        'default_right.png': DEFAULT_RIGHT_UUID,
    }

    for filename, content_uuid in defaults.items():
        source = defaults_dir / filename
        dest = assets_dir / f"{content_uuid}.png"

        # Only copy if source exists and dest doesn't exist
        if source.exists() and not dest.exists():
            shutil.copy2(source, dest)
            logging.info(f"Initialized default asset: {dest}")
        elif not source.exists():
            logging.warning(f"Default asset source not found: {source}")


def generate_uuid() -> str:
    """Generate a new UUID for an asset."""
    return str(uuid.uuid4())


def store_file(source_path: Path, content_uuid: Optional[str] = None) -> str:
    """
    Store a file in the assets directory with a UUID name.

    Args:
        source_path: Path to the source file
        content_uuid: Optional UUID to use (generates new one if not provided)

    Returns:
        The UUID of the stored file
    """
    if content_uuid is None:
        content_uuid = generate_uuid()

    # Get file extension
    extension = source_path.suffix

    # Build destination path
    assets_dir = get_assets_dir()
    dest_path = assets_dir / f"{content_uuid}{extension}"

    # Copy file
    shutil.copy2(source_path, dest_path)
    logging.info(f"Stored file {source_path} as {dest_path}")

    return content_uuid


def get_file_path(content_uuid: str, extension: str = None) -> Optional[Path]:
    """
    Get the filesystem path for a UUID.

    Args:
        content_uuid: The UUID of the asset
        extension: Optional extension (will try to find if not provided)

    Returns:
        Path to the file, or None if not found
    """
    assets_dir = get_assets_dir()

    if extension:
        file_path = assets_dir / f"{content_uuid}{extension}"
        if file_path.exists():
            return file_path
        return None

    # Try common extensions
    extensions = ['.png', '.jpg', '.jpeg', '.svg', '.gif', '.mp4', '.webm']
    for ext in extensions:
        file_path = assets_dir / f"{content_uuid}{ext}"
        if file_path.exists():
            return file_path

    return None


def delete_file(content_uuid: str) -> bool:
    """
    Delete a file from the assets directory.

    Args:
        content_uuid: The UUID of the asset to delete

    Returns:
        True if file was deleted, False otherwise
    """
    file_path = get_file_path(content_uuid)
    if file_path and file_path.exists():
        file_path.unlink()
        logging.info(f"Deleted file: {file_path}")
        return True
    return False


def get_public_url(content_uuid: str) -> str:
    """
    Get the public URL path for serving a file.

    Args:
        content_uuid: The UUID of the asset

    Returns:
        URL path like '/content/assets/{uuid}.png'
    """
    file_path = get_file_path(content_uuid)
    if file_path:
        return f"/content/assets/{file_path.name}"
    return ""




def get_db_path() -> Path:
    """Get the path to the database."""
    return Path.home() / ".triptic" / "triptic.db"


def get_current_version_number(asset_group_id: str, screen: str) -> int:
    """
    Get the current version number for an asset (1-9).

    Returns 9 by default (the main file without .vN suffix).
    """
    db_path = get_db_path()
    if not db_path.exists():
        return 9

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Look up asset_group
        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (asset_group_id,))
        result = cursor.fetchone()
        if not result:
            return 9

        group_id = result[0]

        # Look up asset
        cursor.execute(
            "SELECT current_version FROM assets WHERE asset_group_id = ? AND screen = ?",
            (group_id, screen)
        )
        result = cursor.fetchone()
        conn.close()

        if result and result[0] is not None:
            # current_version is stored as 0-8, we display as 1-9
            return result[0] + 1 if result[0] < 8 else 9

        return 9
    except Exception as e:
        logging.error(f"Error getting current version: {e}")
        return 9


def set_current_version_number(asset_group_id: str, screen: str, version: int) -> bool:
    """
    Set the current version number for an asset (1-9).

    Args:
        asset_group_id: The asset group ID
        screen: Screen position (left/center/right)
        version: Version number 1-9

    Returns:
        True if successful
    """
    if version < 1 or version > 9:
        return False

    db_path = get_db_path()
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Look up asset_group
        cursor.execute("SELECT id FROM asset_groups WHERE group_id = ?", (asset_group_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        group_id = result[0]

        # Update asset current_version (store as 0-8)
        db_version = version - 1 if version < 9 else 8
        cursor.execute(
            "UPDATE assets SET current_version = ? WHERE asset_group_id = ? AND screen = ?",
            (db_version, group_id, screen)
        )

        conn.commit()
        conn.close()

        logging.info(f"Set current version for {asset_group_id}/{screen} to v{version}")
        return True
    except Exception as e:
        logging.error(f"Error setting current version: {e}")
        return False


def get_asset_uuid(asset_group_id: str, screen: str) -> Optional[str]:
    """
    Get the UUID for an asset by asset_group_id and screen.

    Args:
        asset_group_id: The asset group identifier (e.g., 'cyberdoc3', 'art/jazz')
        screen: The screen position ('left', 'center', or 'right')

    Returns:
        UUID string if found, None otherwise
    """
    db_path = get_db_path()
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Look up asset_group by group_id
        cursor.execute(
            "SELECT id FROM asset_groups WHERE group_id = ?",
            (asset_group_id,)
        )
        result = cursor.fetchone()
        if not result:
            return None

        group_id = result[0]

        # Look up asset by asset_group_id and screen
        cursor.execute(
            "SELECT id FROM assets WHERE asset_group_id = ? AND screen = ?",
            (group_id, screen)
        )
        result = cursor.fetchone()
        if not result:
            return None

        asset_id = result[0]

        # Get the current version's UUID
        cursor.execute(
            """
            SELECT content_uuid FROM asset_versions
            WHERE asset_id = ?
            ORDER BY version_index DESC
            LIMIT 1
            """,
            (asset_id,)
        )
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]

        return None

    except Exception as e:
        logging.error(f"Error looking up asset UUID: {e}")
        return None


def get_asset_file_path_by_group(asset_group_id: str, screen: str) -> Optional[Path]:
    """
    Get the file path for an asset by asset_group_id and screen.

    This function looks up the UUID from the database and returns the file path.
    If no asset exists or file doesn't exist, returns the default placeholder asset for that screen.

    Args:
        asset_group_id: The asset group identifier (e.g., 'cyberdoc3', 'art/jazz')
        screen: The screen position ('left', 'center', or 'right')

    Returns:
        Path to the file (real asset or default placeholder)
    """
    content_uuid = get_asset_uuid(asset_group_id, screen)
    if content_uuid and not content_uuid.startswith('img/'):
        file_path = get_file_path(content_uuid)
        # Check if file actually exists on filesystem
        if file_path and file_path.exists():
            return file_path

    # If no asset found or file doesn't exist, return default placeholder for this screen
    default_uuids = {
        'left': DEFAULT_LEFT_UUID,
        'center': DEFAULT_CENTER_UUID,
        'right': DEFAULT_RIGHT_UUID,
    }

    default_uuid = default_uuids.get(screen)
    if default_uuid:
        return get_file_path(default_uuid)

    return None
