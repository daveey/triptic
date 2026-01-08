---
name: triptic
description: Generate AI art for the Triptic display system. Use this when the user wants to create new asset groups or playlists with generated images. Supports creating single asset groups from a theme/concept, or entire playlists with multiple themed asset groups.
allowed-tools: Read, Write, Bash, Grep, Glob
---

# Triptic Asset Generation

Generate AI-generated triptych artwork for the Triptic display system.

## Capabilities

1. **Single Asset Group**: Create one asset group from a theme (e.g., "cyberpunk city")
2. **Full Playlist**: Create a playlist with multiple themed asset groups
3. **Add to Existing Playlist**: Add new asset groups that match the playlist's style

## API Endpoints

The Triptic server provides these endpoints (requires Basic Auth):

### Create Asset Group from Prompt
```
POST /asset-group/create-from-prompt
Content-Type: application/json

{
  "prompt": "detailed style and theme description",
  "name": "optional-custom-name",
  "playlist": "optional-playlist-name"
}
```

**Parameters:**
- `prompt`: The full description including style, theme, and visual elements
- `name`: Custom asset group ID (optional, otherwise generated from prompt)
- `playlist`: Playlist to add the asset group to (optional)

Response:
```json
{
  "status": "ok",
  "asset_group_id": "custom-name-or-slugified-prompt",
  "prompts": {
    "left": "generated prompt for left panel",
    "center": "generated prompt for center panel",
    "right": "generated prompt for right panel"
  },
  "queued": [...]
}
```

### Get Playlist Asset Groups
```
GET /playlists/{playlist-name}/asset-groups
```

### Get Asset Group Details
```
GET /asset-group/{id}
```

### Create Playlist
```
POST /playlist/create
Content-Type: application/json

{
  "name": "playlist-name"
}
```

### Add Asset Group to Playlist
```
POST /asset-group/{id}/add-to-playlists
Content-Type: application/json

{
  "playlists": ["playlist-name"]
}
```

## CRITICAL: Matching Playlist Style

**When adding to an existing playlist, you MUST first check the playlist's style and match it.**

### Step 1: Identify Existing Playlist Style

Before adding to any existing playlist, fetch a sample of existing asset groups to understand the style:

```bash
# Get list of asset groups in the playlist
curl -s "https://triptic-daveey.fly.dev/playlists/PLAYLIST_NAME/asset-groups" \
  -u "$TRIPTIC_AUTH_USERNAME:$TRIPTIC_AUTH_PASSWORD"
```

### Step 2: Analyze the Naming Convention

Look at existing asset group names in the playlist:
- `animal-nouveau` playlist has: `nouveau-peacock`, `nouveau-swan`, `nouveau-dragon`, etc.
- Pattern: `nouveau-{animal}` with Art Nouveau artistic style

### Step 3: Craft a Style-Appropriate Prompt

The `prompt` parameter must include the FULL style description, not just the subject. Examples:

**BAD** (missing style):
```json
{"prompt": "platypus", "name": "nouveau-platypus", "playlist": "animal-nouveau"}
```
This will generate generic platypus images that don't match the Art Nouveau style.

**GOOD** (includes full style):
```json
{
  "prompt": "platypus in Art Nouveau style, ornate decorative borders, flowing organic lines, Alphonse Mucha inspired, elegant natural forms, muted earth tones with gold accents",
  "name": "nouveau-platypus",
  "playlist": "animal-nouveau"
}
```

### Known Playlist Styles

| Playlist | Style Description | Naming Pattern |
|----------|-------------------|----------------|
| `animal-nouveau` | Art Nouveau style, ornate decorative borders, flowing organic lines, Alphonse Mucha inspired, elegant natural forms, muted earth tones with gold accents | `nouveau-{animal}` |
| `surreal` | Surrealist art, dreamlike, Salvador Dali / Magritte inspired | `surreal-{theme}` |

**Always ask for clarification if the playlist style is unknown.**

## Instructions

When the user invokes `/triptic`:

### 1. Parse the Request

Determine if the user wants:
- A **single asset group**: They mention one theme/concept
- A **playlist**: They mention "playlist" or want multiple related themes
- **Add to existing playlist**: They specify an existing playlist name

### 2. For Adding to Existing Playlist

**ALWAYS check the playlist style first:**

a. Fetch existing asset groups to understand the style
b. Match the naming convention (e.g., `nouveau-{subject}`)
c. Include the full style description in the prompt
d. Use the `name` parameter for consistent naming

```bash
curl -s -X POST "https://triptic-daveey.fly.dev/asset-group/create-from-prompt" \
  -H "Content-Type: application/json" \
  -u "$TRIPTIC_AUTH_USERNAME:$TRIPTIC_AUTH_PASSWORD" \
  -d '{
    "prompt": "SUBJECT in FULL_STYLE_DESCRIPTION",
    "name": "style-prefix-subject",
    "playlist": "existing-playlist"
  }'
```

### 3. For Single Asset Group (New Style)

Call the API to create the asset group:

```bash
curl -s -X POST "https://triptic-daveey.fly.dev/asset-group/create-from-prompt" \
  -H "Content-Type: application/json" \
  -u "$TRIPTIC_AUTH_USERNAME:$TRIPTIC_AUTH_PASSWORD" \
  -d '{"prompt": "USER_THEME", "playlist": "OPTIONAL_PLAYLIST"}'
```

### 4. For Playlist Generation

a. First, brainstorm 5-10 creative theme variations based on the user's description
b. Decide on a consistent style and naming convention
c. Create the playlist:
```bash
curl -s -X POST "https://triptic-daveey.fly.dev/playlist/create" \
  -H "Content-Type: application/json" \
  -u "$TRIPTIC_AUTH_USERNAME:$TRIPTIC_AUTH_PASSWORD" \
  -d '{"name": "playlist-name"}'
```

d. For each theme, create an asset group with consistent style:
```bash
curl -s -X POST "https://triptic-daveey.fly.dev/asset-group/create-from-prompt" \
  -H "Content-Type: application/json" \
  -u "$TRIPTIC_AUTH_USERNAME:$TRIPTIC_AUTH_PASSWORD" \
  -d '{
    "prompt": "SUBJECT in CONSISTENT_STYLE_DESCRIPTION",
    "name": "style-prefix-subject",
    "playlist": "playlist-name"
  }'
```

### 5. Report Results

After creation, summarize:
- Playlist name (if created)
- Number of asset groups created
- List of themes/prompts generated
- Note that images are queued for generation

## Examples

### Example 1: Add to Existing Playlist (animal-nouveau)
User: `/triptic add platypus to animal-nouveau`

Action:
1. Recognize `animal-nouveau` uses Art Nouveau style
2. Create with full style prompt:
```json
{
  "prompt": "platypus in Art Nouveau style, ornate decorative borders, flowing organic lines, Alphonse Mucha inspired, elegant natural forms, muted earth tones with gold accents",
  "name": "nouveau-platypus",
  "playlist": "animal-nouveau"
}
```

### Example 2: New Playlist
User: `/triptic create a playlist of cyberpunk cityscapes`

Action:
1. Create playlist "cyberpunk-cities"
2. Define consistent style: "cyberpunk cityscape, neon lights, rain-slicked streets, holographic advertisements, dark atmosphere, Blade Runner inspired"
3. Generate variations with consistent style:
   - `{"prompt": "Tokyo in cyberpunk style, neon lights...", "name": "cyberpunk-tokyo", "playlist": "cyberpunk-cities"}`
   - `{"prompt": "New York in cyberpunk style, neon lights...", "name": "cyberpunk-newyork", "playlist": "cyberpunk-cities"}`
   - etc.

### Example 3: Single Asset Group
User: `/triptic a peaceful zen garden with cherry blossoms`

Action: Create one asset group with that theme (no playlist style to match).

## Server Configuration

Production URL: `https://triptic-daveey.fly.dev`
Local development: `http://localhost:3000`

Authentication requires `TRIPTIC_AUTH_USERNAME` and `TRIPTIC_AUTH_PASSWORD` environment variables.

Read credentials from `.env` file if environment variables are not set.
