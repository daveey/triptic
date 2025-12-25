"""
Test version-specific prompt handling.
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


def test_version_prompts():
    """Test that prompts update when changing versions."""

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

        print("=" * 80)
        print("TESTING VERSION-SPECIFIC PROMPTS")
        print("=" * 80)

        # Load bird asset group
        print("\n1. Loading bird asset group...")
        page.goto('https://triptic-daveey.fly.dev/asset_group.html?id=bird', timeout=30000)
        page.wait_for_load_state('networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        # Get initial prompt
        prompt_textarea = page.locator('#prompt-left')
        initial_prompt = prompt_textarea.input_value()
        print(f"   Initial prompt (version shown): {initial_prompt[:80]}...")

        # Get version numbers available
        version_buttons = page.locator('#version-picker-left .version-number.available')
        count = version_buttons.count()
        print(f"   Found {count} available versions")

        if count >= 2:
            # Click on version 1
            print("\n2. Clicking version 1...")
            page.locator('#version-picker-left .version-number.available').first.click()
            page.wait_for_timeout(2000)

            prompt_v1 = prompt_textarea.input_value()
            print(f"   Version 1 prompt: {prompt_v1[:80]}...")

            # Click on version 2 (or last version)
            print("\n3. Clicking version 2...")
            page.locator('#version-picker-left .version-number.available').nth(1).click()
            page.wait_for_timeout(2000)

            prompt_v2 = prompt_textarea.input_value()
            print(f"   Version 2 prompt: {prompt_v2[:80]}...")

            print("\n" + "=" * 80)
            if prompt_v1 == prompt_v2:
                print("✗ BUG: Prompts are the SAME across versions (should be different)")
            else:
                print("✓ GOOD: Prompts differ across versions")
            print("=" * 80)
        else:
            print("   Not enough versions to test (need at least 2)")

        page.wait_for_timeout(2000)
        browser.close()


if __name__ == '__main__':
    test_version_prompts()
