# Image Generation with triptic

Triptic now supports AI-powered image generation using Google's Imagen 4 Fast model via the official Google Gen AI SDK.

## Setup

1. **Install dependencies** (already done if you installed triptic with uv):
   ```bash
   uv add google-genai pillow
   ```

2. **Get a Gemini API key**:
   - Visit https://aistudio.google.com/apikey
   - Sign in with your Google account
   - Create a new API key

3. **Configure your API key** (choose one method):

   **Option A: Interactive prompt** (recommended for first-time setup)
   ```bash
   uv run triptic imgen test "A beautiful sunset" -p animals
   # You'll be prompted to enter your API key, which will be saved to .env
   ```

   **Option B: Manual .env file**
   ```bash
   echo "GEMINI_API_KEY=your_api_key_here" > .env
   ```

   **Option C: Environment variable**
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

## Usage

Generate a triplet of images with AI:

```bash
# Generate images for a playlist
uv run triptic imgen <name> "<prompt>" -p <playlist>

# Example: Create image set #17 in the animals playlist
uv run triptic imgen 17 "Majestic lion in the savanna" -p animals
```

The command will:
1. Generate three related images (left, center, right perspectives)
2. Save them to `~/.triptic/content/img/<playlist>/<name>.{left,center,right}.png`
3. Add the imageset to the specified playlist
4. Display a URL to preview the triplet in the dashboard

## How It Works

- **Left panel**: Prompt with "(left panel perspective)" added
- **Center panel**: Prompt with "(center panel, main focus)" added  
- **Right panel**: Prompt with "(right panel perspective)" added

This creates a cohesive triptych with subtle variations across the three screens.

## Error Handling

If nano-banana is not installed or no API key is configured:
- The command will fail with a clear error message
- No placeholder images will be created
- You must configure your API key before generating images

## Files

Generated images are stored in:
```
~/.triptic/content/img/<playlist>/<name>.{left,center,right}.png
```

The API key is stored in `.env` (gitignored automatically).
