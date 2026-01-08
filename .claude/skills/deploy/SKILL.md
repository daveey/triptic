---
name: deploy
description: Deploy the triptic application to production. Runs tests, checks for uncommitted changes, commits if needed, deploys to Fly.io, and verifies the deployment.
allowed-tools: Read, Bash, Grep, Glob
---

# Deploy Triptic

Deploy the triptic application to production after running tests and verifying everything works.

## Workflow

When the user runs `/deploy`, execute these steps in order:

### Step 1: Run Unit Tests

```bash
uv run pytest tests/ -v --tb=short
```

**STOP if any tests fail.** Report the failures to the user and do not proceed with deployment.

### Step 2: Check for Uncommitted Changes

```bash
git status --porcelain
```

If there are uncommitted changes, show them to the user and ask if they want to:
- Commit and deploy
- Deploy without committing (not recommended)
- Cancel

### Step 3: Commit Changes (if requested)

```bash
git add -A
git commit -m "$(cat <<'EOF'
<commit message based on changes>

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
git push
```

### Step 4: Deploy to Fly.io

```bash
fly deploy
```

Wait for deployment to complete. Check for any errors in the output.

### Step 5: Verify Deployment

Run these health checks against production:

```bash
# Check server is responding
curl -s -u "daveey:daviddavid" "https://triptic-daveey.fly.dev/config" | jq

# Check playlist endpoint works
curl -s -u "daveey:daviddavid" "https://triptic-daveey.fly.dev/playlist" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Playlist: {d[\"name\"]}, Items: {len(d[\"items\"])}')"

# Check asset groups are accessible
curl -s -u "daveey:daviddavid" "https://triptic-daveey.fly.dev/asset-groups" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Asset groups: {len(d[\"asset_groups\"])}')"
```

### Step 6: Report Results

Summarize:
- Test results (passed/failed)
- What was deployed (commit hash if applicable)
- Health check results
- Any warnings or issues

## Configuration

```bash
TRIPTIC_URL=https://triptic-daveey.fly.dev
TRIPTIC_AUTH_USERNAME=daveey
TRIPTIC_AUTH_PASSWORD=daviddavid
```

## Rollback

If deployment fails or issues are detected, roll back with:

```bash
fly releases -a triptic-daveey
fly deploy -i <previous-image>
```

## Quick Deploy (skip tests)

If the user explicitly requests to skip tests:

```bash
fly deploy
```

But always warn that this is not recommended.
