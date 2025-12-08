# Changes Made

## Issue #1: Prompts now stored in database, not files

### Changes:
1. **Client-side (`public/asset_group.html`):**
   - Removed `savePromptFile()` function
   - Removed all calls to `savePromptFile()`
   - Removed auto-save logic (debouncing, beforeunload handlers)
   - Updated `regenerateAll()` to send prompt in request body for each screen
   - Updated `regenerateImage()` to remove file saving, just updates in memory
   - Updated `regenerateWithContext()` to remove file saving
   - Simplified `handlePromptInput()` to just update in-memory promptData

2. **Server-side (`src/triptic/server.py`):**
   - Removed `/asset-group/{name}/save-prompt` endpoint handler
   - Removed `_handle_save_prompt()` function
   - Updated `_handle_regenerate_image()` to require prompt in request body (removed fallback to file reading)
   - Updated `_handle_regenerate_with_context()` to get prompt from database instead of files

### Result:
- Prompts are now **only** stored in the database as part of AssetVersion records
- No more .prompt.txt files being created or read
- Prompts are passed in the request body when regenerating images
- Prompts persist with each version in the database

## Issue #2: Drag-and-drop image upload

### Changes:
1. **Client-side (`public/asset_group.html`):**
   - Updated `drop` event handler in `setupDragAndDrop()` to detect file drops
   - When a file is dropped onto a panel, it validates it's an image and calls `uploadImage()`
   - File drops take priority over panel swapping
   - Non-image files show an error message

### Result:
- Users can now drag an image file from their computer onto any frame (left/center/right)
- The image is uploaded as a new version for that screen
- Works alongside existing panel swap/copy functionality

## Testing

To test these changes:

1. **Test prompt storage:**
   - Create a new asset group
   - Edit the main prompt
   - Hit "Regenerate All"
   - Check that the image is generated with the correct prompt
   - Verify no .prompt.txt files are created in the filesystem
   - Check the database to confirm the prompt is stored in the AssetVersion

2. **Test version count:**
   - Create a new asset group and regenerate (should create version 1)
   - Edit the prompt and regenerate again (should create version 2, NOT version 3)
   - Verify the version picker shows only 2 versions

3. **Test drag-and-drop:**
   - Open an existing asset group
   - Drag an image file from your computer onto one of the frames
   - Verify it uploads successfully
   - Check that a new version was created
