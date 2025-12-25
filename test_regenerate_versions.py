#!/usr/bin/env python3
"""Test script to reproduce the regenerate 2 versions bug."""

import requests
import json
import time

BASE_URL = "http://localhost:3000"
TEST_ASSET = "test_regen_bug"

def main():
    print(f"Testing regenerate with asset group: {TEST_ASSET}")

    # Step 1: Delete the asset group if it exists
    print("\n1. Cleaning up existing asset group...")
    response = requests.delete(f"{BASE_URL}/asset-group/{TEST_ASSET}")
    print(f"   Delete response: {response.status_code}")

    # Step 2: Create initial version by regenerating left
    print("\n2. Creating initial version (regenerate left with prompt)...")
    response = requests.post(
        f"{BASE_URL}/asset-group/{TEST_ASSET}/regenerate/left",
        json={"prompt": "a red ball"}
    )
    print(f"   Regenerate response: {response.status_code}")
    if response.ok:
        print(f"   Response: {response.json()}")
    time.sleep(2)  # Wait for image generation

    # Step 3: Check how many versions exist
    print("\n3. Checking versions after first regenerate...")
    response = requests.get(f"{BASE_URL}/asset-group/{TEST_ASSET}/versions/left")
    if response.ok:
        data = response.json()
        print(f"   Versions: {data['versions']}")
        print(f"   Current: {data['current']}")
        print(f"   Version count: {len(data['versions'])}")
        if len(data['versions']) != 1:
            print(f"   ❌ ERROR: Expected 1 version, got {len(data['versions'])}")
        else:
            print(f"   ✓ OK: Got 1 version as expected")

    # Step 4: Regenerate again with a different prompt
    print("\n4. Regenerating with edited prompt...")
    response = requests.post(
        f"{BASE_URL}/asset-group/{TEST_ASSET}/regenerate/left",
        json={"prompt": "a blue cube"}
    )
    print(f"   Regenerate response: {response.status_code}")
    time.sleep(2)  # Wait for image generation

    # Step 5: Check versions again
    print("\n5. Checking versions after second regenerate...")
    response = requests.get(f"{BASE_URL}/asset-group/{TEST_ASSET}/versions/left")
    if response.ok:
        data = response.json()
        print(f"   Versions: {data['versions']}")
        print(f"   Current: {data['current']}")
        print(f"   Version count: {len(data['versions'])}")
        if len(data['versions']) != 2:
            print(f"   ❌ ERROR: Expected 2 versions, got {len(data['versions'])}")
        else:
            print(f"   ✓ OK: Got 2 versions as expected")

    print("\n6. Getting asset group details...")
    response = requests.get(f"{BASE_URL}/asset-group/{TEST_ASSET}")
    if response.ok:
        data = response.json()
        if 'left' in data and 'versions' in data['left']:
            print(f"   Left versions: {len(data['left']['versions'])}")
            for i, v in enumerate(data['left']['versions']):
                print(f"     Version {i+1}: prompt='{v.get('prompt', 'N/A')}', content={v.get('content', 'N/A')}")

if __name__ == "__main__":
    main()
