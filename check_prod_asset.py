#!/usr/bin/env python3
"""Check production server for asset groups containing a specific content UUID."""

import requests
import sys

def check_asset_group(group_id: str, content_uuid: str, base_url: str):
    """Check if an asset group contains the specified content UUID."""
    try:
        # Try to fetch the asset group data
        response = requests.get(f"{base_url}/content/asset_groups/{group_id}.json", timeout=5)

        if response.status_code == 200:
            data = response.json()

            # Check each screen (left, center, right)
            for screen in ['left', 'center', 'right']:
                if screen in data:
                    asset = data[screen]
                    if 'versions' in asset:
                        for version in asset['versions']:
                            if version.get('content') == content_uuid:
                                return screen

        return None
    except Exception as e:
        return None

def main():
    base_url = "https://triptic-daveey.fly.dev"
    content_uuid = "6e633ca0-74a5-4c4b-ad2e-a664f75907a1"

    # List of common asset groups from test files
    test_groups = [
        'apple', 'bird', 'cat', 'model', 'flip',
        'animals-1', 'animals-2', 'landscape-1',
        'test_nonexistent_zzzz', 'test_three_panels',
        'test_version_picker', 'test_edit_name',
        'test_playlists', 'test_controls', 'test_nav',
        'test_css', 'test_cache_busting'
    ]

    print(f"Searching for content UUID: {content_uuid}\n")

    for group_id in test_groups:
        screen = check_asset_group(group_id, content_uuid, base_url)
        if screen:
            print(f"✓ Found in asset group: {group_id}")
            print(f"  Screen position: {screen}")
            print(f"\n  Page URL: {base_url}/asset_group.html?id={group_id}")
            return

    print("Asset not found in any of the test asset groups.")
    print("\nThe asset may be:")
    print("1. In a different asset group not in the test list")
    print("2. An orphaned file not linked to any asset group")
    print("3. A temporary or deleted asset")

if __name__ == "__main__":
    main()
