#!/usr/bin/env python3
"""List all asset groups and their content UUIDs."""

from src.triptic.db import get_db_connection

def list_all_asset_groups():
    """List all asset groups with their content UUIDs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT group_id FROM asset_groups ORDER BY id DESC LIMIT 20")
        groups = [row[0] for row in cursor.fetchall()]

        print(f"Found {len(groups)} recent asset groups:\n")

        for group_id in groups:
            print(f"\n{group_id}:")
            cursor.execute("""
                SELECT ag.id
                FROM asset_groups ag
                WHERE ag.group_id = ?
            """, (group_id,))

            result = cursor.fetchone()
            if not result:
                continue

            group_db_id = result[0]

            for screen in ['left', 'center', 'right']:
                cursor.execute("""
                    SELECT a.id, a.current_version_uuid
                    FROM assets a
                    WHERE a.asset_group_id = ? AND a.screen = ?
                """, (group_db_id, screen))

                asset_result = cursor.fetchone()
                if not asset_result:
                    continue

                asset_id, current_version_uuid = asset_result

                cursor.execute("""
                    SELECT content_uuid
                    FROM asset_versions
                    WHERE asset_id = ? AND version_uuid = ?
                """, (asset_id, current_version_uuid))

                version_result = cursor.fetchone()
                if version_result:
                    print(f"  {screen}: {version_result[0]}")

if __name__ == "__main__":
    list_all_asset_groups()
