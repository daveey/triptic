"""
Test flip image functionality on bird asset group to reproduce the bug.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import os
import time


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


def test_flip_bug():
    """Test flip functionality on bird asset group."""

    load_env_file()

    username = os.environ.get('TRIPTIC_AUTH_USERNAME')
    password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

    if not username or not password:
        print("ERROR: Missing credentials")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={
                "username": username,
                "password": password
            }
        )
        page = context.new_page()

        # Track console messages and network requests
        console_messages = []
        page.on("console", lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text
        }))

        network_requests = []
        def handle_response(response):
            if '/flip/' in response.url or '/asset-group/' in response.url:
                network_requests.append({
                    'url': response.url,
                    'status': response.status,
                    'method': response.request.method
                })
        page.on("response", handle_response)

        print("=" * 80)
        print("TESTING FLIP IMAGE BUG ON BIRD ASSET GROUP")
        print("=" * 80)
        print()

        # Navigate to bird asset group
        print("1. Loading bird asset group page...")
        try:
            page.goto('https://triptic-daveey.fly.dev/asset_group.html?id=bird', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            print("   ✓ Page loaded")
        except Exception as e:
            print(f"   ✗ Failed to load: {e}")
            browser.close()
            return

        # Take initial screenshot
        page.screenshot(path='/tmp/bird_before_flip.png', full_page=True)
        print("   ✓ Screenshot saved: /tmp/bird_before_flip.png")

        # Check if images are loaded
        print("\n2. Checking images...")
        for screen in ['left', 'center', 'right']:
            img = page.locator(f'#img-{screen}')
            if img.is_visible():
                src = img.get_attribute('src')
                print(f"   ✓ {screen}: {src[:60]}...")
            else:
                print(f"   ✗ {screen}: not visible")

        # Try to flip left image
        print("\n3. Attempting to flip LEFT image...")
        try:
            flip_button = page.locator('#controls-left').locator('button:has-text("Flip")')

            if not flip_button.is_visible():
                print("   ✗ Flip button not visible")
                browser.close()
                return

            print("   ✓ Flip button found, clicking...")
            flip_button.click()

            # Wait for loading overlay or response
            page.wait_for_timeout(3000)

            print("   ✓ Clicked flip button")

        except Exception as e:
            print(f"   ✗ Error clicking flip button: {e}")

        # Check for messages
        print("\n4. Checking for error messages...")
        message_el = page.locator('#message')
        if message_el.is_visible():
            message_text = message_el.text_content()
            message_class = message_el.get_attribute('class')
            print(f"   Message: {message_text}")
            print(f"   Class: {message_class}")
        else:
            print("   No message displayed")

        # Check console errors
        print("\n5. Console messages:")
        error_messages = [msg for msg in console_messages if msg['type'] == 'error']
        if error_messages:
            for msg in error_messages[-5:]:
                print(f"   ERROR: {msg['text']}")
        else:
            print("   No console errors")

        # Check network requests
        print("\n6. Network requests:")
        for req in network_requests:
            status_symbol = "✓" if req['status'] < 400 else "✗"
            print(f"   {status_symbol} {req['method']} {req['url']} - HTTP {req['status']}")

        # Take screenshot after flip attempt
        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/bird_after_flip.png', full_page=True)
        print("\n   ✓ Screenshot saved: /tmp/bird_after_flip.png")

        print("\n7. Waiting 5 seconds to observe...")
        page.wait_for_timeout(5000)

        browser.close()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    test_flip_bug()
