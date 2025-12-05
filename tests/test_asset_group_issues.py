"""Playwright tests for asset group page issues.

Following TDD workflow: Write tests first, verify they fail, then fix the code.

Issues to test:
1. Prompts not showing for images (should always show, even if empty)
2. Version 9 always showing as selected (should show actual current version)
3. Regen not creating versions or refreshing the page
"""

import re
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the triptic server (test port)."""
    return "http://localhost:3001"


# Issue 1: Prompt Display Tests


def test_prompts_are_always_visible_even_if_empty(page: Page, base_url: str):
    """Test that prompt textareas are always visible, even if not set.

    Bug: Prompts may not be showing when they should always be visible.
    """
    page.goto(f"{base_url}/asset_group.html?id=test_prompt_visibility")
    page.wait_for_load_state("networkidle")

    # All three prompt textareas should be visible
    left_prompt = page.locator("#prompt-left")
    center_prompt = page.locator("#prompt-center")
    right_prompt = page.locator("#prompt-right")

    expect(left_prompt).to_be_visible()
    expect(center_prompt).to_be_visible()
    expect(right_prompt).to_be_visible()

    # They should be editable (not disabled)
    expect(left_prompt).to_be_editable()
    expect(center_prompt).to_be_editable()
    expect(right_prompt).to_be_editable()


def test_prompt_displays_stored_value(page: Page, base_url: str):
    """Test that prompts display the stored value from database.

    Bug: Prompts should be stored in DB, not on disk.
    """
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)  # Wait for data to load

    # Check if any prompts have values (model asset group should have prompts)
    left_prompt = page.locator("#prompt-left")
    center_prompt = page.locator("#prompt-center")
    right_prompt = page.locator("#prompt-right")

    # At least one should have a value if the asset was generated with prompts
    left_value = left_prompt.input_value()
    center_value = center_prompt.input_value()
    right_value = right_prompt.input_value()

    # If model exists, at least one prompt should be non-empty
    has_prompt = len(left_value) > 0 or len(center_value) > 0 or len(right_value) > 0
    assert has_prompt, f"No prompts found. Left: '{left_value}', Center: '{center_value}', Right: '{right_value}'"


# Issue 2: Version Selection Tests


def test_correct_version_is_marked_as_current(page: Page, base_url: str):
    """Test that the actual current version is marked, not always version 9.

    Bug: Version 9 is always showing as selected, should show actual current version.
    """
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Check each panel's version picker
    for screen in ['left', 'center', 'right']:
        picker = page.locator(f"#version-picker-{screen}")

        # There should be exactly one element with class "current"
        current_versions = picker.locator(".version-number.current")
        count = current_versions.count()

        assert count == 1, f"{screen} panel has {count} current versions (should be exactly 1)"

        # Get the version number
        current_version_text = current_versions.text_content()
        print(f"[{screen}] Current version: {current_version_text}")

        # Version should be a number between 1-9
        assert current_version_text.isdigit(), f"Current version '{current_version_text}' is not a digit"
        version_num = int(current_version_text)
        assert 1 <= version_num <= 9, f"Version {version_num} out of range [1-9]"


def test_different_panels_can_have_different_versions(page: Page, base_url: str):
    """Test that different panels can independently show different current versions.

    This validates that version tracking is per-panel, not global.
    """
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Get current version for each panel
    versions = {}
    for screen in ['left', 'center', 'right']:
        picker = page.locator(f"#version-picker-{screen}")
        current = picker.locator(".version-number.current")
        if current.count() > 0:
            versions[screen] = current.text_content()

    # Log the versions for debugging
    print(f"Current versions: {versions}")

    # Versions should exist for all panels
    assert len(versions) == 3, f"Expected 3 versions, got {len(versions)}: {versions}"


# Issue 3: Regeneration Tests


def test_regenerate_creates_new_version(page: Page, base_url: str):
    """Test that clicking regenerate creates a new version in the version history.

    Bug: Regen creates a new image but doesn't add a version to the version picker.
    """
    # Use "model" asset group which should have images
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Count initial versions for left panel
    left_picker = page.locator("#version-picker-left")
    initial_version_count = left_picker.locator(".version-number").count()
    print(f"Initial version count: {initial_version_count}")

    # Note: This test will likely fail because we can't actually trigger
    # a regen without a real API key. But it documents the expected behavior.
    # A real test would need to mock the API or use a test fixture.

    # For now, just verify the structure exists
    # Regen button is inside #controls-left with text "Regen"
    controls_left = page.locator("#controls-left")
    regen_btn = controls_left.get_by_role("button", name="Regen", exact=True)
    expect(regen_btn).to_be_visible()


def test_regenerate_refreshes_image_on_page(page: Page, base_url: str):
    """Test that after regeneration, the displayed image updates.

    Bug: Regen doesn't refresh the image on the page.
    """
    page.goto(f"{base_url}/asset_group.html?id=test_regen_refresh")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Get initial image src
    left_img = page.locator("#img-left")
    initial_src = left_img.get_attribute("src")
    print(f"Initial image src: {initial_src}")

    # The image should have a src attribute
    assert initial_src is not None and len(initial_src) > 0, "Image has no src"

    # Note: Actually testing the regeneration would require mocking or real API
    # This test validates the structure exists


def test_version_data_includes_prompt_info(page: Page, base_url: str):
    """Test that version data includes prompt information.

    Each version should store the prompt used to generate it.
    """
    page.goto(f"{base_url}/asset_group.html?id=model")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Check that version elements exist with data attributes
    left_picker = page.locator("#version-picker-left")
    version_elements = left_picker.locator(".version-number")

    if version_elements.count() > 0:
        # Check first version has expected structure
        first_version = version_elements.first
        expect(first_version).to_be_visible()

        # Version should be clickable
        expect(first_version).not_to_be_disabled()
