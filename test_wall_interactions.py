"""
Comprehensive interaction test for wall.html page on production site.
Tests all user interactions and documents any bugs found.
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


def test_wall_interactions():
    """Test all interactions on the wall.html page."""

    bugs_found = []
    test_results = []

    # Load .env file if present
    load_env_file()

    # Get credentials from environment
    username = os.environ.get('TRIPTIC_AUTH_USERNAME')
    password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

    if not username or not password:
        print("ERROR: TRIPTIC_AUTH_USERNAME and TRIPTIC_AUTH_PASSWORD must be set in environment")
        print("Please set these in your .env file or export them in your shell")
        return [], ["✗ Missing authentication credentials in environment"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Set up basic auth
        context = browser.new_context(
            http_credentials={
                "username": username,
                "password": password
            }
        )
        page = context.new_page()

        # Track console errors
        console_messages = []
        page.on("console", lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text
        }))

        # Track network errors
        failed_requests = []
        def handle_response(response):
            if response.status >= 400:
                failed_requests.append({
                    'url': response.url,
                    'status': response.status
                })
        page.on("response", handle_response)

        print("=" * 80)
        print("WALL.HTML COMPREHENSIVE INTERACTION TEST")
        print("=" * 80)
        print()

        # Navigate to wall.html
        print("1. Loading wall.html...")
        try:
            page.goto('https://triptic-daveey.fly.dev/wall.html', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            page.wait_for_timeout(2000)  # Extra time for JavaScript to execute
            test_results.append("✓ Page loads successfully")
            print("   ✓ Page loaded")
        except Exception as e:
            bugs_found.append(f"Page failed to load: {e}")
            test_results.append(f"✗ Page load failed: {e}")
            print(f"   ✗ Failed: {e}")
            browser.close()
            return bugs_found, test_results

        # Take initial screenshot
        page.screenshot(path='/tmp/wall_initial.png', full_page=True)
        print("   ✓ Initial screenshot saved to /tmp/wall_initial.png")

        # Test 2: Check that all control elements are visible
        print("\n2. Testing control elements visibility...")
        controls_to_check = [
            ('#scale', 'Scale dropdown'),
            ('#gap', 'Gap dropdown'),
            ('#frequency', 'Image Change dropdown'),
            ('#playlist', 'Playlist dropdown'),
            ('button:has-text("Reload Screens")', 'Reload Screens button'),
            ('#time', 'Time display'),
        ]

        for selector, name in controls_to_check:
            try:
                element = page.locator(selector)
                if element.is_visible():
                    test_results.append(f"✓ {name} is visible")
                    print(f"   ✓ {name} visible")
                else:
                    bugs_found.append(f"{name} is not visible")
                    test_results.append(f"✗ {name} is NOT visible")
                    print(f"   ✗ {name} NOT visible")
            except Exception as e:
                bugs_found.append(f"{name} error: {e}")
                test_results.append(f"✗ {name} error: {e}")
                print(f"   ✗ {name} error: {e}")

        # Test 3: Check navigation controls
        print("\n3. Testing navigation controls...")
        nav_controls = [
            ('button:has-text("< Prev")', 'Previous button'),
            ('button:has-text("Next >")', 'Next button'),
            ('#current-asset-group-link', 'Current asset group link'),
        ]

        for selector, name in nav_controls:
            try:
                element = page.locator(selector)
                if element.is_visible():
                    test_results.append(f"✓ {name} is visible")
                    print(f"   ✓ {name} visible")
                else:
                    bugs_found.append(f"{name} is not visible")
                    test_results.append(f"✗ {name} is NOT visible")
                    print(f"   ✗ {name} NOT visible")
            except Exception as e:
                bugs_found.append(f"{name} error: {e}")
                test_results.append(f"✗ {name} error: {e}")
                print(f"   ✗ {name} error: {e}")

        # Test 4: Check that iframes are present
        print("\n4. Testing iframes...")
        iframes = [
            ('#iframe-left', 'Left iframe'),
            ('#iframe-center', 'Center iframe'),
            ('#iframe-right', 'Right iframe'),
        ]

        for selector, name in iframes:
            try:
                element = page.locator(selector)
                if element.is_visible():
                    src = element.get_attribute('src')
                    test_results.append(f"✓ {name} is present (src: {src})")
                    print(f"   ✓ {name} present (src: {src})")
                else:
                    bugs_found.append(f"{name} is not visible")
                    test_results.append(f"✗ {name} is NOT visible")
                    print(f"   ✗ {name} NOT visible")
            except Exception as e:
                bugs_found.append(f"{name} error: {e}")
                test_results.append(f"✗ {name} error: {e}")
                print(f"   ✗ {name} error: {e}")

        # Test 5: Test scale dropdown interaction
        print("\n5. Testing scale dropdown...")
        try:
            scale_select = page.locator('#scale')
            original_value = scale_select.input_value()
            print(f"   Current scale: {original_value}")

            # Change to 50%
            scale_select.select_option('0.5')
            page.wait_for_timeout(1000)
            new_value = scale_select.input_value()

            if new_value == '0.5':
                test_results.append("✓ Scale dropdown works (changed to 50%)")
                print("   ✓ Scale changed to 50%")
                page.screenshot(path='/tmp/wall_scale_50.png', full_page=True)
                print("   ✓ Screenshot saved to /tmp/wall_scale_50.png")

                # Change back
                scale_select.select_option(original_value)
                page.wait_for_timeout(500)
            else:
                bugs_found.append(f"Scale dropdown did not update (expected 0.5, got {new_value})")
                test_results.append(f"✗ Scale dropdown failed to update")
                print(f"   ✗ Scale failed to change")
        except Exception as e:
            bugs_found.append(f"Scale dropdown error: {e}")
            test_results.append(f"✗ Scale dropdown error: {e}")
            print(f"   ✗ Scale error: {e}")

        # Test 6: Test gap dropdown interaction
        print("\n6. Testing gap dropdown...")
        try:
            gap_select = page.locator('#gap')
            original_value = gap_select.input_value()
            print(f"   Current gap: {original_value}")

            # Change to 40px
            gap_select.select_option('40')
            page.wait_for_timeout(1000)
            new_value = gap_select.input_value()

            if new_value == '40':
                test_results.append("✓ Gap dropdown works (changed to 40px)")
                print("   ✓ Gap changed to 40px")
                page.screenshot(path='/tmp/wall_gap_40.png', full_page=True)
                print("   ✓ Screenshot saved to /tmp/wall_gap_40.png")

                # Change back
                gap_select.select_option(original_value)
                page.wait_for_timeout(500)
            else:
                bugs_found.append(f"Gap dropdown did not update (expected 40, got {new_value})")
                test_results.append(f"✗ Gap dropdown failed to update")
                print(f"   ✗ Gap failed to change")
        except Exception as e:
            bugs_found.append(f"Gap dropdown error: {e}")
            test_results.append(f"✗ Gap dropdown error: {e}")
            print(f"   ✗ Gap error: {e}")

        # Test 7: Test frequency dropdown interaction
        print("\n7. Testing frequency dropdown...")
        try:
            frequency_select = page.locator('#frequency')
            original_value = frequency_select.input_value()
            print(f"   Current frequency: {original_value}s")

            # Change to 10 seconds
            frequency_select.select_option('10')
            page.wait_for_timeout(1000)
            new_value = frequency_select.input_value()

            if new_value == '10':
                test_results.append("✓ Frequency dropdown works (changed to 10s)")
                print("   ✓ Frequency changed to 10s")

                # Check for save indicator
                save_indicator = page.locator('#save-indicator')
                if save_indicator.is_visible():
                    test_results.append("✓ Save indicator appears after frequency change")
                    print("   ✓ Save indicator appeared")
                else:
                    bugs_found.append("Save indicator did not appear after frequency change")
                    test_results.append("✗ Save indicator did NOT appear")
                    print("   ✗ Save indicator did not appear")

                # Change back
                frequency_select.select_option(original_value)
                page.wait_for_timeout(500)
            else:
                bugs_found.append(f"Frequency dropdown did not update (expected 10, got {new_value})")
                test_results.append(f"✗ Frequency dropdown failed to update")
                print(f"   ✗ Frequency failed to change")
        except Exception as e:
            bugs_found.append(f"Frequency dropdown error: {e}")
            test_results.append(f"✗ Frequency dropdown error: {e}")
            print(f"   ✗ Frequency error: {e}")

        # Test 8: Test playlist dropdown
        print("\n8. Testing playlist dropdown...")
        try:
            playlist_select = page.locator('#playlist')

            # Get all options
            options = playlist_select.locator('option').all()
            option_texts = [opt.text_content() for opt in options]
            print(f"   Available playlists: {option_texts}")

            if len(options) > 1:  # More than just "Loading..."
                original_value = playlist_select.input_value()
                print(f"   Current playlist: {original_value}")

                # Try to select a different playlist
                if len(options) > 1:
                    # Get the second option value
                    second_option = options[1].get_attribute('value')
                    print(f"   Changing to: {second_option}")

                    playlist_select.select_option(second_option)
                    page.wait_for_timeout(2000)  # Wait for reload
                    new_value = playlist_select.input_value()

                    if new_value == second_option:
                        test_results.append(f"✓ Playlist dropdown works (changed to {second_option})")
                        print(f"   ✓ Playlist changed to {second_option}")

                        # Check for save indicator
                        page.wait_for_timeout(500)
                        save_indicator = page.locator('#save-indicator')
                        if save_indicator.is_visible():
                            test_results.append("✓ Save indicator appears after playlist change")
                            print("   ✓ Save indicator appeared")

                        # Check if screens reloaded (iframe src should have timestamp)
                        iframe_left = page.locator('#iframe-left')
                        src = iframe_left.get_attribute('src')
                        if '&t=' in src:
                            test_results.append("✓ Screens reloaded after playlist change")
                            print("   ✓ Screens reloaded")
                        else:
                            bugs_found.append("Screens did not reload after playlist change")
                            test_results.append("✗ Screens did NOT reload")
                            print("   ✗ Screens did not reload")

                        # Change back
                        playlist_select.select_option(original_value)
                        page.wait_for_timeout(2000)
                    else:
                        bugs_found.append(f"Playlist dropdown did not update")
                        test_results.append(f"✗ Playlist dropdown failed to update")
                        print(f"   ✗ Playlist failed to change")
            else:
                test_results.append("⚠ Only one playlist available, cannot test switching")
                print("   ⚠ Only one playlist available")
        except Exception as e:
            bugs_found.append(f"Playlist dropdown error: {e}")
            test_results.append(f"✗ Playlist dropdown error: {e}")
            print(f"   ✗ Playlist error: {e}")

        # Test 9: Test Reload Screens button
        print("\n9. Testing Reload Screens button...")
        try:
            # Get current iframe src
            iframe_left = page.locator('#iframe-left')
            original_src = iframe_left.get_attribute('src')
            print(f"   Original iframe src: {original_src}")

            # Click reload button
            reload_btn = page.locator('button:has-text("Reload Screens")')
            reload_btn.click()
            page.wait_for_timeout(1000)

            # Check if src changed (should have new timestamp)
            new_src = iframe_left.get_attribute('src')
            print(f"   New iframe src: {new_src}")

            if new_src != original_src and '&t=' in new_src:
                test_results.append("✓ Reload Screens button works")
                print("   ✓ Reload button works")
            else:
                bugs_found.append("Reload Screens button did not update iframe src")
                test_results.append("✗ Reload Screens button did NOT work")
                print("   ✗ Reload button did not work")
        except Exception as e:
            bugs_found.append(f"Reload Screens button error: {e}")
            test_results.append(f"✗ Reload Screens button error: {e}")
            print(f"   ✗ Reload error: {e}")

        # Test 10: Test time display updates
        print("\n10. Testing time display...")
        try:
            time_display = page.locator('#time')
            initial_time = time_display.text_content()
            print(f"   Initial time: {initial_time}")

            # Wait 2 seconds
            page.wait_for_timeout(2000)
            new_time = time_display.text_content()
            print(f"   Time after 2s: {new_time}")

            if new_time != initial_time and new_time != '--:--:--':
                test_results.append("✓ Time display updates")
                print("   ✓ Time updates")
            else:
                bugs_found.append(f"Time display does not update (stayed at {initial_time})")
                test_results.append("✗ Time display does NOT update")
                print("   ✗ Time does not update")
        except Exception as e:
            bugs_found.append(f"Time display error: {e}")
            test_results.append(f"✗ Time display error: {e}")
            print(f"   ✗ Time error: {e}")

        # Test 11: Test Previous button
        print("\n11. Testing Previous button...")
        try:
            current_link = page.locator('#current-asset-group-link')
            original_text = current_link.text_content()
            print(f"   Current asset group: {original_text}")

            # Click previous button
            prev_btn = page.locator('button:has-text("< Prev")')
            prev_btn.click()
            page.wait_for_timeout(2000)  # Wait for reload

            new_text = current_link.text_content()
            print(f"   Asset group after Prev: {new_text}")

            if new_text != original_text:
                test_results.append(f"✓ Previous button works (changed from '{original_text}' to '{new_text}')")
                print(f"   ✓ Previous button works")

                # Check if screens reloaded
                iframe_left = page.locator('#iframe-left')
                src = iframe_left.get_attribute('src')
                if '&t=' in src:
                    test_results.append("✓ Screens reloaded after Previous")
                    print("   ✓ Screens reloaded")
            else:
                bugs_found.append("Previous button did not change asset group")
                test_results.append("✗ Previous button did NOT work")
                print("   ✗ Previous button did not work")
        except Exception as e:
            bugs_found.append(f"Previous button error: {e}")
            test_results.append(f"✗ Previous button error: {e}")
            print(f"   ✗ Previous error: {e}")

        # Test 12: Test Next button
        print("\n12. Testing Next button...")
        try:
            current_link = page.locator('#current-asset-group-link')
            original_text = current_link.text_content()
            print(f"   Current asset group: {original_text}")

            # Click next button
            next_btn = page.locator('button:has-text("Next >")')
            next_btn.click()
            page.wait_for_timeout(2000)  # Wait for reload

            new_text = current_link.text_content()
            print(f"   Asset group after Next: {new_text}")

            if new_text != original_text:
                test_results.append(f"✓ Next button works (changed from '{original_text}' to '{new_text}')")
                print(f"   ✓ Next button works")

                # Check if screens reloaded
                iframe_left = page.locator('#iframe-left')
                src = iframe_left.get_attribute('src')
                if '&t=' in src:
                    test_results.append("✓ Screens reloaded after Next")
                    print("   ✓ Screens reloaded")
            else:
                bugs_found.append("Next button did not change asset group")
                test_results.append("✗ Next button did NOT work")
                print("   ✗ Next button did not work")
        except Exception as e:
            bugs_found.append(f"Next button error: {e}")
            test_results.append(f"✗ Next button error: {e}")
            print(f"   ✗ Next error: {e}")

        # Test 13: Test current asset group link
        print("\n13. Testing current asset group link...")
        try:
            current_link = page.locator('#current-asset-group-link')
            href = current_link.get_attribute('href')
            link_text = current_link.text_content()
            print(f"   Link text: {link_text}")
            print(f"   Link href: {href}")

            if href and href.startswith('/asset_group.html?id='):
                test_results.append(f"✓ Asset group link is valid ({href})")
                print(f"   ✓ Link is valid")

                # Test if link is clickable (don't actually navigate)
                if current_link.is_visible():
                    test_results.append("✓ Asset group link is clickable")
                    print("   ✓ Link is clickable")
            else:
                bugs_found.append(f"Asset group link href is invalid: {href}")
                test_results.append(f"✗ Asset group link is invalid")
                print(f"   ✗ Link is invalid")
        except Exception as e:
            bugs_found.append(f"Asset group link error: {e}")
            test_results.append(f"✗ Asset group link error: {e}")
            print(f"   ✗ Link error: {e}")

        # Test 14: Test playlist header link
        print("\n14. Testing playlist header link...")
        try:
            playlist_header = page.locator('#playlist-header')
            playlist_link = playlist_header.locator('.playlist-name-link')

            if playlist_link.is_visible():
                link_text = playlist_link.text_content()
                print(f"   Playlist link text: {link_text}")
                test_results.append(f"✓ Playlist header link is visible ({link_text})")
                print(f"   ✓ Playlist header link visible")

                # Check if it's styled as clickable
                cursor = playlist_link.evaluate('el => window.getComputedStyle(el).cursor')
                if cursor == 'pointer':
                    test_results.append("✓ Playlist header link has pointer cursor")
                    print("   ✓ Has pointer cursor")
                else:
                    bugs_found.append(f"Playlist header link cursor is '{cursor}', expected 'pointer'")
                    test_results.append(f"✗ Playlist header link cursor is not pointer")
                    print(f"   ✗ Cursor is not pointer")
            else:
                bugs_found.append("Playlist header link is not visible")
                test_results.append("✗ Playlist header link is NOT visible")
                print("   ✗ Link not visible")
        except Exception as e:
            bugs_found.append(f"Playlist header link error: {e}")
            test_results.append(f"✗ Playlist header link error: {e}")
            print(f"   ✗ Playlist header error: {e}")

        # Test 15: Test playlist info display
        print("\n15. Testing playlist info display...")
        try:
            playlist_info = page.locator('#playlist-info')
            info_text = playlist_info.text_content()
            print(f"   Playlist info: {info_text}")

            if info_text and info_text.strip():
                # Should be in format: "playlist X/Y · Zm" or similar
                test_results.append(f"✓ Playlist info displays: {info_text}")
                print(f"   ✓ Info displays correctly")
            else:
                bugs_found.append("Playlist info is empty")
                test_results.append("✗ Playlist info is empty")
                print("   ✗ Info is empty")
        except Exception as e:
            bugs_found.append(f"Playlist info error: {e}")
            test_results.append(f"✗ Playlist info error: {e}")
            print(f"   ✗ Playlist info error: {e}")

        # Test 16: Check console errors
        print("\n16. Checking console for errors...")
        error_messages = [msg for msg in console_messages if msg['type'] == 'error']
        if error_messages:
            print(f"   Found {len(error_messages)} console errors:")
            for msg in error_messages[:5]:  # Show first 5
                print(f"   - {msg['text']}")
                bugs_found.append(f"Console error: {msg['text']}")
            test_results.append(f"✗ Found {len(error_messages)} console errors")
        else:
            test_results.append("✓ No console errors")
            print("   ✓ No console errors")

        # Test 17: Check network errors
        print("\n17. Checking for network errors...")
        if failed_requests:
            print(f"   Found {len(failed_requests)} failed requests:")
            for req in failed_requests[:5]:  # Show first 5
                print(f"   - {req['url']} (HTTP {req['status']})")
                bugs_found.append(f"Failed request: {req['url']} (HTTP {req['status']})")
            test_results.append(f"✗ Found {len(failed_requests)} failed network requests")
        else:
            test_results.append("✓ No failed network requests")
            print("   ✓ No failed requests")

        # Take final screenshot
        page.screenshot(path='/tmp/wall_final.png', full_page=True)
        print("\n18. Final screenshot saved to /tmp/wall_final.png")

        browser.close()

    return bugs_found, test_results


if __name__ == '__main__':
    bugs, results = test_wall_interactions()

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
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
        print("NO BUGS FOUND")
        print("=" * 80)

    print("\nScreenshots saved:")
    print("  - /tmp/wall_initial.png")
    print("  - /tmp/wall_scale_50.png (if test ran)")
    print("  - /tmp/wall_gap_40.png (if test ran)")
    print("  - /tmp/wall_final.png")
