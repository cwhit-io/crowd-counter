#!/bin/bash

# Update script for crowd-counter application
# This script pulls the latest changes from GitHub and restarts the application

set -e  # Exit on any error

echo "🔄 Starting update process..."

# Configuration
REPO_URL="https://github.com/cwhit-io/crowd-counter.git"
APP_DIR="/app"
BACKUP_DIR="/app/backup"
BRANCH="main"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup current files
echo "📦 Creating backup of current files..."
cp -r "$APP_DIR"/*.py "$BACKUP_DIR/" 2>/dev/null || true
cp -r "$APP_DIR"/*.json "$BACKUP_DIR/" 2>/dev/null || true

# Initialize git repo if not already done
if [ ! -d "$APP_DIR/.git" ]; then
    echo "🔧 Initializing Git repository..."
    cd "$APP_DIR"
    git init
    git remote add origin "$REPO_URL"
else
    cd "$APP_DIR"
fi

# Fetch latest changes
echo "⬇️ Fetching latest changes from GitHub..."
git fetch origin "$BRANCH"

# Check if there are updates
LOCAL_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
REMOTE_COMMIT=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo "✅ Already up to date!"
    exit 0
fi

echo "🔄 Updates available. Updating..."

# Backup any local changes
if ! git diff --quiet 2>/dev/null; then
    echo "💾 Stashing local changes..."
    git stash push -m "Auto-stash before update $(date)"
fi

# Pull the latest changes
git reset --hard "origin/$BRANCH"

echo "✅ Update completed successfully!"
echo "📄 Updated to commit: $REMOTE_COMMIT"

# Optional: Show what changed
echo "📋 Recent changes:"
git log --oneline -5

echo "🔄 Restart the container to apply changes:"
echo "   docker restart crowd-counter"