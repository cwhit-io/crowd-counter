#!/usr/bin/env python3
"""
Update script for crowd-counter application
Pulls latest changes from GitHub and manages the update process
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime

class UpdateManager:
    def __init__(self):
        self.repo_url = "https://github.com/cwhit-io/crowd-counter.git"
        self.app_dir = "/app"
        self.backup_dir = "/app/backup"
        self.branch = "main"
        
    def run_command(self, cmd, check=True):
        """Run shell command and return result"""
        print(f"🔧 Running: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            raise Exception(f"Command failed: {cmd}")
        return result
    
    def create_backup(self):
        """Backup current files"""
        print("📦 Creating backup of current files...")
        os.makedirs(self.backup_dir, exist_ok=True)
        
        for file_pattern in ["*.py", "*.json"]:
            try:
                shutil.copy2(f"{self.app_dir}/{file_pattern}", self.backup_dir)
            except:
                pass  # File might not exist
    
    def init_git_repo(self):
        """Initialize git repository if needed"""
        if not os.path.exists(f"{self.app_dir}/.git"):
            print("🔧 Initializing Git repository...")
            os.chdir(self.app_dir)
            self.run_command("git init")
            self.run_command(f"git remote add origin {self.repo_url}")
        else:
            os.chdir(self.app_dir)
    
    def check_for_updates(self):
        """Check if updates are available"""
        print("⬇️ Checking for updates...")
        self.run_command(f"git fetch origin {self.branch}")
        
        try:
            local_commit = self.run_command("git rev-parse HEAD").stdout.strip()
        except:
            local_commit = ""
            
        remote_commit = self.run_command(f"git rev-parse origin/{self.branch}").stdout.strip()
        
        return local_commit != remote_commit, local_commit, remote_commit
    
    def apply_updates(self):
        """Apply the updates"""
        print("🔄 Applying updates...")
        
        # Check for local changes
        result = self.run_command("git diff --quiet", check=False)
        if result.returncode != 0:
            print("💾 Stashing local changes...")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.run_command(f"git stash push -m 'Auto-stash before update {timestamp}'")
        
        # Apply updates
        self.run_command(f"git reset --hard origin/{self.branch}")
    
    def show_changes(self):
        """Show recent changes"""
        print("📋 Recent changes:")
        result = self.run_command("git log --oneline -5", check=False)
        print(result.stdout)
    
    def update(self):
        """Main update process"""
        try:
            print("🔄 Starting update process...")
            
            self.create_backup()
            self.init_git_repo()
            
            has_updates, local_commit, remote_commit = self.check_for_updates()
            
            if not has_updates:
                print("✅ Already up to date!")
                return True
            
            print(f"🔄 Updates available. Updating from {local_commit[:8]} to {remote_commit[:8]}...")
            self.apply_updates()
            self.show_changes()
            
            print("✅ Update completed successfully!")
            print("🔄 Restart the container to apply changes:")
            print("   docker restart crowd-counter")
            
            return True
            
        except Exception as e:
            print(f"❌ Update failed: {e}")
            return False

if __name__ == "__main__":
    updater = UpdateManager()
    success = updater.update()
    sys.exit(0 if success else 1)