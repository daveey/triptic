"""Debug test for specific asset group page loading issue."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the triptic server.

    Uses port 3001 for tests to avoid conflicts with production server on port 3000.
    """
    return "http://localhost:3001"


def test_model_asset_group_page_loads(page: Page, base_url: str):
    """Test that the model asset group page loads correctly."""
    # Enable console logging to see JavaScript errors
    page.on("console", lambda msg: print(f"[CONSOLE {msg.type}]: {msg.text}"))
    page.on("pageerror", lambda error: print(f"[PAGE ERROR]: {error}"))

    # Navigate to the model asset group page
    page.goto(f"{base_url}/asset_group.html?id=model")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Take a screenshot for debugging
    page.screenshot(path="/tmp/model_asset_group.png")
    print("Screenshot saved to /tmp/model_asset_group.png")

    # Check if there are any error messages
    message = page.locator("#message")
    if message.is_visible():
        message_text = message.text_content()
        print(f"[MESSAGE]: {message_text}")

    # Check that the asset group name is displayed
    name_element = page.locator("#asset-group-name")
    expect(name_element).to_be_visible()

    actual_name = name_element.text_content()
    print(f"[ASSET GROUP NAME]: {actual_name}")

    # Check that the page has loaded properly
    left_panel = page.locator("#panel-left")
    center_panel = page.locator("#panel-center")
    right_panel = page.locator("#panel-right")

    expect(left_panel).to_be_visible()
    expect(center_panel).to_be_visible()
    expect(right_panel).to_be_visible()

    # Check image sources
    left_img = page.locator("#img-left")
    center_img = page.locator("#img-center")
    right_img = page.locator("#img-right")

    left_src = left_img.get_attribute("src")
    center_src = center_img.get_attribute("src")
    right_src = right_img.get_attribute("src")

    print(f"[LEFT IMAGE]: {left_src}")
    print(f"[CENTER IMAGE]: {center_src}")
    print(f"[RIGHT IMAGE]: {right_src}")

    # Get all text content from the page for debugging
    page_content = page.locator("body").text_content()
    print(f"[PAGE CONTENT LENGTH]: {len(page_content)} characters")

    # Check if prompt container is visible
    prompt_container = page.locator("#prompt-container")
    print(f"[PROMPT CONTAINER VISIBLE]: {prompt_container.is_visible()}")
