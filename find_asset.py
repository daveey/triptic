#!/usr/bin/env python3
"""Find which asset group contains a specific content UUID."""

import sys
from src.triptic.db import get_db_connection

def find_asset_group_by_content_uuid(content_uuid: str) -> tuple[str, str] | None:
    """
    Find the asset group and screen position for a given content UUID.

    Returns: (asset_group_id, screen) or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Find the asset_version with this content_uuid
        cursor.execute("""
            SELECT av.asset_id
            FROM asset_versions av
            WHERE av.content_uuid = ?
        """, (content_uuid,))

        result = cursor.fetchone()
        if not result:
            return None

        asset_id = result[0]

        # Get the asset group and screen for this asset
        cursor.execute("""
            SELECT ag.group_id, a.screen
            FROM assets a
            JOIN asset_groups ag ON a.asset_group_id = ag.id
            WHERE a.id = ?
        """, (asset_id,))

        result = cursor.fetchone()
        if result:
            return (result[0], result[1])

        return None

if __name__ == "__main__":
    content_uuid = "6e633ca0-74a5-4c4b-ad2e-a664f75907a1"

    result = find_asset_group_by_content_uuid(content_uuid)

    if result:
        asset_group_id, screen = result
        print(f"Asset found in group: {asset_group_id}")
        print(f"Screen position: {screen}")
        print(f"\nPage URL: https://triptic-daveey.fly.dev/asset_group.html?id={asset_group_id}")
    else:
        print(f"Asset {content_uuid} not found in any asset group")
