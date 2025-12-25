"""
Test that regenerating with a new prompt creates a version with that prompt,
and switching between versions shows the correct prompts.
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


def test_regenerate_with_new_prompt():
    """Test regenerating with a modified prompt."""

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
        print("TESTING PROMPT CHANGES WITH REGENERATE")
        print("=" * 80)

        # Load cat asset group
        print("\n1. Loading cat asset group...")
        page.goto('https://triptic-daveey.fly.dev/asset_group.html?id=cat', timeout=30000)
        page.wait_for_load_state('networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        # Get initial prompt
        prompt_textarea = page.locator('#prompt-left')
        initial_prompt = prompt_textarea.input_value()
        print(f"   Initial prompt: {initial_prompt[:60]}...")

        # Modify the prompt
        new_prompt = "A majestic orange tabby cat sitting regally on a red velvet cushion"
        print(f"\n2. Changing prompt to: {new_prompt}")
        prompt_textarea.fill(new_prompt)
        page.wait_for_timeout(500)

        # Click Regen button (exact match to avoid clicking Regen+)
        print("\n3. Clicking Regen button...")
        regen_button = page.locator('#controls-left').get_by_role("button", name="Regen", exact=True)
        regen_button.click()

        # Wait for generation (this takes a while)
        print("   Waiting for image generation (30s)...")
        page.wait_for_timeout(30000)

        # Check message
        message_el = page.locator('#message')
        if message_el.is_visible():
            message_text = message_el.text_content()
            print(f"   Message: {message_text}")

        # Get current prompt
        current_prompt = prompt_textarea.input_value()
        print(f"\n4. Current prompt after regen: {current_prompt[:60]}...")

        # Get version buttons
        version_buttons = page.locator('#version-picker-left .version-number.available')
        count = version_buttons.count()
        print(f"   Available versions: {count}")

        if count >= 2:
            # Click on the previous version (second to last)
            print(f"\n5. Switching to previous version...")
            version_buttons.nth(count - 2).click()
            page.wait_for_timeout(2000)

            old_prompt = prompt_textarea.input_value()
            print(f"   Previous version prompt: {old_prompt[:60]}...")

            # Click on the latest version
            print(f"\n6. Switching back to latest version...")
            version_buttons.nth(count - 1).click()
            page.wait_for_timeout(2000)

            new_prompt_shown = prompt_textarea.input_value()
            print(f"   Latest version prompt: {new_prompt_shown[:60]}...")

            print("\n" + "=" * 80)
            if old_prompt != new_prompt_shown:
                print("✓ SUCCESS: Prompts are DIFFERENT across versions!")
                print(f"  Old: {old_prompt[:60]}...")
                print(f"  New: {new_prompt_shown[:60]}...")
            else:
                print("✗ FAILED: Prompts are the same")
            print("=" * 80)

        page.wait_for_timeout(2000)
        browser.close()


if __name__ == '__main__':
    test_regenerate_with_new_prompt()
