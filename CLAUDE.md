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

## Creating Playlists and Asset Groups via API

When creating themed playlists with multiple asset groups, use the following workflow:

### Authentication

The production server requires Basic Auth:
```bash
# Get credentials from .env
TRIPTIC_AUTH_USERNAME=daveey
TRIPTIC_AUTH_PASSWORD=daviddavid

# Use with curl
curl -u "${TRIPTIC_AUTH_USERNAME}:${TRIPTIC_AUTH_PASSWORD}" ...
```

### 1. Create a Playlist

```bash
curl -s -u "daveey:daviddavid" -X POST https://triptic-daveey.fly.dev/playlist/create \
  -H "Content-Type: application/json" \
  -d '{"name": "playlist-name"}'
```

### 2. Create Asset Groups

Asset groups use `id` (not `name`) in the JSON body. Use `/` for hierarchical naming:

```bash
curl -s -u "daveey:daviddavid" -X POST https://triptic-daveey.fly.dev/asset-group/create \
  -H "Content-Type: application/json" \
  -d '{"id": "theme/subject-name"}'
```

### 3. Add Asset Groups to Playlist

URL-encode the `/` as `%2F`:

```bash
curl -s -u "daveey:daviddavid" -X POST \
  "https://triptic-daveey.fly.dev/asset-group/theme%2Fsubject-name/add-to-playlists" \
  -H "Content-Type: application/json" \
  -d '{"playlists": ["playlist-name"]}'
```

### 4. Queue Image Generation

Queue generation for each screen (left, center, right) with a prompt:

```bash
curl -s -u "daveey:daviddavid" -X POST \
  "https://triptic-daveey.fly.dev/asset-group/theme%2Fsubject-name/regenerate/left" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your detailed image prompt here"}'
```

### Full Example: Creating a Themed Playlist

```bash
# Variables
AUTH="daveey:daviddavid"
BASE="https://triptic-daveey.fly.dev"
PLAYLIST="surreal"
THEME="surreal"

# 1. Create playlist
curl -s -u "$AUTH" -X POST "$BASE/playlist/create" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$PLAYLIST\"}"

# 2. Create asset groups
for name in melting-time floating-apple elephant-parade; do
  curl -s -u "$AUTH" -X POST "$BASE/asset-group/create" \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"$THEME/$name\"}"
done

# 3. Add to playlist
for name in melting-time floating-apple elephant-parade; do
  curl -s -u "$AUTH" -X POST "$BASE/asset-group/${THEME}%2F${name}/add-to-playlists" \
    -H "Content-Type: application/json" \
    -d "{\"playlists\": [\"$PLAYLIST\"]}"
done

# 4. Queue generation for all screens
PROMPT="Melting clocks in desert, Salvador Dalí style"
for screen in left center right; do
  curl -s -u "$AUTH" -X POST "$BASE/asset-group/${THEME}%2Fmelting-time/regenerate/$screen" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$PROMPT\"}"
done
```

## Complete API Reference

All endpoints require Basic Auth on production: `-u "daveey:daviddavid"`

URL-encode `/` as `%2F` in asset group IDs (e.g., `theme/name` → `theme%2Fname`)

### Playlist Management

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| List all playlists | GET | `/playlists` | - |
| Get current playlist | GET | `/playlist` | - |
| Get playlist by name | GET | `/playlists/{name}` | - |
| Get playlist asset groups | GET | `/playlists/{name}/asset-groups` | - |
| Set current playlist | POST | `/playlist` | `{"name": "playlist-name"}` |
| Create playlist | POST | `/playlist/create` | `{"name": "playlist-name"}` |
| Rename playlist | POST | `/playlist/{name}/rename` | `{"new_name": "new-name"}` |
| Delete playlist | DELETE | `/playlist/{name}` | - |
| Reorder playlist | POST | `/playlists/{name}/reorder` | `{"order": ["asset1", "asset2"]}` |
| Remove from playlist | POST | `/playlists/{name}/remove` | `{"asset_group": "asset-id"}` |

### Asset Group Management

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| List all asset groups | GET | `/asset-groups` | - |
| Get asset group | GET | `/asset-group/{id}` | - |
| Create asset group | POST | `/asset-group/create` | `{"id": "theme/name"}` |
| Create from prompt | POST | `/asset-group/create-from-prompt` | `{"prompt": "...", "playlist": "...", "name": "..."}` |
| Delete asset group | DELETE | `/asset-group/{id}` | - |
| Add to playlists | POST | `/asset-group/{id}/add-to-playlists` | `{"playlists": ["p1", "p2"]}` |
| Rename asset group | POST | `/asset-group/{id}/rename` | `{"newName": "new-name"}` |
| Duplicate asset group | POST | `/asset-group/{id}/duplicate` | `{"newName": "copy-name"}` |

### Image Generation & Manipulation

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Generate image | POST | `/asset-group/{id}/regenerate/{screen}` | `{"prompt": "..."}` |
| Generate with context | POST | `/asset-group/{id}/regenerate-with-context/{screen}` | `{"contextScreens": ["left", "right"]}` |
| Edit image | POST | `/asset-group/{id}/edit/{screen}` | `{"prompt": "edit instructions"}` |
| Upload image | POST | `/asset-group/{id}/upload/{screen}` | Raw image bytes |
| Upload from URL | POST | `/asset-group/{id}/upload-from-url/{screen}` | `{"url": "...", "prompt": "..."}` |
| Upload video | POST | `/asset-group/{id}/upload-video/{screen}` | Raw video bytes |
| Generate video | POST | `/asset-group/{id}/video/{screen}` | - |
| Flip image | POST | `/asset-group/{id}/flip/{screen}` | - |
| Swap screens | POST | `/asset-group/{id}/swap` | `{"screen1": "left", "screen2": "right"}` |
| Copy to screen | POST | `/asset-group/{id}/copy` | `{"sourceScreen": "left", "targetScreen": "right"}` |

**Screen values:** `left`, `center`, `right`

### Version Management

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Get versions | GET | `/asset-group/{id}/versions/{screen}` | - |
| Restore version | POST | `/asset-group/{id}/version/{screen}` | `{"version": 1}` |
| Delete version | POST | `/asset-group/{id}/delete-version/{screen}` | - |

### Generation Queue

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Get queue | GET | `/generation-queue` | - |
| Cancel generations | POST | `/generation-queue/cancel` | `{"uuids": ["uuid1", "uuid2"]}` |

### Prompt Enhancement (AI-assisted)

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Expand prompt | POST | `/prompt/fluff` | `{"prompt": "simple prompt"}` |
| Generate 3 sub-prompts | POST | `/prompt/fluff-plus` | `{"prompt": "theme"}` |
| Generate matching prompt | POST | `/prompt/diff-single` | `{"main_prompt": "...", "screen": "center", "other_prompts": {"left": "...", "right": "..."}}` |

### Display Control

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Get current asset group | GET | `/state/current-asset-group` | - |
| Set/lock asset group | POST | `/state/current-asset-group` | `{"asset_group": "id"}` or `{}` to clear |

### System & Config

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Get config | GET | `/config` | - |
| Update config | POST | `/config` | `{...config...}` |
| Get settings | GET | `/settings` | - |
| Update settings | POST | `/settings` | `{...settings...}` |
| Get video models | GET | `/video-models` | - |
| Video job status | GET | `/video-job/{job_id}` | - |
| Screen heartbeat | POST | `/heartbeat/{screen_id}` | - |
| Frame logs | GET | `/frame-logs` | - |
| Post frame log | POST | `/frame-log` | `{"screen": "...", "level": "...", "message": "..."}` |
| Generate thumbnails | POST | `/admin/generate-thumbnails` | - |

### Static Content

| Path | Description |
|------|-------------|
| `/` | Redirects to `/wall.html` |
| `/wall.html` | Main display wall |
| `/playlists.html` | Playlist management UI |
| `/asset_group.html?id={id}` | Asset group editor |
| `/content/assets/{uuid}.png` | Serve image by UUID |
| `/content/assets/{uuid}_thumb.png` | Serve thumbnail |
| `/content/assets/{uuid}.mp4` | Serve video |
| `/defaults/generating.png` | Placeholder during generation |

### Quick Reference: Common Tasks

**Display a specific playlist on the wall:**
```bash
curl -u "$AUTH" -X POST "$BASE/playlist" \
  -H "Content-Type: application/json" \
  -d '{"name": "princess-stained-glass"}'
```

**Lock display to a single asset group:**
```bash
curl -u "$AUTH" -X POST "$BASE/state/current-asset-group" \
  -H "Content-Type: application/json" \
  -d '{"asset_group": "princess/aurora"}'
```

**Unlock display (return to playlist rotation):**
```bash
curl -u "$AUTH" -X POST "$BASE/state/current-asset-group" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Generate all 3 screens from a theme (AI generates sub-prompts):**
```bash
curl -u "$AUTH" -X POST "$BASE/asset-group/create-from-prompt" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "underwater coral reef", "playlist": "ocean", "name": "coral-reef"}'
```

**Check generation queue status:**
```bash
curl -u "$AUTH" "$BASE/generation-queue"
```

**Cancel pending generations:**
```bash
curl -u "$AUTH" -X POST "$BASE/generation-queue/cancel" \
  -H "Content-Type: application/json" \
  -d '{"uuids": ["uuid1", "uuid2"]}'
```
