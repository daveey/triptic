# Triptic API Documentation

Base URL: `https://triptic-daveey.fly.dev` (or `http://localhost:3000` for local development)

## Authentication

Most write operations require HTTP Basic Authentication:
- Username: Set via `TRIPTIC_AUTH_USERNAME` environment variable
- Password: Set via `TRIPTIC_AUTH_PASSWORD` environment variable

Read-only endpoints for screen display (`/config`, `/playlist`, `/content/*`) do not require authentication.

## Data Models

### AssetGroup
An asset group contains three screen assets (left, center, right), each with version history.

```json
{
  "id": "my-asset-group",
  "left": {
    "versions": [AssetVersion, ...],
    "current_version_uuid": "uuid-string",
    "image_url": "/content/assets/{uuid}.png"
  },
  "center": { ... },
  "right": { ... }
}
```

### AssetVersion
A single version of an image with its generation prompt.

```json
{
  "version_uuid": "uuid-string",
  "content": "uuid-string",  // UUID of the actual image file
  "prompt": "Description used to generate this image",
  "timestamp": "2025-01-01T12:00:00.000000"
}
```

### Playlist
A named collection of asset groups displayed in sequence.

```json
{
  "name": "my-playlist",
  "items": [
    {
      "name": "asset-group-name",
      "left": "/content/assets/{uuid}.png",
      "center": "/content/assets/{uuid}.png",
      "right": "/content/assets/{uuid}.png"
    }
  ]
}
```

---

## Asset Group Endpoints

### Get All Asset Groups
```
GET /asset-groups
```

**Response:**
```json
{
  "asset_groups": {
    "group-name": { AssetGroup },
    ...
  }
}
```

### Get Single Asset Group
```
GET /asset-group/{name}
```

**Response:** `AssetGroup` object

### Create Asset Group
```
POST /asset-group/create
Content-Type: application/json

{
  "name": "new-group-name",
  "prompt": "Optional prompt for AI generation"
}
```

**Response:**
```json
{
  "status": "ok",
  "name": "new-group-name"
}
```

### Delete Asset Group
```
DELETE /asset-group/{name}
```

**Response:**
```json
{
  "status": "ok",
  "deleted": "group-name"
}
```

### Rename Asset Group
```
POST /asset-group/{name}/rename
Content-Type: application/json

{
  "newName": "new-name"
}
```

### Duplicate Asset Group
```
POST /asset-group/{name}/duplicate
Content-Type: application/json

{
  "newName": "copy-name"
}
```

---

## Image Operations

### Upload Image
Upload an image file to a specific screen, creating a new version.

```
POST /asset-group/{name}/upload/{screen}
Content-Type: application/octet-stream

[binary image data]
```

**Parameters:**
- `name`: Asset group name
- `screen`: `left`, `center`, or `right`

**Response:**
```json
{
  "status": "ok",
  "uploaded": "center",
  "new_uuid": "uuid-string",
  "image_url": "/content/assets/{uuid}.png"
}
```

### Regenerate Image (AI Generation)
Generate a new image using a text prompt.

```
POST /asset-group/{name}/regenerate/{screen}
Content-Type: application/json

{
  "prompt": "A beautiful sunset over mountains"
}
```

**Response:**
```json
{
  "status": "ok",
  "regenerated": "left"
}
```

### Regenerate with Context
Generate an image using the other two screens as visual context.

```
POST /asset-group/{name}/regenerate-with-context/{screen}
Content-Type: application/json

{
  "contextScreens": ["left", "right"]
}
```

Uses the prompt from the target screen's current version.

### Edit Image (AI Morphing)
Modify an existing image using a text description of changes.

```
POST /asset-group/{name}/edit/{screen}
Content-Type: application/json

{
  "prompt": "Make the sky more purple"
}
```

**Response:**
```json
{
  "status": "ok",
  "edited": "center",
  "new_uuid": "uuid-string",
  "image_url": "/content/assets/{uuid}.png"
}
```

### Flip Image (Horizontal Mirror)
Create a horizontally flipped version of the current image.

```
POST /asset-group/{name}/flip/{screen}
```

**Response:**
```json
{
  "status": "ok",
  "flipped": "left",
  "new_uuid": "uuid-string"
}
```

### Copy Image Between Screens
Copy an image from one screen to another (creates new version in target).

```
POST /asset-group/{name}/copy
Content-Type: application/json

{
  "sourceScreen": "left",
  "targetScreen": "center"
}
```

**Response:**
```json
{
  "status": "ok",
  "copied": {"source": "left", "target": "center"},
  "new_uuid": "uuid-string"
}
```

### Swap Images Between Screens
Swap the current versions and history between two screens.

```
POST /asset-group/{name}/swap
Content-Type: application/json

{
  "screen1": "left",
  "screen2": "right"
}
```

---

## Version Management

### Get Versions for Screen
```
GET /asset-group/{name}/versions/{screen}
```

**Response:**
```json
{
  "versions": [1, 2, 3, 4, 5],
  "currentVersion": 3,
  "prompts": {
    "1": "First prompt",
    "2": "Second prompt",
    ...
  }
}
```

### Set Current Version
Switch to a specific version number.

```
POST /asset-group/{name}/version/{screen}
Content-Type: application/json

{
  "version": 2
}
```

### Delete Version
Delete a specific version (cannot delete current version).

```
POST /asset-group/{name}/delete-version/{screen}
Content-Type: application/json

{
  "version": 3
}
```

---

## Playlist Endpoints

### Get Current Playlist
Returns the currently active playlist for display.

```
GET /playlist
```

**Response:** `Playlist` object

### Get All Playlists
```
GET /playlists
```

**Response:**
```json
{
  "playlists": ["playlist1", "playlist2", ...],
  "current": "playlist1"
}
```

### Set Current Playlist
```
POST /playlist
Content-Type: application/json

{
  "name": "playlist-name"
}
```

### Create Playlist
```
POST /playlist/create
Content-Type: application/json

{
  "name": "new-playlist"
}
```

### Delete Playlist
```
DELETE /playlist/{name}
```

### Rename Playlist
```
POST /playlist/{name}/rename
Content-Type: application/json

{
  "newName": "new-name"
}
```

### Get Playlist Asset Groups
```
GET /playlists/{name}/asset-groups
```

**Response:**
```json
{
  "asset_groups": ["group1", "group2", ...]
}
```

### Reorder Playlist
```
POST /playlists/{name}/reorder
Content-Type: application/json

{
  "asset_groups": ["group2", "group1", "group3"]
}
```

### Remove from Playlist
```
POST /playlists/{name}/remove
Content-Type: application/json

{
  "asset_group": "group-to-remove"
}
```

### Add Asset Group to Playlists
```
POST /asset-group/{name}/add-to-playlists
Content-Type: application/json

{
  "playlists": ["playlist1", "playlist2"]
}
```

---

## Video Generation

### Generate Video from Image
Starts async video generation using Google Veo API.

```
POST /asset-group/{name}/video/{screen}
```

**Response (202 Accepted):**
```json
{
  "status": "processing",
  "job_id": "uuid-string"
}
```

### Check Video Job Status
```
GET /video-job/{job_id}
```

**Response (processing):**
```json
{
  "status": "processing"
}
```

**Response (complete):**
```json
{
  "status": "complete",
  "video_url": "/content/assets/{uuid}.mp4"
}
```

**Response (error):**
```json
{
  "status": "error",
  "error": "Error message"
}
```

---

## Configuration

### Get Config
```
GET /config
```

**Response:**
```json
{
  "frequency": 60
}
```

### Update Config
```
POST /config
Content-Type: application/json

{
  "frequency": 120
}
```

### Get Settings
```
GET /settings
```

### Update Settings
```
POST /settings
Content-Type: application/json

{ ... }
```

---

## Prompt Enhancement

### Fluff Prompt
Enhance a simple prompt with more detail.

```
POST /prompt/fluff
Content-Type: application/json

{
  "prompt": "a cat"
}
```

**Response:**
```json
{
  "fluffed": "A majestic orange tabby cat sitting regally..."
}
```

### Fluff Plus
More aggressive prompt enhancement.

```
POST /prompt/fluff-plus
Content-Type: application/json

{
  "prompt": "a cat"
}
```

### Diff Single Prompt
Generate a variation prompt based on existing prompts.

```
POST /prompt/diff-single
Content-Type: application/json

{
  "prompt": "current prompt",
  "otherPrompts": ["prompt1", "prompt2"]
}
```

---

## Static Content

### Get Image/Video Content
```
GET /content/assets/{uuid}.png
GET /content/assets/{uuid}.mp4
```

Returns the binary image or video file.

---

## State Management

### Get Current Asset Group
Get the currently displayed asset group name.

```
GET /state/current-asset-group
```

**Response:**
```json
{
  "current_asset_group": "group-name"
}
```

### Set Current Asset Group
Jump to display a specific asset group.

```
POST /state/current-asset-group
Content-Type: application/json

{
  "asset_group": "group-name"
}
```

---

## Screen Heartbeat

Screens send periodic heartbeats to indicate they're active.

```
POST /heartbeat/{screen_id}
```

---

## Example: Create and Populate Asset Group

```python
import requests
from requests.auth import HTTPBasicAuth

BASE = "https://triptic-daveey.fly.dev"
auth = HTTPBasicAuth("username", "password")

# 1. Create asset group
requests.post(f"{BASE}/asset-group/create",
    auth=auth,
    json={"name": "my-scene", "prompt": "A peaceful forest"})

# 2. Generate images for each screen
for screen in ["left", "center", "right"]:
    requests.post(f"{BASE}/asset-group/my-scene/regenerate/{screen}",
        auth=auth,
        json={"prompt": f"A peaceful forest, {screen} panel"})

# 3. Add to a playlist
requests.post(f"{BASE}/asset-group/my-scene/add-to-playlists",
    auth=auth,
    json={"playlists": ["main"]})

# 4. Set as current playlist
requests.post(f"{BASE}/playlist",
    auth=auth,
    json={"name": "main"})
```

## Example: Upload Custom Image

```python
# Upload an image file
with open("my-image.png", "rb") as f:
    requests.post(f"{BASE}/asset-group/my-scene/upload/center",
        auth=auth,
        headers={"Content-Type": "application/octet-stream"},
        data=f.read())
```

## Example: Iterate on an Image

```python
# 1. Start with AI generation
requests.post(f"{BASE}/asset-group/my-scene/regenerate/center",
    auth=auth,
    json={"prompt": "A red sports car"})

# 2. Edit to modify
requests.post(f"{BASE}/asset-group/my-scene/edit/center",
    auth=auth,
    json={"prompt": "Change the car color to blue"})

# 3. Flip horizontally
requests.post(f"{BASE}/asset-group/my-scene/flip/center", auth=auth)

# 4. Go back to version 1 if needed
requests.post(f"{BASE}/asset-group/my-scene/version/center",
    auth=auth,
    json={"version": 1})
```
