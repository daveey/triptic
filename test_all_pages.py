"""
Comprehensive test for all pages on Triptic site.
Tests every page and every interaction to identify bugs.
"""

from playwright.sync_api import sync_playwright, Page
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


def test_all_pages():
    """Test all pages on the Triptic site."""

    bugs_found = []
    test_results = []

    # Load .env file if present
    load_env_file()

    # Get credentials from environment
    username = os.environ.get('TRIPTIC_AUTH_USERNAME')
    password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

    if not username or not password:
        print("ERROR: TRIPTIC_AUTH_USERNAME and TRIPTIC_AUTH_PASSWORD must be set")
        return [], ["✗ Missing authentication credentials"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={
                "username": username,
                "password": password
            }
        )
        page = context.new_page()

        # Track console errors and network failures
        console_messages = []
        page.on("console", lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text
        }))

        failed_requests = []
        def handle_response(response):
            if response.status >= 400:
                failed_requests.append({
                    'url': response.url,
                    'status': response.status
                })
        page.on("response", handle_response)

        print("=" * 80)
        print("TRIPTIC - COMPREHENSIVE ALL PAGES TEST")
        print("=" * 80)
        print()

        base_url = "https://triptic-daveey.fly.dev"

        # ========== TEST 1: WALL.HTML (Already tested, just verify) ==========
        print("=" * 80)
        print("TEST 1: WALL.HTML")
        print("=" * 80)
        try:
            page.goto(f'{base_url}/wall.html', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            test_results.append("✓ wall.html loads successfully")
            print("✓ wall.html loads")
        except Exception as e:
            bugs_found.append(f"wall.html failed to load: {e}")
            test_results.append(f"✗ wall.html load failed: {e}")
            print(f"✗ wall.html failed: {e}")

        # ========== TEST 2: SETTINGS.HTML ==========
        print("\n" + "=" * 80)
        print("TEST 2: SETTINGS.HTML")
        print("=" * 80)
        try:
            page.goto(f'{base_url}/settings.html', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(1000)
            test_results.append("✓ settings.html loads")
            print("✓ Page loads")

            # Test 2.1: Check image model radio buttons
            print("\n2.1: Testing image model selection...")
            imagen4_radio = page.locator('input[value="imagen-4.0-generate-001"]')
            if imagen4_radio.is_visible():
                test_results.append("✓ Imagen 4.0 radio button visible")
                print("  ✓ Imagen 4.0 option visible")
            else:
                bugs_found.append("Imagen 4.0 radio button not visible")
                test_results.append("✗ Imagen 4.0 radio button NOT visible")
                print("  ✗ Imagen 4.0 not visible")

            # Test 2.2: Check video model dropdown
            print("\n2.2: Testing video model dropdown...")
            video_select = page.locator('#video-model-select')
            if video_select.is_visible():
                test_results.append("✓ Video model dropdown visible")
                print("  ✓ Video dropdown visible")
            else:
                bugs_found.append("Video model dropdown not visible")
                test_results.append("✗ Video model dropdown NOT visible")
                print("  ✗ Video dropdown not visible")

            # Test 2.3: Check API token fields
            print("\n2.3: Testing API token fields...")
            gemini_token = page.locator('#gemini-token')
            if gemini_token.is_visible():
                test_results.append("✓ Gemini API token field visible")
                print("  ✓ Gemini token field visible")
            else:
                bugs_found.append("Gemini API token field not visible")
                test_results.append("✗ Gemini API token field NOT visible")
                print("  ✗ Gemini token field not visible")

            # Test 2.4: Test save button
            print("\n2.4: Testing save button...")
            save_btn = page.locator('button:has-text("Save Settings")')
            if save_btn.is_visible():
                test_results.append("✓ Save Settings button visible")
                print("  ✓ Save button visible")
            else:
                bugs_found.append("Save Settings button not visible")
                test_results.append("✗ Save Settings button NOT visible")
                print("  ✗ Save button not visible")

            page.screenshot(path='/tmp/settings_page.png', full_page=True)
            print("  ✓ Screenshot saved to /tmp/settings_page.png")

        except Exception as e:
            bugs_found.append(f"settings.html error: {e}")
            test_results.append(f"✗ settings.html error: {e}")
            print(f"✗ settings.html error: {e}")

        # ========== TEST 3: PLAYLISTS.HTML ==========
        print("\n" + "=" * 80)
        print("TEST 3: PLAYLISTS.HTML")
        print("=" * 80)
        try:
            page.goto(f'{base_url}/playlists.html', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(2000)  # Wait for playlists to load
            test_results.append("✓ playlists.html loads")
            print("✓ Page loads")

            # Test 3.1: Check New Playlist button
            print("\n3.1: Testing New Playlist button...")
            new_playlist_btn = page.locator('button:has-text("+ New Playlist")')
            if new_playlist_btn.is_visible():
                test_results.append("✓ New Playlist button visible")
                print("  ✓ New Playlist button visible")
            else:
                bugs_found.append("New Playlist button not visible")
                test_results.append("✗ New Playlist button NOT visible")
                print("  ✗ New Playlist button not visible")

            # Test 3.2: Check for playlist containers
            print("\n3.2: Testing playlist display...")
            playlists_container = page.locator('#playlists-container')
            playlist_divs = playlists_container.locator('.playlist').all()
            count = len(playlist_divs)
            test_results.append(f"✓ Found {count} playlist(s)")
            print(f"  ✓ Found {count} playlist(s)")

            if count > 0:
                # Test 3.3: Check playlist has action buttons
                print("\n3.3: Testing playlist action buttons...")
                first_playlist = playlist_divs[0]

                add_btn = first_playlist.locator('button:has-text("+ Add Asset Group")')
                if add_btn.is_visible():
                    test_results.append("✓ Add Asset Group button visible")
                    print("  ✓ Add Asset Group button visible")
                else:
                    bugs_found.append("Add Asset Group button not visible in playlist")
                    test_results.append("✗ Add Asset Group button NOT visible")
                    print("  ✗ Add Asset Group button not visible")

                rename_btn = first_playlist.locator('button:has-text("Rename")')
                if rename_btn.is_visible():
                    test_results.append("✓ Rename button visible")
                    print("  ✓ Rename button visible")
                else:
                    bugs_found.append("Rename button not visible in playlist")
                    test_results.append("✗ Rename button NOT visible")
                    print("  ✗ Rename button not visible")

                delete_btn = first_playlist.locator('button:has-text("Delete")')
                if delete_btn.is_visible():
                    test_results.append("✓ Delete button visible")
                    print("  ✓ Delete button visible")
                else:
                    bugs_found.append("Delete button not visible in playlist")
                    test_results.append("✗ Delete button NOT visible")
                    print("  ✗ Delete button not visible")

                # Test 3.4: Check for triplets (playlist items)
                print("\n3.4: Testing playlist items...")
                triplets_container = first_playlist.locator('.triplets')
                triplets = triplets_container.locator('.triplet').all()
                triplet_count = len(triplets)
                test_results.append(f"✓ Found {triplet_count} item(s) in first playlist")
                print(f"  ✓ Found {triplet_count} item(s)")

                if triplet_count > 0:
                    # Test 3.5: Check triplet has thumbnails and actions
                    print("\n3.5: Testing playlist item elements...")
                    first_triplet = triplets[0]

                    thumbnails = first_triplet.locator('.triplet-thumbnail').all()
                    if len(thumbnails) == 3:
                        test_results.append("✓ Triplet has 3 thumbnails")
                        print("  ✓ Has 3 thumbnails")
                    else:
                        bugs_found.append(f"Triplet has {len(thumbnails)} thumbnails, expected 3")
                        test_results.append(f"✗ Triplet has {len(thumbnails)} thumbnails")
                        print(f"  ✗ Has {len(thumbnails)} thumbnails")

                    edit_btn = first_triplet.locator('button:has-text("Edit")')
                    if edit_btn.is_visible():
                        test_results.append("✓ Triplet Edit button visible")
                        print("  ✓ Edit button visible")
                    else:
                        bugs_found.append("Triplet Edit button not visible")
                        test_results.append("✗ Triplet Edit button NOT visible")
                        print("  ✗ Edit button not visible")

                    remove_btn = first_triplet.locator('button:has-text("Remove")')
                    if remove_btn.is_visible():
                        test_results.append("✓ Triplet Remove button visible")
                        print("  ✓ Remove button visible")
                    else:
                        bugs_found.append("Triplet Remove button not visible")
                        test_results.append("✗ Triplet Remove button NOT visible")
                        print("  ✗ Remove button not visible")

            page.screenshot(path='/tmp/playlists_page.png', full_page=True)
            print("\n  ✓ Screenshot saved to /tmp/playlists_page.png")

        except Exception as e:
            bugs_found.append(f"playlists.html error: {e}")
            test_results.append(f"✗ playlists.html error: {e}")
            print(f"✗ playlists.html error: {e}")

        # ========== TEST 4: ASSET_GROUP.HTML ==========
        print("\n" + "=" * 80)
        print("TEST 4: ASSET_GROUP.HTML")
        print("=" * 80)
        try:
            # Use the first asset group from playlists (cat or dog)
            page.goto(f'{base_url}/asset_group.html?id=cat', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            test_results.append("✓ asset_group.html loads")
            print("✓ Page loads")

            # Test 4.1: Check asset group name is displayed
            print("\n4.1: Testing asset group name display...")
            name_element = page.locator('#asset-group-name')
            if name_element.is_visible():
                name_text = name_element.text_content()
                test_results.append(f"✓ Asset group name displayed: {name_text}")
                print(f"  ✓ Name displayed: {name_text}")
            else:
                bugs_found.append("Asset group name not visible")
                test_results.append("✗ Asset group name NOT visible")
                print("  ✗ Name not visible")

            # Test 4.2: Check three image panels exist
            print("\n4.2: Testing image panels...")
            panels = ['left', 'center', 'right']
            for panel_name in panels:
                panel = page.locator(f'#panel-{panel_name}')
                if panel.is_visible():
                    test_results.append(f"✓ {panel_name.capitalize()} panel visible")
                    print(f"  ✓ {panel_name.capitalize()} panel visible")
                else:
                    bugs_found.append(f"{panel_name.capitalize()} panel not visible")
                    test_results.append(f"✗ {panel_name.capitalize()} panel NOT visible")
                    print(f"  ✗ {panel_name.capitalize()} panel not visible")

            # Test 4.3: Check images are displayed
            print("\n4.3: Testing images...")
            for panel_name in panels:
                img = page.locator(f'#img-{panel_name}')
                if img.is_visible():
                    test_results.append(f"✓ {panel_name.capitalize()} image visible")
                    print(f"  ✓ {panel_name.capitalize()} image visible")
                else:
                    bugs_found.append(f"{panel_name.capitalize()} image not visible")
                    test_results.append(f"✗ {panel_name.capitalize()} image NOT visible")
                    print(f"  ✗ {panel_name.capitalize()} image not visible")

            # Test 4.4: Check version pickers
            print("\n4.4: Testing version pickers...")
            for panel_name in panels:
                picker = page.locator(f'#version-picker-{panel_name}')
                if picker.is_visible():
                    test_results.append(f"✓ {panel_name.capitalize()} version picker visible")
                    print(f"  ✓ {panel_name.capitalize()} version picker visible")

                    # Check for available versions
                    available_versions = picker.locator('.version-number.available').all()
                    count = len(available_versions)
                    test_results.append(f"✓ {panel_name.capitalize()} has {count} version(s)")
                    print(f"  ✓ Has {count} version(s)")
                else:
                    bugs_found.append(f"{panel_name.capitalize()} version picker not visible")
                    test_results.append(f"✗ {panel_name.capitalize()} version picker NOT visible")
                    print(f"  ✗ {panel_name.capitalize()} version picker not visible")

            # Test 4.5: Check prompt container
            print("\n4.5: Testing prompt container...")
            prompt_container = page.locator('#prompt-container')
            if prompt_container.is_visible():
                test_results.append("✓ Prompt container visible")
                print("  ✓ Prompt container visible")

                # Check Regenerate All button
                regen_all_btn = prompt_container.locator('button:has-text("Regenerate All")')
                if regen_all_btn.is_visible():
                    test_results.append("✓ Regenerate All button visible")
                    print("  ✓ Regenerate All button visible")
                else:
                    bugs_found.append("Regenerate All button not visible")
                    test_results.append("✗ Regenerate All button NOT visible")
                    print("  ✗ Regenerate All button not visible")
            else:
                bugs_found.append("Prompt container not visible")
                test_results.append("✗ Prompt container NOT visible")
                print("  ✗ Prompt container not visible")

            # Test 4.6: Check playlist checkboxes
            print("\n4.6: Testing playlist checkboxes...")
            playlist_checkboxes = page.locator('#playlist-checkboxes')
            if playlist_checkboxes.is_visible():
                checkboxes = playlist_checkboxes.locator('.playlist-checkbox').all()
                count = len(checkboxes)
                test_results.append(f"✓ Found {count} playlist checkbox(es)")
                print(f"  ✓ Found {count} playlist checkbox(es)")
            else:
                bugs_found.append("Playlist checkboxes container not visible")
                test_results.append("✗ Playlist checkboxes NOT visible")
                print("  ✗ Playlist checkboxes not visible")

            # Test 4.7: Check control buttons
            print("\n4.7: Testing control buttons...")
            duplicate_btn = page.locator('button:has-text("Duplicate")')
            if duplicate_btn.is_visible():
                test_results.append("✓ Duplicate button visible")
                print("  ✓ Duplicate button visible")
            else:
                bugs_found.append("Duplicate button not visible")
                test_results.append("✗ Duplicate button NOT visible")
                print("  ✗ Duplicate button not visible")

            delete_btn = page.locator('button:has-text("Delete Asset Group")')
            if delete_btn.is_visible():
                test_results.append("✓ Delete Asset Group button visible")
                print("  ✓ Delete Asset Group button visible")
            else:
                bugs_found.append("Delete Asset Group button not visible")
                test_results.append("✗ Delete Asset Group button NOT visible")
                print("  ✗ Delete Asset Group button not visible")

            page.screenshot(path='/tmp/asset_group_page.png', full_page=True)
            print("\n  ✓ Screenshot saved to /tmp/asset_group_page.png")

        except Exception as e:
            bugs_found.append(f"asset_group.html error: {e}")
            test_results.append(f"✗ asset_group.html error: {e}")
            print(f"✗ asset_group.html error: {e}")

        # ========== TEST 5: INDEX.HTML (Display page) ==========
        print("\n" + "=" * 80)
        print("TEST 5: INDEX.HTML (Display Page)")
        print("=" * 80)
        try:
            page.goto(f'{base_url}/index.html?id=left', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            test_results.append("✓ index.html loads with screen ID")
            print("✓ Page loads")

            # Test 5.1: Check display image exists
            print("\n5.1: Testing display image...")
            display_img = page.locator('#display')
            if display_img.is_visible():
                test_results.append("✓ Display image visible")
                print("  ✓ Display image visible")

                # Get the src to verify it's not empty
                src = display_img.get_attribute('src')
                if src:
                    test_results.append(f"✓ Display image has src attribute")
                    print(f"  ✓ Has src: {src[:50]}...")
                else:
                    bugs_found.append("Display image has no src")
                    test_results.append("✗ Display image has NO src")
                    print("  ✗ No src attribute")
            else:
                bugs_found.append("Display image not visible")
                test_results.append("✗ Display image NOT visible")
                print("  ✗ Display image not visible")

            # Test 5.2: Check loading indicator is hidden (images loaded)
            print("\n5.2: Testing loading state...")
            loading_el = page.locator('#loading')
            if loading_el.is_visible():
                bugs_found.append("Loading indicator still visible after load")
                test_results.append("✗ Loading indicator still visible")
                print("  ✗ Loading indicator still visible")
            else:
                test_results.append("✓ Loading indicator hidden")
                print("  ✓ Loading indicator hidden")

            page.screenshot(path='/tmp/index_page.png', full_page=True)
            print("\n  ✓ Screenshot saved to /tmp/index_page.png")

        except Exception as e:
            bugs_found.append(f"index.html error: {e}")
            test_results.append(f"✗ index.html error: {e}")
            print(f"✗ index.html error: {e}")

        # ========== Check for console errors and network failures ==========
        print("\n" + "=" * 80)
        print("GLOBAL CHECKS")
        print("=" * 80)

        print("\nChecking console errors...")
        error_messages = [msg for msg in console_messages if msg['type'] == 'error']
        if error_messages:
            print(f"  Found {len(error_messages)} console error(s):")
            for msg in error_messages[:5]:
                print(f"  - {msg['text']}")
                bugs_found.append(f"Console error: {msg['text']}")
            test_results.append(f"✗ Found {len(error_messages)} console errors")
        else:
            test_results.append("✓ No console errors")
            print("  ✓ No console errors")

        print("\nChecking network errors...")
        if failed_requests:
            print(f"  Found {len(failed_requests)} failed request(s):")
            for req in failed_requests[:5]:
                print(f"  - {req['url']} (HTTP {req['status']})")
                bugs_found.append(f"Failed request: {req['url']} (HTTP {req['status']})")
            test_results.append(f"✗ Found {len(failed_requests)} failed requests")
        else:
            test_results.append("✓ No failed network requests")
            print("  ✓ No failed requests")

        browser.close()

    return bugs_found, test_results


if __name__ == '__main__':
    print("\nStarting comprehensive test of all pages...\n")
    bugs, results = test_all_pages()

    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    print("\nAll Test Results:")
    for result in results:
        print(f"  {result}")

    print("\n" + "=" * 80)
    if bugs:
        print(f"BUGS FOUND: {len(bugs)}")
        print("=" * 80)
        for i, bug in enumerate(bugs, 1):
            print(f"{i}. {bug}")
    else:
        print("NO BUGS FOUND - ALL TESTS PASSED!")
        print("=" * 80)

    print("\nScreenshots saved:")
    print("  - /tmp/settings_page.png")
    print("  - /tmp/playlists_page.png")
    print("  - /tmp/asset_group_page.png")
    print("  - /tmp/index_page.png")
