#!/usr/bin/env python3
"""Find or help locate an asset by its content UUID."""

import sys
import requests

def main():
    content_uuid = "6e633ca0-74a5-4c4b-ad2e-a664f75907a1"
    asset_url = f"https://triptic-daveey.fly.dev/content/assets/{content_uuid}.png"

    print(f"Asset URL: {asset_url}")
    print(f"\nChecking if asset exists...")

    try:
        response = requests.head(asset_url, timeout=5)
        if response.status_code == 200:
            print(f"✓ Asset exists on server")
            print(f"\nTo find which page displays this asset:")
            print(f"1. Check the database for asset groups containing this UUID")
            print(f"2. Search through asset group JSON files in content/asset_groups/")
            print(f"3. Use the CLI: triptic list-assets")
        else:
            print(f"✗ Asset not found (HTTP {response.status_code})")
    except Exception as e:
        print(f"✗ Error checking asset: {e}")

    print(f"\n" + "="*60)
    print(f"If you want to display this asset, you can:")
    print(f"1. Add it to an existing asset group")
    print(f"2. Create a new asset group for it")
    print(f"3. Use the direct asset URL in a custom page")

if __name__ == "__main__":
    main()
