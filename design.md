# Triptic Architecture Documentation

## Project Overview

**Project Name**: Triptic (internally named "EO Player")
**Purpose**: Time-based image display application for triptych installations
**Technology**:
- Frontend: Vanilla JavaScript (bypasses included React scaffold)
- Backend: Python (for LLM API calls and dynamic content generation)
**Target Hardware**: Portrait displays (1080×1920 pixels)

The application displays different images based on the current minute, cycling through 6 images per hour (one image every 10 minutes). It's designed to run on multiple synchronized screens that can display different image sets. The Python backend enables dynamic content generation using LLM APIs for future enhancements.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User/Browser                      │
│          (Accesses URL with screen ID)              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              Railway Deployment                     │
│    Node.js (serve) + Python Backend                │
└────────┬────────────────────────────────────┬───────┘
         │                                    │
         ▼                                    ▼
┌────────────────────────┐    ┌────────────────────────────┐
│  Static File Server    │    │  Python Backend            │
│  (serve package)       │    │  src/triptic/              │
│                        │    │                            │
│  Serves:               │    │  - LLM API integration     │
│  - public/index.html   │    │  - Dynamic content gen     │
│  - public/img/*        │    │  - Future API endpoints    │
└──────────┬─────────────┘    └────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│           public/index.html                         │
│       (Vanilla JavaScript Application)              │
│                                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  1. Parse URL for screen ID                  │ │
│  │  2. Load 6 images for that screen            │ │
│  │  3. Calculate current minute % 6             │ │
│  │  4. Display appropriate image                │ │
│  │  5. Refresh every 100ms                      │ │
│  │  6. (Future) Fetch dynamic content via API   │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              Static Image Assets                    │
│           public/img/[screenId]/                    │
│           1.png, 2.png ... 6.png                    │
│        (Future: dynamically generated)              │
└─────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Entry Point: `public/index.html`

**Location**: `/public/index.html`
**Responsibility**: Single-file application that handles all image display logic

**Core Functions**:

- **`onLoad()`** (line 39): Initialization function
  - Calls `loadImages()` to preload all 6 images
  - Sets up 100ms interval to check if images are loaded and display current image

- **`loadImages()`** (line 12): Image preloader
  - Creates 6 invisible `<img>` elements (0x0 size)
  - Loads images from `img/${screenId}/1.png` through `6.png`
  - Tracks loading progress via `numImagesLoaded` counter

- **`displayImage()`** (line 34): Display logic
  - Calculates image index: `(new Date()).getMinutes() % imageUrls.length`
  - Calls `setBackground()` with the selected image URL

- **`setBackground(imgUrl)`** (line 28): Rendering function
  - Sets HTML element background with `background-size: cover`
  - Applies: `no-repeat center center fixed` for full-screen display

**URL Routing**:
```javascript
let screenId = document.URL.split("#")[1] || "";
```
- `http://localhost:3000/#center` → loads from `img/center/`
- `http://localhost:3000/#left` → loads from `img/left/`
- `http://localhost:3000/` → loads from `img/` (root)

### 2. Image Asset Structure

**Location**: `/public/img/`

**Organization**:
```
public/img/
├── 1.png through 6.png       # Default/root screen images
├── center/                   # Center screen images
│   └── 1.png through 6.png
├── left/                     # Left screen images
│   └── 1.png through 6.png
└── right/                    # Right screen images
    └── 1.png through 6.png
```

**Design Requirements**:
- Fixed resolution: 1080×1920 pixels (portrait orientation)
- 6 images per set (displayed in 10-minute rotations per hour)

### 3. Unused React Scaffold

**Location**: `/src/` directory

**Status**: Dormant/Unused

The project was bootstrapped with Create React App but the React rendering is commented out:

**File**: `src/index.js` (lines 7-12)
```javascript
// ReactDOM.render(
//   <React.StrictMode>
//     <App />
//   </React.StrictMode>,
//   document.getElementById('root')
// );
```

**Components Present but Unused**:
- `src/index.js` - React entry point (disabled)
- `src/App.js` - Main React component (not rendered)
- `src/App.test.js` - Tests
- `src/setupTests.js` - Test configuration
- `src/reportWebVitals.js` - Performance monitoring (only this runs)

**Note**: The React scaffold remains for potential future use but is completely bypassed in the current implementation.

### 4. Python Backend

**Location**: `/src/triptic/` directory

**Status**: Active - Hybrid Architecture

The project includes a Python backend for future dynamic content generation and LLM API integration. This enables the application to evolve beyond static images.

**Current Files**:
- `src/triptic/__init__.py` - Package initialization
- `src/triptic/main.py` - Entry point for Python services

**Configuration**:
- `pyproject.toml` - Python project configuration using `uv` for package management
- `requirements.txt` - (Future) Dependencies for LLM APIs (OpenAI, Anthropic, etc.)

**Planned Features**:
- LLM API integration for dynamic content generation
- Image generation pipeline for creating triptych content
- API endpoints for content management
- Scheduled content updates

**Deployment Strategy**:
The hybrid architecture will be deployed on Railway with:
- Node.js process serving static files (via `serve` package)
- Python process running backend services
- Shared file system for generated images

---

## Data Flow

```
┌─────────────────────────────────────────────────────┐
│  User Opens URL: http://domain.com/#center          │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Parse URL Hash → screenId = "center"               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Build Image URLs Array:                            │
│  ["img/center/1.png", ... "img/center/6.png"]      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Preload All 6 Images (async)                       │
│  Track loading: numImagesLoaded++                   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Every 100ms Check:                                 │
│  if (numImagesLoaded == 6) { displayImage() }      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Get Current Minute (0-59)                          │
│  Calculate Index: minute % 6                        │
│  Example: 13:27 → 27 % 6 = 3 → Display 4.png       │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Set Background Image (full-screen, cover mode)     │
└─────────────────────────────────────────────────────┘
```

**Time-to-Image Mapping**:
- Minutes 0-9, 10-19, 20-29, 30-39, 40-49, 50-59
- Display images 1.png, 2.png, 3.png, 4.png, 5.png, 6.png respectively

---

## API Endpoints

**Current**: None - The frontend is currently a static application with no backend API. All functionality is client-side JavaScript with static image assets.

**Future Python API Endpoints** (Planned):
- `POST /api/generate` - Generate new triptych images using LLM APIs
- `GET /api/content` - Retrieve current content metadata
- `POST /api/schedule` - Schedule content updates
- `GET /api/health` - Health check for Python backend

---

## Build & Deploy Process

### Development Mode

**Command**: `npm run dev` (package.json:17)

**Process**:
1. Uses `react-scripts start`
2. Starts development server on `http://localhost:3000`
3. Hot-reload enabled for development

**Command**: `npm start` (package.json:19)

**Process**:
1. Uses `serve public -l ${PORT:-3000}`
2. Serves static files from `public/` directory
3. Listens on Railway's `$PORT` or defaults to 3000

### Production Deployment (Railway)

**Platform**: Railway.app

**Configuration Files**:

1. **`railway.json`**:
   - Build system: NIXPACKS
   - Start command: `npm start`
   - Restart policy: ON_FAILURE (max 10 retries)

2. **`nixpacks.toml`**:
   - Runtime: Node.js 18.x
   - Install: `npm ci` (clean install from package-lock.json)
   - Start: `npm start`

3. **`Procfile`**:
   - Web process: `npm start`

4. **`package.json`**:
   - Build script: `echo 'No build needed for static site'` (no compilation)
   - Start script: Serves `public/` directory via `serve` package

**Deployment Steps**:
1. Push code to GitHub
2. Railway auto-detects configuration
3. Installs dependencies via `npm ci`
4. Starts static file server via `serve`
5. Assigns public URL (e.g., `https://your-app.railway.app`)

**Port Handling**:
- Railway provides `$PORT` environment variable
- App listens on `${PORT:-3000}` (Railway port or 3000 fallback)

---

## Technical Details

### Fixed Viewport
```css
body {
  width: 1080px;
  height: 1920px;
}
```
- No responsive design
- Optimized for portrait displays
- Full-screen background rendering

### Image Display Timing
- **Update Frequency**: Checks every 100ms for loaded images
- **Image Duration**: ~10 minutes per image (6 images per hour)
- **Synchronization**: All screens synced by system clock (minute-based)

### Browser Compatibility
- Uses standard ES5/ES6 JavaScript
- No modern framework dependencies
- Compatible with all modern browsers

---

## Technical Debt & Known Issues

### 1. Unused React Scaffold
**Issue**: Entire `src/` directory and React dependencies are unused
**Impact**:
- Increases repository size unnecessarily
- Confusing for new developers (which codebase is active?)
- Additional dependencies in `package.json` (react, react-dom, react-scripts)

**Recommendation**:
- Remove React dependencies and `src/` directory
- Convert to pure static HTML project
- Or integrate React properly if future features require it

### 2. Polling-Based Display Updates
**Issue**: Uses `setInterval(displayImage, 100)` polling every 100ms
**Impact**:
- Unnecessary CPU/battery usage
- 100ms polling for something that changes every 10 minutes

**Recommendation**:
- Calculate milliseconds until next minute change
- Use `setTimeout` to wake up at the exact minute boundary
- Only poll during image loading phase

### 3. No Error Handling
**Issue**: No fallback if images fail to load
**Impact**:
- App hangs if any image fails to load (`numImagesLoaded` never reaches 6)
- No user feedback for missing images or network errors

**Recommendation**:
- Add `onerror` handlers to image loading
- Implement loading timeout
- Show error state or fallback image

### 4. Hardcoded Image Count
**Issue**: Image count (6) is hardcoded in multiple places
**Impact**: Changing the number of images requires code changes in loop logic

**Recommendation**:
- Make image count configurable
- Store in config object or data attribute

### 5. No Build Step
**Issue**: Build script echoes 'No build needed for static site' (package.json:18)
**Impact**:
- Cannot use modern JavaScript features (ES modules, optional chaining)
- No minification or optimization
- No asset pipeline for images

**Recommendation**:
- Either embrace zero-build with explicit documentation
- Or add lightweight build step (esbuild, Vite) for modern JS

### 6. Inconsistent Naming
**Issue**:
- Project called "Triptic" but HTML title is "EO Player"
- Package name is "amplifyapp" (package.json:2)
- References to "Game of Life" in RAILWAY_DEPLOY.md

**Recommendation**: Standardize all naming to "Triptic"

### 7. Documentation Discrepancies
**Issue**: README.md is generic Create React App documentation, doesn't reflect actual architecture

**Recommendation**: Replace README.md with accurate project documentation

---

## Future Enhancement Opportunities

1. **Configuration System**: JSON config for screen IDs, image counts, and timing
2. **Admin Panel**: Web interface to upload images and configure screens
3. **Transition Effects**: Fade or crossfade between images
4. **Health Monitoring**: Report screen status to central dashboard
5. **Dynamic Content**: Support for video or animated content
6. **Time-Based Playlists**: Different images for different times of day/week
7. **Content Management**: Backend API for managing image sets

---

## Quick Reference

### Start Development

**Frontend (Node.js)**:
```bash
npm install
npm run dev          # Development mode with hot reload
npm start            # Production-like static server
```

**Backend (Python)**:
```bash
uv pip install -e ".[dev]"   # Install with dev dependencies
python -m triptic.main       # Run Python backend
```

### Deploy to Railway
```bash
railway login
railway init
railway up
```

### Access Screens
- Center: `http://localhost:3000/#center`
- Left: `http://localhost:3000/#left`
- Right: `http://localhost:3000/#right`
- Default: `http://localhost:3000/`

### Add New Screen
1. Create directory: `public/img/[screen-id]/`
2. Add images: `1.png` through `6.png` (1080×1920px)
3. Access: `http://localhost:3000/#[screen-id]`

---

## File Structure Summary

```
/
├── .git/                      # Git repository
├── .github/                   # GitHub settings
├── .aegis/                    # Aegis configuration
├── docs/
│   └── (documentation files)
├── public/                    # Static assets (served by app)
│   ├── index.html            # Main application (ACTIVE)
│   ├── img/                  # Image assets
│   │   ├── 1.png-6.png      # Default screen images
│   │   ├── center/          # Center screen images (1-6.png)
│   │   ├── left/            # Left screen images (1-6.png)
│   │   └── right/           # Right screen images (1-6.png)
│   ├── favicon.ico
│   ├── logo192.png
│   ├── logo512.png
│   ├── manifest.json
│   └── robots.txt
├── src/                       # Python backend (ACTIVE)
│   └── triptic/
│       ├── __init__.py       # Package initialization
│       └── main.py           # Python entry point
├── tests/                     # Python tests
├── package.json               # Node.js dependencies and scripts
├── pyproject.toml            # Python project configuration
├── railway.json               # Railway deployment config
├── nixpacks.toml             # Railway build config (Node.js)
├── Procfile                  # Process definition for Railway
├── design.md                 # This architecture documentation
└── README.md                 # Project documentation
```

---

## Architecture Decisions

### Why Vanilla JavaScript?
- **Simplicity**: No build step, no framework overhead
- **Performance**: Minimal bundle size, instant page load
- **Reliability**: Fewer dependencies, less breaking changes
- **Maintenance**: Easy for non-React developers to understand

### Why Not Remove React Entirely?
- **Future Flexibility**: React scaffold may be useful for admin panel
- **Low Cost**: React files don't impact production runtime
- **Create React App Tools**: Useful for testing and development utilities

### Why Railway Instead of Static Hosting?
- **Simplicity**: One-command deployment
- **Process Management**: Automatic restarts on failure
- **Environment Variables**: Easy configuration management
- **Logs**: Built-in logging and monitoring
- **Hybrid Support**: Can run both Node.js and Python processes

### Why Hybrid Architecture (Node.js + Python)?
- **Specialized Tools**: Node.js excels at serving static files, Python excels at LLM APIs
- **Future Flexibility**: Python backend enables dynamic content generation without rebuilding frontend
- **Separation of Concerns**: Frontend display logic separate from backend content generation
- **Development Experience**: Each team can work in their preferred language
- **Package Management**: Using `uv` for Python ensures fast, reliable dependency management

---

## Conclusion

Triptic is a hybrid application for synchronized triptych displays, combining a minimalist vanilla JavaScript frontend with a Python backend for future dynamic content generation. The architecture prioritizes simplicity for the display layer while maintaining flexibility for content generation through LLM APIs. Current focus is on reliable image display, with the Python backend prepared for future enhancements in dynamic content creation.

