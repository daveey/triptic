# Project Guidelines

## Code Philosophy

**Use asserts, not defensive branching.**

- Do NOT use fallback code paths or handle "old" ways of doing things
- Do NOT use defensive if/else checks when the precondition should always be true
- DO use asserts to document and enforce expectations
- DO let the code fail fast with clear error messages when assumptions are violated

Examples:

```python
# ❌ BAD: Defensive branching
def get_asset(name):
    path = storage.get_path(name)
    if path:
        return path
    else:
        # Try legacy path
        return legacy_path(name)

# ✅ GOOD: Assert expectations
def get_asset(name):
    path = storage.get_path(name)
    assert path, f"Asset not found: {name}"
    return path
```

The goal is clean, maintainable code that fails loudly when invariants are broken, rather than silently covering up problems with fallback logic.

## Testing Requirements

**CRITICAL: Always test commands and code changes before marking work as complete.**

When implementing or modifying CLI commands, API integrations, or any executable code:

1. **Test immediately after implementation** - Don't assume the code works
2. **Test with actual execution** - Run the command/function with real inputs
3. **Test error cases** - Verify error handling works as expected
4. **Test with minimal/no configuration** - Ensure helpful error messages appear
5. **Document test results** - Show the user that testing was performed

If a test fails:
- Fix the issue immediately
- Test again
- Only mark as complete after successful test execution

## Examples

❌ **Bad**: Implement feature → Tell user it's done → User finds it broken

✅ **Good**: Implement feature → Test it → Fix any issues → Test again → Confirm it works → Tell user

## Frontend Testing with Playwright

**CRITICAL: When fixing frontend bugs, always write a Playwright test first.**

### Test-Driven Bug Fix Workflow

1. **Write the test** - Create a Playwright test that reproduces the bug
2. **Verify it fails** - Run the test and confirm it catches the issue
3. **Fix the bug** - Implement the fix in the code
4. **Verify it passes** - Run the test again and confirm it now passes

This ensures:
- The bug is properly understood and reproducible
- The fix actually works
- The bug won't reoccur in the future (regression protection)

### Running Frontend Tests

```bash
# Run all frontend tests (automatically starts test server on port 3001)
uv run pytest tests/test_frontend_playwright.py -v

# Run specific test
uv run pytest tests/test_frontend_playwright.py::test_name -v

# Tests have a 30-second timeout to prevent hanging
```

### Writing Frontend Tests

Tests are in `tests/test_frontend_playwright.py`. Example:

```python
def test_feature_works(page: Page, base_url: str):
    """Test that feature X works correctly."""
    # Navigate to page
    page.goto(f"{base_url}/page.html")
    page.wait_for_load_state("networkidle")

    # Interact and assert
    button = page.get_by_role("button", name="Click Me")
    expect(button).to_be_visible()
```

**Key Points:**
- Test server runs on port 3001 (production uses 3000)
- Tests automatically start/stop the server
- Use `page.wait_for_load_state("networkidle")` after navigation
- Add timeouts for slow operations: `page.wait_for_timeout(1000)`
- Track network requests to catch API failures

### Visual Verification with Screenshots

**IMPORTANT: Always visually verify frontend changes using screenshots.**

After making frontend changes, use Playwright to capture screenshots and visually inspect them:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    # Navigate to the page
    page.goto('http://localhost:3000/asset_group.html?id=apple')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    # Check element visibility programmatically
    element = page.locator('#my-element')
    is_visible = element.is_visible()
    print(f"Element visible: {is_visible}")

    # Take a screenshot for visual inspection
    page.screenshot(path='/tmp/page_screenshot.png', full_page=True)
    print("Screenshot saved to /tmp/page_screenshot.png")

    browser.close()
```

**Then use the Read tool to visually inspect the screenshot:**

```python
# Claude can view images directly
# Use: Read tool with path='/tmp/page_screenshot.png'
```

**Benefits:**
- Catch visual regressions that tests might miss
- Verify layout, spacing, colors, and styling
- Ensure UI elements are properly positioned
- Confirm responsive design works correctly
- See exactly what the user sees

**When to use screenshots:**
- After fixing CSS/styling issues
- When debugging "element not visible" test failures
- When verifying complex UI interactions
- After making layout changes
- To document "before" and "after" states

## Gen-AI Integration Tests

When making changes to gen-ai endpoints or image generation code, run the integration tests:

```bash
# Run all gen-ai integration tests (requires GEMINI_API_KEY)
pytest tests/test_genai_integration.py -v -m genai

# Run quick tests only (excludes video generation which takes ~10 minutes)
pytest tests/test_genai_integration.py -v -m "genai and not slow"

# Run all tests including slow video generation tests
pytest tests/test_genai_integration.py -v -m "genai or slow"
```

**Important Notes:**
- Tests require a valid `GEMINI_API_KEY` environment variable or `.env` file
- Tests will be automatically skipped if no API key is available
- Video generation tests are marked as `slow` and can take 5-10 minutes
- Tests use real API calls and will consume API quota

## Code Quality

- Use type hints for function parameters and return values
- Add docstrings for public functions
- Handle errors gracefully with clear messages
- Follow the project's existing code style
