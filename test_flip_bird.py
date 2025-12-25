"""
Test flip on bird asset group to verify the original issue is fixed.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import os
import re


def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value


def extract_uuid_from_url(url):
    """Extract UUID from image URL."""
    match = re.search(r'assets/([a-f0-9\-]+)\.png', url)
    if match:
        return match.group(1)
    return None


def test_flip_bird():
    """Test that flip works on bird asset group."""

    load_env_file()

    username = os.environ.get('TRIPTIC_AUTH_USERNAME')
    password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={
                "username": username,
                "password": password
            }
        )
        page = context.new_page()

        # Track network requests
        flip_requests = []
        def handle_response(response):
            if '/flip/' in response.url:
                flip_requests.append({
                    'url': response.url,
                    'status': response.status,
                    'method': response.request.method
                })
        page.on("response", handle_response)

        print("=" * 80)
        print("TESTING FLIP ON BIRD ASSET GROUP (Original Issue)")
        print("=" * 80)

        # Test bird asset group
        print("\n1. Loading bird asset group...")
        page.goto('https://triptic-daveey.fly.dev/asset_group.html?id=bird', timeout=30000)
        page.wait_for_load_state('networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        # Get displayed image UUID
        img_left = page.locator('#img-left')
        initial_src = img_left.get_attribute('src')
        displayed_uuid = extract_uuid_from_url(initial_src)
        print(f"   Currently displayed UUID: {displayed_uuid}")

        # Take before screenshot
        page.screenshot(path='/tmp/bird_before_flip.png', full_page=True)
        print(f"   Screenshot saved: /tmp/bird_before_flip.png")

        # Click flip
        print("\n2. Clicking flip button...")
        flip_button = page.locator('#controls-left').locator('button:has-text("Flip")')
        flip_button.click()
        page.wait_for_timeout(3000)

        # Check flip request status
        if flip_requests:
            for req in flip_requests:
                status_symbol = "✓" if req['status'] < 400 else "✗"
                print(f"   {status_symbol} Flip request: HTTP {req['status']}")

        # Get new image UUID
        new_src = img_left.get_attribute('src')
        new_uuid = extract_uuid_from_url(new_src)
        print(f"   New displayed UUID: {new_uuid}")

        # Take after screenshot
        page.screenshot(path='/tmp/bird_after_flip.png', full_page=True)
        print(f"   Screenshot saved: /tmp/bird_after_flip.png")

        # Check message
        message_el = page.locator('#message')
        if message_el.is_visible():
            message_text = message_el.text_content()
            print(f"   Message: {message_text}")

        print("\n" + "=" * 80)
        print(f"BEFORE: {displayed_uuid}")
        print(f"AFTER:  {new_uuid}")
        if displayed_uuid != new_uuid:
            print("✓ SUCCESS: Image was flipped and UUID changed!")
        else:
            print("✗ FAILED: UUID did not change")
        print("=" * 80)

        page.wait_for_timeout(2000)
        browser.close()


if __name__ == '__main__':
    test_flip_bird()
