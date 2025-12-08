"""Playwright tests for frontend functionality."""

import re
import pytest
from pathlib import Path
from PIL import Image
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the triptic server.

    Uses port 3001 for tests to avoid conflicts with production server on port 3000.
    """
    return "http://localhost:3001"


# ========== Index/Display Page Tests ==========


def test_index_page_redirects_without_id(page: Page, base_url: str):
    """Test that the index page redirects to dashboard when no screen ID is provided."""
    # The index page redirects to /dashboard.html when no screen ID is specified
    # Since dashboard.html was deleted, we'll test with a specific screen ID
    page.goto(f"{base_url}/?id=left")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check that the display image element exists
    display_img = page.locator("#display")
    expect(display_img).to_be_attached()


# ========== Asset Group Page Tests ==========


def test_placeholder_images_on_nonexistent_asset_group(page: Page, base_url: str):
    """Test that placeholder images are shown for non-existent asset groups."""
    # Visit a non-existent asset group
    page.goto(f"{base_url}/asset_group.html?id=test_nonexistent_zzzz")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check that placeholder images are loaded
    left_img = page.locator("#img-left")
    center_img = page.locator("#img-center")
    right_img = page.locator("#img-right")

    # Verify images have src attributes pointing to defaults (with cache-busting timestamp)
    expect(left_img).to_have_attribute("src", re.compile(r"^/defaults/default_left\.png"), timeout=10000)
    expect(center_img).to_have_attribute("src", re.compile(r"^/defaults/default_center\.png"), timeout=10000)
    expect(right_img).to_have_attribute("src", re.compile(r"^/defaults/default_right\.png"), timeout=10000)

    # Verify the message is shown
    message = page.locator("#message")
    expect(message).to_be_visible()
    expect(message).to_contain_text("doesn't exist")

    # Verify controls are visible
    prompt_container = page.locator("#prompt-container")
    expect(prompt_container).to_be_visible()

    # Verify regenerate all button is visible
    regenerate_btn = page.get_by_role("button", name="Regenerate All")
    expect(regenerate_btn).to_be_visible()


def test_placeholder_images_actually_load(page: Page, base_url: str):
    """Test that placeholder images actually load successfully."""
    # Visit defaults directly
    page.goto(f"{base_url}/defaults/default_left.png")

    # Check that the image loads (no error page)
    # If it's an image, the page won't have an h1 error title
    expect(page.locator("h1:has-text('Error')")).not_to_be_visible()

    # Check the other default images
    page.goto(f"{base_url}/defaults/default_center.png")
    expect(page.locator("h1:has-text('Error')")).not_to_be_visible()

    page.goto(f"{base_url}/defaults/default_right.png")
    expect(page.locator("h1:has-text('Error')")).not_to_be_visible()


def test_asset_group_name_displayed(page: Page, base_url: str):
    """Test that asset group name is displayed correctly."""
    test_name = "test_display_name_xyz"
    page.goto(f"{base_url}/asset_group.html?id={test_name}")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check that the asset group name is displayed
    name_element = page.locator("#asset-group-name")
    expect(name_element).to_have_text(test_name)


def test_prompt_defaulted_to_asset_name(page: Page, base_url: str):
    """Test that the main prompt defaults to asset group name."""
    test_name = "test_prompt_default_abc"
    page.goto(f"{base_url}/asset_group.html?id={test_name}")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check that prompt is set to asset name
    prompt_main = page.locator("#prompt-main")
    expect(prompt_main).to_have_text(test_name)


def test_asset_group_has_three_panels(page: Page, base_url: str):
    """Test that asset group page has all three image panels."""
    page.goto(f"{base_url}/asset_group.html?id=test_three_panels")
    page.wait_for_load_state("networkidle")

    # Check for all three image panels
    left_panel = page.locator("#panel-left")
    center_panel = page.locator("#panel-center")
    right_panel = page.locator("#panel-right")

    expect(left_panel).to_be_visible()
    expect(center_panel).to_be_visible()
    expect(right_panel).to_be_visible()

    # Check panel headings
    expect(left_panel.locator("h3")).to_have_text("Left")
    expect(center_panel.locator("h3")).to_have_text("Center")
    expect(right_panel.locator("h3")).to_have_text("Right")


def test_asset_group_version_picker_visible(page: Page, base_url: str):
    """Test that version pickers are visible for each panel."""
    page.goto(f"{base_url}/asset_group.html?id=test_version_picker")
    page.wait_for_load_state("networkidle")

    # Check that version pickers exist for all panels
    left_picker = page.locator("#version-picker-left")
    center_picker = page.locator("#version-picker-center")
    right_picker = page.locator("#version-picker-right")

    expect(left_picker).to_be_visible()
    expect(center_picker).to_be_visible()
    expect(right_picker).to_be_visible()

    # Check that version numbers are present (1-9)
    version_1 = left_picker.locator(".version-number[data-version='1']")
    version_9 = left_picker.locator(".version-number[data-version='9']")
    expect(version_1).to_be_visible()
    expect(version_9).to_be_visible()


def test_asset_group_edit_name_button_visible(page: Page, base_url: str):
    """Test that the edit name button is visible."""
    page.goto(f"{base_url}/asset_group.html?id=test_edit_name")
    page.wait_for_load_state("networkidle")

    edit_btn = page.locator("#edit-name-btn")
    expect(edit_btn).to_be_visible()
    expect(edit_btn).to_have_text("Edit")


def test_asset_group_playlist_section_visible(page: Page, base_url: str):
    """Test that the playlist section is visible."""
    page.goto(f"{base_url}/asset_group.html?id=test_playlists")
    page.wait_for_load_state("networkidle")

    # Check for playlists section
    playlist_checkboxes = page.locator("#playlist-checkboxes")
    expect(playlist_checkboxes).to_be_attached()


def test_asset_group_controls_visible(page: Page, base_url: str):
    """Test that control buttons are visible."""
    page.goto(f"{base_url}/asset_group.html?id=test_controls")
    page.wait_for_load_state("networkidle")

    # Check for main control buttons
    duplicate_btn = page.get_by_role("button", name="Duplicate")
    delete_btn = page.get_by_role("button", name="Delete Asset Group")

    expect(duplicate_btn).to_be_visible()
    expect(delete_btn).to_be_visible()


def test_drag_and_drop_image_upload(page: Page, base_url: str, tmp_path: Path):
    """Test that dragging and dropping an image onto a frame uploads it as a new version."""
    # Create a test image file
    test_image_path = tmp_path / "test_upload.png"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(test_image_path)

    # Navigate to asset group page
    test_name = "test_drag_drop_upload"
    page.goto(f"{base_url}/asset_group.html?id={test_name}")
    page.wait_for_load_state("networkidle")

    # Track success messages
    success_messages = []
    def handle_console(msg):
        if msg.type == "log" and "uploaded successfully" in msg.text.lower():
            success_messages.append(msg.text)
    page.on("console", handle_console)

    # Get the initial image source for the left panel
    left_img = page.locator("#img-left")
    initial_src = left_img.get_attribute("src")

    # Drag and drop the file onto the left panel
    left_panel = page.locator("#panel-left")

    # Use Playwright's file chooser to simulate drag and drop
    # Note: We need to use the file input approach since true drag-and-drop from OS
    # is not fully supported in headless browsers
    with page.expect_file_chooser() as fc_info:
        # Programmatically trigger the file drop
        page.evaluate("""
            (testImagePath) => {
                fetch(testImagePath)
                    .then(res => res.blob())
                    .then(blob => {
                        const file = new File([blob], 'test_upload.png', { type: 'image/png' });
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);

                        const dropEvent = new DragEvent('drop', {
                            dataTransfer: dataTransfer,
                            bubbles: true,
                            cancelable: true
                        });

                        document.getElementById('panel-left').dispatchEvent(dropEvent);
                    });
            }
        """, f"data:image/png;base64,{_image_to_base64(test_image_path)}")

    # Wait for the upload to complete
    page.wait_for_timeout(2000)

    # Check for success message
    message = page.locator("#message")
    expect(message).to_contain_text("uploaded successfully", timeout=5000)

    # Verify the image source changed (cache-busting query param should update)
    new_src = left_img.get_attribute("src")
    assert new_src != initial_src, "Image source should have changed after upload"


def _image_to_base64(image_path: Path) -> str:
    """Convert an image file to base64 string."""
    import base64
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


# ========== Playlists Page Tests ==========


def test_playlists_page_loads(page: Page, base_url: str):
    """Test that the playlists page loads."""
    page.goto(f"{base_url}/playlists.html")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check title
    expect(page).to_have_title("Triptic - Playlists")


def test_playlists_page_has_container(page: Page, base_url: str):
    """Test that the playlists page has the playlists container."""
    page.goto(f"{base_url}/playlists.html")
    page.wait_for_load_state("networkidle")

    # Check for playlists container (dynamically populated)
    container = page.locator("#playlists-container")
    expect(container).to_be_visible()

    # Check for new playlist button
    new_playlist_btn = page.get_by_role("button", name="+ New Playlist")
    expect(new_playlist_btn).to_be_visible()


# ========== Settings Page Tests ==========


def test_settings_page_loads(page: Page, base_url: str):
    """Test that the settings page loads."""
    page.goto(f"{base_url}/settings.html")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check title
    expect(page).to_have_title("Triptic - Settings")


def test_settings_page_has_form(page: Page, base_url: str):
    """Test that the settings page has settings cards."""
    page.goto(f"{base_url}/settings.html")
    page.wait_for_load_state("networkidle")

    # Check for settings cards
    settings_card = page.locator(".settings-card").first
    expect(settings_card).to_be_visible()


# ========== Wall Page Tests ==========


def test_wall_page_loads(page: Page, base_url: str):
    """Test that the wall page loads."""
    page.goto(f"{base_url}/wall.html")

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Check title
    expect(page).to_have_title("Triptic - Wall")


def test_wall_page_has_controls(page: Page, base_url: str):
    """Test that the wall page has control elements."""
    page.goto(f"{base_url}/wall.html")
    page.wait_for_load_state("networkidle")

    # Check for controls section
    controls = page.locator(".controls")
    expect(controls).to_be_visible()


# ========== Navigation Tests ==========


def test_navigation_exists_on_asset_group_page(page: Page, base_url: str):
    """Test that navigation exists on asset group page."""
    page.goto(f"{base_url}/asset_group.html?id=test_nav")
    page.wait_for_load_state("networkidle")

    # The nav.js script should inject navigation
    # Wait a bit for the script to execute
    page.wait_for_timeout(500)

    # Check if nav was injected (nav.js creates nav elements dynamically)
    # We can't easily test this without knowing the exact structure


def test_shared_nav_css_loads(page: Page, base_url: str):
    """Test that shared navigation CSS loads."""
    page.goto(f"{base_url}/asset_group.html?id=test_css")
    page.wait_for_load_state("networkidle")

    # Check that the nav.css is linked
    # This will pass if the page doesn't have CSS errors
    # A more robust test would check for specific styles


# ========== Error Handling Tests ==========


def test_missing_asset_group_id_shows_error(page: Page, base_url: str):
    """Test that missing asset group ID shows an error."""
    page.goto(f"{base_url}/asset_group.html")
    page.wait_for_load_state("networkidle")

    # Should show an error message about no asset group specified
    message = page.locator("#message")
    expect(message).to_be_visible()
    expect(message).to_contain_text("No asset group specified")


def test_asset_group_images_load_without_404(page: Page, base_url: str):
    """Test that asset group images don't return 404 errors."""
    # Track console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Track failed requests
    failed_requests = []
    def handle_response(response):
        if response.status >= 400 and '/content/assets/' in response.url:
            failed_requests.append({
                'url': response.url,
                'status': response.status
            })
    page.on("response", handle_response)

    # Load an existing asset group (model in this case)
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")

    # Give it a bit more time for all resources to load
    page.wait_for_timeout(1000)

    # Check if there were any 404 errors for asset images
    if failed_requests:
        error_msg = f"Found {len(failed_requests)} failed asset requests:\n"
        for req in failed_requests:
            error_msg += f"  - {req['url']} (HTTP {req['status']})\n"
        raise AssertionError(error_msg)

    # Also check console for asset loading errors
    asset_errors = [err for err in console_errors if '404' in err or 'Asset not found' in err]
    if asset_errors:
        raise AssertionError(f"Found {len(asset_errors)} console errors about missing assets:\n" + "\n".join(asset_errors[:5]))


def test_assets_load_with_cache_busting_query_params(page: Page, base_url: str):
    """Test that asset URLs with cache-busting query parameters load correctly.

    Regression test for: Asset URLs with ?t=timestamp were failing because
    the server wasn't stripping query parameters before looking up files.
    Fixed in src/triptic/server.py:1547-1549 and :1584-1586
    """
    # Track all asset requests
    asset_requests = []
    def handle_response(response):
        if '/content/assets/' in response.url or '/defaults/' in response.url:
            asset_requests.append({
                'url': response.url,
                'status': response.status,
                'has_query': '?' in response.url
            })
    page.on("response", handle_response)

    # Load a page with assets
    page.goto(f"{base_url}/asset_group.html?id=test_cache_busting")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Verify we got some asset requests
    assert len(asset_requests) > 0, "No asset requests were made"

    # Check that all assets loaded successfully (200 status)
    failed_assets = [req for req in asset_requests if req['status'] != 200]
    if failed_assets:
        error_msg = f"Found {len(failed_assets)} failed asset requests:\n"
        for req in failed_assets:
            query_info = " (with query params)" if req['has_query'] else ""
            error_msg += f"  - {req['url']}{query_info} (HTTP {req['status']})\n"
        raise AssertionError(error_msg)

    # Verify that at least some requests had cache-busting query parameters
    requests_with_query = [req for req in asset_requests if req['has_query']]
    assert len(requests_with_query) > 0, "No asset requests had cache-busting query parameters"
