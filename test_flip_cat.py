"""
Test flip on cat asset group (known to exist).
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import os


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


def test_flip_cat():
    """Test flip on cat asset group."""

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

        # Track network
        network_requests = []
        def handle_response(response):
            if '/flip/' in response.url:
                network_requests.append({
                    'url': response.url,
                    'status': response.status,
                    'method': response.request.method
                })
        page.on("response", handle_response)

        print("Testing flip on CAT asset group...")
        page.goto('https://triptic-daveey.fly.dev/asset_group.html?id=cat', timeout=30000)
        page.wait_for_load_state('networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        print("✓ Page loaded")

        # Get initial image src
        img_left = page.locator('#img-left')
        initial_src = img_left.get_attribute('src')
        print(f"Initial image: {initial_src[:60]}...")

        # Click flip
        flip_button = page.locator('#controls-left').locator('button:has-text("Flip")')
        print("Clicking flip button...")
        flip_button.click()
        page.wait_for_timeout(3000)

        # Check message
        message_el = page.locator('#message')
        if message_el.is_visible():
            message_text = message_el.text_content()
            message_class = message_el.get_attribute('class')
            print(f"Message: {message_text} ({message_class})")

        # Check network
        for req in network_requests:
            status_symbol = "✓" if req['status'] < 400 else "✗"
            print(f"{status_symbol} {req['method']} - HTTP {req['status']}")

        # Get new image src
        new_src = img_left.get_attribute('src')
        print(f"New image: {new_src[:60]}...")

        if initial_src != new_src:
            print("✓ Image source changed!")
        else:
            print("✗ Image source did not change")

        page.screenshot(path='/tmp/cat_after_flip.png', full_page=True)
        print("Screenshot: /tmp/cat_after_flip.png")

        page.wait_for_timeout(3000)
        browser.close()


if __name__ == '__main__':
    test_flip_cat()
